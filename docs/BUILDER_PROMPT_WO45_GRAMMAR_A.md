# Builder prompt: work order 45, A = motor grammar conditioned on controls (7.73 "THEN: A", 7.74) (2026-11-16)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BRAIN_SPEC.md` **§7.73, §7.74 and §7.76** (points 2 and 3; including their overseer notes), then 7.59-7.71 where they do not change them. No
verdict. One arm. **A only: no listener (B), no teacher, no lookahead selection (7.74 "planned stage", 7.76.5: later), no music-fit critic (7.76.7: deferred).** You do not
run Kosta's viewing: the overseer serves it. Another builder (WO46) works on cores 14-19: stay on cores 6-13.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-grammar origin/body`; absolute paths; no new
worktrees. Detached units `hyst-wo45-<fresh>`, `MemoryMax=10G`, `MemorySwapMax=0`, cores 6-13, `python -u`; read logs 1 min after start.
Run on battery. Commit and push before every run. Plain commit messages, no co-author or attribution lines. No installs, downloads,
uploads. Env `/secondary/hyst-env/brain`. In (read-only): `/secondary/hyst-data/body/{t0,t0_phantom,t0_motorica,t1a2,t1b,controls,join}/`
(frozen gesture vocabulary and decoder `t1a2/runB/best.pt`). Out: `/secondary/hyst-data/body/grammar/`. Nothing on the root disk.
Motorica stays on this laptop. Training resumable per epoch. Scan every input for empty or malformed files before any training (E1 lost a
run to a zero-token song). Night log `docs/NIGHT_LOG_body-grammar.md`. Keep messages short.

## Read first

`docs/BRAIN_SPEC.md` 7.59-7.76 (7.73, 7.74 and 7.76 in full); `docs/CONTROLS_RULES.md` (with addenda 1-2), `docs/CONTROLS_REPORT.md`,
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
2b. **Control refinements, report-only, not adopted (7.76.3):** vigour split into amplitude (lamp path extent per token) and speed, with
   their correlation and each one's relation to the combined vigour; the sharpness 3 Hz threshold checked against filtered human vs realised
   robot motion and against noise (state the noise model), with sharpness at 2 / 3 / 4 / 6 Hz; pause as occupancy and duration at 2-8 s
   scales. `docs/CONTROLS_REFINE_REPORT.md`, night log "REFINE DONE". Nothing in A changes because of it without a ruling.
3. **Rules note `docs/A_RULES.md`, pushed before any training:**
   - architecture per 7.73 + 7.76.2: GRU 256 over gesture codes + absolute posture codes; inputs previous tokens, controls for the current
     token and the next 1-2 s through a small temporal convolution (state the window); a persistent STYLE / MOVEMENT-MODE embedding at
     sequence level (dataset + copy V1/V2 + genre where labelled), sampled per song at generation (state how); a persistent MOTIF state
     (latent, updated every 2 s, not every token; state its update rule and size); the accent input is the token-relative pattern (7.74
     Q1) — beat-relative timing is B's job later; parameter counts per part;
   - loss: token likelihood (heads as stated) + auxiliary control loss = expected controls under the predicted code distribution (per-code
     statistics of step 2) vs requested controls; the weight of the auxiliary term stated and fixed;
   - control dropout 15 % (whole vector); control corruption sampled from realistic JOINT control distributions (state the sampler, e.g.
     whole control vectors drawn from other training tokens or a fitted joint model; never independent per control);
   - data: FineDance + AIOZ (calibrated keep list) + PhantomDance + Motorica (Kosta's look check 2026-11-16: 11 yes, 1 partly,
     `docs/T0_PHANTOM_LOOK_RESULT.md`; a per-dataset switch, all on). Splits as T0. Song-level bootstrap everywhere. The copy (V1 / V2)
     enters through the style embedding (7.76.2; V2 copies are markedly sharper, `docs/PLANNER_BRIEF_VIEWINGS.md`, 7.75 pending: which
     copy generation defaults to is set after that ruling);
   - decoder A1 (7.74 Q4) for every trajectory; realised stage for every motion measure;
   - 3 seeds (7.68.9), early stopping and epoch cap, train/validation per head per epoch;
   - the A checks (step 6) with exact formulas, fixed before training.
   Tests: causality of the control window (no control beyond the stated horizon), control dropout and corruption rates, per-code statistics
   round-trip, a tiny overfit run.
4. **Timing run + estimate** for 3 seeds in parallel on cores 6-13. Night log "A ESTIMATE <hours, peak memory>". **Then STOP and wait for
   the overseer's GO** (it depends on WO46's posture-vs-gesture report and on the 7.75 ruling).
5. **Train** on GO.
6. **A checks (7.73), numbers only:**
   - residual-code utilisation and conditional entropy of the second gesture stage given the first (7.73: "before keeping the residual
     stage in A"); report;
   - intervention matrix: same start, one control varied at a time over held-out-song starts, including held-out combinations; output
     controls measured on the realised A1 trajectory; expected direction and effect size per control, with song-bootstrap intervals;
   - control substitution: one song's start, several control sequences (own, other performance's, shuffled, constant); does the output
     follow each (control match per sequence);
   - jitter and frozen share against re-joined human A1 (7.74 Q4 reference);
   - coherence over 2-4 s (7.76.2): state the measure (e.g. self-similarity of control and gesture-family sequences at 2 and 4 s), A vs human.
7. **S-B clip candidates** (not served; excerpt choice per 7.75 Q3 once ruled): human vs A with own oracle controls vs other performance's controls vs shuffled vs constant, held-out
   FineDance songs, 8 s, rendered as WO43 did; manifest only. Night log "SB CLIPS READY".
8. **Done when:** `docs/A_REPORT.md` and "A READY <commit>" in the night log, pushed; all tests pass. Then STOP.
