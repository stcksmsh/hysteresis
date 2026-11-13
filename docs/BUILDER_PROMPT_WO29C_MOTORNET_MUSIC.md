# Builder prompt: work order 29C, motor-network toy test Part 3: music pairs (2026-11-13)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER" instead of
waiting. You start with no context: everything you need is named below.

**This is a disposable study.** Nothing ships. No learning or training of any kind, no hand-picking of settings or excerpts, no verdict.
Kosta (the user) judges blind. One arm only (permanent rule). A second builder (29D) adds the Part 3 columns to the report script in parallel.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works. Retry on a GitHub server
  error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:**
  - `src/` and `tools/` are read-only. Never drive hardware. Install nothing. No network downloads.
  - The cortex (B7 epoch 6) is frozen: read its lanes, never change or retrain it.
  - v47 must not seed anything. Its exports stay byte-identical in Off.
  - Data, audio and videos stay outside git. Copyrighted audio is never committed or uploaded anywhere.
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-mnet3 origin/body`, then push `body-mnet3`.
- **Jobs:**
  - Detached and memory-capped:
    `systemd-run --user --unit=hyst-wo29c-<fresh-name> -p MemoryMax=10G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`.
  - `python -u`. Cores **6-11** (`taskset -c 6-11`), 6 threads; state the thread count in the report.
  - Mains only: the script polls `/sys/class/power_supply/ADP1/online` and waits while it reads 0.
  - Agent 2 (29D) uses cores 12-17.
- **Push** within 30 minutes and after every phase. Log: `docs/NIGHT_LOG_body-mnet3.md` (new; MORNING SUMMARY on top).
- **Environments:** body `/secondary/hyst-env/body` (MuJoCo, JAX), brain `/secondary/hyst-env/brain` (torch, for the cortex lanes).
  **Output root:** `/secondary/hyst-data/body/motornet_toy/` (new).

- **Copyrighted audio:** the five mp3 files never enter git and are never uploaded anywhere.

## Read first

- `docs/BRAIN_SPEC.md` **§7.46** (binding: Part 3, excerpt times, extra numbers), §7.45 and §7.44.
- `docs/MOTORNET_RULES.md`, `docs/MOTORNET_PARAMS.md`, `docs/NIGHT_LOG_body-mnet.md` (all on body): the network, input scale s, calibration,
  spinal layer, gates and the music path (`scripts/body/motornet.py`, `motornet_run.py`, `motornet_music.py`, `motornet_render.sh`), and the
  music-path test on a synthetic click track.
- `scripts/body/k5_video_lanes.py`, `scripts/body/k5_data.py` (cortex lanes `l3_cos`, `l3_sin`, `arousal_b7` from B7 epoch 6, frozen).
- `/secondary/hyst-data/body/motornet_toy/clips/manifest.json` and `settings.json` (S01-S10 shown; S11/S12 failed gates, not shown).

## The work

Everything about the network and body is **UNCHANGED** (as in MOTORNET_PARAMS at body-mnet 265fe79).

1. **Audio:** `/secondary/hyst-data/audio/checkset/` (5 mp3, 48 kHz stereo). Excerpts (Kosta), 12 s each; the 10 s before the start drive the
   warm-up:
   - Blue Lagoon 0:20;
   - 21st Century Schizoid Man 0:58;
   - Epitaph 5:45;
   - Breathe 1:17;
   - One of These Days 3:57.
2. **Per song:**
   - compute the cortex lanes with `k5_video_lanes` (same model, same normalisation as the music path);
   - draw two different settings with `numpy.random.default_rng(29031)` from the shown settings S01-S10, songs in the order above;
   - render both with the lamp, the song's excerpt audio muxed, the same camera, 12 s, 1280x720 h264 + aac.
3. **Gates:** gate every render with the same gates. If a render fails, report it and **STOP for the overseer** (no redraw).
4. **Manifest:**
   - first copy `/secondary/hyst-data/body/motornet_toy/clips/manifest.json` to `manifest_parts124.json`;
   - then add one Part 3 item per song: `{id, part: 3, files: [a, b], setting: [Sx, Sy], song, excerpt_start_s, csv: [..], activity: [..],
     hand_speed: [va, vb], arousal_raw, arousal_std, gates}`;
   - also write `part3_numbers.json`, holding the mean hand speed per render and the mean `arousal_b7` over the shown 12 s per song, both
     raw and as the standardised network input.
5. **Done when:**
   - all 10 renders are gated and in the manifest;
   - you have looked at 3 frames per render;
   - night log with MORNING SUMMARY, pushed, "PART3 READY <commit>". Then stop.

   Do not show clips to the user; the overseer checks them first.

**Out of scope (stop and ask; log FOR USER):** any change to the network, scale, calibration, spinal layer or gates; choosing excerpts or
settings; training; cortex changes; hardware; any other audio.
