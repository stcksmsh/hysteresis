# Night log: body-dial (work order 28A, 2026-11-12)

## MORNING SUMMARY

- **Rendered:** Sets A (11 clips) and B (5 clips), 16 in all, 12 s, 1280x720 h264, silent AAC track, fixed one-arm camera of `ensemble_preview
  --joint-csv`. All 16 pass the gates of `docs/DIALSTUDY_RULES.md` (d). Files, 50 Hz joint CSVs, dial values and `manifest.json`:
  `/secondary/hyst-data/body/dialstudy/clips/` (16 MB, outside git). Work dir with gate json and review sheets: `.../dialstudy/work/`.
- **Not done:** Set C waits for the overseer's word that work order 28B's end-effector option is merged into `body`. Set D skipped (no audio folder).
- **Regenerated (all before any clip left the work dir):** (1) amplitudes and posture centres changed because the hand sat on the plane at
  vigour high / posture low (contact gate); (2) stiffness low raised from kp 0.3 / zeta 0.25 to 0.45 / 0.3 (arm lay on the plane); (3) lag
  delays enlarged 2x because lag low/neutral/high CSVs differed by under 1 deg rms in every joint but the roll. Details in
  `docs/DIALSTUDY_DIALS.md`. Everything rendered with the first lag values was discarded and all 16 re-rendered.
- **Threads and compute:** 6 cores (6-11), 6 threads in all: simulation one process per clip (about 1 s of CPU per clip, plain MuJoCo, one
  thread each, `OMP_NUM_THREADS=1`), rendering 3 clips in parallel (headless Chrome + ffmpeg), about 3.5 min wall for 16 clips; cargo build of
  `ensemble_preview` 50 s CPU. Detached units `hyst-wo28a-*`, memory cap 10 GB. Mains polled before every clip.
- **Look-and-feel notes for the overseer, no reading of the clips:** 3 frames per clip and a 12-frame contact sheet per clip were looked at by
  the builder (no plane or base penetration seen); sheets in `.../work/sheets/`. The camera shows a table plane, not a pillar; the page overlay
  text "1 arm" and "Score N s" and an orange hand trail are part of the existing page and are in every clip. The gates are numerically
  permissive on jitter (all clips show an 8 Hz+ velocity-power share under 0.0005; threshold floor 0.01).
- **FOR USER:** (a) neutral posture is the study's own, not the rig home pose; (b) STS3215 plausibility estimate is unverified (in the dials doc);
  (c) the page's orange hand trail and clock overlay stay unless 28B or the overseer wants them hidden.

## Log

- 21:55 fetched `origin/body`, branch `body-dial`; read 7.43 and the body code.
- 22:00 rules pushed (`a777668`) before any rendering.
- 22:02 plain-MuJoCo v2f simulation, generator and gates written (`scripts/body/dialstudy.py`); first run: 5 of 16 failed gates (contact);
  fixed by feasibility changes listed above; second run 16 of 16.
- 22:03 test render of `A_neutral` (66 s alone), framing checked.
- 22:07 first full render stopped when the lag check showed almost no lag effect; lag range doubled, regenerated, all re-rendered (22:11).
- 22:12 manifest built, 16 clips.
