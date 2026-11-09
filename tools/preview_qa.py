"""Preview QA: after a render, check that `edit/preview.mp4` plays the words and the cuts the edit says it does.

    uv run tools/preview_qa.py <project> [--spec edit/short.json] [--reuse]

`check` can only say what the cut should sound like; this listens. It transcribes the preview (local Whisper),
compares what is heard with the words the edit keeps, and measures the sound at every cut against the speech level.
It reports, each with the output time, the segment and the fix:

    unexpected speech   heard words (more than three letters each) the edit doesn't contain: a stumble the transcript hid
                        (not after the last kept word: the end tail leaves nothing but Whisper's own additions there)
    clipped word        a kept word that is cut short at a cut
    repeat              a 3-word run that plays more often than the takes say it
    restart             a false start heard in the preview
    cut energy          a cut louder than -12 dB relative to the speech (a cut through a word)

Each source word belongs to the one segment that covers most of it (Whisper's stamps can straddle a cut that sits in
a pause inside them). Cut times come from the real length of each rendered clip, after edge refinement.
Thresholds were calibrated on 6 projects plus a control with injected faults: good cuts sit at -13.6 dB or lower, the
injected ones at -7.2 and +1.6 dB; revisit them with more data.
"""

from __future__ import annotations

import difflib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from edit_plan import norm, sentences  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CUT_DB = -12.0        # a cut louder than this, relative to the speech, is a cut through sound
CUT_WINDOW = 0.04     # s each side of a cut
OWN_MIN = 0.03        # s of overlap for a word to belong to a segment
SHORT_WORD = 3        # letters: words this short don't count as unexpected speech (Whisper adds and drops them)
UNEXPECTED_MIN = 1    # heard words of more than SHORT_WORD letters, in a run the edit doesn't contain


def _fault(kind: str, t: float, seg: int | None, message: str, fix: str) -> dict:
    return {"kind": kind, "t": round(t, 2), "segment": seg, "message": f"{t:.2f} s: {message}", "fix": fix}


def expected(p: Any, root: Path) -> tuple[list[dict], list[int]]:
    """The words the edit plays, in order, each once: {"w": normalised, "seg": piece, "t": output seconds}; and the
    indexes where a cut falls between two of them."""
    offs = p.offsets()
    owner: dict[int, list[tuple[float, str, float]]] = {}
    for take in {s.take for s in p.segments}:
        ws = json.loads((root / "edit" / "transcripts" / f"{take}.json").read_text())["words"]
        for w in ws:
            if w.get("type", "word") != "word" or not norm(w["text"]):
                continue
            best = max(((min(w["end"], s.t_out) - max(w["start"], s.t_in), k) for k, s in enumerate(p.segments)
                        if s.take == take), default=(0, None))
            if best[1] is not None and best[0] > OWN_MIN:
                k = best[1]
                owner.setdefault(k, []).append((w["start"], norm(w["text"]), offs[k] + max(0.0, w["start"] - p.segments[k].t_in)))
    words: list[dict] = []
    cuts: list[int] = []
    for k in range(len(p.segments)):
        if words:
            cuts.append(len(words))
        words += [{"w": n, "seg": k, "t": t} for _, n, t in sorted(owner.get(k, []))]
    return words, cuts


def clip_durations(root: Path, n: int) -> list[float]:
    clips = sorted((root / "edit" / "clips_preview").glob("seg_*.mov"))[:n]  # older renders leave extra files
    if len(clips) < n:
        raise SystemExit(f"edit/clips_preview has {len(clips)} clips for {n} segments; render the preview again")
    return [float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(c)],
                                 capture_output=True, text=True, check=True).stdout) for c in clips]


def cut_energy(p: Any, root: Path) -> list[dict]:
    """The 40 ms each side of every cut on the dialogue-only base, against the speech level (its 90th percentile).
    Independent of any transcript: a clipped word is loud at the cut. A cut at the very start of a take is clean."""
    import numpy as np
    from audio_env import envelope

    db, _ = envelope(root / "edit" / "base_preview.mov")
    speech = float(np.percentile(db, 90))
    durs = clip_durations(root, len(p.segments))
    if len(db) * 0.005 < sum(durs) - 0.5 - 0.05 * len(durs):  # a frame of rounding per clip is not stale
        raise SystemExit(f"edit/base_preview.mov is {len(db) * 0.005:.1f} s but the clips add up to {sum(durs):.1f} s: "
                         f"the preview is stale, render it again")
    hop, t, out = 0.005, 0.0, []
    for k, d in enumerate(durs[:-1]):
        t += d
        for side, a, b, seg in (("end of", t - CUT_WINDOW, t - 0.01, k), ("start of", t + 0.01, t + CUT_WINDOW, k + 1)):
            if side == "start of" and p.segments[k + 1].t_in <= 0.02:
                continue  # the media starts there: nothing was cut
            lvl = float(db[int(a / hop):int(b / hop)].max()) - speech
            if lvl > CUT_DB:
                out.append(_fault("cut_energy", t, seg,
                                  f"sound at the cut ({side} segment {seg}): {lvl:+.1f} dB relative to speech "
                                  f"(over {CUT_DB:g} dB)",
                                  f"the cut lands in a word: end segment {k} on the end of a word (`to`) and start segment "
                                  f"{k + 1} on the start of one (`from`), or keep the neighbouring words"))
    return out


def transcribe(root: Path, language: str | None) -> list[dict]:
    from transcribe_local import transcribe_one

    qa = root / "edit" / "qa"
    qa.mkdir(exist_ok=True)
    (qa / "transcripts" / "preview.json").unlink(missing_ok=True)  # the transcriber reuses a cached file by name
    transcribe_one(root / "edit" / "preview.mp4", qa, None, language, 0, None)
    return heard_words(root)


def heard_words(root: Path) -> list[dict]:
    d = json.loads((root / "edit" / "qa" / "transcripts" / "preview.json").read_text())
    return [w for w in d["words"] if w.get("type", "word") == "word" and norm(w["text"])]


def _trigrams(ws: list[str]) -> Counter:
    return Counter(" ".join(ws[i:i + 3]) for i in range(len(ws) - 2))


def compare(p: Any, root: Path, heard: list[dict]) -> tuple[list[dict], dict]:
    """Faults from comparing the heard words with the expected ones (no audio needed)."""
    exp, cuts = expected(p, root)
    e = [x["w"] for x in exp]
    g = [norm(w["text"]) for w in heard]
    offs = p.offsets()
    seg_at = lambda t: max(0, min(len(p.segments) - 1, next((k for k in range(len(offs) - 1) if offs[k] <= t < offs[k + 1]),  # noqa: E731
                                                              len(p.segments) - 1)))
    faults: list[dict] = []
    sm = difflib.SequenceMatcher(a=e, b=g, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "insert" and i1 >= len(e):
            continue  # after the last kept word: the end tail stops the audio before the next source word, so this is Whisper
        if tag in ("insert", "replace"):
            extra = [(heard[j]["start"], g[j]) for j in range(j1, j2)]
            run = [x for _, x in extra if len(x) > SHORT_WORD]
            if len(run) >= UNEXPECTED_MIN and (j2 - j1) > (i2 - i1) and not _is_mishearing(e[i1:i2], g[j1:j2]):
                t = extra[0][0]
                faults.append(_fault("unexpected_speech", t, seg_at(t),
                                     f"speech heard that the edit doesn't contain: {' '.join(g[j1:j2])!r}",
                                     f"segment {seg_at(t)} plays something the transcript does not show: cut around it, or "
                                     f"keep the line where it is said cleanly"))
        near = [c for c in cuts if i1 - 1 <= c <= i2]
        if near and tag in ("delete", "replace"):
            for a, b in zip(exp[i1:i2], g[j1:j2] + [""] * (i2 - i1)):
                if (not b and len(a["w"]) >= 4) or (b and len(b) < 0.7 * len(a["w"]) and a["w"].startswith(b[:2])):
                    faults.append(_fault("clipped_word", a["t"], a["seg"],
                                         f"clipped word at a cut: expected {a['w']!r}, heard {b!r}",
                                         f"segment {a['seg']} loses the end or start of {a['w']!r}: keep the neighbouring "
                                         f"word, or move the edge into the pause"))
    said: list[str] = []  # everything the speaker said in the takes used: audio can't repeat more than that
    for take in sorted({s.take for s in p.segments}):
        said += [norm(w["text"]) for w in json.loads((root / "edit" / "transcripts" / f"{take}.json").read_text())["words"]
                 if w.get("type", "word") == "word" and norm(w["text"])]
    e3, g3 = _trigrams(said), _trigrams(g)
    for tri, n in g3.items():
        if n > 1 and n > e3[tri]:
            at = [heard[i]["start"] for i in range(len(g) - 2) if " ".join(g[i:i + 3]) == tri][-1]
            faults.append(_fault("repeat", at, seg_at(at), f"{tri!r} plays {n}× (said {e3[tri]}× in the takes)",
                                 "a line plays twice: keep only the clean one, or drop the segment that repeats it"))
    for s in sentences({"preview": heard}):
        if s.get("restart_of"):
            faults.append(_fault("restart", s["start"], seg_at(s["start"]),
                                 f"false start heard in the preview: {s['text']!r} (again in {s['restart_of']})",
                                 "keep only the take of the line that is said through"))
    return faults, {"expected_words": len(e), "heard_words": len(g), "similarity": round(sm.ratio(), 2), "cuts": len(cuts)}


def _is_mishearing(a: list[str], b: list[str]) -> bool:
    """A replaced run that sounds like the expected one (Whisper hears 'girlie' as 'girl y', 'tecnologia' as
    'tecnologias'): the same letters, split or ended differently, not a stumble."""
    return bool(a) and difflib.SequenceMatcher(a="".join(a), b="".join(b)).ratio() >= 0.7


def preview_qa(root: Path, spec: Path | None = None, heard: list[dict] | None = None, reuse: bool = False) -> dict:
    """{"ok", "errors": [fault…], "stats"}; transcribes the preview unless `heard` words (or `reuse` of the last
    transcript) are given."""
    import short_spec as SS

    spec = spec or root / "edit" / "short.json"
    if not (root / "edit" / "preview.mp4").exists():
        raise SystemExit("no edit/preview.mp4; render the preview first (shortform render --preview)")
    p, _ = SS.load(spec, root)
    if heard is None:
        heard = heard_words(root) if reuse else transcribe(root, _language(root))
    faults, stats = compare(p, root, heard)
    faults += cut_energy(p, root)
    faults.sort(key=lambda f: f["t"])
    return {"ok": not faults, "errors": faults, "stats": stats}


def _language(root: Path) -> str | None:
    for f in sorted((root / "edit" / "transcripts").glob("*.json")):
        return json.loads(f.read_text()).get("language_code") or None
    return None


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project", help="footage/<project>")
    ap.add_argument("--spec", help="default: <project>/edit/short.json")
    ap.add_argument("--reuse", action="store_true", help="use the last transcript of the preview instead of transcribing again")
    a = ap.parse_args(argv)
    root = Path(a.project)
    res = preview_qa(root, Path(a.spec) if a.spec else None, reuse=a.reuse)
    s = res["stats"]
    print(f"{root.name}: {s['expected_words']} expected words, {s['heard_words']} heard, similarity {s['similarity']}, {s['cuts']} cuts")
    for f in res["errors"]:
        print(f"  FAULT {f['message']}\n        fix: {f['fix']}")
    if res["ok"]:
        print("  no faults")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
