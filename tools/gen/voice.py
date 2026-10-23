"""Local text-to-speech: script line → mono 24 kHz WAV + sidecar JSON, fully offline once cached.

    uv sync --group gen                                    # once: installs mlx-audio + misaki
    uv run tools/gen/voice.py "One clear idea." -o out.wav --lang en
    uv run tools/gen/voice.py "Una idea clara." -o out.wav --lang es --preset em_alex --speed 1.1
    uv run tools/gen/voice.py --list                       # languages and their voice presets

Model: Kokoro-82M, weights `mlx-community/Kokoro-82M-bf16` (MLX conversion of `hexgrad/Kokoro-82M`),
licence Apache-2.0, run through `mlx-audio` (MIT). Text → phonemes with `misaki` (Apache-2.0); for
non-English languages (and English words misaki doesn't know) misaki calls the `espeak-ng` library
(GPL-3.0) bundled in the `espeakng-loader` wheel. It's loaded on this machine and not redistributed;
it doesn't change the licence of the audio we produce. English also uses the spaCy model
`en_core_web_sm` (MIT), pinned in the `gen` group. First run downloads ~0.36 GB of weights + voices.

Each clip gets `<clip>.json` next to it: the cache key (text sent, lang, preset, speed, model) plus
duration and seconds taken. A request whose key matches is skipped; `--force` re-synthesises.

Module top level is standard library only, so `tools/storyboard.py check` can validate languages and
presets and read sidecars on a default install; `mlx-audio` is imported inside `synthesize_many`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import wave
from dataclasses import dataclass
from pathlib import Path

MODEL_ID = "mlx-community/Kokoro-82M-bf16"
MODEL_LICENCE = "Apache-2.0"
SAMPLE_RATE = 24000
INSTALL_HINT = "uv sync --group gen"

# storyboard `lang` → (Kokoro language code, language name, default preset)
# en and es defaults picked by ear from sample clips (2026-10-22); the others are Kokoro's best-rated voice
LANGS: dict[str, tuple[str, str, str]] = {
    "en": ("a", "English (US)", "af_heart"),
    "en-us": ("a", "English (US)", "af_heart"),
    "en-gb": ("b", "English (UK)", "bf_emma"),
    "es": ("e", "Spanish (Latin America)", "em_alex"),
    "es-419": ("e", "Spanish (Latin America)", "em_alex"),
    "es-es": ("e", "Spanish (Spain)", "em_alex"),
    "fr": ("f", "French", "ff_siwis"),
    "it": ("i", "Italian", "if_sara"),
    "pt": ("p", "Portuguese (BR)", "pf_dora"),
    "pt-br": ("p", "Portuguese (BR)", "pf_dora"),
    "hi": ("h", "Hindi", "hf_alpha"),
}
# espeak-ng dialect for the phonemiser, where Kokoro's default isn't the one wanted. Kokoro's `e`
# uses espeak `es` (Spain: "doce" → ˈdoθe, "cierran" → θjˈeran); most Spanish-speaking audiences
# expect seseo, so plain `es` means Latin American Spanish and `es-es` opts into Spain.
ESPEAK = {"es": "es-419", "es-419": "es-419", "es-es": "es"}
# Kokoro's Japanese and Mandarin need misaki[ja]/[zh] (pyopenjtalk, unidic, jieba…), which the
# `gen` group doesn't install; add them there before listing `ja`/`zh` here.

# Every Kokoro v1.0 preset; the first letter is its language code, the second its gender.
PRESETS = (
    "af_alloy af_aoede af_bella af_heart af_jessica af_kore af_nicole af_nova af_river af_sarah af_sky "
    "am_adam am_echo am_eric am_fenrir am_liam am_michael am_onyx am_puck am_santa "
    "bf_alice bf_emma bf_isabella bf_lily bm_daniel bm_fable bm_george bm_lewis "
    "ef_dora em_alex em_santa ff_siwis hf_alpha hf_beta hm_omega hm_psi if_sara im_nicola "
    "pf_dora pm_alex pm_santa"
).split()

TRIM_DB = -50.0  # silence threshold for the edge trim (dBFS, RMS over 10 ms windows)
TRIM_KEEP_S = 0.04  # silence kept at each end; + one window of slack stays under 50 ms
# Kokoro reads a whole line in one breath: it drops the pause after ".", "…", ":" and turns a
# sentence break into a comma. So a line is synthesised one sentence/clause at a time and joined
# with these silences (s) after the mark that ends each piece. Commas stay inside a piece.
PAUSE_S = {".": 0.18, "!": 0.18, "?": 0.2, "…": 0.25, ":": 0.12, ";": 0.12}  # short: longer reads as hesitant
PROSODY = 3  # bump when the chunking/pauses change, so cached clips are re-synthesised


def presets_for(lang: str) -> list[str]:
    code = LANGS[lang][0]
    return [p for p in PRESETS if p[0] == code]


def validate(lang: str, preset: str | None) -> str | None:
    """None if `lang` + `preset` can be synthesised, else a message naming the valid choices."""
    if lang not in LANGS:
        return f"language {lang!r} isn't supported; use one of: {', '.join(LANGS)}"
    if preset is not None and preset not in presets_for(lang):
        return f"voice {preset!r} isn't a {LANGS[lang][1]} preset; use one of: {', '.join(presets_for(lang))}"
    return None


def default_preset(lang: str) -> str:
    return LANGS[lang][2]


def clean(narration: str) -> str:
    """Script text without the authoring marks (`*emphasis*`, `|` phrase breaks)."""
    return re.sub(r"\s+", " ", narration.replace("*", "").replace("|", " ")).strip()


def spoken(narration: str, pronounce: dict[str, str] | None = None) -> str:
    """The text sent to TTS: `clean()` + the `pronounce` map applied word by word, matching the
    word without surrounding punctuation, case-sensitively first, then case-insensitively."""
    if not pronounce:
        return clean(narration)
    lower = {k.lower(): v for k, v in pronounce.items()}
    out = []
    for tok in clean(narration).split(" "):
        m = re.match(r"^(\W*)(.*?)(\W*)$", tok)
        pre, core, post = m.groups() if m else ("", tok, "")
        rep = pronounce.get(core, lower.get(core.lower()))
        out.append(pre + rep + post if rep is not None else tok)
    return " ".join(out)


@dataclass
class Job:
    out: Path
    text: str  # what is sent to TTS (already through `spoken()`)
    lang: str
    preset: str | None = None
    speed: float = 1.0

    @property
    def voice(self) -> str:
        return self.preset or default_preset(self.lang)

    def key(self) -> dict:
        return {"text": self.text, "lang": self.lang, "preset": self.voice,
                "speed": round(float(self.speed), 3), "model": MODEL_ID, "prosody": PROSODY,
                "phonemes": ESPEAK.get(self.lang)}


def sidecar_path(wav: Path) -> Path:
    return wav.with_suffix(".json")


def read_sidecar(wav: Path) -> dict | None:
    try:
        return json.loads(sidecar_path(wav).read_text())
    except (OSError, ValueError):
        return None


def is_fresh(job: Job) -> bool:
    """The clip exists and its sidecar's cache key matches the job."""
    side = read_sidecar(job.out)
    return job.out.exists() and side is not None and all(side.get(k) == v for k, v in job.key().items())


def _phonemiser_missing() -> bool:
    """misaki's espeak path loads the libespeak-ng bundled in the `espeakng-loader` wheel."""
    try:
        import espeakng_loader
    except ImportError:
        return True
    return not Path(espeakng_loader.get_library_path()).exists()


def _trim(audio, sr: int):
    import numpy as np

    win = sr // 100
    n = len(audio) // win
    if n == 0:
        return audio
    rms = np.sqrt(np.mean(audio[: n * win].reshape(n, win).astype(np.float64) ** 2, axis=1) + 1e-12)
    loud = np.nonzero(20 * np.log10(rms) > TRIM_DB)[0]
    if not len(loud):
        return audio
    keep = round(TRIM_KEEP_S * sr)
    return audio[max(0, loud[0] * win - keep): min(len(audio), (loud[-1] + 1) * win + keep)]


def pieces(text: str) -> list[tuple[str, float]]:
    """The line cut after each sentence/clause mark: [(text for TTS, pause after it in s)].
    "…" is sent as "." (the phonemiser has no ellipsis); the last piece gets no pause."""
    parts = [p for p in re.split(r"(?<=[.!?…:;])\s+", text.strip()) if p]
    # a one-word piece ("Ojo:") said alone comes out garbled: keep it with the next, as a comma
    k = 0
    while k < len(parts) - 1:
        if len(parts[k].split()) < 2:
            parts[k : k + 2] = [parts[k][:-1] + ", " + parts[k + 1]]
        else:
            k += 1
    out = []
    for k, p in enumerate(parts):
        mark = p.rstrip("»\"')")[-1:] if p else ""
        out.append((p.replace("…", "."), 0.0 if k == len(parts) - 1 else PAUSE_S.get(mark, 0.0)))
    return out


def _write_wav(path: Path, audio, sr: int) -> None:
    import numpy as np

    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def _load_model():
    import contextlib
    import io
    import os

    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    from huggingface_hub import snapshot_download
    from mlx_audio.tts.utils import load_model

    files = ["config.json", "kokoro-v1_0.safetensors"]  # voices download one by one, on first use
    try:  # no network call when the weights are already cached
        path = snapshot_download(MODEL_ID, allow_patterns=files, local_files_only=True)
    except Exception:
        print(f"  downloading {MODEL_ID} (~330 MB, once)…", flush=True)
        path = snapshot_download(MODEL_ID, allow_patterns=files)
    with contextlib.redirect_stdout(io.StringIO()):
        model = load_model(Path(path))
    model.repo_id = MODEL_ID  # voice presets come from the same repo as the weights
    return model


def _use_dialect(model, lang: str) -> None:
    """Point the language's espeak phonemiser at its dialect (ESPEAK). mlx-audio caches one
    pipeline per Kokoro language code and builds its EspeakG2P from a fixed table, so the cached
    pipeline's g2p is replaced (private API: `_get_pipeline`, checked by `voice --list` users)."""
    variant = ESPEAK.get(lang)
    if not variant:
        return
    import contextlib
    import io

    from misaki import espeak

    with contextlib.redirect_stdout(io.StringIO()):
        pipe = model._get_pipeline(LANGS[lang][0])
    if getattr(pipe.g2p, "_dialect", None) != variant:
        pipe.g2p = espeak.EspeakG2P(language=variant)
        pipe.g2p._dialect = variant


def synthesize_many(jobs: list[Job], force: bool = False) -> list[dict]:
    """Synthesise every job whose clip is missing or stale, loading the model once.
    Returns one dict per job: {out, cached, duration, seconds}. Validates everything first and
    exits (writing nothing) on a bad language/preset or a missing install."""
    for j in jobs:
        if err := validate(j.lang, j.preset):
            sys.exit(f"{j.out.name}: {err}")
    todo = [j for j in jobs if force or not is_fresh(j)]
    if todo:
        try:
            import mlx_audio  # noqa: F401
            import misaki  # noqa: F401
        except ImportError:
            sys.exit(f"the voice dependencies aren't installed; run: {INSTALL_HINT}")
        if any(LANGS[j.lang][0] not in "ab" for j in todo) and _phonemiser_missing():
            sys.exit(f"the espeak-ng phonemiser (bundled in espeakng-loader) is missing; run: {INSTALL_HINT}")
    import contextlib
    import io

    model = _load_model() if todo else None
    results = []
    for j in jobs:
        if j not in todo:
            side = read_sidecar(j.out) or {}
            print(f"  cached: {j.out.name} ({side.get('duration', 0):.2f}s)")
            results.append({"out": j.out, "cached": True, "duration": side.get("duration"), "seconds": 0.0})
            continue
        import numpy as np

        t0 = time.time()
        sr = model.sample_rate
        _use_dialect(model, j.lang)
        chunks = []
        for text, pause in pieces(j.text):
            with contextlib.redirect_stdout(io.StringIO()):
                segs = [np.array(r.audio, dtype=np.float32).ravel()
                        for r in model.generate(text=text, voice=j.voice, speed=float(j.speed),
                                                lang_code=LANGS[j.lang][0])]
            chunks += [_trim(np.concatenate(segs), sr), np.zeros(round(pause * sr), dtype=np.float32)]
        audio = _trim(np.concatenate(chunks), sr)
        _write_wav(j.out, audio, model.sample_rate)
        took = round(time.time() - t0, 2)
        dur = round(len(audio) / model.sample_rate, 3)
        sidecar_path(j.out).write_text(json.dumps({**j.key(), "duration": dur, "seconds": took},
                                                  indent=1, ensure_ascii=False))
        print(f"  voice: {j.out.name} ({dur:.2f}s audio in {took:.2f}s)")
        results.append({"out": j.out, "cached": False, "duration": dur, "seconds": took})
    return results


def _languages_help() -> str:
    rows = [f"  {k:<6} {v[1]:<16} default {v[2]:<9} voices: {' '.join(presets_for(k))}" for k, v in LANGS.items()]
    return (f"model: {MODEL_ID} (Kokoro-82M), licence {MODEL_LICENCE}, through mlx-audio (MIT)\n"
            f"languages:\n" + "\n".join(rows))


def main() -> None:
    ap = argparse.ArgumentParser(description="Local text-to-speech (Kokoro-82M on MLX) → mono 24 kHz WAV + sidecar",
                                 epilog=_languages_help(), formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", nargs="?", help="the line to speak (`*` and `|` marks are stripped)")
    ap.add_argument("-o", "--out", type=Path, help="output WAV")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--preset", help="voice preset (default: the language's default)")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--pronounce", help='JSON map of respellings, e.g. \'{"SaaS": "sass"}\'')
    ap.add_argument("--force", action="store_true", help="re-synthesise even if the clip is cached")
    ap.add_argument("--list", action="store_true", help="print languages and voice presets")
    a = ap.parse_args()
    if a.list:
        print(_languages_help())
        return
    if not a.text or not a.out:
        ap.error("text and -o/--out are required")
    if err := validate(a.lang, a.preset):
        sys.exit(err)
    text = spoken(a.text, json.loads(a.pronounce) if a.pronounce else None)
    synthesize_many([Job(a.out.resolve(), text, a.lang, a.preset, a.speed)], force=a.force)


if __name__ == "__main__":
    main()
