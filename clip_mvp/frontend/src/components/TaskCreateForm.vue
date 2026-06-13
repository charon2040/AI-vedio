<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { api } from "../api/client";
import type {
  KnowledgePolicy,
  Project,
  ProjectKnowledge,
  TaskItem,
  VoiceMode,
  VoiceProfile,
  VoiceSource,
  WorkflowTemplate,
} from "../types";
import { normalizedVoiceMode, voiceModeLabel } from "../utils/format";

const props = defineProps<{
  projects: Project[];
  activeProjectId: string;
  workflowTemplates: WorkflowTemplate[];
  voiceProfiles: VoiceProfile[];
  knowledgeItems: ProjectKnowledge[];
  activeKnowledgeId: string;
}>();

const emit = defineEmits<{
  created: [task: TaskItem];
  selectProject: [id: string];
  createProject: [];
  refreshProfiles: [];
}>();

const file = ref<File | null>(null);
const requirements = ref("");
const projectContext = ref("");
const selectedProjectId = ref("");
const pipelineMode = ref("narration_clip");
const selectedKnowledgeId = ref("");
const knowledgePolicy = ref<KnowledgePolicy>("none");
const durationSeconds = ref("0");
const style = ref("summary");
const enableDubbing = ref(false);
const keepOriginalAudio = ref(true);
const voiceSource = ref<VoiceSource>("tts");
const uploadedVoiceover = ref<File | null>(null);
const voiceMode = ref<VoiceMode>("standard");
const voiceProfileId = ref("");
const ttsSpeed = ref("1.00");
const submitStatus = ref("等待提交");
const submitting = ref(false);
const lastDefaultedProjectId = ref("");

const profileLabel = ref("");
const profileDescription = ref("");
const profileLanguage = ref("zh-CN");
const profilePromptText = ref("");
const profileAudio = ref<File | null>(null);
const profileStatus = ref("创建后会自动刷新 CosyVoice 克隆模板库。");
const creatingProfile = ref(false);

const projectOptions = computed(() => {
  return props.projects.length
    ? props.projects
    : [{ id: "default", title: "默认项目", default_knowledge_base_id: "default" }];
});

const workflowOptions = computed<WorkflowTemplate[]>(() => {
  return props.workflowTemplates.length
    ? props.workflowTemplates
    : [{ id: "narration_clip", title: "AI 解说剪辑", description: "生成文案、确认后配音，并按配音时长匹配画面。" }];
});

const selectedWorkflow = computed(() => {
  return workflowOptions.value.find((item) => item.id === pipelineMode.value)
    || workflowOptions.value[0]
    || { id: "narration_clip", title: "AI 解说剪辑", description: "" };
});

const knowledgeOptions = computed(() => {
  return props.knowledgeItems.length
    ? props.knowledgeItems
    : [{ id: "default", project_id: selectedProjectId.value || "default", title: "项目知识库", content: "" }];
});

const activeProject = computed(() => {
  return projectOptions.value.find((item) => item.id === selectedProjectId.value)
    || projectOptions.value[0]
    || { id: "default", title: "默认项目", default_knowledge_policy: "none" };
});

const activeProjectDefaultKnowledgeId = computed(() => {
  return String(activeProject.value.default_knowledge_base_id || "").trim();
});

const activeProjectDefaultKnowledgeTitle = computed(() => {
  const defaultId = activeProjectDefaultKnowledgeId.value;
  if (!defaultId) return "未设置";
  const item = knowledgeOptions.value.find((knowledge) => knowledge.id === defaultId);
  return item?.title || defaultId;
});

const filteredProfiles = computed(() => {
  return props.voiceProfiles.filter((profile) => {
    const kind = String(profile.voice_kind || "").toLowerCase();
    const sourceType = String(profile.source_type || "").toLowerCase();
    if (voiceMode.value === "clone") {
      return kind === "clone" || sourceType === "user";
    }
    return kind !== "clone" && sourceType !== "user";
  });
});

const useTtsVoice = computed(() => enableDubbing.value && voiceSource.value === "tts");
const useUploadedVoiceover = computed(() => voiceSource.value === "uploaded_voiceover");

function normalizeKnowledgePolicy(value: unknown): KnowledgePolicy {
  const policy = String(value || "").trim().toLowerCase();
  return policy === "project_default" || policy === "selected" ? policy : "none";
}

function normalizeVoiceModeValue(value: unknown): VoiceMode {
  return value === "clone" ? "clone" : "standard";
}

function applyProjectDefaults(projectId: string, force = false) {
  const project = projectOptions.value.find((item) => item.id === projectId);
  if (!project) return;
  const defaultKey = `${projectId}|${workflowOptions.value.map((item) => item.id).join("|")}`;
  if (!force && lastDefaultedProjectId.value === defaultKey) return;

  const defaultKnowledgeId = String(project.default_knowledge_base_id || "").trim();
  const defaultPolicy = normalizeKnowledgePolicy(project.default_knowledge_policy);
  const defaultPipelineMode = String(project.default_pipeline_mode || "").trim();
  pipelineMode.value = workflowOptions.value.some((item) => item.id === defaultPipelineMode)
    ? defaultPipelineMode
    : workflowOptions.value[0]?.id || "narration_clip";
  selectedKnowledgeId.value = defaultKnowledgeId || props.activeKnowledgeId || knowledgeOptions.value[0]?.id || "";
  knowledgePolicy.value = defaultKnowledgeId ? defaultPolicy : "none";
  durationSeconds.value = String(project.default_duration_seconds || 0);
  style.value = String(project.default_style || "summary");
  enableDubbing.value = Boolean(project.default_enable_dubbing);
  voiceSource.value = "tts";
  uploadedVoiceover.value = null;
  keepOriginalAudio.value = project.default_keep_original_audio !== false;
  voiceMode.value = normalizeVoiceModeValue(project.default_voice_mode);
  voiceProfileId.value = String(project.default_voice_profile_id || "");
  ttsSpeed.value = Number(project.default_tts_speed || 1).toFixed(2);
  lastDefaultedProjectId.value = defaultKey;
}

watch(
  () => [
    props.activeProjectId,
    projectOptions.value.map((item) => item.id).join("|"),
    workflowOptions.value.map((item) => item.id).join("|"),
  ],
  () => {
    const fallbackId = props.activeProjectId || projectOptions.value[0]?.id || "default";
    if (selectedProjectId.value !== fallbackId && projectOptions.value.some((item) => item.id === fallbackId)) {
      selectedProjectId.value = fallbackId;
      applyProjectDefaults(fallbackId, true);
      return;
    }
    applyProjectDefaults(fallbackId);
  },
  { immediate: true },
);

watch(voiceSource, (nextSource) => {
  if (nextSource === "uploaded_voiceover") {
    enableDubbing.value = true;
  }
});

watch(enableDubbing, (enabled) => {
  if (!enabled) {
    voiceSource.value = "tts";
    uploadedVoiceover.value = null;
  }
});

watch(
  () => [
    useTtsVoice.value,
    voiceMode.value,
    voiceProfileId.value,
    filteredProfiles.value.map((profile) => `${profile.id}:${profile.label}`).join("|"),
  ],
  () => {
    if (!useTtsVoice.value) {
      return;
    }
    if (!filteredProfiles.value.some((profile) => profile.id === voiceProfileId.value)) {
      voiceProfileId.value = filteredProfiles.value[0]?.id || "";
    }
  },
  { immediate: true },
);

watch(
  () => [props.activeKnowledgeId, knowledgeOptions.value.map((item) => item.id).join("|")],
  () => {
    const fallbackId = props.activeKnowledgeId || knowledgeOptions.value[0]?.id || "default";
    if (!knowledgeOptions.value.some((item) => item.id === selectedKnowledgeId.value)) {
      selectedKnowledgeId.value = fallbackId;
    }
  },
  { immediate: true },
);

function changeProject(projectId: string) {
  const nextId = String(projectId || "default").trim() || "default";
  selectedProjectId.value = nextId;
  applyProjectDefaults(nextId, true);
  emit("selectProject", nextId);
}

function onFileChange(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0] || null;
}

function onProfileAudioChange(event: Event) {
  profileAudio.value = (event.target as HTMLInputElement).files?.[0] || null;
}

function onUploadedVoiceoverChange(event: Event) {
  uploadedVoiceover.value = (event.target as HTMLInputElement).files?.[0] || null;
}

function syncDefaultProfile() {
  if (useTtsVoice.value && !voiceProfileId.value && filteredProfiles.value.length) {
    voiceProfileId.value = filteredProfiles.value[0].id;
  }
}

async function submit() {
  if (!file.value) {
    submitStatus.value = "请先选择视频文件。";
    return;
  }
  if (!requirements.value.trim()) {
    submitStatus.value = "请先填写目标文案。";
    return;
  }
  if (useUploadedVoiceover.value && !uploadedVoiceover.value) {
    submitStatus.value = "上传完整配音模式需要选择配音音频文件。";
    return;
  }

  submitting.value = true;
  submitStatus.value = "正在创建任务并生成文案初稿...";
  try {
    syncDefaultProfile();
    const formData = new FormData();
    formData.append("file", file.value);
    formData.append("requirements", requirements.value.trim());
    formData.append("project_id", selectedProjectId.value || props.activeProjectId || "default");
    formData.append("pipeline_mode", pipelineMode.value || "narration_clip");
    formData.append("project_context", projectContext.value.trim());
    formData.append("knowledge_policy", knowledgePolicy.value);
    formData.append("knowledge_base_id", knowledgePolicy.value === "selected" ? selectedKnowledgeId.value : "");
    formData.append("duration_seconds", durationSeconds.value);
    formData.append("style", style.value);
    formData.append("enable_dubbing", enableDubbing.value || useUploadedVoiceover.value ? "true" : "false");
    formData.append("voice_source", voiceSource.value);
    formData.append("voice_mode", voiceMode.value);
    formData.append("keep_original_audio", keepOriginalAudio.value ? "true" : "false");
    formData.append("voice_profile_id", voiceProfileId.value || "");
    formData.append(
      "tts_voice",
      filteredProfiles.value.find((profile) => profile.id === voiceProfileId.value)?.label || "",
    );
    formData.append("tts_speed", ttsSpeed.value);
    if (useUploadedVoiceover.value && uploadedVoiceover.value) {
      formData.append("uploaded_voiceover", uploadedVoiceover.value);
    }
    const task = await api.createTask(formData);
    submitStatus.value = "任务已提交，正在生成文案初稿。";
    emit("created", task);
  } catch (error) {
    submitStatus.value = `提交失败：${(error as Error).message}`;
  } finally {
    submitting.value = false;
  }
}

async function createProfile() {
  if (!profileLabel.value.trim()) {
    profileStatus.value = "请先填写模板名称。";
    return;
  }
  if (!profilePromptText.value.trim()) {
    profileStatus.value = "请先填写参考文案。";
    return;
  }
  if (!profileAudio.value) {
    profileStatus.value = "请先上传参考音频。";
    return;
  }

  creatingProfile.value = true;
  profileStatus.value = "正在创建克隆模板...";
  try {
    const formData = new FormData();
    formData.append("label", profileLabel.value.trim());
    formData.append("description", profileDescription.value.trim());
    formData.append("language", profileLanguage.value.trim());
    formData.append("prompt_text", profilePromptText.value.trim());
    formData.append("prompt_audio", profileAudio.value);
    await api.createVoiceProfile(formData);
    profileStatus.value = "克隆模板已创建。";
    profileLabel.value = "";
    profileDescription.value = "";
    profilePromptText.value = "";
    profileAudio.value = null;
    emit("refreshProfiles");
  } catch (error) {
    profileStatus.value = `创建失败：${(error as Error).message}`;
  } finally {
    creatingProfile.value = false;
  }
}
</script>

<template>
  <section class="panel form-panel">
    <div class="panel-header">
      <h2>创建任务</h2>
      <p>先生成文案初稿，确认后再继续配音和选片。</p>
    </div>

    <form class="task-form" @submit.prevent="submit">
      <label class="field">
        <span>原始视频</span>
        <input type="file" accept="video/*" required @change="onFileChange" />
      </label>
      <label class="field">
        <span>剪辑目标 / 要求</span>
        <textarea v-model="requirements" rows="8" required placeholder="例如：保留团战逆转和关键决策，做成 60 秒赛事复盘。" />
      </label>

      <div class="field-row">
        <label class="field">
          <span>项目</span>
          <select :value="selectedProjectId" @change="changeProject(($event.target as HTMLSelectElement).value)">
            <option v-for="item in projectOptions" :key="item.id" :value="item.id">
              {{ item.title || item.id }}
            </option>
          </select>
        </label>
        <label class="field">
          <span>知识库使用方式</span>
          <select v-model="knowledgePolicy">
            <option value="none">不使用知识库</option>
            <option value="project_default" :disabled="!activeProjectDefaultKnowledgeId">
              使用项目默认：{{ activeProjectDefaultKnowledgeTitle }}
            </option>
            <option value="selected">指定知识库</option>
          </select>
        </label>
      </div>
      <label class="field">
        <span>工作流模板</span>
        <select v-model="pipelineMode">
          <option v-for="item in workflowOptions" :key="item.id" :value="item.id">
            {{ item.title || item.id }}
          </option>
        </select>
      </label>
      <p class="field-hint">
        {{ selectedWorkflow.description || "当前版本先保存模板选择，后续会把模板拆成可组合节点执行。" }}
      </p>
      <label v-if="knowledgePolicy === 'selected'" class="field">
        <span>指定知识库</span>
        <select v-model="selectedKnowledgeId">
          <option v-for="item in knowledgeOptions" :key="item.id" :value="item.id">
            {{ item.title }}{{ item.id === activeProjectDefaultKnowledgeId ? " · 项目默认" : "" }}
          </option>
        </select>
      </label>
      <p v-else-if="knowledgePolicy === 'project_default'" class="field-hint">
        本次会读取项目默认知识库：{{ activeProjectDefaultKnowledgeTitle }}。
      </p>
      <p v-else class="field-hint">本次不会注入知识库，只使用视频字幕和你填写的补充事实。</p>
      <button class="ghost-btn inline-action" type="button" @click="emit('createProject')">新建项目</button>

      <label class="field">
        <span>本次补充事实（可选）</span>
        <textarea v-model="projectContext" rows="5" placeholder="只写本次视频才成立的事实，比如左右方、人物身份、简称含义。" />
      </label>

      <div class="field-row">
        <label class="field">
          <span>目标时长</span>
          <select v-model="durationSeconds">
            <option value="0">自动</option>
            <option value="30">30 秒</option>
            <option value="45">45 秒</option>
            <option value="60">60 秒</option>
            <option value="90">90 秒</option>
          </select>
        </label>
        <label class="field">
          <span>输出风格</span>
          <select v-model="style">
            <option value="summary">总结</option>
            <option value="highlight">高光</option>
            <option value="analysis">复盘</option>
            <option value="short_hook">短视频感</option>
          </select>
        </label>
      </div>

      <div class="field-row">
        <label class="checkbox-card">
          <input v-model="enableDubbing" type="checkbox" />
          <span>开启配音</span>
        </label>
        <label class="checkbox-card">
          <input v-model="keepOriginalAudio" type="checkbox" />
          <span>保留低音量原声</span>
        </label>
      </div>

      <label v-if="enableDubbing" class="field">
        <span>配音来源</span>
        <select v-model="voiceSource">
          <option value="tts">AI TTS 生成配音</option>
          <option value="uploaded_voiceover">上传完整配音</option>
        </select>
      </label>

      <label v-if="useUploadedVoiceover" class="field">
        <span>完整配音音频</span>
        <input type="file" accept="audio/*,video/*" required @change="onUploadedVoiceoverChange" />
      </label>
      <p v-if="useUploadedVoiceover" class="field-hint">
        上传的是已经录好的整段配音。确认文案后，系统会按每段文案切分音频，再用真实配音时长做选片。
      </p>

      <label v-if="useTtsVoice" class="field">
        <span>配音通道</span>
        <select v-model="voiceMode" @change="voiceProfileId = ''">
          <option value="standard">{{ voiceModeLabel("standard") }}</option>
          <option value="clone">{{ voiceModeLabel("clone") }}</option>
        </select>
      </label>

      <label v-if="useTtsVoice" class="field">
        <span>{{ normalizedVoiceMode(voiceMode) === "clone" ? "克隆模板" : "普通音色" }}</span>
        <select v-model="voiceProfileId">
          <option v-for="profile in filteredProfiles" :key="profile.id" :value="profile.id">
            {{ profile.label }}
          </option>
        </select>
      </label>

      <label v-if="useTtsVoice" class="field">
        <span>配音语速</span>
        <select v-model="ttsSpeed">
          <option value="0.85">0.85x 较慢</option>
          <option value="1.00">1.00x 默认</option>
          <option value="1.10">1.10x 稍快</option>
          <option value="1.20">1.20x 更快</option>
        </select>
      </label>

      <details v-if="useTtsVoice" class="fold-panel">
        <summary>
          <div>
            <strong>{{ normalizedVoiceMode(voiceMode) === "clone" ? "查看克隆模板库" : "查看普通音色库" }}</strong>
            <small>当前可用模板 {{ filteredProfiles.length }} 个。</small>
          </div>
          <span class="section-pill">Template</span>
        </summary>
        <div class="voice-profile-library">
          <article
            v-for="profile in filteredProfiles"
            :key="profile.id"
            class="voice-profile-card"
            :class="{ active: profile.id === voiceProfileId }"
            @click="voiceProfileId = profile.id"
          >
            <div class="voice-profile-head">
              <strong>{{ profile.label }}</strong>
              <span v-if="profile.is_default" class="section-pill">默认</span>
            </div>
            <div class="voice-profile-copy">{{ profile.description || "项目内置音色/模板" }}</div>
            <audio v-if="profile.preview_available" controls preload="none" :src="profile.preview_url" />
          </article>
          <div v-if="!filteredProfiles.length" class="voice-profile-empty">暂无可用模板。</div>
        </div>
      </details>

      <div class="form-actions">
        <button type="submit" :disabled="submitting">开始 AI 粗剪</button>
        <p class="submit-status">{{ submitStatus }}</p>
      </div>
    </form>

    <section class="profile-builder">
      <details class="fold-panel">
        <summary>
          <div>
            <strong>新增克隆模板</strong>
            <small>上传参考音频和原文案，只用于 CosyVoice 克隆配音。</small>
          </div>
          <span class="section-pill">New</span>
        </summary>
        <form class="task-form fold-panel-body" @submit.prevent="createProfile">
          <label class="field">
            <span>模板名称</span>
            <input v-model="profileLabel" type="text" placeholder="例如：我的解说女声" required />
          </label>
          <div class="field-row">
            <label class="field">
              <span>语言标签</span>
              <input v-model="profileLanguage" type="text" placeholder="zh-CN" />
            </label>
            <label class="field">
              <span>模板说明</span>
              <input v-model="profileDescription" type="text" placeholder="偏稳重的赛事复盘声线" />
            </label>
          </div>
          <label class="field">
            <span>参考文案</span>
            <textarea v-model="profilePromptText" rows="4" required placeholder="填写参考音频里真实说出的文案。" />
          </label>
          <label class="field">
            <span>参考音频</span>
            <input type="file" accept="audio/*,video/*" required @change="onProfileAudioChange" />
          </label>
          <div class="form-actions">
            <button type="submit" :disabled="creatingProfile">创建克隆模板</button>
            <p class="submit-status">{{ profileStatus }}</p>
          </div>
        </form>
      </details>
    </section>
  </section>
</template>
