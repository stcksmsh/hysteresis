# Builder prompt: work order 45, A = motor grammar conditioned on controls (7.73 "THEN: A", 7.74) (2026-11-16)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BRAIN_SPEC.md` **§7.73 and §7.74** (including their overseer notes), then 7.59-7.71 where they do not change them. No
verdict. One arm. **A only: no listener (B), no teacher, no lookahead selection (7.74 "planned stage", not a build order).** You do not
run Kosta's viewing: the overseer serves it. Another builder (WO46) works on cores 14-19: stay on cores 6-13.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-grammar origin/body`; absolute paths; no new
worktrees. Detached units `hyst-wo45-<fresh>`, `MemoryMax=10G`, `MemorySwapMax=0`, cores 6-13, `python -u`; read logs 1 min after start.
Run on battery. Commit and push before every run. Plain commit messages, no co-author or attribution lines. No installs, downloads,
uploads. Env `/secondary/hyst-env/brain`. In (read-only): `/secondary/hyst-data/body/{t0,t0_phantom,t0_motorica,t1a2,t1b,controls,join}/`
(frozen gesture vocabulary and decoder `t1a2/runB/best.pt`). Out: `/secondary/hyst-data/body/grammar/`. Nothing on the root disk.
Motorica stays on this laptop. Training resumable per epoch. Scan every input for empty or malformed files before any training (E1 lost a
run to a zero-token song). Night log `docs/NIGHT_LOG_body-grammar.md`. Keep messages short.

## Read first

`docs/BRAIN_SPEC.md` 7.59-7.74 (7.73 and 7.74 in full); `docs/CONTROLS_RULES.md` (with addenda 1-2), `docs/CONTROLS_REPORT.md`,
`docs/JOIN_RULES.md`, `docs/JOIN_REPORT.md`, `docs/T1A2_RULES.md`, `docs/T1B_RULES.md`, `docs/T1B_REPORT.md`. Code: `scripts/body/controls_*.py`,
`join_*.py`, `t1b_*.py` (tokens, model, training, T2 measures), `t1a2_realised.py`.

## The work

1. **Controls as of 7.74**, in `controls_lib.py` behind a version flag (the WO43 values stay reproducible): vigour (combined), height,
   accent PATTERN (8 sub-slots / token mean; rule for a near-zero token mean stated), sharpness (rule for its undefined tokens stated),
   direction (unit 3-D, flag for near-zero speed), pause probability. Activity and accent level are not controls. Recompute per token for
   FineDance and AIOZ (PhantomDance / Motorica too, kept separate: see step 3). Night log "CONTROLS V2 <counts>".
2. **Absolute posture vocabulary (7.73 Step 0a: "posture vocabulary rebuilt on absolute posture"; 7.74 Q6: change-based posture drifted):**
   residual 2 x 256 like 7.70, fitted on the training split only, on absolute posture per token (state exactly which quantity). Report
   variance explained train / validation (7.63.8 STOP below 0.9 still applies). Per-code control statistics for the gesture codes (both
   stages) and posture codes: mean and covariance of the controls of the tokens assigned to each code, training split only.
3. **Rules note `docs/A_RULES.md`, pushed before any training:**
   - architecture per 7.73: GRU 256 over gesture codes + absolute posture codes; inputs previous tokens, controls for the current token and
     the next 1-2 s through a small temporal convolution (state the window), dataset/domain embedding; parameter counts per part;
   - loss: token likelihood (heads as stated) + auxiliary control loss = expected controls under the predicted code distribution (per-code
     statistics of step 2) vs requested controls; the weight of the auxiliary term stated and fixed;
   - control dropout 15 % (whole vector); control corruption sampled from realistic JOINT control distributions (state the sampler, e.g.
     whole control vectors drawn from other training tokens or a fitted joint model; never independent per control);
   - data: FineDance + AIOZ (calibrated keep list) + PhantomDance + Motorica (Kosta's look check 2026-11-16: 11 yes, 1 partly,
     `docs/T0_PHANTOM_LOOK_RESULT.md`; a per-dataset switch, all on). Splits as T0. Song-level bootstrap everywhere. Keep the copy
     (V1 / V2 / mirror) of every token available as a possible conditioning input (V2 copies are markedly sharper,
     `docs/PLANNER_BRIEF_VIEWINGS.md` Q1); whether A uses it waits for 7.75: build it as a switch, default off;
   - decoder A1 (7.74 Q4) for every trajectory; realised stage for every motion measure;
   - 3 seeds (7.68.9), early stopping and epoch cap, train/validation per head per epoch;
   - the A checks (step 6) with exact formulas, fixed before training.
   Tests: causality of the control window (no control beyond the stated horizon), control dropout and corruption rates, per-code statistics
   round-trip, a tiny overfit run.
4. **Timing run + estimate** for 3 seeds in parallel on cores 6-13. Night log "A ESTIMATE <hours, peak memory>". **Then STOP and wait for
   the overseer's GO** (it depends on WO46's posture-vs-gesture report and on Kosta's look check).
5. **Train** on GO.
6. **A checks (7.73), numbers only:**
   - residual-code utilisation and conditional entropy of the second gesture stage given the first (7.73: "before keeping the residual
     stage in A"); report;
   - intervention matrix: same start, one control varied at a time over held-out-song starts, including held-out combinations; output
     controls measured on the realised A1 trajectory; expected direction and effect size per control, with song-bootstrap intervals;
   - control substitution: one song's start, several control sequences (own, other performance's, shuffled, constant); does the output
     follow each (control match per sequence);
   - jitter and frozen share against re-joined human A1 (7.74 Q4 reference).
7. **S-B clip candidates** (not served; excerpt choice per 7.75 Q3 once ruled): human vs A with own oracle controls vs other performance's controls vs shuffled vs constant, held-out
   FineDance songs, 8 s, rendered as WO43 did; manifest only. Night log "SB CLIPS READY".
8. **Done when:** `docs/A_REPORT.md` and "A READY <commit>" in the night log, pushed; all tests pass. Then STOP.
