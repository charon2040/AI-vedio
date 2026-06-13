import type { TaskItem, VoiceMode, VoiceSource } from "../types";

export function normalizedVoiceMode(value: unknown): VoiceMode {
  return value === "clone" ? "clone" : "standard";
}

export function voiceModeLabel(value: unknown): string {
  return normalizedVoiceMode(value) === "clone"
    ? "克隆配音（CosyVoice 0.5B）"
    : "普通配音（CosyVoice）";
}

export function normalizedVoiceSource(value: unknown): VoiceSource {
  return value === "uploaded_voiceover" ? "uploaded_voiceover" : "tts";
}

export function voiceSourceLabel(value: unknown): string {
  return normalizedVoiceSource(value) === "uploaded_voiceover" ? "上传完整配音" : "AI TTS 配音";
}

export function stageLabel(stage: unknown): string {
  const key = String(stage || "");
  return {
    queued: "等待中",
    preparing: "准备任务",
    preparing_alignment_retry: "准备重试选片",
    extracting_audio: "抽取音频",
    transcribing: "FunASR 识别",
    drafting: "生成文案初稿",
    awaiting_script_review: "等待文案确认",
    planning: "AI 生成方案",
    planning_from_voice: "按配音选片",
    synthesizing_voice: "合成配音",
    aligning: "AI 文案对齐",
    rendering: "FFmpeg 粗剪",
    mixing_audio: "混音封装",
    completed: "完成",
    failed: "失败",
  }[key] || key || "--";
}

export function badgeClass(status: unknown): string {
  return status === "completed" || status === "failed" ? String(status) : "running";
}

export function formatDate(value: unknown): string {
  if (!value) return "--";
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

export function formatMs(ms: unknown): string {
  const total = Math.max(0, Number(ms) || 0);
  const minutes = Math.floor(total / 60000);
  const seconds = Math.floor((total % 60000) / 1000);
  const millis = Math.floor((total % 1000) / 100);
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${millis}`;
}

export function elapsedLabel(ms: unknown): string {
  const total = Math.max(0, Number(ms) || 0);
  if (total < 1000) return `${Math.round(total)}ms`;
  return `${(total / 1000).toFixed(1)}s`;
}

export function durationLabel(value: unknown): string {
  const seconds = Number(value) || 0;
  return seconds > 0 ? `${seconds}s` : "自动";
}

export function actualDurationLabel(ms: unknown): string {
  const total = Number(ms) || 0;
  return total > 0 ? formatMs(total) : "--";
}

export function finalDurationMs(task: TaskItem | null | undefined): number {
  const actual = Number(task?.result?.actual_duration_ms) || 0;
  if (actual > 0) return actual;
  return Number(task?.result?.total_duration_ms) || 0;
}

export function styleLabel(value: unknown): string {
  const key = String(value || "");
  return {
    summary: "总结",
    highlight: "高光",
    analysis: "复盘",
    short_hook: "短视频感",
  }[key] || key || "--";
}

export function selectionStrategyLabel(value: unknown): string {
  const key = String(value || "");
  return {
    global_llm_align: "全局 LLM 逐段匹配",
    none: "未命中",
  }[key] || key || "--";
}

export function eventTypeLabel(value: unknown): string {
  const key = String(value || "");
  return {
    task_created: "任务创建",
    task_started: "任务启动",
    workflow_started: "工作流启动",
    workflow_completed: "工作流完成",
    workflow_node_started: "节点开始",
    workflow_node_completed: "节点完成",
    workflow_node_failed: "节点失败",
    asr_cache_hit: "ASR 缓存命中",
    asr_completed: "ASR 完成",
    alignment_completed: "选片完成",
    alignment_failed: "选片失败",
    alignment_retry_requested: "重试选片",
    draft_saved: "草稿保存",
    draft_approved: "文案确认",
    draft_ready: "初稿完成",
    task_completed: "任务完成",
    task_failed: "任务失败",
    progress_updated: "进度更新",
  }[key] || stageLabel(key.replace(/^stage_/, "")) || key || "事件";
}

export function eventDetailLabel(detail: unknown): string {
  if (!detail || typeof detail !== "object") return "";
  const payload = detail as Record<string, unknown>;
  const nodeTitle = String(payload.node_title || "").trim();
  const nodeType = String(payload.node_type || "").trim();
  const durationMs = Number(payload.duration_ms) || 0;
  const phase = String(payload.phase || "").trim();
  const templateTitle = String(payload.workflow_template_title || "").trim();
  const pipelineMode = String(payload.pipeline_mode || "").trim();
  const parts = [
    nodeTitle || nodeType,
    phase ? `阶段 ${phase}` : "",
    templateTitle || pipelineMode,
    durationMs > 0 ? `耗时 ${elapsedLabel(durationMs)}` : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

export function boolLabel(value: unknown, yes = "开启", no = "关闭"): string {
  return value ? yes : no;
}

export function ttsSpeedValue(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}

export function ttsSpeedLabel(value: unknown): string {
  return `${ttsSpeedValue(value).toFixed(2)}x`;
}

export function shortText(value: unknown, maxLength = 84): string {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "--";
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}...` : text;
}

export function canDeleteTask(task: TaskItem | null | undefined): boolean {
  return task?.status === "completed" || task?.status === "failed" || task?.status === "waiting_review";
}

export function canRetryAlignment(task: TaskItem | null | undefined): boolean {
  const beats = task?.result?.draft_beats;
  return (
    task?.status === "failed"
    && task?.result?.review_status === "approved"
    && Array.isArray(beats)
    && beats.length > 0
  );
}

export function isAwaitingDraftReview(task: TaskItem | null | undefined): boolean {
  return task?.status === "waiting_review" || task?.stage === "awaiting_script_review" || task?.result?.review_status === "awaiting_review";
}
