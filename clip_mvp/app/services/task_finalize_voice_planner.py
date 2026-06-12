from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from app.domain.schemas import build_script_from_beats, normalize_draft_beats
from app.services.alignment_workflow_service import alignment_workflow_service
from app.services.task_finalize_plan_models import (
    FinalizePlanningResult,
    RecordTaskEventCallback,
    UpdateTaskCallback,
)
from app.services.task_finalize_plan_validation_service import task_finalize_plan_validation_service
from app.services.task_run_context_service import TaskRunContext
from app.services.voice_workflow_service import voice_workflow_service


class TaskFinalizeVoicePlanner:
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
        voice_source_label = "上传完整配音" if context.voice_source == "uploaded_voiceover" else context.voice_mode
        update_task(
            task_id,
            stage="synthesizing_voice",
            progress=80,
            message=f"正在根据确认后的文案准备配音（{len(reviewed_beats)} 段，{voice_source_label}）",
            artifacts={"audio_url": f"/audio/{audio_path.name}"},
            result={
                "subtitle_count": len(subtitles),
                "asr_cache_hit": asr_cache_hit,
                "review_status": "approved",
                "voice_source": context.voice_source,
                "voiceover_segment_count": len(reviewed_beats),
            },
        )
        if context.voice_source == "uploaded_voiceover":
            synthesized_beats = voice_workflow_service.split_uploaded_voiceover_beats(
                task_id=task_id,
                uploaded_voiceover_path=context.uploaded_voiceover_path,
                uploaded_voiceover_duration_ms=context.uploaded_voiceover_duration_ms,
                beats=reviewed_beats,
                update_task=update_task,
            )
        else:
            synthesized_beats = voice_workflow_service.synthesize_reviewed_beats(
                task_id=task_id,
                voice_mode=context.voice_mode,
                voice=context.voice_profile_ref,
                beats=reviewed_beats,
                speed=context.tts_speed,
                user_id=context.user_id,
                update_task=update_task,
            )
        if not synthesized_beats:
            raise RuntimeError("没有生成有效配音，请检查文案内容或配音配置。")

        reviewed_beats = normalize_draft_beats(synthesized_beats)
        approved_script = build_script_from_beats(reviewed_beats)
        update_task(
            task_id,
            stage="planning_from_voice",
            progress=86,
            message="已拿到真实配音时长，正在按语音时长选择视频片段",
            result={
                "draft_script": approved_script,
                "draft_beats": reviewed_beats,
                "voiceover_script": approved_script,
                "voiceover_segment_count": len(reviewed_beats),
            },
        )
        voice_plan = alignment_workflow_service.plan_segments_with_global_llm(
            task_id=task_id,
            beats=synthesized_beats,
            synthesized_beats=synthesized_beats,
            subtitles=subtitles,
            style=context.style,
            project_context=context.project_context,
            record_task_event=record_task_event,
        )
        reviewed_beats = voice_plan.beats_payload()
        synthesized_beats = voice_plan.synthesized_beats_payload()
        source_segments = voice_plan.source_segments_payload()
        approved_script = build_script_from_beats(reviewed_beats)
        selection_strategy = voice_plan.selection_strategy
        task_finalize_plan_validation_service.validate_segment_count(
            reviewed_beats=reviewed_beats,
            source_segments=source_segments,
        )
        total_duration_ms = task_finalize_plan_validation_service.total_segment_duration_ms(source_segments)
        task_finalize_plan_validation_service.validate_voice_duration_coverage(
            reviewed_beats=reviewed_beats,
            source_segments=source_segments,
            total_duration_ms=total_duration_ms,
        )
        alignment_workflow_service.validate_voice_aligned_segments(reviewed_beats, source_segments)
        return FinalizePlanningResult(
            reviewed_beats=reviewed_beats,
            synthesized_beats=synthesized_beats,
            source_segments=source_segments,
            approved_script=approved_script,
            selection_strategy=selection_strategy,
            total_duration_ms=total_duration_ms,
        )


task_finalize_voice_planner = TaskFinalizeVoicePlanner()
