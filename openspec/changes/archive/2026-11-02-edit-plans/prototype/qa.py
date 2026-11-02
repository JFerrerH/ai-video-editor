"""Prototype preview QA (preview-qa-gate D3): transcribe the preview, compare with the words the edit keeps.

    uv run python qa.py footage/<p>        # from the engine repo root
"""
from __future__ import annotations

import difflib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compile_plan import norm  # noqa: E402


def expected(proj: Path) -> tuple[list[str], list[int]]:
    """The words the edit plays, in order: each word once, in the segment that holds most of it (Whisper's stamps
    can straddle a cut that sits in the pause inside them)."""
    spec = json.loads((proj / "edit" / "short.json").read_text())
    segs = spec["segments"]
    owner = {}
    for take in {g["take"] for g in segs}:
        ws = json.loads((proj / "edit" / "transcripts" / f"{take}.json").read_text())["words"]
        for n, w in enumerate(ws):
            if w.get("type", "word") != "word" or not norm(w["text"]):
                continue
            best = max(((min(w["end"], g["out"]) - max(w["start"], g["in"]), k) for k, g in enumerate(segs) if g["take"] == take),
                       default=(0, None))
            if best[1] is not None and best[0] > 0.03:
                owner.setdefault(best[1], []).append((w["start"], norm(w["text"])))
    words, cuts = [], []
    for k in range(len(segs)):
        if words:
            cuts.append(len(words))
        words += [t for _, t in sorted(owner.get(k, []))]
    return words, cuts


def cut_energy(proj: Path) -> list[str]:
    """SKILL "Verify before presenting" 1b: on the dialogue-only base, the 40 ms each side of every cut must be
    ≥ 20 dB under the speech level. Independent of any transcript: a clipped word is loud at the cut."""
    import numpy as np
    from audio_env import envelope
    spec = json.loads((proj / "edit" / "short.json").read_text())
    db, floor = envelope(proj / "edit" / "base_preview.mov")
    speech = float(np.percentile(db, 90))
    clips = sorted((proj / "edit" / "clips_preview").glob("seg_*.mov"))[:len(spec["segments"])]  # older renders leave extra files
    durs = [float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(c)],
                                 capture_output=True, text=True).stdout) for c in clips]  # real cut times, after refinement
    hop, t, out = 0.005, 0.0, []
    for k, d in enumerate(durs[:-1]):
        t += d
        for side, a, b in (("end of", t - 0.04, t - 0.01), ("start of", t + 0.01, t + 0.04)):
            lvl = float(db[int(a / hop):int(b / hop)].max())
            if lvl > speech - 12:  # calibrated: injected faults −7/+2 dB, good cuts ≤ −13.6 dB
                seg = k if side == "end of" else k + 1
                out.append(f"sound at the cut {t:.2f} s ({side} segment {seg}): {lvl - speech:+.1f} dB vs speech")
    return out


def got_words(proj: Path) -> list[dict]:
    out = proj / "edit" / "qa"
    out.mkdir(exist_ok=True)
    lang = "en" if proj.name.endswith("-en") else "es"
    subprocess.run(["uv", "run", "tools/transcribe_local.py", str(proj / "edit" / "preview.mp4"), "--edit-dir", str(out),
                    "--language", lang], check=True, capture_output=True)
    return [w for w in json.loads((out / "transcripts" / "preview.json").read_text())["words"]
            if w.get("type", "word") == "word" and norm(w["text"])]


def tri(ws: list[str]) -> Counter:
    return Counter(" ".join(ws[i:i + 3]) for i in range(len(ws) - 2))


def main() -> None:
    proj = Path(sys.argv[1])
    exp, cuts = expected(proj)
    gw = got_words(proj)
    g = [norm(w["text"]) for w in gw]
    faults = []
    sm = difflib.SequenceMatcher(a=exp, b=g, autojunk=False)
    ops = sm.get_opcodes()
    for tag, i1, i2, j1, j2 in ops:
        if tag in ("insert", "replace") and (j2 - j1) - (i2 - i1) >= 3:
            faults.append(f"unexpected speech: {' '.join(g[j1:j2])!r}")
        near = [c for c in cuts if i1 - 1 <= c <= i2]
        if near and tag in ("delete", "replace"):
            for a, b in zip(exp[i1:i2], g[j1:j2] + [""] * (i2 - i1)):
                if (not b and len(a) >= 4) or (b and len(b) < 0.7 * len(a) and a.startswith(b[:2])):  # Whisper drops lone "y", "el"
                    faults.append(f"clipped word at a cut: expected {a!r}, heard {b!r}")
    spec = json.loads((proj / "edit" / "short.json").read_text())
    said = []  # everything the speaker said in the takes used: audio can't repeat more than that unless it plays twice
    for take in sorted({x["take"] for x in spec["segments"]}):
        said += [norm(w["text"]) for w in json.loads((proj / "edit" / "transcripts" / f"{take}.json").read_text())["words"]
                 if w.get("type", "word") == "word" and norm(w["text"])]
    e3, g3 = tri(said), tri(g)
    faults += [f"repeat: {t!r} plays {n}× (said {e3[t]}× in the takes)" for t, n in g3.items() if n > 1 and n > e3[t]]
    faults += cut_energy(proj)
    from compile_plan import sentences
    sents = sentences({"preview": gw})
    faults += [f"false start heard in the preview: {x['text']!r} (again in {x['restart_of']})" for x in sents if x.get("restart_of")]
    print(f"{proj.name}: {len(exp)} expected words, {len(g)} heard, similarity {sm.ratio():.2f}, {len(cuts)} cuts")
    print("\n".join(f"  FAULT {f}" for f in faults) or "  no faults")


if __name__ == "__main__":
    main()
