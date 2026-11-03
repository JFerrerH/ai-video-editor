## 1. Fix

- [x] 1.1 `_vf`: `fps` before `zoompan`. Test at 24, 25 and 30 fps
- [x] 1.2 `_base_frame`: an error when ffmpeg writes no file. Test

## 2. Verification

- [x] 2.1 Unit tests, which fail without the fix; `openspec validate`
- [x] 2.2 A real take at 24 fps and 720x1280, through plan build, render and `preview_qa`: video and audio both 64.233 s, no faults
