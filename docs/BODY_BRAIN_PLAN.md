# The body and the brain: plan, rules and checks (Hysteresis), version 2

Version 2, 2026-11-04, accepted by the user. Replaces version 1 (2026-11-03) in full; the dated notes recorded under
version 1 stay valid where this file repeats them. It sits on top of `docs/BRAIN_SPEC.md` (B1–B7 and H1, closed). Branch
`body`. Never push to `master`.

## 0. The goal, and how every step must serve it

**"A scaled human, just so it can dance."** One arm, driven entirely by a simulated brain built from real brain
structures, as far as the hardware allows. Nobody designs how it moves: its movement is learned. Its brain is shown,
quasi-live, as real data that reads as a brain. Every public sentence about it is true (a passed check or true by
construction). The work is creepy because all of that is real and it is still unclear whether anyone is home.

Every step below is judged by four questions, in this order:
1. **Self-driven:** does it bring the arm closer to moving by its own learned control, with no hand-designed mapping?
2. **Brain-like:** is the mechanism a real brain structure working the way that structure works (not a label on a trick)?
3. **Shown:** can it be displayed as real data on the monitor or seen in the arm?
4. **True:** what sentence does it license, and which check decides that?

The authoring tool (`scripts/author/`) is the last-resort fallback only: it drives the arm from brain lanes if the arm
cannot learn to move. No further work on it.

## 1. Rules (binding)

- **Claims vs design.** A public claim needs a check committed before its result; two rounds at most (build, then one
  adjustment limited to what the failing check names). Design (look, layout, staging, knob values set on toys) is judged
  by the user's eye.
- **Toy first.** Every new mechanism passes a toy test (synthetic data, minutes to a few hours, time-boxed) before any run
  over 2 h. Toy tests are engineering go/no-go: no round limit, but a fixed number of tries where stated.
- **Never tune on held-out artists or test sets** (held-out = 73 artists / 357 songs, BRAIN_SPEC §1.4).
- **Truth words** as in §9. Interpretive nicknames only inside the user's private tools.
- **Money:** free tiers only (laptop, Kaggle, Modal's free credit). Any paid spend needs the user's go-ahead each time.
- **Data:** private datasets only; features, never audio.
- **Unattended work** follows §11's template. Long runs through `scripts/compute/run_job.py`, checkpointing, memory-capped,
  on mains power.
- **Provisional servo model:** every body result states it (Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5,
  acceleration share 0.25) until the user chooses a servo.
- Frozen `src/` and `tools/` read-only; never drive hardware; version 47 byte-identical in `Off`; plain commit messages,
  no attribution lines; data, models, audio and videos outside git.

## 2. Where things stand (2026-11-04)

| Part | State |
|---|---|
| Cortex (B7 epoch 6) | the cortex of record, frozen. Claims in §9 |
| Hippocampus H1 (gradient-trained keys) | failed both tries; off. Training made retrieval worse than untrained keys; the oracle works |
| Compute (step Z) | done: GPU flag in training, mid-epoch checkpoints, private datasets `hyst-features` and `hyst-code`, Kaggle job path, benchmarks |
| Body (M0) | done: MuJoCo arm from the rig, mirror ball implement, provisional servo, proprioception, CPU/MJX parity, CSV export |
| Spinal pattern generators (M2) | done: per-joint oscillators, coupling, rate limits, ±180° cap on continuous joints |

Benchmarks: a B7-size training epoch over the 175 h corpus is ~1.9 h on the laptop, ~0.8 h on a Kaggle T4. B7 forward
runs at 0.24 % of real time on the laptop (a live mode is possible later). Physics: the laptop CPU beats the T4 up to
1,024 environments.

Rulings of 2026-11-04 (record them as a dated note): implement = mirror ball; ±180° cap; B7 lane export comes with the
monitor (§8); checks stay on CPU; servo values provisional; a Kaggle job verifies the whole `hyst-features` upload; K4 as
in §6; the self-similarity data lane (§8) is allowed with no claim; H1 confirmed off, M4 (H1-based) dropped.

## 3. The machine, and how close it is to the user's A/B/C framework

| Region | Mechanism | Learns by | Step | A/B/C |
|---|---|---|---|---|
| Ear + thalamus | 44 fixed sound features at 100 Hz, relayed to every layer | — (relay learned) | built | A, weak: fixed features, not a learned hierarchy |
| Cortex | 4 oscillatory layers, nested timescales, per-layer prediction, learned precision | prediction | built, frozen | B, about half (see below) |
| Arousal (noradrenaline-like) | own surprisal scales gain and memory length | — | built | B, neuromodulatory state |
| Precision (acetylcholine-like) | learned predicted variance weights each layer's error | prediction | built | B, precision |
| Hippocampus | sparse random code, one-shot storage, trained readout | one-shot + readout | **H2** (§4) | beyond A/B/C |
| Body + proprioception | physics arm; position, velocity, load, quantised, 10 ms delay | — | built | — |
| Cerebellum | forward model of its own body (efference copy) | supervised | **M1** (§5) | beyond A/B/C |
| Spinal pattern generators | per-joint oscillators set by the brain | — | built | — |
| Basal ganglia + dopamine | **selection** among motor programs by go/no-go gating; dopamine = TD error | reward | **M3** (§6) | **C, literal** |
| Ignition readout | cross-band coherence events | — | **B5** data lane (§8) | B, ignition (shown, not claimed) |

What is missing from B, parked until after M3 (a cortex retrain, §10): each level predicting the level below literally; a
learned hierarchical A; emotion as attractor basins; a multi-function workspace. The learning split follows Doya 1999
(cortex unsupervised, cerebellum supervised, basal ganglia reinforcement). Verify every citation in this file before
public use; the planner cited from memory.

## 4. H2: the hippocampus, built the way a hippocampus works (toy)

H1 trained its keys by gradient, which a hippocampus does not do. H2:
- **Dentate gyrus (pattern separation):** a fixed random projection of [raw features pooled over 2 s, cortex L3 + L4
  state] to 2,048 dimensions, then top-k sparsification (k = 64, ~3 %), then L2-normalised. Fixed seed; never trained.
- **CA3 (one-shot storage):** every 0.5 s, store (sparse key, pointer to that moment) in the per-song store. No gradient.
- **Retrieval:** cosine of the current sparse code against entries ≥ 17 s old; top-k = 4; a fixed temperature (set on the
  toy, recorded).
- **CA1 (the only learned part):** the replay of the four horizon targets from the retrieved pointers (as in B7's pointer
  replay), plus recognition (max similarity), fed into the relay; only the relay weights train.
- **Novelty:** 1 − max similarity, every 0.5 s.
- **Toy bar:** T1a + T1b (BRAIN_SPEC §7.10 R3), on the three designs. Two tries, 3 h box each. Try 2 may change only k,
  the sparsity, and the temperature.
- **If it passes:** it joins the cortex's relay in M3 (the cortex core stays frozen; the CA1 relay trains with M3's music
  loss), and C1–C3 (BRAIN_SPEC §7.4; C3 on the 0.5 s novelty lane, window unchanged) get their round 1 on held-out songs
  after M3 training. It may also store the arm's own commands with each entry ("how it moved here last time"), shown on
  the monitor, with no claim.
- **If it fails:** the hippocampus is closed for this plan.

## 5. M1: the cerebellum

- **Babbling data:** M2 commands as Ornstein–Uhlenbeck processes (time constant 1 s, full command ranges, fixed seeds)
  through the M0 body; 20 h train, 2 h held out. Out-of-distribution set: v47's three danced songs' commanded
  trajectories replayed in physics as servo targets (no pattern generator).
- **Model:** a small recurrent network; input = proprioception + the current command + the last 100 ms of commands
  (efference copy); output = Gaussian predictions of proprioception at +10, +50 and +100 ms; loss β-NLL (β = 0.5).
- **Toy first (≤ 30 min):** 1 h of babbling, a small model, must beat persistence at +100 ms on held-out babbling.
- **Check K1** (committed before the run): on held-out babbling and on the v47 set separately, NLL interval above 0
  against persistence and against ridge on the same inputs (per-trajectory bootstrap), and MSE ≥ 5 % below the better
  baseline. Claim: **"It predicts where its own arm will be a moment from now."**
- **Lane:** self-surprisal = NLL of the actual body state under the cerebellum's prediction.
- Local; Kaggle only if the run projects past ~4 h on the laptop.

## 6. M3: basal ganglia, dopamine, and learning to dance

**Listening first.** The B7 cortex is frozen. New zero-initialised relay weights carry proprioception and the
cerebellum's prediction error into every cortex layer (step 0 = B7 exactly; tested). Only they, the H2 readout (if H2
passed), the basal ganglia and the motor cortex learn.

**Basal ganglia as selection (C, literal).**
- A repertoire of K = 8 **motor programs**. Each is a learned vector of M2 commands (per joint: frequency, amplitude,
  centre, neighbour lag), initialised from 8 random babbling commands (fixed seed).
- Every 0.5 s the striatum scores each program (Go minus NoGo, from the pooled L3 + L4 state, proprioception, cerebellar
  prediction and error, arousal). A softmax picks one; staying with the current program is free, switching costs c_sw
  (set on the toy). Gating is literal: only the selected program reaches the spinal generators.
- **Motor cortex** adds a small continuous modulation to the selected program at 10 Hz (bounded to ±20 % of each command
  range), so movement can follow the music within a program.
- **Critic** (striatal value) on the same input. **Dopamine lane** = the TD error δ.
- Algorithm: PPO with a hybrid action (categorical program, Gaussian modulation), clip 0.2, GAE λ 0.95, γ 0.99 per 0.1 s.
  Program vectors are learned with the policy. Every setting is recorded before the first run.

**Reward, per 0.1 s:** `r = (S_still − S_moving) + β · LP − λ · E`
- S_moving: the cortex's total music surprisal with the real proprioception; S_still: a twin pass fed the proprioception
  of the arm at rest in its neutral pose;
- LP: the cerebellum's learning progress (mean error over the previous 10 s minus over the last 10 s, floored at 0);
- E: mechanical energy over the step (Σ|τ·ω|·dt).
- **Round-2 fallback, fixed now:** if K2 fails in round 1, round 2 adds `+ γ · SYNC`, where SYNC is the phase-locking
  value over the last 2 s between the dominant joint's velocity and the cortex's own L3 (beat-band) phase. That is its
  internal rhythm, not the beat grid. γ is set on the toy. Nothing else changes in round 2.

**Toy T-M3** (go/no-go; two tries, 4 h box each): synthetic pulse-train features with slow tempo drift; a reduced
cortex (B7 architecture, 16 modes per layer, briefly trained on the synthetic stream, then frozen) so internal memory is
scarce.
- β, λ, c_sw (and γ, in a separate fallback toy run) are set by a small grid on the toy only: β ∈ {0, 0.1, 1}, λ ∈ {0.01,
  0.1, 1}, c_sw ∈ {0, 0.1} (all relative to the toy's mean |S_still − S_moving| at initialisation). Pick the setting that
  maximises (a) subject to (b), then freeze and record them.
- Pass: (a) mean S_still − S_moving > 0, interval over episodes above 0; (b) RMS joint speed ≥ 10 °/s; (c) joint velocity
  phase-locks to the pulse (phase-locking value above 1,000 circular-shift surrogates, p < 0.01).
  Report: programs used, switches per minute, selection entropy.
- If T-M3 fails twice: M3 stops; the fallback drives the arm (authoring tool on brain lanes). Report why.

**Real run:** training artists only; checkpoints every 30 min; laptop for physics, the cortex twin pass wherever the M3
benchmark says is cheaper.

**Checks on held-out songs** (two rounds each; round 2 for K2 is the SYNC fallback; for K3 and K4 a change of λ only):
- **K2:** mean S_still − S_moving > 0, per-song bootstrap interval above 0. Claim: **"It learned to move because moving
  helps it anticipate the music."** (With the fallback: "...because moving helps it anticipate the music, and it is
  rewarded for moving in time with its own internal rhythm.")
- **K3:** phase-locking value between the dominant joint's velocity and the offline beat grid's phase above 1,000
  circular-shift surrogates (p < 0.05) on ≥ 70 % of held-out songs. Claim: **"Its movement locks to the beat."**
- **K4** (ruling 2026-11-04): two runs per held-out song (initial pose within ±10° of neutral, independent sensor noise,
  policy mean action); non-overlapping 8 s windows from 10 s after the start to 10 s before the end; the 37 body-study
  descriptors per window, standardised by the body-study SDs; d_same = distance between run 1 and run 2 of the song at
  the same window; d_diff = distance between run 1 and run 1 of another held-out song (fixed-seed pairing) at the same
  relative position. Pass: the per-song mean of (d_diff − d_same) is above 0, with a 95 % bootstrap interval over songs
  above 0. Claim: **"It moves differently to different music."**
- By construction, if only the learned policy drives the arm: **"Nobody designed how it moves."**
- **The user's eye** on the three danced songs (previz from physics) is the final judge of whether it is watchable.

## 7. Real arm (the user)

When the user chooses a servo, the provisional model is replaced by datasheet values, M0's tests rerun, and K1–K4 are
re-reported (not re-claimed) on the new model. An agent never drives hardware.

## 8. B5: showing the brain

Every mark is a real variable; layout may be designed, values may not. House style: near-black, fine line, one system,
mechanism labels, no chrome, no REC indicators, no drawn brain.

- **Export `brainDump`** per song (outside git), 30 Hz: B7 mode states (4 × 256 complex); per-layer predicted mean and
  actual target; per-layer surprisal; arousal, gain and |λ| exponent per layer; **self-similarity** (1 − max cosine to its
  stored past states, random projection; a data lane, never called novelty or recognition unless H2's C1/C3 pass);
  **ignition readout** (cross-band coherence of the four layers' phases over 1 s windows, with threshold crossings marked;
  a data lane, never called ignition or awareness); later: cerebellar predicted vs actual pose, self-surprisal, selected
  program, Go/NoGo scores, dopamine δ, motor commands; H2 recognition and recall source if H2 passes.
- **Elements:** EEG strip of the four layers; the cortex sheet (each mode a needle, length = magnitude, angle = phase,
  laid out along a folded curve, the folding stated as decorative); expected vs arrived with the gap lit; surprisal
  climbing the layers; arousal as a global intensity; a ghost of the arm where the cerebellum expects it; the basal
  ganglia's program choice as a row of eight gates; the dopamine trace; recall arcs if H2 passes.
- The planner renders mockups on synthetic data; the user picks a look; then the builder builds a standalone page synced
  to the audio clock, later inside СИНТЕЗА.

## 9. Truth table

Allowed now:
- "Its activity is organised in bands modelled on EEG rhythms." (construction)
- "An arousal signal computed from its own surprisal changes the gain and memory length of its layers." (construction)
- "When its arousal signal is frozen, its predictions get measurably worse." (C4a)
- "It assigns higher probability to music it has not heard than a linear model, simple persistence, or an untrained copy
  of itself." (C5 NLL condition)
- "Its surprisal rises more when the music cuts to a different song than when it cuts within the same song (median z
  5.3 vs 0.7)."
- "Rhythmic movement comes from oscillators in its 'spinal cord'; its brain sets their speed, size and timing."
  (construction, M2; true once the arm is driven through them)
- Monitor label: "A recurrent network trained on 175 hours of Creative Commons music to predict what comes next. Its own
  surprisal drives an arousal signal that changes how it runs."

Pending, each only if its check passes: K1, K2 (or its fallback wording), K3, K4; C1–C3 (only with H2); "nobody designed
how it moves" (construction, only if the fallback is unused); "its basal ganglia choose among motor programs it learned"
(construction, once M3 drives the arm).

Forbidden: learned to predict music; arousal shortens/lengthens its memory (as one direction); entrains, pulse, meter;
coupling; ignition, awareness, conscious; novelty or recognition without H2's checks; tracks arousal or feeling;
remembers, surprised, expects, anticipates, familiar, dreams, wants, enjoys, likes, feels.

## 10. Later, parked until M3 is done

A cortex retrain to close the gap with the user's B: each level predicting the level below literally; a learned
hierarchical encoder for A; emotion as attractor basins in the slow layers; the hippocampal readout trained jointly.
Then: lifetime learning and nightly consolidation; a live listening mode (compute already allows it).

*Correction (user, 2026-11-05):* the installation is ONE arm. The ensemble (hexagon, six-arm wiring, multiple arms) is out of
scope for good and was removed from this list (BRAIN_SPEC §7.17 point 4).

## 11. Order, and the unattended template

Three tracks, run in parallel where builders and cores allow:
- **Body:** M1 (K1) → M3 benchmark → T-M3 → M3 run → K2–K4 → user's eye.
- **Memory:** H2 toy → (if pass) joins M3 → C1–C3 after M3 training.
- **Show:** B7 lane export and `brainDump` (with the self-similarity and ignition lanes) → planner mockups → monitor build.
  Grows as M1 and M3 add lanes.

Template for any multi-hour order without the user: `docs/NIGHT_LOG.md` with a MORNING SUMMARY on top; rules committed
first; time boxes; a named default for every failure; never wait for input; "FOR USER" items with the default taken;
prefer the conservative path (drop a module rather than change a rule); long runs via run_job, checkpointing,
memory-capped, on mains power; morning summary with the path taken, numbers, what is running and how to stop it.

## 12. Story (draft; only licensed lines; the user edits)

> It listened to 175 hours of music before it moved, learning only to predict what comes next. Then it was given a body,
> a sense of where its body is, a small part that predicts its own movements, and a single reward: moving was worth it
> when moving helped it anticipate the music. It chose, from a handful of movements it had invented, which to make.
> Nobody designed how it moves. Everything on the screen is its actual state, at the moment you hear it. The screen
> cannot show whether anyone is there.

(Each clause stands only once its check passes or its mechanism drives the arm.)
