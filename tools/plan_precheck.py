"""Everything about an edit plan that can be checked without the audio: only the plan, the transcript JSON and the
component schemas. Standard library only (a test enforces it), so a service can run it without the engine's models,
numpy or a worker. `edit_plan.build` runs the part that doesn't depend on timing first and stops on its errors, and does the timing
checks again with the same functions on the audio-measured cut.

    uv run tools/run_job.py -   {"op": "plan_precheck", "project": "<p>", "args": {"plan": "edit/plan.json"}}

    import plan_precheck
    plan_precheck.check(plan, {"take1": <transcript JSON>}, order=["take1"])   # {"errors": […], "warnings": […]}

The times it works with come from the transcript's word times, with the air round each cut that edge refinement leaves
(`PRE` / `POST`) and the same dead-air splits. They are approximate (Whisper stretches a stamp over the pauses beside a
word: on real footage a cut can be a second or two off), so the errors that come from them are also listed under
`timed_errors`, and the build recomputes them from the audio.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import edit_plan as E  # noqa: E402
import overlay_schema  # noqa: E402

PRE, POST = 0.10, 0.12            # s of air kept before a cut's first word and after its last (short_spec's `edges` defaults)
MIN_PAUSE = 0.06                  # s: a quiet run this long is a pause (short_spec); a shorter gap between two words is none
DEAD_AIR, MIN_SPLIT = 0.30, 0.08  # s: a pause this long inside a run is cut down to the air, when that removes this much

FUNCTION_WORDS = {
    # es
    "de", "que", "por", "la", "el", "y", "en", "un", "una", "me", "se", "les", "a", "mi",
    "los", "las", "con", "para", "nos", "si", "tú", "esa", "lo", "es", "del", "al",
    "unos", "unas", "nuestra", "nuestro", "nuestras", "nuestros", "su", "sus", "tus", "mis",
    "este", "esta", "primer",
    # en
    "the", "a", "an", "of", "to", "and", "in", "on", "for", "with", "my", "is", "that",
}
# word-synced devices: emphasis, not restatement (the echo rule exempts them; captions don't emphasise what they show)
SYNCED_MAX_WORDS = 3
# text keys whose content a viewer reads on screen (code lines / emails are decoration)
ECHO_KEYS = {"label", "stamp", "title", "chip", "note", "kicker", "year", "text", "docTitle",
             "emphasis", "success", "button", "handle", "items", "lines_", "photos", "screens"}


# ── echo: a graphic must complement the captions, never repeat them ─────────
def echo_norm(s: str) -> str:
    return re.sub(r"[^\wáéíóúñü%]", "", s.lower())


def echo_exempt(e: dict) -> bool:
    """Emphasis, not restatement: stickers and behind-the-head words of at most SYNCED_MAX_WORDS words each
    (kinetic type on its spoken beat), and a notice quoting what the speaker reports."""
    p = e.get("props", {})
    if e["type"] == "Notice":
        return True
    if e["type"] == "Stickers":
        return all(len(str(i.get("text", "")).split()) <= SYNCED_MAX_WORDS for i in p.get("items", []))
    if e["type"] == "BehindWord":
        return len(str(p.get("word", "")).split()) <= SYNCED_MAX_WORDS
    return False


def echo(events: list[dict], caption_words: list[dict], window: float = 1.0) -> list[str]:
    """Any content word (or number) shown by an event (`type`, `start`, `duration`, `props`) that is also captioned
    (`text`, `start`; already cleaned) within ±window s of it."""
    def texts(obj, key=""):
        if isinstance(obj, str):
            if key in ECHO_KEYS:
                yield obj
        elif isinstance(obj, dict):
            for k, v in obj.items():
                yield from texts(v, k if k in ECHO_KEYS else key)
        elif isinstance(obj, list):
            for v in obj:
                yield from texts(v, key)

    out = []
    for e in events:
        if echo_exempt(e):
            continue
        a, b = e["start"] - window, e["start"] + e["duration"] + window
        spoken = {echo_norm(w["text"]) for w in caption_words if a <= w["start"] <= b}
        shown = {echo_norm(t) for s in texts(e.get("props", {})) for t in re.split(r"[\s·/\n]+", s)}
        hits = sorted(t for t in shown & spoken
                      if t and (t.isdigit() or t.endswith("%") or (len(t) > 3 and t not in FUNCTION_WORDS)))
        if hits:
            out.append(f"ECHO {e['type']} @ {e['start']:.2f}s shows {hits} while the captions say them")
    return out


def clean(word: str, fixes: dict[str, str] | None = None) -> str:
    core = re.sub(r"[.,]+$", "", word.strip())
    return (fixes or {}).get(core.lower(), core)


# ── the cut: kept sentences → runs → segments ──────────────────────────────
def cut_plan(plan: dict, words: dict, by_id: dict) -> dict:
    """The segments a plan's `keep` makes (a punch-in's sentence and the low line are cuts of their own; a long
    pause inside a run is a jump cut) and the cuts that fall where words run together.
    {"story", "segs", "low_ids", "breaks", "errors"}; each seg is {take, a, b, low}."""
    kept = [i for item in plan["keep"] for i in E._ids(item, by_id, "keep", [])]
    story = [by_id[i] for i in kept]
    errors: list[str] = []
    low = plan.get("low")
    low_ids = E._span(words, by_id[low["at"]], low["words"]) if low else None
    breaks: dict[str, set[int]] = {}
    for b in plan.get("beats") or []:
        if b.get("punch"):
            s = by_id[b["at"]]
            breaks.setdefault(s["take"], set()).update({s["a"], s["b"] + 1})
    if low_ids:
        breaks.setdefault(by_id[low["at"]]["take"], set()).update({low_ids[0], low_ids[1] + 1})
    runs = E._runs(story)
    for take, xs in breaks.items():  # a cut made for the plan must fall in a pause
        ws = words[take]
        for x in sorted(xs):
            inside = any(r["take"] == take and r["a"] < x <= r["b"] for r in runs)
            if inside and 0 < x < len(ws) and ws[x]["start"] - ws[x - 1]["end"] < E.BREAK_GAP:
                what = "the low line" if low_ids and x in (low_ids[0], low_ids[1] + 1) else "a punch-in"
                errors.append(f"{what} would cut between \"{ws[x - 1]['text'].strip()}\" and \"{ws[x]['text'].strip()}\", which run "
                              f"together ({ws[x]['start'] - ws[x - 1]['end']:.2f} s); a cut needs a pause of {E.BREAK_GAP:g} s: "
                              f"{'pick other words' if what == 'the low line' else 'punch in on a sentence that follows a pause'}")
    segs: list[dict] = []
    for r in runs:
        ws = words[r["take"]]
        cuts = sorted({r["a"], r["b"] + 1} | {x for x in breaks.get(r["take"], ()) if r["a"] < x <= r["b"]})
        for x in range(r["a"] + 1, r["b"] + 1):  # long pauses inside the run, when both sides stay long enough
            if ws[x]["start"] - ws[x - 1]["end"] >= E.SPLIT_GAP and x not in cuts:
                before = max((c for c in cuts if c < x), default=r["a"])
                after = min((c for c in cuts if c > x), default=r["b"] + 1)
                if ws[x - 1]["end"] - ws[before]["start"] >= E.MIN_PIECE and ws[after - 1]["end"] - ws[x]["start"] >= E.MIN_PIECE:
                    cuts = sorted(cuts + [x])
        for a, nxt in zip(cuts, cuts[1:]):
            is_low = bool(low_ids) and r["take"] == by_id[low["at"]]["take"] and (a, nxt - 1) == low_ids
            segs.append({"take": r["take"], "a": a, "b": nxt - 1, "low": is_low})
    return {"story": story, "segs": segs, "low_ids": low_ids, "breaks": breaks, "errors": errors}


def no_pause_cuts(story: list[dict], words: dict) -> list[str]:
    """Warnings for a kept run starting or ending where the transcript's words run together (under `MIN_PAUSE`).
    Only a warning: Whisper stamps a word over the pause beside it, so a real pause can read as no gap at all; the
    audio check in the build decides, and refuses a cut through sound. A cut the plan itself makes (a punch-in, the
    low line) is an error in `cut_plan`: there the plan chooses the words."""
    out = []
    for r in E._runs(story):
        ws = words[r["take"]]
        if r["a"] > 0 and (g := ws[r["a"]]["start"] - ws[r["a"] - 1]["end"]) < MIN_PAUSE:
            out.append(f"{r['ids'][0]} starts where \"{ws[r['a'] - 1]['text'].strip()}\" and \"{ws[r['a']]['text'].strip()}\" "
                       f"run together in the transcript ({g:.2f} s); if the build says it cuts through sound, "
                       f"keep the neighbouring sentence too, or start at another sentence")
        if r["b"] + 1 < len(ws) and (g := ws[r["b"] + 1]["start"] - ws[r["b"]]["end"]) < MIN_PAUSE:
            out.append(f"{r['ids'][-1]} ends where \"{ws[r['b']]['text'].strip()}\" and \"{ws[r['b'] + 1]['text'].strip()}\" "
                       f"run together in the transcript ({g:.2f} s); if the build says it cuts through sound, "
                       f"keep the neighbouring sentence too, or end at another sentence")
    return out


# ── the clock: where each word plays in the output ─────────────────────────
class Clock:
    """Output times for `segs`: `out_t(take, source_t)`, `bounds[k]` (where segment k plays), `total`, and `_dur`
    set on every seg. The build's clock is the audio-measured cut; `word_clock` approximates it from word times."""

    def __init__(self, segs: list[dict], pieces: list[tuple[int, str, float, float]], durs: list[float] | None = None):
        self.pieces = pieces  # (segment, take, t_in, t_out) in play order
        self.offs, t = [], 0.0
        for i, (_, _, a, b) in enumerate(pieces):
            self.offs.append(t)
            t += durs[i] if durs else round((b - a) * E.FPS) / E.FPS  # a piece plays whole frames
        self.offs.append(t)
        self.total = t
        self.bounds = []
        for k in range(len(segs)):
            idx = [i for i, p in enumerate(pieces) if p[0] == k]
            self.bounds.append((self.offs[idx[0]], self.offs[idx[-1] + 1]))
        for g, (a, b) in zip(segs, self.bounds):
            g["_dur"] = b - a

    def out_t(self, take: str, t: float) -> float:
        for i, (_, tk, a, b) in enumerate(self.pieces):
            if tk == take and a - 0.02 <= t <= b + 0.02:
                return self.offs[i] + max(0.0, t - a)
        for i, (_, tk, a, b) in enumerate(self.pieces):  # a segment's first word is stamped early, in trimmed silence
            if tk == take and a - 0.4 <= t < a:
                return self.offs[i]
        raise ValueError(f"{take}@{t} is not in the cut")


def _core(w: dict) -> float:
    """How long a word's sound surely lasts (short_spec's `_core`): Whisper stretches a stamp over the pauses beside
    a word, so a stamp longer than its letters counts as 0.025 s per letter + 0.02 s."""
    return min(w["end"] - w["start"], 0.025 * sum(c.isalnum() for c in w["text"]) + 0.02)


def word_clock(words: dict, segs: list[dict]) -> Clock:
    """The cut as the audio would place it, from word times: the sound of a word sits at the end of its stamp going in
    (a first word is stamped early) and at the start going out (a stretched stamp runs on into the pause)."""
    pieces: list[tuple[int, str, float, float]] = []
    for k, g in enumerate(segs):
        ws = words[g["take"]]
        first, last = ws[g["a"]], ws[g["b"]]
        t_in = max(first["start"] - PRE, ws[g["a"] - 1]["end"] if g["a"] > 0 else 0.0)
        t_out = last["end"] + POST
        if g["b"] + 1 < len(ws):
            t_out = min(t_out, ws[g["b"] + 1]["start"])
        cuts: list[tuple[float, float]] = []
        for x in range(g["a"] + 1, g["b"] + 1):  # dead air inside the cut
            if ws[x]["start"] - ws[x - 1]["end"] >= DEAD_AIR:
                a, b = ws[x - 1]["end"] + POST, ws[x]["start"] - PRE
                if b - a >= MIN_SPLIT and t_in < a and b < t_out:
                    cuts.append((a, b))
        edges = [t_in] + [x for c in cuts for x in c] + [t_out]
        for i in range(0, len(edges), 2):
            pieces.append((k, g["take"], edges[i], edges[i + 1]))
    return Clock(segs, pieces)


# ── beats: when each one starts, and whether its entrances fit ─────────────
def first_in_seg(segs: list[dict], take: str, i: int) -> int | None:
    k = next(k for k, g in enumerate(segs) if g["take"] == take and g["a"] <= i <= g["b"])
    return k if segs[k]["a"] == i else None


def compile_times(words: dict, by_id: dict, plan: dict, segs: list[dict], clock: Clock) -> dict:
    """The beats in the order they play, each with its start `st` and the time its hold ends `hold`, and the
    beats that carry a device or a camera move in play order (`timed`). {"beats", "timed", "cta_st", "errors"}."""
    errors: list[str] = []
    beats = []
    for n, b in enumerate(plan.get("beats") or []):
        s = by_id[b["at"]]
        i = E._find(words, s, b["word"]) if b.get("word") else s["a"]
        w = words[s["take"]][i]
        k0 = first_in_seg(segs, s["take"], i)
        try:  # the first word of a cut is stamped early, in the silence before it: it plays where its segment starts
            st = clock.bounds[k0][0] if k0 is not None else clock.out_t(s["take"], w["start"])
        except ValueError:
            errors.append(f"plan.beats[{n}]: {b['at']} \"{w['text'].strip()}\" is cut out of the video")
            continue
        until = by_id[b.get("until", b["at"])]
        last = until["b"]
        if b.get("through"):  # the word the hold ends on, after the beat's own word when they share a sentence
            j = E._find(words, until, b["through"], i if until is s else None)
            last = j if j is not None else last
        try:
            hold = clock.out_t(until["take"], words[until["take"]][last]["end"])
        except ValueError:
            hold = st + E.HOLD_MIN
        beats.append({"n": n, "b": b, "s": s, "i": i, "w": w, "st": st, "hold": hold, "seg0": k0,
                      "label": f"beat {n} ({b['at']} \"{w['text'].strip()}\"" + (f", {b['device']}" if b.get("device") else "") + ")"})
    timed = sorted((x for x in beats if x["b"].get("device") or x["b"].get("camera") not in (None, "none")),
                   key=lambda x: x["st"])
    for x, y in zip(timed, timed[1:]):
        if y["st"] - x["st"] < 0.3:
            errors.append(f"{x['label']} and {y['label']} start within 0.3 s of each other; a beat needs its own moment: "
                          f"put them on different words")
    cta_st = None  # the CTA's card takes over the space: a graphic before it ends in time
    if plan.get("cta"):
        cs = by_id[plan["cta"]["at"]]
        ci = E._find(words, cs, plan["cta"]["word"]) if plan["cta"].get("word") else cs["a"]
        ck = first_in_seg(segs, cs["take"], ci)
        cta_st = clock.bounds[ck][0] if ck is not None else clock.out_t(cs["take"], words[cs["take"]][ci]["start"])
    return {"beats": beats, "timed": timed, "cta_st": cta_st, "errors": errors}


def resolve_cues(x: dict, dev: str, props: dict, words: dict, by_id: dict, errors: list[str]) -> None:
    """Each time prop of a device is the word it lands on: searched from the beat's word to the end of its hold,
    and replaced by that word's anchor (`edit_plan._anchor`)."""
    b, s, w = x["b"], x["s"], x["w"]
    take = s["take"]
    until_s = by_id[b.get("until", b["at"])]
    stop = until_s["b"] if until_s["take"] == take else s["b"]
    for path, v, parent, key in overlay_schema.time_fields(dev, props):
        i = E._find(words, s, v["word"], x["i"], stop)
        if i is None:
            errors.append(f"{x['label']}.props.{path}: the word {v['word']!r} isn't between "
                          f"\"{w['text'].strip()}\" and the end of the hold")
            continue
        parent[key] = E._anchor(take, words[take][i])


def fit_beat(x: dict, dev: str | None, props: dict, words: dict, later_st: float | None, cta_st: float | None,
             clock: Clock, errors: list[str]) -> float:
    """How long beat `x` holds: its words' hold, clamped to the room before the next beat (`later_st`), the CTA and
    the end, and made long enough for its entrances. Fills the entrances of a list the plan left without a time
    into `props`. Appends what doesn't fit to `errors`."""
    b, st = x["b"], x["st"]
    take = x["s"]["take"]
    total = clock.total
    nxt = later_st - E.NEXT_GAP if later_st is not None else total
    if cta_st is not None and cta_st > st:
        nxt = min(nxt, cta_st - E.NEXT_GAP)
    limit = min(nxt, total, st + E.HOLD_MAX)
    dur = E.HOLD_FIXED[dev] if dev in E.HOLD_FIXED else min(max(x["hold"] - st, E.HOLD_MIN), E.HOLD_MAX)
    dur = min(dur, nxt - st)
    need = 0.0
    if dev:
        E._fill_array_cues(dev, props, max(dur, E.HOLD_MIN))
        # entrances must have finished before the beat ends: make the hold long enough, or say what doesn't fit
        numeric = json.loads(json.dumps(props))
        for path, v, parent, key in overlay_schema.time_fields(dev, numeric):
            try:
                parent[key] = max(0.0, clock.out_t(take, E._word_at(words[take], v["after"], v["word"])) - st)
            except (ValueError, TypeError, StopIteration):
                parent[key] = 0.0
        ends = [e for _, _, e in overlay_schema.cue_finish(dev, numeric, E.FPS, max(dur, E.HOLD_MAX))]
        need = max(ends, default=0.0) + E.CUE_MARGIN
    if need > dur:
        dur = min(need, limit - st)
    if dev and need - E.CUE_MARGIN + E.CUE_MIN > dur + 0.03:  # the margin yields to the room there is; the entrances don't
        errors.append(f"{x['label']}: its entrances need {need - E.CUE_MARGIN:.2f} s, but only {dur:.2f} s fit before "
                      f"{'the next beat' if limit == nxt else 'the end of the video'}; start this beat on an earlier "
                      f"word, use fewer items, or move the next beat")
    if dur < min(0.5, E.HOLD_FIXED.get(dev, 0.5)):
        errors.append(f"{x['label']}: only {dur:.1f} s fit before the next beat or the end of the video")
    return round(dur, 2)


def layer_camera(b: dict, dev: str | None, props: dict) -> tuple[str | None, Any]:
    """The layer and the camera move a beat gets: its own, else its device's (PhonePanel's depend on its mode)."""
    layer, cam = b.get("layer"), b.get("camera")
    if dev:
        mode = props.get("mode")
        if dev == "PhonePanel" and mode in E.PHONE_PANEL:
            layer = layer or E.PHONE_PANEL[mode][0]
            cam = E.PHONE_PANEL[mode][1] if cam is None else cam
        layer = layer or E.DEFAULT_LAYER.get(dev, "front")
        if cam is None:
            cam = E.DEFAULT_CAMERA.get(dev)
    return layer, cam


def later_start(timed: list[dict], j: int) -> float | None:
    return timed[j + 1]["st"] if j + 1 < len(timed) else None


def hook_duration(first_seg_dur: float, beats: list[dict]) -> float:
    """The hook gives way to the first graphic: two cards never share the space above the head."""
    first = min((x["st"] for x in beats if x["b"].get("device") and x["b"]["device"] not in E.HOLD_FIXED
                 and not x["b"].get("props", {}).get("full")), default=E.HOOK_MAX)
    return round(max(E.HOLD_MIN, min(E.HOOK_MAX, max(E.HOOK_MIN, first_seg_dur), first - E.NEXT_GAP)), 2)


def cta_duration(cta_st: float, timed: list[dict]) -> float | None:
    """The CTA card holds until the next graphic takes over (None: to the end of the video)."""
    later = [x["st"] for x in timed if x["b"].get("device") and x["b"]["device"] not in E.HOLD_FIXED and x["st"] > cta_st]
    return round(max(E.HOLD_MIN, min(later) - E.NEXT_GAP - cta_st), 2) if later else None


# ── what is on screen, and when ─────────────────────────────────────────────
def shared_screen(events: list[dict]) -> list[str]:
    """Two graphics on screen at once, one over the other. A Flash is over at once; a full-screen scene covers the rest."""
    shown = sorted((e for e in events if e["type"] not in ("Captions", *E.HOLD_FIXED) and not e.get("props", {}).get("full")),
                   key=lambda e: e["start"])
    out = []
    for a, b in zip(shown, shown[1:]):
        over = a["start"] + a["duration"] - b["start"]
        if over > E.NEXT_GAP:
            out.append(f"{a['type']} and {b['type']} are both on screen for {over:.2f} s from {b['start']:.2f} s, one over the "
                       f"other; start the second on a later word, or end the first sooner with `through`")
    return out


def pacing(spans: list[tuple[float, float]], total: float) -> dict:
    """Visual aids on screen (an event or a camera move, as (start, end)), not cuts: the longest stretch with none.
    Over `PACING_WARN` it is a warning, over `PACING_MAX` an error. Nothing is ever added to fill it: the author
    decides what the line needs."""
    gaps, t = [], 0.0
    for a, b in sorted(spans):
        if a > t:
            gaps.append((a - t, t))
        t = max(t, b)
    if total > t:
        gaps.append((total - t, t))
    gap, at = max(gaps, default=(0.0, 0.0))
    covered = total - sum(g for g, _ in gaps)
    out = {"longest_s": round(gap, 1), "from_s": round(at, 1), "covered": round(covered / total, 2) if total else 0.0,
           "warn_over_s": E.PACING_WARN, "max_s": E.PACING_MAX}
    msg = (f"pacing: no graphic or camera move on screen for {gap:.1f} s from {at:.1f} s; show what the line says there "
           f"(a device on one of its words), or cut tighter. Nothing was added")
    if gap > E.PACING_MAX:
        out["error"] = msg
    elif gap > E.PACING_WARN:
        out["warning"] = msg
    return out


# ── the precheck ────────────────────────────────────────────────────────────
def caption_words(words: dict, segs: list[dict], clock: Clock, fixes: dict[str, str]) -> list[dict]:
    """The words the captions show, with their output times (what `Project.output_words` finds in the cut)."""
    out: list[dict] = []
    for k, g in enumerate(segs):
        for w in words[g["take"]][g["a"]:g["b"] + 1]:
            try:
                t = clock.out_t(g["take"], w["start"])
            except ValueError:
                continue
            out.append({"text": w["text"], "start": t})
    out.sort(key=lambda w: w["start"])
    merged: list[dict] = []
    for w in out:  # re-join tokens Whisper split ("pa" + "'lante", "80" + "%")
        if merged and (w["text"].startswith("'") or w["text"] in {"%", "%."}):
            merged[-1]["text"] += w["text"]
        else:
            merged.append(dict(w))
    return [{**w, "text": clean(w["text"], fixes)} for w in merged]


def check(plan: Any, transcripts: dict[str, dict], order: list[str] | None = None,
          brands: set[str] | None = None) -> dict:
    """Every error and warning about `plan` that needs no audio: {"errors": […], "warnings": […], "duration",
    "pacing"}. `transcripts` maps a take to its transcript JSON; `order` is the take order `plan ids` used (the same
    order gives the same sentence IDs); `brands` the slugs of the brand kits that exist (None: look in brands/).
    `duration` is the cut's approximate length."""
    words, restarts, breaks = E.words_from(transcripts, order)
    sents = E.sentences(words, restarts, breaks)
    if errs := E.validate_plan(plan, sents, words, brands):
        return {"errors": errs, "warnings": []}
    return check_words(plan, words, {s["id"]: s for s in sents})


def check_words(plan: dict, words: dict, by_id: dict, timing: bool = True) -> dict:
    """`check` for a plan that passed `validate_plan`, on the transcript's words and numbered sentences. With
    `timing` false it stops after the checks that don't depend on when anything plays (the build runs those first
    and measures the rest in the audio). `timed_errors`, in the full answer: the errors that came from the
    clock made of word times, which Whisper's stretched stamps can move by up to a couple of seconds on real
    footage; the build recomputes them from the audio with the same code, and its answer wins."""
    cut = cut_plan(plan, words, by_id)
    errors, warnings = list(cut["errors"]), no_pause_cuts(cut["story"], words)
    if errors or not timing:
        return {"errors": errors, "warnings": warnings}
    n_sure = len(errors)
    segs = cut["segs"]
    clock = word_clock(words, segs)
    times = compile_times(words, by_id, plan, segs, clock)
    errors += times["errors"]
    if errors:
        return {"errors": errors, "warnings": warnings, "timed_errors": errors[n_sure:]}
    beats, timed, cta_st = times["beats"], times["timed"], times["cta_st"]

    events: list[dict] = []
    spans: list[tuple[float, float]] = []
    for j, x in enumerate(timed):
        b = x["b"]
        dev = b.get("device")
        props = json.loads(json.dumps(b.get("props", {}))) if dev else {}
        _, cam = layer_camera(b, dev, props)
        if dev:
            resolve_cues(x, dev, props, words, by_id, errors)
        dur = fit_beat(x, dev, props, words, later_start(timed, j), cta_st, clock, errors)
        x["dur"] = dur
        if dev:
            for path, msg in overlay_schema.validate(dev, props, anchors=True):  # after the entrances are filled in
                errors.append(f"{x['label']}.props{'.' + path if path else ''}: {msg}")
            events.append({"type": dev, "start": x["st"], "duration": dur, "props": props})
            spans.append((x["st"], min(clock.total, x["st"] + dur)))
        if (cam if isinstance(cam, str) else (cam or {}).get("kind")) not in (None, "none"):
            spans.append((x["st"], x["st"] + dur))
    hook = plan.get("hook")
    if hook:
        d = hook_duration(segs[0]["_dur"], beats)
        events.insert(0, {"type": "HookTitle", "start": 0, "duration": d, "props": {"lines": [
            {"text": t, **({"emphasis": hook["emphasis"]} if hook.get("emphasis") and hook["emphasis"] in t else {})}
            for t in hook["title"]]}})
        spans.append((0, d))
    punch: set[int] = set()
    for x in beats:
        if x["b"].get("punch"):
            k = next(k for k, g in enumerate(segs) if g["take"] == x["s"]["take"] and g["a"] <= x["i"] <= g["b"])
            if k in punch:
                errors.append(f"{x['label']}: segment {k} already has a punch-in; one per cut")
            punch.add(k)
    low = plan.get("low")
    if low:
        low_seg = next(k for k, g in enumerate(segs) if g["low"])
        g = segs[low_seg]
        t0 = clock.out_t(g["take"], words[g["take"]][g["a"]]["start"])
        if t0 < E.LOW_FROM:
            errors.append(f"plan.low: the line starts at {t0:.1f} s, over the hook; the low moment comes after the first "
                          f"{E.LOW_FROM:g} s")
    cta = plan.get("cta")
    if cta:
        d = cta_duration(cta_st, timed)
        d = d if d is not None else clock.total - cta_st
        events.append({"type": "HandleCard", "start": cta_st, "duration": d,
                       "props": {"handle": cta["handle"], **({"kicker": cta["kicker"]} if cta.get("kicker") else {})}})
        spans.append((cta_st, cta_st + d))
    if errors:
        return {"errors": errors, "warnings": warnings, "timed_errors": errors[n_sure:]}

    errors += echo(events, caption_words(words, segs, clock, (plan.get("captions") or {}).get("fixes", {})))
    errors += shared_screen(events)
    pace = pacing(spans, clock.total)
    if pace.get("error"):
        errors.append(pace["error"])
    if pace.get("warning"):
        warnings.append(pace["warning"])
    return {"errors": errors, "warnings": warnings, "timed_errors": errors[n_sure:], "duration": round(clock.total, 2),
            "pacing": pace}
