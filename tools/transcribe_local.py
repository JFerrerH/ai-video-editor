"""Local, offline transcription: mlx-whisper on Apple Silicon, faster-whisper (CPU) elsewhere.

Drop-in replacement for video-use's helpers/transcribe.py: writes the same
Scribe-shaped JSON ({"words": [{type, text, start, end, speaker_id}]}) to
<edit_dir>/transcripts/<stem>.json, so pack_transcripts.py and render.py
work unchanged. No API key, nothing leaves the machine.

Differences from ElevenLabs Scribe:
  - no speaker diarization (every word is speaker_0)
  - no audio-event tags like (laughs)
  - fillers are coaxed in with a verbatim-style prompt, but Whisper may still
    drop some "um"/"uh"s

Backends (chosen at runtime; `--backend` forces one):
  - mlx            Apple Silicon macOS: mlx-whisper on Metal, default install
  - faster-whisper anywhere else (Linux, Docker): CTranslate2 on CPU, int8; `uv sync --group asr`
Both use Whisper large-v3-turbo (MIT) and write the same JSON; `source.engine` names the one used.

Usage:
    uv run tools/transcribe_local.py <video> [<video> ...]
    uv run tools/transcribe_local.py <video> --edit-dir /custom/edit --language en
    uv run tools/transcribe_local.py <video> --model mlx-community/whisper-large-v3-mlx
    uv run tools/transcribe_local.py <video> --backend faster-whisper --language es
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
# backend → (default model, module, install hint)
BACKENDS = {
    "mlx": (DEFAULT_MODEL, "mlx_whisper", "uv sync (Apple Silicon macOS only)"),
    "faster-whisper": ("mobiuslabsgmbh/faster-whisper-large-v3-turbo", "faster_whisper", "uv sync --group asr (Linux)"),
}
ENGINE = {"mlx": "mlx-whisper", "faster-whisper": "faster-whisper"}

# Whisper mirrors the style of its prompt; a disfluent prompt keeps fillers in.
# The prompt must be in the spoken language: an English prompt on Spanish audio
# makes the turbo model translate to English.
VERBATIM_PROMPTS = {
    "en": "Umm, so, uh, I was- I was thinking, like, hmm... okay. Yeah.",
    "es": "Eh, bueno, este... o sea, yo- yo pensaba, como que, mmm... ok. Sí.",
}


def _apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def pick_backend(requested: str | None) -> str:
    """`mlx` on Apple Silicon macOS, `faster-whisper` everywhere else; `requested` overrides."""
    if requested in (None, "auto"):
        return "mlx" if _apple_silicon() else "faster-whisper"
    if requested not in BACKENDS:
        sys.exit(f"unknown backend {requested!r}; use auto, {', '.join(BACKENDS)}")
    return requested


def backend_missing(backend: str) -> str | None:
    """None if `backend` can run here, else what to do about it."""
    if backend == "mlx" and not _apple_silicon():
        return "mlx needs Apple Silicon macOS"
    if importlib.util.find_spec(BACKENDS[backend][1]) is None:
        return f"not installed; run: {BACKENDS[backend][2]}"
    return None


def require_backend(backend: str) -> None:
    """Exit (no traceback) with the install command, or the backend that would work instead."""
    if err := backend_missing(backend):
        others = [b for b in BACKENDS if b != backend and backend_missing(b) is None]
        alt = f"; available here: --backend {others[0]}" if others else ""
        sys.exit(f"transcription backend {backend!r}: {err}{alt}")


def model_for(backend: str, model: str | None) -> str:
    """The backend's turbo model when none is given (callers pass DEFAULT_MODEL meaning 'the default')."""
    return BACKENDS[backend][0] if model in (None, DEFAULT_MODEL) else model


def extract_audio(video: Path, dest: Path, audio_track: int) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-map", f"0:a:{audio_track}",
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dest)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def faster_whisper_result(segments, info) -> dict:
    """faster-whisper's segment objects → the mlx-whisper result dict `to_scribe_words` reads."""
    segs = [{"text": s.text, "words": [{"word": w.word, "start": w.start, "end": w.end,
                                        "probability": w.probability} for w in (s.words or [])]}
            for s in segments]
    return {"language": info.language, "text": "".join(s["text"] for s in segs), "segments": segs}


def _run_faster_whisper(wav: Path, model: str, language: str | None) -> dict:
    import wave

    import numpy as np
    from faster_whisper import WhisperModel

    # pass samples, not the path: faster-whisper's own PyAV decode breaks on newer PyAV releases,
    # and extract_audio already made 16 kHz mono PCM
    with wave.open(str(wav), "rb") as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segments, info = m.transcribe(
        audio,
        language=language,
        task="transcribe",
        word_timestamps=True,
        initial_prompt=VERBATIM_PROMPTS.get(language or "en"),
        condition_on_previous_text=False,
        vad_filter=False,
    )
    return faster_whisper_result(segments, info)  # segments is lazy: decoding happens here


def to_scribe_words(result: dict) -> list[dict]:
    """Flatten whisper segments (mlx-whisper's dict shape) into Scribe's word/spacing list."""
    words: list[dict] = []
    prev_end: float | None = None
    for seg in result.get("segments", []):
        for w in seg.get("words", []):
            text = (w.get("word") or "").strip()
            if not text:
                continue
            start, end = float(w["start"]), float(w["end"])
            if prev_end is not None and start > prev_end:
                words.append({"type": "spacing", "text": " ", "start": prev_end,
                              "end": start, "speaker_id": "speaker_0"})
            words.append({"type": "word", "text": text, "start": start, "end": end,
                          "speaker_id": "speaker_0",
                          "logprob": w.get("probability")})
            prev_end = end
    return words


def transcribe_one(video: Path, edit_dir: Path, model: str | None, language: str | None,
                   audio_track: int, backend: str | None = None) -> Path:
    out_dir = edit_dir / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if audio_track == 0 else f".track{audio_track}"
    out_path = out_dir / f"{video.stem}{suffix}.json"
    if out_path.exists():
        print(f"cached: {out_path.name}")
        return out_path

    backend = pick_backend(backend)
    require_backend(backend)
    model = model_for(backend, model)
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        print(f"  extracting audio from {video.name}", flush=True)
        extract_audio(video, wav, audio_track)
        print(f"  transcribing with {model} ({ENGINE[backend]})", flush=True)
        if backend == "mlx":
            import mlx_whisper

            result = mlx_whisper.transcribe(
                str(wav),
                path_or_hf_repo=model,
                word_timestamps=True,
                language=language,
                initial_prompt=VERBATIM_PROMPTS.get(language or "en"),
                condition_on_previous_text=False,
            )
        else:
            result = _run_faster_whisper(wav, model, language)

    words = to_scribe_words(result)
    payload = {
        "language_code": result.get("language"),
        "text": result.get("text", "").strip(),
        "words": words,
        "source": {"engine": ENGINE[backend], "model": model, "file": str(video)},
    }
    out_path.write_text(json.dumps(payload, indent=2))
    n = sum(1 for w in words if w["type"] == "word")
    print(f"  saved: {out_path} ({n} words) in {time.time() - t0:.1f}s")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Offline word-level transcription (mlx-whisper / faster-whisper)")
    ap.add_argument("videos", type=Path, nargs="+")
    ap.add_argument("--edit-dir", type=Path, default=None,
                    help="Edit output dir (default: <video_parent>/edit)")
    ap.add_argument("--language", default=None, help="ISO code, e.g. 'en'. Omit to auto-detect.")
    ap.add_argument("--model", default=None, help="model id (default: large-v3-turbo for the backend)")
    ap.add_argument("--audio-track", type=int, default=0)
    ap.add_argument("--backend", choices=["auto", *BACKENDS], default="auto",
                    help="auto: mlx on Apple Silicon macOS, faster-whisper elsewhere")
    args = ap.parse_args()

    for video in args.videos:
        video = video.resolve()
        if not video.exists():
            sys.exit(f"not found: {video}")
        edit_dir = (args.edit_dir or video.parent / "edit").resolve()
        transcribe_one(video, edit_dir, args.model, args.language, args.audio_track, args.backend)


if __name__ == "__main__":
    main()
