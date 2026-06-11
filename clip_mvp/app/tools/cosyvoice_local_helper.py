from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-dir", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--cache-dir", default="")
    parser.add_argument("--voice", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--speed", type=float, default=1.0)
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


def _load_segments(manifest_path: Path) -> list[dict]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RuntimeError("segments manifest must be a list")
    return data


def _load_model(repo_dir: Path, model_dir: Path):
    _configure_paths(repo_dir)
    print(f"[cosyvoice] importing repo from {repo_dir}", flush=True)
    from cosyvoice.cli.cosyvoice import AutoModel

    print(f"[cosyvoice] loading model from {model_dir}", flush=True)
    return AutoModel(model_dir=str(model_dir))


def _normalize_speed(value: float) -> float:
    try:
        speed = float(value)
    except Exception:
        speed = 1.0
    return max(0.5, min(2.0, speed))


def _save_segment(model, *, text: str, voice: str, output_path: Path, speed: float = 1.0) -> None:
    import torch
    import torchaudio

    print(f"[cosyvoice] synthesizing {output_path.name} chars={len(text)} voice={voice} speed={speed:.2f}", flush=True)
    chunks = []
    for result in model.inference_sft(text, voice, stream=False, speed=speed):
        speech = result.get("tts_speech")
        if speech is None or speech.numel() <= 0:
            continue
        chunks.append(speech.detach().cpu())

    if not chunks:
        raise RuntimeError(f"CosyVoice 没有生成有效音频: {output_path.name}")

    merged = chunks[0] if len(chunks) == 1 else torch.cat(chunks, dim=1)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(output_path), merged, model.sample_rate)
    print(f"[cosyvoice] wrote {output_path}", flush=True)


def main() -> int:
    args = _parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    model_dir = Path(args.model_dir).resolve()
    cache_dir = Path(args.cache_dir).resolve() if args.cache_dir else None
    manifest_path = Path(args.manifest).resolve()

    if not repo_dir.exists():
        raise RuntimeError(f"CosyVoice repo dir not found: {repo_dir}")
    if not model_dir.exists():
        raise RuntimeError(f"CosyVoice model dir not found: {model_dir}")
    if not manifest_path.exists():
        raise RuntimeError(f"segments manifest not found: {manifest_path}")

    _configure_cache(cache_dir)
    model = _load_model(repo_dir, model_dir)
    print("[cosyvoice] model loaded", flush=True)
    speakers = set(model.list_available_spks())
    print(f"[cosyvoice] speakers={len(speakers)}", flush=True)
    if args.voice not in speakers:
        raise RuntimeError(f"音色不存在: {args.voice}; 可用音色: {', '.join(sorted(speakers))}")

    segments = _load_segments(manifest_path)
    speed = _normalize_speed(args.speed)
    for item in segments:
        text = str(item.get("text", "")).strip()
        output_value = str(item.get("audio_path", "")).strip()
        output_path = Path(output_value) if output_value else None
        if not text:
            raise RuntimeError("segment text is empty")
        if output_path is None:
            raise RuntimeError("segment audio_path is empty")
        _save_segment(
            model,
            text=text,
            voice=args.voice,
            output_path=output_path,
            speed=speed,
        )

    print(f"LOCAL_COSYVOICE_OK segments={len(segments)} voice={args.voice}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
