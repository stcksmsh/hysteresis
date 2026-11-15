# Builder prompt: work order 42, PhantomDance download, T0 pipeline, look clips (2026-11-15)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BRAIN_SPEC.md` **§7.69** (including its overseer notes), then 7.59.2 / 7.60 / 7.56 for the T0 pipeline as FineDance used
it. No verdict. One arm. **You do not run Kosta's look session**: the overseer serves it. No planner training of any kind. Another builder
is training E1 on cores 6-17: stay on cores 18-19.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-phantom origin/body`; absolute paths; no new
worktrees. Detached units `hyst-wo42-<fresh>`, `MemoryMax=6G`, `MemorySwapMax=0`, cores 18-19, `python -u`; read logs 1 min after start.
Run on battery. Commit and push before every run. Plain commit messages, no co-author or attribution lines. **The one allowed download is
PhantomDance per 7.69.1** (curl or the existing env; no installs; if a login, captcha or account page appears, STOP and ask). No uploads.
Env `/secondary/hyst-env/brain`. In (read-only): `/secondary/hyst-data/body/t0/` and the FineDance data it used. Out:
`/secondary/hyst-data/phantomdance/` (raw download, licence, README, `PROVENANCE.md`) and `/secondary/hyst-data/body/t0_phantom/`
(everything derived). Nothing on the root disk. Keep messages short.

## Read first

`docs/BRAIN_SPEC.md` 7.56, 7.59.2, 7.60, 7.69; `docs/T0_RULES.md`; `docs/RETARGET_RULES.md`; `docs/LOWPASS_REPORT.md` (cutoffs V1 2.50 Hz,
V2 5.75 Hz); `scripts/body/t0_run.py`, `t0_lib.py`, `t0_lanes.py`, `t0_chain.py`, `retarget.py`, `retarget_run.py`, `lowpass_run.py`,
`retarget_render.sh`; `scripts/brain/fast_features.py`; `scripts/body/dialstudy_session.py`.

## The work

1. **Download** per 7.69.1 from the link in the repository's README. Write `PROVENANCE.md`: date, URL, version, file list with sizes and
   SHA-256, licence as stated (repo MIT) and that music rights are not separately stated; copy the licence and README beside the data.
   Night log "DOWNLOADED <version, pairs, hours>".
2. **Format check:** skeleton, joint order, rotation format, frame rate, units, up axis, root handling, compared with what `retarget.py`
   expects from FineDance. Write the mapping (and anything that does not map) into `docs/T0_PHANTOM_RULES.md` and push it **before** any
   retarget run. If the skeleton cannot be mapped without a design choice, STOP and log FOR USER.
3. **T0 as FineDance (7.69.2):** retarget V1/V2 + mirror, low-pass with the same cutoffs, H1, posture/gesture split, gates at 1.25,
   lanes and cortex states computed locally on its audio exactly as `t0_lanes.py`; split by song with its own seed fixed in the rules
   note; songs also in FineDance (by name) listed. Code reuses the T0 functions; any change is a new flag with the FineDance default
   unchanged (rerun the existing T0 tests).
4. **Report `docs/T0_PHANTOM_REPORT.md`:** hours kept after gates, genres, jitter vs FineDance (the T0 measures), gesture amplitude (RMS,
   p5-p95 per joint) vs FineDance, and the 7.69 band-limit check (which ear columns and cortex inputs depend on content above 8 kHz; the
   shift on 5 FineDance songs low-passed at 8 kHz).
5. **Look clips (7.69.3):** 6 retargeted PhantomDance clips, seeded, across genres (rule and seed in the rules note), 20 s each, rendered
   as the look-test clips (`retarget_render.sh`: camera, lamp head, column, 1280x720, h264 + aac, the song's own audio, offset 0); look at
   3 frames per clip, never to select. Manifest of singles for `dialstudy_session.py`, question "does the dancer follow the music?",
   answers yes / partly / no + note (add a label-set option; change nothing else). To `t0_phantom/look/`; build a throwaway session to
   confirm it loads, then delete it.
6. **Done when:** "PHANTOM READY <commit>" in `docs/NIGHT_LOG_body-phantom.md`, pushed. Then STOP.
