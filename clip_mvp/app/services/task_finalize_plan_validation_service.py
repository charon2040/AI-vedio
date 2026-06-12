from __future__ import annotations

from typing import Any, Dict, List

from app.domain.schemas import normalize_draft_beats


class TaskFinalizePlanValidationService:
    def estimate_beat_duration_ms(self, text: str) -> int:
        compact = "".join(str(text or "").split())
        if not compact:
            return 8000
        # Only used when TTS is disabled. It gives LLM a rough selection range,
        # not a real audio duration.
        return max(5000, min(45000, int((len(compact) / 4.2) * 1000)))

    def attach_estimated_beat_durations(
        self,
        beats: List[Dict[str, Any]],
        *,
        duration_seconds: int = 0,
    ) -> List[Dict[str, Any]]:
        normalized = normalize_draft_beats(beats)
        if not normalized:
            return []

        if duration_seconds > 0:
            total_ms = max(1000, int(duration_seconds) * 1000)
            weights = [
                max(1, len("".join(str(item.get("text", "") or "").split())))
                for item in normalized
            ]
            weight_total = max(1, sum(weights))
            estimated: List[Dict[str, Any]] = []
            assigned = 0
            for index, (item, weight) in enumerate(zip(normalized, weights)):
                if index == len(normalized) - 1:
                    duration_ms = max(1000, total_ms - assigned)
                else:
                    duration_ms = max(1000, int(total_ms * (weight / weight_total)))
                    assigned += duration_ms
                estimated.append({**item, "voice_duration_ms": duration_ms})
            return estimated

        return [
            {
                **item,
                "voice_duration_ms": self.estimate_beat_duration_ms(
                    str(item.get("text", "") or "")
                ),
            }
            for item in normalized
        ]

    def validate_segment_count(
        self,
        *,
        reviewed_beats: List[Dict[str, Any]],
        source_segments: List[Dict[str, Any]],
    ) -> None:
        if not source_segments:
            raise RuntimeError("没有匹配到有效片段，请修改文案后重试。")
        if len(source_segments) != len(reviewed_beats):
            raise RuntimeError(
                f"当前确认文案共有 {len(reviewed_beats)} 段，但素材只匹配出 {len(source_segments)} 段。"
                "请把文案改得更贴近素材内容后重试。"
            )

    def total_segment_duration_ms(self, source_segments: List[Dict[str, Any]]) -> int:
        return sum(
            max(0, int(item.get("end", 0) or 0) - int(item.get("start", 0) or 0))
            for item in source_segments
        )

    def validate_voice_duration_coverage(
        self,
        *,
        reviewed_beats: List[Dict[str, Any]],
        source_segments: List[Dict[str, Any]],
        total_duration_ms: int,
    ) -> None:
        target_voice_duration_ms = sum(
            max(0, int(item.get("voice_duration_ms", 0) or 0))
            for item in reviewed_beats
        )
        required_render_duration_ms = sum(
            max(
                max(0, int(segment.get("end", 0) or 0) - int(segment.get("start", 0) or 0)),
                max(0, int(beat.get("voice_duration_ms", 0) or 0)),
            )
            for segment, beat in zip(source_segments, reviewed_beats)
        )
        if (
            target_voice_duration_ms > 0
            and total_duration_ms < int(target_voice_duration_ms * 0.88)
        ):
            raise RuntimeError(
                "当前选片总时长明显短于配音总时长，已停止渲染以避免生成拉长的错误成片。"
                f" 选片约 {total_duration_ms / 1000:.1f}s，配音约 {target_voice_duration_ms / 1000:.1f}s。"
            )
        extra_pad_budget_ms = max(4000, int(max(target_voice_duration_ms, 1) * 0.06))
        if required_render_duration_ms > total_duration_ms + extra_pad_budget_ms:
            raise RuntimeError(
                "当前逐段选片仍不足以覆盖配音时长，已停止渲染以避免生成长时间补帧或静音段。"
                f" 选片约 {total_duration_ms / 1000:.1f}s，逐段至少需要 {required_render_duration_ms / 1000:.1f}s。"
            )


task_finalize_plan_validation_service = TaskFinalizePlanValidationService()
