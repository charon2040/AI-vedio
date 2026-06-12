<script setup lang="ts">
import { ref, watch } from "vue";
import type { DraftBeat, TaskItem } from "../types";

const props = defineProps<{
  task: TaskItem;
}>();

const emit = defineEmits<{
  saveDraft: [payload: { taskId: string; beats: DraftBeat[]; draftScript: string }];
  approveDraft: [payload: { taskId: string; beats: DraftBeat[]; draftScript: string }];
}>();

const draftBeats = ref<DraftBeat[]>([]);
const draftStatus = ref("确认前可以修改文案，也可以把长段拆开。");

function normalizeDraftBeats(task: TaskItem | null): DraftBeat[] {
  const raw = task?.result?.draft_beats || [];
  if (Array.isArray(raw) && raw.length) {
    return raw.map((item: any, index: number) => ({
      id: String(item.id || `beat_${index + 1}`),
      title: String(item.title || `第 ${index + 1} 段`),
      text: String(item.text || ""),
      order: Number(item.order || index + 1),
      voice_duration_ms: Number(item.voice_duration_ms || 0),
    }));
  }
  const script = String(task?.result?.draft_script || "");
  return script ? [{ id: "beat_1", title: "第 1 段", text: script, order: 1 }] : [];
}

function collectDraft() {
  const beats = draftBeats.value
    .map((beat, index) => ({
      ...beat,
      id: `beat_${index + 1}`,
      title: `第 ${index + 1} 段`,
      order: index + 1,
      text: String(beat.text || "").trim(),
    }))
    .filter((beat) => beat.text);
  return {
    beats,
    draftScript: beats.map((beat) => beat.text).join("\n"),
  };
}

function splitBeat(index: number) {
  const target = draftBeats.value[index];
  const text = String(target?.text || "").trim();
  if (text.length < 24) {
    draftStatus.value = "这段太短，不建议继续拆分。";
    return;
  }
  const punctuation = [...text]
    .map((char, idx) => ("。！？；;!?，,".includes(char) ? idx + 1 : -1))
    .filter((idx) => idx > 10 && idx < text.length - 10);
  const mid = text.length / 2;
  const splitIndex = punctuation.sort((left, right) => Math.abs(left - mid) - Math.abs(right - mid))[0] || Math.floor(mid);
  const before = text.slice(0, splitIndex).trim();
  const after = text.slice(splitIndex).trim();
  if (!before || !after) {
    draftStatus.value = "拆分位置不合适。";
    return;
  }
  draftBeats.value.splice(index, 1, { ...target, text: before }, { id: "", title: "", order: 0, text: after });
  draftStatus.value = "已拆分为两个 beat。";
}

function saveDraft() {
  const payload = collectDraft();
  if (!payload.beats.length) {
    draftStatus.value = "请至少保留一段文案。";
    return;
  }
  draftStatus.value = "正在保存文案草稿...";
  emit("saveDraft", { taskId: props.task.id, ...payload });
}

function approveDraft() {
  const payload = collectDraft();
  if (!payload.beats.length) {
    draftStatus.value = "请至少保留一段文案。";
    return;
  }
  draftStatus.value = "正在确认文案并继续处理...";
  emit("approveDraft", { taskId: props.task.id, ...payload });
}

watch(
  () => props.task,
  (task) => {
    draftBeats.value = normalizeDraftBeats(task);
  },
  { immediate: true },
);
</script>

<template>
  <details class="task-section" open>
    <summary>
      <div><strong>文案初稿确认</strong><small>这里修改的是最终配音文案，不会静默缩短。</small></div>
      <span class="section-pill">{{ draftBeats.length }} 段</span>
    </summary>
    <div class="task-section-body">
      <div v-for="(beat, index) in draftBeats" :key="index" class="voiceover-item draft-beat-editor">
        <div class="draft-beat-head">
          <span>第 {{ index + 1 }} 段</span>
          <button class="ghost-btn slim-btn" type="button" @click="splitBeat(index)">拆分</button>
        </div>
        <textarea v-model="beat.text" class="draft-beat-input" rows="4" />
      </div>
      <div class="form-actions">
        <button class="ghost-btn" type="button" @click="saveDraft">保存草稿</button>
        <button type="button" @click="approveDraft">确认文案并继续</button>
        <p class="submit-status">{{ draftStatus }}</p>
      </div>
    </div>
  </details>
</template>
