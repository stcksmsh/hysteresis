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
