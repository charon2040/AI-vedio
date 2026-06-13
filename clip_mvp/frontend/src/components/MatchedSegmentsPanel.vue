<script setup lang="ts">
import type { MatchedSegment } from "../types";
import { formatMs, shortText } from "../utils/format";

defineProps<{
  segments: MatchedSegment[];
}>();

function hasSemanticRange(segment: MatchedSegment): boolean {
  const semanticStart = Number(segment.semantic_start) || 0;
  const semanticEnd = Number(segment.semantic_end) || 0;
  if (semanticEnd <= semanticStart) return false;
  return semanticStart !== Number(segment.source_start || 0) || semanticEnd !== Number(segment.source_end || 0);
}
</script>

<template>
  <details v-if="segments.length" class="task-section" open>
    <summary>
      <div><strong>最终选片</strong><small>语义范围用于核对，最终剪入范围用于实际成片。</small></div>
      <span class="section-pill">{{ segments.length }} 段</span>
    </summary>
    <div class="segments">
      <div v-for="(segment, index) in segments" :key="index" class="segment">
        <div class="segment-time">
          最终剪入 {{ formatMs(segment.source_start) }} -> {{ formatMs(segment.source_end) }}
          | 输出 {{ formatMs(segment.start) }} -> {{ formatMs(segment.end) }}
        </div>
        <div v-if="hasSemanticRange(segment)" class="segment-semantic-time">
          语义参考 {{ formatMs(segment.semantic_start) }} -> {{ formatMs(segment.semantic_end) }}
        </div>
        <div class="segment-label">最终剪入范围对应字幕</div>
        <div class="segment-content">{{ segment.content || "匹配片段" }}</div>
        <template v-if="segment.dubbing">
          <div class="segment-label">对应配音段</div>
          <div class="segment-dubbing">{{ shortText(segment.dubbing, 140) }}</div>
        </template>
      </div>
    </div>
  </details>
</template>
