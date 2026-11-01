"""Failures of the tools the engine shells out to (ffmpeg, Remotion), and the one line that says why.

`ToolError` is a `SystemExit` (callers that catch that keep working); its message is still
`FAILED: <command>` plus the tool's output tail, and `summary` is one line for a caller to show:
the tool's most specific error line, or what the engine worked out (e.g. which overlay event failed).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CAUSE = re.compile(r"Error|error:|Font did not load|Exception")


def cause_line(msg: str) -> str:
    """The most specific line of a multi-line failure (a tool's stderr under `FAILED: <cmd>`): the last
    line naming an error, else the first; paths under the engine root made relative."""
    lines = [ln.strip() for ln in str(msg).splitlines() if ln.strip()]
    hits = [ln for ln in lines if CAUSE.search(ln)]
    line = hits[-1] if hits else lines[0] if lines else "failed"
    return line.replace(f"{REPO}/", "")[:500]


class ToolError(SystemExit):
    def __init__(self, cmd: list, output: str, summary: str | None = None):
        self.cmd, self.output = [str(c) for c in cmd], output
        message = f"FAILED: {' '.join(self.cmd)}\n{output[-4000:]}"
        self.summary = summary or cause_line(message)
        super().__init__(message if summary is None else f"{summary}\n{message}")
