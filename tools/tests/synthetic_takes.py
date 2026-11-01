"""Synthetic talking-head audio with a known script, made with the local voice tool (tools/gen/voice.py).

Each take: two sentences (the second with a false start), 5 s of silence, then a ~20 s stretch of
speech (four sentences). The silence-then-speech shape is where Whisper skipped whole stretches.

    from synthetic_takes import build, SCRIPTS
    wav, sentences = build("es")      # cached under the system temp dir; needs `uv sync --group gen`

    uv run tools/tests/synthetic_takes.py es en    # build them and print the paths
"""

from __future__ import annotations

import difflib
import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS / "gen"))

CACHE = Path(tempfile.gettempdir()) / "engine-synthetic-takes"
SCRIPTS = {
    "en": (["Most people think that saving money starts with a strict budget.",
            "I was- I was thinking about that on the train last week."],
           ["Here is what actually works for me, and honestly, it is much simpler than any budget I have ever tried.",
            "First, I move a small amount into savings every payday, before I can spend it.",
            "Second, I look at my spending once a week, and I give every goal its own name.",
            "That is the whole system, and it only takes a few minutes on a Sunday morning."]),
    "es": (["Mucha gente cree que ahorrar dinero empieza con un presupuesto estricto.",
            "Yo estaba- yo estaba pensando en eso en el tren la semana pasada."],
           ["Esto es lo que de verdad me funciona, y la verdad es mucho más simple que cualquier presupuesto que probé.",
            "Primero, aparto un poco de dinero cada día de pago, antes de poder gastarlo.",
            "Segundo, reviso mis gastos una vez por semana y le pongo nombre a cada meta.",
            "Ese es todo el sistema, y solo me toma unos minutos el domingo por la mañana."]),
}
LEAD, GAP, TAIL = 0.6, 5.0, 0.8  # s of silence before, between and after


def available() -> bool:
    """The local voice backend is installed (`uv sync --group gen`)."""
    import voice
    return voice.backend_missing(voice.pick_backend(None)) is None and importlib.util.find_spec("misaki") is not None


def build(lang: str) -> tuple[Path, list[str]]:
    """(16 kHz mono WAV of the take, its sentences in order). Synthesised once, then cached."""
    import voice
    CACHE.mkdir(parents=True, exist_ok=True)
    before, after = SCRIPTS[lang]
    parts = [CACHE / f"{lang}_before.wav", CACHE / f"{lang}_after.wav"]
    voice.synthesize_many([voice.Job(parts[0], voice.spoken(" ".join(before)), lang),
                           voice.Job(parts[1], voice.spoken(" ".join(after)), lang)])
    out = CACHE / f"{lang}_take.wav"
    sil = lambda d: ["-f", "lavfi", "-t", str(d), "-i", "anullsrc=r=24000:cl=mono"]  # noqa: E731
    subprocess.run(["ffmpeg", "-v", "error", "-y", *sil(LEAD), "-i", str(parts[0]), *sil(GAP), "-i", str(parts[1]),
                    *sil(TAIL), "-filter_complex", "[0:a][1:a][2:a][3:a][4:a]concat=n=5:v=0:a=1,aresample=16000[a]",
                    "-map", "[a]", "-ac", "1", "-c:a", "pcm_s16le", str(out)], check=True)
    return out, before + after


def tokens(text: str) -> list[str]:
    return [t for t in (re.sub(r"[^\wáéíóúñü']", "", w.lower()) for w in re.split(r"[\s-]+", text)) if t]


def score(words: list[dict], reference: list[str]) -> dict:
    """How complete a transcript is against the sentences actually spoken:
    recall (share of reference words found, in order), ends (sentences whose last word ends in . ? ! or is
    followed by ≥ 0.25 s, so captions break there) out of `sentences`, and `marks` (sentence-end punctuation)."""
    ws = [w for w in words if w["type"] == "word"]
    ref = [(i, t) for i, s in enumerate(reference) for t in tokens(s)]
    got = [(k, t) for k, w in enumerate(ws) for t in tokens(w["text"])]
    sm = difflib.SequenceMatcher(None, [t for _, t in ref], [t for _, t in got], autojunk=False)
    where: dict[int, int] = {}
    for a, b, n in sm.get_matching_blocks():
        for d in range(n):
            where[a + d] = got[b + d][0]
    # a sentence's end in the transcript: the word before the next sentence's first matched word (so a
    # misheard last word still counts by its punctuation), or the last word of the transcript
    first = {}
    for j, (i, _) in enumerate(ref):
        if j in where and i not in first:
            first[i] = where[j]
    ends = 0
    for i in range(len(reference)):
        k = first[i + 1] - 1 if i + 1 < len(reference) and i + 1 in first else (len(ws) - 1 if i + 1 == len(reference) else None)
        if k is None or k < 0:
            continue
        nxt = ws[k + 1]["start"] if k + 1 < len(ws) else None
        if re.search(r"[.?!]$", ws[k]["text"]) or nxt is None or nxt - ws[k]["end"] >= 0.25:
            ends += 1
    return {"recall": round(len(where) / max(1, len(ref)), 3), "ends": ends, "sentences": len(reference),
            "marks": sum(1 for w in ws if re.search(r"[.?!]$", w["text"]))}


if __name__ == "__main__":
    for lang in sys.argv[1:] or SCRIPTS:
        wav, _ = build(lang)
        print(wav)
