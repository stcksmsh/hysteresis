# Builder prompt: work order 18, K5-pass2 check and videos (pass2 is TRAINING now; build the check before it ends) (2026-11-08)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below. **K5-pass2 is training right now in systemd unit `hyst-wo14-a2`
(do not touch it, do not stop it, do not restart it).** It ends around 20:00-20:30 on 2026-11-08. Your job: build and test the check
(`k5p2_eval.py`) and the video scripts NOW, then run them on `best.pkl` as soon as training ends.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min: detached and memory-capped (`systemd-run --user --unit=hyst-wo18-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`), `python -u`, mains power only. **Always set --working-directory or absolute script paths** (a launch failed on a relative path). Kabl jobs share this machine; **pass2 uses cores 6-11 and up to 10 GB**: keep the check's development runs small (3 threads, 6 GB) until training ends; the real check then gets 6 threads / 14 GB (the K5 try 1 check was OOM-killed at 8 GB).
- **Push within 30 minutes and after every phase.** Log: `docs/NIGHT_LOG_body-k5p2.md` (append "Work order 18", MORNING SUMMARY on top).
- **Never go idle while a job you depend on runs:** watch it (a Monitor or a background wait loop) so you see it finish.
- **Worktree: none new.** Stay in the worktree your session is pinned to (`/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-k5video`, branch `body-k5p2`, at 53ff54e or later), absolute paths. `git fetch origin && git merge origin/body`. Push `body-k5p2`.
- Environment `/secondary/hyst-env/body`. Data: training run `/secondary/hyst-data/body/k5p2/run/` (`progress.json`, `train.log`, checkpoints, `best.pkl` at the end); write the check to `/secondary/hyst-data/body/k5p2/check/`, videos to `/secondary/hyst-data/body/k5p2/video/`.
- Do not change `k5_train.py`, `k5_eval.py`, `m3e*.py`, `m3f*.py`, `k5p2_train.py`: import them; new files `k5p2_eval.py`, `k5p2_video*.py`, tests.

## Read first

- `docs/BRAIN_SPEC.md` §7.19 A (argmax; kappa-0 wording rule), §7.22-7.32 (all binding; pass2 bar = full K5 bar + check-csv on the three danced songs + (e'1)/(e'2) per song; report lines added in 7.28-7.31; smooth u 7.32).
- `docs/BUILDER_PROMPT_WO14B_K5_PASS2.md` (the original pass2 order: steps 4-6 are this order's core).
- `docs/NIGHT_LOG_body-k5p2.md` (trainer, options, launch), `docs/NIGHT_LOG_body-k5train.md` (try 1 check: `k5_eval.py`, windows, bootstraps, OOM note), `docs/NIGHT_LOG_body-k5video.md` (WO12: continuous full-song rollout, joint CSV, `ensemble_preview --joint-csv`, `k5_render.sh`, segments, v47 regression), `docs/NIGHT_LOG_body-m3f.md` (WO14A-WO17: end-stop stats, parking gate, `m3f_endstop.py`, `m3f_gate17.py`, `m3f_park_diag.py`, clips).
- `docs/hf_v47_eprime_reference.json`. Code: `scripts/body/k5p2_train.py` (pass2 options: `--body v2f --hard-clip --floor-acc-hinges --contact-tc 0.006 --raised-plane --w-floor 1.0 --smooth-u`), `k5_eval.py`, `k5_video_*.py`, `m3f_report.py`, `m3f_endstop.py`, `m3f_gate17.py`.

## Steps

1. **`k5p2_eval.py`** (build and test now on an intermediate checkpoint `ckpt.pkl`, small, e.g. 30 windows; never write into `run/`):
   - The K5 check exactly as try 1 (1,071 windows, 357 held-out songs; trained / untrained / kappa = 0; per-song paired bootstrap; argmax
     verdict, sampled reported) on the pass2 body and options.
   - The three danced songs (Instant Crush, Five Years, Presence) as in WO12: continuous full-song rollout, joint CSV, `hyst check-csv` per
     song (must pass), (e'1)/(e'2) per song vs `hf_v47_eprime_reference.json` (IC 5.320 / 0.01210, FY 5.182 / 0.00661, PR 7.501 / 0.01431).
   - Report-only per song: (e); table-contact time; per joint share of time within 2 deg of a limit and exactly on a stop; longest stop-hold;
     longest hold of any pose (hand < 2 cm/s); clip-boundary holds; end-stop events per joint and hand acc/jerk within +-0.05 s of events vs
     the song at 50 Hz and 100 Hz, per episode AND pooled; shoulder-at-limit time; programs used and top share; readability per 60 s.
   - Pass2 kappa-0 control decides the inner-rhythm wording (7.31.3): report trained - kappa0 paired, both decoders, argmax.
   - Tests: a tiny end-to-end run; the full-song rollout's first 60 s bit-identical to the windowed rollout (as WO12); resume-safe.
2. **Videos** (scripts now, render after the check): three songs at 1080p + 720p copy < 30 MiB; a three-panel 720p comparison per song
   (v47 one arm | fallback | K5-pass2, same audio) < 30 MiB. Page text should say "K5-pass2 policy". If you touch Rust: tests/clippy/fmt
   clean and the v47 regression byte-identical (as WO12).
3. **When `hyst-wo14-a2` ends** (watch `progress.json` "done" / the unit): run the check on `best.pkl` as one detached unit (6 threads,
   14 GB), then the videos. Look at frames (start, middle, end, most-moving moment) and describe them without judging.
4. Write `check/summary.json` and the night log; push; **report to the overseer: every bar component with intervals, check-csv per song,
   (e') per song, the report-only lines, trained - kappa0, video paths.** If pass2 fails a bar component, stop and report (§7.26 governs
   round 2; change nothing yourself).

## Done when

Check and video scripts committed with tests; check run on best.pkl; videos rendered and looked at; summary + night log pushed; report sent.
