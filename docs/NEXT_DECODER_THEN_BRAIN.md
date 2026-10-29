# Next: the decoder, then the brain (work order)

Status: work order, 2026-10-28. Branch `keys-decide` (never `master`).
Replaces `docs/NEXT_BODY_THEN_MIND.md` as the current work order (that one is
closed: step 1 passed 30/32, step 2 and 2b reported in `ARCHITECTURE.md` §4).

Read first: `docs/ARCHITECTURE.md` (state, numbers, Q1–Q8), `docs/EMOTION.md`
(rules, stages 3 and 4), `docs/MIND.md` §1 (why the mind is part of the work).

## 1. The goal, in the user's words and as settled

- The work is **a soulful machine**: an arm whose whole body conveys a song's
  feeling, driven by a simulated brain whose mechanisms are real. The brain is
  part of the artwork. It must be creepy, mimic the human brain, and be "almost
  human as much as the hardware allows". Showing the brain is part of the piece.
- The end product is **a tool that conveys what we decide to convey**, and an
  installation people watch. Not a research paper.
- **Division of labour.** СИНТЕЗА (projector) follows beat and structure: what
  the machine *hears*. АФЕКТ (arm) follows the feeling and abstraction: what the
  machine *feels*. Both read one engine.
- **Truth rule.** Every public claim is a real, checked mechanism, listed in the
  truth table (`ARCHITECTURE.md` §5). "It feels" is never claimed.

## 2. Decisions the user made on 2026-10-28

1. **Order: the decoder (body path) first, the brain after.** Reason: the brain's
   value only shows through the body; a brain nobody sees move repeats the
   "gates without eyes" loop (`ARCHITECTURE.md` lesson: a green suite says
   nothing about looks). The decoder also fixes the `mindState` interface the
   brain plugs into later.
2. **The brain will be trained** (self-supervised prediction), not left random,
   so that "it learned music", "it is surprised", "it habituates", "it dreams"
   become true claims. CPU only (see §6).
3. **The brain runs at 100 Hz**, with two-rate input (see §5).
4. **The projector/arm split above stands.**

Q1–Q5 of `ARCHITECTURE.md` §6, answered 2026-10-28 (overseer's recommendations
plus four changes, marked **new**):

- **Q1 → a.** Stage 1 + 8 s smoothing drives the body. `core-2b` is checked as a
  candidate inside check 3 only; no further work on it (the brain replaces it).
- **Q2 → a, anchored, with c as baseline. New: anchors and an authoring layer.**
  Distance-matching alone cannot tell "sad" from "its mirror image": a map that
  is rotated or flipped scores the same. So two axes are pinned to the user's own
  dial and to the perception literature (D2). And the user can bias the result
  per section (D1 `authored` lane), because the goal is a tool that conveys what
  we decide.
- **Q3 → a.** Layered on version 47. Joint limits in `Layered`: the body
  generator's per-joint limits (D3).
- **Q4 → b, plus events. New.** Mood changes per phrase; events (D4) act at their
  own time, not at phrase edges. A startle that waits for the phrase edge is not
  a startle.
- **Q5 → a, plus afterglow. New.** Preparation before lifts ("it knows the
  score") and a slow release after them. Same mechanism, no new moves.

**★0: the overseer reads these back to the user in one message and gets an
explicit yes before any build.** If the user changes one, write the change here
as a dated note first.

**Note (user, 2026-10-28, after ★0; the user's yes for ★0).** Five changes to the
text below. Where they differ from §4, this note wins.
1. **Anchors (D2).**
   - *Energy:* the mood direction is fitted on DEAM + MERP arousal, training folds
     only. The user's dial pass A only checks its sign: the correlation of
     `mood.energy` with pass A must be positive on each of the 3 songs (part of
     check 3).
   - *Power:* the second anchor is Emotify's GEMS "power" → Laban weight (light →
     strong), fitted on training folds only, sign-checked against the user's pass B
     heavy/dark axis. **This link is weak:** "power" is not the user's "heavy/dark",
     and 3 songs is thin. If the sign disagrees on 2 of 3 songs, the anchor is
     dropped and weight is left free.
   - Height is not anchored.
2. **`authored` lane:** empty in check 3, in stage 4 and in every other check.
3. **Events: a new step D4a, a lift detector with its own check, before D4.**
   - Truth: the 6 lifts from the user's energy curves (check1b `lifts.json`) plus a
     tap pass the user records (3 songs, audio only, one tap where something
     arrives or lands). Stored before any detector result; the builder does not open
     it until the detector is committed.
   - Candidates, rules fixed before results, nothing fitted on the user's songs:
     (a) version 47's own Foresight logic (arrival lift sign, cuts); (b) the analysis
     chain's section boundaries with an energy rise across them.
   - Pass: a hit is within ±1 bar; at least 75 % of tapped lifts hit, at most 1 false
     alarm per minute, over all 3 songs together. Both candidates reported.
   - Round 2 may change thresholds only. Fails twice: events off, D4 works at phrase
     edges only.
   - The tap page goes to the user only when D4a starts.
4. **Afterglow:** unchanged.
5. **Interface (D1).** The anchors are named lanes, `mood.energy` and `mood.power`,
   so a later source keeps their meaning. The remaining components go in
   `mood.rest`, which is source-specific; the D2 map is refitted per source (a
   rerun, not a redesign).

**Note (overseer, 2026-10-28, before the D1/D2 builder prompt): check 3 made
operational.** Fixed here so `check3.py` has nothing to decide:
- *Segments:* 8 s windows (the body clip length), non-overlapping, from DEAM
  2013/2014, Emotify, the 43 MERP songs and the user's 3 songs; mood is the mean
  over the window. Folds: the five folds by song of `check1b.py` (the user's songs
  are held out together as a sixth set, never trained on).
- *Motion of a segment:* the decoded 15-dim body vector rendered by `body.rs` with 3
  fixed seeds; its descriptors are the mean of the 3 clips' 37 descriptors,
  standardised on training segments. An infeasible body is stretched on the
  existing ladder; one still infeasible counts as a failed segment and is reported.
- *Distances:* Euclidean on standardised mood lanes and on standardised descriptors;
  Spearman rank correlation of the two upper triangles, per held-out fold, then the
  mean over folds.
- *Shuffle test:* 1,000 permutations of the segment pairing inside each held-out
  fold; pass if the observed mean beats 99 % of the permuted means.
- *Against the baseline encoding:* the same map fitted to the 49-dim baseline
  encoding; pass if the bootstrap 95 % interval (2,000 resamples over held-out
  songs) of the difference (decoder minus baseline map) lies above 0.
- *Energy sign:* as note 1, on each of the user's 3 songs.
- Reported beside it, not gated: the library lookup and `core-2b`, the power
  anchor's signs, each anchor's strength on held-out songs, the share of failed
  segments.

**Note (user, 2026-10-29, after D2 round 2, D3 and step H; before anything below is
computed). Rulings A and B and an order change. New rules; where they differ from §4
or §6, this note wins.**

*A. Encoding: `core-2b`.* Best on the user's dial (sixth set rho 0.435), second on
the public references (DEAM/MERP 0.270), near the anchor spec. baseline49 is out: on
the user's songs its anchored links run backwards (energy→time −0.27, power→weight
−0.16). The decoder is last on every human reference. The differences are small and
every score is weak; the truth table says so and claims nothing beyond the numbers.
`core-2b` is the placeholder source of `mindState` until the brain (§6) replaces it;
no further encoding work.

- A1, anchors. The anchor spec is enforced on `core-2b` as on the decoder (each
  anchored link held-out r ≥ 0.5). Report whether it meets all 24 links (five folds
  plus the sixth set, four links each). Also report, for `core-2b`'s own lanes, the
  energy sign against pass A on each of the 3 songs and the power sign against pass B
  (the drop rule of the 2026-10-28 note applies).
- A2, spread fix (new rule). Cause: every check is rank-based, so a compressed or
  saturated map scores the same as a full-range one; the forced links likely saturated
  the sigmoid (stage1 size 0.99, time 0.98–0.99; `core-2b` on the sixth set: arch 0.98,
  succession_direction 0.98–0.99, succession_delay 0.95, breath_rate 0.02, energy
  0.97–0.99). Fix: no saturation. Each body dimension goes through its quantiles over
  the training corpus: 5th percentile → 0.05, 95th → 0.95, linear in rank between.
  Order is kept. The D2 references are rerun on the fixed map and every change is
  reported.
- A3, spread requirement, fixed here before results, scored on the user's 3 songs in
  the body-study region space (the 8 regions of round 2, told apart 30/32):
  1. each song's phrase bodies visit at least 2 regions;
  2. no two songs share their most-visited region;
  3. no body dimension sits within 0.05 of 0 or 1 for more than 20 % of phrases.
  Fails: one adjustment, of the quantile range only, then stop and report. Nothing
  goes to D4 with flat bodies.

*Operational points (overseer, fixed with this note, before results):*
- The quantile map acts on each dimension's value before the sigmoid (same order as
  after it, no float ties at saturation). Empirical CDF of the training corpus's
  decoded values, linear between ranks (so the 5th percentile lands at 0.05 and the
  95th at 0.95), clipped to [0, 1]. Training corpus: a fold's training segments for the
  fold scores; all five folds' segments for the sixth set and the 3 songs' phrases, as
  `final_maps.py` fits the sixth-set map.
- "Rerun the D2 references": `core-2b`'s DEAM/MERP rho (gate 1 shuffle and the value),
  GEMS rho, the sixth set against the dial, failed segments and the 24 links, before
  and after the fix, same folds, seeds and code path as `check3r2.py`.
- Region of a phrase: its body rendered by `body.rs` with the 3 check-3 seeds, mean of
  the 37 descriptors, midrank against the r6 sweep (`body_regions::rank`); the region is
  the nearest (Euclidean) mean of a region's 12 clips' midrank vectors. Every phrase
  gets a region; the distance to it is reported.
- Phrases: `bodyTrack.phrases` (the planner's `musicalMemory.phrases`). Rule 3 is
  scored per song and per dimension, all 15 dimensions.
- The one adjustment allowed: the two quantile anchors (5th/95th → 0.05/0.95) moved
  symmetrically, nothing else.
- A1 (user's answer, 2026-10-29): round 2 already fitted `core-2b` with the
  decoder's bound, and it is deterministic. A1 is therefore the report of round 2's
  links (22 of 24; misses fold 4 energy→size 0.487 and sixth set energy→time 0.378),
  plus the signs above. The 24 links are reported again after the A2 fix. No stricter
  margin.

*B. Clock lag: keep the music's timing; shrink amplitude, not time.*
- Under the per-joint limits, a figure that would break a limit is scaled down in
  amplitude until it fits. It is not time-stretched. Report the shrink per figure. If
  a song needs more than 50 % shrink on more than 20 % of its figures, report it,
  because body size then loses its meaning.
- Backstop: at every phrase edge the figure clock re-syncs to the bar grid. An
  unfinished figure is cut, and the next one starts on the bar.
- Limits stay as they are (`body::LIMITS`). They are assumptions and change only
  after a real servo is measured under load (step H). The v47 CSVs being refused is
  expected.
- v47 stays byte-identical.
- Form (user's answers, 2026-10-29): a new flag `ClockMode::V47 | Music`
  (`--clock v47|music`), default `V47`, orthogonal to `BodyMode`. `V47` is today's
  behaviour in both body modes: v47 Off is byte-identical and D3's Layered is
  unchanged. `Music` = the amplitude fit plus the phrase-edge re-sync, with the
  body.rs per-joint limits in both body modes. D3's slow-down loop is not used, so
  body Off + `Music` CSVs go through `check-csv` like Layered ones.
- **Pass:** lag ≤ half a beat at every phrase edge, on all 3 songs, for body Off +
  `Music` and for Layered + `Music`. Lag = figure clock position minus music time,
  at the phrase edge, after the re-sync. Also reported, not gated: the largest lag
  inside each phrase, before the re-sync; seconds cut per edge; hand-target arrival
  times of moments against their measured times. v47 and D3's Layered + `V47` are
  reported as references.
- Exports for the user's watch: per song, v47 Off, body Off + `Music`, Layered +
  `Music` (`core-2b` bodies after A2), with CSVs and `check-csv` verdicts.

*Order:* A1 → A2 and A3 → B → re-export the 3 songs → the user watches. Then D is
paused. Next is the brain (§6): the overseer writes the spec of B1 (pulse) and B2/B3
(oscillatory core, untrained then trained, 100 Hz two-rate input) with checks fixed
in advance, and gets the user's yes before any build. D4a, D4 and D5 resume after B3;
D5 then compares the brain against `core-2b` as the body's source. Stop at each step
with numbers.

## 3. Rules (all steps)

- `EMOTION.md` rules hold. Version 47 stays reachable and byte-identical: every
  new behaviour sits behind a mode whose `Off` reproduces the golden digests.
- Frozen `src/` and `tools/` read-only. Never drive hardware. Data, models,
  audio and videos outside git. Commit messages plain, no attribution lines.
- **Every pass/fail rule is committed before any result it scores.**
- Never say something improved or looks good. The user judges by eye.
- Each check: at most **two rounds** (build, then one adjustment limited to what
  the failing check names). Then stop and report with numbers.
- Stop at every ★ and wait for the user.
- One arm only. No ensemble, braking, melody-following, live audio, until stage 4
  passes.

---

## 4. Step D: the decoder, layered on version 47

### D1. The `mindState` interface (sidecar, additive)

One lane set per song, written by a script into the sidecar. It is the only
thing the decoder reads, so a later brain replaces its *source*, never its shape.

| Field | Rate | Range | v1 source |
|---|---|---|---|
| `source` | — | string | `"stage1-smooth8"` (Q1a); `"core-2b"` as candidate |
| `mood[k]` | 2 Hz | 0..1 per lane | stage-1 encoding, PCA to k (k chosen inside training folds), 8 s causal smoothing, per-lane fixed scaling stored in the field |
| `events[]` | — | time, kind, strength | look-ahead lifts/cuts from the audio (Q5a, D4) |
| `authored[]` | per section | per body dim, −1..1 bias | the user's hand: optional, empty by default; applied after the decoder, inside feasibility; logged in the export so it is never mistaken for the machine's own output |
| `bands`, `pulse`, `surprise`, `neuromod` | — | — | reserved, empty in v1 (the brain, §5) |

Scaling is fixed per source and stored, never per song, so sources are swappable.
Tests: schema, ranges, determinism, missing field = `Off` behaviour.

### D2. The decoder (Q2a), with a baseline (Q2c)

`EMOTION.md` stage 3, as written there:
- Segments from many songs (DEAM, Emotify, MERP audio, plus the user's three).
  Motions from the body generator (`body.rs`), measured with its 37 descriptors.
- The map: `mood` → 15-dim body vector, so that segments alike in mood move
  alike (representational similarity), smooth over time, inside feasibility.
- **Anchors (new, fixed before fitting).** Two directions of `mood` are tied to
  named body directions, so the map cannot come out flipped:
  1. *Energy*: the mood direction that best predicts the user's dial pass A
     (energy) must map to body energy, size and Laban time with a positive sign
     (perception anchor: speed and acceleration read as arousal; Pollick et al.
     2001, Saerbeck & Bartneck 2010).
  2. *Light/bright vs heavy/dark*: the mood direction that best predicts dial
     pass B must map to Laban weight (light → strong) and height (high → low)
     with the matching sign.
  Fit the directions on training folds only. The rest of the map is free.
  Report each anchor's sign and strength on held-out songs.
- Baseline: library lookup into the body study's 8 regions.
- Candidate: the same map fitted on `core-2b` (Q1b). Decides Q1 on the body.

**Check 3, committed before results**: on held-out songs, rank correlation of
the two distance matrices beats 99 % of 1,000 shuffles of the segment pairing,
and beats the map fitted to the 49-dim baseline encoding. Report library lookup
and `core-2b` beside it.

★ D2: after the check is committed; after results.

**Rule note (user, 2026-10-28, after D2-2, before anything is computed against the
new reference). This is a rule change after a failure.**
- *Round 1 stands as run* (`check3.py` at fd3fbfe, results ac08509): gate 1 PASS,
  gate 2 **FAIL** (decoder 0.624 against baseline49 0.781, difference −0.155
  [−0.173, −0.137]), gate 3 PASS. It is reported as a fail everywhere.
- *Why the gate changes.* The old gate 2 scores each map against its own encoding's
  distances, so it rewards preserving one's own structure (the 49-dim baseline is
  loudness and spectra, easy to carry into speed and size), not whether segments that
  people rated alike move alike.
- *New gate 2: one common yardstick.* Per held-out segment, the human ratings: DEAM
  and MERP valence-arousal (mean over the segment; segments without labels left
  out), and, as a separate score, Emotify's nine GEMS (the clip's profile).
  Distances between ratings (Euclidean) against distances between the segments'
  body descriptors (as round 1), Spearman per held-out fold, mean over folds. Every
  map is scored against it: decoder, baseline49, core-2b, library lookup. **Pass:**
  the decoder beats the baseline49 map on DEAM/MERP, the 95 % bootstrap interval
  (2,000 resamples over held-out songs) of the difference lying above 0. GEMS is
  reported, not gated.
- *Gate 1 rerun against the new reference:* the decoder's DEAM/MERP value beats 99 %
  of 1,000 within-fold shuffles of the pairing.
- *Gate 3* (energy sign on the user's 3 songs) is unchanged and rerun.
- *Fairness.* baseline49 and core-2b get the same two anchors (energy from DEAM +
  MERP arousal, power from Emotify), fitted the same way on the same folds. (Round 1
  already did this through the shared map class; round 2 keeps it and the handoff
  states it.)
- *Size: the one round-2 change, recorded as spec compliance.* §4 D2 says energy maps
  to body energy, size and Laban time with a positive sign; round 1's size loading was
  0.004 (fold 0). For every map, each anchored link must reach a held-out Pearson r of
  at least 0.5 between its lane and the body dimension (energy → energy, size, time;
  power → weight), enforced in fitting; the achieved r per link and map is reported.
  The 0.5 is the overseer's number, set before the run.
- The user's 3 songs (sixth set, no valence-arousal ratings) are reported against the
  user's own dial (pass A energy; pass B light, heavy as a 3-number rating), not gated.
- *Run once.* If the decoder fails the new gate 2: stop; the user decides the encoding
  (option 3). If baseline49 wins, it is a real candidate (simpler, no non-commercial
  model licences).
- Truth table (`ARCHITECTURE.md` §5) and `DANCE_HANDOFF.md`: both gate-2 results, the
  size fix and the anchor fairness, with numbers.

### D3. Layer onto version 47 (Q3a), per phrase (Q4b)

- New mode `BodyMode::Off | Layered`. `Off` = golden digests, byte-identical.
- The planner keeps timing, figures, formations, safety, collision check.
- The body vector sets **quality** only: size, energy, Laban time/weight/flow,
  succession, breath, height, initiation. The planner's figures must expose
  these knobs; list each one and how it maps.
- The body vector changes at phrase edges (16 beats) with a transition over the
  last beat; no per-beat changes in v1.
- **Joint limits**: the planner (240 °/s, 8,000 °/s²) and the body generator
  (per-joint, from cheap bus servos) disagree (`ARCHITECTURE.md` §3.3). In
  `Layered`, use the body generator's per-joint limits (they are the hardware
  assumption). `Off` keeps the old ones. Version 47's figures may not fit the
  slower limits: time-stretch them like the body study did and report how much
  each song needed.
- **Planner intensity vs body energy**: the planner's own intensity keeps its job
  (structure: how big this section is relative to the song). The body vector
  scales within it. Say which knob each one owns, so nothing is counted twice.
- Tests: golden for `Off`; feasibility for `Layered` on the three songs; jolts
  and spans scripts on the exports.

### D4. Anticipation, honestly (Q5a)

The system knows the whole song offline. Before each `events[]` lift, the body
prepares a fixed time ahead (stillness, gathered height, held breath; the exact
form from the body vector dims, no new moves). After it, **afterglow**: the body
vector releases back towards the phrase's value slowly (a decay of a few
seconds, length fixed before results), not at once. Events act at their own
time, not at phrase edges. Truth table: "it knows the score", never "it learned"
or "it predicts". Mode flag, `Off` default.

### D5. Stage 4: does the user read it (Q6)

`EMOTION.md` stage 4 as written: silent odd-one-out (pass ≥16/24), match or
mismatch with audio (pass ≥10/12), whole-song "feels right" dial with taps (not
pass/fail; locates problems). Pages save answers to JSON; the key stays hidden
until all answers are in. Pass rules already fixed in `EMOTION.md`; the overseer
commits the triplet and pair lists before the user sees any clip.

★ D5: pages ready; after the user's answers; after scoring.

### If D fails

Round 2 once, limited to what the failing check names. Fails again: stop, report,
the user decides (encoding, decoder type, or body range).

---

## 5. Step H: one real arm (the user, not the builder)

The previz has never met real servos (jitter, noise, backlash, latency). An arm
that does not read in a room makes everything upstream moot.

- Builder's part only: an export of one arm's joint angles per song (CSV, 50 Hz,
  degrees, audio-time stamps) plus a checker that refuses any file breaking the
  `Layered` limits. Nothing is sent to hardware by any agent.
- The user builds or buys one arm and plays version 47 and `Layered` exports on
  it. Verdict by eye, written into `DANCE_HANDOFF.md` by the overseer.
- H can run alongside the brain work; installation-readiness needs it.

---

## 6. The brain (B1–B6): parked roadmap

**Parked until D5 passes and the user says go.** Nothing below is built now.
When unparked, the overseer turns each phase into a spec with checks fixed in
advance, two rounds max. Recorded here so the design is not lost.

### Why the current core cannot be a brain

`mind.py` uses leaky units: real, negative eigenvalues. They only decay, so the
whole network is a bank of low-pass filters. That is why long τ acts as smoothing
(lesson 5), and why it can never show waves. It was not a tuning failure.

### Design

- **Rate 100 Hz, two-rate input.** Fast: 32–64 cheap features at 100 Hz (onset
  strength, spectral flux, band energies). Slow: the stage-1 ear, held between
  its 0.5 s steps. Audio-rate steps (44.1 kHz) are wrong: the ear does the
  cochlea's job; cortex rhythms are 0.5–100 Hz.
- **Oscillatory recurrence.** Complex-valued diagonal linear recurrence (LRU
  family, Orvieto et al., ICML 2023): each mode decays *and* rotates at its own
  frequency. Modes initialised in bands:

  | Band | Hz | Role |
  |---|---|---|
  | section / phrase | 0.01–0.5 | position in song, tension build |
  | beat / meter | 0.5–4 | pulse, bar |
  | theta-like | 4–8 | grouping inside the beat |
  | fast | 8–40 | texture, onset detail (monitor + coupling only; servos cannot show it) |

- **Pulse layer**: Hopf oscillator bank (Large's GrFNN) entraining to beat and
  meter, keeping pulse through breaks. Neural anchor: steady-state EEG response
  at beat and imagined-meter frequency (Nozaradan 2010/2011).
- **Cross-frequency coupling**: slow-band phase gates fast-band amplitude
  (theta-gamma code analogue, Lisman & Jensen 2013).
- **The user's B framework mapped**: levels τ₁≪…≪τₙ = band groups, each
  predicting the level below; precision π = gain on each level's prediction
  error; emotion as field-state = a few slow **neuromodulator** lanes (global
  gain, τ scale, arousal) driven by prediction-error statistics, written to
  `mindState.neuromod` and read by the decoder; ignition = an event when
  cross-band coherence crosses a threshold, shown as a startle/reorientation.
  Truth table: "coherence crossing", never "conscious".
- **Two streams** (Huron, *Sweet Anticipation*): veridical = D4's look-ahead
  ("knows the score"); schematic = the causal brain, which can still be
  surprised. Showing both is the point: it knows what is coming and still
  flinches.

### Phases and their checks (outline)

- **B1 pulse**: locks to beat on held-out songs (tempo and phase error), holds
  through breaks, meter peak present. First band trace for the monitor.
- **B2 untrained oscillatory core**: the ablation for B3, not a goal.
- **B3 trained predictive core**: next-step prediction of the fast+slow features,
  self-supervised, on an open Creative Commons corpus (licence of every file
  recorded; non-commercial excluded if it blocks exhibition). Checks: beats
  persistence, linear and B2 baselines on held-out songs; surprise drops on
  repeats (habituation); surprise peaks at novelty. **Body check: no loss against
  a smoothing control with the same frequency response** (otherwise lesson 5
  repeats), judged in stage 4 form.
- **B4 dreaming**: free-run with no input between songs; the arm moves faintly.
  Check: beat-band peak in the free-run spectrum; stays inside limits.
- **B5 monitor**: СИНТЕЗА shows the real band powers, pulse and surprise as a
  clinical trace (near-black, fine line; no REC indicators, no chrome).
- **B6 staging**: arm plus dim projection in one dark room, user verdict.

### Compute

The user's machine: no discrete GPU, 32 GB RAM, i7 13th gen, 24 threads. The
company machine is not used. Keep the core small (1–5 M parameters); target
overnight training runs. First measurement when unparked: time to extract the
fast and slow features over the corpus (the likely bottleneck). Report it before
committing to a corpus size.

---

## 7. Handoff

Each step appends a dated entry to `docs/DANCE_HANDOFF.md` (built, constants and
origins, check numbers with intervals, not done, "not verified by eye"), updates
`ARCHITECTURE.md` (pipeline picture, truth table, Q1–Q8 status) and the restart
prompt's "Where we are". Commit and push to `keys-decide`.
