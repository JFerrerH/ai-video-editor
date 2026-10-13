"""Local, offline transcription on Apple Silicon (mlx-whisper).

Drop-in replacement for video-use's helpers/transcribe.py: writes the same
Scribe-shaped JSON ({"words": [{type, text, start, end, speaker_id}]}) to
<edit_dir>/transcripts/<stem>.json, so pack_transcripts.py and render.py
work unchanged. No API key, nothing leaves the machine.

Differences from ElevenLabs Scribe:
  - no speaker diarization (every word is speaker_0)
  - no audio-event tags like (laughs)
  - fillers are coaxed in with a verbatim-style prompt, but Whisper may still
    drop some "um"/"uh"s

Usage:
    uv run tools/transcribe_local.py <video> [<video> ...]
    uv run tools/transcribe_local.py <video> --edit-dir /custom/edit --language en
    uv run tools/transcribe_local.py <video> --model mlx-community/whisper-large-v3-mlx
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"

# Whisper mirrors the style of its prompt; a disfluent prompt keeps fillers in.
# The prompt must be in the spoken language: an English prompt on Spanish audio
# makes the turbo model translate to English.
VERBATIM_PROMPTS = {
    "en": "Umm, so, uh, I was- I was thinking, like, hmm... okay. Yeah.",
    "es": "Eh, bueno, este... o sea, yo- yo pensaba, como que, mmm... ok. Sí.",
}


def extract_audio(video: Path, dest: Path, audio_track: int) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-map", f"0:a:{audio_track}",
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dest)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def to_scribe_words(result: dict) -> list[dict]:
    """Flatten mlx-whisper segments into Scribe's word/spacing list."""
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


def transcribe_one(video: Path, edit_dir: Path, model: str, language: str | None,
                   audio_track: int) -> Path:
    import mlx_whisper

    out_dir = edit_dir / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if audio_track == 0 else f".track{audio_track}"
    out_path = out_dir / f"{video.stem}{suffix}.json"
    if out_path.exists():
        print(f"cached: {out_path.name}")
        return out_path

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        print(f"  extracting audio from {video.name}", flush=True)
        extract_audio(video, wav, audio_track)
        print(f"  transcribing with {model}", flush=True)
        result = mlx_whisper.transcribe(
            str(wav),
            path_or_hf_repo=model,
            word_timestamps=True,
            language=language,
            initial_prompt=VERBATIM_PROMPTS.get(language or "en"),
            condition_on_previous_text=False,
        )

    words = to_scribe_words(result)
    payload = {
        "language_code": result.get("language"),
        "text": result.get("text", "").strip(),
        "words": words,
        "source": {"engine": "mlx-whisper", "model": model, "file": str(video)},
    }
    out_path.write_text(json.dumps(payload, indent=2))
    n = sum(1 for w in words if w["type"] == "word")
    print(f"  saved: {out_path} ({n} words) in {time.time() - t0:.1f}s")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Offline word-level transcription (mlx-whisper)")
    ap.add_argument("videos", type=Path, nargs="+")
    ap.add_argument("--edit-dir", type=Path, default=None,
                    help="Edit output dir (default: <video_parent>/edit)")
    ap.add_argument("--language", default=None, help="ISO code, e.g. 'en'. Omit to auto-detect.")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--audio-track", type=int, default=0)
    args = ap.parse_args()

    for video in args.videos:
        video = video.resolve()
        if not video.exists():
            sys.exit(f"not found: {video}")
        edit_dir = (args.edit_dir or video.parent / "edit").resolve()
        transcribe_one(video, edit_dir, args.model, args.language, args.audio_track)


if __name__ == "__main__":
    main()
