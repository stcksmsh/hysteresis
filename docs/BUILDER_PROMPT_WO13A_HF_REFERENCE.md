# Builder prompt: work order 13A, the high-frequency share (e) and its v47 reference (2026-11-06)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min: detached and memory-capped (`systemd-run --user --unit=hyst-wo13-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1; the script waits while it is 0). Pausable (`systemctl --user freeze/thaw`), stoppable (`systemctl --user stop`, checkpoint, clean exit), restartable with one command without losing finished work. Kabl jobs share this machine: keep to your thread and memory cap, check `free -g` before launching.
- **Push your branch with a first commit within 30 minutes and before any long run.** Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated and pushed after every phase. Usage limits or a power-off may stop you; the overseer resumes you.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- One arm, always: never a hexagon, ring or ensemble as a target (the v47 hexagon files are only a reference).
- Worktree: new `.claude/worktrees/body-hf`, branch `body-hf` from `origin/body` (9acbf19 or later). **Your share: 4 threads, 4 GB.**
  Environments: body `/secondary/hyst-env/body`, brain `/secondary/hyst-env/brain`.

## Read first

`docs/BRAIN_SPEC.md` §7.24 (binding; its last block "Overseer's operational defaults" defines (e) exactly), §7.23, §7.22;
`docs/NIGHT_LOG_body-k5video.md` (the K5 try 1 joint CSVs and the `--joint-csv` render); `scripts/body/arm_sim.py` (`csv_text`, joint order);
`crates/hyst-cli/src/main.rs` (`hyst score-csv SCORE_JSON OUT.csv [--hz 50] [--mode off|layered] [--agent N]`);
`scripts/body/v47_regression.sh` (the exact three v47 hexagon commands: `ensemble_preview OUT.html AUDIO SIDECAR --ring 6,0.8`;
`ensemble_preview` also takes `--score score.json` to write the compiled score).

## The work

1. **`scripts/body/hf_share.py`** (new): `hf_share(q_deg, hz)` for a (n, 5) joint trajectory in the CSV joint order -> the share of
   joint-velocity power above 3 Hz over the four non-roll joints, exactly as defined in §7.24's defaults (central-difference velocity,
   Welch, 4 s Hann segments, 50 % overlap, mean removed, power above 3 Hz / power above 0 Hz, summed over base_yaw, shoulder, elbow,
   wrist_bend). Plus a CSV reader (`hf_share_csv(path)`). Tests: a pure 1 Hz sine gives a share near 0, a 6 Hz sine near 1, a 50/50
   power mix of 1 Hz and 6 Hz near 0.5 (state tolerances). The toy builder (work order 13B) imports this file: **commit and push it within
   1 hour**, before anything else in this order.
2. **v47 reference, recorded before any pass2 result.** For each danced song (instant-crush, five-years, presence), compile the v47 Off
   hexagon score with the v47 commands plus `--score`, export each of the six arms with `hyst score-csv ... --mode off --agent N` (fresh
   `CARGO_TARGET_DIR` under `/secondary/hyst-data/`; the v47 html must stay byte-identical to the stored one, `cmp` it), and compute (e)
   per arm. Per-song value = mean over the six arms; also the mean of the three per-song values (the toy's reference). Write
   `/secondary/hyst-data/body/hf/v47_reference.json` and a copy `docs/hf_v47_reference.json` (commit it), and the limits 1.25 x each value.
3. **Report only, same measure:** K5 try 1 on the three songs (`/secondary/hyst-data/body/k5/danced/<song>.k5.csv`) and the fallback
   (authoring tool, example-sketch mapping) if a joint CSV can be made from its compiled score with `hyst score-csv --mode layered`
   (`scripts/author/retune.sh` builds that sidecar; one arm). Write `/secondary/hyst-data/body/hf/report.json`.

## Done when

hf_share.py and its tests are committed and pushed (within the first hour); v47_reference.json exists with six per-arm values per song, the
per-song means, the overall mean and the 1.25 x limits; the v47 html cmp result is stated; the report has K5 try 1 (and the fallback, or why
not). Night log MORNING SUMMARY with paths and numbers. Then report to the overseer.
