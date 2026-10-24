"""One client for the paid generators on fal.ai: key, model registry, estimate, budget, spend log.

    uv run --group cloud tools/gen/fal.py models                         # registry: endpoints, durations, prices
    uv run --group cloud tools/gen/fal.py total footage/<p>/edit         # spend so far (edit/gen_spend.jsonl)

Used by keyframes.py, animate.py and library.py; nothing here sends a request on import. The key is
`FAL_API_KEY` (or `FAL_KEY`) from the environment or `vendor/video-use/.env`; it is never printed or
logged. Every run goes through `plan()` first: it prints the request count and the estimate at listed
prices, and stops before anything is sent if the estimate is over the run's `--budget` (default $2).
Each finished request appends one line to `gen_spend.jsonl` next to the outputs (project `edit/` or
a brand library). Prices are the provider's listed prices: the log says "estimated", never "charged";
check the fal.ai dashboard for real billing.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENV = REPO / "vendor" / "video-use" / ".env"
KEY_VARS = ("FAL_API_KEY", "FAL_KEY")
DEFAULT_BUDGET = 2.0
SPEND_LOG = "gen_spend.jsonl"
INSTALL_HINT = "uv run --group cloud …"
NEGATIVE = ("morphing, melting, extra limbs, extra fingers, deformed face, changing character design, text, "
            "watermark, blur, flicker, low quality")


@dataclass(frozen=True)
class Model:
    name: str
    endpoint: str
    kind: str  # "video" (image-to-video) or "image" (image edit)
    image_param: str  # start image (video) or list of reference images (image)
    durations: str | tuple[int, ...] = ()  # "any" (float seconds within min/max) or the allowed whole seconds
    min_dur: float = 0.0
    max_dur: float = 0.0
    dur_as: type = float  # how the API wants `duration`: float or str ("5")
    usd_per_s: float = 0.0
    usd_per_image: float = 0.0
    resolution: str = ""
    extra: dict = field(default_factory=dict)  # fixed arguments sent with every request
    verified: bool = False  # held characters on-model in a workspace A/B
    note: str = ""

    def fit(self, need: float) -> float:
        """Duration to request so the clip is at least `need` s long. Any-duration models get `need`
        rounded up to 0.01 s; fixed lists get the smallest allowed value that covers it."""
        if self.durations == "any":
            if need > self.max_dur + 1e-9:
                raise ValueError(f"needs {need:.2f}s, {self.name} makes at most {self.max_dur:g}s")
            return max(self.min_dur, math.ceil(round(need * 100, 6)) / 100)
        for d in sorted(self.durations):
            if d >= need - 1e-9:
                return float(d)
        raise ValueError(f"needs {need:.2f}s, {self.name} makes at most {max(self.durations)}s")

    def cost(self, dur: float | None = None, n: int = 1) -> float:
        return n * self.usd_per_image if self.kind == "image" else (dur or 0.0) * self.usd_per_s

    def video_args(self, image_url: str, prompt: str, dur: float) -> dict:
        d = self.dur_as(int(dur)) if self.dur_as is str else round(dur, 2)
        return {self.image_param: image_url, "prompt": prompt, "duration": d, **self.extra}

    def durations_text(self) -> str:
        if self.durations == "any":
            return f"any {self.min_dur:g}–{self.max_dur:g}s"
        ds = sorted(self.durations)
        if len(ds) > 2 and ds == list(range(ds[0], ds[-1] + 1)):
            return f"{ds[0]}–{ds[-1]}s whole"
        return "/".join(str(d) for d in ds) + "s"


# Listed prices from fal.ai/pricing (checked 2026-10-24). Kling 3.0 Standard has no listed price:
# it is estimated at the Pro price so the budget errs high.
MODELS: dict[str, Model] = {m.name: m for m in [
    Model("minimax-h3-turbo", "minimax/h3-max-turbo/image-to-video", "video", "image_url", "any", 1.0, 20.0,
          float, 0.015, resolution="768P (768x1344)",
          extra={"resolution": "768P", "prompt_expansion_mode": "disabled"}, verified=True,
          note="default: cheapest that held characters on-model; any duration; clips can run ~0.7 s long"),
    Model("kling-2.5-turbo", "fal-ai/kling-video/v2.5-turbo/pro/image-to-video", "video", "image_url", (5, 10),
          dur_as=str, usd_per_s=0.07, resolution="1080x1920", extra={"negative_prompt": NEGATIVE}, verified=True,
          note="stronger acting, 1080p; 5 or 10 s only"),
    Model("kling-3-pro", "fal-ai/kling-video/v3/pro/image-to-video", "video", "start_image_url", tuple(range(3, 16)),
          dur_as=str, usd_per_s=0.14, resolution="1080x1920",
          extra={"negative_prompt": NEGATIVE, "generate_audio": False}, verified=True,
          note="best acting, slowest; 3–15 s whole seconds"),
    Model("kling-3-std", "fal-ai/kling-video/v3/standard/image-to-video", "video", "start_image_url",
          tuple(range(3, 16)), dur_as=str, usd_per_s=0.14, resolution="720x1280",
          extra={"negative_prompt": NEGATIVE, "generate_audio": False},
          note="720p only; price unlisted, estimated at the Pro price"),
    Model("nano-banana-edit", "fal-ai/nano-banana/edit", "image", "image_urls", usd_per_image=0.0398,
          extra={"output_format": "png"}, verified=True, note="keyframes: edit with reference stills"),
]}
DEFAULT_VIDEO = "minimax-h3-turbo"
DEFAULT_IMAGE = "nano-banana-edit"


def model(name: str, kind: str = "video") -> Model:
    m = MODELS.get(name)
    if m is None or m.kind != kind:
        names = ", ".join(k for k, v in MODELS.items() if v.kind == kind)
        raise SystemExit(f"unknown {kind} model {name!r}; registered: {names}")
    return m


# ── key ────────────────────────────────────────────────────────────────────
def read_key(env_file: Path = ENV) -> str | None:
    for var in KEY_VARS:
        if os.environ.get(var, "").strip():
            return os.environ[var].strip()
    try:
        lines = env_file.read_text().splitlines()
    except OSError:
        return None
    for line in lines:
        k, _, v = line.partition("=")
        if k.strip().removeprefix("export ").strip() in KEY_VARS and v.strip().strip("\"'"):
            return v.strip().strip("\"'")
    return None


def load_key(env_file: Path = ENV) -> None:
    """Put the key where fal_client looks (FAL_KEY) or stop, naming what to set. Never prints it."""
    key = read_key(env_file)
    if not key:
        rel = env_file.relative_to(REPO) if env_file.is_relative_to(REPO) else env_file
        raise SystemExit(f"no fal.ai key: set FAL_API_KEY in {rel} (or the environment); nothing was sent")
    os.environ["FAL_KEY"] = key


def client(env_file: Path = ENV):
    """The fal_client module, with the key loaded. Call only after plan() has passed."""
    load_key(env_file)
    try:
        import fal_client
    except ImportError:
        raise SystemExit(f"fal-client isn't installed; run the tool with: {INSTALL_HINT}") from None
    return fal_client


# ── estimate and budget ────────────────────────────────────────────────────
@dataclass
class Request:
    tool: str
    model: Model
    shot: str
    out: Path
    dur: float | None = None  # requested seconds (video)
    n: int = 1  # images per request (image)

    @property
    def usd(self) -> float:
        return self.model.cost(self.dur, self.n)


def plan(requests: list[Request], budget: float = DEFAULT_BUDGET, out=None) -> tuple[int, float]:
    """Print the request count and estimate; stop before anything is sent if it's over `budget`."""
    out = out or sys.stdout
    n, usd = len(requests), sum(r.usd for r in requests)
    names = ", ".join(sorted({r.model.name for r in requests})) or "-"
    print(f"plan: {n} request{'s' * (n != 1)} on {names}, estimated ${usd:.2f} at listed prices "
          f"(budget ${budget:.2f})", file=out, flush=True)
    if usd > budget + 1e-9:
        raise SystemExit(f"estimate ${usd:.2f} is over the budget ${budget:.2f}; nothing was sent. "
                         f"Raise it with --budget {math.ceil(usd * 100) / 100:.2f} if that's intended")
    return n, usd


def add_budget_arg(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--budget", type=float, default=DEFAULT_BUDGET,
                    help=f"stop before sending if the run's estimate is over this many USD (default {DEFAULT_BUDGET:g})")


# ── requests ───────────────────────────────────────────────────────────────
class Uploads:
    """Upload each local file once per run."""

    def __init__(self, fal):
        self.fal, self.urls, self.lock = fal, {}, threading.Lock()

    def __call__(self, path: Path) -> str:
        path = Path(path).resolve()
        with self.lock:
            if path not in self.urls:
                self.urls[path] = self.fal.upload_file(str(path))
            return self.urls[path]


def subscribe(fal, m: Model, arguments: dict) -> dict:
    return fal.subscribe(m.endpoint, arguments=arguments, with_logs=False)


def download(url: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(out)
    return out


# ── spend log ──────────────────────────────────────────────────────────────
_LOG_LOCK = threading.Lock()


def log_spend(log: Path, r: Request, seconds: float | None = None, outs: list[Path] | None = None) -> None:
    line = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": r.tool, "model": r.model.name, "shot": r.shot,
            "dur": r.dur, "n": r.n, "est_usd": round(r.usd, 4),
            "out": [str(p) for p in outs] if outs and len(outs) > 1 else str((outs or [r.out])[0]),
            "seconds": None if seconds is None else round(seconds, 1)}
    with _LOG_LOCK, open(log, "a") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def total(log: Path) -> tuple[int, float]:
    n, usd = 0, 0.0
    try:
        for raw in log.read_text().splitlines():
            if raw.strip():
                n, usd = n + 1, usd + float(json.loads(raw).get("est_usd", 0))
    except OSError:
        pass
    return n, usd


def print_total(log: Path) -> None:
    n, usd = total(log)
    where = log.relative_to(REPO) if log.is_relative_to(REPO) else log
    print(f"spend: {n} request{'s' * (n != 1)}, ${usd:.2f} estimated at listed prices ({where})")


def main() -> None:
    ap = argparse.ArgumentParser(description="fal.ai registry and spend log")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("models", help="list registered models")
    t = sub.add_parser("total", help="print the spend total of an edit dir or library")
    t.add_argument("dir", type=Path)
    a = ap.parse_args()
    if a.cmd == "models":
        for m in MODELS.values():
            price = f"${m.usd_per_image:.4f}/image" if m.kind == "image" else f"${m.usd_per_s:.3f}/s"
            dur = "" if m.kind == "image" else m.durations_text()
            flag = "*" if m.name in (DEFAULT_VIDEO, DEFAULT_IMAGE) else " "
            print(f"{flag} {m.name:<18} {m.kind:<5} {price:<15} {dur:<14} {m.resolution:<16} {m.note}")
        print("* default")
    else:
        print_total(a.dir.resolve() / SPEND_LOG)


if __name__ == "__main__":
    main()
