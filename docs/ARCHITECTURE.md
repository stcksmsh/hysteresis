# Architecture: from a song's feeling to an arm's body

Status: record, 2026-10-28. Branch `keys-decide` at `10b8a66`. Written by the overseer
from the handoff entries, the rules documents, the code, and the overseer's own
recomputation of the step-2 results. This file says what exists, what was measured,
and what is still open. It does not change any rule. Where it and a rules document
differ, the rules document wins (`docs/NEXT_BODY_THEN_MIND.md`, `docs/EMOTION.md`).

Scope: the feeling-to-body pipeline. The ensemble, the visualizer, live audio and the
hardware get one short section each (§7).

---

## 1. Purpose

The piece: servo arms that dance to a song, lit by a projector showing the visualizer.
Anyone can make an arm that moves to the beat. What makes it art is that the arm's whole
body conveys the song's feeling. The work also tells a story about *how*: a machine that
runs real, checkable mechanisms (hearing, remembering, expecting) and is still not
verifiably anyone (`docs/MIND.md` §1). So every capacity the piece is described as
having must be a real mechanism with a passed check.

Two rules hold throughout (`docs/EMOTION.md`):
- No stage assigns emotional meaning by hand ("sad = low"). Meaning comes from labelled
  data and from the user's judgements.
- Every pass/fail rule is committed before any result it scores.

**Decided.** The rig (5 servos, continuous base yaw, a mirror implement). Offline
analysis only, no live audio. The single-arm dance and the six-arm ensemble of version 47.
The body can move in ways a person tells apart (step 1 passed).

**Open.** Which encoding of the song's feeling drives the body (§6 Q1). How the feeling
becomes body parameters (the decoder, stage 3, not built). How the body parameters
combine with the version-47 planner. Whether any of it reads as the song's feeling to a
person (stage 4, not built).

---

## 2. The pipeline in one picture

```
 song audio
    │
    ▼
 [A] offline analysis chain ──────────── sidecar JSON ─────────────┐   built
    │  (beats, phrases, stems, structure, note lanes)               │
    ▼                                                               │
 [B] emotion encoder, stage 1 ── emotionEncoding (2,665 / 0.5 s)    │   built, not wired
    │                                                               │
    ▼                                                               │
 [C] mind core (reservoir) ───── mindState (never written yet)      │   experimental
    │                                                               │
    ▼                                                               │
 [D] decoder, stage 3 ────────── body parameters over time          │   NOT BUILT
    │                                                               │
    ▼                                                               ▼
 [E] body generator (body.rs)            [F] version-47 planner (figures.rs)  built
     8 s study clips, no music               whole songs, 1–6 arms
    │                                        │
    └──────────────► EnsembleScore ◄─────────┘
                          │
                          ▼
            [G] previz HTML / video recorder                      built
                          │
                          ▼
            [H] servos (later, nothing driven)                    not built
```

**Links that exist in code today:** A → F (the planner reads the sidecar), E → G and
F → G (both make an `EnsembleScore`). **No link from B, C or E into F.** A search of
`crates/` finds no `emotionEncoding` or `mindState`; `body::` is used only by the body
study example. The body generator and the planner share only types (`EnsembleScore`,
`Rig`, `IntentCue`).

---

## 3. The parts as built

### 3.1 [A] Offline analysis chain (one song → sidecar)

Driver: `song.sh SOURCE SLUG` in `$D/tracker-scratch/newsong/` (outside git;
`D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm`).
`song2.sh` re-runs the tail for songs with a drifting tempo (tempo map); `three.sh TAG`
exports the three danced songs.

| Step | Script | Adds to the sidecar | Method, one line |
|---|---|---|---|
| 1 | `scripts/analyze.py` (+ `scripts/analyze/`) | base sidecar, schema 3: envelopes, bands, beats, sections, events, onsets | Python port of the old `analyze.ts`; equal to it on 15 inputs within 6.7e-15 |
| 2 | `scripts/dance_memory.py` | `musicalMemory`: beat grid fit, 16-beat phrases, `repeatOf` | grid refit and phrase similarity |
| 3 | Demucs `htdemucs` and `htdemucs_6s` | (stems on disk) | `--shifts 0` since 2026-10-24: runs agree within 6e-7 |
| 4 | `scripts/dance_stems.py` | `stemInterpretation`: RMS, activity, flux, transients per stem | 4 stems |
| 5 | `scripts/dance_structure.py` | `musicalStructure`: novelty at 4/8/16/32 beats, repeats (similarity ≥ 0.72) | no labels such as "chorus" |
| 6 | `scripts/dance_notes.py` | `noteTrack.lanes`: onsets, rough pitch, phrases, level and brightness per beat | 6 stems |
| 7 | `scripts/emotion/encode.py` | `emotionEncoding` (§3.5) | separate run, three songs only |

Known limits: the beat tracker lags (Presence needed a 45 ms refit); Five Years needs a
tempo map. Both fixes are scratch scripts outside the repo. `dance_melody.py` and
`melodyContour` were deleted (`3212b9c`). The three danced songs' stems were made before
`--shifts 0`; they are kept as they are so version 47 stays byte-identical.

### 3.2 [F] The version-47 planner

Entry: `hyst_compile::director::figures::compile_ensemble` (`compile_figures` is the
one-arm case), via `compile_ensemble_with_workspace`. Input struct: `Evidence` in
`director.rs`. Steps:
1. Reads `duration`, `rmsEnvelope`, `musicalMemory`, `stemInterpretation`,
   `musicalStructure`, and `noteTrack.lanes` if present.
2. Intensity: loudness against the song's 90th percentile.
3. Spans at transitions (≥ 8 beats apart) and phrase edges; each span gets a class:
   interlocked, bass-led, melody-led, vocal-led, percussive-open, kick-led, textural,
   silence, other. Classes are named by measured stem share, not by feeling.
4. Leader lane from the note lanes (takes over after leading by 3 dB for 4 beats);
   stabs, swell (loudness and brightness), voice height.
5. Figures per class (`motif`): gather, rise, open, arc, circle, sway, reach, eight,
   still; runs mirror and alternate turning direction per section.
6. Hand path low-passed (σ 0.3 s); moments: arrivals, flourishes, cuts.
7. Formation per run: Unison, Mirrored, Canon, Ripple; runs under 24 beats keep the
   previous one.
8. Figure clock: holds, hand speed cap 0.8 m/s, catch-up at 15 %, pulses on stabs.
9. Solver: damped least squares; red zones (`Zone`) and floor with 5 cm margin; other
   arms as moving obstacles, earlier arms have right of way.

Output: `EnsembleScore { duration, rig, placements, cues, tracks, workspace }`.
`CompileConfig.workspace` defaults to `Off` (B workspace, parked; §4.2).
Guarantee: `golden_digests_of_compile_ensemble` hashes 4 cases; the three songs'
exports must stay byte-identical to `hexagon-47.html`, `five-years-hexagon.html`,
`presence-hexagon.html` (checked by `three.sh` + `cmp`).

What the planner expresses today: *where* the hand goes (figures), *when* (beats,
phrases, moments), *how big and fast* (intensity, swell), and *together or apart*
(formation). It has no notion of the song's feeling beyond loudness, brightness and who
leads.

### 3.3 The rig and the limits

`ensemble.rs`, `Rig::illustrative_five_axis()`: base yaw (continuous, confirmed by the
user), shoulder, elbow, wrist bend, wrist roll. The implement is data
(`Rig.implement`): a mirror disc held by its edge, or a lumpy mirror ball. Links and
limits are invented, not measured on hardware.

The two motion makers use different limits today:

| Limit | Planner rig | Body generator |
|---|---|---|
| joint speed | 240 °/s all joints | base 120, shoulder 90, elbow 150, wrist 200, roll 250 °/s |
| joint acceleration | 8,000 °/s² | 600 / 300 / 1,000 / 2,000 / 3,000 °/s² |
| hand speed | 0.8 m/s (figure clock) | 1.2 m/s |
| jolt mark | 9 m/s² | 9 m/s² |
| floor | 5 cm margin | 5 cm + 6 cm disc |

The body generator's per-joint limits came from the body-study addenda (cheap bus servos,
a light printed arm). Unifying the two is part of §6 Q3.

### 3.4 [E] The body generator (step 1, round 2)

`crates/hyst-compile/src/body.rs`. Input: a body vector of 15 values (0..1) and a seed.
Output: an 8 s one-arm `EnsembleScore` (knots every 0.05 s). Motion is made in joint
space, not by hand target plus IK.

| Dimension | What it changes |
|---|---|
| energy | duration of each leader move, 5.0 s down to 0.7 s |
| size | travel per move, 6 %–100 % of each joint's amplitude |
| rhythm | moves per leader move for elbow (1–2), wrist and roll (1–3) |
| height | shoulder elevation centre, 10–95° |
| curl_extension | elbow centre |
| arch | wrist bend against elbow |
| time (Laban) | acceleration ramp 50 %–12 %, overlap 0.3–0.12 |
| weight (Laban) | share of the move spent decelerating (firm stop against float) |
| flow (Laban) | overshoot up to 25 % on elbow, wrist, roll, then settle |
| space (Laban) | base bows up to 15°, roll up to 30° on the way |
| initiation | which joint leads: base, shoulder, elbow, wrist |
| succession direction, delay | base-to-tip or tip-to-base; 0.12–0.42 s |
| breath depth, rate | shoulder up to 8°, elbow up to 12°; 0.08–0.3 Hz |

The seed sets only start phase and small jitter (±8 % gaps, ±10 % targets). Feasibility:
limits above at 1 kHz, the rig's own checks, a stillness cap (fail if all joints are under
2 °/s for over 2 s, or over 25 % of the clip), in frame. A failing clip is slowed on a
ladder up to 1.95×, else rejected. `descriptors` gives 37 motion measures.
`body_regions.rs` picks regions. CLI: `body_study` example (`sweep`, `regions`,
`ladder`, `html`).

What the body generator does not do: music. It makes a phrase of moves with a quality,
not a dance to a song. It has no beat, no phrase timing, no figures, no ensemble.

### 3.5 [B] The emotion encoder (stage 1)

`scripts/emotion/` (`extract.py`, `features.py`, `encode.py`, `check1.py`, `report.py`);
details in `docs/EMOTION_ARCH.md`. One vector per 0.5 s, each from a 4 s window:

| Component | Dims |
|---|---|
| baseline (sidecar-style mix features + 4 Demucs stems) | 49 |
| MERT-v1-95M, mean of 13 layers | 768 |
| CLAP (music checkpoint) | 512 |
| Essentia Discogs-EffNet embedding | 1,280 |
| Essentia mood/theme head | 56 |
| **total ("baseline+all", the pick)** | **2,665** |

Nothing is learned in it; only check readouts are fitted. Written to sidecars as
`emotionEncoding` (`steps`, `perBeat`) for the three songs (62–77 MB each, outside git).
The planner reads nothing from it.

### 3.6 [C] The mind core

`scripts/emotion/mind.py`, with `smoothing.py`. Design in `docs/MIND.md` §3 (most of it
parked).
- Ear: the 2,665 vector, PCA to 64 on training folds.
- Core: 512 leaky units at 0.5 s; time constants log-uniform 0.5–60 s; 10 % sparse
  random recurrence; spectral radius chosen inside training folds (grid 0.7–0.99);
  seeded, nothing trained.
- Rehearsal (round 1 only): pass 1 stores states; pass 2 also receives the stored state
  at +1, +4, +16 bars, scaled by ρ. Round 1 showed it hurts (§4.6).
- `run_plain` (step 2b): one pass, no rehearsal input.
- Readouts: ridge from state PCA 64 (round 1) or state + ear (2b) to valence/arousal
  (DEAM, MERP) and nine GEMS feelings (Emotify).
- Smoother (2b): causal exponential, τ 0–32 s, delay 0–4 s, chosen inside training folds.

`mind_state_field()` exists but nothing writes `mindState` to a sidecar. Not built:
pulse oscillators (§3.2), audio surprise (`audioic`, §3.3), the core's own prediction
error, a trained core.

### 3.7 Data and labels

| Data | What | Used for | Licence |
|---|---|---|---|
| DEAM 2013/14 | 1,744 clips of 45 s, valence/arousal at 2 Hz | timing (between clips mostly: only ~2.5 % of label variance is inside a clip) | BY-NC |
| Emotify | 400 one-minute clips, nine GEMS feelings | feeling profiles | none stated; cite |
| MERP | 43 songs over 50 s (of 54), valence/arousal | within-song timing | annotations CC BY 4.0; audio per-track CC, licences unknown |
| User's dial | 3 songs: pass A energy (0..1), pass B light/bright and heavy/dark | the user's own feeling; the decision gate | the user's |

MERP labels: the authors' 3,482 kept trials, each taken from its raw 10 Hz series (the
filtered file is the raw series smoothed by Savitzky-Golay 15/2, every 5th sample, cut
12–17 s at the start). The user's dial: `/secondary/hyst-data/emotion/dial/dial2.json`
(5 takes, 10 Hz, no gaps) plus Instant Crush's first take on the old pad (arousal axis,
masked 135–171 s and after 329 s); no Space-bar taps were recorded. Backup in
`~/hyst-backup/emotion-dial/`.

Models: MERT (CC BY-NC 4.0), CLAP (Apache 2.0), Essentia (CC BY-NC-SA 4.0). Most data
and models are non-commercial: fine for research, to be checked before exhibition.

---

## 4. Experiments and results

All numbers are on held-out songs (5 folds by song) unless marked; intervals are 95 %
bootstrap over songs.

### 4.1 Versions 1–47 of the dance (2026-09-23 to 2026-10-06)

Hand-written mappings from sidecar signals to motion, refined by the user's eye over
47 versions (details in `AGENTS.md` §5). Accepted: the single arm at version 32, the
ensemble at version 39, Instant Crush at version 44 ("Its nice now"). Version 47 answers
a list of jerks and weak spots on three songs and has **no verdict yet**. Lesson
recorded in `EMOTION.md`: hand-written mappings cap the result at the author's
vocabulary.

### 4.2 B workspace (2026-10-12, parked)

Expectation signals (surprise, tension, gain) shaping the planner. Round 1 lost a blind
test (1 of 4); round 2 the user could not tell `Off`, `Rehearsed`, `Schematic` apart.
Measured causes: the hand shell caps elevation at 79°, so every "rise" saturates
(Presence: pinned 8–10 % of the time); a held breath reads as low energy, not suspense.
Code stays, `Off` is the default.

### 4.3 Stage 1, check 1: does an encoding hold emotion? (2026-10-12)

| Candidate | Timing R² (DEAM) | Emotify rank ρ | NN agreement |
|---|---|---|---|
| baseline (49) | 0.449 [0.423, 0.473] | 0.524 | 0.215 |
| baseline+all (2,665), pick | 0.617 [0.596, 0.635] | 0.616 [0.588, 0.643] | 0.318 |

Only baseline+all passed all three gates. **Within-song R² is negative for every
candidate** (pick −0.96): the encoding separates songs, it does not follow change inside
one. User's reading of the report: Presence 2:00–3:15 sad, right; Five Years opening read
as the most aroused moment (0.61 against 0.41–0.45 at the climax), wrong.

### 4.4 Step 1, the body study (2026-10-13/14)

Silent odd-one-out: two clips from one region of body space, one from another; the user
picks the odd one.
- **Round 1: 13 of 24, fail** (pass 16). Causes: the seed decided about half of what the
  clips showed; movement floors forced every body to dance at a level (mean joint speed
  24–45 °/s), damping size and energy.
- **Round 2: 30 of 32, pass** (pass 20; P ≈ 1e-12 under guessing). 15 dimensions; the body
  decides pattern, pace, size and rhythm; floors removed. 16/16 in the first half (not
  learning); 16/16 on triplets with close speeds (not speed alone). The user's words for
  regions: "locked groove with holds", "figure eights / fluid", "slow, hanging,
  drooping", "almost straight up and slow", "wild and unstructured".

### 4.5 The user's dial (2026-10-14 to 10-23)

Format 1 (valence/arousal pad): "pleasant/unpleasant" was meaningless to the user, and
songs hold two feelings at once. Format 2: pass A energy slider, pass B two one-sided
axes. All six song/pass pairs exist.

### 4.6 Step 2, round 1: reservoir with rehearsal (`check1b.py`, 2026-10-24)

| Gate | Result | Numbers |
|---|---|---|
| 1 within-song arousal r | FAIL | DEAM core 0.204 [0.182, 0.226] vs reference 0.101 [0.081, 0.120] pass; MERP 0.471 [0.380, 0.554] vs 0.316 [0.236, 0.397], overlap by 0.017 |
| 2 mood kept | FAIL | timing R² 0.559 vs bound 0.596; Emotify 0.582 vs 0.588 |
| 3 memory used | PASS | shuffle: DEAM 0.204 → 0.026, MERP 0.471 → 0.066 |
| 4 rehearsal | FAIL | MERP: 0 lifts (rule threshold too steep for averaged curves); songs: 6 lifts, p = 0.48 |
| 5 the user | PASS | dial r core vs reference: IC 0.177/0.111, FY 0.817/0.869, PR 0.767/0.620 |

Rehearsal hurt: without it (ρ = 0) DEAM 0.221, MERP 0.566.

### 4.7 Step 2b: no rehearsal, readouts on state + ear, a smoothing control (`check2b.py`)

| Gate | Result | Numbers |
|---|---|---|
| A1 core vs smoothed reference | PASS | DEAM 0.277 [0.251, 0.303] vs 0.150 [0.124, 0.177]; MERP 0.626 [0.556, 0.690] vs 0.428 [0.330, 0.519] |
| A2 mood kept | FAIL | timing R² 0.588 vs 0.596 (by 0.008); Emotify 0.607 vs 0.588 pass |
| A3 memory used | PASS | DEAM 0.200 → 0.018, MERP 0.533 → 0.255 |
| B user's energy dial | FAIL, 0 of 3 | smoothed core vs smoothed reference: IC 0.252/0.389, FY 0.887/0.922, PR 0.628/0.664 |

Both sides chose 8 s smoothing, no delay. Unsmoothed, the core leads on Five Years
(0.896 vs 0.869) and Presence (0.720 vs 0.620). Valence (reported): DEAM 0.197 vs 0.073,
MERP 0.407 vs 0.207. Every gate recomputed by the overseer from the saved predictions.
Step 2b was designed after round 1; its fold gates are diagnostics, gate B the decision.
**Outcome: A1 passes, B fails; the user decides** (open).

### 4.8 Infrastructure checks (2026-10-23/24)

- Python analyzer = TypeScript analyzer on 15 inputs (max difference 6.7e-15).
- Demucs default `shifts=1` made stems vary run to run (vocal presence up to 0.91 apart);
  `--shifts 0` gives agreement within 6e-7.

### 4.9 Lessons

1. A probe on a filtered sample gave a wrong spread and sank a rule (body addendum 4):
   check a sample is unbiased before writing a rule on it.
2. Gates on distribution shapes force shapes on the space; gate only what the test needs.
3. Movement floors flattened the body: the body must decide size and energy.
4. An untrained network cannot use a future-state input; feeding it one adds noise.
5. Long time constants partly act as smoothing: always run a smoothing control.
6. A design chosen after seeing results must be judged on data not yet seen.
7. A green test suite says nothing about how a motion or an image looks.

---

## 5. What the evidence licenses (truth table)

| Claim | Licensed? | Evidence |
|---|---|---|
| The arm can move in ways a person tells apart | yes | body study round 2, 30/32 |
| The encoding holds a clip's overall mood | yes | check 1, R² 0.617, ρ 0.616 |
| The encoding follows change inside a song | no (stage 1) | within-song R² negative |
| A memory core follows change inside a song better than smoothing, on public data | yes | 2b A1, both datasets |
| ... and on the user's own energy, for their songs | no | 2b B, 0/3 |
| The machine has rehearsed and anticipates | no | round 1 gate 4; rehearsal hurt |
| It is surprised / keeps a pulse | untested | not built |
| The dance conveys the song's feeling | untested | decoder and stage 4 not built |

---

## 6. Open architecture questions

Each has options and the overseer's recommendation. None is decided until the user says
so and it is written into a rules document.

**Q1. Which encoding drives the body?**
- a) Stage 1 + 8 s smoothing. Simplest; at least as close to the user's energy dial.
- b) The memory core (2b). Stronger on 1,787 public clips and songs; drops the dial gate.
- c) Record 2–3 more songs on pass A, then decide.
- *Recommendation:* a) as the primary, with b) kept as a second candidate inside stage 3's
  own check, so the memory question is decided on the body. The memory claim stays
  unused until then.

**Q2. What is the decoder (stage 3)?**
- a) Representational-similarity map (`EMOTION.md` stage 3): learn a map from encoding to
  body vector so that segments that feel alike move alike; checked by rank correlation of
  the two distance matrices against shuffles.
- b) Direct regression from encoding to body dimensions, trained on the user's
  judgements of clips.
- c) Library lookup: the body study's 8 regions as a vocabulary, each song segment
  assigned to the region whose labelled clips feel closest.
- *Recommendation:* a), because it needs no hand-assigned meaning and has a pre-set
  check; c) as its baseline. b) needs many judgements the user has not made.

**Q3. How do body parameters meet the version-47 planner?**
- a) Layered: the planner keeps timing, figures, formations and safety; the body vector
  sets quality (size, energy, time/weight/flow, succession, breath, height) on top.
- b) Replace: the body generator becomes the dance, with beats and phrases added to it.
- c) Switch: the planner for structure, the body generator for chosen passages.
- *Recommendation:* a). Version 47 holds 47 rounds of the user's corrections on timing
  and safety; the body study proved quality dimensions are visible. Needs: unified joint
  limits (§3.3), and the planner's figures exposing the quality knobs the body generator
  has.

**Q4. At what timescale do body parameters change?**
- a) Per beat (follows the 0.5 s encoding, smoothed).
- b) Per phrase (16 beats), with transitions at phrase edges.
- c) Two layers: a slow per-section mood plus per-phrase variation.
- *Recommendation:* b) to start: phrases already structure the planner, and an 8 s
  smoothing time already fits the user's dial; c) once b) works.

**Q5. Anticipation, done honestly.**
- a) Explicit look-ahead: the system knows the whole song offline, so the body prepares a
  fixed time before lifts found in the audio. Described as "it knows the score".
- b) None for now.
- *Recommendation:* a), small, after Q3; never described as learned.

**Q6. How does the user judge stage 4?**
- `EMOTION.md` stage 4: silent odd-one-out from different song passages; match/mismatch
  with audio; the whole-song "feels right" dial while watching. *Recommendation:* keep;
  fix the pass rules before stage 3's results exist.

**Q7. More within-song labels?**
- a) The user's dial on more songs (5 min each for pass A).
- b) Another public whole-song set.
- *Recommendation:* a) only if a decision depends on it (e.g. Q1 c); public sets are
  scarce and MERP is the only one found.

**Q8. Licences before exhibition.** MERT, Essentia, DEAM, and some MERP audio are
non-commercial. Before any show or sale each is checked, replaced or dropped. Not urgent
for research.

---

## 7. Out of this document's depth

- **Ensemble.** Six arms on a 0.8 m hexagon facing the centre; formations Unison,
  Mirrored, Canon, Ripple; cross-check of links and implements with right of way. Open:
  overlap in the mirrored formation; red zones as a general tool against equipment.
  Waits for the emotion work (out of scope until stage 4 passes).
- **Visualizer.** `hyst-render` (Julia with perturbation deep zoom, memory field, bloom,
  Lissajous beam, Mandelbulb), last changed in September. The plan links it to the
  encoding later; out of scope now.
- **Live audio.** Decided out: the dance works from offline sidecars only. `hyst-audio`
  exists for live analysis but is not in this pipeline.
- **Hardware.** Cheap bus servos, a light printed arm, a mirror disc. Nothing built or
  driven. Limits in §3.3 are assumptions.

---

## 8. Where things live

| What | Where |
|---|---|
| Current work order | `docs/NEXT_DECODER_THEN_BRAIN.md` (from 2026-10-28) |
| Rules | `docs/NEXT_BODY_THEN_MIND.md` (closed; dated notes kept), `docs/EMOTION.md`, `docs/MIND.md`, `docs/BODY_STUDY.md` |
| History and numbers | `docs/DANCE_HANDOFF.md` (newest last), `AGENTS.md` §5 |
| How to run and review | `docs/DANCE_RESTART_PROMPT.md`, `docs/OVERSEER_HANDOFF.md` |
| Planner, body, rig | `crates/hyst-compile/src/director/`, `body.rs`, `body_regions.rs`, `ensemble.rs` |
| Previews | `crates/hyst-previz/examples/ensemble_preview.rs`, `body_study.rs` |
| Analysis chain | `scripts/analyze.py`, `scripts/dance_*.py` |
| Emotion and mind | `scripts/emotion/` (tests: `python -m unittest` there) |
| Data | `/secondary/hyst-data/emotion/` (DEAM, Emotify, MERP, dial, check1b, check2b), `/secondary/hyst-data/bodystudy/` |
| Environments | `/secondary/hyst-env/` (`emotion`, `analyze-py`, `demucs`) |
| Audio, sidecars, exports, recorder | `$D` (outside git) |

Read order for a new agent: this file, then the rules documents, then the last
`DANCE_HANDOFF.md` entries.
