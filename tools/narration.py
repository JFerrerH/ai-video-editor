"""Narration timing for storyboards: script words, word times aligned to speech recognition,
headline phrases, and `@word` cues. Used by tools/storyboard.py; standard library + numpy only.

    words = script_words("Ship it in *one day.*")          # [{text, emph, brk}], marks stripped
    timed = align(words, spoken_tokens, recognised, onset, clip_end)  # strictly increasing times
    phrases(timed)                                          # adds `phrase` per word (.?! | or 7 words)
    resolve_cue("@day+0.2", timed)                          # seconds, or None if the word isn't there
"""

from __future__ import annotations

import difflib
import re
import subprocess
from pathlib import Path

ALIGN_VERSION = 2  # bump when alignment or phrase rules change: re-times cached word files
PHRASE_MAX = 7  # words per headline phrase before a forced break
MIN_GAP = 0.02  # s between consecutive word times when a recogniser bunches them
ONSET_DB = -40.0  # a clip's voice onset: first sample above this (dBFS)
CUE_RE = re.compile(r"^@([^#+-]+)(?:#(\d+))?([+-]\d*\.?\d+)?$")


def norm(tok: str) -> str:
    """Comparison form of a word: lower case, letters and digits only (any script)."""
    return re.sub(r"[\W_]+", "", tok.lower())


def script_words(narration: str) -> list[dict]:
    """The narration's words in order, as displayed: `*` and `|` removed, punctuation kept.
    `emph` = inside a `*…*` group; `brk` = a `|` follows the word (forced phrase break)."""
    out: list[dict] = []
    on = False
    for tok in narration.replace("|", " | ").split():
        if tok == "|":
            if out:
                out[-1]["brk"] = True
            continue
        core, emph = "", False
        for ch in tok:  # `*` toggles emphasis; a word is emphasised if any letter of it is inside
            if ch == "*":
                on = not on
            else:
                core += ch
                emph = emph or (on and ch.isalnum())
        if core:
            out.append({"text": core, "emph": emph, "brk": False})
    return out


def spoken_tokens(words: list[dict], pronounce: dict[str, str] | None = None) -> list[tuple[int, str]]:
    """(script word index, normalised spoken token) after the `pronounce` map, so one script word can
    map to several spoken tokens ("SaaS" → "sass", "2FA" → "two factor")."""
    lower = {k.lower(): v for k, v in (pronounce or {}).items()}
    out = []
    for i, w in enumerate(words):
        core = re.sub(r"^\W+|\W+$", "", w["text"])
        rep = (pronounce or {}).get(core, lower.get(core.lower()))
        toks = [norm(t) for t in (rep.split() if rep is not None else [w["text"]])]
        out += [(i, t) for t in toks if t] or [(i, norm(w["text"]) or w["text"])]
    return out


def align(words: list[dict], spoken: list[tuple[int, str]], recognised: list[dict],
          onset: float, clip_end: float) -> list[dict]:
    """Give every script word a start time (s from the clip start).

    `recognised` = [{text, start, end}] from speech recognition. Normalised tokens are matched with
    difflib; a matched script word takes its first spoken token's start. Unmatched words are spread
    between their matched neighbours in proportion to their length. The first word is clamped to the
    measured `onset` (Whisper stamps first words early, inside the silence). Times strictly increase
    and stay inside [onset, clip_end)."""
    rec = [(norm(r["text"]), float(r["start"])) for r in recognised if norm(r["text"])]
    sm = difflib.SequenceMatcher(None, [t for _, t in spoken], [t for t, _ in rec], autojunk=False)
    tok_time: dict[int, float] = {}
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            tok_time[a + k] = rec[b + k][1]
    first_tok: dict[int, int] = {}
    for k, (i, _) in enumerate(spoken):
        first_tok.setdefault(i, k)
    times: list[float | None] = [tok_time.get(first_tok[i]) for i in range(len(words))]
    matched = [t is not None for t in times]
    times[0] = onset
    matched[0] = True
    # interpolate the gaps by character length
    i = 0
    n = len(words)
    while i < n:
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < n and times[j] is None:
            j += 1
        t0 = times[i - 1]
        t1 = times[j] if j < n else max(t0 + MIN_GAP * (j - i + 1), clip_end - 0.15)
        lens = [len(words[k - 1]["text"]) + 1 for k in range(i, j + 1)]  # the previous word's length pushes the next
        tot = sum(lens)
        acc = 0
        for k in range(i, j):
            acc += lens[k - i]
            times[k] = t0 + (t1 - t0) * acc / tot
        i = j
    # strictly increasing, inside the clip
    hi = clip_end - MIN_GAP
    for k in range(1, n):
        times[k] = max(times[k], times[k - 1] + MIN_GAP)
    if n and times[-1] > hi:  # squeeze the tail back inside the clip
        for k in range(n - 1, 0, -1):
            times[k] = min(times[k], hi - MIN_GAP * (n - 1 - k))
            times[k] = max(times[k], times[k - 1] + 1e-3)
    return [{**w, "t": round(t, 3) + 0.0, "aligned": m} for w, t, m in zip(words, times, matched)]


def phrases(words: list[dict]) -> list[dict]:
    """Cut headline phrases: after `.?!` (ignoring closing quotes/brackets) and after `|`; a run
    longer than PHRASE_MAX words is split into even chunks of at most PHRASE_MAX (8 → 4 + 4, so no
    word is left alone on screen). Writes `phrase` (0-based) into each word."""
    runs, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[.?!…][\"'”’»)\]]*$", w["text"]) or w.get("brk"):
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    p = 0
    for run in runs:
        k = -(-len(run) // PHRASE_MAX)  # chunks
        for j, w in enumerate(run):
            w["phrase"] = p + j * k // len(run)
        p += k
    return words


def resolve_cue(cue: str, words: list[dict]) -> float | None:
    """`@word`, `@word#n` (n-th occurrence, 1-based), `@word+0.2` → seconds (same clock as the words'
    `t`). Case- and punctuation-insensitive. None if the word isn't in the narration."""
    m = CUE_RE.match(cue)
    if not m:
        return None
    want, nth, off = norm(m.group(1)), int(m.group(2) or 1), float(m.group(3) or 0)
    hits = [w["t"] for w in words if norm(w["text"]) == want]
    if len(hits) < nth:
        return None
    return round(hits[nth - 1] + off, 3)


def is_cue(v) -> bool:
    return isinstance(v, str) and v.startswith("@") and bool(CUE_RE.match(v))


def decode_mono(path: Path, sr: int = 16000):
    """Any audio file → float32 mono numpy array at `sr` (through ffmpeg)."""
    import numpy as np

    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype="<f4")


def onset_of(audio, sr: int, db: float = ONSET_DB) -> float:
    """Seconds to the first sample above `db` dBFS (0 if none)."""
    import numpy as np

    hit = np.nonzero(np.abs(audio) > 10 ** (db / 20))[0]
    return round(float(hit[0]) / sr, 4) if len(hit) else 0.0
