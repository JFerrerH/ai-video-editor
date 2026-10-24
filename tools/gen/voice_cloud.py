"""Cloud narration (ElevenLabs): one mono 48 kHz WAV + sidecar per shot line, same contract as voice.py.

    uv run tools/gen/voice_cloud.py footage/<p>/edit --voice <voice_id>             # → edit/audio/vo/<shot id>.wav
    uv run tools/gen/voice_cloud.py footage/<p>/edit --voice <id> --out audio/vo_el --lang es
    uv run tools/gen/voice_cloud.py footage/<p>/edit --voices                       # voices this account can use
    flags: --model eleven_multilingual_v2  --settings '{"stability": 0.45}'  --name <shared-library search>  --force

Paid service, opt-in: needs `ELEVENLABS_API_KEY` in `vendor/video-use/.env` (or the environment);
the key is never printed or written. Standard library HTTP only. The `voice` block of shots.json
can hold the defaults (`id`, `model`, `settings`, `lang`); flags override it.

- Speaks each shot's `line`, with the shot list's `pronounce` respellings applied to the text sent
  (the sidecar keeps the script text). Edge silence is trimmed like local voice.
- A clip whose sidecar key (text sent, voice, model, settings, lang) matches is not sent again.
- A voice id not in the account is added from the shared voice library first. On a plan refusal
  (free plan: no library voices through the API) it stops, naming the limit and the voices the
  account can use. Clips are written only after every line succeeded: no partial set.
- Before sending, prints the characters pending and the account's remaining monthly characters,
  and stops if they don't fit. A plan without a commercial licence (free) gets a warning every run.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import shotlist
    import voice
else:
    from . import shotlist, voice

REPO = Path(__file__).resolve().parents[2]
ENV = REPO / "vendor" / "video-use" / ".env"
KEY_VAR = "ELEVENLABS_API_KEY"
API = "https://api.elevenlabs.io/v1"
PROVIDER = "elevenlabs"
DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_SETTINGS = {"stability": 0.45, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True}
SAMPLE_RATE = 48000
NO_COMMERCIAL = {"free"}  # plan tiers without a commercial licence


class PlanLimit(SystemExit):
    pass


def read_key(env_file: Path = ENV) -> str | None:
    if os.environ.get(KEY_VAR, "").strip():
        return os.environ[KEY_VAR].strip()
    try:
        for line in env_file.read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip().removeprefix("export ").strip() == KEY_VAR and v.strip().strip("\"'"):
                return v.strip().strip("\"'")
    except OSError:
        pass
    return None


class Api:
    def __init__(self, key: str):
        self.key = key

    def req(self, path: str, body: dict | None = None, method: str = "GET") -> bytes:
        r = urllib.request.Request(f"{API}{path}", method=method,
                                   headers={"xi-api-key": self.key, "Content-Type": "application/json"},
                                   data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(r, timeout=120) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:400]
            if e.code == 402 or "paid_plan_required" in detail:
                raise PlanLimit(f"paid plan required ({path.split('?')[0]}): {detail}") from None
            raise SystemExit(f"ElevenLabs {method} {path.split('?')[0]} → HTTP {e.code}: {detail}") from None

    def json(self, path: str, body: dict | None = None, method: str = "GET") -> dict:
        return json.loads(self.req(path, body, method))

    def subscription(self) -> dict:
        return self.json("/user/subscription")

    def voices(self) -> list[dict]:
        return self.json("/voices")["voices"]

    def own_voice(self, voice_id: str, search: str | None) -> str:
        """The id to synthesise with; adds a shared-library voice to the account if needed."""
        if any(v["voice_id"] == voice_id for v in self.voices()):
            return voice_id
        q = urllib.parse.quote(search or voice_id)
        shared = self.json(f"/shared-voices?page_size=100&search={q}").get("voices", [])
        hit = next((v for v in shared if v["voice_id"] == voice_id), None)
        if hit is None:
            raise SystemExit(f"voice {voice_id} is neither in the account nor found in the shared library"
                             + ("" if search else "; pass --name <its name> to search for it"))
        added = self.json(f"/voices/add/{hit['public_owner_id']}/{voice_id}",
                          {"new_name": hit.get("name") or voice_id}, "POST")
        print(f"  added library voice {hit.get('name', voice_id)} to the account")
        return added["voice_id"]

    def tts(self, voice_id: str, text: str, model: str, settings: dict, lang: str | None) -> bytes:
        body = {"text": text, "model_id": model, "voice_settings": settings}
        if lang:
            body["language_code"] = lang.split("-")[0]
        return self.req(f"/text-to-speech/{voice_id}?output_format=mp3_44100_128", body, "POST")


def usable_voices(api: Api) -> str:
    try:
        return ", ".join(f"{v['name']} ({v['voice_id']})" for v in api.voices()) or "none"
    except SystemExit:
        return "(couldn't list them)"


def key_for(text: str, voice_id: str, model: str, settings: dict, lang: str | None) -> dict:
    return {"text": text, "voice": voice_id, "model": model, "settings": settings, "lang": lang,
            "provider": PROVIDER}


def is_fresh(wav: Path, key: dict) -> bool:
    side = voice.read_sidecar(wav)
    return wav.exists() and side is not None and all(side.get(k) == v for k, v in key.items())


def to_wav(mp3: bytes, out: Path) -> float:
    """mp3 bytes → trimmed mono 48 kHz WAV; returns its duration in s."""
    import numpy as np

    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le",
                          "pipe:1"], input=mp3, capture_output=True, check=True).stdout
    audio = voice._trim(np.frombuffer(pcm, dtype="<f4"), SAMPLE_RATE)
    voice._write_wav(out, audio, SAMPLE_RATE)
    return round(len(audio) / SAMPLE_RATE, 3)


def jobs_for(sl: shotlist.ShotList, out_dir: Path, voice_id: str, model: str, settings: dict,
             lang: str | None) -> list[tuple[dict, Path, str, dict]]:
    pron = sl.data.get("pronounce") or {}
    jobs = []
    for s in sl.shots:
        text = voice.spoken(s["line"], pron)
        jobs.append((s, out_dir / f"{s['id']}.wav", text, key_for(text, voice_id, model, settings, lang)))
    return jobs


def run(sl: shotlist.ShotList, out_dir: Path, voice_id: str, model: str = DEFAULT_MODEL,
        settings: dict | None = None, lang: str | None = None, search: str | None = None, force: bool = False,
        api: Api | None = None) -> list[Path]:
    settings = {**DEFAULT_SETTINGS, **(settings or {})}
    shotlist.check(sl, sl.shots, "line")
    jobs = jobs_for(sl, out_dir, voice_id, model, settings, lang)
    todo = [j for j in jobs if force or not is_fresh(j[1], j[3])]
    for s, wav, _, _ in jobs:
        if all(wav is not t[1] for t in todo):
            print(f"  cached: {wav.name} ({(voice.read_sidecar(wav) or {}).get('duration', 0):.2f}s)")
    if api is None:
        key = read_key()
        if not key:
            if not todo:
                return []
            raise SystemExit(f"no ElevenLabs key: set {KEY_VAR} in vendor/video-use/.env; nothing was sent")
        api = Api(key)
    sub = api.subscription()
    tier = str(sub.get("tier", "?"))
    if tier in NO_COMMERCIAL:
        print(f"WARNING: the ElevenLabs {tier} plan has no commercial licence: these clips are not cleared "
              "for commercial publication (upgrade before posting for a brand)")
    pending = sum(len(t) for _, _, t, _ in todo)
    left = int(sub.get("character_limit", 0)) - int(sub.get("character_count", 0))
    print(f"characters: {pending} to send, {left} left this month (plan {tier})")
    if pending > left:
        raise SystemExit(f"{pending} characters pending but only {left} left on the account; nothing was sent")
    if not todo:
        return []
    try:
        vid = api.own_voice(voice_id, search)
    except PlanLimit as e:
        raise SystemExit(f"{e}\n  the plan can't use this voice through the API; usable voices: "
                         f"{usable_voices(api)}\n  narration folder unchanged") from None
    written = []
    with tempfile.TemporaryDirectory() as tmp:
        staged = []
        try:
            for s, wav, text, key in todo:
                t0 = time.time()
                part = Path(tmp) / wav.name
                dur = to_wav(api.tts(vid, text, model, settings, lang), part)
                side = {**key, "script": s["line"], "duration": dur, "seconds": round(time.time() - t0, 2)}
                part.with_suffix(".json").write_text(json.dumps(side, indent=1, ensure_ascii=False))
                staged.append((part, wav))
                print(f"  voice: {wav.name} ({dur:.2f}s)", flush=True)
        except PlanLimit as e:
            raise SystemExit(f"{e}\n  usable voices: {usable_voices(api)}\n  narration folder unchanged") from None
        out_dir.mkdir(parents=True, exist_ok=True)
        for part, wav in staged:
            shutil.move(part, wav)
            shutil.move(part.with_suffix(".json"), voice.sidecar_path(wav))
            written.append(wav)
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edit", type=Path, help="the project's edit/ folder (holds shots.json)")
    ap.add_argument("--voice", help="ElevenLabs voice id (default: shots.json voice.id)")
    ap.add_argument("--name", help="voice name to search the shared library with, if the id isn't in the account")
    ap.add_argument("--out", default="audio/vo", help="narration folder, relative to edit/ (default audio/vo)")
    ap.add_argument("--model", help=f"default: shots.json voice.model or {DEFAULT_MODEL}")
    ap.add_argument("--settings", help="JSON voice settings merged over the defaults")
    ap.add_argument("--lang", help="language code (default: shots.json voice.lang)")
    ap.add_argument("--force", action="store_true", help="re-synthesise cached clips")
    ap.add_argument("--voices", action="store_true", help="list the voices this account can use")
    a = ap.parse_args()
    edit = a.edit.resolve()
    if a.voices:
        key = read_key() or sys.exit(f"no ElevenLabs key: set {KEY_VAR} in vendor/video-use/.env")
        print(usable_voices(Api(key)).replace(", ", "\n"))
        return
    sl = shotlist.ShotList(edit / "shots.json")
    v = sl.data.get("voice") or {}
    vid = a.voice or v.get("id")
    if not vid:
        ap.error("--voice is required (or set voice.id in shots.json)")
    settings = {**(v.get("settings") or {}), **(json.loads(a.settings) if a.settings else {})}
    run(sl, edit / a.out, vid, a.model or v.get("model") or DEFAULT_MODEL, settings, a.lang or v.get("lang"),
        a.name, a.force)


if __name__ == "__main__":
    main()
