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

Completeness (Whisper can skip whole stretches of speech without a word):
  - no --language: the language is detected from 30 s of speech first, then transcribed with that
    language's prompt; the JSON records `language_detected`
  - speech (the RMS envelope, tools/audio_env.py) that no word covers for 1.5 s or more is transcribed
    again on its own, with no prompt, and merged: `source.patched` lists each patch {from, to, words}
  - speech still without words is listed in `untranscribed` ([[from, to], …]) and printed as a warning

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
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audio_env import envelope, speech_runs  # noqa: E402

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


PLAIN_PROMPTS = {
    "en": "Hello. This is a short, clear recording, with full sentences.",
    "es": "Hola. Esta es una grabación corta y clara, con oraciones completas.",
}
# Measured per backend × language (tools/transcribe_prompts.md): the verbatim prompt made both backends skip
# ~21 s of a real Spanish take; English scores the same with every candidate.
PROMPTS = {
    ("mlx", "en"): VERBATIM_PROMPTS["en"],
    ("mlx", "es"): PLAIN_PROMPTS["es"],
    ("faster-whisper", "en"): VERBATIM_PROMPTS["en"],
    ("faster-whisper", "es"): None,
}


def prompt_for(backend: str, language: str | None) -> str | None:
    """The measured prompt for this backend and language (PROMPTS, tools/transcribe_prompts.md); none for a
    language without one (never another language's: an English prompt on Spanish audio makes it translate)."""
    return PROMPTS.get((backend, language or ""))


SR = 16000
DETECT_S = 30.0  # seconds of speech the language is detected from
# a word "covers" its first COVER_CAP s (± COVER_PAD); uncovered speech of MIN_HOLE s or more is re-transcribed
COVER_CAP, COVER_PAD, MIN_HOLE, PATCH_PAD = 1.5, 0.3, 1.5, 0.5
# what Whisper says over silence or noise; a patch made of these (or of low-confidence words) is dropped
HALLUCINATIONS = ("subtítulos", "subtitulos", "amara.org", "thanks for watching", "thank you for watching",
                  "gracias por ver", "suscríbete", "subscribe", "please like", "music", "música", "thank you")


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


def load_wav(wav: Path):
    """16 kHz mono PCM → float32 samples (passed to both backends: faster-whisper's own PyAV decode
    breaks on newer PyAV releases, and extract_audio already made the PCM)."""
    import numpy as np
    with wave.open(str(wav), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0


class Engine:
    """One loaded model per run: language detection, the main pass and every hole re-transcription."""

    def __init__(self, backend: str, model: str):
        self.backend, self.model = backend, model
        self._fw = None

    def _faster(self):
        if self._fw is None:
            from faster_whisper import WhisperModel
            self._fw = WhisperModel(self.model, device="cpu", compute_type="int8")
        return self._fw

    def transcribe(self, audio, language: str | None, prompt: str | None) -> dict:
        """mlx-whisper's result shape ({language, text, segments[words]}) from either backend."""
        if self.backend == "mlx":
            import mlx_whisper
            return mlx_whisper.transcribe(audio, path_or_hf_repo=self.model, word_timestamps=True,
                                          language=language, initial_prompt=prompt, condition_on_previous_text=False)
        segments, info = self._faster().transcribe(audio, language=language, task="transcribe", word_timestamps=True,
                                                   initial_prompt=prompt, condition_on_previous_text=False,
                                                   vad_filter=False)
        return faster_whisper_result(segments, info)  # segments is lazy: decoding happens here

    def detect(self, audio) -> str | None:
        """Spoken language of `audio` (≤ 30 s), with no prompt to bias it."""
        if self.backend == "mlx":
            return self.transcribe(audio, None, None).get("language")
        m = self._faster()
        if hasattr(m, "detect_language"):
            return m.detect_language(audio)[0]
        return m.transcribe(audio, language=None, task="transcribe")[1].language


def plain_words(result: dict) -> list[dict]:
    """Whisper words (mlx-whisper's dict shape) as Scribe word entries, no spacing."""
    out = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []):
            text = (w.get("word") or "").strip()
            if text:
                out.append({"type": "word", "text": text, "start": float(w["start"]), "end": float(w["end"]),
                            "speaker_id": "speaker_0", "logprob": w.get("probability")})
    return out


def with_spacing(words: list[dict]) -> list[dict]:
    """Scribe's word/spacing list: a spacing entry in every gap between consecutive words."""
    out: list[dict] = []
    prev_end: float | None = None
    for w in words:
        if prev_end is not None and w["start"] > prev_end:
            out.append({"type": "spacing", "text": " ", "start": prev_end, "end": w["start"], "speaker_id": "speaker_0"})
        out.append(w)
        prev_end = w["end"]
    return out


def to_scribe_words(result: dict) -> list[dict]:
    """Flatten whisper segments (mlx-whisper's dict shape) into Scribe's word/spacing list."""
    return with_spacing(plain_words(result))


# ── completeness: speech that no word covers ──────────────────────────────
def uncovered(words: list[dict], runs: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Stretches of speech (`runs`) of at least MIN_HOLE s that no word covers. A word covers only its
    first COVER_CAP s (± COVER_PAD): Whisper can stretch one word over a long run it never transcribed."""
    cov = sorted((w["start"] - COVER_PAD, min(w["end"], w["start"] + COVER_CAP) + COVER_PAD)
                 for w in words if w["type"] == "word")
    out = []
    for a, b in runs:
        cur = a
        for c0, c1 in cov:
            if c1 <= cur:
                continue
            if c0 >= b:
                break
            if c0 > cur:
                out.append((cur, min(c0, b)))
            cur = max(cur, c1)
            if cur >= b:
                break
        if cur < b:
            out.append((cur, b))
    return [(round(a, 2), round(b, 2)) for a, b in out if b - a >= MIN_HOLE]


def _hallucination(words: list[dict]) -> bool:
    text = " ".join(w["text"] for w in words).lower()
    probs = [w["logprob"] for w in words if w.get("logprob") is not None]
    return (len(words) <= 12 and any(h in text for h in HALLUCINATIONS)) or bool(probs and sum(probs) / len(probs) < 0.3)


def fill_holes(words: list[dict], runs: list[tuple[float, float]], retranscribe, duration: float):
    """Re-transcribe every uncovered stretch of speech on its own and merge its words.
    `retranscribe(lo, hi)` → a Whisper result for the audio [lo, hi] with times from lo.
    Returns (words with spacing rebuilt, patched [{from, to, words}], untranscribed [[from, to]])."""
    plain = [w for w in words if w["type"] == "word"]
    patched = []
    for a, b in uncovered(plain, runs):
        lo, hi = max(0.0, a - PATCH_PAD), min(duration, b + PATCH_PAD)
        new = []
        for w in plain_words(retranscribe(lo, hi)):
            w = {**w, "start": round(w["start"] + lo, 3), "end": round(w["end"] + lo, 3)}
            mid = (w["start"] + w["end"]) / 2
            if lo <= w["start"] <= hi and not any(x["start"] <= mid <= x["end"] for x in plain):
                new.append(w)
        if new and not _hallucination(new):
            plain += new
            patched.append({"from": a, "to": b, "words": len(new)})
    plain.sort(key=lambda w: (w["start"], w["end"]))
    for prev, w in zip(plain, plain[1:]):  # keep times non-decreasing where a patch meets a word
        if prev["end"] > w["start"]:
            prev["end"] = max(prev["start"], w["start"])
    return with_spacing(plain), patched, [list(r) for r in uncovered(plain, runs)]


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
    engine = Engine(backend, model)
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        print(f"  extracting audio from {video.name}", flush=True)
        extract_audio(video, wav, audio_track)
        audio = load_wav(wav)
        db, floor = envelope(wav)
    runs = speech_runs(db, floor)
    duration = len(audio) / SR
    detected = None
    if language is None:
        a = runs[0][0] if runs else 0.0
        detected = language = engine.detect(audio[int(a * SR):int((a + DETECT_S) * SR)])
        print(f"  language detected: {detected}", flush=True)
    prompt = prompt_for(backend, language)
    print(f"  transcribing with {model} ({ENGINE[backend]}), {language}, {'a' if prompt else 'no'} prompt", flush=True)
    result = engine.transcribe(audio, language, prompt)

    def retranscribe(lo: float, hi: float) -> dict:
        print(f"  re-transcribing speech with no words at {lo:.1f}–{hi:.1f} s", flush=True)
        return engine.transcribe(audio[int(lo * SR):int(hi * SR)], language, None)

    words, patched, untranscribed = fill_holes(to_scribe_words(result), runs, retranscribe, duration)
    text = " ".join(w["text"] for w in words if w["type"] == "word")
    payload = {
        "language_code": result.get("language") or language,
        **({"language_detected": detected} if detected else {}),
        "text": text if patched else result.get("text", "").strip(),
        "words": words,
        "untranscribed": untranscribed,
        "source": {"engine": ENGINE[backend], "model": model, "file": str(video), "prompt": prompt, "patched": patched},
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    n = sum(1 for w in words if w["type"] == "word")
    for p in patched:
        print(f"  patched {p['from']:.1f}–{p['to']:.1f} s: {p['words']} words Whisper had skipped")
    for a, b in untranscribed:
        print(f"  WARN no words for the speech at {a:.1f}–{b:.1f} s in {video.name} (check it by ear or re-record)")
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
