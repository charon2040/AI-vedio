from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from app.domain.schemas import normalize_draft_beats
from app.services.task_finalize_plan_models import (
    FinalizePlanningResult,
    RecordTaskEventCallback,
    UpdateTaskCallback,
)
from app.services.task_finalize_script_planner import task_finalize_script_planner
from app.services.task_finalize_voice_planner import task_finalize_voice_planner
from app.services.task_run_context_service import TaskRunContext


class TaskFinalizePlanningService:
    def build_plan(
        self,
        *,
        context: TaskRunContext,
        subtitles: List[Dict[str, Any]],
        audio_path: Path,
        asr_cache_hit: bool,
        current_result: Dict[str, Any],
        update_task: UpdateTaskCallback,
        record_task_event: RecordTaskEventCallback,
    ) -> FinalizePlanningResult:
        reviewed_beats = normalize_draft_beats(current_result.get("draft_beats", []))
        if not reviewed_beats:
            raise RuntimeError("文案草稿为空，请先确认文案内容。")

        if context.enable_dubbing:
            return task_finalize_voice_planner.build_plan(
                context=context,
                reviewed_beats=reviewed_beats,
                subtitles=subtitles,
                audio_path=audio_path,
                asr_cache_hit=asr_cache_hit,
                update_task=update_task,
                record_task_event=record_task_event,
            )

        return task_finalize_script_planner.build_plan(
            context=context,
            reviewed_beats=reviewed_beats,
            subtitles=subtitles,
            audio_path=audio_path,
            asr_cache_hit=asr_cache_hit,
            update_task=update_task,
            record_task_event=record_task_event,
        )


task_finalize_planning_service = TaskFinalizePlanningService()
