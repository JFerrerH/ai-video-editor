## Context

The prototype (`prototype/compile_plan.py`, `prototype/qa.py`; the plans contain users' footage text and are kept in the private product repo) was iterated on 6 held-out projects on 2026-11-02. Its first versions added rules to move a metric, and the user rejected each one:
- a full-screen cutaway every 20 s;
- "≥ 8 graphics per minute";
- a forced low moment whenever the text sounded sad;
- a punch-in on every key phrase.

What survived is restraint and execution. The plan says what to show; the compiler says when and where. `video-studio/docs/editing-references.md` holds the source for every rule.

## Decisions

### D1. Sentences, not seconds

A sentence breaks on final punctuation or a pause of 0.8 s or more. A likely restart is flagged when the same opening ≥ 2 words return within 6 s after a pause of 0.3 s or more (aligned with `strict-edit-faults`' restart marker, which becomes the source once it exists). IDs are stable for a given transcript.

### D2. A beat is a device plus content, chosen by the author

The compiler doesn't map meanings to components. Prototype v1 did that (`means` → a fixed card list), and it produced the "same 2–3 components" result the user rejected. The plan names the device. The compiler only:
- fills in the defaults (layer, camera, duration);
- validates the content;
- refuses combinations the stage refuses (a `panel` without `corner`, overlapping moves).

### D3. Timing from words

A beat starts on its word: the word's start, or `pre` seconds before it for entrances. It holds until the end of the sentence or the next beat, at most 6 s.

The prototype handles one Whisper artefact: a word stamped early before a cut (its start falls in the removed gap). Such a word is anchored to the segment start instead.

### D4. Sound effects

| Device or moment | Effect |
|---|---|
| Hook | pop |
| `corner`, `side` | swipe |
| `pull` | short whoosh |
| `Drawer` shut | thud |
| `Gauge` stamp | stamp |
| `Notice` | chime |
| `Stickers` | pop on the first item only |
| Turn after a low look | whoosh |
| CTA submit | click |

Volumes are 0.25–0.6. The brand's `rejected_sfx` and `pluck` are excluded (the user's standing rule). The parser takes only the words before "use"/"instead", which fixes the prototype's over-ban of "use click".

### D5. Pacing is reported, not forced

`plan build` prints the longest stretch without a visual change (a new event, a camera move or a cut with a zoom change) and warns past 8 s. It never adds anything to fill the stretch.

### D6. QA owns words to segments by overlap

Prototype faults fixed along the way:
- counting a word in two segments (now: the segment with the largest overlap owns it);
- ignoring short function words for "unexpected speech";
- comparing repeats with the take's own trigram counts, not with the edit's;
- measuring cut energy at the nominal times instead of the real clip durations (now: `clips_preview` durations).

The thresholds were calibrated on 6 videos plus the `xp-bad` control. They are recorded in the spec and revisited with more data.

## Risks / Trade-offs

- **The quality ceiling moves to the plan's author.** A flat plan gives a flat video. The guide (product) teaches the devices with the user-approved launch and habilidades plans as worked examples.
- **Small calibration set**: the QA thresholds can produce false refusals. Every refusal names the measurement, so a false one is visible and fixable.
