from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Dict, List

from app.services.clip_plan_service import clip_plan_service
from app.services.render_workflow_service import render_workflow_service
from app.services.task_event_service import now_iso
from app.services.task_finalize_plan_models import FinalizePlanningResult
from app.services.task_run_context_service import TaskRunContext


logger = logging.getLogger(__name__)

UpdateTaskCallback = Callable[..., Dict[str, Any]]
RecordTaskEventCallback = Callable[..., None]


class TaskFinalizeOutputService:
    def _build_voiceover_script(self, segments: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for segment in segments or []:
            text = str(segment.get("dubbing", "") or segment.get("content", "") or "").strip()
            if text:
                lines.append(text)
        return "\n".join(lines)

    def render_output(
        self,
        *,
        context: TaskRunContext,
        subtitles: List[Dict[str, Any]],
        suggestions: List[Any],
        plan: FinalizePlanningResult,
        update_task: UpdateTaskCallback,
        record_task_event: RecordTaskEventCallback,
    ) -> None:
        task_id = context.task_id
        source_segments = plan.source_segments
        if not source_segments:
            raise RuntimeError("没有匹配到有效片段，请调整要求、改写文案，或检查素材内容。")

        clip_plan_id = uuid.uuid4().hex[:12]
        plan_mode = "draft_voice_align" if context.enable_dubbing else "draft_script_align"
        clip_plan_service.upsert_clip_plan(
            {
                "id": clip_plan_id,
                "user_id": context.user_id,
                "task_id": task_id,
                "source_hash": context.source_hash,
                "request_text": context.request_text,
                "request_mode": context.request_mode,
                "duration_seconds": context.duration_seconds,
                "style": context.style,
                "script": plan.approved_script,
                "suggestions": suggestions,
                "segments": source_segments,
                "plan_mode": plan_mode,
                "total_duration_ms": plan.total_duration_ms,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
        )

        update_task(
            task_id,
            stage="rendering",
            progress=90,
            message="正在剪辑并拼接粗剪视频",
            result={
                "segment_count": len(source_segments),
                "matched_segments": render_workflow_service.build_timeline_segments(source_segments),
                "script": plan.approved_script,
                "suggestions": suggestions,
                "plan_mode": plan_mode,
                "selection_strategy": plan.selection_strategy,
                "total_duration_ms": plan.total_duration_ms,
                "clip_plan_id": clip_plan_id,
                "voiceover_enabled": context.enable_dubbing,
                "voiceover_script": self._build_voiceover_script(source_segments),
                "draft_script": plan.approved_script,
                "draft_beats": plan.reviewed_beats,
            },
        )

        render_result = render_workflow_service.render_final_output(
            task_id=task_id,
            source_path=context.source_path,
            original_filename=context.original_filename,
            source_segments=source_segments,
            subtitles=subtitles,
            reviewed_beats=plan.reviewed_beats,
            synthesized_beats=plan.synthesized_beats,
            enable_dubbing=context.enable_dubbing,
            keep_original_audio=context.keep_original_audio,
            total_duration_ms=plan.total_duration_ms,
            output_path=context.output_path,
            subtitle_work_path=context.subtitle_work_path,
            raw_output_path=context.raw_output_path,
            srt_path=context.srt_path,
            ass_path=context.ass_path,
            edl_path=context.edl_path,
            voiceover_path=context.voiceover_path,
            update_task=update_task,
            record_task_event=record_task_event,
        )

        update_task(
            task_id,
            status="completed",
            stage="completed",
            progress=100,
            message="任务完成，可以预览和下载结果",
            error="",
            artifacts=render_result.artifacts,
            result={
                "review_status": "approved",
                "actual_duration_ms": render_result.actual_duration_ms,
                "voiceover_duration_ms": render_result.voiceover_duration_ms,
                "selection_strategy": plan.selection_strategy,
            },
        )
        logger.info("Task %s finished successfully", task_id)


task_finalize_output_service = TaskFinalizeOutputService()
