from __future__ import annotations

import argparse
import io
import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


MODEL = None
NATIVE_SPEAKERS: set[str] = set()
PROFILE_SPEAKERS: set[str] = set()
MODEL_DIR = ""
MODEL_TYPE = ""
PROFILES_PATH = ""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-dir", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--cache-dir", default="")
    parser.add_argument("--profiles-path", default="")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=50000)
    return parser.parse_args()


def _configure_paths(repo_dir: Path) -> None:
    sys.path.insert(0, str(repo_dir))
    sys.path.insert(0, str(repo_dir / "third_party" / "Matcha-TTS"))


def _configure_cache(cache_dir: Path | None) -> None:
    if cache_dir is None:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache_dir))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(cache_dir / "hub"))
    os.environ.setdefault("MODELSCOPE_CACHE", str(cache_dir / "modelscope"))
    os.environ.setdefault("COSYVOICE_DISABLE_WETEXT", "1")


def _load_model(repo_dir: Path, model_dir: Path):
    _configure_paths(repo_dir)
    print(f"[cosyvoice-server] importing repo from {repo_dir}", flush=True)
    from cosyvoice.cli.cosyvoice import AutoModel

    print(f"[cosyvoice-server] loading model from {model_dir}", flush=True)
    return AutoModel(model_dir=str(model_dir))


def _synthesize_wav_bytes_from_generator(generator) -> bytes:
    import torch
    import torchaudio

    chunks = []
    for result in generator:
        speech = result.get("tts_speech")
        if speech is None or speech.numel() <= 0:
            continue
        chunks.append(speech.detach().cpu())

    if not chunks:
        raise RuntimeError("CosyVoice 没有生成有效音频")

    merged = chunks[0] if len(chunks) == 1 else torch.cat(chunks, dim=1)
    buffer = io.BytesIO()
    torchaudio.save(buffer, merged, MODEL.sample_rate, format="wav")
    return buffer.getvalue()


def _normalize_speed(value) -> float:
    try:
        speed = float(value if value is not None else 1.0)
    except Exception:
        speed = 1.0
    return max(0.5, min(2.0, speed))


def _synthesize_sft_wav_bytes(*, text: str, voice: str, speed: float = 1.0) -> bytes:
    if MODEL is None:
        raise RuntimeError("CosyVoice model is not ready")
    if voice not in NATIVE_SPEAKERS:
        raise RuntimeError(f"SFT 音色不存在或当前模型不支持: {voice}")

    print(
        f"[cosyvoice-server] synthesize_sft chars={len(text)} voice={voice} speed={speed:.2f}",
        flush=True,
    )
    return _synthesize_wav_bytes_from_generator(
        MODEL.inference_sft(text, voice, stream=False, speed=speed)
    )


def _synthesize_zero_shot_spk_wav_bytes(*, text: str, voice: str, speed: float = 1.0) -> bytes:
    if MODEL is None:
        raise RuntimeError("CosyVoice model is not ready")
    if voice not in PROFILE_SPEAKERS:
        raise RuntimeError(f"Zero-shot profile 不存在: {voice}")

    print(
        f"[cosyvoice-server] synthesize_profile chars={len(text)} voice={voice} speed={speed:.2f}",
        flush=True,
    )
    return _synthesize_wav_bytes_from_generator(
        MODEL.inference_zero_shot(
            text,
            "",
            "",
            zero_shot_spk_id=voice,
            stream=False,
            speed=speed,
        )
    )


def _detect_model_type(model_dir: Path) -> str:
    if (model_dir / "cosyvoice3.yaml").exists():
        return "cosyvoice3"
    if (model_dir / "cosyvoice2.yaml").exists():
        return "cosyvoice2"
    if (model_dir / "cosyvoice.yaml").exists():
        return "cosyvoice1"
    return "unknown"


def _load_native_speakers() -> set[str]:
    try:
        speakers = MODEL.list_available_spks()
    except Exception as exc:
        print(f"[cosyvoice-server] failed to load native speakers: {exc}", flush=True)
        return set()
    return {str(item).strip() for item in speakers if str(item).strip()}


def _load_profiles(profiles_path: Path) -> set[str]:
    if not profiles_path.exists():
        print(f"[cosyvoice-server] profiles manifest not found: {profiles_path}", flush=True)
        return set()

    try:
        payload = json.loads(profiles_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[cosyvoice-server] failed to read profiles manifest: {exc}", flush=True)
        return set()

    if not isinstance(payload, dict):
        return set()

    loaded: set[str] = set()
    for voice, item in payload.items():
        if not isinstance(item, dict):
            continue
        prompt_text = str(item.get("prompt_text", "") or "").strip()
        prompt_wav_path = str(item.get("prompt_wav_path", "") or item.get("wav_path", "") or "").strip()
        if not prompt_text or not prompt_wav_path:
            continue

        wav_path = Path(prompt_wav_path)
        if not wav_path.is_absolute():
            wav_path = profiles_path.parent / wav_path
        if not wav_path.exists():
            print(f"[cosyvoice-server] profile wav missing for {voice}: {wav_path}", flush=True)
            continue

        try:
            MODEL.add_zero_shot_spk(prompt_text, str(wav_path), str(voice))
            loaded.add(str(voice))
        except Exception as exc:
            print(f"[cosyvoice-server] failed to load profile {voice}: {exc}", flush=True)
    return loaded


class CosyVoiceHandler(BaseHTTPRequestHandler):
    server_version = "CosyVoiceLocalHTTP/1.0"

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or 0)
        return self.rfile.read(length) if length > 0 else b""

    def _json_payload(self) -> dict:
        body = self._read_body()
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def _form_payload(self) -> dict[str, str]:
        body = self._read_body().decode("utf-8")
        parsed = parse_qs(body, keep_blank_values=True)
        return {key: (values[0] if values else "") for key, values in parsed.items()}

    def _send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_audio(self, data: bytes) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "model_dir": MODEL_DIR,
                    "model_type": MODEL_TYPE,
                    "profiles_path": PROFILES_PATH,
                    "native_speakers": sorted(NATIVE_SPEAKERS),
                    "native_speaker_count": len(NATIVE_SPEAKERS),
                    "profile_speakers": sorted(PROFILE_SPEAKERS),
                    "profile_speaker_count": len(PROFILE_SPEAKERS),
                    "speakers": sorted(NATIVE_SPEAKERS | PROFILE_SPEAKERS),
                    "speaker_count": len(NATIVE_SPEAKERS | PROFILE_SPEAKERS),
                },
            )
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/inference_sft":
                if "application/json" in str(self.headers.get("Content-Type", "")):
                    payload = self._json_payload()
                    text = str(payload.get("tts_text", "") or payload.get("text", "") or "").strip()
                    voice = str(payload.get("spk_id", "") or payload.get("voice", "") or "").strip()
                    speed = _normalize_speed(payload.get("speed", 1.0))
                else:
                    payload = self._form_payload()
                    text = str(payload.get("tts_text", "") or payload.get("text", "") or "").strip()
                    voice = str(payload.get("spk_id", "") or payload.get("voice", "") or "").strip()
                    speed = _normalize_speed(payload.get("speed", 1.0))

                if not text:
                    raise RuntimeError("tts_text 不能为空")
                if not voice:
                    raise RuntimeError("spk_id 不能为空")

                self._send_audio(_synthesize_sft_wav_bytes(text=text, voice=voice, speed=speed))
                return

            if path == "/inference_zero_shot_spk":
                if "application/json" in str(self.headers.get("Content-Type", "")):
                    payload = self._json_payload()
                    text = str(payload.get("tts_text", "") or payload.get("text", "") or "").strip()
                    voice = str(payload.get("spk_id", "") or payload.get("voice", "") or "").strip()
                    speed = _normalize_speed(payload.get("speed", 1.0))
                else:
                    payload = self._form_payload()
                    text = str(payload.get("tts_text", "") or payload.get("text", "") or "").strip()
                    voice = str(payload.get("spk_id", "") or payload.get("voice", "") or "").strip()
                    speed = _normalize_speed(payload.get("speed", 1.0))

                if not text:
                    raise RuntimeError("tts_text 不能为空")
                if not voice:
                    raise RuntimeError("spk_id 不能为空")

                self._send_audio(_synthesize_zero_shot_spk_wav_bytes(text=text, voice=voice, speed=speed))
                return
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def log_message(self, format: str, *args) -> None:
        print(f"[cosyvoice-server] {self.address_string()} - {format % args}", flush=True)


def main() -> int:
    global MODEL, MODEL_DIR, MODEL_TYPE, PROFILES_PATH, NATIVE_SPEAKERS, PROFILE_SPEAKERS

    args = _parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    model_dir = Path(args.model_dir).resolve()
    cache_dir = Path(args.cache_dir).resolve() if args.cache_dir else None
    profiles_path = Path(args.profiles_path).resolve() if args.profiles_path else None

    if not repo_dir.exists():
        raise RuntimeError(f"CosyVoice repo dir not found: {repo_dir}")
    if not model_dir.exists():
        raise RuntimeError(f"CosyVoice model dir not found: {model_dir}")

    _configure_cache(cache_dir)
    MODEL = _load_model(repo_dir, model_dir)
    MODEL_DIR = str(model_dir)
    MODEL_TYPE = _detect_model_type(model_dir)
    PROFILES_PATH = str(profiles_path) if profiles_path is not None else ""
    NATIVE_SPEAKERS = _load_native_speakers()
    PROFILE_SPEAKERS = _load_profiles(profiles_path) if profiles_path is not None else set()

    print("[cosyvoice-server] model loaded", flush=True)
    print(f"[cosyvoice-server] model_type={MODEL_TYPE}", flush=True)
    print(f"[cosyvoice-server] native_speakers={len(NATIVE_SPEAKERS)}", flush=True)
    print(f"[cosyvoice-server] profile_speakers={len(PROFILE_SPEAKERS)}", flush=True)
    print(f"[cosyvoice-server] listening http://{args.host}:{args.port}", flush=True)

    server = ThreadingHTTPServer((args.host, args.port), CosyVoiceHandler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
