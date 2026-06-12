from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from app.core.db import app_db


logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ClipPlanService:
    def list_clip_plans_for_task(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not task:
            return []

        items: List[Dict[str, Any]] = []
        source_hash = str(task.get("source_hash", "") or "")
        user_id = str(task.get("user_id", "") or "local")
        if source_hash:
            items.extend(app_db.list_clip_plans(source_hash=source_hash, user_id=user_id))
        items.extend(app_db.list_clip_plans(task_id=str(task.get("id", "") or ""), user_id=user_id))

        deduped: Dict[str, Dict[str, Any]] = {}
        for item in sorted(items, key=lambda value: value.get("created_at", ""), reverse=True):
            deduped.setdefault(str(item.get("id", "")), item)
        return list(deduped.values())

    def _build_backfill_segments(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        result = task.get("result", {}) or {}
        matched_segments = result.get("matched_segments", []) or []
        source_segments: List[Dict[str, Any]] = []
        for segment in matched_segments:
            try:
                start = int(segment.get("source_start", segment.get("start", 0)) or 0)
                end = int(segment.get("source_end", segment.get("end", 0)) or 0)
            except Exception:
                continue
            if end <= start:
                continue

            item: Dict[str, Any] = {
                "start": start,
                "end": end,
                "content": str(segment.get("content", "") or "").strip(),
            }
            dubbing = str(segment.get("dubbing", "") or "").strip()
            if dubbing:
                item["dubbing"] = dubbing
            source_segments.append(item)
        return source_segments

    def build_backfill_clip_plan(self, task: Dict[str, Any]) -> Dict[str, Any]:
        payload = task.get("payload", {}) or {}
        result = task.get("result", {}) or {}
        source_segments = self._build_backfill_segments(task)
        total_duration_ms = sum(
            max(0, int(segment["end"]) - int(segment["start"]))
            for segment in source_segments
        )
        return {
            "id": str(result.get("clip_plan_id") or f"backfill_{task['id']}"),
            "user_id": str(task.get("user_id", "") or "local"),
            "task_id": str(task.get("id", "")),
            "source_hash": str(task.get("source_hash", "") or ""),
            "request_text": str(payload.get("request_text", "") or ""),
            "request_mode": str(payload.get("request_mode", "requirements") or "requirements"),
            "duration_seconds": int(payload.get("duration_seconds", 0) or 0),
            "style": str(payload.get("style", "") or ""),
            "script": str(result.get("script", "") or ""),
            "suggestions": result.get("suggestions", []) or [],
            "segments": source_segments,
            "plan_mode": str(result.get("plan_mode", "") or ""),
            "total_duration_ms": int(result.get("total_duration_ms", 0) or total_duration_ms),
            "created_at": str(task.get("created_at", "") or _now_iso()),
            "updated_at": str(task.get("updated_at", "") or _now_iso()),
        }

    def ensure_plan_metadata(self, task: Dict[str, Any]) -> Dict[str, Any]:
        if not task or task.get("status") != "completed":
            return {}

        result = task.get("result", {}) or {}
        matched_segments = result.get("matched_segments", []) or []
        if not matched_segments:
            return {}

        task_id = str(task.get("id", "") or "")
        plans = app_db.list_clip_plans(
            task_id=task_id,
            user_id=str(task.get("user_id", "") or "local"),
        )
        if not plans:
            backfilled = self.build_backfill_clip_plan(task)
            app_db.upsert_clip_plan(backfilled)
            plans = [backfilled]
            logger.info("Backfilled clip plan for historical task %s", task_id)

        latest_plan = plans[0]
        result_patch: Dict[str, Any] = {}
        if not result.get("clip_plan_id"):
            result_patch["clip_plan_id"] = latest_plan.get("id", "")
        if not int(result.get("total_duration_ms", 0) or 0):
            result_patch["total_duration_ms"] = int(latest_plan.get("total_duration_ms", 0) or 0)
        return result_patch

    def upsert_clip_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        return app_db.upsert_clip_plan(plan)


clip_plan_service = ClipPlanService()
