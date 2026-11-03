## Why

A hosted short failed every time with `Error loading image … base_005.18.png`, from a phone clip at 24 fps. `conform` deliberately keeps 24 and 25 fps, but a zoomed segment goes through `zoompan`, which emits one frame per input frame and stamps them at 30 fps. At 24 fps a segment comes out 20 % shorter and faster. A still near its end asks for a frame that doesn't exist: ffmpeg exits 0 with no file, and Remotion only says it can't load the image. In a render, the same segment would run ahead of its audio. No test covered it, because every test take and real fixture was at 30 fps.

## What Changes

- A zoomed segment is brought to 30 fps before `zoompan`, so it lasts as long as its audio at any rate `conform` keeps.
- A base frame that ffmpeg can't make is an error naming the time and the segment.

## Capabilities

### Modified Capabilities

- `shortform-spec`: zoomed segments keep their length at any source frame rate.

## Impact

`tools/shortform.py`, its tests. Output at 30 fps sources doesn't change.
