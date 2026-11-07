# Builder prompt: work order 14B, K5-pass2: trainer, timing, run, check, videos (2026-11-07)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min: detached and memory-capped (`systemd-run --user --unit=hyst-wo14-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1; the script waits while it is 0). Pausable (`systemctl --user freeze/thaw`), stoppable (`systemctl --user stop`, checkpoint, clean exit), restartable with one command without losing finished work. Kabl jobs share this machine: keep to your thread and memory cap, check `free -g` before launching.
- **Push your branch with a first commit within 30 minutes and before any long run.** Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated and pushed after every phase. Usage limits or a power-off may stop you; the overseer resumes you.
- **Worktree: none new.** Stay in the worktree your session is pinned to (`/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-k5video`), absolute paths. There: `git fetch origin && git checkout -b body-k5p2 origin/body` (f44a196 or later). Push `body-k5p2`.
- **Your share: 6 threads, 10 GB** (8 GB OOM-killed the K5 try 1 check once; size the cap from a measured round). Environment
  `/secondary/hyst-env/body`. Data under `/secondary/hyst-data/body/k5p2/`. Do not change `k5_train.py`, `k5_eval.py`, `m3e*.py`, `m3f*.py`
  (agent 2 owns m3f): import them; new files `k5p2_*.py`.

## Read first

`docs/BRAIN_SPEC.md` §7.22-7.27 (binding: the pass2 body, movement changes, bar = full K5 bar + check-csv on the three danced songs + (e'1)
and (e'2) per song, the §7.26 round-2 rule, the 30 h box); `scripts/body/K5_RUN.md`, `docs/NIGHT_LOG_body-k5train.md` (try 1 trainer,
early stopping, pause/stop/resume requirements), `docs/BUILDER_PROMPT_WO10_K5_RUN.md` (the pause/stop rules 1b: keep them all);
`docs/NIGHT_LOG_body-m3f.md` (M3f: body v2f, switches, normalisation, selected weights jerk 0.03 / switch 0.01); your own
`docs/NIGHT_LOG_body-k5video.md` (full-song rollout, joint CSV, `--joint-csv` render, segments); `docs/hf_v47_eprime_reference.json`.

## The work

1. **Trainer** `k5p2_train.py`: K5 try 1's trainer (one full pass over the 15,624 training windows in the fixed seeded order, validation
   every 200 rounds on the 217 validation windows, early stopping as try 1, checkpoint after every round, atomic, pause/stop/resume as WO10
   1b, mains-power wait) with M3f's body and loss in place of M3e's: body v2f, movement changes 1-4 on, jerk 0.03, switch 0.01, and the two
   §7.27 hinges plus the hard clip **as agent 2 builds them in work order 14A** (branch `body-m3f`; merge it from origin when its toy rerun
   is merged into body). Seed and order as try 1. Tests: resume bit-identity in process (as try 1), one round runs.
2. **Timing:** time 3 real rounds with the final loss (after 14A lands) and project one pass + validations + the check. Write it in the
   night log. **Launch without asking if the projection is <= 30 h** of compute (§7.27 point 5); above that, stop and report to the overseer.
   **Do not launch before the overseer tells you 14A's toy rerun passed and is merged.** You can build and test everything before that.
3. **Run** (one detached capped service, mains only, pausable/stoppable). Report at each validation (round, ext/int (a)) to the overseer.
4. **Check** on `best.pkl`, ARGMAX for the verdict (sampled reported): the K5 check exactly as try 1 (1,071 windows, 357 held-out songs,
   trained / untrained / kappa = 0, per-song bootstrap, paired) PLUS the three danced songs as in work order 12 (continuous full-song
   rollout, joint CSV, `hyst check-csv` per song must pass) PLUS (e'1) and (e'2) per song against `docs/hf_v47_eprime_reference.json`
   (Instant Crush 5.320 / 0.01210, Five Years 5.182 / 0.00661, Presence 7.501 / 0.01431). Also report (e), table-contact time per song, per
   joint time within 2 deg of a limit, and readability per 60 s (report only).
5. **Videos** for the user's eye: the three songs at 1080p and a 720p copy under 30 MiB, and a three-panel 720p comparison per song
   (v47 one arm | fallback | K5-pass2, same audio) under 30 MiB.
6. If pass2 fails, stop and report: §7.26 governs round 2; do not change anything yourself.

## Done when

Trainer tests committed; timing and launch in the log; the check result per bar component with intervals; check-csv per song; (e') per
song; videos made and looked at (frames at start, middle, end and the most-moving moment, described without judging). Night log MORNING
SUMMARY; branch pushed. Then report to the overseer.
