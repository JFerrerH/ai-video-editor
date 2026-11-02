"""Prototype v2: compile a story plan (sentence IDs + what to show) into an engine short.json using only general
rules from short-form-pro SKILL.md and the brand kit. No rule may name a word, time, brand or project.

    uv run python compile_plan.py ids   footage/<p>                 # numbered transcript + visual candidates
    uv run python compile_plan.py build footage/<p> plan.json       # -> footage/<p>/edit/short.json, placed
Run from the engine repo root (needs tools/ on the path).
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ENGINE = Path.cwd()
sys.path.insert(0, str(ENGINE / "tools"))

SAFE_TOP, SAFE_SIDE, BAND_GAP = 300, 130, 30          # SKILL "Layout rules": nothing readable above 290; sides 130
CAPTION_TOP = 1170                                    # SKILL: caption band 1170–1300; graphics stay out of it
FLOAT_MIN, FLOAT_MAX, CUTAWAY_MAX = 2.0, 5.0, 3.0     # SKILL 5: cutaways ≤ 3 s; floating holds a thought
MIN_SCALE = 0.5                                       # the local edits floated cards at 0.52–0.7 above the head
SENT_GAP, RESTART_GAP, RESTART_WIN = 0.8, 0.3, 6.0    # sentence split on a long pause; restart signals
PRE, POST = 0.10, 0.12                                # SKILL gotcha: 100 ms pre-roll, 120 ms tail, nothing more
DEAD_AIR = 0.30                                       # a pause this long inside kept speech is cut (SKILL: cut dead air)
MIN_PIECE = 1.0                                       # never leave a piece shorter than this after a dead-air cut
BELOW_SPEECH = 25.0                                   # SKILL gotcha: silence = 25 dB under speech (breaths included)
GRAPHICS_PER_MIN, PHRASE_EVERY = 8.0, 6.0             # local exports: 8.5–14.9 graphics/min; SKILL 6: a key phrase ~4–5 s
# SKILL 7b vocabulary; first entry not rejected by the brand wins, alternatives rotate so it doesn't loop
SFX_FOR = {"HookTitle": ["pop"], "card": ["click", "tap"], "tracker": ["tick"], "scene": ["whoosh"],
           "stat": ["tick"], "chat": ["bubble"], "search": ["typing", "click"], "idea": ["sparkle"],
           "HandleCard": ["click"], "Flash": ["whoosh"], "phrase": ["click"], "big": ["sub"]}
GROUP = {"Receipt": "card", "DocumentCard": "card", "IdCard": "card", "Drawer": "card", "TopicCards": "card",
         "FrameworkCard": "card", "Milestones": "card", "SkillSlots": "tracker", "RingStat": "stat",
         "ProgressCard": "stat", "AgeBars": "stat", "RoomDots": "stat", "ListScene": "scene", "PostPile": "scene",
         "ChatThread": "chat", "SearchBar": "search"}


def norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return re.sub(r"[^\w]", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))


# ── transcript → numbered sentences ─────────────────────────────────────────
def load_words(proj: Path) -> dict[str, list[dict]]:
    out = {}
    for f in sorted((proj / "edit" / "transcripts").glob("*.json")):
        out[f.stem] = [w for w in json.loads(f.read_text())["words"] if w.get("type", "word") == "word" and w["text"].strip()]
    return out


def sentences(words: dict[str, list[dict]]) -> list[dict]:
    sents = []
    for take, ws in words.items():
        cur = []
        for i, w in enumerate(ws):
            cur.append(i)
            t = w["text"].strip()
            gap = ws[i + 1]["start"] - w["end"] if i + 1 < len(ws) else 99
            if re.search(r"[.?!]$", t) or t.endswith(("…", "...")) or gap >= SENT_GAP:
                sents.append({"take": take, "a": cur[0], "b": cur[-1]})
                cur = []
        if cur:
            sents.append({"take": take, "a": cur[0], "b": cur[-1]})
    for k, s in enumerate(sents):
        ws = words[s["take"]]
        s["id"] = f"F{k + 1}"
        s["start"], s["end"] = ws[s["a"]]["start"], ws[s["b"]]["end"]
        s["text"] = " ".join(ws[i]["text"].strip() for i in range(s["a"], s["b"] + 1))
    mark_restarts(sents, words)
    return sents


def mark_restarts(sents: list[dict], words: dict) -> None:
    """Abandoned end (ellipsis, or a ≥0.3 s pause without .?!) + the same opening bigram again within 6 s."""
    for k, s in enumerate(sents):
        ws = words[s["take"]]
        last = ws[s["b"]]["text"].strip()
        gap = ws[s["b"] + 1]["start"] - ws[s["b"]]["end"] if s["b"] + 1 < len(ws) else 0
        abandoned = last.endswith(("…", "...")) or (gap >= RESTART_GAP and not re.search(r"[.?!]$", last))
        if not abandoned or s["b"] - s["a"] < 1:
            continue
        head = [norm(ws[i]["text"]) for i in (s["a"], s["a"] + 1)]
        for t in sents[k + 1:]:
            if t["take"] != s["take"] or t["start"] - s["end"] > RESTART_WIN:
                break
            tw = words[t["take"]]
            if t["b"] > t["a"] and [norm(tw[i]["text"]) for i in (t["a"], t["a"] + 1)] == head:
                s["restart_of"] = t["id"]
                break


NUMBER_WORDS = {"uno", "dos", "tres", "cuatro", "cinco", "diez", "cien", "mil", "millon", "millones", "mitad",
                "one", "two", "three", "four", "five", "ten", "hundred", "thousand", "million", "half", "percent"}
ORDINALS = {"primero", "primera", "segundo", "segunda", "tercero", "tercera", "cuarto", "first", "second", "third",
            "fourth", "tips", "pasos", "habilidades", "steps", "things"}


def candidates(s: dict) -> list[str]:
    """Why a sentence is a natural place for a visual (SKILL 3: each concrete noun, number or claim)."""
    toks = [norm(t) for t in s["text"].split()]
    why = []
    if any(re.search(r"\d", t) for t in s["text"].split()) or NUMBER_WORDS & set(toks):
        why.append("number")
    if "$" in s["text"] or {"plata", "dinero", "pesos", "dolares", "money", "dollars"} & set(toks):
        why.append("money")
    if ORDINALS & set(toks):
        why.append("step")
    if s["text"].count(",") >= 2:
        why.append("series")
    if {"soy", "llamo", "im"} & set(toks[:6]):
        why.append("who")
    if s["text"].rstrip().endswith("?"):
        why.append("question")
    return why


def print_ids(proj: Path) -> None:
    for s in sentences(load_words(proj)):
        flag = f"  [false start: said again in {s['restart_of']}]" if s.get("restart_of") else ""
        cand = f"  <{', '.join(candidates(s))}>" if candidates(s) else ""
        print(f"{s['id']:>4} [{s['take']} {s['start']:.2f}–{s['end']:.2f}]{flag}{cand} {s['text']}")


# ── audio: where a cut can go ───────────────────────────────────────────────
_ENV: dict = {}
SRC: dict[str, Path] = {}


def env(take: str):
    if take not in _ENV:
        import numpy as np
        from audio_env import envelope
        db, floor = envelope(SRC[take])
        speech = float(np.percentile(db, 90))
        _ENV[take] = (db, max(floor + 9.0, speech - BELOW_SPEECH))  # breaths count as silence (runs ≥ 0.12 s, below)
    return _ENV[take]


def gap_between(take: str, ws: list[dict], i: int) -> tuple[float, float, float] | None:
    """The silence between word i and i+1, measured in the audio: (out_cut for i, in_cut for i+1, silence length).
    Cuts sit tight on the words (PRE/POST), so breaths and dead air go. None when the speech runs on."""
    db, thr = env(take)
    hop = 0.005
    if i < 0:
        w = ws[0]
        if w["start"] <= 0.05:
            return 0.0, 0.0, 0.0
        a, b = 0.0, w["start"] + 0.05
    else:
        # Whisper's stamps stretch words over the pauses around them, so the window spans from the core of word i
        # (its start plus the time its letters need) to the core of word i+1, and the audio decides
        pw = ws[i]
        a = pw["start"] + min(pw["end"] - pw["start"], 0.025 * len(norm(pw["text"])) + 0.02)
        if i + 1 < len(ws):
            w = ws[i + 1]
            b = max(a, w["end"] - min(w["end"] - w["start"], 0.025 * len(norm(w["text"])) + 0.02))
        else:
            b = min(pw["end"] + 1.0, len(db) * hop)
    lo, hi = int(a / hop), min(len(db), int(b / hop))
    quiet = [k for k in range(lo, hi) if db[k] < thr]
    raw, start = [], None
    for k in range(lo, hi + 1):
        q = k < hi and db[k] < thr
        if q and start is None:
            start = k
        elif not q and start is not None:
            raw.append([start * hop, k * hop])
            start = None
    merged = []  # room noise flickering over the threshold for < 50 ms isn't voice: join those pieces
    for r in raw:
        if merged and r[0] - merged[-1][1] <= 0.05:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    runs = [(a0, b0) for a0, b0 in merged if b0 - a0 >= 0.06]
    if not runs:
        return None
    qs, qe = max(runs, key=lambda r: r[1] - r[0])  # the longest quiet run is the pause; short dips are inside words
    # a run cut off by the window goes on while the audio stays quiet: Whisper's stamps, not the voice, set the window
    k = int(qe / hop)
    while abs(qe - b) < hop * 1.5 and k < min(len(db), int((b + 1.0) / hop)) and db[k:k + 10].min() < thr:
        k += 1
        qe = k * hop
    k = int(qs / hop) - 1
    while abs(qs - a) < hop * 1.5 and k > max(0, int((a - 1.0) / hop)) and db[max(0, k - 10):k + 1].min() < thr:
        qs = k * hop
        k -= 1
    out_cut, in_cut = min(qs + POST, qe), max(qe - PRE, qs)
    if out_cut > in_cut:
        out_cut = in_cut = round((qs + qe) / 2, 3)
    if i < 0:
        return in_cut, in_cut, qe - qs
    if i + 1 >= len(ws):
        return out_cut, out_cut, qe - qs
    return round(out_cut, 3), round(in_cut, 3), round(qe - qs, 3)


# ── plan → segments ─────────────────────────────────────────────────────────
def expand(ids: list[str], by_id: dict) -> list[dict]:
    out = []
    for item in ids:
        a, _, b = item.partition("-")
        out += [by_id[f"F{k}"] for k in range(int(a[1:]), int((b or a)[1:]) + 1)]
    return out


def build_segments(story: list[dict], words: dict, force: set = frozenset()) -> list[dict]:
    for s in story:
        if s.get("restart_of"):
            raise SystemExit(f"{s['id']} is a false start (said again in {s['restart_of']}): keep {s['restart_of']}")
    # runs of kept words, per take, in story order
    runs: list[dict] = []
    for s in story:
        last = runs[-1] if runs else None
        if last and last["take"] == s["take"] and last["b"] + 1 == s["a"]:
            last["b"], last["ids"] = s["b"], last["ids"] + [s["id"]]
        else:
            runs.append({"take": s["take"], "a": s["a"], "b": s["b"], "ids": [s["id"]]})
    segs = []
    for r in runs:
        ws = words[r["take"]]
        head = gap_between(r["take"], ws, r["a"] - 1)
        tail = gap_between(r["take"], ws, r["b"])
        if head is None or tail is None:
            which = f"before \"{ws[r['a']]['text'].strip()}\"" if head is None else f"after \"{ws[r['b']]['text'].strip()}\""
            raise SystemExit(f"{r['ids'][0]}–{r['ids'][-1]}: the speech runs on {which} with no pause, so it can't be "
                             f"cut cleanly there; keep the neighbouring sentence too, or start/end at another sentence")
        start, a = head[1], r["a"]
        for i in range(r["a"], r["b"]):  # dead air inside kept speech is cut out (jump cut, nothing said is dropped)
            g = gap_between(r["take"], ws, i)
            if g and g[1] - g[0] >= 0.08 and (g[2] >= DEAD_AIR or (r["take"], i) in force) and g[0] - start >= MIN_PIECE * (0.5 if (r["take"], i) in force else 1) \
                    and tail[0] - g[1] >= MIN_PIECE * (0.5 if (r["take"], i) in force else 1):
                segs.append({"take": r["take"], "in": start, "out": g[0], "_a": a, "_b": i})
                start, a = g[1], i + 1
        segs.append({"take": r["take"], "in": start, "out": tail[0], "_a": a, "_b": r["b"]})
    for g in segs:
        # the edges were measured against the voice level (breaths are cut); the engine still measures against the room
        # floor and would widen them back into the breath, so they're held (engine fix: edge loudness relative to speech)
        g["lock_in"] = g["lock_out"] = True
    return segs


def set_zooms(segs: list[dict], words: dict, punch_at: dict[int, dict]) -> None:
    """SKILL 2: punch-in on emphasis words; jump cuts change zoom; never hold the same frame > ~4 s."""
    prev = None
    for k, g in enumerate(segs):
        if k in punch_at:
            w = punch_at[k]
            g["zoom"] = {"kind": "punch", "base": 1.0, "peak": 1.12,
                         "at": {"word": w["text"].strip(), "after": round(max(0.0, w["start"] - 0.01), 2)}}
        elif g["out"] - g["in"] > 4.0 or prev == "static":
            g["zoom"] = {"kind": "push", "from": 1.0, "to": 1.06}
        else:
            g["zoom"] = {"kind": "static", "scale": 1.08 if prev != "static" else 1.0}
        prev = g["zoom"]["kind"]


def out_time(segs: list[dict], take: str, t: float) -> float | None:
    """Output time of source time t; a word stamped up to 0.4 s before an in-point (Whisper starts words early,
    SKILL gotcha) maps to that segment's start, as the engine's p.at() does."""
    acc = 0.0
    for g in segs:
        if g["take"] == take and g["in"] - 0.4 <= t < g["in"] - 0.02:
            return acc
        acc += g["out"] - g["in"]
    acc = 0.0
    for g in segs:
        if g["take"] == take and g["in"] - 0.02 <= t <= g["out"] + 0.02:
            return acc + max(0.0, t - g["in"])
        acc += g["out"] - g["in"]
    return None


def word_out(segs: list[dict], take: str, w: dict) -> float | None:
    """Output time of a word that overlaps a kept segment (its stamped start may sit before the measured cut)."""
    acc = 0.0
    for g in segs:
        if g["take"] == take and w["end"] > g["in"] and w["start"] < g["out"]:
            return acc + max(0.0, w["start"] - g["in"])
        acc += g["out"] - g["in"]
    return None


def seg_of(segs: list[dict], take: str, t: float) -> int | None:
    for k, g in enumerate(segs):
        if g["take"] == take and g["in"] - 0.4 <= t <= g["out"] + 0.02:
            return k
    return None


def find_word(words: dict, sent: dict, word: str | None) -> dict:
    ws = words[sent["take"]]
    if word:
        for i in range(sent["a"], sent["b"] + 1):
            if norm(ws[i]["text"]) == norm(word):
                return ws[i]
        raise SystemExit(f"word {word!r} not in {sent['id']}")
    return ws[sent["a"]]


# ── colours and brand ───────────────────────────────────────────────────────
def lum(hexc: str) -> float:
    h = hexc.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def money(v, locale: str) -> str:
    if not isinstance(v, (int, float)):
        return str(v)
    s = f"{abs(v):,.0f}"
    return ("-" if v < 0 else "") + "$" + (s.replace(",", ".") if locale.startswith("es") else s)


def rejected_sfx(brand_slug: str) -> set[str]:
    """Every SFX name the brand kit's notes reject ("Rejected before", "never", "don't"): a hard constraint."""
    from sfx_synth import EFFECTS as SOUNDS
    md = ENGINE / "brands" / brand_slug / "brand.md"
    if not md.exists():
        return set()
    out = set()
    for line in md.read_text().splitlines():
        whole = re.search(r"rejected", line, re.I)  # a "Rejected before" line bans every sound it names…
        for clause in re.split(r"[.;]", line):
            if not (whole or re.search(r"never|don't|nunca", clause, re.I)):
                continue
            banned_part = re.split(r"\b(?:use|usar|instead|en su lugar)\b", clause, flags=re.I)[0]  # …except "use Y"
            out |= {n for n in SOUNDS if re.search(rf"`{n}`|\b{n}\b", banned_part)}
    return out


# ── graphics ────────────────────────────────────────────────────────────────
def graphic(item: dict, col: dict, locale: str) -> tuple[str, dict, bool]:
    """(type, props, full) for one `show` beat. Component per SKILL 3 and the components table."""
    accent = col.get("accent", "#000000")
    accent_ok = contrast(accent, "#FFFFFF") >= 3.0
    accent_on_bg = contrast(accent, col.get("bg", "#FFFFFF")) >= 3.0
    at = lambda j, step=0.35, first=0.3: round(first + step * j, 2)  # noqa: E731
    k = item["kind"]
    if k == "amount":
        props = {"title": item.get("title", "").upper() or " ", "enterFrom": "above",
                 "items": [{"text": it["text"], "amount": money(it.get("amount", ""), locale), "at": at(j)}
                           for j, it in enumerate(item.get("items", []))], "total": money(item["value"], locale)}
        if item.get("stamp") and accent_ok:
            props["stamp"], props["stampAt"] = item["stamp"], at(len(props["items"]), first=0.6)
        return "Receipt", props, False
    if k == "list":
        dark = not accent_on_bg and contrast(accent, col.get("ink", "#000000")) >= 3.0
        return "ListScene", {"title": item.get("title", ""), **({"kicker": item["kicker"]} if item.get("kicker") else {}),
                             **({"bg": "dark", "dark": True} if dark else {}),
                             "items": [{"text": t, "at": at(j, 0.45)} for j, t in enumerate(item["items"])],
                             "marker": "number" if item.get("numbered") else "check", "full": True}, True
    if k in ("step", "doc", "quote"):
        return "DocumentCard", {"kicker": item.get("kicker", ""), "title": item["title"],
                                **({"year": str(item["year"])} if item.get("year") else {}),
                                **({"author": item["author"]} if item.get("author") else {}), "enterFrom": "above"}, False
    if k == "topics":
        if long := [c["title"] for c in item["cards"] if len(c["title"]) > 14]:
            raise SystemExit(f"topic cards hold ≤ 14 characters per title ({', '.join(map(repr, long))}): shorten them or use kind \"list\"")
        return "TopicCards", {"cards": [{"icon": c.get("icon", "check"), "kicker": c.get("kicker", ""), "title": c["title"],
                                         "at": at(j, 0.5, 0.2)} for j, c in enumerate(item["cards"])]}, False
    if k == "percent":
        return "RingStat", {"value": item["value"], **({"label": item["label"]} if item.get("label") else {})}, False
    if k == "progress":
        return "ProgressCard", {"label": item["label"], "to": item["value"], **({"note": item["note"]} if item.get("note") else {}),
                                **({"stall": True} if item.get("stall") else {})}, False
    if k == "bars":
        return "AgeBars", {"bars": [{"value": b["value"], "label": b["label"], "at": at(j, 0.3),
                                     **({"highlight": True} if b.get("highlight") and accent_ok else {})}
                                    for j, b in enumerate(item["bars"])],
                           **({"caption": item["caption"]} if item.get("caption") else {})}, False
    if k == "who":
        return "IdCard", {"title": item["title"], **({"kicker": item["kicker"]} if item.get("kicker") else {}),
                          **({"subtitle": item["subtitle"]} if item.get("subtitle") else {}),
                          "rows": [{"icon": r.get("icon", "dot"), "text": r["text"], "at": at(j, 0.4, 0.5)}
                                   for j, r in enumerate(item.get("rows", []))]}, False
    if k == "shelved":
        return "Drawer", {"docTitle": item["title"], "closeAt": 1.2}, False
    if k == "milestones":
        return "Milestones", {"items": [{"icon": m.get("icon", "star"), "label": m.get("label", ""), "at": at(j, 0.4)}
                                        for j, m in enumerate(item["items"])]}, False
    if k == "chat":
        return "ChatThread", {"floating": True, "messages": [{"from": m["from"], "at": at(j, 0.6, 0.2),
                                                              **({"icon": m["icon"]} if m.get("icon") else {})}
                                                             for j, m in enumerate(item["messages"])]}, False
    if k == "search":
        return "SearchBar", {"query": item["query"], "typeEnd": 1.0, "resultsAt": 1.3}, False
    if k == "room":
        return "RoomDots", {"count": item.get("count", 7), "highlight": item.get("highlight", 3), "highlightAt": 0.8}, False
    if k == "phone":  # the product itself, SKILL 3 first choice: real screens, a full montage ≤ 7 s
        return "PhoneMockup", {"variant": "center", "full": True,
                               "screens": [{"src": src, "at": round(j * 1.2, 2)} for j, src in enumerate(item["screens"])]}, True
    if k == "photos":  # people in the story, with permission (SKILL 3)
        return "Polaroids", {"photos": [{"src": ph["src"], "label": ph.get("label", ""), "at": at(j, 0.5, 0.25),
                                         "rotate": (-4, 5, -2, 3)[j % 4]} for j, ph in enumerate(item["photos"])]}, False
    if k == "stat":  # a big number counting up, full screen
        shown = (item.get("prefix", "") + f"{item['value']:,}" + item.get("suffix", ""))
        size = max(90, min(220, int(1080 * 0.8 / (0.6 * len(shown)))))  # the number fits 80 % of the width
        return "StatScene", {"value": item["value"], "size": size, **({"prefix": item["prefix"]} if item.get("prefix") else {}),
                             **({"suffix": item["suffix"]} if item.get("suffix") else {}), "locale": locale,
                             **({"label": item.get("label") or item.get("title")} if item.get("label") or item.get("title") else {}),
                             **({"kicker": item["kicker"]} if item.get("kicker") else {}),
                             **({"bg": "dark", "dark": True} if not accent_on_bg else {}), "full": True}, True
    if k == "statement":  # the line as big kinetic type, full screen
        lines = item.get("lines") or [item.get("title") or item.get("text")]
        return "KineticType", {"lines": [{"text": t, "at": at(j, 0.4, 0.15)} for j, t in enumerate(lines)],
                               **({"bg": "dark", "dark": True} if item.get("dark") else {}), "full": True}, True
    if k == "punch":  # a big serif punch line tucked behind the speaker's head (SKILL components: NameTitle behind)
        text = item.get("text") or item.get("title")
        fit = int(1080 * 0.8 / (0.5 * max(len(text), 1)))  # a serif glyph is ~0.5 em wide: the line fits 80 % of the width
        return "NameTitle", {"text": text, "behind": True, "size": max(70, min(150, fit)),
                             "top": 470, **({"color": col["accent"]} if col.get("accent") and contrast(col["accent"], "#000000") > 7 else {})}, False
    if k == "building":  # building / hustle montage: a code editor, dark, full screen
        return "CodeEditor", {"file": item.get("file", "app.ts"), "lines": item.get("lines") or ["build()", "ship()"],
                              "full": True, "dark": True}, True
    if k == "signup":
        return "Waitlist", {"title": item.get("title", "Lista de espera"), "placeholder": item.get("placeholder", "tu@correo.com"),
                            "email": item.get("email", "ana@correo.com"), "button": item.get("button", "Unirme"),
                            "success": item.get("success", "¡Listo!"), "typeStart": 0.3, "typeEnd": 1.2, "submitAt": 1.5}, False
    if k == "chart":
        return "BarChart", {"title": item.get("title", ""), "bars": [{"label": b["label"], "value": b["value"],
                                                                      **({"highlight": True} if b.get("highlight") else {})}
                                                                     for b in item["bars"]],
                            **({"bg": "dark", "dark": True} if not accent_on_bg else {}), "full": True}, True
    if k == "pile":
        return "PostPile", {"count": item.get("count", 24), "pileStart": 0.2, "pileEnd": 1.6, "full": True}, True
    raise SystemExit(f"unknown show kind {k!r}")


# what a beat means → the components that show it, in order of preference (SKILL 3 + the components table)
MEANS = {"money": ["amount", "stat"], "number": ["stat", "chart", "percent"], "percent": ["percent", "progress", "stat"],
         "punchline": ["punch", "statement"], "statement": ["statement", "punch"], "year": ["doc", "statement"],
         "idea": ["doc", "statement"], "gave_up": ["shelved"], "building": ["building"], "product": ["phone"],
         "people": ["photos"], "who": ["who", "punch"], "list": ["list", "topics"], "only_one": ["room"],
         "too_much": ["pile"], "ask_ai": ["chat"], "search": ["search"], "not_ready": ["progress"],
         "comparison": ["bars", "chart"], "life_steps": ["milestones"], "signup": ["signup"]}
FAMILY = {"Receipt": "card", "DocumentCard": "card", "IdCard": "card", "TopicCards": "card", "ProgressCard": "card",
          "Milestones": "card", "FrameworkCard": "card", "Drawer": "object", "CodeEditor": "full", "PhoneMockup": "full",
          "ListScene": "full", "StatScene": "full", "BarChart": "full", "PostPile": "full", "KineticType": "type",
          "NameTitle": "type", "Polaroids": "photo", "RingStat": "stat", "AgeBars": "stat", "RoomDots": "stat",
          "ChatThread": "ui", "SearchBar": "ui", "Waitlist": "ui"}
CARD_WORDS = 5   # a card title is read at a glance
LOW_WORDS = {"cajon", "costoso", "caro", "tarde", "miedo", "panico", "susto", "desastre", "perdi", "perdon", "nadie",
             "fracaso", "dificil", "imposible", "solo", "sola", "guardarla", "guardar", "nunca", "lost", "afraid",
             "late", "failed", "impossible", "expensive", "alone", "drawer"}


def low_candidates(story: list[dict]) -> list[str]:
    return [s["id"] for s in story if LOW_WORDS & {norm(t) for t in s["text"].split()}]


def build(proj: Path, plan: dict) -> dict:
    words = load_words(proj)
    sents = sentences(words)
    by_id = {s["id"]: s for s in sents}
    slug = plan.get("brand", "none")
    brand = json.loads((ENGINE / "brands" / slug / "brand.json").read_text()) if slug != "none" else {}
    col = brand.get("colors", {})
    locale = plan.get("locale", "es-ES")
    conform_f = proj / "edit" / "conformed" / "conform.json"
    conform = json.loads(conform_f.read_text()) if conform_f.exists() else {}
    for take in words:
        info = conform.get("takes", {}).get(take)
        SRC[take] = proj / (info["output"] if info and info.get("as_is") else f"edit/conformed/{take}.mov")
    story = expand(plan["story"], by_id)
    force = set()  # the low moment is applied on output times after render (post.py), no forced cuts needed
    segs = build_segments(story, words, force)

    # key phrases (SKILL 6) and the segment each punches in on (SKILL 2)
    kept = {(g["take"], i) for g in segs for i in range(g["_a"], g["_b"] + 1)}
    emphasis, punch_at, phrase_words = [], {}, []
    for ph in plan.get("punch", []):
        toks = [norm(t) for t in ph.split()]
        for take, ws in words.items():
            hit = next((i for i in range(len(ws) - len(toks) + 1)
                        if [norm(ws[i + j]["text"]) for j in range(len(toks))] == toks and (take, i) in kept), None)
            if hit is not None:
                emphasis.append({"take": take, "phrase": ph, "after": round(ws[hit]["start"] - 0.01, 2)})
                if ph in plan.get("big", [])[:2]:  # docs/editing-references.md rule 2: zero to two punch-ins
                    k = seg_of(segs, take, ws[hit]["start"])
                    if k is not None and k not in punch_at:
                        punch_at[k] = ws[hit]
                    phrase_words.append((take, ws[hit]))
                break
        else:
            raise SystemExit(f"punch phrase {ph!r} not in the kept words")
    if 0 not in punch_at:  # the hook always punches in
        g0 = segs[0]
        punch_at[0] = words[g0["take"]][(g0["_a"] + g0["_b"]) // 2]
    set_zooms(segs, words, punch_at)
    total = sum(g["out"] - g["in"] for g in segs)

    def anchor(sent: dict, word: str | None = None) -> tuple[dict, float]:
        w = find_word(words, sent, word)
        st = word_out(segs, sent["take"], w)
        if st is None:
            raise SystemExit(f"{sent['id']} isn't in the story")
        for k, g in enumerate(segs):  # a word stamped well before the measured cut: anchor to the segment's start
            if g["take"] == sent["take"] and w["end"] > g["in"] and w["start"] < g["in"] - 0.35:
                return {"seg": k, "edge": "start"}, st
        return {"word": w["text"].strip(), "take": sent["take"], "after": round(max(0.0, w["start"] - 0.01), 2)}, st

    def sent_end(sent: dict) -> float:
        return out_time(segs, sent["take"], words[sent["take"]][sent["b"]]["end"]) or total

    events = []
    hook = plan.get("hook")
    if hook:
        lines = [{"text": t, **({"emphasis": hook["emphasis"]} if hook.get("emphasis") and hook["emphasis"] in t else {})}
                 for t in hook["title"]]
        events.append({"type": "HookTitle", "start": 0, "duration": round(min(3.0, max(2.0, segs[0]["out"] - segs[0]["in"])), 2),
                       "props": {"lines": lines}, "_st": 0.0})
    # structure: a "N steps" video gets a tracker at the intro, at each step, and as the recap (SKILL components)
    steps = plan.get("steps")
    if steps:
        icons = steps["icons"]
        if steps.get("intro"):
            a, st = anchor(by_id[steps["intro"]["at"]], steps["intro"].get("word"))
            events.append({"type": "SkillSlots", "start": a, "duration": 2.4, "props": {"slots": [{"icon": i} for i in icons]}, "_st": st})
        for j, sid in enumerate(steps["at"]):
            a, st = anchor(by_id[sid])
            slots = [{"icon": ic, "at": (0.2 if n == j else 0)} for n, ic in enumerate(icons[:j + 1])] + [{"icon": ic} for ic in icons[j + 1:]]
            events.append({"type": "SkillSlots", "start": a, "duration": 2.2, "props": {"slots": slots, "active": j}, "_st": st})
        if steps.get("recap"):
            a, st = anchor(by_id[steps["recap"]["at"]], steps["recap"].get("word"))
            events.append({"type": "SkillSlots", "start": a, "duration": 2.6, "props": {"slots": [{"icon": i, "at": 0} for i in icons]}, "_st": st})
    prev_family = None
    for item in sorted(plan.get("show", []), key=lambda i: int(i["at"][1:])):
        sent = by_id[item["at"]]
        a, st = anchor(sent, item.get("word"))
        options = MEANS.get(item.get("means"), []) if item.get("means") else [item["kind"]]
        if not options:
            raise SystemExit(f"show at {item['at']}: unknown meaning {item.get('means')!r}; one of {', '.join(sorted(MEANS))}")
        built = []
        for kind in options:
            try:
                built.append(graphic({**item, "kind": kind}, col, locale))
            except (KeyError, TypeError, ValueError):
                continue  # this component needs content the beat doesn't give
        if not built:
            raise SystemExit(f"show at {item['at']} ({item.get('means') or item['kind']}): missing content for {', '.join(options)}")
        typ, props, full = next((b for b in built if FAMILY.get(b[0]) != prev_family), built[0])  # never the same look twice in a row
        if FAMILY.get(typ) == "card" and len(str(props.get("title", "")).split()) > CARD_WORDS:
            raise SystemExit(f"show at {item['at']}: card title {props['title']!r} has more than {CARD_WORDS} words; cut it to read at a glance")
        prev_family = FAMILY.get(typ, typ)
        end = sent_end(by_id[item.get("until", item["at"])]) + 0.3
        need = {"Waitlist": 3.0, "PhoneMockup": 3.0, "CodeEditor": 2.5, "Drawer": 2.0}.get(typ, FLOAT_MIN)  # its animation
        dur = min(max(end - st, need), (7.0 if typ == "PhoneMockup" else CUTAWAY_MAX) if full else FLOAT_MAX)
        hold_to = sent_end(by_id[item.get("until", item["at"])])
        nxt_sent = next((x for x in story if int(x["id"][1:]) > int(item.get("until", item["at"])[1:])), None)
        if nxt_sent and not item.get("until"):  # the thought may run into the next sentence, never past it
            hold_to = sent_end(nxt_sent)
        events.append({"type": typ, "start": a, "duration": round(dur, 2), "props": props, "_st": st, "_idea": item.get("idea"),
                       "_hold": hold_to})
    # the emotional arc (SKILL 4): bw only on the low line, a Flash on the turn
    arc = plan.get("arc")  # optional: a creative choice, never required (the user, 2026-11-02)
    arc = arc if isinstance(arc, dict) else {}
    post = {}
    if arc.get("low"):  # docs/editing-references.md rule 1: one short line, ~1.5–2.5 s, static frame, muffled voice
        lo = arc["low"]
        s0 = by_id[lo["at"]]
        ws0 = words[s0["take"]]
        toks = [norm(t) for t in lo["words"].split()]
        hit = next((i for i in range(s0["a"], s0["b"] - len(toks) + 2)
                    if [norm(ws0[i + j]["text"]) for j in range(len(toks))] == toks), None)
        if hit is None:
            raise SystemExit(f"arc.low words {lo['words']!r} aren't in {lo['at']}")
        t0 = word_out(segs, s0["take"], ws0[hit])
        t1 = word_out(segs, s0["take"], ws0[hit + len(toks) - 1])
        t1 = t1 + (ws0[hit + len(toks) - 1]["end"] - ws0[hit + len(toks) - 1]["start"]) + 0.08 if t1 is not None else None
        if t0 is None or t1 is None:
            raise SystemExit(f"arc.low words {lo['words']!r} aren't in the cut")
        if not 1.0 <= t1 - t0 <= 3.0:
            raise SystemExit(f"arc.low lasts {t1 - t0:.1f} s; the low moment is one short line, 1–3 s: pick fewer words")
        if t0 < 3.0:
            raise SystemExit("arc.low falls in the first 3 s, over the hook: the low moment comes later in the story")
        post = {"low": {"start": round(t0, 3), "end": round(t1, 3), "freeze": 0.4}}
        k = seg_of(segs, s0["take"], ws0[hit]["start"])
        if k is not None:
            punch_at.pop(k, None)
            segs[k]["zoom"] = {"kind": "static", "scale": 1.0}  # the low line holds still
    if arc.get("turn"):
        a, st = anchor(by_id[arc["turn"]])
        events.append({"type": "Flash", "start": a, "duration": 0.4, "props": {}, "_st": st})
    cta = plan.get("cta")
    if cta:
        a, st = anchor(by_id[cta["at"]], cta.get("word"))
        events.append({"type": "HandleCard", "start": a, "end": {"seg": len(segs) - 1, "edge": "end"},
                       "props": {"handle": cta["handle"], **({"kicker": cta["kicker"]} if cta.get("kicker") else {})}, "_st": st})
    # one floating graphic at a time: trim each to the next one's start
    timed = sorted([e for e in events if e["type"] not in ("Flash",)], key=lambda e: e["_st"])
    for x, y in zip(timed, timed[1:]):
        if "duration" in x:
            x["duration"] = round(max(1.2, min(x["duration"], y["_st"] - x["_st"] - 0.1)), 2)

    # coverage: a floating graphic stays until the next one starts or 6 s (local edits: 57–73 % of the time covered)
    timed = sorted([e for e in events if e["type"] not in ("Flash",) and "duration" in e], key=lambda e: e["_st"])
    for x, y in zip(timed, timed[1:] + [None]):
        if x["props"].get("full") or x["type"] == "HookTitle":
            continue
        nxt = y["_st"] if y else total
        x["duration"] = round(max(x["duration"], min(nxt - x["_st"] - 0.15, x.get("_hold", 0) - x["_st"], 6.0)), 2)
    # inner cues (list items, messages, rows) must have entered before a trimmed event ends: compress them
    for e in events:
        d = e.get("duration")
        ats = []
        def walk(o):
            if isinstance(o, dict):
                for k2, v in o.items():
                    if k2 in ("at", "closeAt", "resultsAt", "typeStart", "typeEnd", "submitAt", "highlightAt", "stampAt") and isinstance(v, (int, float)):
                        ats.append((o, k2))
                    else:
                        walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(e["props"])
        if d and ats:
            last = max(o[k2] for o, k2 in ats)
            if last > d - 0.6:
                f = max(0.0, d - 0.6) / last
                for o, k2 in ats:
                    o[k2] = round(o[k2] * f, 2)
    # docs/editing-references.md rule 3: a visual change about every 5 s by any means (a cut, a graphic, a flash)
    changes, acc = [0.0], 0.0
    for g in segs[:-1]:
        acc += g["out"] - g["in"]
        changes.append(acc)
    changes += [e["_st"] for e in events] + [e["_st"] + e.get("duration", 0) for e in events if e.get("duration")]
    changes = sorted(set(round(c, 2) for c in changes if c <= total)) + [total]
    gaps = [(b - a, a) for a, b in zip(changes, changes[1:]) if b - a > 8.0]
    if gaps:
        raise SystemExit("nothing changes on screen for " + "; ".join(f"{d:.1f} s from {a:.1f} s" for d, a in gaps)
                         + ": show something there (a graphic for what's said), or cut tighter")
    # SFX: one per graphic entrance, vocabulary from SKILL 7b, minus whatever the brand rejected; ≥ 0.3 s apart
    banned = rejected_sfx(slug) | {"pluck"}  # user rejects pluck everywhere (feedback memory)
    turn = {}

    def pick(group: str) -> str | None:
        opts = [n for n in SFX_FOR[group] if n not in banned]
        if not opts:
            return None
        turn[group] = turn.get(group, -1) + 1
        return opts[turn[group] % len(opts)]

    sfx, times = [], []
    for e in sorted(events, key=lambda e: e["_st"]):
        if e["type"] == "HookTitle":
            group = "HookTitle"
        elif e["type"] in ("Flash",) or e["props"].get("full"):
            group = "scene"           # a cut to full screen or the turn: one whoosh
        elif e["type"] in ("HandleCard", "SkillSlots", "Waitlist"):
            group = GROUP.get(e["type"], e["type"]) if e["type"] != "HandleCard" else "HandleCard"
        else:
            continue                  # floating cards land silently
        name = pick(group) if group in SFX_FOR else None
        if name and all(abs(e["_st"] - t) >= 1.0 for t in times):
            gain = {"whoosh": -14, "sub": -22, "tick": -18}.get(name, -16)
            sfx.append({"name": name, "at": 0.06 if e["start"] == 0 else e["start"], "gain_db": gain})
            times.append(e["_st"])
    if phrase_words and (name := pick("big")):  # one soft sub under the biggest line
        take, w = phrase_words[0]
        sfx.append({"name": name, "at": {"word": w["text"].strip(), "take": take, "after": round(max(0.0, w["start"] - 0.01), 2)}, "gain_db": -22})

    for e in events:
        e.pop("_st", None)
        e.pop("_idea", None)
        e.pop("_hold", None)
    for g in segs:
        g["note"] = f"{g.pop('_a')}-{g.pop('_b')}"
    return {"version": 1, "brand": slug, "sources": {t: {"file": str(SRC[t].relative_to(proj))} for t in sorted({g["take"] for g in segs})},
            "segments": segs, "events": events, "emphasis": emphasis, "sfx": sfx, "public_files": plan.get("assets", {}), "_post": post}


# ── placement above the head (SKILL 4b + layout rules) ──────────────────────
def faces(proj: Path, spec: dict) -> dict:
    cache = proj / "edit" / "xp_face.json"
    known = json.loads(cache.read_text()) if cache.exists() else {}
    from face_centre import suggest
    for take, src in spec["sources"].items():
        if take not in known:
            known[take] = suggest(proj / src["file"])["face"]
    cache.write_text(json.dumps(known))
    return known


def head_top_out(face: list[int], z: float) -> float:
    """Head top from the face step's own definition (face y = top + 15 % of person height, person to the bottom),
    then through the segment's crop at zoom z (shortform crops around the face, clamped to the frame)."""
    cx, cy = face
    top = (cy - 0.15 * 1920) / 0.85
    ch = 1920 / z
    y0 = max(0, min(1920 - ch, cy - ch / 2))
    return (top - y0) * z


def place(proj: Path) -> list[str]:
    from short_spec import load
    notes = []
    spec_path = proj / "edit" / "short.json"
    spec = json.loads(spec_path.read_text())
    fc = faces(proj, spec)
    for take, f in fc.items():
        if take in spec["sources"]:
            spec["sources"][take]["face"] = f
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    p, _ = load(spec_path)
    offs = p.offsets()
    pub, _ = p.stage_overlay()
    tmp = p.edit_dir / "stills" / "_xp"
    tmp.mkdir(parents=True, exist_ok=True)
    floating = {i for i, e in enumerate(spec["events"]) if not e["props"].get("full") and e["type"] != "Flash"}
    for k, e in enumerate(p.events):
        idx = e.get("index", k)
        if e["type"] == "Captions" or idx not in floating:
            continue
        t = p._still_time(e)
        png = tmp / f"e{idx}.png"
        p._still(p._props_file([{**e, "props": {**e["props"], "frame": {"scale": 1, "y": 0}}}], tmp / f"e{idx}.json"), t, png, 0.5, pub)
        img = p._rgba(png)
        ys, xs = (img[:, :, 3] > 8).nonzero()
        if not len(ys):
            notes.append(f"events[{idx}] {e['type']}: drew nothing")
            continue
        f = 1080 / img.shape[1]
        x0, y0, x1, y1 = xs.min() * f, ys.min() * f, (xs.max() + 1) * f, (ys.max() + 1) * f
        s0, s1 = e["start"], e["start"] + e["duration"]
        tops = []
        for j, seg in enumerate(spec["segments"]):
            if offs[j] < s1 and offs[j + 1] > s0:
                z = seg["zoom"]
                zmax = {"static": z.get("scale", 1.0), "push": max(z.get("from", 1.0), z.get("to", 1.0)),
                        "punch": z.get("peak", 1.0)}.get(z["kind"], 1.0)
                tops.append(head_top_out(fc[seg["take"]], zmax))
        limit = min(tops or [680]) - BAND_GAP
        sc = min(1.0, (limit - SAFE_TOP) / (y1 - y0), (1080 - 2 * SAFE_SIDE) / (x1 - x0))
        if sc < MIN_SCALE and e["type"] == "HookTitle":
            raise SystemExit("the hook title doesn't fit above the speaker's head in this framing (it would need scale "
                             f"{sc:.2f}): drop the hook title and make the hook a punch phrase, or use fewer words")
        if sc < MIN_SCALE:
            fs = min(1.4, (CAPTION_TOP - 20 - SAFE_TOP) / (y1 - y0), (1080 - 2 * SAFE_SIDE) / (x1 - x0))
            ev = spec["events"][idx]
            ev["props"]["full"] = True
            ev["props"]["frame"] = {"scale": round(fs, 3), "x": round(-((x0 + x1) / 2 - 540) * fs),
                                    "y": round((SAFE_TOP + CAPTION_TOP - 20) / 2 - (y0 + y1) / 2 * fs)}
            if "duration" in ev:
                ev["duration"] = min(ev["duration"], CUTAWAY_MAX)
            notes.append(f"events[{idx}] {e['type']}: needs scale {sc:.2f} above the head → full screen at {fs:.2f}")
            continue
        spec["events"][idx]["props"]["frame"] = {"scale": round(sc, 3), "x": round(-((x0 + x1) / 2 - 540) * sc),
                                                 "y": round(SAFE_TOP - y0 * sc)}
        notes.append(f"events[{idx}] {e['type']}: scale {sc:.2f}, {SAFE_TOP}–{SAFE_TOP + (y1 - y0) * sc:.0f} (head {limit:.0f})")
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    return notes


if __name__ == "__main__":
    cmd, proj = sys.argv[1], Path(sys.argv[2])
    if cmd == "ids":
        print_ids(proj)
    elif cmd == "build":
        spec = build(proj, json.loads(Path(sys.argv[3]).read_text()))
        (proj / "edit" / "xp_post.json").write_text(json.dumps(spec.pop("_post")))
        (proj / "edit" / "short.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1))
        print("\n".join(place(proj)))
