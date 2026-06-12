<script setup lang="ts">
import { computed } from "vue";
import type { ClipPlan, DraftBeat, ProjectKnowledge, TaskEvent, TaskItem, VoiceProfile } from "../types";
import {
  actualDurationLabel,
  badgeClass,
  boolLabel,
  canDeleteTask,
  canRetryAlignment,
  durationLabel,
  finalDurationMs,
  formatDate,
  isAwaitingDraftReview,
  selectionStrategyLabel,
  stageLabel,
  styleLabel,
  ttsSpeedLabel,
  voiceModeLabel,
  voiceSourceLabel,
} from "../utils/format";
import ClipPlansPanel from "./ClipPlansPanel.vue";
import DraftReviewPanel from "./DraftReviewPanel.vue";
import MatchedSegmentsPanel from "./MatchedSegmentsPanel.vue";
import ReplanPanel from "./ReplanPanel.vue";
import TaskEventTimeline from "./TaskEventTimeline.vue";

const emit = defineEmits<{
  delete: [taskId: string];
  saveDraft: [payload: { taskId: string; beats: DraftBeat[]; draftScript: string }];
  approveDraft: [payload: { taskId: string; beats: DraftBeat[]; draftScript: string }];
  replan: [payload: { taskId: string; formData: FormData }];
  retryAlignment: [taskId: string];
}>();

const props = defineProps<{
  task: TaskItem | null;
  plans: ClipPlan[];
  plansLoading: boolean;
  voiceProfiles: VoiceProfile[];
  knowledgeItems: ProjectKnowledge[];
}>();

const awaitingReview = computed(() => isAwaitingDraftReview(props.task));
const retryAlignmentAvailable = computed(() => canRetryAlignment(props.task));
const taskEvents = computed<TaskEvent[]>(() => (Array.isArray(props.task?.events) ? props.task!.events! : []));
const matchedSegments = computed(() => props.task?.result?.matched_segments || []);
const suggestions = computed<string[]>(() => props.task?.result?.suggestions || []);
const voiceSummary = computed(() => {
  if (!props.task?.payload?.enable_dubbing) return "无配音";
  if (props.task.payload.voice_source === "uploaded_voiceover") return voiceSourceLabel("uploaded_voiceover");
  return voiceModeLabel(props.task.payload.voice_mode);
});
const workflowSummary = computed(() => {
  return String(
    props.task?.payload?.workflow_template_title
    || props.task?.payload?.pipeline_mode
    || "narration_clip",
  );
});
</script>

<template>
  <section class="panel detail-panel">
    <div class="panel-header">
      <h2>任务状态</h2>
      <p>系统先生成文案初稿，等待确认，再继续配音、选片和导出。</p>
    </div>

    <div v-if="!task" class="empty-state">提交一个任务后，这里会出现实时进度。</div>
    <article v-else class="task-detail">
      <div class="task-summary">
        <div class="task-summary-main">
          <div class="task-head">
            <div>
              <div class="task-id">Task {{ task.id }}</div>
              <h3>{{ task.payload?.original_filename || "--" }}</h3>
            </div>
            <div class="task-head-side">
              <span class="badge" :class="badgeClass(task.status)">{{ stageLabel(task.stage) }}</span>
              <button
                v-if="retryAlignmentAvailable"
                class="ghost-btn slim-btn"
                type="button"
                @click="emit('retryAlignment', task.id)"
              >
                从配音后重新选片
              </button>
              <button v-if="canDeleteTask(task)" class="ghost-btn danger-btn slim-btn" type="button" @click="emit('delete', task.id)">删除任务</button>
            </div>
          </div>
          <div class="task-inline-meta">
            <span>{{ formatDate(task.created_at) }}</span>
            <span>{{ styleLabel(task.payload?.style) }}</span>
            <span>{{ workflowSummary }}</span>
            <span>{{ boolLabel(task.payload?.enable_dubbing, "配音开启", "无配音") }}</span>
            <span>{{ voiceSummary }}</span>
            <span>Plan {{ task.result?.clip_plan_id || "--" }}</span>
          </div>
          <p class="muted">{{ task.message }}</p>
          <div class="progress-wrap">
            <div class="progress-bar"><span :style="{ width: `${Math.max(0, Math.min(100, task.progress || 0))}%` }"></span></div>
          </div>
          <div v-if="Object.keys(task.artifacts || {}).length" class="task-links task-links-inline">
            <a v-if="task.artifacts.output_video_url" :href="task.artifacts.output_video_url" target="_blank">下载 MP4</a>
            <a v-if="task.artifacts.srt_url" :href="task.artifacts.srt_url" target="_blank">下载 SRT</a>
            <a v-if="task.artifacts.edl_url" :href="task.artifacts.edl_url" target="_blank">下载 EDL</a>
            <a v-if="task.artifacts.audio_url" :href="task.artifacts.audio_url" target="_blank">查看 WAV</a>
            <a v-if="task.artifacts.uploaded_voiceover_url" :href="task.artifacts.uploaded_voiceover_url" target="_blank">试听上传配音</a>
            <a v-if="task.artifacts.voiceover_audio_url" :href="task.artifacts.voiceover_audio_url" target="_blank">下载配音 WAV</a>
          </div>
        </div>

        <div class="task-summary-side">
          <div class="metric-grid">
            <div class="metric-card"><span>工作流</span><strong>{{ workflowSummary }}</strong></div>
            <div class="metric-card"><span>选片策略</span><strong>{{ selectionStrategyLabel(task.result?.selection_strategy) }}</strong></div>
            <div class="metric-card"><span>目标时长</span><strong>{{ durationLabel(task.payload?.duration_seconds) }}</strong></div>
            <div class="metric-card"><span>成片时长</span><strong>{{ actualDurationLabel(finalDurationMs(task)) }}</strong></div>
            <div class="metric-card"><span>字幕句数</span><strong>{{ task.result?.subtitle_count ?? 0 }}</strong></div>
            <div class="metric-card"><span>片段数</span><strong>{{ task.result?.segment_count ?? 0 }}</strong></div>
            <div class="metric-card">
              <span>{{ task.payload?.voice_source === "uploaded_voiceover" ? "配音来源" : "配音语速" }}</span>
              <strong>{{ task.payload?.voice_source === "uploaded_voiceover" ? voiceSourceLabel(task.payload?.voice_source) : ttsSpeedLabel(task.payload?.tts_speed) }}</strong>
            </div>
          </div>
        </div>
      </div>

      <div v-if="task.error" class="task-alert">{{ task.error }}</div>
      <div v-if="task.artifacts?.output_video_url" class="task-media">
        <div class="task-block-title">结果预览</div>
        <video class="result-video" :src="task.artifacts.output_video_url" controls />
      </div>

      <div class="task-sections">
        <TaskEventTimeline :events="taskEvents" />

        <DraftReviewPanel
          v-if="awaitingReview"
          :task="task"
          @save-draft="emit('saveDraft', $event)"
          @approve-draft="emit('approveDraft', $event)"
        />

        <details v-if="suggestions.length" class="task-section">
          <summary><div><strong>优化建议</strong><small>LLM 返回的剪辑建议</small></div></summary>
          <ul class="task-list">
            <li v-for="item in suggestions" :key="item">{{ item }}</li>
          </ul>
        </details>

        <MatchedSegmentsPanel :segments="matchedSegments" />

        <ClipPlansPanel :task="task" :plans="plans" :plans-loading="plansLoading" />

        <ReplanPanel
          :task="task"
          :voice-profiles="voiceProfiles"
          :knowledge-items="knowledgeItems"
          @replan="emit('replan', $event)"
        />
      </div>
    </article>
  </section>
</template>
