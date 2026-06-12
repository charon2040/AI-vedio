from __future__ import annotations

import logging
from typing import Any, Dict, List


logger = logging.getLogger(__name__)


class AlignmentDurationService:
    def selected_duration_tolerances(self, voice_duration_ms: int) -> Dict[str, int]:
        target_ms = max(0, int(voice_duration_ms or 0))
        if target_ms <= 0:
            return {
                "short_tolerance_ms": 0,
                "long_tolerance_ms": 0,
            }

        return {
            "short_tolerance_ms": 120,
            "long_tolerance_ms": 1000,
        }

    def aligned_duration_bounds(self, voice_duration_ms: int) -> Dict[str, int]:
        target_ms = max(0, int(voice_duration_ms or 0))
        if target_ms <= 0:
            return {
                "preferred_max_ms": 0,
                "hard_max_ms": 0,
            }

        return {
            "preferred_max_ms": max(target_ms + 8000, int(target_ms * 1.35)),
            "hard_max_ms": max(target_ms + 18000, int(target_ms * 1.65)),
        }

    def validate_voice_aligned_segments(
        self,
        beats: List[Dict[str, Any]],
        source_segments: List[Dict[str, Any]],
    ) -> None:
        if not beats or not source_segments:
            return

        total_actual_ms = 0
        total_hard_max_ms = 0
        offending: List[str] = []
        warnings: List[str] = []

        for index, (beat, segment) in enumerate(zip(beats, source_segments), start=1):
            target_ms = max(0, int(beat.get("voice_duration_ms", 0) or 0))
            actual_ms = max(0, int(segment.get("end", 0) or 0) - int(segment.get("start", 0) or 0))
            total_actual_ms += actual_ms
            bounds = self.aligned_duration_bounds(target_ms)
            preferred_max_ms = int(bounds.get("preferred_max_ms", 0) or 0)
            hard_max_ms = int(bounds.get("hard_max_ms", 0) or 0)
            total_hard_max_ms += hard_max_ms or actual_ms

            if target_ms <= 0 or actual_ms <= 0:
                continue
            if actual_ms > hard_max_ms > 0:
                offending.append(
                    f"第 {index} 段选片约 {actual_ms / 1000:.1f}s，明显超过配音 {target_ms / 1000:.1f}s 的允许上限 {hard_max_ms / 1000:.1f}s"
                )
            elif actual_ms > preferred_max_ms > 0:
                warnings.append(
                    f"第 {index} 段选片约 {actual_ms / 1000:.1f}s，已高于建议上限 {preferred_max_ms / 1000:.1f}s"
                )

        if total_hard_max_ms > 0 and total_actual_ms > total_hard_max_ms:
            offending.append(
                f"总选片约 {total_actual_ms / 1000:.1f}s，超过基于配音时长推算的总上限 {total_hard_max_ms / 1000:.1f}s"
            )

        if offending:
            detail = "；".join(offending[:3])
            raise RuntimeError(
                "最终逐段选片明显长于对应配音，已停止渲染以避免生成长时间空镜或错误延长成片。"
                f" {detail}。"
            )

        for message in warnings:
            logger.warning("Voice-aligned segment duration warning: %s", message)

    def validate_llm_selected_voice_durations(
        self,
        beats: List[Dict[str, Any]],
        source_segments: List[Dict[str, Any]],
        *,
        tolerance_ms: int | None = None,
    ) -> None:
        if not beats or not source_segments:
            return

        offending: List[str] = []
        previous_end = -1
        for index, (beat, segment) in enumerate(zip(beats, source_segments), start=1):
            target_ms = max(0, int(beat.get("voice_duration_ms", 0) or 0))
            start_ms = max(0, int(segment.get("start", 0) or 0))
            end_ms = max(start_ms, int(segment.get("end", 0) or 0))
            actual_ms = end_ms - start_ms
            title = str(beat.get("title", "") or f"第 {index} 段").strip()

            if previous_end >= 0 and start_ms < previous_end - 300:
                offending.append(
                    f"第 {index} 段“{title}”选片起点 {start_ms / 1000:.1f}s 早于上一段终点 {previous_end / 1000:.1f}s"
                )
            previous_end = max(previous_end, end_ms)

            if target_ms <= 0:
                continue
            tolerances = self.selected_duration_tolerances(target_ms)
            short_tolerance_ms = max(
                0,
                int(tolerance_ms if tolerance_ms is not None else tolerances["short_tolerance_ms"]),
            )
            long_tolerance_ms = max(0, int(tolerances["long_tolerance_ms"]))
            delta_ms = actual_ms - target_ms
            allowed_delta = long_tolerance_ms if delta_ms > 0 else short_tolerance_ms
            if actual_ms <= 0 or abs(delta_ms) > allowed_delta:
                direction = "长于" if delta_ms > 0 else "短于"
                offending.append(
                    f"第 {index} 段“{title}”LLM 选片 {actual_ms / 1000:.1f}s，"
                    f"配音 {target_ms / 1000:.1f}s，{direction}配音 {abs(delta_ms) / 1000:.1f}s，"
                    f"允许 {allowed_delta / 1000:.1f}s"
                )

        if offending:
            raise RuntimeError(
                "LLM 未按配音时长选出可直接剪入的画面，后端已停止，不再自动裁切、扩窗或冻结补帧。"
                + "；".join(offending[:5])
                + "。画面短于配音只允许 0.12s 内编码/时间戳误差；画面长于配音 1.0s 内会补静音尾巴。请重新生成/重跑对齐，或拆小对应文案段。"
            )

    def validate_semantic_span_focus(
        self,
        beats: List[Dict[str, Any]],
        source_segments: List[Dict[str, Any]],
    ) -> None:
        if not beats or not source_segments:
            return

        offending: List[str] = []
        for index, (beat, segment) in enumerate(zip(beats, source_segments), start=1):
            target_ms = max(0, int(beat.get("voice_duration_ms", 0) or 0))
            if target_ms <= 0:
                continue
            semantic_start = max(0, int(segment.get("semantic_start", segment.get("start", 0)) or 0))
            semantic_end = max(semantic_start, int(segment.get("semantic_end", segment.get("end", 0)) or 0))
            semantic_duration = semantic_end - semantic_start
            final_duration = max(0, int(segment.get("end", 0) or 0) - int(segment.get("start", 0) or 0))
            if semantic_duration <= 0 or final_duration <= 0:
                continue

            hard_focus_ms = max(target_ms + 30000, int(target_ms * 2.25))
            final_covers_little = final_duration < int(semantic_duration * 0.72)
            if semantic_duration > hard_focus_ms and final_covers_little:
                title = str(beat.get("title", "") or f"第 {index} 段").strip()
                offending.append(
                    f"第 {index} 段“{title}”语义参考约 {semantic_duration / 1000:.1f}s，"
                    f"但配音/最终剪入约 {target_ms / 1000:.1f}s。"
                    "这通常说明该段文案覆盖了多个不连续事件，LLM 只能在其中截取局部画面。"
                )

        if offending:
            raise RuntimeError(
                "当前文案段落覆盖范围过宽，已停止渲染以避免选片偏移。"
                + "；".join(offending[:3])
                + " 请把这些段落拆成更小的连续事件，或删掉该段中无法被同一段素材覆盖的内容。"
            )


alignment_duration_service = AlignmentDurationService()
