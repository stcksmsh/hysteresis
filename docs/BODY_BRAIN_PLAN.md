# The body and the brain: plan, rules and checks (Hysteresis, from 2026-11-03)

Status: **accepted by the user, 2026-11-03.** This file is the work order from here on. It sits on top of
`docs/BRAIN_SPEC.md` (B1–B7, closed except where this file reopens something) and replaces the "next step" parts of
`docs/NEXT_DECODER_THEN_BRAIN.md`. Where they differ, this file wins. Branch for this work: `body` (cut from `b7`). Never push
to `master`.

## 0. What the user decided on 2026-11-03

1. **The goal, in the user's words:** "to make a scaled human, just so it can dance". The machine gets as many real brain
   structures as the hardware allows: cortex, hippocampus, neuromodulators, cerebellum, spinal pattern generators, basal
   ganglia and dopamine, proprioception. The arm **drives itself**: nobody designs how its state becomes movement.
2. **The authoring tool** (`scripts/author/`, built) is the **last-resort fallback** only. No further investment in it.
3. **B7 round 2 is not taken.** B7 epoch 6 is the cortex of record (§2).
4. **Showing the brain is half the work:** a quasi-live display of the real network that reads as a brain (§9).
5. **Compute:** local CPU first; GPU from **free tiers** (Kaggle first, Modal's free credit second). Data goes up as
   **private** datasets. Paid GPU (Vast interruptible, RunPod community) only with the user's explicit go-ahead each time.
6. **Process:** iterate faster. Toy tests in minutes before any long run; long runs only when the toys pass.

## 1. Rules (binding for every step below)

- **Claims vs design.** A public claim (wall text, monitor wording) needs a check whose pass rule is committed before its
  result, with at most two rounds (build, then one adjustment limited to what the failing check names). Design choices
  (how it looks, layout, staging) are judged by the user's eye with no pre-registered rules.
- **Toy first.** Every new mechanism gets a toy test (synthetic data, small model, minutes) as an engineering go/no-go
  before any run longer than 2 h. Toy tests are not claim checks and have no round limit, but each has a time box.
- **Nothing is tuned on held-out artists or test sets.** Held-out = the 73 artists / 357 songs of BRAIN_SPEC §1.4.
- **Truth words.** Mechanism names on every lane and label; interpretive words only where a passed check licenses them
  (§10). Interpretive nicknames are allowed only inside the user's private tools.
- **Money.** Never create a paid account, add a card, or start a paid instance. Free tiers only, unless the user says go
  for that specific spend.
- **Data.** Datasets uploaded anywhere are private. Audio is never uploaded; features only.
- **Unattended work.** Every overnight or multi-hour order uses the template in §12: time boxes, a default for every
  failure, a `docs/NIGHT_LOG.md` with a morning summary, no waiting for input.
- **Power.** Long local runs only on mains power.
- Frozen `src/` and `tools/` read-only. Never drive hardware. Version 47 stays byte-identical in `Off`. Commit messages
  plain, no attribution lines. Data, models, audio, videos outside git.

## 2. B7 close-out (rulings of 2026-11-03; record in BRAIN_SPEC §7 as a dated note)

1. Round 2 not taken. **B7 epoch 6 is the cortex of record** and the source of every brain lane in `mindState`. C4 and
   C5 round-2 rights are recorded as "not taken", not as failed twice.
2. C5 unchanged. For the record, the warm start restarted the learning rate at ~9× B3's final rate. **Rule for every
   future warm start:** constant learning rate at the source run's final rate, or a warm-up of ≤ 200 steps to it.
3. C4(b): "one common direction across all four layers" is the correct reading and stays. The per-layer directions are
   reported as data (L1 +36 %, L2 −29 %, L3 −8 %, L4 −12 %; 99.4 % same sign) and may appear on the monitor as numbers.
4. The hippocampus is not in B7. It continues as toy step H1 (§5).
5. Backlog: the unexplained step-2 memory growth; long runs on mains power only.
6. Truth table for B7: see §10.

## 3. The target machine

| Region | Mechanism | Learns by | Status |
|---|---|---|---|
| Ear + thalamus | 44 fast features at 100 Hz, relayed to every layer, 10-frame tap to every head | — | built (B7) |
| Cortex | 4 oscillatory LRU layers (8–20, 4–8, 0.5–4, 0.01–0.5 Hz) | prediction (β-NLL) | built (B7 epoch 6), **frozen from here** |
| Noradrenaline-like arousal | surprisal-driven, scales each layer's gain and memory length | — | built, acting (B7) |
| Acetylcholine-like precision | learned predicted variance, weighting each layer's error | prediction | built (B3/B7) |
| Hippocampus | index and replay of the per-song store; novelty | prediction + hindsight retrieval | toy step H1 (§5) |
| Body | MuJoCo model of the 5-joint arm with masses, gravity, servo limits | — | M0 (§6) |
| Proprioception | joint angle, velocity, load (what bus servos report), with latency and quantisation | — | M0 |
| Cerebellum | forward model: command + body state → next body state (efference copy) | supervised, from babbling | M1 (§7) |
| Spinal pattern generators | one oscillator per joint; the brain sets frequency, amplitude, centre, phase | — | M2 (§7) |
| Basal ganglia + dopamine | actor-critic; dopamine = temporal-difference error | reward (§8) | M3 (§8) |

The division of learning rules follows Doya 1999 (cortex unsupervised, cerebellum supervised, basal ganglia
reinforcement). The arousal / precision split follows Yu & Dayan 2005. **Verify every citation in this file against the
paper before it reaches any public text** (the planner cited from memory); record page numbers in the notes.

## 4. Step Z: compute (do first)

Scaffolding is in `scripts/compute/` (tested: `python -m unittest -v test_compute`). Read its README.

- **Z1. GPU support in the existing code.** `train.py`, `train_b7.py`, `core.py`, `core_b7.py`, `check_*.py`:
  a `--device {cpu,cuda}` flag (default cpu; results on cpu must not change: the golden/identity tests still pass).
  The complex recurrence stays float32. Mixed precision only for the MLPs and heads, and only after a toy shows the
  same loss within 1 % over 500 steps. Manifest paths may be relative (resolve against the manifest's folder).
  Feature loaders cast to float32 on load (the packed features are float16).
- **Z2. Checkpoint discipline for 12 h sessions.** Every long job checkpoints at least every 30 min and on SIGTERM, and
  resumes from `{CKPT}` (the runner copies the previous session's checkpoints there). Test it: kill a toy run mid-epoch,
  resume, compare with an uninterrupted run (identical up to float rounding).
- **Z3. Data up.** `pack_features.py` on the corpus (train + validation + held-out) and, separately, on the evaluation
  sets that checks need (DEAM, MERP, Ballroom, GTZAN features; private, never public). Report the float16 cast error
  (the tool prints it). `manifest.py verify` before and after upload.
- **Z4. Code up.** `code_snapshot.py` per commit that runs remotely.
- **Z5. Two benchmark jobs, then nothing long until their numbers are in the log:**
  - `scripts/brain/bench_b7.py` (job `jobs/bench_b7.json`): B7 forward+backward per audio hour on cpu and cuda, peak
    memory, with and without gradient checkpointing; B7 forward-only per audio hour (decides whether a live mode is
    possible later). Writes `results.json`.
  - `scripts/body/bench_physics.py` (job `jobs/bench_mjx.json`): physics steps per second for the M0 arm at
    1, 64, 512, 1,024 and 4,096 parallel environments, on MuJoCo CPU (vectorised) and on MJX GPU if it installs on Kaggle.
- **Z6. Overflow order:** Kaggle (weekly GPU quota shown in account settings) → Modal (free monthly credit, per-second,
  scales to zero) → paid only with the user's go-ahead. One job format everywhere.

User tasks for step Z (the agent cannot do these): create the Kaggle account, verify the phone number, put the API token
in `~/.kaggle/kaggle.json`; later, if needed, the Modal account.

## 5. H1: the hippocampus, toy only (from the 2026-11-03 B7 rulings)

- Diagnosis: chicken-and-egg. Unreliable early retrieval makes the replay noise; the relay learns to ignore it; ignored
  replay gives the retrieval no gradient. The oracle passing (error ratio 0.348) shows the downstream path works.
- Fixes, both in the toy:
  (a) **hindsight retrieval loss:** per read, find (no gradient) the stored entry whose replay would have given the lowest
  prediction error, and train the query with cross-entropy toward it, weight 0.1;
  (b) **scheduled sampling:** start with the oracle pointer and hand over linearly to retrieval over the first 50 % of
  toy training.
- Novelty lane: computed every 0.5 s as 1 − max cosine against the store, with no gradient, independent of the 2 s read.
- Toy bar unchanged (T1a + T1b of BRAIN_SPEC §7.10). Two tries, 3 h time box each. If it passes, the hippocampus joins at
  M4 and C1–C3 get their round 1. If not, it stays off and the monitor never shows recall.

## 6. M0: the body in physics

- **Model:** an MJCF file `scripts/body/arm.xml` built from `Rig::illustrative_five_axis()` (`ensemble.rs`): base yaw
  (z, column 0.08 m), shoulder bend (y, 0.28 m), elbow bend (y, 0.22 m), wrist bend (y, 0.08 m), wrist roll (x, 0.11 m to
  the hand point), mirror implement at the end. Joint ranges as in the rig (base and roll continuous; bends ±110°).
- **Masses and inertias:** estimated, every number recorded with its basis in `scripts/body/BODY_NOTES.md`:
  printed links (material density × estimated volume), one bus servo per joint (mass and stall torque from the datasheet
  of the servo the user intends to buy; if none chosen, a typical 30 kg·cm-class bus servo, marked provisional), the
  mirror implement.
- **Actuators:** position servos (kp, kd) with torque saturation at the servo's stall torque and the body generator's
  per-joint speed and acceleration limits (base 120, shoulder 90, elbow 150, wrist 200, roll 250 °/s; 600 / 300 / 1,000 /
  2,000 / 3,000 °/s²). Gravity on. Timestep 2 ms; control at 100 Hz.
- **Proprioception** (exactly what bus servos report): position (quantised to the servo encoder's resolution),
  velocity, load (actuator force), all delayed by one control step (10 ms).
- **Exports:** trajectories to `EnsembleScore` / the 50 Hz joint CSV, so the existing previz, recorder and limit checker
  work unchanged.
- **Tests (design, no claim):** gravity sag at rest within the servos' torque; limits never exceeded; MuJoCo CPU and MJX
  agree on a 10 s trajectory within tolerance; mechanical power computed per step (Σ|τ·ω|) for the effort term.

## 7. M1 cerebellum and M2 spinal pattern generators

**M2 first (no learning, by construction):** per joint, a phase oscillator producing the joint target
`centre + amplitude · cos(phase)`, with `dphase/dt = 2π · frequency + coupling to the neighbouring joint at a commanded
lag`. The brain commands, at 10 Hz, per joint: frequency (0.1–4 Hz), amplitude (0–joint range), centre, and the
neighbour lag (0–0.5 cycle). Command changes are rate-limited so targets stay smooth and inside limits. Unit tests:
smoothness, limits, coupling sign. Truth line by construction: "Rhythmic movement comes from oscillators in its 'spinal
cord'; its brain sets their speed, size and timing."

**M1 cerebellum:**
- **Babbling data:** random pattern-generator commands (Ornstein–Uhlenbeck in each command, seeds fixed) through the M0
  body; 20 h of simulated time for training, 2 h held out. An out-of-distribution test set: v47's three danced songs
  replayed in physics as commanded trajectories.
- **Model:** a small recurrent network; input = proprioception + the current command + the last 100 ms of commands
  (efference copy); output = Gaussian predictions of proprioception at +10, +50 and +100 ms; loss β-NLL (β = 0.5).
- **Self-surprisal lane:** the negative log-likelihood of the actual body state under the cerebellum's prediction.
- **Check K1, fixed now:** on held-out babbling and on the v47 set separately: NLL interval above 0 against persistence
  and against a ridge model on the same inputs (per-trajectory bootstrap), and MSE ≥ 5 % below the better baseline.
  Claim if pass: **"It predicts where its own arm will be a moment from now."**

## 8. M3: basal ganglia and dopamine (it learns to dance)

- **Listening first:** the B7 cortex is frozen. New, zero-initialised relay weights carry proprioception and the
  cerebellum's prediction error into every cortex layer (step 0 = B7 exactly; test it). Only these relay weights learn
  from the music-prediction loss.
- **Motor cortex (actor):** input = pooled L3 + L4 state, proprioception, cerebellar prediction and error, arousal;
  output = the M2 commands at 10 Hz (Gaussian policy). **Striatum (critic):** value of the same input.
  **Dopamine lane** = the temporal-difference error δ.
- **Reward, per 0.1 s step:**
  `r = (S_still − S_moving) + β · LP − λ · E`, where:
  - `S_moving` = total music surprisal of the cortex with the real proprioception;
  - `S_still` = the same, from a twin pass fed the proprioception of the arm resting at its neutral pose;
  - `LP` = the cerebellum's learning progress (its mean error over the previous 10 s minus over the last 10 s, ≥ 0;
    after Oudeyer's intrinsic-motivation work);
  - `E` = mechanical energy over the step (Σ|τ·ω|·dt).
  β and λ are set on the toy only, then frozen and recorded. They are the only free knobs.
  Grounding (verify before public use): pleasure in music tracks prediction (Salimpoor et al. 2011; Gold et al. 2019);
  movement shapes rhythm perception (Phillips-Silver & Trainor 2005); groove peaks at medium syncopation (Witek et
  al. 2014).
- **Algorithm:** PPO with standard settings (clip 0.2, GAE λ 0.95, γ 0.99 per 0.1 s step); vectorised environments
  (count from the Z5 benchmark); songs from training artists only. Record every setting before the first run.
- **Toy T-M3 (go/no-go, two tries, 4 h box each):** synthetic pulse-train features with slow tempo drift, a reduced
  cortex (16 modes per layer, so internal memory is scarce and the body's physics can help). Pass:
  (a) mean `S_still − S_moving` > 0, interval over episodes above 0;
  (b) RMS joint speed ≥ 10 °/s (it is not standing still);
  (c) joint velocity phase-locks to the pulse: phase-locking value above 1,000 circular-shift surrogates, p < 0.01.
  If T-M3 fails twice: M3 stops, and the fallback (the authoring tool on brain lanes) drives the body. Report why.
- **Checks on held-out songs (two rounds each; a change of β or λ counts as the round-2 adjustment):**
  - **K2:** mean `S_still − S_moving` > 0, per-song bootstrap interval above 0. Claim: **"It learned to move because
    moving helps it anticipate the music."**
  - **K3:** phase-locking value between the dominant joint's velocity and the offline beat grid's phase, above 1,000
    circular-shift surrogates (p < 0.05) on ≥ 70 % of held-out songs. Claim: **"Its movement locks to the beat."**
  - **K4:** it does not do one dance: across held-out songs, the ratio of between-song to within-song variance of the
    body study's 37 motion descriptors exceeds 99 % of 1,000 song-label shuffles. Claim: **"It moves differently to
    different music."**
  - By construction, if the arm is driven only by the learned policy: "Nobody designed how it moves."
- **The user's eye** judges whether it is watchable. If not: one λ change (round 2), else the fallback.

## 9. B5: the monitor (parallel with everything from M0 on)

The user's intent: show the brain quasi-live so that it reads as a brain. **Every mark is a real variable; layout may be
designed, values may not.** House style: near-black, fine line, one system, mechanism labels, no chrome, no REC
indicators, no drawn brain.

- **Export `brainDump`** per song (outside git), 30 Hz: all cortex mode states (4 × 256 complex); per-layer predicted
  mean and actual target; per-layer surprisal; arousal, gain and |λ| exponent per layer; later the cerebellum's
  predicted vs actual pose, self-surprisal, dopamine δ, policy commands, and (if H1 passes) recognition, novelty,
  recall source. Report size per song.
- **Elements:** (1) EEG strip of the four layers; (2) the cortex sheet: each mode a needle (length = magnitude, angle =
  phase) laid out along a folded curve (the folding is decorative and is stated); (3) expected vs arrived, gap lit =
  surprisal; (4) per-layer surprisal shown climbing the layers; (5) arousal as a global intensity; (6) from M1: a ghost
  of the arm where the cerebellum expects it; (7) from M3: the dopamine trace; (8) from M4: arcs back to recalled moments.
- Synced to the audio clock from the sidecar; standalone page first, then inside СИНТЕЗА.
- Before building: the planner renders mockups on synthetic data for the user to pick a look.

## 10. Truth table (all lines; numbers in the records)

Allowed now (B7 epoch 6):
- "Its activity is organised in bands modelled on EEG rhythms." (construction)
- "An arousal signal computed from its own surprisal changes the gain and memory length of its layers." (construction)
- "When its arousal signal is frozen, its predictions get measurably worse." (C4a: +0.061 [0.025, 0.103])
- "It assigns higher probability to music it has not heard than a linear model, simple persistence, or an untrained copy
  of itself." (C5 NLL condition)
- "Its surprisal rises more when the music cuts to a different song than when it cuts within the same song (median z 5.3
  vs 0.7)." (§4.5 condition 2 statistic on B7)
- Monitor label: "A recurrent network trained on 175 hours of Creative Commons music to predict what comes next. Its own
  surprisal drives an arousal signal that changes how it runs."

Pending, each only if its check passes: K1 (predicts its own arm), K2 (moves because moving helps it anticipate),
K3 (locks to the beat), K4 (moves differently to different music), C1–C3 (recognises / habituates / novelty signal,
only with H1). By construction once built: the spinal-oscillator line (§7); "nobody designed how it moves" (§8).

Forbidden: learned to predict music; arousal shortens/lengthens its memory (as one direction); entrains, pulse, meter;
coupling; tracks arousal or feeling; remembers, surprised, expects, anticipates, familiar, dreams, wants, enjoys, feels,
conscious.

## 11. Story (draft wall text; only licensed lines; the user edits)

> It listened to 175 hours of music before it moved, learning only to predict what comes next. Then it was given a body,
> and a single reward: moving was worth it when moving helped it anticipate the music. Nobody designed how it moves.
> Everything on the screen is its actual state, at the moment you hear it. The screen cannot show whether anyone is there.

(Lines about the reward and "nobody designed" stand only after K2 passes and the authoring fallback is unused.)

## 12. Order and the unattended work-order template

Order: **Z** (compute) → **M0** (body) → **M2** (pattern generators) → **M1** (cerebellum, K1) → **T-M3** toy → **M3** run
(K2–K4) → **M4** (hippocampus, if H1 passed) → staging. **H1** and **B5** run in parallel whenever a builder or the
machine is free. Each arrow is a ★ stop with a short report (numbers, held-out sets, "not verified by eye" where true).

Template for any multi-hour order without the user:
1. Setup (≤ 30 min): `docs/NIGHT_LOG.md` with a MORNING SUMMARY block on top; commit the rules first.
2. Phases with time boxes; each failure has a named default; never wait for input; log "FOR USER" items with the default
   taken; prefer the conservative path (drop a module rather than change a rule).
3. Long runs only through `scripts/compute/run_job.py` (locally too), checkpointing, memory-capped
   (`systemd-run --scope -p MemoryMax=20G` locally), on mains power.
4. Morning summary: path taken, numbers, what is running (where, ETA, how to stop it), FOR USER items, commits.

## 13. Out of scope

The ensemble of six arms; live audio in the dance path (the live-brain benchmark is report-only); lifetime learning and
nightly consolidation (later, after M4); any change to the closed B1–B7 claims; real servos (never driven by an agent).
