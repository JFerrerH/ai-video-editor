"""Cloud voice: clip contract, cache, respellings, character budget, plan limits. No network (fake API).

    uv run python -m unittest discover -s tools/tests
"""

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gen"))

import shotlist  # noqa: E402
import voice_cloud  # noqa: E402

MP3 = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=220:d=0.6", "-f", "mp3", "pipe:1"],
                     capture_output=True, check=True).stdout


class FakeApi(voice_cloud.Api):
    def __init__(self, tier="creator", left=10000, library_refused=False):
        super().__init__("k")
        self.tier, self.left, self.library_refused, self.sent = tier, left, library_refused, []

    def subscription(self):
        return {"tier": self.tier, "character_count": 0, "character_limit": self.left}

    def voices(self):
        return [{"voice_id": "own1", "name": "Premade One"}]

    def own_voice(self, voice_id, search):
        if voice_id != "own1" and self.library_refused:
            raise voice_cloud.PlanLimit("paid plan required (/voices/add): paid_plan_required")
        return voice_id

    def tts(self, voice_id, text, model, settings, lang):
        self.sent.append(text)
        return MP3


class CloudVoice(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.data = {"pronounce": {"2030": "dos mil treinta"},
                     "shots": [{"id": f"s{k}", "line": f"Line {k} of the script."} for k in range(3)]}
        self.data["shots"][1]["line"] = "Hasta 2030, todo cambia."
        self.out = self.dir / "audio" / "vo"

    def tearDown(self):
        shutil.rmtree(self.dir)

    def run_tool(self, api, **kw):
        (self.dir / "shots.json").write_text(json.dumps(self.data))
        buf = io.StringIO()
        with redirect_stdout(buf):
            voice_cloud.run(shotlist.ShotList(self.dir / "shots.json"), self.out, kw.pop("voice", "own1"),
                            api=api, **kw)
        return buf.getvalue()

    def test_one_clip_per_line_mono_48k(self):
        self.run_tool(FakeApi())
        wavs = sorted(self.out.glob("*.wav"))
        self.assertEqual(len(wavs), 3)
        self.assertEqual(len(list(self.out.glob("*.json"))), 3)
        with wave.open(str(wavs[0])) as w:
            self.assertEqual((w.getnchannels(), w.getframerate()), (1, 48000))
        side = json.loads(wavs[0].with_suffix(".json").read_text())
        self.assertEqual(side["provider"], "elevenlabs")
        self.assertGreater(side["duration"], 0.3)

    def test_rerun_after_editing_one_line(self):
        self.run_tool(FakeApi())
        self.data["shots"][2]["line"] = "An edited line."
        api = FakeApi()
        self.run_tool(api)
        self.assertEqual(api.sent, ["An edited line."])

    def test_respelling_sent_script_kept(self):
        api = FakeApi()
        self.run_tool(api)
        self.assertIn("Hasta dos mil treinta, todo cambia.", api.sent)
        side = json.loads((self.out / "s1.json").read_text())
        self.assertIn("2030", side["script"])

    def test_not_enough_characters(self):
        api = FakeApi(left=10)
        with self.assertRaises(SystemExit) as e:
            self.run_tool(api)
        self.assertIn("10 left", str(e.exception))
        self.assertEqual(api.sent, [])

    def test_free_plan_library_voice_refused_folder_unchanged(self):
        with self.assertRaises(SystemExit) as e:
            self.run_tool(FakeApi(tier="free", library_refused=True), voice="shared9")
        msg = str(e.exception)
        self.assertIn("paid plan required", msg)
        self.assertIn("Premade One", msg)
        self.assertFalse(self.out.exists())

    def test_free_plan_warning(self):
        out = self.run_tool(FakeApi(tier="free"))
        self.assertIn("no commercial licence", out)


if __name__ == "__main__":
    unittest.main()
