<script setup lang="ts">
import { computed } from "vue";
import type { SSEEvent } from "../api/client";

const props = defineProps<{
  interaction: SSEEvent;
}>();

const emit = defineEmits<{
  approve: [];
  cancel: [];
  edit: [data: Record<string, unknown>];
}>();

const data = computed(() => props.interaction.data.data as Record<string, unknown> || {});
const intent = computed(() => props.interaction.data.interaction_type as string || "unknown");
const title = computed(() => data.value.title as string || "Input Required");
const description = computed(() => data.value.description as string || "");
</script>

<template>
  <div class="interaction-card">
    <div class="interaction-header">
      <span class="interaction-type">{{ intent }}</span>
      <h3>{{ title }}</h3>
    </div>
    <p v-if="description" class="interaction-desc">{{ description }}</p>

    <!-- Product context confirmation -->
    <div v-if="intent === 'confirm_extracted_product_context' || intent === 'confirm_generation_start'" class="interaction-body">
      <div v-if="data.cost_breakdown" class="cost-breakdown">
        <h4>Cost Breakdown</h4>
        <pre>{{ JSON.stringify(data.cost_breakdown, null, 2) }}</pre>
      </div>
    </div>

    <!-- Storyboard review -->
    <div v-if="intent === 'review_storyboard_script'" class="interaction-body">
      <div v-if="data.script" class="review-content">
        <h4>Script</h4>
        <pre>{{ JSON.stringify(data.script, null, 2) }}</pre>
      </div>
      <div v-if="data.storyboard" class="review-content">
        <h4>Storyboard</h4>
        <pre>{{ JSON.stringify(data.storyboard, null, 2) }}</pre>
      </div>
    </div>

    <div class="interaction-actions">
      <button @click="emit('approve')" class="btn-approve">✓ Approve</button>
      <button @click="emit('cancel')" class="btn-cancel">✕ Cancel</button>
    </div>
  </div>
</template>

<style scoped>
.interaction-card {
  background: #fff;
  border: 2px solid #1a73e8;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(26, 115, 232, 0.1);
}
.interaction-header { margin-bottom: 12px; }
.interaction-type { font-size: 11px; color: #1a73e8; text-transform: uppercase; letter-spacing: 0.5px; }
.interaction-header h3 { font-size: 18px; margin-top: 4px; }
.interaction-desc { color: #666; font-size: 14px; margin-bottom: 16px; }
.interaction-body { margin-bottom: 16px; }
.cost-breakdown, .review-content { background: #f5f7fa; border-radius: 8px; padding: 12px; margin-bottom: 8px; }
.cost-breakdown h4, .review-content h4 { font-size: 13px; margin-bottom: 8px; color: #333; }
pre { font-size: 12px; overflow-x: auto; }
.interaction-actions { display: flex; gap: 8px; }
.btn-approve { padding: 8px 20px; background: #1a73e8; color: #fff; border: none; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-cancel { padding: 8px 20px; background: #fff; color: #d93025; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; cursor: pointer; }
</style>
