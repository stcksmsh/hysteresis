# Work order 2 (2026-11-04): two builders, unattended-safe

Read first: `docs/BODY_BRAIN_PLAN.md` (version 2). Branch: each builder works on its own branch from `body`
(`body-m1m3`, `body-h2show`) and the overseer merges. Each builder keeps its own `docs/NIGHT_LOG_<branch>.md` with a
MORNING SUMMARY on top, updated after every phase. Never wait for input: take the named default, log "FOR USER".

Cores: builder 1 gets 12 threads, builder 2 gets 6, 2 stay free. Memory caps: 14 GB and 6 GB (systemd-run scopes).
All long runs through `scripts/compute/run_job.py`. Laptop on mains power. Kaggle only where stated (free quota; no paid
service ever).

Before anything else, the overseer: commits plan version 2 and the 2026-11-04 rulings (plan §2) as a dated note.

---

## Builder 1: body track (M1, M3 benchmark, T-M3)

**Phase 1, M1 toy (≤ 45 min).**
1. Babbling generator: M2 commands as Ornstein–Uhlenbeck processes (time constant 1 s, full ranges, seeds fixed) → M0
   physics → proprioception logs. Unit test: reproducible from a seed.
2. 1 h of babbling; a small forward model (plan §5); must beat persistence at +100 ms on 10 min of held-out babbling.
   Fails → debug (alignment of the 10 ms proprioception delay first), 30 min more. Still failing → log, skip to phase 3.

**Phase 2, M1 run and K1 (≤ 4 h).**
1. Data: 20 h train, 2 h held out (seeds fixed); the v47 set (three danced songs' trajectories as servo targets).
2. Commit `check_m1.py` with K1 exactly as plan §5 before training.
3. Train. If the projection exceeds 4 h on the laptop → a Kaggle job via run_job (checkpointed). Otherwise local.
4. Run K1. Fails → round 2, limited to model width and training length; one rerun. Record both.
5. Export the self-surprisal lane for the three danced songs (the arm replaying v47 in physics).

**Phase 3, M3 step benchmark (≤ 45 min, report only).** One full step: cortex twin pass (moving and still) with the
zero-initialised proprioceptive relay, relay backward, physics, basal ganglia + motor cortex + critic forward/backward,
at 16, 64 and 256 environments, laptop CPU (and one Kaggle T4 job). Report seconds per simulated hour and memory. Also
the identity test: with the new relay at zero, cortex outputs equal B7 epoch 6 (float64 ≤ 1e-9).

**Phase 4, T-M3 build (≤ 2 h).** Plan §6 exactly: synthetic pulse-train features with slow tempo drift; reduced cortex
(16 modes per layer), trained briefly on the synthetic stream and frozen; K = 8 motor programs with Go/NoGo selection
every 0.5 s and switch cost; bounded motor-cortex modulation at 10 Hz; critic; dopamine lane; reward with S_still twin,
LP from the M1 cerebellum (or a toy cerebellum if M1 failed: log it), energy; the SYNC term behind a flag (off). PPO with
a hybrid action. Unit tests: gating (only the chosen program reaches the generators), switch cost, reward pieces on
synthetic values, identity at step 0.

**Phase 5, T-M3 tries (two tries, 4 h box each).**
1. The grid of plan §6 (β, λ, c_sw), runs in parallel within builder 1's threads; pick by the rule; freeze; record.
2. Try 1 with the chosen setting. Pass (a)+(b)+(c) → stop and report.
3. Fail → diagnose in ≤ 30 min (is S_still − S_moving ever non-zero? does the critic learn? does selection collapse to one
   program?), then try 2 with one engineering change named in the log (learning rates, entropy bonus, episode length;
   not the reward definition). Also run the γ grid for the SYNC fallback (flag on) as a separate toy run, report only, so
   γ is fixed before any real K2 result.
4. **Stop. Do not start the real M3 run.** Report.

Defaults if blocked: Kaggle unavailable → everything local, smaller sizes, logged. Physics or JAX install trouble → MuJoCo
CPU only. A unit test that cannot pass in 30 min → log, skip the dependent phase, continue with the next independent one.

---

## Builder 2: memory and show tracks (H2, brainDump)

**Phase 1, H2 toy (two tries, 3 h box each).** Plan §4 exactly: fixed random projection to 2,048 dimensions, top-64
sparsification, one-shot store every 0.5 s, retrieval ≥ 17 s old, fixed temperature, only the relay trains. Same three
designs, same toy settings and bar as H1 (T1a + T1b). Also run the oracle and the untrained-H1 baseline for comparison.
Try 2 may change only k, the sparsity and the temperature (chosen before the run, logged). Unit tests: the projection is
fixed (no gradient reaches it), storage is one-shot, eligibility age, novelty lane every 0.5 s.

**Phase 2, brainDump exporter (≤ 3 h).** Plan §8: a script that runs B7 epoch 6 over a song's features and writes, at
30 Hz: mode states (4 × 256 complex), per-layer predicted mean and actual target, per-layer surprisal, arousal, gain and
|λ| exponent, the self-similarity lane, the ignition readout (cross-band phase coherence over 1 s windows, threshold
crossings marked; threshold = the 99th percentile over 20 training songs, fixed before the danced songs are run). Format:
float16 `.npz` per song plus a JSON schema. Run it on the three danced songs. Report size per song. No claims, mechanism
names only.

**Phase 3, B7 lanes into `mindState`** for the three danced songs (mechanism names per the 2026-11-01 naming ruling), so
the authoring fallback and the monitor read B7, not core-2b. `mood.energy` stays from core-2b.

**Phase 4, if time is left:** a static HTML trace viewer of one brainDump (EEG strip of the four layers, surprisal, arousal,
self-similarity, ignition crossings) synced to the song's audio clock. Plain, fine-line, near-black. This is a debugging
view for the overseer, not the monitor design (the planner renders the design mockups separately).

Defaults: H2 fails both tries → log, the hippocampus is closed for this plan, continue with phase 2.

---

## What comes back (the overseer, after recomputing the key numbers)

- K1 with intervals (both sets), the self-surprisal lane, M1 training time and where it ran.
- The M3 benchmark table and the identity test.
- T-M3: the grid, the chosen β, λ, c_sw, γ; (a)–(c) per try; programs used, switches per minute, selection entropy.
- H2: T1a/T1b per design and try, oracle and untrained baselines.
- brainDump: sizes, the ignition threshold, the three songs' files; the B7 lanes in `mindState`.
- FOR USER items from both night logs.
