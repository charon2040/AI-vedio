<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { Project, ProjectKnowledge } from "../types";

const props = defineProps<{
  projects: Project[];
  activeProjectId: string;
  activeProjectDefaultKnowledgeId: string;
  items: ProjectKnowledge[];
  activeId: string;
  saving: boolean;
  status: string;
}>();

const emit = defineEmits<{
  selectProject: [id: string];
  select: [id: string];
  save: [payload: { id: string; title: string; content: string }];
  create: [];
  import: [file: File];
  delete: [id: string];
  createProject: [];
  setDefault: [id: string];
}>();

const title = ref("");
const content = ref("");
const fileInput = ref<HTMLInputElement | null>(null);

const projectOptions = computed(() => {
  return props.projects.length
    ? props.projects
    : [{ id: "default", title: "默认项目", default_knowledge_base_id: "default" }];
});

const active = computed(() => {
  return props.items.find((item) => item.id === props.activeId) || props.items[0] || {
    id: "default",
    project_id: props.activeProjectId || "default",
    title: "项目知识库",
    content: "",
  };
});

const isProjectDefault = computed(() => {
  return active.value.id === props.activeProjectDefaultKnowledgeId;
});

watch(
  active,
  (item) => {
    title.value = item.title || "项目知识库";
    content.value = item.content || "";
  },
  { immediate: true },
);

function save() {
  emit("save", {
    id: active.value.id || "default",
    title: title.value.trim() || "项目知识库",
    content: content.value.trim(),
  });
}

function openImportPicker() {
  fileInput.value?.click();
}

function importFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  emit("import", file);
}
</script>

<template>
  <section class="panel knowledge-panel">
    <div class="panel-header">
      <div>
        <h2>项目知识库</h2>
        <p>项目默认知识库是可选上下文模板；创建任务时仍需明确选择是否使用。</p>
      </div>
      <div class="panel-actions knowledge-actions">
        <select
          :value="activeProjectId"
          aria-label="选择项目"
          @change="emit('selectProject', ($event.target as HTMLSelectElement).value)"
        >
          <option v-for="project in projectOptions" :key="project.id" :value="project.id">
            {{ project.title || project.id }}
          </option>
        </select>
        <select :value="active.id" aria-label="选择知识库" @change="emit('select', ($event.target as HTMLSelectElement).value)">
          <option v-for="item in items" :key="item.id" :value="item.id">
            {{ item.title }}{{ item.id === activeProjectDefaultKnowledgeId ? " · 项目默认" : "" }}
          </option>
        </select>
        <button class="ghost-btn" type="button" :disabled="saving" @click="emit('createProject')">新建项目</button>
        <button class="ghost-btn" type="button" :disabled="saving" @click="emit('create')">新建知识库</button>
        <input
          ref="fileInput"
          class="hidden-file-input"
          type="file"
          accept=".md,.markdown,.txt,text/markdown,text/plain"
          @change="importFile"
        />
        <button class="ghost-btn" type="button" :disabled="saving" @click="openImportPicker">导入 Markdown</button>
        <button
          class="ghost-btn"
          type="button"
          :disabled="saving || isProjectDefault"
          @click="emit('setDefault', active.id)"
        >
          设为项目默认
        </button>
        <button class="ghost-btn" type="button" :disabled="saving" @click="save">保存知识库</button>
        <button
          class="ghost-btn danger-btn"
          type="button"
          :disabled="saving"
          @click="emit('delete', active.id)"
        >
          删除知识库
        </button>
      </div>
    </div>

    <div class="knowledge-editor">
      <label class="field compact-field">
        <span>知识库名称</span>
        <input v-model="title" type="text" />
      </label>
      <label class="field">
        <span>长期实体资料</span>
        <textarea
          v-model="content"
          rows="7"
          placeholder="例如：项目 A 的人物、组织、角色、别名、术语。不要写本次视频才成立的临时事实。"
        />
      </label>
      <p class="submit-status">{{ status }}</p>
    </div>
  </section>
</template>
