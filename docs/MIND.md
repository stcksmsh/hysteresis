# MIND: the recurrent core between the ear and the body (design, not built)

Status: design, **parked**, 2026-10-13. Nothing here is built. Branch
`keys-decide`. The current work order is `docs/NEXT_BODY_THEN_MIND.md`: its step 2
builds only §3.4–3.6 with the reservoir core. The rest of this file waits for that
step's verdict and for the body study.
Extends `docs/EMOTION.md`: adds **stage 1b** between stage 1 (the encoder, A)
and stages 2–3 (the body and the decoder, C). Stage 1's pick is unchanged.
`director/workspace.rs` (B v1, hand-built fields) stays parked and is not the
basis of this work.

---

## 1. Why this exists

### The story is part of the work

The piece is not "an arm that moves well to music". It is a machine running a
**simulated mind**: it hears a pulse, expects, is surprised, remembers what it
has heard, has rehearsed the song, and carries a mood that builds and fades. A
viewer who learns *how* it works should feel two things at once: wonder, and
unease. It is not faking feeling with a lookup table. It runs the same *kind*
of machinery a person does, and still nobody is verifiably home. That is the
through line of the user's work.

Two requirements follow, and they bind every choice below:

1. **Truth.** Every capacity the piece is described as having must be a real
   mechanism, measured by a check. "It is surprised" means a measured
   prediction error inside it, not a label. Someone who knows the field and
   looks under the hood must find the claim holds. Section 9 lists the claims
   and what licenses each one.
2. **Brain-analogue first.** Where two mechanisms both pass a check, take the
   one with a defensible analogue in how brains handle music, and cite it. A
   black box is allowed only if the analogue fails its check, and the handoff
   says so.

### The engineering reason

Stage 1's encoding holds a clip's **overall** mood (pooled timing R² 0.617
against the baseline's 0.449). But its within-song R² is **negative for every
candidate** (pick −0.96). It does not follow change inside a song. Every 4 s
window is judged with no past: "swapping two windows in time would change
nothing" (`docs/EMOTION_ARCH.md`). The user's reading of the report shows the
symptom: "Five Years" reads its lone-drum opening as the most aroused moment
(0.61 against 0.41–0.45 at the climax).

Musical feeling is made in time. A drop is a payoff because of the build before
it. A chorus moves you because it returns. An opening is a beginning
(expectation theory: Meyer; Huron, *Sweet Anticipation*). A memoryless window
cannot carry that. A recurrent core can.

### What it is not

- Not one step per audio sample. The ear splits sound into frequency bands
  before cortex sees it, and cortex works on envelopes at tens of Hz at most.
  44,100 steps per second would also be untrainable (13 million steps per
  song, no target at that rate). Each level runs at its own rate (section 3).
- Not five named fields. Feeling lives in an unnamed state; named values are
  readouts of it, used for checking and display, never as the state.
- Not a hand-written mapping from feeling to motion (`EMOTION.md` rule).

---

## 2. Principles

- **Two streams, as a rehearsed listener has.** *Schematic*: what this song
  has done so far, causal, able to be surprised. *Veridical*: memory of having
  heard this song before, weighted by precision ρ. The default dancer is
  rehearsed (ρ = 1) and deterministic.
- **Causal core.** The core reads beat *n*'s inputs only at step *n*. The only
  route to the future is the rehearsal memory (section 3.5), which is itself a
  record of an earlier causal pass. This keeps a live mode possible later.
- **Seeded and deterministic.** Same song, same seed, same output, byte for byte.
- **Checks fixed before results** (section 7), the same discipline as
  `check1.py`: folds by song, fixed seeds, 95 % bootstrap over songs.
- **Bounded.** At most two rounds (section 8). Failure stops the stage and is
  reported. The dance is untouched until the checks pass.

---

## 3. The anatomy

| Part | Brain analogue | Rate | What it is | Trained? |
|---|---|---|---|---|
| 3.1 Ear | cochlea and auditory cortex | 75 Hz to 2 Hz | stage 1's encoder, unchanged, plus a 100 Hz onset envelope | no (frozen models) |
| 3.2 Pulse | neural entrainment to rhythm | 100 Hz | a bank of nonlinear oscillators driven by onsets | no (physics) |
| 3.3 Surprise | prediction error | about 11 Hz | an audio surprisal model (information content) | pretrained |
| 3.4 Workspace | hierarchy of temporal receptive windows in cortex | 2 Hz | a recurrent core with time constants from 0.5 s to 60 s | no (seeded), or small if 8 needs it |
| 3.5 Rehearsal | episodic memory of the song | per step | the core's own trajectory from an earlier pass, fed back as expectation | no |
| 3.6 Readouts | (instruments, not organs) | 2 Hz | linear maps from state to valence/arousal and the nine GEMS feelings | ridge, on labelled data |

### 3.1 Ear (exists)

Stage 1's pick, `baseline+all`: 2,665 numbers every 0.5 s. The core reads a
**PCA reduction to 64 dimensions**, fitted on the training folds only (the full
vectors stay in the sidecar). New: an **onset envelope at 100 Hz** from the mix
and the drum stem (spectral flux, half-wave rectified, normalised per song), the
pulse layer's input.

### 3.2 Pulse: oscillators that entrain

Edward Large's neural resonance model: a bank of nonlinear oscillators (the
canonical form near a Hopf bifurcation), log-spaced in frequency, driven by the
onset envelope. They phase-lock to the beat and to its multiples and divisions.
- Large, Almonte, Velasco 2010 (*Physica D*) defines the canonical oscillator
  and simulates 360 of them over 6 octaves, 60 per octave.
- Large, Herrera, Velasco 2015 (*Frontiers in Systems Neuroscience*) predicted
  that listeners would hear a pulse at a frequency with **no energy** in the
  audio (the "missing pulse"), and listeners confirmed it.
- Near or above criticality an oscillator keeps oscillating without input, so the
  pulse can be **held through a break** (Kim & Large 2015 on autonomous
  behaviour). The regime is a parameter; choose it by check 7.3.

Start: 0.125–8 Hz (6 octaves), 30 per octave (180 oscillators), integrated at
100 Hz. Outputs to the core, per step: amplitude per octave band (6), the
strongest oscillator's frequency, its phase as sin and cos, and the summed
amplitude (pulse strength). Also exposed for the body later: **expected time of
the next onset**, which is anticipation from physics, not from a rule.

The beat tracker and the sidecar's beat grid stay as they are. The oscillators
are a second, brain-like account of the pulse, checked against the grid.

### 3.3 Surprise: information content from audio

An autoregressive model predicts the next frame of compressed audio. Its
negative log-likelihood per frame is the **information content (IC)**: how
surprising the next moment is, given everything heard so far in the song.
- `audioic` (Sony CSL / JKU; Bjare, Cantisani, Lattner, Widmer, ICASSP 2025):
  a causal Transformer (GIVT) predicting Music2Latent frames (64 dimensions,
  about 11 Hz). In their paper IC **falls with repetitions** (in-song learning),
  is higher for segment types that come later in a piece, and **significantly
  predicts EEG responses to songs** beyond the energy envelope (20 participants,
  p = 0.025). That is the strongest true claim available for "it is surprised".
- A diffusion-based successor (Bjare, Lattner, Widmer 2025, arXiv 2508.05306)
  fits data better and matches or beats GIVT on pitch surprisal and boundary
  detection. Same repository.
- Licence: CC BY-NC 4.0 (commercial licence on request from Sony CSL). Fine for
  building; flag before exhibition.

Run it once per song and per library clip; resample IC to the 2 Hz step (mean
and max inside the step). If it does not install or is too slow, say so and use
the fallback: the core's own prediction error (section 3.4). Do not fake it.

### 3.4 Workspace: the recurrent core

Brains integrate over longer and longer windows further up the cortex: Hasson et
al. 2008 (*J. Neuroscience*) measured about 12 s in the STS and precuneus and
about 36 s in higher areas, against short windows in early sensory cortex.

**Round 1 core: a seeded leaky reservoir.**
- 512 leaky units at the 0.5 s step. Each unit's time constant drawn
  log-uniformly from 0.5 s to 60 s: the receptive-window hierarchy. Sparse random
  recurrent weights (10 % density), scaled to a spectral radius set by check 7.2,
  start at 0.9. Fixed by a seed; nothing in the core is trained. A hierarchical
  or clockwork arrangement (groups updating at different rates; Koutník et al.
  2014) is allowed if a flat reservoir mixes timescales poorly.
- Input per step: the 64-dim ear vector, the pulse summary (10), IC mean and max
  (2), and the rehearsal input (3.5). Inputs are standardised on training folds.
- **The core's own expectation**: a ridge readout from state *n* predicts the ear
  vector at *n + 1*. Its error per step is a second, in-song surprise signal,
  split by time-constant band (fast, middle, slow units). This is also the
  fallback if 3.3 is unavailable.
- Output: the state (512) and its PCA to 64 dimensions, the **mind state**.

**Only if round 1 fails check 7.1**: a small trained core. Candidate: a liquid
time-constant network (Hasani et al., AAAI 2021), whose units' time constants
change with input, a closer analogue to neuromodulated cortex. Trained on DEAM
and MERP continuous labels plus next-step prediction, folds by song. The brain
analogue argues for it; the cost (training, instability) argues for trying the
reservoir first.

### 3.5 Rehearsal: the memory of having heard it

The dancer has rehearsed the song, so the claim has to be literally true.
1. **Rehearsal pass**: run the core over the whole song from rest, causally,
   with no rehearsal input. Store its mind state per step.
2. **Performance pass**: run again from rest. At step *n* the core also receives
   what it *remembers* comes next: the stored rehearsal mind state at *n + L*
   for L of 1 bar, 4 bars and 16 bars (PCA'd to 8 each: 24 inputs), scaled by ρ.
   Its schematic stream is still surprised by a drop it knows is coming. Its
   veridical stream starts moving before it.

ρ = 1 by default. ρ = 0 is the naive first listen and the ablation. A learning
installation (several passes, memory building between them, as in
complementary learning systems) is possible on top of this and **out of scope**.

### 3.6 Readouts

Linear ridge maps from the mind state, fitted on labelled data with folds by
song. These are instruments for checks and for display. The body never reads
them; stage 3's decoder reads the mind state itself.
- Valence and arousal over time: DEAM (2013/2014 release, as stage 1) and
  **MERP**: 54 full-length songs, continuous valence and arousal at 10 Hz, 277
  raters after filtering; annotations CC BY 4.0, audio from the Free Music
  Archive under per-track Creative Commons licences, some NC (Koh et al. 2023,
  *Sensors*). MERP matters because its songs are **whole**: DEAM's 45 s clips
  hold no sections, returns or climaxes for a memory to use.
- The nine GEMS feelings: Emotify, clip means, as stage 1.

---

## 4. Rates and flow

```
audio ──▶ onset envelope 100 Hz ──▶ PULSE (180 oscillators, 100 Hz) ──┐ summary per 0.5 s
      ├─▶ stage-1 encoder 2,665 / 0.5 s ──▶ PCA 64 ───────────────────┤
      └─▶ audio IC ~11 Hz ──▶ mean, max per 0.5 s ────────────────────┤
                                                                       ▼
                     rehearsal memory (n+1 bar, +4, +16) × ρ ──▶ WORKSPACE (512 leaky units,
                                                                 τ 0.5–60 s, seeded) at 2 Hz
                                                                       │
                                     own prediction error per band ◀───┤
                                                                       ▼
                                              MIND STATE (PCA 64) per 0.5 s, per beat
                                                    │                       │
                                         readouts (checks, display)   stage 3 decoder → body
```

---

## 5. Output

Additive sidecar field `mindState`, written by `scripts/emotion/mind.py`:
`version`, `seed`, `rho`, `hopSeconds`, `steps` (64 per step), `perBeat`,
`pulse` (per step: band amplitudes, phase, strength, expected next onset),
`ic` (mean, max), `ownError` (fast, middle, slow), `readouts` (valence, arousal,
nine GEMS, with fold provenance), `provenance` (component versions, PCA and
ridge fit ids). The input sidecar stays byte-identical. Stage 3 compares the
stage-1 encoding and the mind state as decoder inputs under its own check.

---

## 6. Where things live

Python, offline, `scripts/emotion/` (`pulse.py`, `ic.py`, `mind.py`, tests
beside them). Environment `/secondary/hyst-env/emotion`; data and caches under
`/secondary/hyst-data/emotion/`; nothing on the root disk. Nothing in the planner
changes in this stage. Golden digests and `Off` untouched. A Rust port, for live
use or the engine, is later and out of scope.

---

## 7. Check 1b, fixed before any result

Same folds (by song), seeds and bootstrap as `check1.py`, plus MERP split by song
into the same five folds. The **reference is stage 1's pick read memorylessly**
(ridge on the 2,665 vector per step), and **ρ = 0** is the ablation of rehearsal.

### 7.1 It follows the song (the gate)
- **Within-song tracking**: per held-out song, Pearson r between predicted and
  rated arousal and valence over time (song means removed), averaged over songs;
  on DEAM and on MERP separately. Pass: arousal r beats the reference on both,
  with non-overlapping 95 % intervals. Valence is reported, not gated (it is the
  weaker label; DEAM's manual says the dynamic arousal annotations are better).
  For scale only, not a target: an LSTM in MediaEval 2014 reached mean r 0.354
  arousal and 0.198 valence on a different setup (Coutinho et al. 2014).
- **Mood kept**: pooled timing R² and the Emotify rank correlation stay inside
  stage 1's pick's intervals (no loss of what stage 1 gained).

### 7.2 It uses its memory (an ablation the story depends on)
- Shuffle the order of steps within each held-out song, rerun the core: within-
  song arousal r must drop by at least half. If order does not matter, there is
  no memory, and no claim to make.
- The spectral radius is chosen inside the training folds by 7.1; the test
  folds never see it.

### 7.3 It keeps a pulse
On the three danced songs against their sidecar grids (Five Years: its tempo map):
lock within 8 beats of the song's first sustained drum; median phase error
under 60 ms after lock; through each "Presence" break, the phase drifts by under
a quarter beat. Report the missing-pulse case if any song shows one.

### 7.4 It is surprised, and it learns within a song
- IC (or the fallback own error) on the second occurrence of repeated material
  (the repetition map) is lower than on the first, on MERP and on the three
  songs (sign test over pairs, p < 0.05 on MERP).
- At the known lifts of the three songs, surprise is in the top 10 % of that
  song's steps.

### 7.5 It has rehearsed
ρ = 1 against ρ = 0 on the three songs and MERP: the mind state's distance
between the two passes, in the 8 beats before each known lift, is larger than in
random 8-beat windows elsewhere (permutation test, 1,000 draws, p < 0.05).
Anticipation must exist, and must sit where the arrivals are.

### 7.6 The user's own feeling (diagnostic and, once recorded, a gate)
- The user's stage-1 notes are fixed tests: the "Five Years" opening reads lower
  in arousal than its climax; "Presence" 2:00–3:10 reads sad.
- **Before round 1 starts**, the user records the whole-song dial from
  `EMOTION.md` stage 4 on the three songs, **audio only**, once, unseen by the
  builder until results are in. It is the only within-song truth that is the
  user's own feeling. Gate: the mind's arousal readout correlates with the dial
  better than the reference does, on at least 2 of the 3 songs.

---

## 8. Rounds and stop rules

| Round | What | Then |
|---|---|---|
| **1** | Build 3.1–3.6 with the reservoir core. Run check 1b. | All gates pass → done. Else round 2. |
| **2** | Change only what the failing check points at: oscillator regime and density (7.3), spectral radius and τ range (7.1, 7.2), PCA size, or swap the reservoir for the LTC core (7.1 only). No new parts. | Pass → done. Fail → stop, park, report. Stage 3 then uses the stage-1 encoding. |

Every result in `docs/DANCE_HANDOFF.md`: numbers, intervals, held-out set, every
constant and where it came from, and what was not done. Nothing is "better"
until its check says so.

---

## 9. What may be said about it (the truth table)

| Public claim | Mechanism | Licensed by |
|---|---|---|
| "It hears a pulse, and holds it through silence." | oscillator bank (3.2) | 7.3 |
| "It is surprised." | audio information content (3.3), its own prediction error (3.4) | 7.4 |
| "It remembers what it has heard in the song." | the recurrent core (3.4) | 7.2, 7.4 |
| "It has rehearsed the song, and expects what comes." | rehearsal memory (3.5) | 7.5 |
| "Its mood builds and fades over the song." | the core's slow units | 7.1 |
| "Its feeling of the song resembles a person's." | readouts against human ratings | 7.1, 7.6 |
| "It feels." | — | **never**. That is the open question the piece asks. |

A claim whose check fails is removed from all wall text, captions and talk.

---

## 10. Display (later, not this stage)

The mind state is recorded per step so it can be shown: СИНТЕЗА rendering the
mind beside the body, or a second screen of its pulse, surprise and slow mood.
Showing the inner state is what makes the "how" legible. The data contract above
is enough; nothing is built for it now.

For stage 2 (the body), related evidence on what makes motion read as alive:
self-propelled changes of speed and direction, motion that seems to carry its own
energy, orientation that turns with the path, and goal-directed or contingent
motion (Torabian & Grossman 2023, *Frontiers in Psychology*, a review of
Heider-Simmel-style work). The pulse's expected-next-onset and the rehearsal
memory are the honest sources of such anticipation.

---

## 11. Licences

| Part | Licence |
|---|---|
| MERT-v1-95M | CC BY-NC 4.0 |
| Essentia Discogs-EffNet, mood head | CC BY-NC-SA 4.0 |
| CLAP (`larger_clap_music`) | Apache-2.0 |
| `audioic` | CC BY-NC 4.0 (commercial on request) |
| DEAM | BY-NC, non-profit |
| MERP | annotations CC BY 4.0; audio per track, some NC |
| Emotify | none stated, cite the paper |

All fine for building and checking. Before the piece is exhibited or sold, each
is checked, and anything that does not allow it is replaced or dropped.

---

## 12. Out of scope

A live port; per-arm minds; the learning installation (several passes with
consolidation); the body feeling itself (motor state fed back into the core);
СИНТЕЗА reading the mind; any change to the planner, the dance, or version 47.

---

## 13. For the builder: order of work, stop at each ★

1. Read `docs/EMOTION.md`, `docs/EMOTION_ARCH.md` (or the "Emotion stage 1"
   handoff entry) and this file. Run the repository's checks.
2. Write `check1b.py` with every rule in section 7 **before** computing anything
   it scores. Commit it.
3. Data: MERP download, licence text and hashes into `SOURCES.md`; folds by song.
   ★ Report MERP's size and any licence surprise.
4. `pulse.py` (3.2) with unit tests on synthetic click trains (lock, missing
   pulse, held through a gap). Then 7.3 on the three songs. ★ Report.
5. `ic.py` (3.3): install `audioic`, run on one song, report speed. If it fails,
   say so and use the fallback. ★ Report.
6. `mind.py` (3.4–3.6), deterministic with tests: same seed gives the same
   output; shuffle changes it; ρ = 0 drops the rehearsal input exactly.
7. Run check 1b. Write the handoff entry. ★ Stop for the user's verdict.

The user records the stage-4 dial on the three songs (7.6) before step 7's
results are opened.

---

## Sources

- Large, Almonte, Velasco 2010, canonical model for gradient frequency neural
  networks, *Physica D* 239:905–911.
- Large, Herrera, Velasco 2015, Neural networks for beat perception in musical
  rhythm, *Frontiers in Systems Neuroscience* 9.
- Kim & Large 2015, Signal processing in periodically forced gradient frequency
  neural networks, *Frontiers in Computational Neuroscience*.
- Hasson, Yang, Vallines, Heeger, Rubin 2008, A hierarchy of temporal receptive
  windows in human cortex, *J. Neuroscience* 28(10):2539–2550.
- Bjare, Cantisani, Lattner, Widmer 2025, Estimating musical surprisal in audio,
  ICASSP 2025; code `github.com/SonyCSLParis/audioic`.
- Bjare, Lattner, Widmer 2025, Estimating musical surprisal from audio in
  autoregressive diffusion model noise spaces, arXiv 2508.05306.
- Koutník, Greff, Gomez, Schmidhuber 2014, A Clockwork RNN, ICML.
- Hasani, Lechner, Amini, Rus, Grosu 2021, Liquid time-constant networks, AAAI.
- Koh, Cheuk, Heung, Agres, Herremans 2023, MERP, *Sensors* 23(1):382.
- Coutinho, Weninger, Schuller, Scherer 2014, The Munich LSTM-RNN approach to the
  MediaEval 2014 "Emotion in Music" task.
- Torabian & Grossman 2023, review of motion cues to animacy and agency,
  *Frontiers in Psychology*.
- Huron 2006, *Sweet Anticipation*, MIT Press.
