"""A synthetic project for the edit-plan and preview-QA tests: one 108x192 take of tone bursts, one burst per word,
with a transcript that has a restart. No footage, no models.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

# (text, start, end). F1 "Hola mundo." · F2 "En esa tesis" abandoned after a 0.5 s pause · F3 the same opening again ·
# F4 "Sin estudiar nada ahora." · F5 "ya es tarde." · F6 "sígueme ahora, hoy mismo." · F7 "Gracias a todos."
WORDS = [
    ("Hola", 0.5, 0.9), ("mundo.", 1.0, 1.5),
    ("En", 2.4, 2.6), ("esa", 2.7, 3.0), ("tesis", 3.1, 3.6),
    ("en", 4.1, 4.3), ("esa", 4.4, 4.7), ("tesis", 4.8, 5.3), ("hablaba", 5.4, 5.9), ("mucho.", 6.0, 6.5),
    ("Sin", 7.5, 7.8), ("estudiar", 7.9, 8.5), ("nada", 8.6, 9.0), ("ahora.", 9.1, 9.6),
    ("ya", 10.6, 10.9), ("es", 11.0, 11.2), ("tarde.", 11.3, 11.9),
    ("sígueme", 13.0, 13.6), ("ahora,", 13.7, 14.2), ("hoy", 14.3, 14.6), ("mismo.", 14.7, 15.2),
    ("Gracias", 16.2, 16.8), ("a", 16.9, 17.0), ("todos.", 17.1, 17.7),
]
DURATION = 18.5


def make_take(path: Path, words=WORDS, d: float = DURATION, amp: float = 0.5) -> None:
    expr = "+".join(f"{amp}*between(t,{a},{b})" for _, a, b in words)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s=108x192:r=30:d={d}",
                    "-f", "lavfi", "-i", f"aevalsrc='sin(2*PI*220*t)*({expr})':s=48000:d={d}",
                    "-shortest", "-c:v", "libx264", "-c:a", "pcm_s16le", str(path)], check=True)


class PlanFixture(unittest.TestCase):
    """footage/demo with take1, its transcript and a face centre, in a temporary directory."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.root = cls.tmp / "demo"
        (cls.root / "edit" / "transcripts").mkdir(parents=True)
        (cls.root / "edit" / "conformed").mkdir()
        make_take(cls.root / "edit" / "conformed" / "take1.mov")
        (cls.root / "edit" / "transcripts" / "take1.json").write_text(json.dumps(
            {"language_code": "es", "words": [{"type": "word", "text": t, "start": a, "end": b} for t, a, b in WORDS]}))
        (cls.root / "edit" / "face.json").write_text(json.dumps({"take1": {"face": [54, 96], "head": [38, 63, 70, 100]}}))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def ids(self) -> dict:
        import edit_plan as E
        return {s["id"]: s for s in E.plan_ids(self.root)}
