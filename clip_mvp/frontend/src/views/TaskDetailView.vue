<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import TaskDetail from "../components/TaskDetail.vue";
import { useClipAppState } from "../stores/clipAppState";

const route = useRoute();
const router = useRouter();
const app = useClipAppState();

const routeProjectId = computed(() => String(route.params.projectId || ""));

async function loadRouteTask() {
  const taskId = String(route.params.id || "");
  if (!taskId) return;
  await app.loadVoiceProfiles();
  await app.openTask(taskId);
  if (routeProjectId.value && app.activeProjectId.value !== routeProjectId.value) {
    await router.replace({
      name: "project-task-detail",
      params: { projectId: app.activeProjectId.value, id: taskId },
    });
  }
}

async function deleteTask(taskId: string) {
  await app.deleteTask(taskId);
  if (!app.activeTask.value) {
    if (routeProjectId.value) {
      await router.push({ name: "project-tasks", params: { projectId: routeProjectId.value } });
      return;
    }
    await router.push({ name: "tasks" });
  }
}

onMounted(loadRouteTask);
watch(() => route.params.id, loadRouteTask);
</script>

<template>
  <div class="view-stack">
    <section class="page-title">
      <p class="eyebrow">Task Detail</p>
      <h1>任务详情</h1>
      <p>这里集中处理文案确认、阶段事件、最终选片、方案历史和重新生成。</p>
    </section>

    <TaskDetail
      :task="app.activeTask.value"
      :plans="app.taskPlans.value"
      :plans-loading="app.plansLoading.value"
      :voice-profiles="app.voiceProfiles.value"
      :knowledge-items="app.knowledgeItems.value"
      @delete="deleteTask"
      @save-draft="app.saveDraft"
      @approve-draft="app.approveDraft"
      @replan="app.replanTask"
      @retry-alignment="app.retryAlignment"
    />
  </div>
</template>
