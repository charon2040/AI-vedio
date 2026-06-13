<script setup lang="ts">
import type { ClipPlan, TaskItem } from "../types";
import { actualDurationLabel, durationLabel, formatDate } from "../utils/format";

defineProps<{
  task: TaskItem;
  plans: ClipPlan[];
  plansLoading: boolean;
}>();
</script>

<template>
  <details v-if="task.status === 'completed'" class="task-section">
    <summary>
      <div><strong>方案历史</strong><small>同素材的历史生成方案</small></div>
      <span class="section-pill">{{ plans.length }} 条</span>
    </summary>
    <div v-if="plansLoading" class="plan-empty">正在读取方案历史...</div>
    <div v-else-if="!plans.length" class="plan-empty">这个任务还没有可展示的方案记录。</div>
    <div v-else class="plan-list">
      <article v-for="plan in plans" :key="plan.id" class="plan-card" :class="{ current: plan.id === task.result?.clip_plan_id }">
        <div class="task-head">
          <div><div class="task-id">Plan {{ plan.id }}</div><strong>{{ formatDate(plan.created_at) }}</strong></div>
          <span class="badge" :class="plan.id === task.result?.clip_plan_id ? 'completed' : 'running'">
            {{ plan.id === task.result?.clip_plan_id ? "当前方案" : "历史方案" }}
          </span>
        </div>
        <div class="task-meta compact">
          <div><span>目标时长</span><strong>{{ durationLabel(plan.duration_seconds) }}</strong></div>
          <div><span>素材时长</span><strong>{{ actualDurationLabel(plan.total_duration_ms) }}</strong></div>
          <div><span>片段数</span><strong>{{ plan.segments?.length || 0 }}</strong></div>
        </div>
        <div class="task-block"><div class="task-block-title">生成文案</div><div class="task-block-body">{{ plan.script || "--" }}</div></div>
      </article>
    </div>
  </details>
</template>
