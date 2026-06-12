from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from app.domain.schemas import build_script_from_beats
from app.services.alignment_workflow_service import alignment_workflow_service
from app.services.task_finalize_plan_models import (
    FinalizePlanningResult,
    RecordTaskEventCallback,
    UpdateTaskCallback,
)
from app.services.task_finalize_plan_validation_service import task_finalize_plan_validation_service
from app.services.task_run_context_service import TaskRunContext


class TaskFinalizeScriptPlanner:
    def build_plan(
        self,
        *,
        context: TaskRunContext,
        reviewed_beats: List[Dict[str, Any]],
        subtitles: List[Dict[str, Any]],
        audio_path: Path,
        asr_cache_hit: bool,
        update_task: UpdateTaskCallback,
        record_task_event: RecordTaskEventCallback,
    ) -> FinalizePlanningResult:
        task_id = context.task_id
        reviewed_beats = task_finalize_plan_validation_service.attach_estimated_beat_durations(
            reviewed_beats,
            duration_seconds=context.duration_seconds,
        )
        approved_script = build_script_from_beats(reviewed_beats)
        update_task(
            task_id,
            stage="planning",
            progress=82,
            message="文案已确认，正在按 beat 全量字幕选片",
            artifacts={"audio_url": f"/audio/{audio_path.name}"},
            result={
                "subtitle_count": len(subtitles),
                "asr_cache_hit": asr_cache_hit,
                "review_status": "approved",
                "draft_script": approved_script,
                "draft_beats": reviewed_beats,
            },
        )
        script_plan = alignment_workflow_service.plan_segments_with_global_llm(
            task_id=task_id,
            beats=reviewed_beats,
            subtitles=subtitles,
            style=context.style,
            project_context=context.project_context,
            record_task_event=record_task_event,
        )
        reviewed_beats = script_plan.beats_payload()
        source_segments = script_plan.source_segments_payload()
        selection_strategy = script_plan.selection_strategy
        task_finalize_plan_validation_service.validate_segment_count(
            reviewed_beats=reviewed_beats,
            source_segments=source_segments,
        )
        total_duration_ms = task_finalize_plan_validation_service.total_segment_duration_ms(source_segments)
        alignment_workflow_service.validate_voice_aligned_segments(reviewed_beats, source_segments)
        return FinalizePlanningResult(
            reviewed_beats=reviewed_beats,
            synthesized_beats=[],
            source_segments=source_segments,
            approved_script=build_script_from_beats(reviewed_beats),
            selection_strategy=selection_strategy,
            total_duration_ms=total_duration_ms,
        )


task_finalize_script_planner = TaskFinalizeScriptPlanner()
