from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

import requests

from app.core.config import settings


logger = logging.getLogger(__name__)


class CosyVoiceRuntimeService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None

    def is_managed_local_service(self, provider: str | None = None) -> bool:
        value = str(provider or settings.tts_clone_provider or settings.tts_provider or "").strip().lower()
        return value in {"cosyvoice", "cosyvoice_service"}

    def is_subprocess_local_service(self, provider: str | None = None) -> bool:
        value = str(provider or settings.tts_clone_provider or settings.tts_provider or "").strip().lower()
        return value in {"cosyvoice_local", "local_cosyvoice"}

    def _health_url(self) -> str:
        return f"{str(settings.cosyvoice_base_url).rstrip('/')}/health"

    def _parsed_base_url(self):
        return urlparse(str(settings.cosyvoice_base_url))

    def _service_pid(self) -> int | None:
        if self._process is not None and self._process.poll() is None:
            return int(self._process.pid)

        parsed = self._parsed_base_url()
        port = int(parsed.port or 50000)
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception:
            return None

        pattern = re.compile(rf"^\s*TCP\s+\S+:{port}\s+\S+\s+LISTENING\s+(\d+)\s*$", re.IGNORECASE)
        for line in (result.stdout or "").splitlines():
            match = pattern.match(line.strip())
            if match:
                try:
                    return int(match.group(1))
                except Exception:
                    return None
        return None

    def _service_args(self) -> list[str]:
        parsed = self._parsed_base_url()
        host = parsed.hostname or "127.0.0.1"
        port = int(parsed.port or 50000)

        return [
            str(settings.cosyvoice_local_python),
            str(settings.cosyvoice_service_path),
            "--repo-dir",
            str(settings.cosyvoice_repo_dir),
            "--model-dir",
            str(settings.cosyvoice_model_dir),
            "--cache-dir",
            str(settings.cosyvoice_cache_dir),
            "--profiles-path",
            str(settings.tts_runtime_profile_manifest),
            "--host",
            host,
            "--port",
            str(port),
        ]

    def get_service_status(self, timeout: float = 2.0) -> Dict[str, Any]:
        try:
            response = requests.get(
                self._health_url(),
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            return {
                "healthy": True,
                "payload": payload,
                "pid": self._service_pid(),
            }
        except Exception as exc:
            return {
                "healthy": False,
                "error": str(exc),
                "pid": self._service_pid(),
            }

    def _start_service_process(self) -> None:
        python_bin = Path(settings.cosyvoice_local_python)
        service_path = settings.cosyvoice_service_path
        repo_dir = Path(settings.cosyvoice_repo_dir)
        model_dir = Path(settings.cosyvoice_model_dir)
        cache_dir = Path(settings.cosyvoice_cache_dir)

        if not python_bin.exists():
            raise RuntimeError(f"CosyVoice Python 环境不存在: {python_bin}")
        if not service_path.exists():
            raise RuntimeError(f"CosyVoice 服务脚本不存在: {service_path}")
        if not repo_dir.exists():
            raise RuntimeError(f"CosyVoice 仓库不存在: {repo_dir}")
        if not model_dir.exists():
            raise RuntimeError(f"CosyVoice 模型目录不存在: {model_dir}")

        cache_dir.mkdir(parents=True, exist_ok=True)
        stdout_handle = open(settings.cosyvoice_service_stdout_log, "a", encoding="utf-8")
        stderr_handle = open(settings.cosyvoice_service_stderr_log, "a", encoding="utf-8")

        popen_kwargs: Dict[str, Any] = {
            "stdout": stdout_handle,
            "stderr": stderr_handle,
            "cwd": str(settings.project_dir),
            "text": True,
        }

        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        self._process = subprocess.Popen(
            self._service_args(),
            **popen_kwargs,
        )
        logger.info(
            "Started local CosyVoice service: pid=%s base_url=%s",
            self._process.pid,
            settings.cosyvoice_base_url,
        )

    def _wait_until_healthy(self) -> Dict[str, Any]:
        deadline = time.time() + max(5, int(settings.cosyvoice_service_startup_seconds))
        last_error = ""
        while time.time() < deadline:
            time.sleep(1)
            status = self.get_service_status(timeout=4.0)
            if status.get("healthy"):
                return status
            last_error = str(status.get("error", "") or "")
        raise RuntimeError(
            "CosyVoice 常驻服务启动失败，请检查模型目录或日志文件："
            f"{settings.cosyvoice_service_stderr_log} {last_error}".strip()
        )

    def stop_service(self) -> None:
        pid = self._service_pid()
        if pid is None:
            self._process = None
            return

        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            else:
                os.kill(pid, 9)
        except Exception as exc:
            logger.warning("Failed to stop CosyVoice service pid=%s: %s", pid, exc)
        finally:
            self._process = None

        deadline = time.time() + 10
        while time.time() < deadline:
            if self._service_pid() is None:
                return
            time.sleep(0.5)

    def restart_service(self) -> Dict[str, Any]:
        if not self.is_managed_local_service():
            return {"healthy": False, "error": "provider_not_managed"}

        with self._lock:
            self.stop_service()
            self._start_service_process()
            return self._wait_until_healthy()

    def ensure_service_running(self) -> Dict[str, Any]:
        if not self.is_managed_local_service():
            return {"healthy": False, "error": "provider_not_managed"}

        status = self.get_service_status()
        if status.get("healthy"):
            return status

        with self._lock:
            status = self.get_service_status()
            if status.get("healthy"):
                return status

            self._start_service_process()
            return self._wait_until_healthy()


cosyvoice_runtime_service = CosyVoiceRuntimeService()
