<script setup lang="ts">
import { ref, onMounted } from "vue";
import { projectApi, type Project } from "../../api/client";

const projects = ref<Project[]>([]);
const loading = ref(true);
const error = ref("");
const showCreate = ref(false);
const newName = ref("");
const newDescription = ref("");

onMounted(async () => {
  try {
    const resp = await projectApi.list();
    projects.value = resp.items;
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Failed to load projects";
  } finally {
    loading.value = false;
  }
});

async function handleCreate() {
  if (!newName.value.trim()) return;
  try {
    const project = await projectApi.create(newName.value.trim(), newDescription.value.trim() || undefined);
    projects.value.unshift(project);
    showCreate.value = false;
    newName.value = "";
    newDescription.value = "";
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Failed to create project";
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Projects</h1>
      <button @click="showCreate = !showCreate" class="btn-primary">+ New Project</button>
    </div>

    <form v-if="showCreate" @submit.prevent="handleCreate" class="create-form">
      <input v-model="newName" placeholder="Project name" required />
      <input v-model="newDescription" placeholder="Description (optional)" />
      <button type="submit" class="btn-primary">Create</button>
      <button type="button" @click="showCreate = false" class="btn-secondary">Cancel</button>
    </form>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="loading" class="loading">Loading projects...</div>

    <div v-else-if="projects.length === 0" class="empty">
      No projects yet. Create your first project to get started.
    </div>

    <div v-else class="project-grid">
      <router-link
        v-for="p in projects"
        :key="p.id"
        :to="`/projects/${p.id}`"
        class="project-card"
      >
        <h3>{{ p.name }}</h3>
        <p v-if="p.description">{{ p.description }}</p>
        <div class="project-meta">
          <span class="status-badge" :class="p.status">{{ p.status }}</span>
          <span class="date">{{ new Date(p.created_at).toLocaleDateString() }}</span>
        </div>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h1 { font-size: 24px; }
.create-form { display: flex; gap: 8px; margin-bottom: 24px; }
.create-form input { padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
.create-form input:first-child { flex: 1; }
.btn-primary { padding: 10px 20px; background: #1a73e8; color: #fff; border: none; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-secondary { padding: 10px 20px; background: #f0f0f0; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; cursor: pointer; }
.error { color: #d93025; margin-bottom: 16px; }
.loading { color: #888; padding: 40px; text-align: center; }
.empty { color: #888; padding: 40px; text-align: center; background: #fff; border-radius: 8px; }
.project-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
@media (max-width: 640px) {
  .page-header { flex-direction: column; gap: 12px; }
  .create-form { flex-direction: column; }
  .project-grid { grid-template-columns: 1fr; }
}
.project-card { background: #fff; border-radius: 8px; padding: 20px; text-decoration: none; color: inherit; border: 1px solid #e0e0e0; transition: box-shadow 0.15s; }
.project-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.project-card h3 { font-size: 16px; margin-bottom: 8px; }
.project-card p { font-size: 13px; color: #666; margin-bottom: 12px; }
.project-meta { display: flex; justify-content: space-between; align-items: center; }
.status-badge { font-size: 11px; padding: 2px 8px; border-radius: 12px; background: #e8f5e9; color: #2e7d32; }
.status-badge.archived { background: #fff3e0; color: #e65100; }
.date { font-size: 12px; color: #999; }
</style>
