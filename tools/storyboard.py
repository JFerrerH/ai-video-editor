"""Videos from scratch: `edit/storyboard.json` → Remotion `Story` → audio mix → MP4.

    uv run tools/storyboard.py footage/<project>/edit check              # timeline + craft warnings
    uv run tools/storyboard.py footage/<project>/edit voice              # narration clips + word times (needs `uv sync --group gen`)
    uv run tools/storyboard.py footage/<project>/edit sheet poses        # reference sheet: figure poses (or `widgets [--aspect A]`)
    uv run tools/storyboard.py footage/<project>/edit stills             # contact sheet → edit/stills/contact.png
    uv run tools/storyboard.py footage/<project>/edit stills --at 1.2,4  # specific times (s)
    uv run tools/storyboard.py footage/<project>/edit render --preview   # 720p → edit/preview.mp4
    uv run tools/storyboard.py footage/<project>/edit render             # full res → edit/final.mp4
    uv run tools/storyboard.py footage/<project>/edit render --export reels   # + exports/<project>_reels_<date>.mp4

storyboard.json (see templates/storyboard.json, templates/storyboard_explainer.json and the
motion-graphics skill):
    {"aspect": "9:16"|"16:9"|"1:1"|"4:5", "fps": 30, "brand": "<slug>"|"none", "grain": 0.4,
     "voice": {"lang": "en", "preset": "af_heart", "speed": 1.0,        # optional: narrate the scenes
               "pronounce": {"SaaS": "sass"}},                          # respellings sent to TTS only
     "progress": true,                                                  # thin progress bar on top
     "scenes": [{"name", "type", "duration": 3.0|"auto", "bg", "transition": {"type", "duration", "direction"},
                 "props": {...}, "narration": "spoken line, *emphasis*, | break",
                 "narration_audio": "audio/take.wav",   # a recorded clip instead of the synthesised one
                 "tail": 0.3, "speed": 1.1,             # per scene: silence after the clip, TTS speed
                 "sfx": [["whoosh", 0.0, -18]]}],
     "events": [{"type", "start", "duration", "props"}],          # global overlays (Flash, Captions…)
     "audio": {"voice": "audio/vo.wav", "voice_start": 0.0,
               "music": {"file": "assets/music/…", "db": -18, "duck": true},
               "sfx": [["click", 4.2, -16]]},                      # absolute times (s)
     "lufs": -14}
Scene `sfx` times are relative to the scene start. Asset paths in props (images…) are relative to
the edit dir, or to the repo root (`assets/…`, `brands/…`); they're staged into edit/motion_public.

Narration: with a `voice` block, `voice` synthesises each narrated scene into
edit/audio/narration/<scene>.wav (+ sidecar; unchanged lines stay cached) and times its words with
local Whisper aligned to the script (<scene>.words.json). A scene without `duration` (or "auto")
lasts transition-in + clip + tail; its clip starts when the transition-in ends. `render` lays the
clips on edit/audio/narration_track.wav and mixes it as the voice. Without a `voice` block,
`narration` is only a planning note (pace warning), as before.
Cues: any time in a scene's props or `sfx` can be "@word" (first time that word is spoken in the
scene), "@word#2" (second time) or "@word+0.2" (offset in s); `check` errors on cues that match no
word. On-screen text keys (text, title, label…) are never read as cues.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import narration as N
from brand import load_brand
from gen import voice as V
from shortform import DELIVERY_X264, MOTION, REPO, SFX_DIR, loudness, loudnorm_2pass, run

ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}
# mirrors DEFAULT_TRANSITION_S in tools/motion/src/scenes/transitions.tsx
TRANSITION_S = {"cut": 0, "fade": 0.4, "slide": 0.45, "wipe": 0.5, "flip": 0.6, "iris": 0.6,
                "clockWipe": 0.7, "zoom": 0.45}
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".mp4", ".mov", ".webm", ".json"}
TEXT_KEYS = {"text", "title", "kicker", "sub", "label"}  # on-screen text, for the reading-time check
NARRATION_WPS = 2.6  # ≈155 wpm, a natural voiceover pace
READ_WPS = 4.0  # on-screen words a viewer reads per second (display text), after READ_SETTLE s to find it
READ_SETTLE = 0.8
TAIL_S = 0.3  # breathing room after the last narration clip before a transition or a silent scene
PAUSE_OVERHEAD_S = 0.12  # a piece's own edge silences: a 0.18 s `.` pause measures ~0.30 s inside a clip
# on-screen text keys: never read as `@word` cues (a subtitle can say "@handle")
DISPLAY_KEYS = TEXT_KEYS | {"emphasis", "prefix", "suffix", "handle", "name", "icon", "words"}


def _trailing_silence(clip: Path, db: float = -35.0) -> float:
    """Seconds of near-silence at the end of a mono 16-bit WAV (after the last 10 ms window above `db`)."""
    import wave

    import numpy as np

    try:
        with wave.open(str(clip)) as w:
            sr, a = w.getframerate(), np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768
    except (OSError, wave.Error):
        return 0.0
    win = sr // 100
    n = len(a) // win
    if n == 0:
        return 0.0
    rms = 20 * np.log10(np.sqrt((a[: n * win].reshape(n, win) ** 2).mean(1)) + 1e-9)
    loud = np.nonzero(rms > db)[0]
    return 0.0 if not len(loud) else (n - 1 - loud[-1]) * win / sr


def _registry(path: Path, block: str) -> set[str]:
    src = path.read_text()
    m = re.search(block + r"[^{]*\{([^}]*)\}", src)
    return set(re.findall(r"\b([A-Z]\w+)\b", m.group(1))) if m else set()


SCENE_TYPES = _registry(MOTION / "src/scenes/index.ts", r"export const SCENES")
_poses = (MOTION / "src/explainer/poses.ts").read_text()
POSE_NAMES = re.findall(r"^  (\w+): P\(", _poses, re.M)
PROP_NAMES = re.findall(r'"(\w+)"', re.search(r"PROP_NAMES[^=]*=\s*\[([^\]]*)\]", _poses).group(1))
WIDGET_TYPES = _registry(MOTION / "src/explainer/widgets/index.ts", r"export const WIDGETS")
SLOT_NAMES = re.findall(r'"(\w+)"', re.search(r"SLOT_NAMES[^=]*=\s*\[([^\]]*)\]",
                                              (MOTION / "src/explainer/slots.ts").read_text()).group(1))
OVERLAY_TYPES = _registry(MOTION / "src/Overlay.tsx", r"export const REGISTRY")
_icons = (MOTION / "src/components/icons.tsx").read_text()
ICON_NAMES = re.findall(r'\|\s*"(\w+)"', re.search(r"export type IconKind\s*=([^;]*);", _icons).group(1))
ICON_KEYS = ("icon", "leftIcon", "rightIcon")
HEADLINE_SCENES = {"BeatScene", "WorldScene"}  # scenes that draw the voice-built headline
_world = (MOTION / "src/world/model.ts").read_text()
WORLD_KINDS = re.findall(r'"(\w+)"', re.search(r"WORLD_KINDS = \[([^\]]*)\]", _world).group(1))
WORLD_ACTIONS = {a: (WORLD_KINDS if k.strip() == "WORLD_KINDS" else re.findall(r'"(\w+)"', k))
                 for a, k in re.findall(r"^  (\w+): (WORLD_KINDS|\[[^\]]*\])", _world.split("export const ACTIONS")[1].split("};")[0], re.M)}
WORLD_FIELDS = {"block": ("w", "h", "label"), "sign": ("text",), "prop": ("item",), "callout": ("text", "target")}
PROP_ITEMS = re.findall(r'"(\w+)"', re.search(r"export type PropItem = ([^;]*);", _world).group(1))
WORLD_TIME_KEYS = ("at", "arrive", "until")  # action fields on the run's clock (shifted when beats merge)
VOICE_MAX_WPS = 4.0  # above this a synthetic voice gets hard to follow
MOVE_S = 0.8  # default figure move time (Figure.tsx MOVE_S)
OFFICE_GRID = (8, 6)  # IsoOffice default floor, cols x rows (IsoOffice.tsx)


class Story:
    def __init__(self, path: Path):
        path = path.resolve()
        self.file = path if path.suffix == ".json" else path / "storyboard.json"
        self.edit_dir = self.file.parent
        self.sb = json.loads(self.file.read_text())
        self.aspect = self.sb.get("aspect", "9:16")
        if self.aspect not in ASPECTS:
            sys.exit(f"aspect must be one of {list(ASPECTS)}, got {self.aspect!r}")
        self.fps = int(self.sb.get("fps", 30))
        # resolved copy: auto durations filled in, `@word` cues replaced by seconds (see resolve())
        self.scenes: list[dict] = copy.deepcopy(self.sb["scenes"])
        self.kit = load_brand(self.sb.get("brand"))
        self.lufs = float(self.sb.get("lufs", -14))
        self.project = self.edit_dir.parent.name
        self.vc: dict | None = self.sb.get("voice")
        self.lang = (self.vc or {}).get("lang", "en")
        self.resolve()

    # ── narration (voice block, clips, word times, cues) ─────────────────
    def clip_for(self, i: int, s: dict) -> Path | None:
        """The scene's narration clip: its recorded `narration_audio`, or (with a `voice` block) the
        synthesised edit/audio/narration/<scene>.wav. None = not narrated."""
        if s.get("narration_audio"):
            return self._resolve(s["narration_audio"]) or (self.edit_dir / s["narration_audio"])
        if self.vc is not None and s.get("narration", "").strip():
            slug = re.sub(r"[^a-z0-9]+", "-", s.get("name", f"scene{i}").lower()).strip("-") or f"scene{i}"
            return self.edit_dir / "audio" / "narration" / f"{slug}.wav"
        return None

    def _job(self, i: int, s: dict) -> V.Job:
        vc = self.vc or {}
        return V.Job(self.clip_for(i, s), V.spoken(s["narration"], vc.get("pronounce")), self.lang,
                     vc.get("preset"), float(s.get("speed", vc.get("speed", 1.0))))

    def _words_sig(self, i: int, s: dict, clip: Path) -> str:
        if s.get("narration_audio"):
            st = clip.stat()
            src = [st.st_size, st.st_mtime_ns]
        else:
            src = self._job(i, s).key()
        key = [src, s.get("narration", ""), (self.vc or {}).get("pronounce"), self.lang, N.ALIGN_VERSION]
        return hashlib.sha1(json.dumps(key, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]

    def _words_file(self, clip: Path) -> Path:
        return clip.with_suffix(".words.json")

    def _fresh_words(self, i: int, s: dict, clip: Path) -> dict | None:
        try:
            w = json.loads(self._words_file(clip).read_text())
        except (OSError, ValueError):
            return None
        return w if w.get("sig") == self._words_sig(i, s, clip) else None

    def time_words(self, items: list[tuple[int, dict, Path]]) -> None:
        """Word times for clips: local Whisper (tools/transcribe_local.py) in one batch, aligned to
        the script, cut into phrases. Writes <clip>.words.json (times in s from the clip start)."""
        if not items:
            return
        import os

        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        from transcribe_local import DEFAULT_MODEL, transcribe_one

        lang = self.lang.split("-")[0]
        pron = (self.vc or {}).get("pronounce")
        print(f"  timing words: {len(items)} clips with local Whisper…", flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            for i, s, clip in items:
                with contextlib.redirect_stdout(io.StringIO()):
                    rec = json.loads(transcribe_one(clip, Path(tmp), DEFAULT_MODEL, lang, 0).read_text())
                audio = N.decode_mono(clip)
                dur, onset = len(audio) / 16000, N.onset_of(audio, 16000)
                words = N.script_words(s["narration"])
                if not words:
                    continue
                timed = N.phrases(N.align(words, N.spoken_tokens(words, pron),
                                          [w for w in rec["words"] if w["type"] == "word"], onset, dur))
                n = sum(w["aligned"] for w in timed)
                self._words_file(clip).write_text(json.dumps(
                    {"sig": self._words_sig(i, s, clip), "duration": round(dur, 3), "onset": onset,
                     "aligned": n, "words": timed}, indent=1, ensure_ascii=False))
                print(f"  words: {clip.name} {n}/{len(timed)} aligned")

    def _tail(self, i: int, s: dict, clip: Path) -> float:
        """Silence after a narrated scene's clip. An explicit `tail` wins. Otherwise, when the next
        scene is narrated and cut straight in, the gap between the two voices matches the pause the
        voice makes for the same punctuation inside a clip (`.` ≈ 0.3 s, `,` ≈ 0.13 s), so a full
        stop sounds the same within a beat and across beats. Before a transition or a silent scene,
        TAIL_S."""
        if "tail" in s:
            return float(s["tail"])
        nxt = self.scenes[i + 1] if i + 1 < len(self.scenes) else None
        if not nxt or nxt.get("transition") or self.clip_for(i + 1, nxt) is None:
            return TAIL_S
        text = re.sub(r"[*|\s]+$", "", s.get("narration", ""))
        mark = text[-1:] if text and not text[-1].isalnum() else ""
        gap = V.PAUSE_S.get(mark, 0.0) + PAUSE_OVERHEAD_S if mark in V.PAUSE_S else (0.13 if mark == "," else 0.08)
        return max(0.0, gap - _trailing_silence(clip))

    def resolve(self) -> None:
        """Fill auto durations from narration clips, record each narrated scene's voice start, and
        resolve `@word` cues in props and `sfx` to seconds. Problems go to `self.narr_errors`."""
        errs: list[str] = []
        self.narr_errors, self.narr_warns = errs, []
        self.narrated: dict[int, dict] = {}  # scene index → {clip, duration, onset, origin, words…}
        if self.vc is not None and (err := V.validate(self.lang, self.vc.get("preset"))):
            errs.append(f"voice: {err} (then run `voice`)")
        recorded = []
        for i, s in enumerate(self.scenes):
            clip = self.clip_for(i, s)
            if clip and s.get("narration_audio") and clip.exists() and s.get("narration", "").strip() \
                    and not self._fresh_words(i, s, clip):
                recorded.append((i, s, clip))
        self.time_words(recorded)  # recorded clips get their word times on `check`
        names: dict[str, int] = {}
        for i, s in enumerate(self.scenes):
            name = s.get("name", f"#{i}")
            clip = self.clip_for(i, s)
            tf = self.trans_frames(s) if i else 0
            info = None
            if clip is not None:
                if clip.name in names:
                    errs.append(f"{name}: narration clip name clashes with scene #{names[clip.name]}; give scenes unique names")
                names[clip.name] = i
                if s.get("narration_audio"):
                    if not clip.exists():
                        errs.append(f"{name}: narration_audio not found: {s['narration_audio']}")
                    elif not s.get("narration", "").strip():
                        errs.append(f"{name}: narration_audio needs its `narration` text (for the headline and cues)")
                    else:
                        info = self._fresh_words(i, s, clip)
                elif not (self.vc is not None and V.validate(self.lang, self.vc.get("preset")) is None):
                    pass  # the voice error above covers it
                elif not V.is_fresh(self._job(i, s)):
                    why = "missing" if not clip.exists() else "stale (narration or voice changed)"
                    errs.append(f"{name}: narration clip {why}; run `voice`")
                elif not (info := self._fresh_words(i, s, clip)):
                    errs.append(f"{name}: word times missing or stale; run `voice`")
            d = s.get("duration")
            if info:
                need = tf + math.ceil((info["duration"] + self._tail(i, s, clip)) * self.fps - 1e-6)
                if d in (None, "auto"):
                    s["duration"] = need / self.fps
                elif self._frames(float(d)) < need:
                    errs.append(f"{name}: duration {float(d):.2f}s is shorter than its narration; it needs {need / self.fps:.2f}s")
                # the clip is placed so its voice onset lands exactly where the transition-in ends
                origin = tf / self.fps - info["onset"]
                words = [{**w, "t": round(origin + w["t"], 3) + 0.0} for w in info["words"]]
                self.narrated[i] = {"clip": clip, "duration": info["duration"], "origin": origin,
                                    "voiceStart": tf / self.fps, "words": words, "aligned": info["aligned"]}
                groups = {}
                for a, b in zip([None] + words, words):
                    if b["emph"] and not (a and a["emph"] and a["phrase"] == b["phrase"]):
                        groups[b["phrase"]] = groups.get(b["phrase"], 0) + 1
                if any(n > 1 for n in groups.values()):
                    self.narr_warns.append(f"{name}: more than one *emphasis* in a phrase; keep one per phrase")
            elif d in (None, "auto"):
                if clip is None:
                    errs.append(f"{name}: `duration` is required (no narration clip to time it)")
                    s["duration"] = 3.0
                else:  # placeholder until `voice` has run, so the plan still prints
                    s["duration"] = round(len(s.get("narration", "").split()) / NARRATION_WPS + TAIL_S, 2)
            s["duration"] = float(s["duration"])
            self._resolve_cues(i, s, errs)

    def _resolve_cues(self, i: int, s: dict, errs: list[str]) -> None:
        name = s.get("name", f"#{i}")
        words = self.narrated.get(i, {}).get("words")

        def cue(v):
            if not N.is_cue(v):
                return v
            if words is None:
                if self.clip_for(i, s) is None:  # a narrated scene's missing clip is reported once, above
                    errs.append(f"{name}: cue {v!r} needs narration (a `voice` block or `narration_audio`)")
                return 0.0
            t = N.resolve_cue(v, words)
            if t is None:
                errs.append(f"{name}: cue {v!r} matches no word in its narration")
                return 0.0
            return t

        def walk(o):
            if isinstance(o, dict):
                return {k: (v if k in DISPLAY_KEYS else walk(v)) for k, v in o.items()}
            if isinstance(o, list):
                return [walk(v) for v in o]
            return cue(o)

        if "props" in s:
            s["props"] = walk(s["props"])
        if "sfx" in s:
            s["sfx"] = [[n, cue(t), db] for n, t, db in s["sfx"]]

    # ── timeline (same frame maths as Story.tsx) ──────────────────────────
    def _frames(self, s: float) -> int:
        return round(s * self.fps)

    def trans_frames(self, scene: dict) -> int:
        t = scene.get("transition")
        if not t or t.get("type", "cut") == "cut":
            return 0
        return self._frames(t.get("duration", TRANSITION_S[t["type"]]))

    def timeline(self) -> list[tuple[float, float]]:
        """(start, duration) of each scene in seconds, transitions overlapping."""
        out, f = [], 0
        for i, s in enumerate(self.scenes):
            n = max(1, self._frames(s["duration"]))
            if i > 0:
                f -= self.trans_frames(s)
            out.append((f / self.fps, n / self.fps))
            f += n
        return out

    @property
    def total(self) -> float:
        start, dur = self.timeline()[-1]
        return start + dur

    @property
    def audio_len(self) -> float:
        """Audio length in s, rounded *up* to the ms: rounding down makes `-shortest` drop the last frame."""
        return math.ceil(self.total * 1000 - 1e-6) / 1000

    def all_sfx(self) -> list[tuple[str, float, float]]:
        tl = self.timeline()
        out = [(n, t, db) for n, t, db in self.sb.get("audio", {}).get("sfx", [])]
        for (start, _), s in zip(tl, self.scenes):
            out += [(n, start + t, db) for n, t, db in s.get("sfx", [])]
        return sorted(out, key=lambda x: x[1])

    # ── checks ────────────────────────────────────────────────────────────
    def _assets(self, obj) -> list[str]:
        if isinstance(obj, dict):
            return [a for v in obj.values() for a in self._assets(v)]
        if isinstance(obj, list):
            return [a for v in obj for a in self._assets(v)]
        if isinstance(obj, str) and Path(obj).suffix.lower() in MEDIA_EXT and not obj.startswith("http"):
            return [obj]
        return []

    def _resolve(self, rel: str) -> Path | None:
        if Path(rel).is_absolute():
            return None
        for base in (self.edit_dir, REPO):
            if (base / rel).exists():
                return base / rel
        return None

    def _text_words(self, obj) -> int:
        if isinstance(obj, dict):
            return sum(len(str(v).split()) if k in TEXT_KEYS and isinstance(v, str) else self._text_words(v)
                       for k, v in obj.items())
        if isinstance(obj, list):
            return sum(self._text_words(v) for v in obj)
        return 0

    def check(self, quiet: bool = False) -> list[str]:
        errors, warns = [], []
        tl = self.timeline()
        rows = []
        for i, ((start, dur), s) in enumerate(zip(tl, self.scenes)):
            name = s.get("name", f"#{i}")
            t = s["type"]
            if t not in SCENE_TYPES | OVERLAY_TYPES:
                errors.append(f"{name}: unknown type {t!r} (scenes: {', '.join(sorted(SCENE_TYPES))})")
            elif t not in SCENE_TYPES and self.aspect != "9:16":
                errors.append(f"{name}: {t} is a 9:16 overlay component; use a scene primitive in {self.aspect}")
            tf = self.trans_frames(s) if i else 0
            prev = max(1, self._frames(self.scenes[i - 1]["duration"])) if i else 10 ** 9
            if tf and tf >= min(prev, max(1, self._frames(s["duration"]))):
                errors.append(f"{name}: transition ({tf} f) must be shorter than both neighbouring scenes")
            words = self._text_words(s.get("props", {}))
            need = READ_SETTLE + words / READ_WPS if words else 0
            if dur < need:
                warns.append(f"{name}: {words} on-screen words need ~{need:.1f}s to read, scene is {dur:.1f}s")
            narr = len(s.get("narration", "").split())
            if narr and i not in self.narrated and self.clip_for(i, s) is None and narr / NARRATION_WPS > dur + 0.2:
                warns.append(f"{name}: narration ({narr} words) needs ~{narr / NARRATION_WPS:.1f}s, scene is {dur:.1f}s")
            if dur > 7:
                warns.append(f"{name}: {dur:.1f}s on one scene. Hold attention with a beat inside it, or split it")
            if (nv := self.narrated.get(i)) and nv["duration"] > 0.8 and len(nv["words"]) / nv["duration"] > VOICE_MAX_WPS:
                warns.append(f"{name}: narration runs at {len(nv['words']) / nv['duration']:.1f} words/s (clear is ≤ {VOICE_MAX_WPS}); "
                             "shorten the line (slowing the voice below 1.0 makes it drag)")
            if t == "BeatScene":
                errors += self._check_beat(name, s.get("props", {}))
            elif t == "NetworkScene":
                errors += self._check_network(name, s.get("props", {}))
            elif t == "IsoOffice":
                errors += self._check_office(name, s.get("props", {}), dur)
            elif t == "WorldScene":
                errors += self._check_world_beat(name, s.get("props", {}))
            for a in self._assets(s.get("props", {})):
                if not self._resolve(a):
                    errors.append(f"{name}: asset not found: {a} (relative to edit/ or repo root)")
            tr = (s.get("transition") or {}).get("type", "cut") if i else "—"
            nv = self.narrated.get(i)
            vo = f"{start + nv['voiceStart']:6.2f} {nv['aligned']:>2}/{len(nv['words']):<2}" if nv else f"{'':6} {'':5}"
            rows.append(f"{i:>2} {start:6.2f} {dur:5.2f}  {t:<13} {s.get('bg', '-'):<7} {tr:<9} {vo} {name}")
        w_err, w_warn = self._check_worlds()
        errors += w_err
        warns += w_warn
        for e in self.sb.get("events", []):
            if e["type"] not in SCENE_TYPES | OVERLAY_TYPES:
                errors.append(f"event {e['type']!r} at {e['start']}: unknown type")
            if e["start"] + e["duration"] > self.total + 1e-6:
                warns.append(f"event {e['type']} at {e['start']}s runs past the end ({self.total:.2f}s)")
        sfx = [x for x in self.all_sfx() if x[0] != "typing"]
        for a, b in zip(sfx, sfx[1:]):
            if b[1] - a[1] < 0.3:
                warns.append(f"SFX {a[0]}@{a[1]:.2f} and {b[0]}@{b[1]:.2f} are {b[1] - a[1]:.2f}s apart")
        for n, _, _ in self.all_sfx():
            if not (SFX_DIR / f"{n}.wav").exists():
                errors.append(f"SFX {n!r} not in {SFX_DIR.relative_to(REPO)} (run tools/sfx_synth.py)")
        audio = self.sb.get("audio", {})
        if audio.get("voice") and not self._resolve(audio["voice"]):
            errors.append(f"audio.voice not found: {audio['voice']}")
        if audio.get("voice") and any(self.clip_for(i, s) for i, s in enumerate(self.scenes)):
            errors.append("two voice sources: audio.voice and per-scene narration clips; use one of them")
        errors += self.narr_errors
        warns += self.narr_warns
        if audio.get("music") and not self._resolve(audio["music"]["file"]):
            errors.append(f"audio.music not found: {audio['music']['file']}")
        if not quiet:
            w, h = ASPECTS[self.aspect]
            print(f"{self.project}: {self.aspect} {w}x{h} @{self.fps}, brand={self.kit.slug or 'none'}, "
                  f"{len(self.scenes)} scenes, {self.total:.2f}s")
            if self.vc is not None:
                print(f"voice: {self.lang} {self.vc.get('preset') or V.default_preset(self.lang) if self.lang in V.LANGS else '?'}"
                      f" speed {self.vc.get('speed', 1.0)}, {V.MODEL_ID}")
            print(" #  start   dur  type          bg      in        vo@   words name")
            print("\n".join(rows))
            for x in warns:
                print(f"  WARN  {x}")
            for x in errors:
                print(f"  ERROR {x}")
        return errors

    def voice(self, force: bool = False) -> None:
        """Synthesise every narrated scene's clip (skipping cached ones), then time their words."""
        if self.vc is None:
            sys.exit("no `voice` block in the storyboard: add {\"voice\": {\"lang\": \"en\"}} to narrate scenes")
        if err := V.validate(self.lang, self.vc.get("preset")):
            sys.exit(f"voice: {err}")
        synth = [(i, s) for i, s in enumerate(self.scenes) if self.clip_for(i, s) and not s.get("narration_audio")]
        print(f"voice: {len(synth)} narrated scenes, {self.lang} {self.vc.get('preset') or V.default_preset(self.lang)}")
        V.synthesize_many([self._job(i, s) for i, s in synth], force=force)
        stale = [(i, s, self.clip_for(i, s)) for i, s in synth
                 if s.get("narration", "").strip() and (force or not self._fresh_words(i, s, self.clip_for(i, s)))]
        self.time_words(stale)
        if not stale:
            print("  word times: all cached")
        self.scenes = copy.deepcopy(self.sb["scenes"])
        self.resolve()

    def _check_beat(self, name: str, props: dict) -> list[str]:
        """BeatScene props: widget types and slots, the figure's poses, props and slot."""
        errs = []
        for k, w in enumerate(props.get("widgets", [])):
            if w.get("type") not in WIDGET_TYPES:
                errs.append(f"{name}: unknown widget {w.get('type')!r} (widgets: {', '.join(sorted(WIDGET_TYPES))})")
            if w.get("slot", "main") not in SLOT_NAMES:
                errs.append(f"{name}: widget {w.get('type')} in unknown slot {w.get('slot')!r} (slots: {', '.join(SLOT_NAMES)})")
            for key in ICON_KEYS:
                if key in w and w[key] not in ICON_NAMES:
                    errs.append(f"{name}: widget {w.get('type')} has unknown {key} {w[key]!r} (icons: {', '.join(ICON_NAMES)})")
        fig = props.get("figure")
        if fig:
            cues = fig.get("poses") or ([{"pose": fig["pose"]}] if fig.get("pose") else [])
            for c in cues:
                if c.get("pose") not in POSE_NAMES:
                    errs.append(f"{name}: unknown pose {c.get('pose')!r} (poses: {', '.join(POSE_NAMES)})")
                if c.get("prop") not in (None, *PROP_NAMES):
                    errs.append(f"{name}: unknown prop {c.get('prop')!r} (props: {', '.join(PROP_NAMES)})")
            if not 0 <= float(fig.get("x", 0.5)) <= 1:
                errs.append(f"{name}: figure x {fig['x']} is outside 0–1")
            end = None
            for m in sorted(fig.get("moves", []), key=lambda m: float(m.get("at", 0))):
                at, x = float(m.get("at", 0)), m.get("x")
                if not isinstance(x, (int, float)) or not 0 <= x <= 1:
                    errs.append(f"{name}: figure move at {at:.2f}s has x {x!r}; x must be 0–1")
                if end is not None and at < end - 1e-6:
                    errs.append(f"{name}: figure move at {at:.2f}s starts before the previous one ends ({end:.2f}s)")
                end = at + float(m.get("dur", MOVE_S))
            if fig.get("slot", "figure") not in SLOT_NAMES:
                errs.append(f"{name}: unknown figure slot {fig.get('slot')!r} (slots: {', '.join(SLOT_NAMES)})")
        return errs

    def world_runs(self) -> list[list[int]]:
        """Indices of consecutive WorldScene beats sharing a `world`; each run renders as one scene."""
        runs: list[list[int]] = []
        for i, s in enumerate(self.scenes):
            wid = s.get("props", {}).get("world") if s["type"] == "WorldScene" else None
            if wid is not None and runs and self.scenes[runs[-1][-1]].get("props", {}).get("world") == wid and runs[-1][-1] == i - 1:
                runs[-1].append(i)
            elif wid is not None:
                runs.append([i])
        return runs

    def _check_worlds(self) -> tuple[list[str], list[str]]:
        """World definitions (kinds, ids, fields), transitions inside runs, unused worlds."""
        errs, warns = [], []
        for wid, wd in self.sb.get("worlds", {}).items():
            ids = [o.get("id") for o in wd.get("objects", [])]
            for d in sorted({i for i in ids if ids.count(i) > 1}, key=str):
                errs.append(f"world {wid}: duplicate object id {d!r}")
            for o in wd.get("objects", []):
                oid, kind = o.get("id"), o.get("kind")
                if kind not in WORLD_KINDS:
                    errs.append(f"world {wid}: object {oid!r} has unknown kind {kind!r} (kinds: {', '.join(WORLD_KINDS)})")
                    continue
                if kind != "callout" and not isinstance(o.get("x"), (int, float)):
                    errs.append(f"world {wid}: {kind} {oid!r} needs a numeric `x`")
                for f in WORLD_FIELDS.get(kind, ()):
                    if f not in o:
                        errs.append(f"world {wid}: {kind} {oid!r} needs `{f}`")
                if kind == "prop" and o.get("item") not in PROP_ITEMS:
                    errs.append(f"world {wid}: prop {oid!r} has unknown item {o.get('item')!r} (items: {', '.join(PROP_ITEMS)})")
                if kind == "callout" and o.get("target") not in ids:
                    errs.append(f"world {wid}: callout {oid!r} points at unknown object {o.get('target')!r}")
                if kind == "figure" and o.get("pose", "stand") not in POSE_NAMES:
                    errs.append(f"world {wid}: figure {oid!r} has unknown pose {o.get('pose')!r}")
            if (k := (wd.get("terrain") or {}).get("kind", "snow")) != "snow":
                errs.append(f"world {wid}: unknown terrain {k!r} (terrains: snow)")
        used = {self.scenes[r[0]].get("props", {}).get("world") for r in self.world_runs()}
        for wid in self.sb.get("worlds", {}):
            if wid not in used:
                warns.append(f"world {wid!r} is defined but no WorldScene uses it")
        for run in self.world_runs():
            for i in run[1:]:
                if self.scenes[i].get("transition"):
                    errs.append(f"{self.scenes[i].get('name', f'#{i}')}: transition inside world run "
                                f"{self.scenes[run[0]]['props'].get('world')!r}; beats of one world are continuous")
        return errs, warns

    def _check_world_beat(self, name: str, props: dict) -> list[str]:
        """WorldScene props: a known world; actions with known targets, verbs that fit the target's kind."""
        wid = props.get("world")
        wd = self.sb.get("worlds", {}).get(wid)
        if wd is None:
            return [f"{name}: unknown world {wid!r} (worlds: {', '.join(self.sb.get('worlds', {})) or 'none'})"]
        kinds = {o.get("id"): o.get("kind") for o in wd.get("objects", [])} | {"sky": "sky", "camera": "camera"}
        errs = []
        for a in props.get("actions", []):
            tgt, verb = a.get("target"), a.get("do")
            what = f"action {verb!r} on {tgt!r}"
            if tgt not in kinds:
                errs.append(f"{name}: {what}: unknown target {tgt!r} (objects: {', '.join(k for k in kinds if k not in ('sky', 'camera'))})")
                continue
            if verb not in WORLD_ACTIONS:
                errs.append(f"{name}: {what}: unknown action (actions: {', '.join(WORLD_ACTIONS)})")
                continue
            if kinds[tgt] not in WORLD_ACTIONS[verb]:
                errs.append(f"{name}: {what}: {verb!r} applies to {', '.join(WORLD_ACTIONS[verb])}, not a {kinds[tgt]}")
            if verb == "roll" and isinstance(a.get("to"), str) and kinds.get(a["to"]) != "block":
                errs.append(f"{name}: {what}: `to` {a['to']!r} is not a block")
            if verb == "throw" and kinds.get(a.get("item")) != "prop":
                errs.append(f"{name}: {what}: `item` {a.get('item')!r} is not a prop")
            if verb == "hold" and kinds.get(a.get("on")) != "figure":
                errs.append(f"{name}: {what}: `on` {a.get('on')!r} is not a figure")
            if verb == "camera" and a.get("follow") is not None and a["follow"] not in kinds:
                errs.append(f"{name}: {what}: follows unknown object {a['follow']!r}")
            if verb == "pose" and a.get("pose") not in POSE_NAMES:
                errs.append(f"{name}: {what}: unknown pose {a.get('pose')!r} (poses: {', '.join(POSE_NAMES)})")
            if verb == "pose" and a.get("prop") not in (None, *PROP_NAMES):
                errs.append(f"{name}: {what}: unknown prop {a.get('prop')!r} (props: {', '.join(PROP_NAMES)})")
        return errs

    def _merge_worlds(self, scenes: list[dict]) -> list[dict]:
        """Render props: each world run becomes one scene on one clock (durations summed, action
        times and headline words shifted by each beat's offset), with the world definition inlined."""
        runs = {r[0]: r for r in self.world_runs()}
        out, i = [], 0
        while i < len(scenes):
            if i not in runs:
                out.append(scenes[i])
                i += 1
                continue
            run = runs[i]
            first = scenes[i]
            acts, words, beats, off = [], [], [], 0.0
            for j in run:
                p = scenes[j].get("props", {})
                beats.append({"name": scenes[j].get("name", f"#{j}"), "start": round(off, 3)})
                for a in p.get("actions", []):
                    acts.append({k: (round(v + off, 3) if k in WORLD_TIME_KEYS and isinstance(v, (int, float)) else v) for k, v in a.items()})
                base = max((w["phrase"] for w in words), default=-1) + 1  # phrases never span two beats
                words += [{**w, "t": round(w["t"] + off, 3), "phrase": w["phrase"] + base} for w in p.get("words", [])]
                off += float(scenes[j]["duration"])
            merged = {**first, "duration": round(off, 4), "name": first.get("name", "world"),
                      "props": {**{k: v for k, v in first.get("props", {}).items() if k not in ("actions", "words")},
                                "world": self.sb["worlds"][first["props"]["world"]], "actions": acts, "words": words, "beats": beats}}
            out.append(merged)
            i = run[-1] + 1
        return out

    def _check_icons(self, name: str, what: str, obj: dict) -> list[str]:
        icon = obj.get("icon")
        if icon is not None and icon not in ICON_NAMES:
            return [f"{name}: {what} has unknown icon {icon!r} (icons: {', '.join(ICON_NAMES)})"]
        return []

    def _check_network(self, name: str, props: dict) -> list[str]:
        """NetworkScene props: messages and chips name existing nodes; icons are known."""
        nodes = props.get("nodes") or []
        if not nodes:
            return [f"{name}: NetworkScene needs `nodes`"]
        ids = [n.get("id") for n in nodes]
        errs = [f"{name}: duplicate node id {i!r}" for i in sorted({i for i in ids if ids.count(i) > 1})]
        for n in nodes:
            errs += self._check_icons(name, f"node {n.get('id')!r}", n)
        if isinstance(props.get("hub"), dict):
            errs += self._check_icons(name, "hub", props["hub"])
        for m in props.get("messages", []):
            for key in ("from", "to"):
                if m.get(key) not in ids:
                    errs.append(f"{name}: message {key} unknown node {m.get(key)!r} (nodes: {', '.join(map(str, ids))})")
        for c in props.get("chips", []):
            if c.get("node") not in ids:
                errs.append(f"{name}: chip on unknown node {c.get('node')!r} (nodes: {', '.join(map(str, ids))})")
        return errs

    def _check_office(self, name: str, props: dict, dur: float) -> list[str]:
        """IsoOffice props: walks, bubbles and carries name existing agents; positions are desk ids or
        [u, v] inside the floor; icons are known; a replay ends inside the scene."""
        agents = props.get("agents") or []
        if not agents:
            return [f"{name}: IsoOffice needs `agents`"]
        cols, rows = int(props.get("cols", OFFICE_GRID[0])), int(props.get("rows", OFFICE_GRID[1]))
        ids = [a.get("id") for a in agents]
        desks = [d.get("id") for d in props["desks"]] if props.get("desks") else \
            [f"desk{k + 1}" for k in range(max(4, len(agents)))]  # IsoOffice.tsx autoDesks
        errs = [f"{name}: duplicate agent id {i!r}" for i in sorted({i for i in ids if ids.count(i) > 1})]

        def place(what: str, p) -> None:
            if isinstance(p, str):
                if p not in desks:
                    errs.append(f"{name}: {what} unknown desk {p!r} (desks: {', '.join(map(str, desks))})")
            elif not (isinstance(p, list) and len(p) == 2 and 0 <= p[0] < cols and 0 <= p[1] < rows):
                errs.append(f"{name}: {what} {p!r} must be a desk id or [u, v] inside the {cols}x{rows} floor")

        for a in agents:
            place(f"agent {a.get('id')!r} pos", a.get("pos"))
        for d in props.get("desks") or []:
            if not (0 <= d.get("u", -1) < cols and 0 <= d.get("v", -1) < rows):
                errs.append(f"{name}: desk {d.get('id')!r} at ({d.get('u')}, {d.get('v')}) is outside the {cols}x{rows} floor")
        for w in props.get("walks", []):
            what = "carry" if w.get("carry") else "walk"
            if w.get("agent") not in ids:
                errs.append(f"{name}: {what} by unknown agent {w.get('agent')!r} (agents: {', '.join(map(str, ids))})")
            place(f"{what} by {w.get('agent')!r} to", w.get("to"))
        for b in props.get("bubbles", []):
            if b.get("agent") not in ids:
                errs.append(f"{name}: bubble on unknown agent {b.get('agent')!r} (agents: {', '.join(map(str, ids))})")
            errs += self._check_icons(name, f"bubble on {b.get('agent')!r}", b)
        if r := props.get("replay"):
            at, rd = float(r.get("at", 0)), float(r.get("dur", 0))
            if rd <= 0:
                errs.append(f"{name}: replay needs a positive `dur`")
            if at + rd > dur + 1e-6:
                errs.append(f"{name}: replay ends at {at + rd:.2f}s, after the scene ({dur:.2f}s)")
            if float(r.get("to", 0)) >= at:
                errs.append(f"{name}: replay `to` ({r.get('to', 0)}) must be before its `at` ({at})")
        return errs

    # ── Remotion ──────────────────────────────────────────────────────────
    def stage(self) -> Path:
        """Copy brand fonts + referenced assets into edit/motion_public, write story_props.json,
        and bundle the Remotion project once (stills and the render reuse it)."""
        pub = self.edit_dir / "motion_public"
        pub.mkdir(exist_ok=True)
        files = dict(self.kit.public_files)
        for s in self.scenes + self.sb.get("events", []):
            for a in self._assets(s.get("props", {})):
                if src := self._resolve(a):
                    files[a] = src
        for name, src in files.items():
            dst = pub / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists() or dst.stat().st_mtime < Path(src).stat().st_mtime:
                shutil.copy2(src, dst)
        keep = ("type", "duration", "bg", "grain", "transition", "props", "name")
        scenes = [{k: s[k] for k in keep if k in s} for s in self.scenes]
        for i, nv in self.narrated.items():  # the headline draws these
            if scenes[i]["type"] in HEADLINE_SCENES:
                scenes[i]["props"] = {**scenes[i].get("props", {}), "words": [
                    {"text": w["text"], "t": w["t"], "emph": w["emph"], "phrase": w["phrase"]} for w in nv["words"]]}
        for i, sc in enumerate(scenes):  # consecutive figures don't sway in lockstep
            fig = sc.get("props", {}).get("figure")
            if sc["type"] == "BeatScene" and fig and "phase" not in fig:
                sc["props"] = {**sc["props"], "figure": {**fig, "phase": round(i * 0.9, 2)}}
        scenes = self._merge_worlds(scenes)
        events = list(self.sb.get("events", []))
        if self.sb.get("progress"):
            events.append({"type": "ProgressBar", "start": 0, "duration": self.audio_len, "name": "progress"})
        props = {"aspect": self.aspect, "fps": self.fps, "brand": self.kit.theme,
                 "grain": self.sb.get("grain", 0), "scenes": scenes, "events": events}
        (self.edit_dir / "story_props.json").write_text(json.dumps(props, indent=1, ensure_ascii=False))
        bundle = self.edit_dir / "motion_bundle"
        run(["npx", "remotion", "bundle", f"--public-dir={pub}", f"--out-dir={bundle}", "--log=error"], cwd=MOTION)
        return bundle

    def _remotion(self, bundle: Path, *args: str) -> None:
        run(["npx", "remotion", *args[:1], str(bundle), "Story", *args[1:],
             f"--props={self.edit_dir / 'story_props.json'}", "--log=error"], cwd=MOTION)

    def sheet(self, kind: str, aspect: str | None = None, bg: str = "light") -> Path:
        """Verification contact sheets in this storyboard's brand: every pose (`poses`), or every
        widget in a BeatScene at an aspect (`widgets`), with the safe box drawn on and checked: a
        widget must not change any pixel outside it. → edit/stills/<kind>[_<aspect>][_dark].png"""
        bundle = self.stage()
        out_dir = self.edit_dir / "stills"
        out_dir.mkdir(exist_ok=True)
        tag = "" if bg == "light" else f"_{bg}"
        props = {"brand": self.kit.theme, "bg": bg}
        pf = self.edit_dir / "sheet_props.json"
        if kind == "poses":
            pf.write_text(json.dumps(props, ensure_ascii=False))
            out = out_dir / f"poses{tag}.png"
            run(["npx", "remotion", "still", str(bundle), "PoseSheet", str(out), f"--props={pf}", "--log=error"], cwd=MOTION)
            print(f"sheet: {out}")
            return out
        return self._widget_sheet(bundle, aspect or self.aspect, props, pf, out_dir / f"widgets_{(aspect or self.aspect).replace(':', 'x')}{tag}.png")

    def _widget_sheet(self, bundle: Path, aspect: str, props: dict, pf: Path, out: Path) -> Path:
        import numpy as np
        from PIL import Image, ImageDraw

        src = (MOTION / "src/explainer/sheets.tsx").read_text()
        names = re.findall(r'\{ type: "(\w+)"', src[src.index("WIDGET_SAMPLES"):src.index("WIDGET_SEG")])
        seg = int(re.search(r"WIDGET_SEG = (\d+)", src).group(1))
        safe = dict(re.findall(r"(\w+): (\d+)", re.search(rf'"{aspect}": \{{([^}}]*)\}}',
                    (MOTION / "src/layout.ts").read_text().split("SAFE_BY_ASPECT")[1]).group(1)))
        W, H = ASPECTS[aspect]
        x0, y0, x1, y1 = int(safe["left"]), int(safe["top"]), W - int(safe["right"]), H - int(safe["bottom"])
        pf.write_text(json.dumps({**props, "aspect": aspect}, ensure_ascii=False))
        tmp = out.parent / "_widgets"
        tmp.mkdir(exist_ok=True)
        shots = []
        for k in range(len(names) + 1):  # the last one is the empty reference
            p = tmp / f"{k}.png"
            run(["npx", "remotion", "still", str(bundle), "WidgetSheet", str(p), f"--frame={k * seg + seg - 1}",
                 f"--props={pf}", "--log=error"], cwd=MOTION)
            shots.append(np.asarray(Image.open(p).convert("RGB")).astype(int))
        ref = shots.pop()
        outside = np.ones((H, W), bool)
        outside[y0:y1, x0:x1] = False
        bad = []
        for n, im in zip(names, shots):
            leak = (np.abs(im - ref).max(axis=2) > 24) & outside
            if leak.sum() > 20:
                ys, xs = np.nonzero(leak)
                bad.append(f"{n}: {leak.sum()} px outside the safe box (x {xs.min()}–{xs.max()}, y {ys.min()}–{ys.max()})")
        scale = 360 / min(W, H) if W < H else 480 / W
        tw, th = round(W * scale), round(H * scale)
        cols = 5 if W < H else 3
        rows = -(-len(names) // cols)
        sheet = Image.new("RGB", (cols * (tw + 8) + 8, rows * (th + 30) + 8), "#111")
        d = ImageDraw.Draw(sheet)
        for k, (n, im) in enumerate(zip(names, shots)):
            x, y = 8 + (k % cols) * (tw + 8), 8 + (k // cols) * (th + 30)
            sheet.paste(Image.fromarray(im.astype("uint8")).resize((tw, th)), (x, y))
            d.rectangle([x + x0 * scale, y + y0 * scale, x + x1 * scale, y + y1 * scale], outline="#00C2FF", width=2)
            d.text((x, y + th + 6), n, fill="#ddd")
        sheet.save(out)
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"sheet: {out}  ({aspect}, safe box in blue)")
        for b in bad:
            print(f"  ERROR {b}")
        if not bad:
            print(f"  all {len(names)} widgets inside the safe box")
        return out

    def stills(self, times: list[float] | None = None) -> Path:
        """PNG per time (default: each scene once it has settled + each transition midpoint),
        then one labelled contact sheet."""
        if self.check(quiet=True):
            sys.exit("fix the ERRORs from `check` first")
        tl = self.timeline()
        if not times:
            times = []
            for i, ((start, dur), s) in enumerate(zip(tl, self.scenes)):
                if i and self.trans_frames(s):
                    times.append(start + self.trans_frames(s) / self.fps / 2)
                times.append(start + min(dur * 0.7, dur - 0.1))
        bundle = self.stage()
        out_dir = self.edit_dir / "stills"
        shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir()
        last = round(self.total * self.fps) - 1
        paths = []
        for t in times:
            p = out_dir / f"s_{t:06.2f}.png"
            self._remotion(bundle, "still", str(p), f"--frame={min(last, round(t * self.fps))}", "--scale=0.5")
            paths.append((t, p))
        return self._contact(paths, out_dir / "contact.png")

    def _contact(self, paths: list[tuple[float, Path]], out: Path) -> Path:
        from PIL import Image, ImageDraw

        tl = self.timeline()
        ims = [Image.open(p).convert("RGB") for _, p in paths]
        w, h = ims[0].size
        scale = (360 / w) if w < h else (480 / w)
        tw, th = round(w * scale), round(h * scale)
        cols = 6 if w < h else 4
        rows = -(-len(ims) // cols)
        sheet = Image.new("RGB", (cols * (tw + 8) + 8, rows * (th + 36) + 8), "#111")
        d = ImageDraw.Draw(sheet)
        for k, ((t, _), im) in enumerate(zip(paths, ims)):
            x, y = 8 + (k % cols) * (tw + 8), 8 + (k // cols) * (th + 36)
            sheet.paste(im.resize((tw, th)), (x, y))
            idx = max(i for i, (s, _) in enumerate(tl) if s <= t + 1e-6)
            d.text((x, y + th + 6), f"{t:.2f}s  {self.scenes[idx].get('name', self.scenes[idx]['type'])}", fill="#ddd")
        sheet.save(out)
        print(f"contact sheet: {out}")
        return out

    # ── audio ─────────────────────────────────────────────────────────────
    def narration_track(self) -> Path | None:
        """Every narration clip on one mono 48 kHz track, each placed so its voice onset lands on its
        scene's voice start. → edit/audio/narration_track.wav (None if nothing is narrated)."""
        if not self.narrated:
            return None
        tl = self.timeline()
        T = self.audio_len
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-t", str(T), "-i", "anullsrc=r=48000:cl=mono"]
        parts, labels = [], ["[0:a]"]
        for n, (i, nv) in enumerate(sorted(self.narrated.items()), start=1):
            at = tl[i][0] + nv["origin"]  # where the clip's first sample goes on the timeline
            cut = max(0.0, -at)  # a first scene's lead-in can start before 0: trim it instead
            ms = round(max(0.0, at) * 1000)
            cmd += ["-i", str(nv["clip"])]
            parts.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=mono,atrim=start={cut:.4f},"
                         f"asetpts=PTS-STARTPTS,adelay={ms}:all=1[c{n}]")
            labels.append(f"[c{n}]")
        parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first[m]")
        out = self.edit_dir / "audio" / "narration_track.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        run(cmd + ["-filter_complex", ";".join(parts), "-map", "[m]", "-c:a", "pcm_s24le", str(out)])
        return out

    def mix(self) -> Path | None:
        """Voice + music bed (ducked under the voice) + attack-aligned SFX. Loudness-normalised to
        `lufs` when there's a voice or music; SFX-only mixes keep their levels. None = silent."""
        audio = self.sb.get("audio", {})
        voice = self._resolve(audio["voice"]) if audio.get("voice") else None
        voice_start = float(audio.get("voice_start", 0))
        if track := self.narration_track():
            voice, voice_start = track, 0.0
        music = audio.get("music")
        sfx = self.all_sfx()
        if not (voice or music or sfx):
            return None
        T = self.audio_len
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-t", str(T), "-i", "anullsrc=r=48000:cl=stereo"]
        parts, labels, n = [], ["[0:a]"], 1
        if voice:
            ms = round(voice_start * 1000)
            cmd += ["-i", str(voice)]
            parts.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms},asplit=2[vo][vk]")
            labels.append("[vo]")
            n += 1
        if music:
            cmd += ["-stream_loop", "-1", "-i", str(self._resolve(music["file"]))]
            db = music.get("db", -20 if voice else -14)
            parts.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{T},"
                         f"afade=t=in:d=0.4,afade=t=out:st={max(0, T - 1.5)}:d=1.5,volume={db}dB[mu0]")
            if voice and music.get("duck", True):
                parts.append("[mu0][vk]sidechaincompress=threshold=0.02:ratio=6:attack=30:release=450[mu]")
            else:
                parts.append("[mu0]anull[mu]" + (";[vk]anullsink" if voice else ""))
            labels.append("[mu]")
            n += 1
        elif voice:
            parts.append("[vk]anullsink")
        attacks = json.loads((SFX_DIR / "attack.json").read_text())
        for name, t, db in sfx:
            cmd += ["-i", str(SFX_DIR / f"{name}.wav")]
            ms = max(0, round((t - attacks[name]) * 1000))
            parts.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,volume={db}dB,adelay={ms}|{ms}[s{n}]")
            labels.append(f"[s{n}]")
            n += 1
        parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first[m]")
        raw = self.edit_dir / "mix_raw.wav"
        run(cmd + ["-filter_complex", ";".join(parts), "-map", "[m]", "-c:a", "pcm_s24le", str(raw)])
        out = self.edit_dir / "mix.wav"
        if voice or music:
            loudnorm_2pass(raw, out, self.lufs)
        else:
            shutil.copy2(raw, out)
        return out

    # ── render ────────────────────────────────────────────────────────────
    def render(self, preview: bool, export: str | None = None) -> Path:
        if self.check():
            sys.exit("fix the ERRORs above first")
        bundle = self.stage()
        tag = "preview" if preview else "final"
        video = self.edit_dir / (f"story_{tag}" + (".mp4" if preview else ".mov"))
        print(f"  rendering Remotion Story ({self.total:.2f}s)…")
        if preview:
            self._remotion(bundle, "render", str(video), "--codec=h264", "--crf=18")
        else:  # mezzanine; the delivery encode happens once, below
            self._remotion(bundle, "render", str(video), "--codec=prores", "--prores-profile=hq")
        mix = self.mix()
        out = self.edit_dir / f"{tag}.mp4"
        w, h = ASPECTS[self.aspect]
        scale = (["-vf", f"scale={720}:-2:flags=lanczos" if w <= h else f"scale=-2:{720}:flags=lanczos"]
                 if preview else [])
        enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"]
        if not preview:
            enc = list(DELIVERY_X264)
            enc[enc.index("-g") + 1] = str(self.fps)  # 1 s GOP at this storyboard's frame rate
        audio_in = ["-i", str(mix)] if mix else ["-f", "lavfi", "-t", str(self.audio_len),
                                                 "-i", "anullsrc=r=48000:cl=stereo"]
        run(["ffmpeg", "-y", "-i", str(video), *audio_in, "-map", "0:v", "-map", "1:a", *scale, *enc,
             "-pix_fmt", "yuv420p", "-r", str(self.fps), "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
             "-movflags", "+faststart", "-shortest", str(out)])
        dur = _duration(out)
        print(f"wrote {out}  ({dur:.2f}s, planned {self.total:.2f}s)")
        if mix:
            i, tp = loudness(out)
            print(f"  loudness: {i:.1f} LUFS integrated, true peak {tp:.1f} dBTP (target {self.lufs})")
        else:
            print("  audio: silent (no voice, music or SFX in the storyboard)")
        if export:
            dst = REPO / "exports" / f"{self.project}_{export}_{date.today():%Y%m%d}.mp4"
            shutil.copy2(out, dst)
            print(f"  exported {dst.relative_to(REPO)}")
        return out


def _duration(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path, help="edit dir (with storyboard.json) or the storyboard file")
    ap.add_argument("cmd", choices=["check", "voice", "sheet", "stills", "render"])
    ap.add_argument("what", nargs="?", choices=["poses", "widgets"], help="sheet: which contact sheet")
    ap.add_argument("--aspect", choices=list(ASPECTS), help="sheet widgets: aspect to lay out (default: the storyboard's)")
    ap.add_argument("--bg", choices=["light", "dark"], default="light", help="sheet: background tone")
    ap.add_argument("--at", help="stills: comma-separated times in seconds")
    ap.add_argument("--preview", action="store_true", help="render: 720p quick encode")
    ap.add_argument("--export", metavar="PLATFORM", help="render: copy to exports/<project>_<PLATFORM>_<date>.mp4")
    ap.add_argument("--force", action="store_true", help="voice: re-synthesise and re-time every clip")
    a = ap.parse_args()
    st = Story(a.path)
    if a.cmd == "check":
        sys.exit(1 if st.check() else 0)
    if a.cmd == "voice":
        st.voice(a.force)
        sys.exit(1 if st.check() else 0)
    if a.cmd == "sheet":
        st.sheet(a.what or "poses", a.aspect, a.bg)
        return
    if a.cmd == "stills":
        st.stills([float(x) for x in a.at.split(",")] if a.at else None)
    else:
        st.render(a.preview, a.export)


if __name__ == "__main__":
    main()
