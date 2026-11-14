# Builder prompt: work order 37, T0 training data for the motor vocabulary + sequencer (2026-11-14)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER"
instead of waiting. If you start fresh, everything is named below.

**Binding:** `docs/BRAIN_SPEC.md` **§7.59** (point 2 = T0, point 8 = overseer notes; 7.56.8 and 7.56.10 where 7.59.8 keeps them). Then §7.55,
§7.50. **T0 only: no model, no training, no clips, no uploads, no verdict.** The installation is ONE arm. If anything is unclear or conflicts
with the repo docs, stop and ask (log "HOLD unclear <what>", push, stop).

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

- `docs/BRAIN_SPEC.md` §7.59 (all), §7.56 (points 8, 10), §7.55.
- `docs/RETARGET_RULES.md` (a)-(n), `docs/LOWPASS_REPORT.md`, `docs/EAR_ENERGY_RULES.md`, `docs/DATASET_LICENCES.md`.
- `/secondary/hyst-data/datasets/finedance/INVENTORY.md`, `readme.md`, `LICENSE.txt`; `/secondary/hyst-data/datasets/aioz/INVENTORY.md`,
  `LICENSE.txt`. Never upload or redistribute. **AIOZ `.pkl` files are untrusted: never `pickle.load` them; only a restricted unpickler.**
- Code: `scripts/body/lowpass_run.py`, `lowpass_cutoff.py`, `retarget.py`, `retarget_run.py`, `retarget_limiter.py`, `jitter_diag.py`
  (`run_variant`), `motornet.py` (`spinal`), `make_arm_v2p.py`, `v3_lib.py` (human FK, end-point measures); lanes: `motornet_part3.py`,
  `motornet_music.py`, `motornet2_lanes.py`, `ear_energy.py` (+ `ear_energy_norm.json`); cortex: `scripts/brain/core.py`, `b2.py`
  (`build_inputs`, `surprisal_lanes`), `fast_features.py`, `brain_mindstate.py`.

## The work

1. **Rules note `docs/T0_RULES.md`, pushed before any full run.** The overseer reviews it. It states, per 7.59.2 and 7.59.8:
   - the split over FineDance songs and AIOZ YouTube ids together (grouping, audio hash, seed 33001, 75 / 10 / 15); song lists in
     `t0/split.json`; the check against the 5 check songs and 3 danced songs (no name or audio-hash match);
   - the AIOZ restricted unpickler, adapter (SMPL 24 axis-angle -> the retarget code's input), derived frame rate, validity measures and
     prune rule, with the FineDance reference percentiles computed and written into the note BEFORE any AIOZ measure is computed;
   - the mirror (lateral axis found from the data, joint swap table, tests);
   - targets: after spline and guard, before H1, per variant (V1 2.50 Hz, V2 5.75 Hz); 4 copies per dancer; time alignment (motion frame
     k at k / fps; music time 0 = motion frame 0);
   - posture/gesture split (0.5 Hz filtfilt);
   - token features (0.5 s grid; the exact pooling of 7.59.8) and their standardisation constants file;
   - weighting (7.59.8 formula);
   - windows (non-overlapping 20 s, tail dropped) and gating through H1, limiter, servo, v2p at 1.25 (all parts);
   - file formats in `t0/`: per dancer and copy one npz with `targets` (T, 5) at 100 Hz, `posture`, `gesture`, `tokens` (n_tok, F) with
     column names, `token_mask`, `weight`, window table with pass / failed parts; and the run plan with time estimates.
2. **Reproduction and tests before any full run:**
   - recompute arousal_b7 and the L4 state of one check song (`/secondary/hyst-data/body/motornet_toy/work3/`) and one danced song and
     compare with the stored lanes; more than 1e-4 max abs difference -> "HOLD lanes <lane> <diff>", push, stop;
   - reproduce one look-test window's V2 target stage before H1 from `retarget_look/lowpass/work/` (max abs difference in degrees);
   - restricted unpickler refuses a crafted pickle; adapter round trip on one FineDance sequence; mirror twice = identity; split grouping
     (no song or id in two splits, all dancers and copies of a song together, seed reproducible); window cutting; token pooling on a
     synthetic signal.
3. **AIOZ validity check (report-only stop point):** measures and prune per dancer; `docs/T0_AIOZ_CHECK.md` with counts dropped per reason
   and per style, survivors' hours, and contact-sheet frames of 3 dropped and 3 kept dancers (looked at, never used to change the rule).
   Push "AIOZ CHECKED <commit>". If fewer than 30 % survive, log "HOLD aioz <share>" and continue with FineDance alone.
4. **Time estimate:** run the full chain on one long FineDance sequence; log wall time and the projected total. Above 10 hours ->
   "HOLD time <hours>", push, stop.
5. **Full run** (detached unit; resumable: skip an npz that exists and verifies; stoppable at any time without loss).
6. **Report `docs/T0_REPORT.md` + `t0/numbers.json`:** per dataset (never only pooled), per copy (V1 / V2 / mirrored), per split and per
   genre: dancers, windows kept / dropped by failed part, tails dropped, usable hours, tokens; weights summary (songs capped, effective
   hours); token-feature coverage (masked tokens); run time; FOR USER items. Numbers only, no verdict.
7. **Done when:** "T0 READY <commit>" in `docs/NIGHT_LOG_body-t0.md` with a short MORNING SUMMARY (songs per split, usable hours per dataset
   and split, AIOZ survivors, tokens per split), pushed. Then **STOP**. Do not start T1a.
