# Builder prompt: work order 45B, finish WO45: A checks, S-B clip candidates, A report (2026-11-16)

You are a builder for Hysteresis, taking over WO45 from a session that hit its usage limit after training finished. Work alone and
unattended; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BUILDER_PROMPT_WO45_GRAMMAR_A.md` (header rules, steps 6-8) and `docs/A_RULES.md` **with addendum 1** (branch
`body-grammar`, commit 6f2eb5f), then `docs/BRAIN_SPEC.md` 7.73-7.77. No new training; do not change the rules note. One arm. Another
builder (WO47) works on cores 14-19: stay on cores 6-13.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-grammar origin/body-grammar` (the branch exists;
continue on it); absolute paths; no new worktrees. Detached units `hyst-wo45b-<fresh>`, `MemoryMax=10G`, `MemorySwapMax=0`, cores 6-13,
`python -u`; read logs 1 min after start; catch errors per item and log names. Run on battery. Commit and push before every run. Plain
commit messages, no co-author or attribution lines. No installs, downloads, uploads. Env `/secondary/hyst-env/brain`. Data
`/secondary/hyst-data/body/grammar/` (trained runs `runs/seed4510{1,2,3}/`, logs `logs/train4510*.log`: all three reached the 40-epoch cap,
validation 18.417 / 18.469 / 18.446, still improving at the cap). Night log `docs/NIGHT_LOG_body-grammar.md` (read it first). Keep messages short.

## The work

1. Read `docs/A_RULES.md` (sections 6-7 and addendum 1) and the night log; confirm the checkpoints load (best epoch per seed).
2. Report the training: per-head train / validation per epoch (all three seeds), the "no controls" validation, the gap, the auxiliary
   term, and the fact that every seed stopped at the cap while still improving.
3. Run the A checks exactly as `A_RULES.md` section 6 + addendum 1 fix them (residual-code utilisation; intervention matrix incl.
   direction-change rate and base-rotation speed; control substitution; jitter and frozen share vs re-joined human A1; the posture/gesture
   split; coherence over 2-4 s with the motif ablation), every seed, song bootstrap.
4. S-B clip candidates per section 7 + addendum 1 (sharpness-matched V1 vs V2; excerpts at or above the song's median RMS, not in the first
   or last 10 s, same excerpt across conditions). Render, manifest only; do not serve. Night log "SB CLIPS READY".
5. `docs/A_REPORT.md` and "A READY <commit>" in the night log, pushed; all tests pass. Then STOP.
