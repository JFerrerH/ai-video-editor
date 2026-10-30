# Spec Delta

## Purpose

Get raw uploads, whatever device recorded them, into an edit-ready format, and make them readable for an editor who never watches video: packed transcripts, stills, contact sheets and a suggested face centre.

## ADDED Requirements

### Requirement: Conform to an edit-ready format

Conform SHALL write a new file per source in `edit/conformed/`, leaving the original untouched. The file SHALL be H.264 SDR BT.709 with rotation applied, at constant frame rate (24, 25 or 30 fps kept; anything else to 30), with 48 kHz stereo audio. Conform SHALL record each file's original, frame and transform in `edit/conformed/conform.json`.

#### Scenario: Phone HDR 60 fps

- **WHEN** a source is 2160x3840 HLG at 59.94 fps
- **THEN** the conformed file is 1080x1920, `color_transfer` is bt709, it runs at 30 fps constant, its duration is within one frame of the source, and the original's checksum is unchanged

#### Scenario: Already edit-ready

- **WHEN** a source is already 1080x1920, SDR BT.709, 30 fps constant, 48 kHz
- **THEN** conform records it in `conform.json` as usable as is and writes no new copy

### Requirement: Conform frame choice

Conform SHALL take a frame: `9:16` or `source`.
- `9:16` scales vertical sources to 1080x1920. It crops horizontal sources to 9:16 around a face centre (the given one, else the suggested one), then scales to 1080x1920.
- `source` keeps orientation and scales the short side to 1080.

#### Scenario: Horizontal to vertical

- **WHEN** a 1920x1080 source is conformed with frame `9:16` and its suggested face centre is x = 1300
- **THEN** the output is 1080x1920, and a still at its midpoint shows the face centre within 10% of the frame width from the horizontal centre

#### Scenario: Keep orientation

- **WHEN** a 3840x2160 source is conformed with frame `source`
- **THEN** the output is 1920x1080

### Requirement: Transcripts of conformed files

Transcripts SHALL be keyed by the take name the edit uses. A transcript made from the original SHALL be reusable for its conformed file, because conform keeps the timeline: same start, no added frames, duration within one frame.

#### Scenario: Times line up

- **WHEN** a word starts at 12.34 s in the original's transcript
- **THEN** the same word is audible at 12.34 s (±1 frame) in the conformed file, and its RMS onset there matches the original within 20 ms

### Requirement: Packed transcript

The system SHALL pack every transcript in `edit/transcripts/` into `edit/takes_packed.md`, phrase by phrase with `[start-end]` source times. A new break SHALL start at each silence of at least 0.5 s.

#### Scenario: Pack after transcription

- **WHEN** two takes are transcribed and the pack runs
- **THEN** `edit/takes_packed.md` exists, has one section per take, and every line starts with a `[NNN.NN-NNN.NN]` range

### Requirement: Source stills and contact sheet

The system SHALL write PNG stills of a source at given source times (at most 24 per call), and optionally one contact-sheet PNG with the time printed under each frame. Images SHALL be no larger than 720 px on the long side.

#### Scenario: Stills at times

- **WHEN** stills of `take1` are requested at 1.0, 5.0 and 9.5 s with a contact sheet
- **THEN** three PNGs and one contact sheet appear under `edit/frames/`, each at most 720 px on the long side

#### Scenario: Time past the end

- **WHEN** a requested time is after the source's duration
- **THEN** the request fails, naming that time and the source's duration, and no stills are written

### Requirement: Face-centre suggestion

The system SHALL suggest a face centre per source, in source pixels, from the person matte on 5 sampled frames. It SHALL report a confidence, and `null` with confidence 0 when a person appears in fewer than 3 of the samples. The suggestion SHALL be deterministic for the same file and backend.

#### Scenario: Talking head

- **WHEN** a face-centre suggestion runs on a selfie talking-head take
- **THEN** it returns an (x, y) inside the frame, in the upper half of the person's area, with confidence above 0.5, and running it again returns the same values

#### Scenario: No person

- **WHEN** it runs on a screen recording with no person in it, or with a person in only one sampled frame (a photo shown in an app)
- **THEN** it returns `null` with confidence 0 and does not fail
