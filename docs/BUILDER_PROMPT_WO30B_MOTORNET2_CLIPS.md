# Builder prompt: work order 30B, motor-network toy round 2: two populations, clips (2026-11-13)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER" instead of
waiting. You start with no context: everything you need is named below.

**This is a disposable study.** Nothing ships. No learning or training of any kind, no hand-picking of settings or excerpts, no hand-shaping
of movement, no verdict. Kosta (the user) judges blind. One arm only (permanent rule). A second builder (30A) writes the ear-energy formula,
the arousal/energy comparison and the round-2 session tool in parallel.

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
  `git fetch origin && git checkout -b body-mnet4 origin/body`, then push `body-mnet4`.
- **Jobs:**
  - Detached and memory-capped:
    `systemd-run --user --unit=hyst-wo30b-<fresh-name> -p MemoryMax=10G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`.
  - `python -u`. Cores **6-11** (`taskset -c 6-11`), 6 threads, never 12-17 (30A's); state the thread count.
  - Mains only: the script polls `/sys/class/power_supply/ADP1/online` and waits while it reads 0.
- **Push** within 30 minutes and after every phase. Log: `docs/NIGHT_LOG_body-mnet4.md` (new; MORNING SUMMARY on top).
- **Environments:** body `/secondary/hyst-env/body` (MuJoCo, JAX), brain `/secondary/hyst-env/brain` (torch, for the cortex lanes).
  **Output root:** `/secondary/hyst-data/body/motornet_toy2/` (new). Round 1's data in `/secondary/hyst-data/body/motornet_toy/` is read-only.

## Read first

- `docs/BRAIN_SPEC.md` **§7.47** (binding, including the overseer notes 7.47.6), then §7.46, §7.45, §7.44.
- `docs/MOTORNET_RULES.md`, `docs/MOTORNET_PARAMS.md`, `docs/MOTORNET_REPORT.md`, `docs/NIGHT_LOG_body-mnet.md`,
  `docs/NIGHT_LOG_body-mnet3.md`; code `scripts/body/motornet.py`, `motornet_run.py`, `motornet_music.py`, `motornet_part3.py`,
  `motornet_render.sh`, `motornet_part3_render.sh`, `motornet_stoprule.py`, `motornet_measure.py`.
- `scripts/body/k5_video_lanes.py`, `scripts/body/k5_data.py` (`song_lanes`: the B7 layers; L4 = `out[3]`, the slowest, horizon 800 frames),
  `scripts/brain/core.py`.

## The work

1. **Rules file first:** `docs/MOTORNET2_RULES.md`, pushed before any clip is rendered. It fixes everything below, with numbers:
   - **Network:** slow population 100 units, tau 300 ms; fast population 100 units, tau 75 ms; nonlinearity as round 1. Full 200 x 200
     recurrent matrix drawn iid (seed 30001); all rows of a population scaled by one factor so that its within-population block has spectral
     radius 1.05; between-population blocks keep that row factor; report the full matrix's radius.
   - **Readout:** base yaw and shoulder from the slow population only; elbow, wrist bend, wrist roll from the fast population only; random,
     seeded, fixed. Calibration as round 1: one scale and offset per joint at gain 1 silent, +-60 %.
   - **Inputs:** beat-band phase cos/sin to both (silent: fixed 100 BPM as round 1); L4 to the slow population: L4's complex state (real and
     imaginary parts) projected by a seeded Gaussian matrix (seed 30002) to 4 signals, standardised with one mean and sd over the three
     danced songs, clipped to +-3, no extra filtering; ear energy (30A's `scripts/body/ear_energy.py`, its standardised network lane) and
     `arousal_b7` (standardised as round 1) to both. Silent: L4, energy and arousal are 0. Input weights random, seeded.
   - **Drive ratio:** one input scale per population, found by fixed-point iteration as in 7.45.10 on the gain-1 silent run: input std =
     0.25 x recurrent std in each population, within 2 %. State both scales.
   - **Control units:** 4, as round 1 (gain range as round 1), each scaling a random subset of neurons drawn from both populations (subsets
     overlap); state subset sizes per population.
   - **Body:** spinal spring-damper, servo, limiter, gates, warm-up (10 s) and minimum motion exactly as round 1 (MOTORNET_PARAMS at body-mnet
     265fe79). The 7.45.2 limiter rule applies again (base yaw or shoulder losing more than half its target p5-p95 range at gain 1 silent ->
     spinal 1.5 Hz, recalibrate); report limiter shares either way.
   - **Manifest format** (30A's tool reads it): per clip id, part (A / B), files, setting, song, excerpt_start_s, csv, activity, population
     index per unit, gates.
   - **ENERGY:** wait for "ENERGY READY <commit>" in `docs/NIGHT_LOG_body-mnettool4.md` on `origin/body-mnettool4`; merge that commit into
     body-mnet4 before computing any music input. Do the network, calibration and silent checks while you wait.
2. **Lanes** for the five check songs (`/secondary/hyst-data/audio/checkset/`, 5 mp3) and the three danced songs: `arousal_b7`, L4 projection,
   ear energy, beat phase, same model and normalisation as round 1.
3. **Sampling:** `numpy.random.default_rng(30011)`, settings as round 1. Each candidate is simulated (no render needed for gating) on 10 s
   warm-up + 30 s: silent, and each of the five songs at Kosta's start times (Blue Lagoon 0:20; 21st Century Schizoid Man 0:58; Epitaph 5:45;
   Breathe 1:17; One of These Days 3:57). It must pass the gates on all six. Take the first 8 that pass, in draw order, as S01-S08. Log every
   discard with its failing gate(s) and song.
4. **Round-1 reference:** round-1 S03 (round-1 network and inputs, unchanged, from `/secondary/hyst-data/body/motornet_toy/clips/settings.json`)
   simulated and gated at 30 s per song. If it fails a gate on a song, that song's pair is not rendered and is reported; S03 is not replaced.
5. **Stop rule (7.47.4.8) before rendering Part B:** on the silent runs, if all 8 settings have PR < 3 in both populations AND base yaw
   p5-p95 range < 20 deg, write "STOP RULE HIT" with the numbers in the night log, push, and stop.
6. **Renders** (lamp, same camera and framing as round 1, 30 s, 1280x720 h264, aac where music):
   - Part A: S01-S08 silent.
   - Part B: `default_rng(30031)` draws 5 different settings from S01-S08, one per song, songs in the order above; per song render that
     setting and round-1 S03 on the song's 30 s excerpt, audio muxed.
   - Save CSVs and activity arrays as round 1. `manifest.json`, `settings.json`, `numbers.json` (per clip: PR per population, base yaw and
     shoulder p5-p95, facing drift, mean hand speed; per song: mean ear energy and mean `arousal_b7` over the 30 s).
7. **Done when:** rules file pushed; all clips gated and in the manifest; you have looked at 3 frames per clip; night log with MORNING
   SUMMARY pushed with **"CLIPS READY <commit>"**. Then stop. Do not show clips to the user; the overseer checks them first.

**Out of scope (stop and ask; log FOR USER):** any change after the rules file is pushed; choosing excerpts or settings; training or learning;
the limbic part; cortex changes; hardware; other audio; the session tool and report (30A's).
