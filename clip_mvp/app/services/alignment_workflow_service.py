from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

from app.domain.schemas import AlignmentPlan, normalize_draft_beats
from app.services.alignment_duration_service import alignment_duration_service
from app.services.alignment_subtitle_service import alignment_subtitle_service
from app.services.llm_service import llm_service


logger = logging.getLogger(__name__)

RecordTaskEventCallback = Callable[..., None]


class AlignmentWorkflowService:
    def validate_voice_aligned_segments(
        self,
        beats: List[Dict[str, Any]],
        source_segments: List[Dict[str, Any]],
    ) -> None:
        alignment_duration_service.validate_voice_aligned_segments(beats, source_segments)

    def validate_semantic_span_focus(
        self,
        beats: List[Dict[str, Any]],
        source_segments: List[Dict[str, Any]],
    ) -> None:
        alignment_duration_service.validate_semantic_span_focus(beats, source_segments)

    def _build_segments_from_global_llm_align(
        self,
        *,
        beats: List[Dict[str, Any]],
        subtitles: List[Dict[str, Any]],
        style: str,
        project_context: str,
    ) -> List[Dict[str, Any]]:
        normalized_subtitles = alignment_subtitle_service.normalize_subtitles_for_alignment(subtitles)
        if not normalized_subtitles or not beats:
            return []

        aligned_items = llm_service.align_beats_with_subtitles(
            beats,
            normalized_subtitles,
            style=style,
            project_context=project_context,
        )
        if len(aligned_items) != len(beats):
            return []

        aligned_by_id: Dict[str, Dict[str, Any]] = {}
        for item in aligned_items:
            beat_id = str(item.get("beat_id", "") or "").strip()
            if beat_id:
                aligned_by_id[beat_id] = item

        source_segments: List[Dict[str, Any]] = []
        last_end_index = -1
        for index, beat in enumerate(beats, start=1):
            beat_id = str(beat.get("id", "") or f"beat_{index}").strip()
            aligned = aligned_by_id.get(beat_id)
            if aligned is None and index - 1 < len(aligned_items):
                aligned = aligned_items[index - 1]
            if not aligned:
                return []

            semantic_start = int(aligned.get("semantic_start", aligned.get("start", 0)) or aligned.get("start", 0) or 0)
            semantic_end = int(aligned.get("semantic_end", aligned.get("end", 0)) or aligned.get("end", 0) or 0)
            overlap = alignment_subtitle_service.find_overlapping_range(
                normalized_subtitles,
                start_ms=semantic_start,
                end_ms=semantic_end,
            )
            if overlap is None:
                return []

            start_index, end_index = overlap
            if start_index <= last_end_index:
                start_index = last_end_index + 1
            if start_index > end_index or start_index >= len(normalized_subtitles):
                return []

            segment = alignment_subtitle_service.compose_segment_from_subtitles(
                normalized_subtitles,
                start_index=start_index,
                end_index=end_index,
                dubbing=str(beat.get("text", "") or "").strip(),
                voice_duration_ms=int(beat.get("voice_duration_ms", 0) or 0),
            )
            segment["semantic_start"] = int(segment.get("start", 0) or 0)
            segment["semantic_end"] = int(segment.get("end", 0) or 0)
            try:
                final_start = int(aligned.get("start", segment["semantic_start"]) or segment["semantic_start"])
                final_end = int(aligned.get("end", segment["semantic_end"]) or segment["semantic_end"])
            except Exception:
                final_start = int(segment["semantic_start"])
                final_end = int(segment["semantic_end"])
            if final_end > final_start:
                segment["start"] = final_start
                segment["end"] = final_end
                content = alignment_subtitle_service.content_for_subtitle_range(
                    normalized_subtitles,
                    start_ms=final_start,
                    end_ms=final_end,
                )
                if content:
                    segment["content"] = content
            source_segments.append(segment)
            last_end_index = end_index

        alignment_duration_service.validate_llm_selected_voice_durations(beats, source_segments)
        alignment_duration_service.validate_semantic_span_focus(beats, source_segments)
        return source_segments

    def plan_segments_with_global_llm(
        self,
        *,
        task_id: str,
        beats: List[Dict[str, Any]],
        synthesized_beats: List[Dict[str, Any]] | None = None,
        subtitles: List[Dict[str, Any]],
        style: str,
        project_context: str,
        record_task_event: RecordTaskEventCallback,
    ) -> AlignmentPlan:
        base_beats = normalize_draft_beats(beats)
        if not base_beats:
            return AlignmentPlan.empty(synthesized_beats=synthesized_beats or [])

        global_segments = self._build_segments_from_global_llm_align(
            beats=base_beats,
            subtitles=subtitles,
            style=style,
            project_context=project_context,
        )
        global_valid = bool(global_segments) and len(global_segments) == len(base_beats)

        if global_valid:
            logger.info(
                "Task %s using global LLM beat alignment as primary plan: beats=%s",
                task_id,
                len(base_beats),
            )
            record_task_event(
                task_id,
                event_type="alignment_completed",
                detail={
                    "beat_count": len(base_beats),
                    "segment_count": len(global_segments),
                    "selection_strategy": "global_llm_align",
                },
            )
            return AlignmentPlan.from_raw(
                beats=base_beats,
                synthesized_beats=synthesized_beats or [],
                source_segments=global_segments,
                selection_strategy="global_llm_align",
            )

        logger.warning(
            "Task %s global LLM beat alignment failed without auto-merge fallback: beats=%s",
            task_id,
            len(base_beats),
        )
        record_task_event(
            task_id,
            event_type="alignment_failed",
            detail={
                "beat_count": len(base_beats),
                "selection_strategy": "none",
            },
        )
        return AlignmentPlan.empty(
            beats=base_beats,
            synthesized_beats=synthesized_beats or [],
        )


alignment_workflow_service = AlignmentWorkflowService()
