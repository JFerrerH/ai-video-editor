"""Measure transcription prompt candidates per backend and language (the table in tools/transcribe_prompts.md).

For each take and candidate prompt (the verbatim prompt, none, a plain punctuated sentence) it records:
words, recall, sentence-end marks, and seconds of speech no word covers before patching (holes).
Recall is against the script for synthetic takes (tools/tests/synthetic_takes.py) and against the
fullest candidate on the same backend for real takes, which have no script. Only numbers are written:
real takes are named by language and length, never by file.

    uv run tools/tests/measure_prompts.py --out rows.json es:footage/<p>/take1.mov en:footage/<q>/clip.mp4
    (synthetic takes are always included; run once per backend: on the Mac and in the container)
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent))
sys.path.insert(0, str(TESTS))

import synthetic_takes as ST  # noqa: E402
import transcribe_local as T  # noqa: E402
from audio_env import envelope, speech_runs  # noqa: E402


def candidates(lang: str) -> dict[str, str | None]:
    return {"verbatim": T.VERBATIM_PROMPTS.get(lang), "none": None, "plain": T.PLAIN_PROMPTS.get(lang)}


def holes(words: list[dict], runs) -> float:
    return round(sum(b - a for a, b in T.uncovered(words, runs)), 1)


def measure(engine: T.Engine, lang: str, wav: Path, reference: list[str] | None) -> list[dict]:
    audio = T.load_wav(wav)
    db, floor = envelope(wav)
    runs = speech_runs(db, floor)
    outs = {name: T.to_scribe_words(engine.transcribe(audio, lang, p)) for name, p in candidates(lang).items()}
    if reference is None:  # real take: the fullest candidate is the reference
        best = max(outs.values(), key=lambda ws: sum(w["type"] == "word" for w in ws))
        reference = [" ".join(w["text"] for w in best if w["type"] == "word")]
    rows = []
    for name, words in outs.items():
        s = ST.score(words, reference)
        rows.append({"candidate": name, "words": sum(w["type"] == "word" for w in words), "recall": s["recall"],
                     "marks": s["marks"], "holes_s": holes(words, runs)})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("takes", nargs="*", help="lang:path of real takes")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    backend = T.pick_backend(None)
    T.require_backend(backend)
    engine = T.Engine(backend, T.model_for(backend, None))
    takes = [(lang, "synthetic", *ST.build(lang)) for lang in ST.SCRIPTS]
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for spec in a.takes:
            lang, path = spec.split(":", 1)
            wav = Path(tmp) / f"real{len(takes)}.wav"
            T.extract_audio(Path(path), wav, 0)
            takes.append((lang, "real", wav, None))
        n = {"synthetic": 0, "real": 0}
        for lang, kind, wav, ref in takes:
            n[kind] += 1
            dur = len(T.load_wav(wav)) / T.SR
            label = f"{lang} {kind} {chr(64 + sum(1 for t in takes[:takes.index((lang, kind, wav, ref)) + 1] if t[0] == lang and t[1] == kind))} ({dur:.0f} s)"
            print(f"  {label}", file=sys.stderr, flush=True)
            for r in measure(engine, lang, wav, ref):
                rows.append({"backend": backend, "lang": lang, "take": label, **r})
    a.out.write_text(json.dumps(rows, indent=1))
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
