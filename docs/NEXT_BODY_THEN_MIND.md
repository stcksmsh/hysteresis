# Next: the body study, then the mind spike (brief for the builder)

Status: brief, 2026-10-13. Branch `keys-decide` (never `master`).
Order decided by the user: **step 1 body, step 2 mind, step 3 decide.** Run them
in sequence. Nothing else is in scope.

Read first: `docs/EMOTION.md` (stages and rules), the "Emotion stage 1" and
"B workspace, round 2" entries of `docs/DANCE_HANDOFF.md`, and `docs/MIND.md`
(the full mind design, **parked**; step 2 builds only a small part of it).

## Why this order

The goal is an arm whose body conveys a song's feeling, driven by a simulated
mind whose mechanisms are real (see `MIND.md` §1, "the story is part of the
work"). Two things are unproven, and each can sink the rest:

1. **The body may not have the range.** B round 2 changed the feeling signals and
   the user saw "not enough differences, all 3 are mostly good". Nobody has shown
   that this arm can move in visibly different ways at all. A better mind cannot
   fix that: the study below has no music and no mind in it.
2. **Memory may not help the mind.** Stage 1's within-song R² is negative for every
   encoder. Whether a recurrent core with a rehearsal pass follows change inside a
   song is a cheap test, not yet run.

A failed body blocks everything downstream. A failed mind spike only parks MIND.
So the body goes first.

## Rules for both steps

- `EMOTION.md` rules hold: no stage assigns emotional meaning by hand; version 47
  stays reachable and byte-identical (`Off`, golden digests); additive sidecar
  changes only; frozen `src/` and `tools/` read-only; never drive hardware; data,
  models, audio and videos outside git.
- **Every pass/fail rule is committed before any result it scores.** Results are
  reported with numbers and the held-out set they were measured on.
- **Never say something improved or looks good.** The user judges by eye.
- Each step: at most **two rounds** (build, then one adjustment limited to what
  the failing check names). Then stop and report.
- Stop at every ★ and wait for the user.
- One arm only. No ensemble, no braking work, no melody-following, no change to
  the dance planner's output.

---

## Step 1: the body study

### Question

Can this arm, alone and in silence, move in ways a person tells apart?
`EMOTION.md` stage 2, check 2b, built minimally.

### What to build

**1. A body generator** (`crates/hyst-compile/src/body.rs`; a new module, the
dance planner untouched). Input: a body vector `b` (all values 0..1) and a seed.
Output: an 8 s one-arm `EnsembleScore` (joint angles per knot, world points), so
the existing preview and recorder render it unchanged.

The motion works **in joint space**, not by hand target plus IK: the body is the
point. Each clip is a short phrase of a few moves (the seed picks their order,
directions and timing, so two clips with the same `b` differ in content but not
in quality). Body parameters, from `EMOTION.md` stage 2:

| Group | Parameters (0..1) | What changes on the arm |
|---|---|---|
| Shape | curl–extension, height, arch | all bends together; shoulder lift; elbow against wrist |
| Effort: time | sustained–sudden | how concentrated each move's acceleration is (number of velocity peaks per move, after Laban Time as used by Cui, Maguire & LaViers 2019) |
| Effort: weight | light–strong | depth of each move, and firm stop against float at the end |
| Effort: flow | bound–free | follow-through and overshoot (damped against loose) |
| Space | direct–indirect | base yaw and wrist-roll wandering on the way to each target |
| Succession | direction, delay | base to tip or tip to base; lag between joints 0–300 ms |
| Initiation | which joint leads | base, shoulder, elbow or wrist starts the move |
| Breath | depth, rate | a slow expansion and contraction under everything |

The numeric ranges are the builder's first guess; write each one down with why.

**2. Feasibility (check 2a), committed before results.** Every clip respects the
rig's joint limits, speeds (240 °/s) and accelerations (8,000 °/s²), the hand-speed
cap the planner uses, and the 9 m/s² jolt mark. A clip that breaks one is slowed
(time-stretched about its centre) until it passes, never shown raw; report how
much stretching each region needed. A region that cannot pass without losing its
character is dropped and reported.

**3. Motion descriptors** per clip (`EMOTION.md` stage 2): per-joint speed,
acceleration and jerk (mean, 90th percentile), posture height, extension and
curl, joint-to-joint lag, periodicity. They are not the judge; they show what
actually differs and they build the triplets.

**4. Regions and triplets.**
- Sample 2,000 feasible body vectors; pick **8 regions** by farthest-point
  sampling in standardised descriptor space (so regions differ in what is
  visible, not just in parameter numbers). A region is a small ball around its
  centre (radius chosen so within-region descriptor distance is under a quarter of
  the between-region distance; report both).
- **24 triplets**: each has two clips from one region and one from another
  (different seeds for all three, so content never matches). Every region appears
  as the pair at least twice and as the odd one at least twice.
- Rendering: the existing `ensemble_preview` + `$D/record-ensemble.cjs`, one arm,
  same camera, same implement, same light, **no audio**, 8 s each. Three clips
  side by side as A | B | C, odd position shuffled. The key goes in a file the
  user does not open until all answers are in.

**5. The answer page** (`scripts/body_study/answer.html`): one triplet at a time,
plays once, buttons A / B / C, an optional free-text box ("what did the odd one
look like?"), saves all answers to a JSON file at the end. The free text is kept:
it is the user's own vocabulary for the regions, useful later and never a gate.

### Check, fixed before any result

- **Pass**: at least **16 of 24** correct (chance is 8; p ≈ 0.0009 under guessing).
- Report per region: how often it was found as the odd one, and which descriptors
  separate the regions found from those missed.

### ★ Stops

1. After the generator and the feasibility sweep: report the parameter ranges,
   how much stretching each region needs, and the descriptor spread. Send two or
   three single clips for a first look (not part of the test).
2. After the triplets and the page are ready: the user takes the test.
3. After scoring.

### If it fails

Round 2, once: widen what the misses point at (larger ranges, more use of base
yaw and wrist roll, stronger effort contrast), fresh regions, fresh triplets,
same rule. If it fails again: stop. The rig and implement as specified may not be
able to express enough, and that is a decision for the user (more joints,
different implement, different scale), not for code.

---

## Step 2: the mind spike

### Question

Does a recurrent core with a memory of having rehearsed the song follow feeling
*inside* a song better than stage 1's memoryless encoding? Only `MIND.md`
§3.4–3.6 with the reservoir core. **Not built**: the oscillator pulse (§3.2),
`audioic` (§3.3), the trained LTC core.

### Before it starts (the user)

Record the **whole-song dial** (`EMOTION.md` stage 4.3) on the three danced songs,
**audio only**, one pass each. The file is stored and not opened by the builder
until step 2's results are in. It is the only within-song truth that is the
user's own feeling.

**Dial format (user, 2026-10-14, before any recording):** a 2D pad, valence
(unpleasant to pleasant, horizontal) and arousal (calm to excited, vertical),
both −1..+1, recorded at 10 Hz against the audio clock, one pass per song,
pause allowed, no seek. The pad shows the current position with live numbers
and a colour that follows the position, so the user always sees what is chosen.
Gate 5 uses the arousal axis; valence is reported, not gated.

**Dial format, revised (user and overseer, 2026-10-14, after one try on Instant
Crush, before any step-2 result).** The user found "pleasant / unpleasant"
meaningless (music is nearly always pleasant to them) and the three songs mixed:
two feelings at once. A single valence line cannot hold that. Replaces the format
above:
- **Pass A, energy:** one vertical slider, calm (0) to energetic (1), plus a key
  tap where something lifts or lands (a build, a drop, an entry). 10 Hz on the
  audio clock, one pass per song, pause allowed, no seek. Gate 5 uses this track;
  the taps are the user's own "known lifts" for gate 4 on the three songs.
- **Pass B, two feelings:** a pad with two one-sided axes, both 0..1, both may be
  high at once: horizontal **light / bright** (hopeful, joyful), vertical
  **heavy / dark** (sad, ominous, longing). Wording on the page: "how the music
  sounds, not whether you like it". Reported, never gated: against the readouts
  DEAM valence (light minus heavy) and GEMS joyful activation, sadness, tension,
  nostalgia.
- A song picker: any song, any order, each pass once per song; a redo only by an
  explicit "discard and redo", the discarded take kept.
- **Instant Crush, try 1** (`/secondary/hyst-data/emotion/dial/dial-ic-try1.json`,
  old 2D pad, 0–329.0 s): its arousal axis is the song's pass A. The spans
  2:15–2:51 (135–171 s), where the user was undecided, are masked out of every
  score, and so is everything after 329.0 s. Its valence is kept as data only,
  marked "old wording". It gets no taps; gate 4 on Instant Crush uses the
  other sources the gate names.

**Known lifts for gate 4, taken from the curves (user, 2026-10-23, after
recording, before any step-2 result).** The user recorded every pass but made no
Space-bar taps. Gate 4's "known lifts" on the three songs and on MERP come from one
rule applied to an energy curve, fixed here before `check1b.py` is written:
- Curve: on the three songs, the user's pass A energy (0..1); Instant Crush uses
  try 1's arousal mapped to 0..1 as (a + 1) / 2. On MERP, each song's mean-rater
  arousal, mapped linearly from MERP's scale range to 0..1.
- Clean-up, because the user moved the dial in a few quick jitters and may have
  flicked it at the end: a running median over 1.5 s (15 samples at 10 Hz), then a
  centred running mean over 2 s. The first 2 s and the last 5 s of every song are
  never a lift. Instant Crush's masks (135–171 s, after 329.0 s) hold: a rise that
  touches a masked span is not a lift.
- A rise is any time t where the cleaned curve at t + 4 s minus at t is at least
  0.15. Overlapping and touching rise times merge into one rise; its onset is its
  earliest t.
- Reaction lag: a person moves the dial after hearing the change. The lift is
  placed at the rise's onset minus 1.5 s, the same constant for every song and for
  MERP.
- Two lifts closer than 16 beats keep only the first.
- A song with no lift is left out of gate 4 and reported. The number of lifts per
  song and in total is reported next to gate 4's p-value.
- The builder applies this rule without opening the dial files before step 2's
  results are in: `check1b.py` reads the files only when it runs, and lifts are
  printed only with the results.

**MERP as fetched, and the open points of check 1b (user and overseer, 2026-10-23,
after ★ 1, before `check1b.py` is written).** MERP differs from what `MIND.md`
assumed: 11 of its 54 songs are excerpts of 31–48 s, and the authors' filtered
labels are 2 Hz series that skip the first 12–17 s of each song (see
`/secondary/hyst-data/emotion/SOURCES.md`, "MERP"). Decided:
- **Labels (user: option a).** Use the 3,482 trials the authors kept (277 raters),
  but take each trial's raw 10 Hz series, which starts at 0 s. Rescale and smooth
  it the way the authors did; which variant of their steps (rescale per trial or
  per rater; smoothing before or after taking every 5th sample) is chosen by how
  well it reproduces the filtered file on the overlap, and the match is reported.
  Where a rater has more than one raw trial for a song, use the one that matches the
  filtered series best. Per song, average the trials, then take the mean over each
  0.5 s step of the ear's grid.
- **Songs (user).** Only the 43 MERP songs longer than 50 s are used in step 2,
  everywhere: five folds by song (seeded as `check1.py`), readouts, gates 1–4. The
  other 11 are not used.
- **Which pass is scored.** Gates 1–3 and 5 score the dancer (ρ = 1); ρ = 0 is
  reported beside it. Gate 2 passes when each pooled measure's point value is not
  below stage 1's pick's lower 95 % bound (stage 1's numbers in `DANCE_HANDOFF.md`).
- **Gate 1.** "Non-overlapping" means the core's lower 95 % bound is above the
  reference's upper bound, on DEAM and on MERP each. Bootstrap as `check1.py`
  (2,000 resamples over songs, percentile).
- **Gate 3.** One seeded shuffle of the step order per held-out song, both passes
  shuffled the same way, readouts as trained; it must hold on DEAM and on MERP each.
- **Gate 4.** Per step, the distance between the ρ = 1 and ρ = 0 mind states (PCA
  64). Statistic: the mean over lifts of that distance averaged over the 8 beats
  before each lift. Null: the same number of 8-beat windows per song drawn at
  random from windows that overlap no lift window, 1,000 draws, p = (1 + draws at
  or above) / 1,001. It must hold on MERP and on the three songs pooled, each.
  Beats: the three songs use their sidecar grids (Five Years its tempo map); MERP
  uses one beat tracker, named in `check1b.py`.
- **Gate 5.** "Five Years" opening is 0–30 s and its climax 156–258 s (2:36–4:18,
  from the version-46 notes): the mean arousal readout over the opening must be
  below the mean over the climax. "Presence" 120–190 s reads sad when sadness is
  among the top three of the nine predicted GEMS feelings averaged over that span
  and its mean there is above its mean over the rest of the song. Dial
  correlation: Pearson r between the arousal readout and the user's pass A, both
  as means over each 0.5 s step, masked spans left out, no lag shift; the core
  beats the reference on at least 2 of 3 songs. Readouts for the three songs are
  fitted on all DEAM 2013/2014 songs and the 43 MERP songs.

**Gate 2's readouts (user, 2026-10-24, after `check1b.py` was written, before it
ran).** Gate 2 compares with stage 1's DEAM-only fit, so its pooled timing R² comes
from valence and arousal readouts fitted on DEAM only, for the core and for the
reference alike (Emotify GEMS as before). Gates 1, 3, 4 and 5 keep the readout
fitted on DEAM and MERP together. The other points `check1b.py` lists as left open
(`POINTS_LEFT_OPEN`, 65a3bc5) stand as written.

### What to build (`scripts/emotion/`)

- **Ear**: stage 1's pick (`baseline+all`, 2,665 per 0.5 s), PCA to 64 fitted on
  training folds only.
- **Core**: 512 leaky units at the 0.5 s step; each unit's time constant drawn
  log-uniformly from 0.5 s to 60 s; sparse random recurrence (10 %) scaled to a
  spectral radius chosen inside training folds (start 0.9); seeded, nothing in it
  trained. Input: the 64-dim ear vector plus the rehearsal input.
- **Rehearsal**: pass 1 runs the core over the song from rest with no rehearsal
  input and stores its state. Pass 2 runs again from rest and also receives the
  stored state at +1, +4 and +16 bars (PCA'd to 8 each), scaled by ρ. ρ = 1 is the
  dancer; ρ = 0 is the ablation.
- **Readouts**: ridge from the state (PCA 64) to valence and arousal (DEAM
  2013/2014 release as in stage 1, plus **MERP**: 54 full-length songs at 10 Hz,
  annotations CC BY 4.0, audio per-track Creative Commons; Koh et al. 2023) and to
  the nine GEMS feelings (Emotify). Folds by song, same seeds and bootstrap as
  `check1.py`.
- Output: an additive `mindState` field (see `MIND.md` §5, minus `pulse` and `ic`).

### Check, committed as `check1b.py` before any result

Reference: stage 1's pick read memorylessly, same folds.
1. **Gate, within-song tracking**: per held-out song, Pearson r over time (song
   means removed) between predicted and rated arousal, averaged over songs, on
   DEAM and on MERP separately. The core must beat the reference on both, with
   non-overlapping 95 % bootstrap intervals. Valence reported, not gated.
2. **Gate, mood kept**: pooled timing R² and Emotify rank correlation stay inside
   stage 1's pick's intervals.
3. **Gate, memory is used**: shuffling the steps of each held-out song cuts the
   within-song arousal r by at least half.
4. **Gate, rehearsal**: on MERP and the three songs, the state's ρ = 1 vs ρ = 0
   difference in the 8 beats before known lifts exceeds random 8-beat windows
   (permutation test, 1,000 draws, p < 0.05).
5. **Gate, the user**: "Five Years" opening reads lower in arousal than its climax;
   "Presence" 2:00–3:10 reads sad; the arousal readout correlates with the user's
   dial better than the reference on at least 2 of the 3 songs.

All five gates must pass.

### ★ Stops

1. After MERP is fetched (size, licence text, hashes into `SOURCES.md`).
2. After `check1b.py` is committed, before running it.
3. After the results.

### If it fails

Round 2, once: only spectral radius, the time-constant range and the PCA size may
change. Fails again: MIND stays parked, the decoder (stage 3) uses the stage-1
encoding. Write down which gate failed and by how much.

### Round 1 result and step 2b (user, 2026-10-24, after the round-1 result)

Round 1 (`a3fab6e`) failed: gates 1 (MERP by 0.017), 2 and 4 failed; 3 and 5
passed. MERP gave no lifts under the b1775f8 rule (largest 4 s rise of the
averaged curves: median 0.05), so gate 4 had no MERP test. The core without
rehearsal (ρ = 0) tracked within-song arousal better than with it on both
datasets (DEAM 0.221, MERP 0.566). The user chose not to run round 2 and to try
**step 2b** instead. Step 2b is designed **after** seeing round 1, so its choices
(no rehearsal input, readouts on state and ear) are not tested by numbers already
seen: the fold-based gates below are a diagnostic, and the decision rests on gate
B, which compares on the three songs' dial with numbers not yet computed for the
new core.

**What changes (the step-2b core).** The round-1 core with no rehearsal pass at all
(ρ = 0, rehearsal input absent), and readouts (ridge) on the state PCA 64
concatenated with the ear PCA 64. Everything else as round 1: ear, units, time
constants, sparsity, the radius grid chosen inside training folds, folds, seeds,
bootstrap, the MERP labels and 43 songs, the gate-2 DEAM-only readouts. Anticipation
is not part of this step: if used later it is an explicit look-ahead in the body
(the system knows the whole song), described as that, never as learned.

**The smoothing control.** Ratings are smooth and lag the music, so a core with long
time constants may gain only by smoothing. Control: the reference (stage 1's pick,
memoryless ridge) with its predictions passed through a causal exponential smoother
with time constant τ and then delayed by L (prediction at t uses the smoothed
prediction at t − L). τ from {0, 0.5, 1, 2, 4, 8, 16, 32} s (0 = none), L from
{0, 0.5, …, 4} s, chosen per outer fold by inner-fold within-song arousal r on
training songs only. The core's predictions get the same option, chosen the same
way, so neither side has a post-processing advantage. The chosen τ and L are
reported per fold.

**Check 2b, committed as `check2b.py` before it runs.**
- **A1, beats smoothing (diagnostic gate):** within-song arousal r (as gate 1), the
  core against the smoothed reference, on DEAM and on MERP each: the core's lower
  95 % bound above the smoothed reference's upper bound.
- **A2, mood kept (diagnostic gate):** as round-1 gate 2.
- **A3, memory used (diagnostic gate):** as round-1 gate 3, on the core.
- **B, the user's dial (the decision):** on the three songs, readouts fitted on all
  DEAM 2013/2014 and the 43 MERP songs, Pearson r between the arousal readout and
  the user's pass A (as round-1 gate 5, same masks, no lag shift beyond the chosen
  L), the core against the smoothed reference. Pass: the core ahead on at least 2 of
  3 songs. Also reported: the plain reference and round-1's numbers beside them.
- Round-1 gate 5's two fixed tests (Five Years opening below climax; Presence
  120–190 s sad) are reported for the new core, not gated.

**Then.** A1 and B pass: the step-2b core is the encoding for stage 3 (the decoder),
and the claims it licenses are memory and within-song tracking, not rehearsal or
anticipation. A1 fails: the stage-1 encoding with the chosen smoothing is the
encoding for stage 3, and the memory claim is dropped. A1 passes and B fails: report,
the user decides. One run, no second round. ★ Stops: after `check2b.py` is committed
(before it runs), and after the results.

---

## Step 3: decide (the user)

| Body | Mind spike | Next |
|---|---|---|
| pass | pass | build full MIND (`MIND.md`: add pulse and surprise), then stage 3, the decoder |
| pass | fail | stage 3 on the stage-1 encoding; MIND parked |
| fail | either | widen the body (or change the rig); mind work waits |

## Handoff

Each step appends a dated entry to `docs/DANCE_HANDOFF.md`: what was built, every
constant and its origin, the check's numbers with intervals, what was not done,
and **"not verified by eye"** where that applies. Update the restart prompt's
"Where we are". Commit and push to `keys-decide`.
