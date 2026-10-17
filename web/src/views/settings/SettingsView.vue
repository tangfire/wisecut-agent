<script setup lang="ts">
import { ref, onMounted } from "vue";
import { providerApi, type ProviderCapability, type ProviderSetting } from "../../api/client";

const capabilities = ref<ProviderCapability[]>([]);
const settings = ref<ProviderSetting[]>([]);
const loading = ref(true);
const error = ref("");
const saveMessage = ref("");

onMounted(async () => {
  try {
    const [caps, sts] = await Promise.all([
      providerApi.list(),
      providerApi.listSettings(),
    ]);
    capabilities.value = caps;
    settings.value = sts;
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Failed to load settings";
  } finally {
    loading.value = false;
  }
});

async function saveSetting(providerType: string, config: Record<string, unknown>) {
  try {
    await providerApi.setSetting(providerType, config, true);
    saveMessage.value = `Saved ${providerType} settings`;
    setTimeout(() => (saveMessage.value = ""), 2000);
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Failed to save";
  }
}
</script>

<template>
  <div>
    <h1>Settings</h1>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="saveMessage" class="success">{{ saveMessage }}</p>

    <div v-if="loading" class="loading">Loading settings...</div>

    <div v-else class="settings-sections">
      <!-- Provider Capabilities -->
      <section class="section">
        <h2>Available Providers</h2>
        <div class="provider-list">
          <div v-for="cap in capabilities" :key="cap.provider_type" class="provider-item">
            <strong>{{ cap.provider_type }}</strong>
            <span class="capabilities">{{ cap.capabilities.join(", ") }}</span>
          </div>
        </div>
      </section>

      <!-- Provider Settings -->
      <section class="section">
        <h2>Provider Settings</h2>
        <p class="hint">Configure your LLM and video generation provider.</p>
        <div class="setting-form">
          <h3>LLM Provider</h3>
          <div class="field">
            <label>Model</label>
            <input value="gpt-4o-mini" readonly />
          </div>
          <div class="field">
            <label>Temperature</label>
            <input value="0.7" readonly />
          </div>
          <button @click="saveSetting('llm', { model: 'gpt-4o-mini', temperature: 0.7 })" class="btn-primary">
            Save LLM Settings
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
h1 { font-size: 24px; margin-bottom: 16px; }
.error { color: #d93025; margin-bottom: 12px; }
.success { color: #2e7d32; margin-bottom: 12px; }
.loading { padding: 40px; text-align: center; color: #888; }
.settings-sections { display: flex; flex-direction: column; gap: 24px; }
.section { background: #fff; border-radius: 8px; padding: 24px; border: 1px solid #e0e0e0; }
.section h2 { font-size: 18px; margin-bottom: 16px; }
.provider-list { display: flex; flex-direction: column; gap: 8px; }
.provider-item { display: flex; gap: 12px; align-items: center; padding: 8px 12px; background: #f9f9f9; border-radius: 6px; }
.capabilities { font-size: 12px; color: #888; }
.hint { color: #666; font-size: 14px; margin-bottom: 16px; }
.setting-form { max-width: 400px; }
.setting-form h3 { font-size: 15px; margin-bottom: 12px; }
.field { margin-bottom: 12px; }
.field label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.field input { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; background: #f5f5f5; }
.btn-primary { padding: 8px 16px; background: #1a73e8; color: #fff; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; margin-top: 8px; }
</style>
