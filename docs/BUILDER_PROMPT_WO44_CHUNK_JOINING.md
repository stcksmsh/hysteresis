# Builder prompt: work order 44, chunk joining (7.73 parallel task) (2026-11-16)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BRAIN_SPEC.md` **§7.73** ("Parallel task: chunk joining"), then 7.61-7.63 for the decoder and the realised-stage jitter
measure. No verdict. One arm. **No training of A, B or any planner; the frozen vocabulary and decoder (`t1a2/runB/best.pt`) are not
retrained.** Another builder (WO43, controls) works on cores 6-13: stay on cores 14-19.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-join origin/body`; absolute paths; no new worktrees.
Detached units `hyst-wo44-<fresh>`, `MemoryMax=8G`, `MemorySwapMax=0`, cores 14-19, `python -u`; read logs 1 min after start. Run on
battery. Commit and push before every run. Plain commit messages, no co-author or attribution lines. No installs, downloads, uploads. Env
`/secondary/hyst-env/brain`. In (read-only): `/secondary/hyst-data/body/{t0,t1a2,t1b}/`. Out: `/secondary/hyst-data/body/join/`.
Nothing on the root disk. Night log `docs/NIGHT_LOG_body-join.md`. Keep messages short.

## Background (numbers from E1, overseer recompute)

In E1's T2 (`docs/T1B_REPORT.md`, per-song values `/secondary/hyst-data/body/t1b/e1/seed*/t2/measures.json`), power above 3 Hz at the
lamp (`p_gt3`, realised stage) relative to continuous human motion was: retrieval control 2.0x, random human chunks 2.5x, model 1.4x.
The controls concatenate raw human training chunks without the decoder, so the joins themselves add high-frequency power. The overseer's
check script is `scripts/body/overseer/e1_t2check.py`. Goal of 7.73: a joining method under which re-joined human chunks reach
human-level high-frequency power, reported before the S-B look.

## Read first

`docs/BRAIN_SPEC.md` 7.73, 7.61-7.63; `docs/T1A2_RULES.md`, `docs/T1A2_REPORT.md`, `docs/T1B_RULES.md`, `docs/T1B_REPORT.md` (controls
section); code `scripts/body/t1a2_realised.py`, the decoder and token code used by `t1b_t2.py` / `t1b_t2_lib.py` (how model tokens and
the retrieval / random controls become trajectories), `pos_measures` (`p_gt3`), `lowpass_cutoff.py`.

## The work

1. **Rules note `docs/JOIN_RULES.md`, pushed before any result:** the joining methods to compare (default set: (a) current: chunk by
   chunk, as E1/T2; (b) whole token sequence decoded in one pass with overlapping decoder windows and a stated crossfade; (c) any third
   method only if it needs no training, stated in full); overlap length and crossfade shape; the test material (FineDance validation +
   test songs: continuous human motion; the same songs cut into the E1 chunk length and re-joined in original order; the retrieval and
   random-chunk controls rebuilt with each method; E1 seed 41101's token sequences decoded with each method); the measures (`p_gt3` per
   joint and at the lamp, realised stage, ratio to continuous human per song; hand jerk; frozen-pose share; commanded vs realised RMS);
   the target fixed before computing: "human level" = re-joined human chunks within the between-song spread of continuous human `p_gt3`
   (state the exact interval); bootstrap by song, seed fixed. Tests: re-joining one unbroken human sequence cut at a single point
   reproduces the original away from the join; overlap decoding of a constant token sequence gives no extra power above 3 Hz.
2. **Run** every method on the test material. Save per-song values for recomputation.
3. **Done when:** `docs/JOIN_REPORT.md` (ratios to human per method and material, intervals, which methods meet the target, compute
   cost per minute of motion) and "JOIN READY <commit>" in the night log, pushed; all tests pass. Then STOP. No clips, no viewing.
