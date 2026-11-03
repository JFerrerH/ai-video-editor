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
  - a word longer than its letters allow (max(1.0, 0.12 s × letters + 0.4)) over speech is transcribed again
    in its own window and the words that come back replace it: `source.patched` lists {from, to, words, replaced}
  - speech (the RMS envelope, tools/audio_env.py) that no word covers for 0.6 s or more is transcribed
    again on its own, with no prompt, and merged: `source.patched` lists each patch {from, to, words}
  - speech still without words is listed in `untranscribed` ([[from, to], …]) and printed as a warning
  - likely false starts ("phrase… phrase again") are listed in `restarts` [{abandoned: [from, to], again, words}]
    and shown inline in the packed transcript (an audio_event entry at the restart)

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
import re
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
# (0.6: a hidden 1.56 s run was split by a 0.6 s pause into two runs under the old 1.5 s)
COVER_CAP, COVER_PAD, MIN_HOLE, PATCH_PAD = 1.5, 0.3, 0.6, 0.5
# a stretch with no words this far under the take's speech is room noise or a breath, not speech nobody transcribed.
# Measured on 5 real takes: their sentences sit at -8.8 dB or above, such stretches at -16.5 dB or below.
NOT_SPEECH_DB = -12.0
# a word lasting longer than max(WORD_MIN, WORD_PER_LETTER × letters + WORD_BASE) s with speech through
# IMPLAUSIBLE_SPEECH of it hides speech Whisper folded into one stamp
WORD_MIN, WORD_PER_LETTER, WORD_BASE, IMPLAUSIBLE_SPEECH = 1.0, 0.12, 0.4, 0.6
# restart marker: an abandoned phrase (ellipsis, or a pause of RESTART_PAUSE s without . ? !) whose first two
# words start again right after it (at most RESTART_FILLER words later, within RESTART_WINDOW s)
RESTART_PAUSE, RESTART_WINDOW, RESTART_FILLER = 0.3, 6.0, 2
# what Whisper says over silence or noise; a patch made of these (plus one stray word at most, or of
# low-confidence words) is dropped
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


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def _hallucination(words: list[dict]) -> bool:
    """Only listed phrases (whole words) plus at most one stray word, or low confidence. A real sentence that
    happens to contain "thank you" or "music" is kept."""
    text = _norm(" ".join(w["text"] for w in words))
    rest = text
    for h in sorted(HALLUCINATIONS, key=len, reverse=True):
        rest = re.sub(rf"(?<!\w){re.escape(_norm(h))}(?!\w)", " ", rest)
    probs = [w["logprob"] for w in words if w.get("logprob") is not None]
    return (rest != text and len(rest.split()) <= 1) or bool(probs and sum(probs) / len(probs) < 0.3)


def _speech_share(a: float, b: float, runs: list[tuple[float, float]]) -> float:
    return sum(max(0.0, min(b, r1) - max(a, r0)) for r0, r1 in runs) / max(1e-6, b - a)


def implausible(w: dict, runs: list[tuple[float, float]]) -> bool:
    """A word longer than its letters allow, with speech through most of it: Whisper folded speech into it."""
    letters = sum(c.isalnum() for c in w["text"])
    dur = w["end"] - w["start"]
    return dur > max(WORD_MIN, WORD_PER_LETTER * letters + WORD_BASE) \
        and _speech_share(w["start"], w["end"], runs) >= IMPLAUSIBLE_SPEECH


def _shifted(result: dict, lo: float) -> list[dict]:
    return [{**w, "start": round(w["start"] + lo, 3), "end": round(w["end"] + lo, 3)} for w in plain_words(result)]


def _merge(ranges: list[list[float]]) -> list[list[float]]:
    out: list[list[float]] = []
    for a, b in sorted(ranges):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def fill_holes(words: list[dict], runs: list[tuple[float, float]], retranscribe, duration: float):
    """Re-transcribe every implausible word and every uncovered stretch of speech on its own and merge
    the words. An implausible word's words replace it; a hole's words are added.
    `retranscribe(lo, hi)` → a Whisper result for the audio [lo, hi] with times from lo.
    Returns (words with spacing rebuilt, patched [{from, to, words, replaced?}], untranscribed [[from, to]])."""
    plain = [w for w in words if w["type"] == "word"]
    patched, failed = [], []
    for bad in [w for w in plain if implausible(w, runs)]:
        a, b = bad["start"], bad["end"]
        lo, hi = max(0.0, a - PATCH_PAD), min(duration, b + PATCH_PAD)
        new = []
        for w in _shifted(retranscribe(lo, hi), lo):
            if a <= (w["start"] + w["end"]) / 2 <= b:  # the retry's padding repeats the neighbours: drop them
                new.append({**w, "start": max(a, w["start"]), "end": min(b, w["end"])})
        if new and not _hallucination(new):
            plain = [w for w in plain if w is not bad] + new
            patched.append({"from": a, "to": b, "words": len(new), "replaced": bad["text"]})
        else:
            failed.append(bad)
    for a, b in uncovered(plain, runs):
        lo, hi = max(0.0, a - PATCH_PAD), min(duration, b + PATCH_PAD)
        solid = [x for x in plain if not any(x is f for f in failed)]
        new = []
        for w in _shifted(retranscribe(lo, hi), lo):
            mid = (w["start"] + w["end"]) / 2  # an implausible word doesn't block its own repair
            if lo <= w["start"] <= hi and not any(x["start"] <= mid <= x["end"] for x in solid):
                new.append(w)
        if new and not _hallucination(new):
            plain += new
            patched.append({"from": a, "to": b, "words": len(new)})
    # an implausible word the hole pass filled is replaced too; one it didn't is speech with no words
    for bad in failed:
        if any(w is not bad and bad["start"] <= (w["start"] + w["end"]) / 2 <= bad["end"] for w in plain):
            plain = [w for w in plain if w is not bad]
    plain.sort(key=lambda w: (w["start"], w["end"]))
    for prev, w in zip(plain, plain[1:]):  # keep times non-decreasing where a patch meets a word
        if prev["end"] > w["start"]:
            prev["end"] = max(prev["start"], w["start"])
    left = [[round(f["start"], 2), round(f["end"], 2)] for f in failed if any(f is w for w in plain)]
    return with_spacing(plain), patched, _merge([list(r) for r in uncovered(plain, runs)] + left)


def audible(holes: list[list[float]], db, hop: float = 0.005) -> list[list[float]]:
    """The stretches loud enough to be speech, against the level of the take's own speech (`db` is its envelope):
    above the room's floor isn't enough, or every breath in a pause would count as speech with no words."""
    import numpy as np

    speech = float(np.percentile(db, 90))
    return [[a, b] for a, b in holes if len(window := db[int(a / hop):int(b / hop)])
            and float(np.percentile(window, 90)) - speech >= NOT_SPEECH_DB]


# ── false starts ──────────────────────────────────────────────────────────
def _ends_sentence(text: str) -> bool:
    return bool(re.search(r"[.?!]$", text.strip()))


def _trails_off(text: str) -> bool:
    return text.strip().endswith(("…", "..."))


def mark_restarts(words: list[dict]) -> list[dict]:
    """Likely false starts: a phrase that ends abandoned (an ellipsis, or a pause of RESTART_PAUSE s without
    . ? !) and whose first two words start again right after it. Words said in between mean the speaker went on:
    two sentences that open alike ("And in that…", "And in spite…") aren't a restart. Deliberate repetition ends a
    sentence first, so it isn't marked. [{"abandoned": [from, to], "again": t, "words": "<abandoned text>"}]"""
    ws = [w for w in words if w["type"] == "word"]
    by_again: dict[int, dict] = {}
    for i, w in enumerate(ws):
        nxt = ws[i + 1] if i + 1 < len(ws) else None
        if nxt is None or not (_trails_off(w["text"]) or
                               (nxt["start"] - w["end"] >= RESTART_PAUSE and not _ends_sentence(w["text"]))):
            continue
        s = i  # back to the previous sentence end or pause
        while s > 0 and not _ends_sentence(ws[s - 1]["text"]) and not _trails_off(ws[s - 1]["text"]) \
                and ws[s]["start"] - ws[s - 1]["end"] < RESTART_PAUSE:
            s -= 1
        if i - s < 1:
            continue  # a one-word phrase has no opening to repeat
        head = (_norm(ws[s]["text"]), _norm(ws[s + 1]["text"]))
        for j in range(i + 1, min(i + 2 + RESTART_FILLER, len(ws) - 1)):
            if ws[j]["start"] - w["end"] > RESTART_WINDOW:
                break
            if (_norm(ws[j]["text"]), _norm(ws[j + 1]["text"])) == head:
                prev = by_again.get(j)
                if prev is None or ws[s]["start"] < prev["abandoned"][0]:
                    by_again[j] = {"abandoned": [ws[s]["start"], w["end"]], "again": ws[j]["start"],
                                   "words": " ".join(x["text"] for x in ws[s:i + 1])}
                break
    return [by_again[j] for j in sorted(by_again)]


def with_restart_marks(words: list[dict], restarts: list[dict]) -> list[dict]:
    """The word list with an audio_event at each restart, so the packed transcript shows it inline
    (pack_transcripts.py prints audio events in the phrase text)."""
    marks = [{"type": "audio_event", "text": f"(restart: false start {r['abandoned'][0]:.2f}–{r['abandoned'][1]:.2f} "
                                             f"\"{r['words']}\")", "start": r["again"], "end": r["again"],
              "speaker_id": "speaker_0"} for r in restarts]
    return sorted(words + marks, key=lambda w: (w["start"], w["type"] != "audio_event"))


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
    untranscribed = audible(untranscribed, db)
    restarts = mark_restarts(words)
    text = " ".join(w["text"] for w in words if w["type"] == "word")
    payload = {
        "language_code": result.get("language") or language,
        **({"language_detected": detected} if detected else {}),
        "text": text if patched else result.get("text", "").strip(),
        "words": with_restart_marks(words, restarts),
        "untranscribed": untranscribed,
        "restarts": restarts,
        "source": {"engine": ENGINE[backend], "model": model, "file": str(video), "prompt": prompt, "patched": patched},
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    n = sum(1 for w in words if w["type"] == "word")
    for p in patched:
        what = f"in place of \"{p['replaced']}\"" if "replaced" in p else "Whisper had skipped"
        print(f"  patched {p['from']:.1f}–{p['to']:.1f} s: {p['words']} words {what}")
    for r in restarts:
        print(f"  restart at {r['again']:.2f} s: false start {r['abandoned'][0]:.2f}–{r['abandoned'][1]:.2f} \"{r['words']}\"")
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
