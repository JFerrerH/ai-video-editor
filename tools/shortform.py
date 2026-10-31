"""Short-form edit engine: talking-head cut + zooms + B&W/freeze looks + Remotion
overlay + karaoke captions + SFX mix, following video-use's hard rules.

A project's `edit/build.py` only holds data (segments, overlay events, SFX) and
calls `Project(...).build()`. See `.claude/skills/short-form-pro/SKILL.md`.

Pipeline:
  1. per-segment extract (grade, look, face-centred zoom, freeze, 30ms fades)
  2. lossless concat → base
  3. Remotion `Overlay` composition (transparent ProRes 4444) from events JSON
  4. dialogue + SFX (attack-aligned) → two-pass loudnorm
  5. final: base ⊕ overlay → karaoke ASS captions LAST → H.264/AAC
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from brand import load_brand
from person_matte import make_matte

REPO = Path(__file__).resolve().parent.parent
MOTION = REPO / "tools" / "motion"
SFX_DIR = REPO / "assets" / "sfx" / "synth"

FUNCTION_WORDS = {
    # es
    "de", "que", "por", "la", "el", "y", "en", "un", "una", "me", "se", "les", "a", "mi",
    "los", "las", "con", "para", "nos", "si", "tú", "esa", "lo", "es", "del", "al",
    "unos", "unas", "nuestra", "nuestro", "nuestras", "nuestros", "su", "sus", "tus", "mis",
    "este", "esta", "primer",
    # en
    "the", "a", "an", "of", "to", "and", "in", "on", "for", "with", "my", "is", "that",
}


def stage(src: Path, dst: Path) -> None:
    """Copy `src` to `dst` unless `dst` is already that file (same size and mtime, which copy2 keeps).
    Not "dst is newer": a different file staged under the same name (another kit's font) must be replaced."""
    s = Path(src).stat()
    if dst.exists() and (d := dst.stat()).st_size == s.st_size and abs(d.st_mtime - s.st_mtime) < 0.001:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def run(cmd: list[str], cwd: Path | None = None) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        raise SystemExit(f"FAILED: {' '.join(map(str, cmd))}\n{(r.stderr or r.stdout)[-4000:]}")
    return r.stderr


# ── zoom expressions (zoompan `it` = segment-local seconds) ───────────────
def _ease_out(u: str) -> str:
    return f"(1-pow(1-clip({u},0,1),3))"


def _ease_io(u: str) -> str:
    c = f"clip({u},0,1)"
    return f"if(lt({c},0.5),4*pow({c},3),1-pow(-2*{c}+2,3)/2)"


def zoom_expr(z: tuple, dur: float) -> str:
    """z (times are SOURCE seconds, localized by the caller):
    ("static", s) | ("push", a, b) | ("punch", base, peak, at) | ("outpunch", a, b, peak, at)"""
    kind = z[0]
    if kind == "push":
        a, b = z[1], z[2]
        return f"{a}+({b - a})*{_ease_io(f'it/{dur:.3f}')}"
    if kind == "punch":
        base, peak, at = z[1:4]
        return f"{base}+({peak - base})*{_ease_out(f'(it-{at:.3f})/0.18')}"
    if kind == "outpunch":
        a, b, peak, at = z[1:5]
        return f"{a}+({b - a})*{_ease_out('it/0.30')}+({peak - b})*{_ease_out(f'(it-{at:.3f})/0.18')}"
    raise ValueError(kind)


# Final delivery for Instagram Reels / TikTok: platforms re-encode everything, so give them a
# clean high-bitrate master at the SOURCE frame rate (30 fps footage → 30 fps; upsampling to 60
# only duplicates frames). High profile, BT.709 tags, 1 s GOP, VBV-capped so huge peaks don't
# trigger extra platform compression.
DELIVERY_X264 = [
    "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-profile:v", "high", "-level:v", "4.2",
    "-g", "30", "-bf", "2", "-maxrate", "25M", "-bufsize", "50M",
    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
    # the flags above can be dropped through a filter graph; write them into the H.264 VUI too
    "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
]

LOOKS = {
    None: "",
    "bw": "hue=s=0,eq=contrast=1.12:brightness=-0.02",
}


HDR_TRANSFERS = {"arib-std-b67", "smpte2084"}  # HLG, PQ


def probe_video(path: Path) -> dict:
    """Display size (rotation applied), transfer and frame rate of a file's first video stream."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,color_transfer,color_primaries,color_space,r_frame_rate,avg_frame_rate"
                        ":stream_side_data=rotation",
                        "-of", "json", str(path)], capture_output=True, text=True)
    st = (json.loads(r.stdout or "{}").get("streams") or [{}])[0]
    w, h = st.get("width", 0), st.get("height", 0)
    rot = next((abs(int(d["rotation"])) for d in st.get("side_data_list", []) if "rotation" in d), 0)
    if rot % 180 == 90:
        w, h = h, w
    # the container can say bt709 while the frames carry HLG/PQ: the first frame's tags win when they're HDR
    fr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-read_intervals", "%+#1",
                         "-show_entries", "frame=color_transfer,color_primaries,color_space", "-of", "json", str(path)],
                        capture_output=True, text=True).stdout
    f0 = (json.loads(fr or "{}").get("frames") or [{}])[0]
    hdr = f0.get("color_transfer") in HDR_TRANSFERS
    pick = lambda k: (f0 if hdr and f0.get(k) else st).get(k, "unknown")  # noqa: E731
    return {"width": w, "height": h, "transfer": pick("color_transfer"),
            "primaries": pick("color_primaries"), "matrix": pick("color_space"),
            "r_frame_rate": st.get("r_frame_rate"), "avg_frame_rate": st.get("avg_frame_rate")}


def source_problem(info: dict) -> str | None:
    """Why a source can't go into the 1080x1920 work frame as is (None = it can)."""
    w, h = info["width"], info["height"]
    if not w or not h:
        return "has no video stream"
    if info["transfer"] in HDR_TRANSFERS:
        return f"is HDR ({info['transfer']}); conform it to SDR first (conform op / tools/conform.py)"
    if w > h:
        return f"is horizontal ({w}x{h}); conform it to 9:16 first (conform op / tools/conform.py)"
    if abs(w / h - 9 / 16) > 0.01 * 9 / 16:
        return f"is {w}x{h}, not 9:16; conform it to 9:16 first (conform op / tools/conform.py)"
    return None


@dataclass
class Seg:
    take: str
    t_in: float
    t_out: float
    zoom: tuple = ("static", 1.0)
    look: str | None = None
    freeze_after: float = 0.0  # hold the last frame (silent) — e.g. record-scratch beat
    note: str = ""
    lock_in: bool = False  # refine_edges() leaves a hand-verified edge alone
    lock_out: bool = False

    @property
    def dur(self) -> float:
        return self.t_out - self.t_in

    @property
    def out_dur(self) -> float:
        return round(self.dur * 30) / 30 + round(self.freeze_after * 30) / 30


@dataclass
class Project:
    edit_dir: Path
    sources: dict[str, Path]
    face: dict[str, tuple[int, int]]  # face centre per take, source px
    segments: list[Seg]
    events: list[dict] = field(default_factory=list)  # Remotion overlay events (output seconds)
    sfx: list[tuple[str, float, float]] = field(default_factory=list)  # (name, contact t, gain dB)
    # brand slug → brands/<slug>/brand.json (theme, fonts, caption style); None/"none" → neutral.
    # A dict is used as the Remotion theme as-is (fonts then go in public_files by hand).
    brand: str | dict | None = None
    public_files: dict[str, Path] = field(default_factory=dict)  # name in public/ → source file
    grade: str = "eq=contrast=1.04:saturation=1.03"
    fps: int = 30
    caption_fixes: dict[str, str] = field(default_factory=dict)
    # one-off fixes for a single word (a global caption_fixes entry would also change every other
    # "del" etc.): {(take, word start in source seconds ±0.02): "text"}
    caption_word_fixes: dict[tuple[str, float], str] = field(default_factory=dict)
    caption_style: dict = field(default_factory=dict)
    # "remotion": progressive serif captions (Captions component, top overlay layer)
    # "ass":      legacy karaoke ASS burned in ffmpeg
    caption_engine: str = "remotion"
    # key phrases rendered heavier/larger in the brand's emphColor: (take, "phrase words", after_source_seconds)
    emphasis: list[tuple[str, str, float]] = field(default_factory=list)
    caption_props: dict = field(default_factory=dict)  # overrides for the Captions component
    # words cut out of the audio whose (drifted) Whisper stamps still overlap a segment, e.g. a
    # drawn-out "y" dropped at an in-point: (take, word start in source seconds ±0.02)
    caption_skip: list[tuple[str, float]] = field(default_factory=list)
    lufs: float = -14.0

    def __post_init__(self) -> None:
        if not isinstance(self.brand, dict):
            kit = load_brand(self.brand)
            self.brand = kit.theme
            self.public_files = {**kit.public_files, **self.public_files}  # project files win
            self.caption_props = {**kit.caption_props, **self.caption_props}

    def source_info(self, take: str) -> dict:
        cache = self.__dict__.setdefault("_probe_cache", {})
        if take not in cache:
            cache[take] = probe_video(self.sources[take])
        return cache[take]

    def source_errors(self) -> list[str]:
        """Sources the engine can't use as is (any SDR 9:16 size works; others need conform)."""
        return [f"source {take} ({Path(self.sources[take]).name}) {why}" for take in self.sources
                if (why := source_problem(self.source_info(take)))]

    # ── timeline ──────────────────────────────────────────────────────────
    def offsets(self) -> list[float]:
        offs, t = [], 0.0
        for s in self.segments:
            offs.append(t)
            t += s.out_dur
        offs.append(t)
        return offs

    def at(self, take: str, src_t: float) -> float:
        """Map a source time (e.g. a word start) to the output timeline."""
        offs = self.offsets()
        for i, s in enumerate(self.segments):
            if s.take == take and s.t_in - 0.02 <= src_t <= s.t_out + 0.02:
                return offs[i] + max(0.0, src_t - s.t_in)
        # Whisper stamps segment-initial words early, into silence we trimmed:
        # snap to the start of the segment that begins just after.
        for i, s in enumerate(self.segments):
            if s.take == take and s.t_in - 0.4 <= src_t < s.t_in:
                return offs[i]
        raise ValueError(f"{take}@{src_t} is not in the cut")

    # ── edge refinement (never clip a word) ───────────────────────────────
    def _env(self, take: str):
        """RMS envelope in dB, 5 ms hop / 20 ms window, cached per take."""
        import numpy as np
        cache = getattr(self, "_env_cache", {})
        if take not in cache:
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(self.sources[take]), "-ac", "1",
                                  "-ar", "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
            x = np.frombuffer(raw, "<i2").astype(np.float32) / 32768
            hop, win = 80, 320
            n = max(1, (len(x) - win) // hop)
            frames = np.lib.stride_tricks.sliding_window_view(x, win)[::hop][:n]
            db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
            floor = float(np.percentile(db, 10))
            cache[take] = (db, floor)
            self._env_cache = cache
        return cache[take]

    def refine_edges(self, pre: float = 0.10, post: float = 0.12, min_sil: float = 0.06,
                     above_floor: float = 9.0, apply: bool = True) -> list[str]:
        """Snap every in/out point to measured silence so no word is clipped.

        Speech = envelope above (noise floor + `above_floor` dB; breaths/room tone sit below). In-points move into the silence
        just before the onset (`pre` s of air); out-points move past the word's decay
        (`post` s of air) but never into the next sound. Edges with no usable silence
        within reach are left alone and reported as WARN — check those by ear/eye.
        """
        hop = 0.005
        report = []
        for i, s in enumerate(self.segments):
            db, floor = self._env(s.take)
            quiet = db < floor + above_floor
            n = len(db)

            def runs(a: float, b: float):
                """Silence runs (start_s, end_s) of ≥ min_sil overlapping [a, b]."""
                lo, hi = max(0, int(a / hop)), min(n, int(b / hop))
                out, k = [], lo
                while k < hi:
                    if quiet[k]:
                        j = k
                        while j < n and quiet[j]:
                            j += 1
                        k0 = k
                        while k0 > 0 and quiet[k0 - 1]:
                            k0 -= 1
                        if (j - k0) * hop >= min_sil:
                            out.append((k0 * hop, j * hop))
                        k = j
                    else:
                        k += 1
                return out

            # IN: silence run whose end (= speech onset) is closest to the current in-point
            new_in, tag_in = s.t_in, "ok"
            cand = runs(s.t_in - 0.5, s.t_in + 0.15)
            if s.t_in <= 0.02:
                cand = cand or [(0.0, s.t_in)]
            if cand:
                r0, r1 = min(cand, key=lambda r: abs(r[1] - s.t_in))
                # only ever widen: never move an in-point later (soft onsets sit near the threshold)
                new_in = min(s.t_in, max(r0 + 0.02 if r0 > 0 else 0.0, r1 - pre))
            else:
                tag_in = "WARN no silence before onset"

            # OUT: first silence run at/after the current out-point (minus a little)
            new_out, tag_out = s.t_out, "ok"
            cand = [r for r in runs(s.t_out - 0.05, s.t_out + 0.6) if r[1] > s.t_out - 0.05]
            if cand:
                r0, r1 = cand[0]
                if r0 <= s.t_out:  # already in silence: keep, but give the decay its air
                    new_out = min(max(s.t_out, r0 + post), r1 - 0.04)
                else:  # current out cuts into sound → extend past it
                    new_out = max(s.t_out, min(r0 + post, r1 - 0.04))
            else:
                tag_out = "WARN no silence after word"

            if s.lock_in:
                new_in, tag_in = s.t_in, "locked"
            if s.lock_out:
                new_out, tag_out = s.t_out, "locked"
            line = (f"seg {i:02d} {s.take} in {s.t_in:6.2f}→{new_in:6.2f} [{tag_in}]  "
                    f"out {s.t_out:6.2f}→{new_out:6.2f} [{tag_out}]  {s.note[:40]}")
            report.append(line)
            if apply:
                s.t_in, s.t_out = round(new_in, 3), round(new_out, 3)
        return report

    def edge_energy(self) -> list[str]:
        """dB above noise floor in the 30 ms just inside each edge (should be ~0 = silence)."""
        out = []
        for i, s in enumerate(self.segments):
            db, floor = self._env(s.take)
            a, b = int(s.t_in / 0.005), int(s.t_out / 0.005)
            head = float(db[a:a + 6].max() - floor)
            tail = float(db[max(0, b - 6):b].max() - floor)
            flag = "  <-- check" if head > 9 or tail > 9 else ""
            out.append(f"seg {i:02d} head +{head:4.1f} dB  tail +{tail:4.1f} dB{flag}")
        return out

    def word(self, take: str, text: str, after: float = 0.0, end: bool = False) -> float:
        """Output time of the first word matching `text` at/after source time `after`."""
        for w in self._words(take):
            if w["start"] >= after - 0.01 and _norm(w["text"]) == _norm(text):
                return self.at(take, w["end"] if end else w["start"])
        raise ValueError(f"word {text!r} not found in {take} after {after}")

    def _words(self, take: str) -> list[dict]:
        p = self.edit_dir / "transcripts" / f"{take}.json"
        return [w for w in json.loads(p.read_text())["words"] if w["type"] == "word"]

    # ── 1. segments ───────────────────────────────────────────────────────
    def _vf(self, s: Seg, w: int, h: int) -> str:
        info = self.source_info(s.take)
        if why := source_problem(info):
            raise SystemExit(f"source {s.take} {why}")
        cx, cy = self.face[s.take]
        # any 9:16 size: work in a 1080x1920 frame (face centre is in source px)
        k_src = 1080 / info["width"]
        fit = "" if (info["width"], info["height"]) == (1080, 1920) else "scale=1080:1920:flags=lanczos,"
        if fit:
            cx, cy = round(cx * k_src), round(cy * k_src)
        look = LOOKS[s.look]
        post = ",".join(x for x in (self.grade, look) if x)
        hold = f",tpad=stop_mode=clone:stop_duration={s.freeze_after:.3f}" if s.freeze_after else ""
        z = s.zoom
        if z[0] == "static":
            sc = z[1]
            cw, ch = round(1080 / sc / 2) * 2, round(1920 / sc / 2) * 2
            x = max(0, min(1080 - cw, cx - cw // 2))
            y = max(0, min(1920 - ch, cy - ch // 2))
            return (f"setpts=PTS-STARTPTS,{fit}crop={cw}:{ch}:{x}:{y},scale={w}:{h}:flags=lanczos,"
                    f"{post},fps={self.fps}{hold},format=yuv420p")
        # localize punch anchors to segment time
        if z[0] == "punch":
            z = (z[0], z[1], z[2], z[3] - s.t_in)
        elif z[0] == "outpunch":
            z = (z[0], z[1], z[2], z[3], z[4] - s.t_in)
        k = 2  # zoompan rounds to whole pixels → upscale first to halve jitter
        ex = f"max(0,min(iw-iw/zoom,{cx * k}-iw/zoom/2))"
        ey = f"max(0,min(ih-ih/zoom,{cy * k}-ih/zoom/2))"
        return (f"setpts=PTS-STARTPTS,scale={1080 * k}:{1920 * k}:flags=bicubic,"
                f"zoompan=z='{zoom_expr(z, s.dur)}':x='{ex}':y='{ey}':d=1:s={w}x{h}:fps={self.fps},"
                f"{post}{hold},format=yuv420p")

    def extract(self, preview: bool) -> list[Path]:
        w, h = (720, 1280) if preview else (1080, 1920)
        d = self.edit_dir / ("clips_preview" if preview else "clips_graded")
        d.mkdir(exist_ok=True)
        paths = []
        for i, s in enumerate(self.segments):
            # Exact length: N video frames and N*(48000/fps) audio samples, so offsets()
            # matches the concat and overlays/captions/SFX never drift.
            n = round(s.out_dur * self.fps)
            af = (f"afade=t=in:st=0:d=0.03,afade=t=out:st={s.dur - 0.03:.3f}:d=0.03,"
                  f"apad,atrim=end_sample={n * 48000 // self.fps}")
            p = d / f"seg_{i:02d}.mov"
            # -t is an INPUT option here so tpad/apad can extend the output (freeze frames)
            run(["ffmpeg", "-y", "-ss", f"{s.t_in:.3f}", "-t", f"{s.dur:.3f}", "-i", str(self.sources[s.take]),
                 "-vf", self._vf(s, w, h), "-af", af, "-frames:v", str(n),
                 "-c:v", "libx264", "-preset", "veryfast" if preview else "medium",
                 "-crf", "20" if preview else "14", "-r", str(self.fps),
                 "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(p)])
            paths.append(p)
            print(f"  seg {i:02d} {s.take} {s.t_in:6.2f}-{s.t_out:6.2f} {s.zoom[0]:8s} {s.look or ''} {s.note}")
        return paths

    def concat(self, paths: list[Path], out: Path) -> None:
        lst = self.edit_dir / "concat.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in paths))
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])

    # ── 3. Remotion overlay ───────────────────────────────────────────────
    def stage_overlay(self) -> tuple[Path, Path]:
        """Copy assets into a per-project Remotion public dir and write the props JSON."""
        pub = self.edit_dir / "motion_public"
        pub.mkdir(exist_ok=True)
        for name, src in self.public_files.items():
            stage(src, pub / name)
        events = [e for e in self.events if not e.get("props", {}).get("behind")]
        if self.caption_engine == "remotion":
            events.append(self.caption_event())  # LAST = top layer (captions above every overlay)
        props = {"durationInSeconds": round(self.offsets()[-1], 3), "brand": self.brand,
                 "events": events}
        pj = self.edit_dir / "overlay_props.json"
        pj.write_text(json.dumps(props, indent=1, ensure_ascii=False))
        return pub, pj

    def overlay_stills(self, times: list[float], out_dir: Path) -> list[Path]:
        """Render overlay frames at output times (s) as PNGs for a quick visual check."""
        pub, pj = self.stage_overlay()
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for t in times:
            p = (out_dir / f"ov_{t:06.2f}.png").resolve()  # remotion runs with cwd=tools/motion
            run(["npx", "remotion", "still", "Overlay", str(p), f"--props={pj}", f"--public-dir={pub}",
                 f"--frame={round(t * self.fps)}", "--scale=0.5", "--log=error"], cwd=MOTION)
            paths.append(p)
        return paths

    def stills(self, times: list[float] | None = None, preview: bool = True) -> list[Path]:
        """Frames of the FINISHED short (cut + zoom/look, overlays, captions, behind-the-speaker
        layers) at output times, without rendering the video: one source frame through the
        segment's own filter, one Remotion still per layer, one ffmpeg composite each.
        Default: the middle of every segment. → edit/stills/short_<t>.png (540x960 preview, else 1080x1920)."""
        offs = self.offsets()
        total = offs[-1]
        times = times if times else [round(offs[i] + s.out_dur / 2, 3) for i, s in enumerate(self.segments)]
        if bad := [t for t in times if not 0 <= t < total]:
            raise ValueError(f"still time(s) {bad} outside the short (0–{total:.2f} s)")
        w, h = (540, 960) if preview else (1080, 1920)
        out_dir = self.edit_dir / "stills"
        tmp = out_dir / "_layers"
        tmp.mkdir(parents=True, exist_ok=True)
        pub, pj = self.stage_overlay()
        scale = "--scale=0.5" if preview else "--scale=1"

        def remotion_still(props: Path, t: float, dst: Path) -> None:
            run(["npx", "remotion", "still", "Overlay", str(dst.resolve()), f"--props={props}", f"--public-dir={pub}",
                 f"--frame={min(round(t * self.fps), round(total * self.fps) - 1)}", scale, "--log=error"], cwd=MOTION)

        paths = []
        for t in times:
            i = max(k for k in range(len(self.segments)) if offs[k] <= t + 1e-9)
            s = self.segments[i]
            local = min(t - offs[i], max(0.0, s.dur - 1 / self.fps))  # inside a freeze: its held frame
            base = tmp / f"base_{t:06.2f}.png"
            run(["ffmpeg", "-y", "-ss", f"{s.t_in:.3f}", "-t", f"{s.dur:.3f}", "-i", str(self.sources[s.take]),
                 "-vf", f"{self._vf(s, w, h)},trim=start={local:.4f}", "-frames:v", "1", str(base)])
            ov = tmp / f"ov_{t:06.2f}.png"
            remotion_still(pj, t, ov)
            inputs, parts, cur = ["-i", str(base)], [], "[0:v]"
            behind = [e for e in self.events if e.get("props", {}).get("behind")
                      and e["start"] <= t < e["start"] + e["duration"]]
            if behind:
                matte = tmp / f"matte_{t:06.2f}.mov"
                make_matte(base, 0, 1 / self.fps, matte, fps=self.fps)
                inputs += ["-i", str(matte)]
                parts += [f"[1:v]scale={w}:{h},format=gray[m]", "[0:v]format=yuva420p[sp]", "[sp][m]alphamerge[pm]"]
                for k, e in enumerate(behind):
                    pk = tmp / f"behind_{t:06.2f}_{k}.json"
                    pk.write_text(json.dumps({"durationInSeconds": round(total, 3), "brand": self.brand, "events": [e]},
                                             ensure_ascii=False))
                    layer = tmp / f"behind_{t:06.2f}_{k}.png"
                    remotion_still(pk, t, layer)
                    inputs += ["-i", str(layer)]
                    parts.append(f"{cur}[{len(inputs) // 2 - 1}:v]overlay=0:0:format=auto[b{k}]")
                    cur = f"[b{k}]"
                parts.append(f"{cur}[pm]overlay=0:0:format=auto[sp2]")
                cur = "[sp2]"
            inputs += ["-i", str(ov)]
            parts.append(f"{cur}[{len(inputs) // 2 - 1}:v]overlay=0:0:format=auto")
            dst = out_dir / f"short_{t:06.2f}.png"
            run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(parts), "-frames:v", "1", str(dst)])
            paths.append(dst)
        shutil.rmtree(tmp, ignore_errors=True)
        return paths

    def render_overlay(self, preview: bool, out: Path) -> None:
        pub, pj = self.stage_overlay()
        cmd = ["npx", "remotion", "render", "Overlay", str(out), f"--props={pj}",
               f"--public-dir={pub}", "--codec=prores", "--prores-profile=4444",
               "--pixel-format=yuva444p10le", "--image-format=png", "--log=error"]
        run(cmd, cwd=MOTION)  # always 1080x1920; ffmpeg scales it to the base for previews

    def render_behind(self, base: Path, tag: str, reuse_layer: bool, reuse_matte: bool) -> list[tuple[float, float, Path, Path]]:
        """Events with `props.behind: true` go UNDER the speaker: each is rendered on its own
        (only its frames) plus a person matte of the base for the same window. build() stacks
        base → this layer → matted speaker → the main overlay."""
        out = []
        pub, _ = self.stage_overlay()
        total = round(self.offsets()[-1], 3)
        for k, e in enumerate(e for e in self.events if e.get("props", {}).get("behind")):
            f0 = round(e["start"] * self.fps)
            f1 = f0 + round(e["duration"] * self.fps) - 1
            t0, dur = f0 / self.fps, (f1 - f0 + 1) / self.fps
            layer = self.edit_dir / f"overlay_behind_{k}.mov"
            matte = self.edit_dir / f"matte_{tag}_{k}.mov"
            if not (reuse_layer and layer.exists()):
                pj = self.edit_dir / f"overlay_behind_{k}.json"
                pj.write_text(json.dumps({"durationInSeconds": total, "brand": self.brand, "events": [e]},
                                         ensure_ascii=False))
                run(["npx", "remotion", "render", "Overlay", str(layer), f"--props={pj}", f"--public-dir={pub}",
                     f"--frames={f0}-{f1}", "--codec=prores", "--prores-profile=4444",
                     "--pixel-format=yuva444p10le", "--image-format=png", "--log=error"], cwd=MOTION)
            if not (reuse_matte and matte.exists()):  # the matte only changes with the cut
                make_matte(base, t0, dur, matte, fps=self.fps)
            out.append((t0, t0 + dur, layer, matte))
        return out

    # ── 4. audio ──────────────────────────────────────────────────────────
    def mix_audio(self, base: Path, out: Path) -> None:
        attacks = json.loads((SFX_DIR / "attack.json").read_text())
        cmd = ["ffmpeg", "-y", "-i", str(base)]
        parts = []
        for j, (name, t, db) in enumerate(self.sfx):
            cmd += ["-i", str(SFX_DIR / f"{name}.wav")]
            ms = max(0, round((t - attacks[name]) * 1000))
            parts.append(f"[{j + 1}:a]volume={db}dB,adelay={ms}|{ms}[s{j}]")
        labels = "".join(f"[s{j}]" for j in range(len(self.sfx)))
        fc = ";".join(parts + [f"[0:a]{labels}amix=inputs={len(self.sfx) + 1}:normalize=0:duration=first[m]"])
        raw = self.edit_dir / "mix_raw.wav"
        run(cmd + ["-filter_complex", fc, "-map", "[m]", "-c:a", "pcm_s24le", str(raw)])
        loudnorm_2pass(raw, out, self.lufs)

    def sfx_check(self, min_gap: float = 0.3) -> list[str]:
        """Effects closer than `min_gap` s read as clutter (two hits on one beat). Typing
        beds are exempt (they run under other sounds by design)."""
        ev = sorted((t, n) for n, t, _ in self.sfx if n != "typing")
        return [f"SFX {a[1]}@{a[0]:.2f} and {b[1]}@{b[0]:.2f} are {b[0] - a[0]:.2f}s apart"
                for a, b in zip(ev, ev[1:]) if b[0] - a[0] < min_gap]

    # ── 5. captions ───────────────────────────────────────────────────────
    def output_words(self) -> list[dict]:
        offs = self.offsets()
        best: dict[tuple[str, int], tuple[float, int]] = {}
        W = {k: self._words(k) for k in self.sources}
        for i, s in enumerate(self.segments):
            for j, w in enumerate(W[s.take]):
                if any(t == s.take and abs(w["start"] - x) <= 0.02 for t, x in self.caption_skip):
                    continue
                ov = min(w["end"], s.t_out) - max(w["start"], s.t_in)
                if ov > min(0.06, 0.5 * (w["end"] - w["start"])) and ov > best.get((s.take, j), (0, -1))[0]:
                    best[(s.take, j)] = (ov, i)
        out = []
        for (take, j), (_, i) in best.items():
            w, s = W[take][j], self.segments[i]
            text = next((v for (t, x), v in self.caption_word_fixes.items()
                         if t == take and abs(w["start"] - x) <= 0.02), w["text"])
            out.append({"text": text, "seg": i, "take": take, "src": w["start"],
                        "start": max(w["start"], s.t_in) - s.t_in + offs[i],
                        "end": min(w["end"], s.t_out) - s.t_in + offs[i]})
        out.sort(key=lambda w: w["start"])
        merged: list[dict] = []
        for w in out:  # re-join tokens Whisper split ("pa" + "'lante", "80" + "%")
            if merged and (w["text"].startswith("'") or w["text"] in {"%", "%."}):
                merged[-1]["text"] += w["text"]
                merged[-1]["end"] = w["end"]
            else:
                merged.append(dict(w))
        return merged

    def clean(self, word: str) -> str:
        core = re.sub(r"[.,]+$", "", word.strip())
        return self.caption_fixes.get(core.lower(), core)

    def chunks(self, words: list[dict], max_words: int = 4, max_chars: int = 17) -> list[list[dict]]:
        phrases: list[list[dict]] = [[]]
        for i, w in enumerate(words):
            phrases[-1].append(w)
            nxt = words[i + 1] if i + 1 < len(words) else None
            if nxt and (re.search(r"[.,?!]$", w["text"]) or nxt["start"] - w["end"] >= 0.25
                        or nxt["seg"] != w["seg"]
                        # a key phrase is always alone on screen: break on entering/leaving it
                        or (w.get("emph") or 0) != (nxt.get("emph") or 0)):
                phrases.append([])
        res = []
        for ph in phrases:
            k = 0
            while k < len(ph):
                fits = [n for n in range(1, min(max_words, len(ph) - k) + 1)
                        if n == 1 or sum(len(self.clean(x["text"])) + 1 for x in ph[k:k + n]) - 1 <= max_chars]
                # never split an emphasis phrase across chunks
                whole = [n for n in fits if k + n == len(ph)
                         or not (ph[k + n - 1].get("emph") and ph[k + n - 1].get("emph") == ph[k + n].get("emph"))]
                fits = whole or fits
                good = [n for n in fits if k + n == len(ph)
                        or self.clean(ph[k + n - 1]["text"]).lower() not in FUNCTION_WORDS]
                n = max(good) if good else max(fits)
                if k + n == len(ph) - 1 and self.clean(ph[-1]["text"]).lower() in FUNCTION_WORDS:
                    n += 1
                res.append(ph[k:k + n])
                k += n
        return res

    def _emph_flags(self, words: list[dict]) -> list[int]:
        """Group id (>0) for words inside an `emphasis` phrase, else 0."""
        flags = [0] * len(words)
        for gid, (take, phrase, after) in enumerate(self.emphasis, 1):
            toks = [_norm(t) for t in phrase.split()]
            for i in range(len(words) - len(toks) + 1):
                win = words[i:i + len(toks)]
                if (win[0]["take"] == take and win[0]["src"] >= after - 0.01
                        and [_norm(self.clean(w["text"])) for w in win] == toks):
                    for k in range(i, i + len(toks)):
                        flags[k] = gid
                    break
            else:
                raise ValueError(f"emphasis phrase not found in the cut: {phrase!r} ({take} after {after})")
        return flags

    def caption_event(self) -> dict:
        """Progressive captions for the Remotion `Captions` component.

        caption_props["mode"]: "phrase" (default) = short phrases that build word by word;
        "word" = one word on screen at a time (each replaces the last), except key phrases,
        which stay together as one chunk."""
        words = self.output_words()
        flags = self._emph_flags(words)
        for w, f in zip(words, flags):
            w["emph"] = f
        if self.caption_props.get("mode") == "word":
            chunks: list[list[dict]] = []
            for w in words:
                if w["emph"] and chunks and chunks[-1][-1]["emph"] == w["emph"]:
                    chunks[-1].append(w)
                else:
                    chunks.append([w])
        else:
            chunks = self.chunks(words, max_words=6, max_chars=30)
            # isolating key phrases can strand a lone "en" / "a la" right before one:
            # fold function-word-only chunks into the previous plain chunk of the same segment
            merged: list[list[dict]] = []
            for c in chunks:
                prev = merged[-1] if merged else None
                if (prev and not c[0].get("emph") and not prev[0].get("emph") and prev[-1]["seg"] == c[0]["seg"]
                        and all(self.clean(w["text"]).lower() in FUNCTION_WORDS for w in c)):
                    prev.extend(c)
                else:
                    merged.append(list(c))
            chunks = merged
        cap_words, cap_chunks = [], []
        for k, c in enumerate(chunks):
            for w in c:
                cap_words.append({"t": round(w["start"], 3), "text": self.clean(w["text"]),
                                  "emph": int(w["emph"]), "chunk": k})
            end = c[-1]["end"] + 0.5
            if k + 1 < len(chunks):
                end = min(end, chunks[k + 1][0]["start"]) if chunks[k + 1][0]["start"] - c[-1]["end"] > 0.6 \
                    else chunks[k + 1][0]["start"]
            cap_chunks.append({"start": round(c[0]["start"] - 0.03, 3), "end": round(end, 3)})
        light = [[e["start"], round(e["start"] + e["duration"], 3)] for e in self.events
                 if e.get("props", {}).get("full") and not e["props"].get("dark")]
        total = round(self.offsets()[-1], 3)
        return {"type": "Captions", "start": 0, "duration": total, "name": "Captions",
                "props": {"words": cap_words, "chunks": cap_chunks, "lightRanges": light, **self.caption_props}}

    # text keys whose content a viewer reads on screen (code lines / emails are decoration)
    ECHO_KEYS = {"label", "stamp", "title", "chip", "note", "kicker", "year", "text", "docTitle",
                 "emphasis", "success", "button", "handle", "items", "lines_", "photos", "screens"}

    def echo_check(self, window: float = 1.0) -> list[str]:
        """Graphics must COMPLEMENT the captions, never repeat them. Flags any content word
        (or number) shown by an overlay that is also captioned within ±window s of it."""
        words = self.output_words()

        def texts(obj, key=""):
            if isinstance(obj, str):
                if key in self.ECHO_KEYS:
                    yield obj
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    yield from texts(v, k if k in self.ECHO_KEYS else key)
            elif isinstance(obj, list):
                for v in obj:
                    yield from texts(v, key)

        out = []
        for e in self.events:
            a, b = e["start"] - window, e["start"] + e["duration"] + window
            spoken = {_norm(self.clean(w["text"])) for w in words if a <= w["start"] <= b}
            shown = {_norm(t) for s in texts(e.get("props", {})) for t in re.split(r"[\s·/\n]+", s)}
            hits = sorted(t for t in shown & spoken
                          if t and (t.isdigit() or t.endswith("%") or (len(t) > 3 and t not in FUNCTION_WORDS)))
            if hits:
                out.append(f"ECHO {e['type']} @ {e['start']:.2f}s shows {hits} while the captions say them")
        return out

    def build_ass(self, out: Path) -> None:
        st = {"font": "Avenir Next Heavy", "size": 84, "outline": 6, "shadow": 2, "margin_v": 640,
              "active": "&H3FD2FF&", "base": "&HFFFFFF&", **self.caption_style}
        head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{st['font']},{st['size']},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,{st['outline']},{st['shadow']},2,140,170,{st['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = []
        cs = self.chunks(self.output_words())
        for k, c in enumerate(cs):
            c_end = c[-1]["end"] + 0.12
            if k + 1 < len(cs):
                nxt = cs[k + 1][0]["start"]
                c_end = nxt if nxt - c[-1]["end"] < 0.45 else min(c_end, nxt)
            for i, w in enumerate(c):  # karaoke: one event per active word
                a = c[0]["start"] if i == 0 else w["start"]
                b = c[i + 1]["start"] if i + 1 < len(c) else c_end
                if b - a < 0.02:
                    continue
                txt = []
                for j, x in enumerate(c):
                    t = self.clean(x["text"]).upper()
                    txt.append(f"{{\\c{st['active']}}}{t}{{\\c{st['base']}}}" if j == i else t)
                pop = r"{\fscx88\fscy88\t(0,90,\fscx100\fscy100)}" if i == 0 else ""
                lines.append(f"Dialogue: 1,{_ts(a)},{_ts(b)},Cap,,0,0,0,,{pop}{' '.join(txt)}")
        out.write_text(head + "\n".join(lines) + "\n")

    # ── all ───────────────────────────────────────────────────────────────
    def build(self, preview: bool, skip_extract: bool = False, skip_overlay: bool = False) -> Path:
        tag = "preview" if preview else "final"
        print(f"planned duration: {self.offsets()[-1]:.2f}s, {len(self.segments)} segments, "
              f"{len(self.events)} overlay events, {len(self.sfx)} sfx")
        d = self.edit_dir / ("clips_preview" if preview else "clips_graded")
        paths = ([d / f"seg_{i:02d}.mov" for i in range(len(self.segments))]
                 if skip_extract else self.extract(preview))
        base = self.edit_dir / f"base_{tag}.mov"
        self.concat(paths, base)
        overlay = self.edit_dir / "overlay.mov"  # same 1080p render for preview and final
        if not (skip_overlay and overlay.exists()):
            print("  rendering Remotion overlay…")
            self.render_overlay(preview, overlay)
        behind = self.render_behind(base, tag, reuse_layer=skip_overlay, reuse_matte=skip_extract)
        mix = self.edit_dir / f"mix_{tag}.wav"
        self.mix_audio(base, mix)
        out = self.edit_dir / f"{tag}.mp4"
        w, h = (720, 1280) if preview else (1080, 1920)
        # behind-the-speaker layers: base → layer → base cut out by the person matte (same window)
        extra, parts, cur = [], [], "[0:v]"
        if behind:
            parts.append("[0:v]split=" + str(len(behind) + 1) + "[bg]" + "".join(f"[sp{k}]" for k in range(len(behind))))
            cur = "[bg]"
        for k, (t0, t1, layer, matte) in enumerate(behind):
            li, mi = 3 + 2 * k, 4 + 2 * k
            extra += ["-i", str(layer), "-i", str(matte)]
            parts += [f"[{li}:v]scale={w}:{h}:flags=lanczos,setpts=PTS-STARTPTS+{t0:.4f}/TB[bl{k}]",
                      f"{cur}[bl{k}]overlay=0:0:eof_action=pass:format=auto[bb{k}]",
                      f"[sp{k}]trim=start={t0:.4f}:end={t1:.4f},setpts=PTS-STARTPTS,format=yuva420p[pp{k}]",
                      f"[{mi}:v]scale={w}:{h},format=gray,setpts=PTS-STARTPTS[m{k}]",
                      f"[pp{k}][m{k}]alphamerge,setpts=PTS-STARTPTS+{t0:.4f}/TB[pm{k}]",
                      f"[bb{k}][pm{k}]overlay=0:0:eof_action=pass:format=auto[cb{k}]"]
            cur = f"[cb{k}]"
        fc = ";".join(parts + [f"[1:v]scale={w}:{h}:flags=lanczos[ov]"]) + f";{cur}[ov]overlay=0:0:format=auto"
        if self.caption_engine == "ass":  # legacy: burn karaoke ASS after the overlay (captions LAST)
            ass = self.edit_dir / "captions.ass"
            self.build_ass(ass)
            ass_arg = str(ass).replace(":", r"\:").replace("'", r"\'")
            fc += f",ass='{ass_arg}'"
        fc += "[v]"  # remotion engine: captions are already the top layer of the overlay
        run(["ffmpeg", "-y", "-i", str(base), "-i", str(overlay), "-i", str(mix), *extra,
             "-filter_complex", fc, "-map", "[v]", "-map", "2:a",
             *(["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"] if preview else DELIVERY_X264),
             "-pix_fmt", "yuv420p", "-r", str(self.fps),
             "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(out)])
        print(f"wrote {out}")
        return out


def loudnorm_2pass(raw: Path, out: Path, lufs: float, tp: float = -1.5) -> None:
    """Two-pass linear loudnorm to `lufs` integrated, true peak ≤ `tp` dBTP, 48 kHz 24-bit."""
    target = f"I={lufs}:TP={tp}:LRA=11"
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(raw), "-af",
               f"loudnorm={target}:print_format=json", "-f", "null", "-"])
    m = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
    ln = (f"loudnorm={target}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
          f"offset={m['target_offset']}:linear=true,aresample=48000")
    run(["ffmpeg", "-y", "-i", str(raw), "-af", ln, "-c:a", "pcm_s24le", str(out)])


def loudness(path: Path) -> tuple[float, float]:
    """(integrated LUFS, true peak dBTP) of a file's audio, via ebur128."""
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true",
               "-f", "null", "-"])
    summary = err[err.rindex("Summary:"):]
    i = float(re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summary).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary).group(1))
    return i, tp


def _norm(s: str) -> str:
    return re.sub(r"[^\wáéíóúñü%]", "", s.lower())


def _ts(t: float) -> str:
    cs = round(max(0.0, t) * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def main() -> None:
    """CLI for a data-only short (`edit/short.json`, see tools/short_spec.py):

        uv run tools/shortform.py check  footage/<project>/edit/short.json
        uv run tools/shortform.py stills footage/<project>/edit/short.json [--at 1.5 4.2]
        uv run tools/shortform.py render footage/<project>/edit/short.json [--preview]
    """
    import argparse
    import sys

    import short_spec as S

    ap = argparse.ArgumentParser(description=main.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("check", "stills", "render"))
    ap.add_argument("spec", type=Path, nargs="?", default=Path("edit/short.json"))
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--at", type=float, nargs="+", help="output times for stills (default: each segment's middle)")
    a = ap.parse_args()
    if a.cmd == "check":
        res = S.check(a.spec)
        print("\n".join(res["timeline"] + [""] + res["edges"]))
        for w in res["warnings"]:
            print(f"WARN  {w}")
        for e in res["errors"]:
            print(f"ERROR {e}")
        if res["duration"] is not None:
            print(f"planned duration: {res['duration']:.2f}s")
        sys.exit(1 if res["errors"] else 0)
    try:
        p, rep = S.load(a.spec)
    except S.SpecError as e:
        sys.exit("\n".join(f"ERROR {x}" for x in e.errors))
    print("\n".join(rep["edges"]))
    if a.cmd == "stills":
        for path in p.stills(a.at, preview=True):
            print(f"wrote {path}")
    else:
        out = p.build(a.preview)
        print("loudness: {:.1f} LUFS, {:.1f} dBTP".format(*loudness(out)))


if __name__ == "__main__":
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
