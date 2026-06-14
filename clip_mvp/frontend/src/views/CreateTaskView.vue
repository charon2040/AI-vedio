<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import TaskCreateForm from "../components/TaskCreateForm.vue";
import { useClipAppState } from "../stores/clipAppState";
import type { TaskItem } from "../types";

const route = useRoute();
const router = useRouter();
const app = useClipAppState();

const routeProjectId = computed(() => String(route.params.projectId || ""));

async function initCreateView() {
  await app.loadVoiceProfiles();
  await syncRouteProject();
}

async function syncRouteProject() {
  if (!routeProjectId.value) return;
  await app.selectProject(routeProjectId.value);
}

async function selectProject(projectId: string) {
  await app.selectProject(projectId);
  if (routeProjectId.value) {
    await router.replace({ name: "project-create", params: { projectId } });
  }
}

async function createProject() {
  await app.createProject();
  await router.push({ name: "project-create", params: { projectId: app.activeProjectId.value } });
}

async function handleTaskCreated(task: TaskItem) {
  await app.handleTaskCreated(task);
  const taskProjectId = String(task.payload?.project_id || app.activeProjectId.value || "default");
  if (routeProjectId.value) {
    await router.push({ name: "project-task-detail", params: { projectId: taskProjectId, id: task.id } });
    return;
  }
  await router.push({ name: "task-detail", params: { id: task.id } });
}

onMounted(initCreateView);
watch(routeProjectId, syncRouteProject);
</script>

<template>
  <div class="view-stack narrow-view">
    <section class="page-title">
      <p class="eyebrow">New Workflow</p>
      <h1>创建任务</h1>
      <p>这里只负责创建任务和维护配音模板。任务提交后会自动进入详情页等待文案确认或继续运行。</p>
    </section>

    <TaskCreateForm
      :projects="app.projects.value"
      :active-project-id="app.activeProjectId.value"
      :workflow-templates="app.workflowTemplates.value"
      :voice-profiles="app.voiceProfiles.value"
      :knowledge-items="app.knowledgeItems.value"
      :active-knowledge-id="app.activeKnowledge.value.id"
      @created="handleTaskCreated"
      @select-project="selectProject"
      @create-project="createProject"
      @refresh-profiles="app.loadVoiceProfiles"
    />
  </div>
</template>
