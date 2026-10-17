<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import { runApi, createSSEConnection, type Run, type SSEEvent } from "../../api/client";
import InteractionCard from "../../components/InteractionCard.vue";

const route = useRoute();
const projectId = route.params.projectId as string;
const runId = route.query.runId as string | undefined;

const run = ref<Run | null>(null);
const events = ref<SSEEvent[]>([]);
const interactions = ref<SSEEvent[]>([]);
const error = ref("");
const connected = ref(false);
let disconnect: (() => void) | null = null;

onMounted(async () => {
  if (runId) {
    try {
      run.value = await runApi.get(runId);
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : "Failed to load run";
    }
  }
  connectSSE();
});

onUnmounted(() => {
  disconnect?.();
});

function connectSSE() {
  if (!runId) return;

  let lastSeq = 0;
  disconnect = createSSEConnection(
    runId,
    lastSeq,
    (event) => {
      connected.value = true;
      events.value.push(event);
      lastSeq = Math.max(lastSeq, Number(event.data.seq) || 0);

      // Track interactions
      if (event.event === "interaction.requested") {
        interactions.value.push(event);
      }

      // Update run status from terminal events
      if (["run.completed", "run.failed", "run.cancelled"].includes(event.event)) {
        if (run.value) {
          run.value.status = event.event.replace("run.", "");
        }
        disconnect?.();
      }
    },
    () => {
      connected.value = false;
    },
  );
}

async function respondToInteraction(interactionEvent: SSEEvent, action: string) {
  const interactionId = interactionEvent.data.interaction_id as string;
  try {
    await runApi.respondToInteraction(interactionId, { action, content: {} });
    // Remove from pending
    interactions.value = interactions.value.filter((i) => i !== interactionEvent);
    // Reconnect SSE to receive new events
    disconnect?.();
    connectSSE();
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Failed to respond";
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

function getEventLabel(event: SSEEvent): string {
  const type = event.event;
  const map: Record<string, string> = {
    "run.started": "▶ Run started",
    "interaction.requested": "⏸ Waiting for your input",
    "interaction.resolved": "✅ Input received",
    "artifact.created": "📦 Artifact created",
    "business.message": "💬 Message",
    "run.completed": "✅ Run completed",
    "run.failed": "❌ Run failed",
    "run.cancelled": "⏹ Run cancelled",
    "tool.started": "🔧 Tool started",
    "tool.completed": "🔧 Tool completed",
    "tool.failed": "🔧 Tool failed",
  };
  return map[type] || type;
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <router-link :to="`/projects/${projectId}`" class="back-link">← Project</router-link>
        <h1>Workbench</h1>
      </div>
      <div class="status-area">
        <span v-if="connected" class="badge live">● Live</span>
        <span v-else class="badge offline">● Disconnected</span>
        <span v-if="run" class="badge" :class="run.status">{{ run.status }}</span>
        <button v-if="run && ['running', 'queued'].includes(run.status)" @click="cancelRun" class="btn-cancel">
          Cancel Run
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
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.back-link { font-size: 13px; color: #1a73e8; text-decoration: none; }
.page-header h1 { font-size: 24px; margin-top: 4px; }
.status-area { display: flex; gap: 8px; align-items: center; }
.badge { font-size: 12px; padding: 4px 10px; border-radius: 12px; background: #eee; }
.badge.live { background: #e8f5e9; color: #2e7d32; }
.badge.offline { background: #fce4ec; color: #c62828; }
.badge.running, .badge.queued { background: #e3f2fd; color: #1565c0; }
.badge.completed { background: #e8f5e9; color: #2e7d32; }
.badge.failed { background: #fce4ec; color: #c62828; }
.btn-cancel { padding: 6px 14px; background: #fff; color: #d93025; border: 1px solid #d93025; border-radius: 6px; font-size: 13px; cursor: pointer; }
.error { color: #d93025; margin-bottom: 16px; }
.interactions { margin-bottom: 24px; }
.section { background: #fff; border-radius: 8px; padding: 24px; border: 1px solid #e0e0e0; }
.section h2 { font-size: 18px; margin-bottom: 16px; }
.empty-text { color: #888; font-size: 14px; padding: 20px; text-align: center; }
.timeline { display: flex; flex-direction: column; gap: 8px; }
.timeline-item { display: flex; gap: 12px; padding: 10px 12px; background: #f9f9f9; border-radius: 6px; }
.timeline-time { font-size: 12px; color: #999; min-width: 80px; }
.timeline-content { flex: 1; font-size: 14px; }
.timeline-item.run\.completed, .timeline-item.run\.failed { border-left: 3px solid #2e7d32; }
.timeline-item.run\.failed { border-left-color: #c62828; }
.event-data { margin-top: 8px; font-size: 12px; background: #f0f0f0; padding: 8px; border-radius: 4px; overflow-x: auto; }
</style>
