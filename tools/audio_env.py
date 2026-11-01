"""RMS envelope of a file's audio and the speech runs in it.

Shared by short-form edge refinement (tools/shortform.py) and the transcriber's hole check
(tools/transcribe_local.py), so "speech" means the same thing in both.

    db, floor = envelope(path)            # dB per 5 ms hop (20 ms window), 10th-percentile floor
    runs = speech_runs(db, floor)         # [(start_s, end_s), …] above floor + 9 dB
"""

from __future__ import annotations

import subprocess
from pathlib import Path

HOP = 0.005  # seconds per envelope frame
SR = 16000


def envelope(path: Path):
    """RMS envelope in dB (5 ms hop / 20 ms window) and its noise floor (10th percentile)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1",
                          "-ar", str(SR), "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, "<i2").astype(np.float32) / 32768
    hop, win = round(HOP * SR), round(0.02 * SR)
    n = max(1, (len(x) - win) // hop)
    if len(x) < win:
        x = np.pad(x, (0, win - len(x)))
    frames = np.lib.stride_tricks.sliding_window_view(x, win)[::hop][:n]
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
    return db, float(np.percentile(db, 10))


def speech_runs(db, floor: float, above: float = 9.0, min_gap: float = 0.3,
                min_len: float = 0.05) -> list[tuple[float, float]]:
    """Stretches where the envelope sits above `floor + above` dB, as (start_s, end_s).
    Runs closer than `min_gap` s are merged (pauses between words); runs shorter than
    `min_len` s after merging are dropped (clicks)."""
    loud = db > floor + above
    runs: list[list[float]] = []
    k, n = 0, len(loud)
    while k < n:
        if loud[k]:
            j = k
            while j < n and loud[j]:
                j += 1
            a, b = k * HOP, j * HOP
            if runs and a - runs[-1][1] < min_gap:
                runs[-1][1] = b
            else:
                runs.append([a, b])
            k = j
        else:
            k += 1
    return [(round(a, 3), round(b, 3)) for a, b in runs if b - a >= min_len]
