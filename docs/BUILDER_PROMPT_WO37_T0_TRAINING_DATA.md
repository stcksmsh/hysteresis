# Builder prompt: work order 37, T0 training-data pipeline for imitation training (2026-11-14)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER"
instead of waiting. If you start fresh, everything is named below.

**Binding:** `docs/BRAIN_SPEC.md` **§7.56** (Kosta's ruling on `docs/PLANNER_BRIEF_LOWPASS_RELOOK.md`), points 6 (T0 only) and 8 (overseer
notes). Then §7.55 and §7.47-7.52. **T0 only: no model, no training, no clips, no verdict.** The installation is ONE arm.

**Header rules:**
- In your current worktree: `git fetch origin && git checkout -b body-t0 origin/body`. Absolute paths; no new worktrees.
- Cores 6-13 (8 threads, §0). Jobs longer than 2 minutes run as detached, memory-capped units (`hyst-wo37-<fresh-name>`, `MemoryMax=16G`,
  `MemorySwapMax=0`), e.g. `systemd-run --user --unit=hyst-wo37-lanes -p AllowedCPUs=6-13 -p MemoryMax=16G -p MemorySwapMax=0 /abs/script.sh`.
- Python through `python -u`; read each unit's log 1 minute after start (a unit that "succeeds" can hide a crashed step).
- Run on battery; never wait for mains.
- Commit and push the code before every run; push at least every 30 minutes.
- Plain commit messages with **no co-author or attribution lines**.
- No installs, downloads, uploads or SMPL model files. Environment `/secondary/hyst-env/brain`.
- Round-1, look-test and low-pass files and outputs unchanged. New output goes to `/secondary/hyst-data/body/t0/`. Audio stays outside git.

## Read first

- `docs/BRAIN_SPEC.md` §7.56 (all of it), §7.55, §7.47.
- `docs/RETARGET_RULES.md` (a)-(n), `docs/LOWPASS_REPORT.md`, `docs/MOTORNET2_RULES.md` (Inputs), `docs/EAR_ENERGY_RULES.md`.
- `/secondary/hyst-data/datasets/finedance/INVENTORY.md`, `readme.md`, `LICENSE.txt` (never upload or redistribute).
- Code: `scripts/body/lowpass_run.py`, `lowpass_cutoff.py`, `retarget.py`, `retarget_run.py`, `retarget_limiter.py`, `jitter_diag.py`
  (`run_variant`), `motornet.py` (`spinal`), `make_arm_v2p.py`; lanes: `motornet_part3.py`, `motornet_music.py`, `motornet2_lanes.py`,
  `ear_energy.py` (+ `ear_energy_norm.json`); cortex: `scripts/brain/b2.py`, `fast_features.py`.

## The work

1. **Rules note `docs/T0_RULES.md`, pushed before any full run.** The overseer reviews it. It states, per 7.56.8:
   - the song split (unit = song; names compared stripped and lower-case; audio hash of the decoded mono 44.1 kHz signal; identical audio
     under different names merged; seed 33001; test = round(0.15 x songs), validation = round(0.10 x songs), rest train); the list of songs
     per split goes into `t0/split.json`;
   - the check of the 5 check songs and 3 danced songs against FineDance (no name or audio-hash match);
   - the lane recipe and the B7 checkpoint path; the standardisation (train songs only, clip +-3) and where the constants are written;
   - the retarget target stage for V1 (2.50 Hz) and V2 (5.75 Hz): H1 output at 100 Hz, before the limiter; time alignment;
   - window rule (non-overlapping 20 s from sequence start, tail dropped) and gates at 1.25 (all parts);
   - file formats in `t0/` (one npz per sequence: lanes (T, 8) at 100 Hz with column names: beat cos, beat sin, arousal_b7, ear energy, L4 1-4, targets_V1 (T, 5), targets_V2 (T, 5), window
     table with per-variant pass / failed parts), and the run plan with time estimates.
2. **Reproduction before any FineDance run:** recompute the cortex lanes for one check song (from
   `/secondary/hyst-data/body/motornet_toy/work3/`) and one danced song with your code and compare with the stored lanes (max abs
   difference per lane, in the log and the rules note). If a lane differs by more than 1e-4, write "HOLD lanes <lane> <diff>", push, stop.
   Also reproduce one look-test window's V2 target stage from `lowpass/work/` (max abs difference in degrees).
3. **Time estimate:** run lanes + retarget + gates on one long FineDance sequence; log the wall time and the projected total. If the
   projected total is above 10 hours, write "HOLD time <hours>", push, stop.
4. **Full run** (detached unit; resumable: skip a sequence whose npz exists and verifies; stoppable at any time without loss).
5. **Report `docs/T0_REPORT.md` + `t0/numbers.json`:** per variant, per split and per genre: sequences, windows kept / dropped by failed
   part, tails dropped, usable hours; total usable hours per split; lane coverage (frames with every lane finite); run time; any
   FOR USER items. Numbers only, no verdict.
6. **Tests** for the split (song grouping, no song in two splits, seed reproducible), window cutting and the lane interpolation.
7. **Done when:** "T0 READY <commit>" in `docs/NIGHT_LOG_body-t0.md` with a short MORNING SUMMARY (songs per split, usable hours per
   split and variant, top failed parts), pushed. Then **STOP**. Do not start T1.
