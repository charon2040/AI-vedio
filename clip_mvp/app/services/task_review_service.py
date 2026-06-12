from __future__ import annotations

from typing import Any, Dict, List

from app.domain.schemas import build_script_from_beats, normalize_draft_beats
from app.services.task_runner_service import task_runner_service
from app.services.task_state_service import task_state_service
from app.services.task_store_service import task_store_service
from app.services.task_worker_service import task_worker_service


class TaskReviewService:
    def update_draft(
        self,
        task_id: str,
        *,
        draft_script: str = "",
        draft_beats: List[Dict[str, Any]] | None = None,
        user_id: str = "local",
    ) -> Dict[str, Any]:
        task = task_store_service.get_task(task_id, user_id=user_id)
        if not task:
            return {}
        draft_patch = self.build_draft_save_patch(
            task=task,
            draft_script=draft_script,
            draft_beats=draft_beats,
        )

        return task_state_service.update_task(
            task_id,
            event_type="draft_saved",
            event_detail=draft_patch["event_detail"],
            result=draft_patch["result"],
        )

    def approve_draft(
        self,
        task_id: str,
        *,
        draft_script: str = "",
        draft_beats: List[Dict[str, Any]] | None = None,
        user_id: str = "local",
    ) -> Dict[str, Any]:
        task = task_store_service.get_task(task_id, user_id=user_id)
        if not task:
            raise ValueError("Task not found")

        self.update_draft(
            task_id,
            draft_script=draft_script,
            draft_beats=draft_beats,
            user_id=user_id,
        )
        updated_task = task_store_service.get_task(task_id, user_id=user_id)
        approval = self.build_draft_approval_patch(task=updated_task)
        approval_patch = approval["patch"]
        updated = task_state_service.update_task(
            task_id,
            event_type="draft_approved",
            event_detail=approval["event_detail"],
            **approval_patch,
        )
        task_worker_service.start_task(
            task_id,
            phase="finalize",
            runner=task_runner_service.run_task,
        )
        return updated

    def retry_alignment(
        self,
        task_id: str,
        *,
        user_id: str = "local",
    ) -> Dict[str, Any]:
        task = task_store_service.get_task(task_id, user_id=user_id)
        if not task:
            raise ValueError("Task not found")
        if str(task.get("status", "") or "") != "failed":
            raise ValueError("只有失败任务才能从配音后重试选片")

        result = task.get("result", {}) or {}
        beats = normalize_draft_beats(result.get("draft_beats", []))
        if str(result.get("review_status", "") or "") != "approved" or not beats:
            raise ValueError("当前任务没有已确认文案，不能直接重试选片")

        updated = task_state_service.update_task(
            task_id,
            status="queued",
            stage="queued",
            progress=84,
            message="配音已完成，准备重新请求大模型选片",
            error="",
            event_type="alignment_retry_requested",
            event_detail={"beat_count": len(beats)},
            result={
                "matched_segments": [],
                "segment_count": 0,
                "selection_strategy": "",
                "total_duration_ms": 0,
                "clip_plan_id": "",
            },
        )
        task_worker_service.start_task(
            task_id,
            phase="retry_alignment",
            runner=task_runner_service.run_task,
        )
        return updated

    def build_draft_save_patch(
        self,
        *,
        task: Dict[str, Any],
        draft_script: str = "",
        draft_beats: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        if task.get("status") != "waiting_review":
            raise ValueError("只有等待文案确认的任务才能修改草稿")

        existing_result = task.get("result", {}) or {}
        beats = normalize_draft_beats(
            draft_beats if draft_beats is not None else existing_result.get("draft_beats", [])
        )
        script = str(draft_script or "").strip() or build_script_from_beats(beats)
        if not beats and script:
            beats = [
                {
                    "id": "beat_1",
                    "title": "第 1 段",
                    "text": script,
                    "order": 1,
                    "voice_duration_ms": 0,
                }
            ]
        if not script:
            script = build_script_from_beats(beats)

        return {
            "event_detail": {
                "beat_count": len(beats),
                "script_chars": len(script),
            },
            "result": {
                "draft_script": script,
                "draft_beats": beats,
                "review_status": "awaiting_review",
            },
        }

    def build_draft_approval_patch(self, *, task: Dict[str, Any]) -> Dict[str, Any]:
        if task.get("status") != "waiting_review":
            raise ValueError("只有等待文案确认的任务才能继续处理")

        result = task.get("result", {}) or {}
        beats = normalize_draft_beats(result.get("draft_beats", []))
        script = str(result.get("draft_script", "") or "").strip()
        if not beats:
            raise ValueError("Draft beats are empty")
        if not script:
            script = build_script_from_beats(beats)

        return {
            "event_detail": {
                "beat_count": len(beats),
                "script_chars": len(script),
            },
            "patch": {
                "status": "queued",
                "stage": "queued",
                "progress": 72,
                "message": "文案已确认，准备继续配音与选片",
                "error": "",
                "result": {
                    "draft_script": script,
                    "draft_beats": beats,
                    "review_status": "approved",
                    "script": script,
                    "voiceover_script": build_script_from_beats(beats),
                },
            },
        }


task_review_service = TaskReviewService()
