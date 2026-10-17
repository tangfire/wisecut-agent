<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from "vue";
import { useRoute } from "vue-router";
import { runApi, artifactApi, assetApi, createSSEConnection, type Run, type SSEEvent, type Artifact, type Asset } from "../../api/client";
import InteractionCard from "../../components/InteractionCard.vue";

const route = useRoute();
const projectId = route.params.projectId as string;
const runId = route.query.runId as string | undefined;

const run = ref<Run | null>(null);
const events = ref<SSEEvent[]>([]);
const interactions = ref<SSEEvent[]>([]);
const artifacts = ref<Artifact[]>([]);
const availableAssets = ref<Asset[]>([]);
const error = ref("");
const connected = ref(false);
const reconnecting = ref(false);
let disconnect: (() => void) | null = null;
let lastSeq = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

const isTerminal = computed(() =>
  run.value && ["completed", "failed", "cancelled"].includes(run.value.status)
);

const finalVideo = computed(() =>
  artifacts.value.find((a) => a.artifact_type === "final_video")
);

onMounted(async () => {
  if (runId) {
    try {
      run.value = await runApi.get(runId);
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : "Failed to load run";
    }
  }
  try {
    const assetList = await assetApi.list(projectId);
    availableAssets.value = assetList.items;
  } catch { /* non-critical */ }
  connectSSE();
});

onUnmounted(() => {
  disconnect?.();
  if (reconnectTimer) clearTimeout(reconnectTimer);
});

function connectSSE() {
  if (!runId) return;

  disconnect?.();
  disconnect = createSSEConnection(
    runId,
    lastSeq,
    (event) => {
      connected.value = true;
      reconnecting.value = false;
      const seq = Number(event.data.seq) || 0;
      if (seq <= lastSeq) return; // dedupe
      lastSeq = Math.max(lastSeq, seq);
      events.value.push(event);

      if (event.event === "interaction.requested") {
        interactions.value.push(event);
      }

      if (event.event === "artifact.created") {
        artifactApi.get(String(event.data.artifact_id || "")).then((a) => {
          artifacts.value.push(a);
        }).catch(() => { /* ignore */ });
      }

      if (["run.completed", "run.failed", "run.cancelled"].includes(event.event)) {
        if (run.value) run.value.status = event.event.replace("run.", "");
        disconnect?.();
      }
    },
    () => {
      connected.value = false;
      // Auto-reconnect with after_seq for SSE 断线续传
      if (!isTerminal.value) {
        reconnecting.value = true;
        reconnectTimer = setTimeout(() => connectSSE(), 3000);
      }
    },
  );
}

async function respondToInteraction(interactionEvent: SSEEvent, action: string) {
  const interactionId = interactionEvent.data.interaction_id as string;
  try {
    // Optimistic: remove card immediately
    interactions.value = interactions.value.filter((i) => i !== interactionEvent);
    await runApi.respondToInteraction(interactionId, { action, content: {} });
    // Reconnect to receive new events
    connectSSE();
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Failed to respond";
    // Put back on error
    interactions.value.push(interactionEvent);
  }
}

async function cancelRun() {
  if (!runId) return;
  try {
    await runApi.cancel(runId);
    if (run.value) run.value.status = "cancelling";
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Failed to cancel";
  }
}

async function downloadArtifact(artifactId: string) {
  try {
    const { download_url } = await artifactApi.downloadUrl(artifactId);
    window.open(download_url, "_blank");
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Download failed";
  }
}

async function retryRun() {
  // Navigate to project to start new run
  window.location.href = `/projects/${projectId}`;
}

function getEventLabel(event: SSEEvent): string {
  const type = event.event;
  const map: Record<string, string> = {
    "run.started": "▶ Run started",
    "run.phase_changed": "📋 Phase changed",
    "interaction.requested": "⏸ Waiting for your input",
    "interaction.resolved": "✅ Input received",
    "tool.started": "🔧 Tool started",
    "tool.completed": "🔧 Tool completed",
    "tool.failed": "🔧 Tool failed",
    "artifact.created": "📦 Artifact created",
    "business.message": "💬 Message",
    "assistant.delta": "💬 Assistant",
    "assistant.message": "💬 Assistant",
    "run.completed": "✅ Run completed",
    "run.failed": "❌ Run failed",
    "run.cancelled": "⏹ Run cancelled",
  };
  return map[type] || type;
}
</script>

<template>
  <div class="workbench">
    <div class="page-header">
      <div>
        <router-link :to="`/projects/${projectId}`" class="back-link">← Project</router-link>
        <h1>Workbench</h1>
      </div>
      <div class="status-area">
        <span v-if="connected" class="badge live">● Live</span>
        <span v-else-if="reconnecting" class="badge reconnecting">● Reconnecting...</span>
        <span v-else class="badge offline">● Disconnected</span>
        <span v-if="run" class="badge" :class="run.status">{{ run.status }}</span>
        <button v-if="run && ['running', 'queued'].includes(run.status)" @click="cancelRun" class="btn-cancel">
          Cancel Run
        </button>
        <button v-if="isTerminal && run?.status === 'failed'" @click="retryRun" class="btn-retry">
          ↻ Retry
        </button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <!-- Interaction Cards -->
    <div v-if="interactions.length > 0" class="interactions">
      <InteractionCard
        v-for="interaction in interactions"
        :key="String(interaction.data.interaction_id)"
        :interaction="interaction"
        @approve="respondToInteraction(interaction, 'approve')"
        @cancel="respondToInteraction(interaction, 'cancel')"
        @edit="() => respondToInteraction(interaction, 'edit')"
      />
    </div>

    <!-- Video Preview -->
    <section v-if="finalVideo" class="section video-section">
      <h2>Final Video</h2>
      <div class="video-preview">
        <video v-if="finalVideo.uri" :src="finalVideo.uri" controls class="video-player"></video>
        <div class="video-actions">
          <button @click="downloadArtifact(finalVideo.id)" class="btn-primary">⬇ Download</button>
        </div>
      </div>
    </section>

    <!-- Artifacts -->
    <section v-if="artifacts.length > 0" class="section">
      <h2>Artifacts ({{ artifacts.length }})</h2>
      <div class="artifact-list">
        <div v-for="a in artifacts" :key="a.id" class="artifact-item">
          <span class="artifact-type">{{ a.artifact_type }}</span>
          <span class="artifact-status" :class="a.status">{{ a.status }}</span>
          <button @click="downloadArtifact(a.id)" class="btn-small">Download</button>
        </div>
      </div>
    </section>

    <!-- Available Assets -->
    <section v-if="availableAssets.length > 0" class="section">
      <h2>Project Assets</h2>
      <div class="asset-grid">
        <div v-for="a in availableAssets" :key="a.id" class="asset-card">
          <span class="asset-name">{{ a.name }}</span>
          <span class="asset-type">{{ a.asset_type }}</span>
        </div>
      </div>
    </section>

    <!-- Event Timeline -->
    <section class="section">
      <h2>Event Timeline</h2>
      <div v-if="events.length === 0" class="empty-text">
        Waiting for events... {{ runId ? "" : "No run selected." }}
      </div>
      <div v-else class="timeline">
        <div
          v-for="(event, i) in events"
          :key="i"
          class="timeline-item"
          :class="event.event"
        >
          <div class="timeline-time">
            {{ new Date().toLocaleTimeString() }}
          </div>
          <div class="timeline-content">
            <strong>{{ getEventLabel(event) }}</strong>
            <pre v-if="event.event === 'business.message'" class="event-data">{{ JSON.stringify(event.data, null, 2) }}</pre>
            <pre v-if="event.event === 'artifact.created'" class="event-data">{{ JSON.stringify(event.data, null, 2) }}</pre>
            <pre v-if="event.event === 'tool.failed'" class="event-data error-data">{{ JSON.stringify(event.data, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.workbench { max-width: 960px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; flex-wrap: wrap; gap: 12px; }
.back-link { font-size: 13px; color: #1a73e8; text-decoration: none; }
.page-header h1 { font-size: 24px; margin-top: 4px; }
.status-area { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.badge { font-size: 12px; padding: 4px 10px; border-radius: 12px; background: #eee; }
.badge.live { background: #e8f5e9; color: #2e7d32; }
.badge.offline { background: #fce4ec; color: #c62828; }
.badge.reconnecting { background: #fff3e0; color: #e65100; }
.badge.running, .badge.queued { background: #e3f2fd; color: #1565c0; }
.badge.completed { background: #e8f5e9; color: #2e7d32; }
.badge.failed { background: #fce4ec; color: #c62828; }
.btn-cancel { padding: 6px 14px; background: #fff; color: #d93025; border: 1px solid #d93025; border-radius: 6px; font-size: 13px; cursor: pointer; }
.btn-retry { padding: 6px 14px; background: #1a73e8; color: #fff; border: none; border-radius: 6px; font-size: 13px; cursor: pointer; }
.error { color: #d93025; margin-bottom: 16px; }
.interactions { margin-bottom: 24px; }
.section { background: #fff; border-radius: 8px; padding: 24px; border: 1px solid #e0e0e0; margin-bottom: 16px; }
.section h2 { font-size: 18px; margin-bottom: 16px; }
.empty-text { color: #888; font-size: 14px; padding: 20px; text-align: center; }
.video-player { width: 100%; max-height: 480px; border-radius: 8px; background: #000; }
.video-actions { margin-top: 12px; }
.btn-primary { padding: 8px 16px; background: #1a73e8; color: #fff; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; }
.artifact-list { display: flex; flex-direction: column; gap: 8px; }
.artifact-item { display: flex; align-items: center; gap: 12px; padding: 10px 12px; background: #f9f9f9; border-radius: 6px; }
.artifact-type { font-size: 13px; font-weight: 600; flex: 1; }
.artifact-status { font-size: 12px; padding: 2px 8px; border-radius: 4px; background: #eee; }
.artifact-status.ready { background: #e8f5e9; color: #2e7d32; }
.artifact-status.failed { background: #fce4ec; color: #c62828; }
.btn-small { padding: 4px 12px; background: #fff; border: 1px solid #ddd; border-radius: 4px; font-size: 12px; cursor: pointer; }
.asset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 8px; }
.asset-card { padding: 10px 12px; background: #f9f9f9; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; }
.asset-name { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.asset-type { font-size: 11px; color: #888; background: #eee; padding: 2px 6px; border-radius: 4px; }
.timeline { display: flex; flex-direction: column; gap: 8px; }
.timeline-item { display: flex; gap: 12px; padding: 10px 12px; background: #f9f9f9; border-radius: 6px; }
.timeline-time { font-size: 12px; color: #999; min-width: 80px; }
.timeline-content { flex: 1; font-size: 14px; min-width: 0; }
.event-data { margin-top: 8px; font-size: 12px; background: #f0f0f0; padding: 8px; border-radius: 4px; overflow-x: auto; }
.error-data { background: #fce4ec; }

/* Mobile responsive */
@media (max-width: 640px) {
  .page-header { flex-direction: column; }
  .status-area { width: 100%; }
  .timeline-item { flex-direction: column; gap: 4px; }
  .timeline-time { min-width: auto; }
  .asset-grid { grid-template-columns: 1fr; }
}
</style>
