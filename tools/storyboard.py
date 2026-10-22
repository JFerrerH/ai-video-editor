"""Videos from scratch: `edit/storyboard.json` → Remotion `Story` → audio mix → MP4.

    uv run tools/storyboard.py footage/<project>/edit check              # timeline + craft warnings
    uv run tools/storyboard.py footage/<project>/edit stills             # contact sheet → edit/stills/contact.png
    uv run tools/storyboard.py footage/<project>/edit stills --at 1.2,4  # specific times (s)
    uv run tools/storyboard.py footage/<project>/edit render --preview   # 720p → edit/preview.mp4
    uv run tools/storyboard.py footage/<project>/edit render             # full res → edit/final.mp4
    uv run tools/storyboard.py footage/<project>/edit render --export reels   # + exports/<project>_reels_<date>.mp4

storyboard.json (see templates/storyboard.json and the motion-graphics skill):
    {"aspect": "9:16"|"16:9"|"1:1"|"4:5", "fps": 30, "brand": "<slug>"|"none", "grain": 0.4,
     "scenes": [{"name", "type", "duration", "bg", "transition": {"type", "duration", "direction"},
                 "props": {...}, "narration": "spoken line", "sfx": [["whoosh", 0.0, -18]]}],
     "events": [{"type", "start", "duration", "props"}],          # global overlays (Flash, Captions…)
     "audio": {"voice": "audio/vo.wav", "voice_start": 0.0,
               "music": {"file": "assets/music/…", "db": -18, "duck": true},
               "sfx": [["click", 4.2, -16]]},                      # absolute times (s)
     "lufs": -14}
Scene `sfx` times are relative to the scene start. Asset paths in props (images…) are relative to
the edit dir, or to the repo root (`assets/…`, `brands/…`); they're staged into edit/motion_public.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from brand import load_brand
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


def _registry(path: Path, block: str) -> set[str]:
    src = path.read_text()
    m = re.search(block + r"[^{]*\{([^}]*)\}", src)
    return set(re.findall(r"\b([A-Z]\w+)\b", m.group(1))) if m else set()


SCENE_TYPES = _registry(MOTION / "src/scenes/index.ts", r"export const SCENES")
OVERLAY_TYPES = _registry(MOTION / "src/Overlay.tsx", r"export const REGISTRY")


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
        self.scenes: list[dict] = self.sb["scenes"]
        self.kit = load_brand(self.sb.get("brand"))
        self.lufs = float(self.sb.get("lufs", -14))
        self.project = self.edit_dir.parent.name

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
            if narr and narr / NARRATION_WPS > dur + 0.2:
                warns.append(f"{name}: narration ({narr} words) needs ~{narr / NARRATION_WPS:.1f}s, scene is {dur:.1f}s")
            if dur > 7:
                warns.append(f"{name}: {dur:.1f}s on one scene. Hold attention with a beat inside it, or split it")
            for a in self._assets(s.get("props", {})):
                if not self._resolve(a):
                    errors.append(f"{name}: asset not found: {a} (relative to edit/ or repo root)")
            tr = (s.get("transition") or {}).get("type", "cut") if i else "—"
            rows.append(f"{i:>2} {start:6.2f} {dur:5.2f}  {t:<13} {s.get('bg', '-'):<7} {tr:<9} {name}")
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
        if audio.get("music") and not self._resolve(audio["music"]["file"]):
            errors.append(f"audio.music not found: {audio['music']['file']}")
        if not quiet:
            w, h = ASPECTS[self.aspect]
            print(f"{self.project}: {self.aspect} {w}x{h} @{self.fps}, brand={self.kit.slug or 'none'}, "
                  f"{len(self.scenes)} scenes, {self.total:.2f}s")
            print(" #  start   dur  type          bg      in        name")
            print("\n".join(rows))
            for x in warns:
                print(f"  WARN  {x}")
            for x in errors:
                print(f"  ERROR {x}")
        return errors

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
        props = {"aspect": self.aspect, "fps": self.fps, "brand": self.kit.theme,
                 "grain": self.sb.get("grain", 0),
                 "scenes": [{k: s[k] for k in keep if k in s} for s in self.scenes],
                 "events": self.sb.get("events", [])}
        (self.edit_dir / "story_props.json").write_text(json.dumps(props, indent=1, ensure_ascii=False))
        bundle = self.edit_dir / "motion_bundle"
        run(["npx", "remotion", "bundle", f"--public-dir={pub}", f"--out-dir={bundle}", "--log=error"], cwd=MOTION)
        return bundle

    def _remotion(self, bundle: Path, *args: str) -> None:
        run(["npx", "remotion", *args[:1], str(bundle), "Story", *args[1:],
             f"--props={self.edit_dir / 'story_props.json'}", "--log=error"], cwd=MOTION)

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
    def mix(self) -> Path | None:
        """Voice + music bed (ducked under the voice) + attack-aligned SFX. Loudness-normalised to
        `lufs` when there's a voice or music; SFX-only mixes keep their levels. None = silent."""
        audio = self.sb.get("audio", {})
        voice = self._resolve(audio["voice"]) if audio.get("voice") else None
        music = audio.get("music")
        sfx = self.all_sfx()
        if not (voice or music or sfx):
            return None
        T = round(self.total, 3)
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-t", str(T), "-i", "anullsrc=r=48000:cl=stereo"]
        parts, labels, n = [], ["[0:a]"], 1
        if voice:
            ms = round(float(audio.get("voice_start", 0)) * 1000)
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
        audio_in = ["-i", str(mix)] if mix else ["-f", "lavfi", "-t", str(round(self.total, 3)),
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
    ap.add_argument("cmd", choices=["check", "stills", "render"])
    ap.add_argument("--at", help="stills: comma-separated times in seconds")
    ap.add_argument("--preview", action="store_true", help="render: 720p quick encode")
    ap.add_argument("--export", metavar="PLATFORM", help="render: copy to exports/<project>_<PLATFORM>_<date>.mp4")
    a = ap.parse_args()
    st = Story(a.path)
    if a.cmd == "check":
        sys.exit(1 if st.check() else 0)
    if a.cmd == "stills":
        st.stills([float(x) for x in a.at.split(",")] if a.at else None)
    else:
        st.render(a.preview, a.export)


if __name__ == "__main__":
    main()
