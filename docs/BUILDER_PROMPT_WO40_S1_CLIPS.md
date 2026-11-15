# Builder prompt: work order 40, S1 rebuild-check clips (2026-11-15)

You are a builder for Hysteresis. Work alone; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BRAIN_SPEC.md` **§7.62** (with overseer notes 7.62.5). No verdict. One arm. **You do not run the blind session**: the
overseer builds and serves it.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-s1 origin/body`; absolute paths; no new worktrees.
Detached units `hyst-wo40-<fresh>`, `MemoryMax=8G`, `MemorySwapMax=0`, cores 6-13; `python -u`; read logs 1 min after start. Run on
battery. Commit and push before every run. Plain commit messages, no co-author or attribution lines. No installs, downloads, uploads. In:
`t0/`, `t1a/`, `t1a2/runB/` (read-only), FineDance `music_wav`, AIOZ `musics/`. Out: `/secondary/hyst-data/body/s1/`. Keep messages short.

## Read first

`docs/BRAIN_SPEC.md` 7.62; `docs/T1A2_REPORT.md`; the look-test render path (`scripts/body/retarget_render.sh`, `lowpass_render.sh`,
`retarget_run.py`) and manifest format (`retarget_look/lowpass/clips/manifest.json`); `dialstudy_session.py` (look-test mode,
first / second / same).

## The work

1. **Pick** per 7.62.5 (seed 35001; pool = test windows whose Run B rebuild passes the gates; one window per song group; 4 FineDance + 2
   AIOZ). Write `s1/picks.json` (dataset, dancer, copy, window, group, genre, pool size per dataset).
2. **Render** 12 clips (6 original, 6 rebuild) as the look-test clips were rendered, to `s1/clips/<id>_orig.mp4` and `<id>_rebuild.mp4`
   (20 s, 1280x720, h264 + aac, the window's music, audio offset 0). Look at 3 frames per clip, never to select or reshape.
3. **Manifest** `s1/clips/manifest.json`: 6 `kind: "pair"` items, files `[orig, rebuild]` or `[rebuild, orig]`, rebuild first in exactly 3
   of 6 by `default_rng(35011)`, `variants` labels in shown order. Build a throwaway test session to confirm 6 pair items with the order
   kept, then delete it.
4. **Done when:** "S1 CLIPS READY <commit>" in `docs/NIGHT_LOG_body-s1.md` (picks, pool sizes, pair order, durations), pushed. Then STOP.
