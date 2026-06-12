from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List

from app.services.task_finalize_output_service import task_finalize_output_service
from app.services.task_finalize_planning_service import task_finalize_planning_service
from app.services.task_run_context_service import TaskRunContext


UpdateTaskCallback = Callable[..., Dict[str, Any]]
RecordTaskEventCallback = Callable[..., None]


class TaskFinalizeWorkflowService:
    def run_finalize(
        self,
        *,
        context: TaskRunContext,
        subtitles: List[Dict[str, Any]],
        audio_path: Path,
        asr_cache_hit: bool,
        current_result: Dict[str, Any],
        update_task: UpdateTaskCallback,
        record_task_event: RecordTaskEventCallback,
    ) -> None:
        suggestions = current_result.get("suggestions", []) or []
        plan = task_finalize_planning_service.build_plan(
            context=context,
            subtitles=subtitles,
            audio_path=audio_path,
            asr_cache_hit=asr_cache_hit,
            current_result=current_result,
            update_task=update_task,
            record_task_event=record_task_event,
        )
        task_finalize_output_service.render_output(
            context=context,
            subtitles=subtitles,
            suggestions=suggestions,
            plan=plan,
            update_task=update_task,
            record_task_event=record_task_event,
        )


task_finalize_workflow_service = TaskFinalizeWorkflowService()
