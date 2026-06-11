<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";
import { useClipAppState } from "./stores/clipAppState";

const route = useRoute();
const router = useRouter();
const app = useClipAppState();

const currentProjectId = computed(() => String(route.params.projectId || app.activeProjectId.value || "default"));
const isLoginRoute = computed(() => String(route.name || "") === "login");

function projectRoute(name: string) {
  return { name, params: { projectId: currentProjectId.value } };
}

function isActiveRoute(names: string[]) {
  return names.includes(String(route.name || ""));
}

onMounted(() => {
  void app.bootstrap();
});

onBeforeUnmount(app.stopPolling);

async function logout() {
  await app.logout();
  await router.push({ name: "login" });
}
</script>

<template>
  <div class="page-shell app-frame" :class="{ 'auth-shell': isLoginRoute }">
    <header v-if="!isLoginRoute" class="app-topbar">
      <RouterLink class="brand" to="/">
        <span>AI Script Alignment</span>
        <strong>Clip MVP</strong>
      </RouterLink>
      <nav class="app-nav" aria-label="主导航">
        <RouterLink to="/" :class="{ active: isActiveRoute(['dashboard']) }">项目入口</RouterLink>
        <RouterLink
          :to="projectRoute('project-workspace')"
          :class="{ active: isActiveRoute(['project-workspace', 'project-settings']) }"
        >
          当前项目
        </RouterLink>
        <RouterLink
          :to="projectRoute('project-create')"
          :class="{ active: isActiveRoute(['project-create', 'create']) }"
        >
          创建任务
        </RouterLink>
        <RouterLink
          :to="projectRoute('project-tasks')"
          :class="{ active: isActiveRoute(['project-tasks', 'tasks', 'project-task-detail', 'task-detail']) }"
        >
          项目任务
        </RouterLink>
        <RouterLink
          :to="projectRoute('project-knowledge')"
          :class="{ active: isActiveRoute(['project-knowledge', 'knowledge']) }"
        >
          知识库
        </RouterLink>
        <RouterLink
          :to="projectRoute('project-settings')"
          :class="{ active: isActiveRoute(['project-settings']) }"
        >
          项目设置
        </RouterLink>
        <RouterLink to="/runtime" :class="{ active: isActiveRoute(['runtime']) }">
          运行环境
        </RouterLink>
      </nav>
      <div class="user-menu">
        <span>{{ app.currentUser.value?.display_name || app.currentUser.value?.username || "未登录" }}</span>
        <button class="ghost-btn slim-btn" type="button" @click="logout">退出</button>
      </div>
    </header>

    <RouterView />
  </div>
</template>
