# Design

## Context

- **`tools/shortform.py`** is the short-form engine. A project's `build.py` builds `Seg` objects, constructs `Project(...)` and calls `refine_edges()`, which widens every cut to measured silence. Only then does it compute overlay and SFX times, with `p.word(take, text, after)` and `offsets()` (the `W1(...)` / `seg_end(i)` helpers). Times therefore depend on the edge-refined cut, so anchors must resolve after refinement, in that order.
- **`Project._vf`** hard-codes a 1080x1920 source: its crop bounds use `1080`/`1920`, and zoompan upscales to `1080*k x 1920*k`. Every project so far had 1080x1920, 30 fps, SDR takes, so this never failed.
- **`vendor/video-use/helpers/render.py`** renders an EDL (`sources`, `ranges`, `grade`, `overlays`, `subtitles`), scales to 1080p at the source orientation and loudness-normalises. It accepts absolute paths and passes a non-preset `grade` string straight into `-vf`. That makes it fine on the CLI, but it must never see an untrusted EDL as written. The vendor directory isn't edited.
- **`tools/run_job.py`** has hand-written argument schemas, `confine()` for paths and in-process op functions. `storyboard` is the model for a multi-command op (`cmd: check|…|render`, `check` returns `errors`).
- **The person matte** (`tools/person_matte.py`) runs on Apple Vision on the Mac and MediaPipe on Linux. It writes a grey matte video for a time window.

## Goals / Non-Goals

**Goals:**
- One loader turns `short.json` into the same `Project` a `build.py` builds. Render, check and stills all go through it, so there's one engine and no second renderer.
- A spec that validates can't make the engine read outside the project or execute anything.
- Mac `build.py` projects render bit-for-bit as before.

**Non-Goals:**
- A JSON Schema file or schema library. Validation is hand-written, like `run_job.py` and `storyboard.py check`, so the error messages name the field and the index.
- Changing what the overlay components accept. Props pass through to Remotion as before.

## Decisions

### 1. `tools/short_spec.py`: load → refine → resolve, mirroring `build.py`

`load(spec_path) -> (Project, report)` does what `build.py` does, in the same order:
1. validate the fields
2. build `Seg`s
3. construct `Project` (brand kit loaded the usual way)
4. `refine_edges()`
5. resolve anchors
6. set `p.events` and `p.sfx`

`check`, `stills` and `render` all start from `load()`. Keeping resolution after refinement is what makes a port of a `build.py` match it frame for frame.

*Alternative:* resolving anchors before refinement. This is simpler, but every word-anchored overlay would drift by the edge widening (up to ~0.3 s), so it was rejected.

### 2. Spec shape

```json
{
  "version": 1,
  "brand": "none",
  "sources": {"take1": {"file": "edit/conformed/take1.mov", "face": [540, 900]}},
  "segments": [
    {"take": "take1", "in": 0.0, "out": 5.0, "zoom": {"kind": "static", "scale": 1.0},
     "look": null, "freeze_after": 0, "lock_in": false, "lock_out": false, "note": "first line"}
  ],
  "captions": {"fixes": {}, "word_fixes": [{"take": "take1", "at": 3.21, "text": "…"}],
               "skip": [{"take": "take1", "at": 7.80}], "props": {}, "engine": "remotion"},
  "emphasis": [{"take": "take1", "phrase": "key words", "after": 0.0}],
  "events": [{"type": "HookTitle", "start": 0, "end": {"seg": 0, "edge": "end"}, "props": {}}],
  "sfx": [{"name": "click", "at": 0.06, "gain_db": -15}],
  "public_files": {"site/img-00.png": "edit/downloads/site/img-00.png"},
  "grade": null, "lufs": -14.0,
  "edges": {"above_floor": 9}
}
```

- Zoom kinds match `zoom_expr`:
  - `static {scale}`
  - `push {from, to}`
  - `punch {base, peak, at}`
  - `outpunch {from, to, peak, at}`
- A zoom's `at` is a source time: a number, or a word anchor in the segment's own take.
- `grade` is `null` (the engine default) or a name from a fixed preset table. Never a filter string.
- `look` is a key of `LOOKS`.
- An event takes `end` or `duration`, not both.
- The take name keys the transcript, as `build.py` already does (`edit/transcripts/<take>.json`).

### 3. Anchors

- **Word:** `{"word", "take", "after"?, "edge": "start"|"end", "offset"?}` calls `Project.word()`, so its semantics are exactly today's.
- **Segment:** `{"seg": i, "edge": "start"|"end", "offset"?}` uses `offsets()[i]` or `offsets()[i+1]`.

A number means output seconds. Errors from `word()`/`at()` are caught and reported with the event index.

### 4. Source size: scale into the work frame, keep the 1080x1920 maths

In `_vf`, a source that is 9:16 but not 1080x1920 gets `scale=1080:1920:flags=lanczos` prepended. Its face centre is scaled by `1080/width`.

1080x1920 sources get no extra filter, so existing projects render identically. Everything after (crop, zoompan) stays as it is, and the change is a few lines.

The source's size, aspect and transfer come from one ffprobe per take, cached on the project. A non-9:16 aspect, landscape orientation or HLG/PQ transfer raises an error that names `conform`.

*Alternative:* generalising the crop maths to any resolution. It's more code in the hot path, and it carries a risk of changing existing renders.

### 5. Conform: `.mov` mezzanine with PCM audio

`tools/conform.py` writes `edit/conformed/<stem>.mov`:
- H.264 `-crf 12 -preset veryfast`, yuv420p, BT.709 tags
- PCM s16le 48 kHz stereo audio

PCM matters: AAC adds priming samples that shift audio against the original, which would break reuse of the original's transcript.

The filter chain:
1. autorotate (ffmpeg default)
2. tone-map when transfer is `arib-std-b67` or `smpte2084` (render.py's `zscale … tonemap=hable` chain, calibrated to `npl=140` + saturation 0.9 on a real phone take)
3. `fps` to 24, 25 or 30 (sources whose average is within 0.5% of those keep it; everything else → 30)
4. the frame step: scale for vertical, or crop then scale for horizontal with `9:16`
5. `setparams` to BT.709 (see "Changes made during apply")

A source already in spec is recorded as `"as_is": true` and not copied. `conform.json` records per take: original, output, source probe, frame, crop box, face used.

*Alternative:* ProRes mezzanine. It decodes faster but is 5–10x larger, which matters for upload/storage round trips in a hosted setting.

### 6. Face suggestion from the matte

1. Sample 5 frames at 10/30/50/70/90% of the duration.
2. For each, run `make_matte` for a one-frame window and read the mask (> 0.5).
3. Take the top 30% of the mask's vertical extent as the head band.
4. The suggested point is the band's centroid x and its vertical middle.

The result is the median over the frames that have a person. Confidence = (frames with a person / 5) × (1 if the median band is inside the frame else 0.5). No person → `null`, 0.

This adds no dependency, and it uses the same backends the engine already ships. It is deterministic because both backends are deterministic on a still frame.

*Alternative:* MediaPipe face detection. It's more precise for the eyes, but it's a second model, and it's Linux-only unless we also wrap Vision faces. The matte head band is close enough for a crop centre (a ±40 px error is invisible at 1.0–1.15 zoom).

### 7. `cut` op: sanitise, then call `render.py` unchanged

`op_cut` validates the EDL against a whitelist:
- `version`, `sources` (name → project-relative file), `ranges` (`source`, `start`, `end`, `beat`?, `quote`?, `reason`?)
- `grade` ∈ preset names ∪ {`auto`, `none`}
- `overlays` (`file` confined, video extension, `start_in_output`, `duration`)
- `subtitles` (`"build"` or a confined `.srt`)

Ranges must lie within each source's probed duration. Total output must be ≤ 3 h.

It then writes `edit/cut/edl.resolved.json` with absolute confined paths and the preset name. It runs `uv run --no-sync vendor/video-use/helpers/render.py <resolved> -o edit/cut/<preview|final>.mp4 [--preview] [--build-subtitles]`, and finally measures loudness with `shortform.loudness`.

`render.py` treats a name it can resolve as a preset. Whitelisting names before the call closes its "unknown preset → raw filter" fallback.

### 8. Stills without a full render

For each requested output time `t`:
1. Find the segment and its local time.
2. Extract that one frame from the source with the segment's own `_vf` (one `ffmpeg -ss … -frames:v 1`, at preview size).
3. Render the overlay frame with the existing `overlay_stills` (captions included, since they're an overlay event).
4. Composite with one ffmpeg `overlay`.

Behind-the-speaker events at `t` get a one-frame matte of the extracted frame, and the same layer order `build()` uses.

That's about 1–2 s per still, against ~10 s+ for a preview render.

### 9. `run_job.py` ops

| op | args | writes |
|---|---|---|
| `conform` | `sources` (list of paths) or all media, `frame` (`9:16`/`source`), `face` (strmap of take → "x,y"), `preview` | `edit/conformed/*`, `conform.json` |
| `pack` | `silence` (float, 0.5) | `edit/takes_packed.md` |
| `frames` | `source`, `at` (floats, ≤ 24), `sheet` (bool) | `edit/frames/<stem>_<t>.png`, `…_sheet.png` |
| `face` | `sources` | result fields only (plus `edit/face.json`) |
| `shortform` | `cmd` check/stills/render, `spec` (default `edit/short.json`), `at`, `preview` | `edit/stills/*`, `edit/preview.mp4` / `final.mp4` |
| `cut` | `cmd` check/render, `edl` (default `edit/edl.json`), `preview` | `edit/cut/*` |

`pack` calls the vendored `pack_transcripts.py` with `--edit-dir`.

The limits from the specs are checked in the loaders, so the CLI and the runner enforce the same limits.

### 10. CLI parity

`tools/shortform.py` gains a small `__main__`: `uv run tools/shortform.py check|stills|render [edit/short.json] [--preview] [--at …]`. `tools/conform.py`, `tools/face_centre.py` and `tools/frames.py` have CLIs too. The runner calls the same functions, which satisfies "Same results as the CLI".

## Risks / Trade-offs

- **[A port drifts from its `build.py`]** Some past `build.py` files hold one-off Python, such as loops that pick words. → The spec covers every field the template exposes, and `build.py` stays the escape hatch. Verification ports one real project and compares frames, duration and loudness.
- **[Tone-mapping looks flat on some HDR clips]** → Hable is what `render.py` already ships. Previews are checked by stills; a per-brand grade can lift it.
- **[The matte head band misses on profile shots or crowds]** → The suggestion reports its confidence, and the caller can pass `face` explicitly. Conform records the face it used.
- **[Conform time on CPU for long 4K uploads]** (~0.5–1x real time) → Conform runs once per upload and is cached; already-ready sources are skipped. A hosted caller can conform at upload time.
- **[`render.py` changes upstream]** (vendored) → The sanitiser writes only fields `render.py` documents, and the `cut` scenarios run in verification after each vendor bump.
- **[Untrusted overlay props]** carry strings into React. → Checked during apply (task 6.4): `tools/motion/src` has no `dangerouslySetInnerHTML`, `innerHTML`, `eval`, `new Function`, dynamic `import()`, `fetch` or `<iframe>`, so props render as text. Every media load goes through `staticFile()`, fed by exactly two prop names: `src` (PhoneMockup, Polaroids, ImageScene) and `logo` (EndCard). The spec requires both (`FILE_KEYS`) to name a staged `public_files` entry. Scene primitives also render as overlay events (`REGISTRY[type] ?? SCENES[type]`), so the spec accepts both registries. A component that loads files through a new prop name must be added to `FILE_KEYS`.

## Verification Notes

**Mac (M-series, 32 GB), runner only, `footage/e2e-pilot` (gitignored).** The upload is a 20 s 2160x3840 HLG HEVC 10-bit clip at 60 fps with 44.1 kHz AAC: a phone-style re-encode of a real 1080p talking-head take, since no real HDR take was at hand.

| step | seconds | result |
|---|---|---|
| inventory | 0.1 | 1 file |
| conform | 7.2 | 1080x1920, bt709 (stream and frame), 30/1 constant, duration = source |
| transcribe (es) | 3.6 | mlx-whisper |
| pack | 0.03 | 3 phrases |
| face | 4.6 | (564, 876), confidence 1.0, the same on every run (Vision) |
| frames (7 + sheet) | ~2 | ≤ 720 px |
| shortform check | ~1.5 | flagged 2 edges with no silence (a cut inside "vivo en el", and the end of the take): fixed in the spec, one edge locked at the measured dip (8.83 s, +2–4 dB over the floor) |
| shortform stills (4) | 9.8 | read: hook card, behind-the-head title, captions, per-segment zoom all correct |
| render preview | 21.5 | 720x1280 |
| render final | 39.8 | 1080x1920, 425 frames = planned 14.167 s, bt709, −14.0 LUFS, −1.5 dBTP |

- **Cuts on the dialogue base** (40 ms each side, relative to the 90th-percentile speech level): 5.33 s −48.7/−50.5 dB, 7.20 s −21.1/−32.4 dB, 11.83 s −24.8/−31.4 dB. All are ≥ 20 dB under speech.
- **Remaining warning:** the echo check flagged "HOLA" on screen while the caption says "Hola". That's the intended craft warning, left in the pilot on purpose.
- **Other checks during apply:**
  - The ported `build.py` pilot rendered from `short.json` with the same frame count and identical frames (PSNR ∞ at 2 points).
  - An existing `build.py` project rendered before and after the engine change gives identical frame MD5s at 4 cut points.
  - A 4K copy of a take gives a static-zoom still at 47–49 dB PSNR against the 1080p take.
  - Conform keeps word onsets at 0 ms offset (3 words, 2 conformed files).
  - A horizontal take conformed to 9:16 puts the face 5 px from the centre.
  - `cut render` of 3 ranges from a 1920x1080 take: 1920x1080, 384 frames (12.8 s = sum of ranges), −14.0 LUFS / −1.0 dBTP, 3.9 s.
- **Docker (arm64 image on the same Mac), `footage/e2e-docker`, the same upload and `short.json`, every step through `docker run … - < job`:**
  - inventory 0.1 s
  - conform 40 s (CPU x264 on 4K HEVC 10-bit, against 7 s on the Mac)
  - transcribe 7.1 s (faster-whisper)
  - pack 0.4 s
  - face 3.9 s (MediaPipe (563, 884) against Vision (564, 876))
  - frames 2.6 s
  - check 0.4 s (same single echo warning, same 14.167 s)
  - stills 9.3 s
  - preview 21.2 s
  - final 37.1 s: 1080x1920, 425 frames, −14.0 LUFS, −1.5 dBTP
  - `cut render` of the horizontal take: 5.2 s, 1920x1080, 384 frames, −14.0 LUFS, −1.0 dBTP
  - `--self-check` exits 0
- **HDR colour, Mac against Linux.** The first Docker run came out pinker than the Mac. The test clip had its BT.2020/HLG tags only in the video stream, and ffmpeg 9 (Mac) and 7.1 (Debian) disagree on whether container or frame tags win. Conform now passes the probed input transfer, primaries and matrix to `zscale` explicitly. Mac and Linux conforms then match at 46 dB PSNR, and a correctly converted HLG clip comes back with the original's hue.
- **Real phone take (SDR HEVC 1080x1920, 30 fps nominal / 29.99 average, 48 kHz):** conform records it `as_is` on both Mac and Docker (no copy, no colour change). A Docker short from it matches the original's colour: mean luma 129 against 133 and saturation 10.0 against 9.8. The difference is the engine's default grade (contrast 1.04, saturation 1.03). The pink first Docker run came only from the mislabelled synthetic clip.
- **Messaging-app take (WhatsApp re-encode: H.264 480x854, 59.94 fps, SDR, 48 kHz):** conform gives 1080x1920, a constant 30 fps, BT.709, 21.967 s against 21.988 s (within one frame), and identical colours side by side. WhatsApp strips HDR when it sends a video, so such files can't be used to calibrate HDR.
- **HDR tone-map calibrated on a real phone take.** A phone recorded the same take in HLG (HEVC 10-bit, 3840x2160 stored with rotation 90, 59.94 fps), and the phone's own SDR export of it arrived via WhatsApp. Measured over 4 frames (mean luma / saturation / PSNR against the phone SDR, which sits at 84.4 / 26.1):
  - render.py's chain (Hable, `npl=100`, full saturation): 94.8 / 30.6 / 22.1 dB, about 12% too bright and 17% too saturated (warm skin).
  - Mobius, Reinhard, desaturating Hable, and plain clipping at `npl` 100 or 203 were all further off (12–19 dB).
  - A grid over `npl` {100, 120, 140} × saturation {0.85, 0.9} × gamma {1, 0.92} picked **Hable, `npl=140`, `eq=saturation=0.9`**: 86.5 / 25.5 / 24.5 dB, the best match. Conform now uses it.
  - Docker and the Mac produce the same conformed file (46–50 dB PSNR, 58 s on CPU for 22 s of 4K HDR).
  - Calibrated on one phone; other makers' HDR may differ a little.
- **Short stills against the rendered final:** 27–31 dB PSNR. The difference is motion: a still is extracted at the exact time, the comparison frame is the nearest one. Composite, captions and layers are visually identical.

## Changes made during apply

- **`edges` in the spec.** Two past projects tuned `refine_edges(above_floor=28)` for very low noise floors, so the spec takes an optional `edges` block (`above_floor`, `pre`, `post`, `min_sil`, each bounded) that passes straight to `refine_edges()`.
- **Conform keeps the timeline without `setpts`.** ffmpeg already shifts both streams by the input's start time, so A/V offsets are preserved. Resetting each stream on its own would have shifted one against the other. Measured: word onsets match the original to 0 ms. `-shortest` is used only with the silent track added to takes that have no audio (capped to the video's duration). Otherwise it dropped trailing video frames.
- **HDR detection reads the first frame's transfer** when the stream-level tag isn't HLG/PQ: a container can say bt709 while the frames carry HLG. Conform ends its chain with `setparams` and writes the BT.709 VUI through `-x264-params`. Without both, the container kept the source's HLG tag.
- **"Already 30 fps" tolerates phone drift:** `r_frame_rate` must be 24/25/30 and `avg_frame_rate` within 0.5% of it. Phones report e.g. 30/1 with an average of 29.993.
- **Face suggestion needs a person in at least 3 of the 5 samples.** A screen recording showed a photo of a person in one frame. That isn't a speaker take, so the answer is `null` with confidence 0.
- **`cut` writes the resolved EDL to `edit/edl_resolved.json`**, not `edit/cut/`, because `render.py` reads transcripts (for `--build-subtitles`) from the EDL's own directory. The video goes to `edit/cut/preview|final.mp4`.
- **Entry points:** `tools/face_centre.py`, `tools/frames.py` and `tools/cut_edl.py` (EDL whitelist) are their own small modules with CLIs; the runner imports them.

## Migration Plan

Additive. Existing `build.py` projects keep rendering, and `shortform.build` stays. New short-form projects get both starters, and the skill recommends `short.json`. Rollback = revert the branch; no data format is replaced.

## Open Questions

- **Other phones' HDR.** The tone-map is calibrated on one phone's HLG take (see Verification Notes). If another maker's footage comes out off, re-run the same comparison against that phone's own SDR export and adjust `tonemap()` in `tools/conform.py`. That's one filter string; no spec or op changes.

- Whether conform should also normalise loudness for the mezzanine. Not needed for this change, because renders loudness-normalise at the end.
