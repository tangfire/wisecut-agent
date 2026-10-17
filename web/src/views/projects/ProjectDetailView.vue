<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { projectApi, assetApi, runApi, type Project, type Asset } from "../../api/client";

const route = useRoute();
const router = useRouter();
const projectId = route.params.projectId as string;

const project = ref<Project | null>(null);
const assets = ref<Asset[]>([]);
const loading = ref(true);
const error = ref("");
const uploadFile = ref<File | null>(null);

const userRequest = ref("");
const profileId = ref("one-click-quick");

onMounted(async () => {
  try {
    const [proj, assetList] = await Promise.all([
      projectApi.get(projectId),
      assetApi.list(projectId),
    ]);
    project.value = proj;
    assets.value = assetList.items;
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Failed to load project";
  } finally {
    loading.value = false;
  }
});

async function handleUpload() {
  if (!uploadFile.value) return;
  try {
    const asset = await assetApi.upload(projectId, uploadFile.value);
    assets.value.unshift(asset);
    uploadFile.value = null;
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Upload failed";
  }
}

async function handleStartRun() {
  if (!userRequest.value.trim()) return;
  try {
    const run = await runApi.create({
      user_request: userRequest.value.trim(),
      profile_id: profileId.value,
    });
    router.push(`/workbench/${projectId}?runId=${run.id}`);
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Failed to start run";
  }
}

async function deleteProject() {
  if (!confirm("Delete this project?")) return;
  try {
    await projectApi.delete(projectId);
    router.push("/projects");
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Failed to delete project";
  }
}
</script>

<template>
  <div v-if="loading" class="loading">Loading project...</div>
  <div v-else-if="!project" class="error">Project not found</div>
  <div v-else>
    <div class="page-header">
      <div>
        <router-link to="/projects" class="back-link">← Projects</router-link>
        <h1>{{ project.name }}</h1>
        <p v-if="project.description" class="desc">{{ project.description }}</p>
      </div>
      <div class="actions">
        <router-link :to="`/workbench/${projectId}`" class="btn-primary">Open Workbench</router-link>
        <button @click="deleteProject" class="btn-danger">Delete</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <!-- Start new run -->
    <section class="section">
      <h2>Start a New Generation</h2>
      <div class="run-form">
        <textarea
          v-model="userRequest"
          placeholder="Describe the video you want to create..."
          rows="3"
        ></textarea>
        <div class="run-form-row">
          <select v-model="profileId">
            <option value="one-click-quick">Quick Mode</option>
            <option value="one-click-cocreate">Deep Mode (Co-creation)</option>
          </select>
          <button @click="handleStartRun" :disabled="!userRequest.trim()" class="btn-primary">
            Start Generation
          </button>
        </div>
      </div>
    </section>

    <!-- Assets -->
    <section class="section">
      <h2>Assets ({{ assets.length }})</h2>
      <div class="upload-row">
        <input type="file" @change="(e: Event) => uploadFile = (e.target as HTMLInputElement).files?.[0] || null" />
        <button @click="handleUpload" :disabled="!uploadFile" class="btn-primary">Upload</button>
      </div>
      <div v-if="assets.length > 0" class="asset-list">
        <div v-for="a in assets" :key="a.id" class="asset-item">
          <span class="asset-name">{{ a.name }}</span>
          <span class="asset-type">{{ a.asset_type }}</span>
          <span class="asset-size">{{ (a.size_bytes / 1024).toFixed(1) }} KB</span>
        </div>
      </div>
      <p v-else class="empty-text">No assets uploaded yet.</p>
    </section>
  </div>
</template>

<style scoped>
.loading { padding: 40px; text-align: center; color: #888; }
.error { color: #d93025; margin-bottom: 16px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.back-link { font-size: 13px; color: #1a73e8; text-decoration: none; }
.page-header h1 { font-size: 24px; margin-top: 4px; }
.desc { color: #666; font-size: 14px; margin-top: 4px; }
.actions { display: flex; gap: 8px; }
.btn-primary { padding: 8px 16px; background: #1a73e8; color: #fff; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; text-decoration: none; display: inline-block; }
.btn-danger { padding: 8px 16px; background: #fff; color: #d93025; border: 1px solid #d93025; border-radius: 6px; font-size: 14px; cursor: pointer; }
.section { background: #fff; border-radius: 8px; padding: 24px; margin-bottom: 24px; border: 1px solid #e0e0e0; }
.section h2 { font-size: 18px; margin-bottom: 16px; }
.run-form textarea { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; resize: vertical; }
.run-form-row { display: flex; gap: 8px; margin-top: 12px; }
.run-form-row select { padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
.upload-row { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.upload-row input[type="file"] { font-size: 13px; }
.asset-list { display: flex; flex-direction: column; gap: 8px; }
.asset-item { display: flex; align-items: center; gap: 12px; padding: 10px 12px; background: #f9f9f9; border-radius: 6px; }
.asset-name { flex: 1; font-size: 14px; }
.asset-type { font-size: 12px; color: #888; background: #eee; padding: 2px 8px; border-radius: 4px; }
.asset-size { font-size: 12px; color: #999; }
.empty-text { color: #888; font-size: 14px; }

/* Mobile responsive */
@media (max-width: 640px) {
  .page-header { flex-direction: column; }
  .actions { width: 100%; }
  .run-form-row { flex-direction: column; }
  .upload-row { flex-direction: column; align-items: stretch; }
}
</style>
