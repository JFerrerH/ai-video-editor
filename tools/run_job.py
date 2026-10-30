"""Headless job runner: one JSON job in, one JSON result out (for queue workers, CI, scripts).

    uv run tools/run_job.py job.json                 # or: … < job.json, or: echo '{…}' | … -
    uv run tools/run_job.py --self-check             # toolchain report (python, ffmpeg filters, node, backends…)

A job names one operation from a fixed list, the project it works in and its arguments:

    {"op": "inventory", "project": "acme-launch", "args": {}}

stdout gets exactly one JSON object: {"ok", "op", "project", "outputs", "seconds"} plus "error" on
failure (one line; the traceback goes to stderr) and any op-specific fields. `outputs` lists files
created or changed under footage/<project>/ during the job, relative to it. Every log line, including
ffmpeg/Remotion output, goes to stderr. Exit code: 0 ok, 1 the op failed, 2 the job was rejected.

Paths in `args` are relative to footage/<project>/ and must stay inside it after following symlinks
(inputs may also be read from the shared assets/ directory). The project name is kebab-case ASCII.
There is no free-form command: unknown ops or arguments are rejected before anything runs.

Ops (args in brackets are optional):
  inventory        ffprobe every media file directly under the project → edit/inventory.json
  transcribe       source [language model audio_track backend] → edit/transcripts/<stem>.json
  voice            text out [lang preset speed pronounce force backend] → <out>.wav + sidecar
  matte            source start dur out [fps backend] → grey person matte video
  storyboard       cmd=check|voice|sheet|stills|render [storyboard what aspect bg at preview export force]
  conform          [sources frame face] → edit/conformed/<stem>.mov + conform.json (SDR, CFR, 9:16 or source frame)
  pack             [silence] → edit/takes_packed.md (every transcript, phrase by phrase)
  frames           source at [sheet] → edit/frames/<stem>_<t>.png (+ _sheet.png), ≤ 24, ≤ 720 px
  face             sources → suggested face centre + confidence per take (also edit/face.json)
  shortform        cmd=check|stills|render [spec at preview] → from edit/short.json (data only; safe for
                   specs written by untrusted users): check returns errors/warnings/duration, renders loudness
  cut              cmd=check|render [edl preview subtitles] → plain EDL cut at the sources' orientation
                   (video-use render.py), EDL validated first: no raw ffmpeg filters, no outside paths
  shortform.build  [preview] → runs footage/<project>/edit/build.py. It EXECUTES the project's Python:
                   trusted input only; never let end users author build.py for a hosted runner.

    uv run tools/run_job.py --prefetch               # download every model (Docker build, WITH_MODELS=1)
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
FOOTAGE = REPO / "footage"
ASSETS = REPO / "assets"
EXPORTS = REPO / "exports"
sys.path.insert(0, str(TOOLS))

PROJECT_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MEDIA_EXT = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi", ".mxf", ".wav", ".mp3", ".m4a", ".aac",
             ".flac", ".aiff", ".aif", ".png", ".jpg", ".jpeg"}
SKIP_DIRS = {"motion_bundle", "motion_public", "node_modules", "__pycache__"}  # build scratch, not outputs


class JobError(Exception):
    """The job itself is invalid (rejected before anything runs)."""


# ── argument schemas ──────────────────────────────────────────────────────
@dataclass
class Arg:
    type: str  # str | int | float | bool | floats | strs | strmap
    required: bool = False
    default: Any = None
    choices: tuple | None = None
    path: str | None = None  # "in" (must exist; project or assets/) | "out" (inside the project)
    pattern: str | None = None  # regex a str must match in full


def _typed(name: str, spec: Arg, v: Any) -> Any:
    ok = {
        "str": isinstance(v, str),
        "int": isinstance(v, int) and not isinstance(v, bool),
        "float": isinstance(v, (int, float)) and not isinstance(v, bool),
        "bool": isinstance(v, bool),
        "floats": isinstance(v, list) and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v),
        "strs": isinstance(v, list) and all(isinstance(x, str) for x in v),
        "strmap": isinstance(v, dict) and all(isinstance(k, str) and isinstance(x, str) for k, x in v.items()),
    }[spec.type]
    if not ok:
        raise JobError(f"argument {name!r} must be {spec.type}, got {type(v).__name__}")
    if spec.choices is not None and v not in spec.choices:
        raise JobError(f"argument {name!r} must be one of {list(spec.choices)}, got {v!r}")
    if spec.pattern and not re.fullmatch(spec.pattern, v):
        raise JobError(f"argument {name!r} has an invalid value {v!r}")
    return float(v) if spec.type == "float" else v


def confine(root: Path, rel: str, kind: str) -> Path:
    """`rel` resolved against the project root, symlinks followed; must stay inside the root
    (inputs may also come from assets/). Inputs must exist."""
    if not rel or "\x00" in rel:
        raise JobError("empty or invalid path")
    root = root.resolve()
    p = (root / rel).resolve()
    allowed = [root] + ([ASSETS.resolve()] if kind == "in" else [])
    if not any(p == a or p.is_relative_to(a) for a in allowed):
        raise JobError(f"path {rel!r} is outside the project")
    if kind == "in" and not p.exists():
        raise JobError(f"not found: {rel}")
    return p


def check_args(schema: dict[str, Arg], args: Any, root: Path) -> dict[str, Any]:
    if not isinstance(args, dict):
        raise JobError("`args` must be an object")
    if unknown := sorted(set(args) - set(schema)):
        raise JobError(f"unknown argument(s): {', '.join(unknown)}")
    out: dict[str, Any] = {}
    for name, spec in schema.items():
        if name not in args or args[name] is None:
            if spec.required:
                raise JobError(f"missing argument: {name}")
            out[name] = confine(root, spec.default, spec.path) if spec.path and spec.default else spec.default
            continue
        v = _typed(name, spec, args[name])
        if spec.path:
            v = [confine(root, x, spec.path) for x in v] if isinstance(v, list) else confine(root, v, spec.path)
        out[name] = v
    return out


# ── ops ───────────────────────────────────────────────────────────────────
@dataclass
class Op:
    fn: Callable[[Path, dict], dict | None]  # (project root, checked args) → extra result fields
    schema: dict[str, Arg]


def _ffprobe(p: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration,bit_rate:stream=index,codec_type,codec_name,width,height,"
                        "r_frame_rate,sample_rate,channels", "-of", "json", str(p)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {"file": p.name, "error": (r.stderr.strip().splitlines() or ["ffprobe failed"])[-1]}
    d = json.loads(r.stdout or "{}")
    fmt = d.get("format", {})
    return {"file": p.name, "bytes": p.stat().st_size,
            "duration": float(fmt["duration"]) if "duration" in fmt else None,
            "streams": d.get("streams", [])}


def op_inventory(root: Path, a: dict) -> dict:
    files = sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in MEDIA_EXT)
    items = []
    for p in files:
        print(f"  ffprobe {p.name}", flush=True)
        items.append(_ffprobe(p))
    out = root / "edit" / "inventory.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"files": items}, indent=1))
    return {"files": len(items)}


def op_transcribe(root: Path, a: dict) -> dict:
    from transcribe_local import transcribe_one

    out = transcribe_one(a["source"], root / "edit", a["model"], a["language"], a["audio_track"], a["backend"])
    return {"transcript": str(out.relative_to(root))}


def op_voice(root: Path, a: dict) -> dict:
    from gen import voice as V

    if a["out"].suffix.lower() != ".wav":
        raise JobError("`out` must be a .wav file")
    if err := V.validate(a["lang"], a["preset"]):
        raise JobError(err)
    job = V.Job(a["out"], V.spoken(a["text"], a["pronounce"]), a["lang"], a["preset"], a["speed"], a["backend"])
    r = V.synthesize_many([job], force=a["force"])[0]
    return {"cached": r["cached"], "duration": r["duration"], "backend": V.pick_backend(a["backend"])}


def op_matte(root: Path, a: dict) -> dict:
    from person_matte import make_matte, pick_backend

    if a["start"] < 0 or a["dur"] <= 0:
        raise JobError("`start` must be ≥ 0 and `dur` > 0")
    a["out"].parent.mkdir(parents=True, exist_ok=True)
    make_matte(a["source"], a["start"], a["dur"], a["out"], fps=a["fps"], backend=a["backend"])
    return {"backend": pick_backend(a["backend"])}


def op_storyboard(root: Path, a: dict) -> dict:
    from storyboard import Story

    st = Story(a["storyboard"])
    cmd = a["cmd"]
    if cmd == "voice":
        st.voice(a["force"])
    if cmd in ("check", "voice"):
        errs = st.check()
        return {"errors": errs, **({"error": f"{len(errs)} storyboard error(s): {errs[0]}"} if errs else {})}
    if cmd == "sheet":
        st.sheet(a["what"] or "poses", a["aspect"], a["bg"])
    elif cmd == "stills":
        st.stills(a["at"] or None)
    else:
        st.render(a["preview"], a["export"])
    return {}


def op_shortform_build(root: Path, a: dict) -> dict:
    """Runs the project's build.py (Python written by whoever authored the project: trusted input only)."""
    build = root / "edit" / "build.py"
    if not build.exists():
        raise JobError("no edit/build.py in the project (start from templates/shortform_build.py)")
    cmd = ["uv", "run", "--no-sync", str(build), *(["--preview"] if a["preview"] else [])]
    r = subprocess.run(cmd, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    sys.stderr.write(r.stdout)
    if r.returncode != 0:
        tail = [ln for ln in r.stdout.splitlines() if ln.strip()]
        return {"error": f"build.py exited {r.returncode}: {tail[-1] if tail else ''}"}
    return {}


def op_conform(root: Path, a: dict) -> dict:
    from conform import VIDEO_EXT, conform

    faces = {}
    for take, xy in (a["face"] or {}).items():
        try:
            x, y = (float(v) for v in xy.split(","))
        except ValueError:
            raise JobError(f"face {take!r} must be \"x,y\" in source pixels, got {xy!r}") from None
        faces[take] = (x, y)
    if bad := [p.name for p in a["sources"] or [] if p.suffix.lower() not in VIDEO_EXT]:
        raise JobError(f"not a video file: {', '.join(bad)}")
    m = conform(root, a["sources"], a["frame"], faces)
    return {"takes": {k: {f: r[f] for f in ("output", "as_is", "crop", "face", "fps")} for k, r in m["takes"].items()}}


def op_pack(root: Path, a: dict) -> dict:
    if not (root / "edit" / "transcripts").is_dir():
        raise JobError("no edit/transcripts/ yet (run transcribe first)")
    r = subprocess.run(["uv", "run", "--no-sync", str(REPO / "vendor/video-use/helpers/pack_transcripts.py"),
                        "--edit-dir", str(root / "edit"), "--silence-threshold", str(a["silence"])],
                       cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    sys.stderr.write(r.stdout)
    if r.returncode != 0:
        return {"error": f"pack_transcripts exited {r.returncode}: {r.stdout.strip().splitlines()[-1:]}"}
    return {}


def op_frames(root: Path, a: dict) -> dict:
    from frames import MAX_TIMES, frames

    if not 1 <= len(a["at"]) <= MAX_TIMES:
        raise JobError(f"`at` needs 1–{MAX_TIMES} times")
    frames(a["source"], a["at"], root / "edit" / "frames", a["sheet"])
    return {}


def op_face(root: Path, a: dict) -> dict:
    from face_centre import suggest

    faces = {p.stem: suggest(p) for p in a["sources"]}
    out = root / "edit" / "face.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(faces, indent=1))
    return {"faces": faces}


def op_shortform(root: Path, a: dict) -> dict:
    import short_spec as S
    from shortform import loudness

    spec = a["spec"]
    if spec.is_dir() or spec.suffix != ".json":
        raise JobError("`spec` must be a .json file (default edit/short.json)")
    if a["cmd"] == "check":
        res = S.check(spec, root)
        out = {k: res[k] for k in ("errors", "warnings", "duration", "timeline")}
        return {**out, **({"error": f"{len(res['errors'])} spec error(s): {res['errors'][0]}"} if res["errors"] else {})}
    try:
        p, rep = S.load(spec, root)
    except S.SpecError as e:
        return {"errors": e.errors, "error": f"{len(e.errors)} spec error(s): {e.errors[0]}"}
    if a["cmd"] == "stills":
        p.stills(a["at"] or None, preview=True)
        return {"duration": rep["duration"]}
    out = p.build(a["preview"])
    lufs, tp = loudness(out)
    return {"duration": rep["duration"], "video": str(out.resolve().relative_to(root)), "lufs": lufs, "true_peak": tp}


def op_cut(root: Path, a: dict) -> dict:
    import cut_edl
    from shortform import loudness

    edl, errors = cut_edl.resolve(a["edl"], root)
    if errors:
        if a["cmd"] == "check":
            return {"errors": errors, "error": f"{len(errors)} EDL error(s): {errors[0]}"}
        raise JobError(f"{len(errors)} EDL error(s): {errors[0]}")
    if a["cmd"] == "check":
        return {"errors": [], "duration": edl["total_duration_s"], "ranges": len(edl["ranges"])}
    resolved = root / "edit" / "edl_resolved.json"  # render.py reads transcripts next to the EDL
    resolved.write_text(json.dumps(edl, indent=1))
    out = root / "edit" / "cut" / ("preview.mp4" if a["preview"] else "final.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["uv", "run", "--no-sync", str(REPO / "vendor/video-use/helpers/render.py"), str(resolved), "-o", str(out)]
    cmd += ["--preview"] if a["preview"] else []
    cmd += {"build": ["--build-subtitles"], "none": ["--no-subtitles"]}.get(a["subtitles"], [])
    r = subprocess.run(cmd, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    sys.stderr.write(r.stdout)
    if r.returncode != 0:
        tail = [ln for ln in r.stdout.splitlines() if ln.strip()]
        return {"error": f"render.py exited {r.returncode}: {tail[-1] if tail else ''}"}
    lufs, tp = loudness(out)
    return {"duration": edl["total_duration_s"], "video": str(out.resolve().relative_to(root)), "lufs": lufs, "true_peak": tp}


REPO_ID = r"(?!.*\.\.)[A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*"  # a Hub repo id, never a local path
LANG = r"[a-z]{2}(-[A-Za-z0-9]+)?"
ASPECT = ("9:16", "16:9", "1:1", "4:5")

OPS: dict[str, Op] = {
    "inventory": Op(op_inventory, {}),
    "transcribe": Op(op_transcribe, {
        "source": Arg("str", required=True, path="in"),
        "language": Arg("str", pattern=LANG),
        "model": Arg("str", pattern=REPO_ID),
        "audio_track": Arg("int", default=0),
        "backend": Arg("str", choices=("auto", "mlx", "faster-whisper")),
    }),
    "voice": Op(op_voice, {
        "text": Arg("str", required=True),
        "out": Arg("str", required=True, path="out"),
        "lang": Arg("str", default="en", pattern=LANG),
        "preset": Arg("str", pattern=r"[a-z]{2}_[a-z]+"),
        "speed": Arg("float", default=1.0),
        "pronounce": Arg("strmap"),
        "force": Arg("bool", default=False),
        "backend": Arg("str", choices=("auto", "mlx", "torch")),
    }),
    "matte": Op(op_matte, {
        "source": Arg("str", required=True, path="in"),
        "start": Arg("float", required=True),
        "dur": Arg("float", required=True),
        "out": Arg("str", required=True, path="out"),
        "fps": Arg("int", default=30, choices=(24, 25, 30, 50, 60)),
        "backend": Arg("str", choices=("auto", "vision", "mediapipe")),
    }),
    "storyboard": Op(op_storyboard, {
        "cmd": Arg("str", required=True, choices=("check", "voice", "sheet", "stills", "render")),
        "storyboard": Arg("str", default="edit", path="in"),
        "what": Arg("str", choices=("poses", "widgets")),
        "aspect": Arg("str", choices=ASPECT),
        "bg": Arg("str", default="light", choices=("light", "dark")),
        "at": Arg("floats"),
        "preview": Arg("bool", default=False),
        "export": Arg("str", pattern=r"[a-z0-9]+(-[a-z0-9]+)*"),
        "force": Arg("bool", default=False),
    }),
    "conform": Op(op_conform, {
        "sources": Arg("strs", path="in"),
        "frame": Arg("str", default="9:16", choices=("9:16", "source")),
        "face": Arg("strmap"),
    }),
    "pack": Op(op_pack, {
        "silence": Arg("float", default=0.5),
    }),
    "frames": Op(op_frames, {
        "source": Arg("str", required=True, path="in"),
        "at": Arg("floats", required=True),
        "sheet": Arg("bool", default=False),
    }),
    "face": Op(op_face, {
        "sources": Arg("strs", required=True, path="in"),
    }),
    "shortform": Op(op_shortform, {
        "cmd": Arg("str", required=True, choices=("check", "stills", "render")),
        "spec": Arg("str", default="edit/short.json", path="in"),
        "at": Arg("floats"),
        "preview": Arg("bool", default=False),
    }),
    "cut": Op(op_cut, {
        "cmd": Arg("str", required=True, choices=("check", "render")),
        "edl": Arg("str", default="edit/edl.json", path="in"),
        "preview": Arg("bool", default=False),
        "subtitles": Arg("str", default="edl", choices=("edl", "build", "none")),
    }),
    "shortform.build": Op(op_shortform_build, {
        "preview": Arg("bool", default=False),
    }),
}


# ── running a job ─────────────────────────────────────────────────────────
def _snapshot(*dirs: Path) -> dict[Path, tuple[int, int]]:
    snap = {}
    for d in dirs:
        if not d.is_dir():
            continue
        for dp, dns, fns in os.walk(d):
            dns[:] = [n for n in dns if n not in SKIP_DIRS]
            for f in fns:
                p = Path(dp) / f
                with contextlib.suppress(OSError):
                    st = p.stat()
                    snap[p] = (st.st_mtime_ns, st.st_size)
    return snap


def _one_line(msg: str) -> str:
    lines = [ln.strip() for ln in str(msg).strip().splitlines() if ln.strip()]
    return (lines[0] if lines else "failed")[:500]


def validate(job: Any) -> tuple[Op, Path, dict]:
    if not isinstance(job, dict):
        raise JobError("the job must be a JSON object")
    if unknown := sorted(set(job) - {"op", "project", "args"}):
        raise JobError(f"unknown job field(s): {', '.join(unknown)}")
    op, project = job.get("op"), job.get("project")
    if op not in OPS:
        raise JobError(f"unknown op {op!r}; use one of: {', '.join(OPS)}")
    if not isinstance(project, str) or not PROJECT_RE.fullmatch(project):
        raise JobError(f"invalid project name {project!r} (kebab-case ASCII, e.g. acme-launch)")
    root = (FOOTAGE / project).resolve()
    if not root.is_dir():
        raise JobError(f"project not found: footage/{project}")
    return OPS[op], root, check_args(OPS[op].schema, job.get("args", {}), root)


def run(job: Any) -> tuple[dict, int]:
    """Validate and run one job; never raises. Returns (result, exit code)."""
    t0 = time.time()
    op = job.get("op") if isinstance(job, dict) else None
    project = job.get("project") if isinstance(job, dict) else None
    res: dict[str, Any] = {"ok": False, "op": op, "project": project, "outputs": [], "seconds": 0.0}
    try:
        spec, root, args = validate(job)
    except JobError as e:
        res.update(error=_one_line(str(e)), seconds=round(time.time() - t0, 3))
        return res, 2
    print(f"[run_job] {op} in footage/{project}", file=sys.stderr, flush=True)
    before = _snapshot(root, EXPORTS)
    code = 1
    try:
        extra = spec.fn(root, args) or {}
        res.update(extra)
        res["ok"] = not res.get("error")
        code = 0 if res["ok"] else 1
    except JobError as e:  # argument checks that need the op's own module
        res["error"], code = _one_line(str(e)), 2
    except SystemExit as e:  # the tools report user errors with sys.exit("message")
        if e.code in (None, 0):
            res["ok"], code = True, 0
        else:
            res["error"] = _one_line(e.code if isinstance(e.code, str) else f"exit status {e.code}")
    except Exception as e:  # noqa: BLE001 - every failure becomes a result
        traceback.print_exc(file=sys.stderr)
        res["error"] = _one_line(f"{type(e).__name__}: {e}")
    after = _snapshot(root, EXPORTS)
    changed = sorted(p for p, sig in after.items() if before.get(p) != sig)
    res["outputs"] = [str(p.relative_to(root)) for p in changed if p.is_relative_to(root)]
    if exported := [str(p.relative_to(REPO)) for p in changed if p.is_relative_to(EXPORTS)]:
        res["exports"] = exported
    res["seconds"] = round(time.time() - t0, 3)
    return res, code


@contextlib.contextmanager
def stdout_to_stderr():
    """Route fd 1 (and sys.stdout) to stderr while a job runs, so subprocess output can't mix
    into the result; yields a writer for the real stdout."""
    sys.stdout.flush()
    saved = os.dup(1)
    os.dup2(2, 1)
    real = os.fdopen(os.dup(saved), "w")
    try:
        with contextlib.redirect_stdout(sys.stderr):
            yield real
    finally:
        sys.stderr.flush()
        os.dup2(saved, 1)
        os.close(saved)


# ── self-check ────────────────────────────────────────────────────────────
def _cmd_ok(cmd: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    out = (r.stdout or r.stderr).strip().splitlines()
    return r.returncode == 0, out[0] if out else ""


def _load_backend(backend: str) -> str | None:
    """Actually load the backend's packages (and native libraries), not just find them: a missing
    system library only shows up here. None if it loads, else the error."""
    try:
        if backend == "mediapipe":  # its native library is only dlopen'd when a task is created
            from mediapipe.tasks.python.core import mediapipe_c_bindings

            mediapipe_c_bindings.load_raw_library()
        else:
            for mod in {"mlx": ["mlx_whisper", "mlx_audio"], "faster-whisper": ["faster_whisper"],
                        "torch": ["kokoro", "misaki"], "vision": []}[backend]:
                __import__(mod)
    except Exception as e:  # noqa: BLE001
        return _one_line(f"{type(e).__name__}: {e}")
    return None


def self_check() -> list[dict]:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("python", sys.version_info[:2] == (3, 12), sys.version.split()[0])
    ok, _ = _cmd_ok(["ffmpeg", "-hide_banner", "-version"])
    if ok:
        flt = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        names = {ln.split()[1] for ln in flt.splitlines() if len(ln.split()) > 2}
        missing = [f for f in ("subtitles", "ass", "drawtext") if f not in names]
        add("ffmpeg filters", not missing, "missing: " + ", ".join(missing) if missing else "subtitles, ass, drawtext")
    else:
        add("ffmpeg filters", False, "ffmpeg not found")
    add("ffprobe", bool(shutil.which("ffprobe")), shutil.which("ffprobe") or "not found")
    ok, v = _cmd_ok(["node", "--version"])
    add("node", ok, v or "not found")
    motion = TOOLS / "motion"
    if not (motion / "node_modules" / "@remotion" / "renderer").is_dir():
        add("remotion browser", False, "run `npm ci` in tools/motion")
    else:
        shells = [p for name in ("chrome-headless-shell", "headless_shell")  # macOS / Linux binary name
                  for p in (motion / "node_modules" / ".remotion").glob(f"chrome-headless-shell/*/*/{name}")]
        add("remotion browser", bool(shells),
            str(shells[0].relative_to(motion)) if shells else "run `npx remotion browser ensure` in tools/motion")
    ok, v = _cmd_ok(["auto-editor", "--version"])
    add("auto-editor", ok, v or "not found")
    helpers = REPO / "vendor" / "video-use" / "helpers"
    add("video-use helpers", (helpers / "pack_transcripts.py").exists(),
        str(helpers.relative_to(REPO)) if helpers.is_dir() else "missing: run scripts/setup.sh (or the Docker build)")
    for name, mod in (("transcription backend", "transcribe_local"), ("voice backend", "gen.voice"),
                      ("matte backend", "person_matte")):
        try:
            m = __import__(mod, fromlist=["pick_backend"])
            b = m.pick_backend(None)
            err = m.backend_missing(b) or _load_backend(b)
            add(name, err is None, b if err is None else f"{b}: {err}")
        except (ImportError, AttributeError) as e:
            add(name, False, str(e))
    return checks


# ── prefetch ──────────────────────────────────────────────────────────────
def prefetch() -> list[dict]:
    """Download every model the platform's backends use (Whisper turbo, Kokoro weights + every voice
    preset, the MediaPipe segmenter), then warm each one up once so nothing is fetched lazily later."""
    import tempfile

    from huggingface_hub import snapshot_download

    import person_matte as PM
    import transcribe_local as T
    from gen import voice as V

    done: list[dict] = []
    tb = T.pick_backend(None)
    if T.backend_missing(tb) is None:
        print(f"  whisper: {T.BACKENDS[tb][0]}", flush=True)
        snapshot_download(T.BACKENDS[tb][0])
        done.append({"name": "transcription", "model": T.BACKENDS[tb][0]})
    vb = V.pick_backend(None)
    if V.backend_missing(vb) is None:
        mid = V.model_id(vb)
        weights = ["config.json", "kokoro-v1_0.pth" if vb == "torch" else "kokoro-v1_0.safetensors"]
        print(f"  voice: {mid} + {len(V.PRESETS)} presets", flush=True)
        snapshot_download(mid, allow_patterns=weights + [f"voices/{p}.*" for p in V.PRESETS])
        done.append({"name": "voice", "model": mid, "presets": len(V.PRESETS)})
    mb = PM.pick_backend(None)
    if mb == "mediapipe" and PM.backend_missing(mb) is None:
        done.append({"name": "matte", "model": str(PM.fetch_segmenter())})
    if any(d["name"] == "voice" for d in done):  # warm-up: misaki/spaCy/espeak paths + word timing
        with tempfile.TemporaryDirectory() as td:
            jobs = [V.Job(Path(td) / f"{lang}.wav", text, lang) for lang, text in
                    (("en", "Every scene starts with one clear idea."), ("es", "Una idea clara."))]
            V.synthesize_many(jobs)
            if any(d["name"] == "transcription" for d in done):
                T.transcribe_one(jobs[0].out, Path(td), None, "en", 0)
    return done


# ── CLI ───────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", nargs="?", help="job JSON file, or - (default) for stdin")
    ap.add_argument("--self-check", action="store_true", help="report the toolchain and backends; exit 1 if any is missing")
    ap.add_argument("--prefetch", action="store_true", help="download (and warm up) every model the backends use")
    a = ap.parse_args()

    with stdout_to_stderr() as out:
        if a.prefetch:
            t0 = time.time()
            try:
                res, code = {"ok": True, "op": "prefetch", "models": prefetch()}, 0
            except Exception as e:  # noqa: BLE001
                traceback.print_exc(file=sys.stderr)
                res, code = {"ok": False, "op": "prefetch", "error": _one_line(f"{type(e).__name__}: {e}")}, 1
            res["seconds"] = round(time.time() - t0, 3)
        elif a.self_check:
            checks = self_check()
            for c in checks:
                print(f"  {'ok ' if c['ok'] else 'MISSING'}  {c['name']:<22} {c['detail']}")
            ok = all(c["ok"] for c in checks)
            res, code = {"ok": ok, "op": "self-check", "checks": checks}, 0 if ok else 1
        else:
            try:
                raw = Path(a.job).read_text() if a.job and a.job != "-" else sys.stdin.read()
                job = json.loads(raw)
            except (OSError, ValueError) as e:
                job = None
                res, code = {"ok": False, "op": None, "project": None, "outputs": [], "seconds": 0.0,
                             "error": _one_line(f"can't read the job: {e}")}, 2
            if job is not None:
                res, code = run(job)
        out.write(json.dumps(res, ensure_ascii=False) + "\n")
        out.flush()
    sys.exit(code)


if __name__ == "__main__":
    main()
