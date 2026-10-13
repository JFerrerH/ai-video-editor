"""Synthesized, license-free SFX library for short-form edits.

Writes 48 kHz stereo WAVs to assets/sfx/synth/ plus `attack.json`, which maps
each effect to its attack in seconds (time from file start to the transient).
To hit a visual on the frame, start the file `attack` seconds BEFORE the
contact time — `tools/shortform.py` does this for you.

Every effect is subtle on purpose: mix them 12–20 dB under dialogue.

Usage:
    uv run tools/sfx_synth.py            # (re)build the library
    uv run tools/sfx_synth.py --list
"""

from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path

import numpy as np

SR = 48000
OUT = Path(__file__).resolve().parent.parent / "assets" / "sfx" / "synth"
rng = np.random.default_rng(7)


def t_axis(d: float) -> np.ndarray:
    return np.arange(int(d * SR)) / SR


def noise(d: float) -> np.ndarray:
    return rng.standard_normal(int(d * SR))


def onepole_lp(x: np.ndarray, cutoff: np.ndarray | float) -> np.ndarray:
    """One-pole low-pass with optional per-sample cutoff (Hz) — enables sweeps."""
    c = np.broadcast_to(np.asarray(cutoff, dtype=float), x.shape)
    a = np.exp(-2 * np.pi * c / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def hp(x: np.ndarray, cutoff: float) -> np.ndarray:
    return x - onepole_lp(x, cutoff)


def norm(x: np.ndarray, peak_db: float = -3.0) -> np.ndarray:
    return x / (np.max(np.abs(x)) + 1e-9) * 10 ** (peak_db / 20)


def fade(x: np.ndarray, fin: float = 0.002, fout: float = 0.01) -> np.ndarray:
    n_in, n_out = int(fin * SR), int(fout * SR)
    x = x.copy()
    if n_in:
        x[:n_in] *= np.linspace(0, 1, n_in)
    if n_out:
        x[-n_out:] *= np.linspace(1, 0, n_out)
    return x


# ── effects: each returns (signal, attack_seconds) ────────────────────────
def whoosh():
    d = 0.42
    t = t_axis(d)
    env = np.where(t < 0.32, (t / 0.32) ** 2.2, np.exp(-(t - 0.32) * 40))
    sweep = 400 + 5200 * np.clip(t / 0.32, 0, 1) ** 1.5
    x = hp(onepole_lp(noise(d), sweep), 150) * env
    return norm(fade(x)), 0.32


def whoosh_short():
    d = 0.22
    t = t_axis(d)
    env = np.where(t < 0.15, (t / 0.15) ** 2, np.exp(-(t - 0.15) * 50))
    x = hp(onepole_lp(noise(d), 800 + 6000 * np.clip(t / 0.15, 0, 1)), 300) * env
    return norm(fade(x)), 0.15


def riser():
    d = 1.4
    t = t_axis(d)
    f = 180 * 2 ** (t / d * 2.5)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.35
    nz = onepole_lp(noise(d), 600 + 7000 * (t / d) ** 2) * 0.6
    env = (t / d) ** 2.5
    return norm(fade((tone + nz) * env, 0.01, 0.02)), d - 0.02


def impact():
    d = 1.1
    t = t_axis(d)
    boom = np.sin(2 * np.pi * np.cumsum(95 * np.exp(-t * 3) + 38) / SR) * np.exp(-t * 4.5)
    crack = onepole_lp(noise(d), 2500) * np.exp(-t * 45) * 0.8
    return norm(fade(boom + crack, 0.001, 0.05)), 0.001


def stamp():
    d = 0.35
    t = t_axis(d)
    thud = np.sin(2 * np.pi * 110 * t * np.exp(-t * 6)) * np.exp(-t * 22)
    slap = hp(noise(d), 900) * np.exp(-t * 90) * 0.7
    return norm(fade(thud + slap, 0.001, 0.02)), 0.001


def thud():  # drawer / box closing
    d = 0.5
    t = t_axis(d)
    body = np.sin(2 * np.pi * 70 * t) * np.exp(-t * 14)
    knock = onepole_lp(noise(d), 1200) * np.exp(-t * 60)
    return norm(fade(body + knock, 0.001, 0.03)), 0.001


def pop():
    d = 0.14
    t = t_axis(d)
    x = np.sin(2 * np.pi * np.cumsum(700 - 2500 * t) / SR) * np.exp(-45 * t)
    return norm(fade(x, 0.001)), 0.004


def click():
    d = 0.03
    t = t_axis(d)
    x = hp(noise(d), 2500) * np.exp(-t * 300)
    return norm(fade(x, 0.0005, 0.005), -6), 0.001


def shutter():
    d = 0.18
    x = np.zeros(int(d * SR))
    for at, g in ((0.0, 1.0), (0.075, 0.7)):
        c, _ = click()
        i = int(at * SR)
        x[i:i + len(c)] += c * g
    t = t_axis(d)
    x += hp(noise(d), 1500) * np.exp(-t * 35) * 0.15
    return norm(fade(x, 0.0005)), 0.001


def typing(n: int = 10, gap: float = 0.085):
    d = n * gap + 0.1
    x = np.zeros(int(d * SR))
    for k in range(n):
        c, _ = click()
        at = k * gap + rng.uniform(-0.015, 0.015)
        i = max(0, int(at * SR))
        x[i:i + len(c)] += c * rng.uniform(0.5, 1.0)
    return norm(x, -4), 0.001


def chime():
    d = 0.8
    t = t_axis(d)
    x = 0.5 * np.sin(2 * np.pi * 1318.5 * t) * np.exp(-7 * t) + 0.35 * np.sin(2 * np.pi * 1975.5 * t) * np.exp(-9 * t)
    return norm(fade(x, 0.002, 0.05)), 0.003


def success():  # two-note up ding
    d = 0.7
    t = t_axis(d)
    a = np.sin(2 * np.pi * 1046.5 * t) * np.exp(-10 * t)
    b = np.where(t > 0.09, np.sin(2 * np.pi * 1568 * (t - 0.09)) * np.exp(-7 * np.clip(t - 0.09, 0, None)), 0)
    return norm(fade(0.6 * a + 0.6 * b, 0.002, 0.05)), 0.003


def error():  # soft descending blip
    d = 0.3
    t = t_axis(d)
    f = np.where(t < 0.12, 520, 390)
    x = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.4
    x = onepole_lp(x, 2200) * np.exp(-t * 7)
    return norm(fade(x, 0.002, 0.03), -6), 0.002


def scratch():  # record scratch for freeze frames
    d = 0.45
    t = t_axis(d)
    speed = np.sin(2 * np.pi * 7 * t) * np.exp(-t * 2)  # back-and-forth hand motion
    f = 500 + 900 * np.abs(speed)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.4
    grit = onepole_lp(noise(d), 1500 + 2500 * np.abs(speed)) * np.abs(speed)
    return norm(fade(tone + grit, 0.002, 0.05)), 0.01


def swell():  # soft reverse-cymbal style build for a flash / reveal
    d = 0.9
    t = t_axis(d)
    x = hp(onepole_lp(noise(d), 3000 + 8000 * (t / d) ** 2), 1500) * (t / d) ** 3
    return norm(fade(x, 0.01, 0.008)), d - 0.008


EFFECTS = {
    "whoosh": whoosh, "whoosh_short": whoosh_short, "riser": riser, "impact": impact,
    "stamp": stamp, "thud": thud, "pop": pop, "click": click, "shutter": shutter,
    "typing": typing, "chime": chime, "success": success, "error": error,
    "scratch": scratch, "swell": swell,
}


def write_wav(path: Path, x: np.ndarray) -> None:
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())


def build(out: Path = OUT) -> dict[str, float]:
    out.mkdir(parents=True, exist_ok=True)
    attacks = {}
    for name, fn in EFFECTS.items():
        x, attack = fn()
        write_wav(out / f"{name}.wav", x)
        attacks[name] = round(float(attack), 4)
    (out / "attack.json").write_text(json.dumps(attacks, indent=2))
    return attacks


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        print("\n".join(EFFECTS))
        return
    attacks = build()
    print(f"wrote {len(attacks)} effects → {OUT}")


if __name__ == "__main__":
    main()
