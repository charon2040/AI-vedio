<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import KnowledgePanel from "../components/KnowledgePanel.vue";
import { useClipAppState } from "../stores/clipAppState";

const route = useRoute();
const router = useRouter();
const app = useClipAppState();

const routeProjectId = computed(() => String(route.params.projectId || ""));

async function syncRouteProject() {
  if (routeProjectId.value) {
    await app.selectProject(routeProjectId.value);
    return;
  }
  await app.loadKnowledge(app.activeProjectId.value);
}

async function selectProject(projectId: string) {
  await app.selectProject(projectId);
  if (routeProjectId.value) {
    await router.replace({ name: "project-knowledge", params: { projectId } });
  }
}

async function createProject() {
  await app.createProject();
  await router.push({ name: "project-knowledge", params: { projectId: app.activeProjectId.value } });
}

onMounted(syncRouteProject);
watch(routeProjectId, syncRouteProject);
</script>

<template>
  <div class="view-stack narrow-view">
    <section class="page-title">
      <p class="eyebrow">Project Context</p>
      <h1>项目知识库</h1>
      <p>知识库单独管理，只放长期事实。左右方、当前局阵容这种临时事实仍然应该在创建任务时填写。</p>
    </section>

    <KnowledgePanel
      :projects="app.projects.value"
      :active-project-id="app.activeProjectId.value"
      :active-project-default-knowledge-id="app.activeProject.value.default_knowledge_base_id || ''"
      :items="app.knowledgeItems.value"
      :active-id="app.activeKnowledge.value.id"
      :saving="app.knowledgeSaving.value"
      :status="app.knowledgeStatus.value"
      @select-project="selectProject"
      @select="app.activeKnowledgeId.value = $event"
      @save="app.saveKnowledge"
      @create="app.createKnowledge"
      @import="app.importKnowledge"
      @delete="app.deleteKnowledge"
      @create-project="createProject"
      @set-default="app.setProjectDefaultKnowledge"
    />
  </div>
</template>
