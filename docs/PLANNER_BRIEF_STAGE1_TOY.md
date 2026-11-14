# Planner brief: the Stage 1 toy is built; two fidelity issues before it runs (2026-11-09)

Rulings in force: BRAIN_SPEC 7.34. The toy's rules: `docs/STAGE1_RULES.md` on branch body-s1 (8700c2b).

## What exists

Built by agent 2 (WO20); the overseer read the rules and the tests. Nothing has run beyond smoke tests.

- **Arm and songs:**
  - a 2-link planar arm, 0.30 m links, 20 Hz, kinematic first-order lag;
  - synthetic 40 s songs: tempo 90-130 BPM, gain, a 2-D slow latent with OU drift;
  - 64 train, 16 validation (only to choose lambda), 32 held-out.
- **Policy:** a GRU. **Observer:** an MLP over 1.5 s of hand positions, output gain G = 4.
- **The four arms:** as in 7.34. Every arm has hinge constraints with dual multipliers, and no other costs.
- **Tests:** 13 pass:
  - InfoNCE ranks the correct pair highest on a constructed batch;
  - the measured Lipschitz constant is <= G;
  - log det K rises when the embeddings spread;
  - the hinges are 0 inside the envelope and fire outside it;
  - the z-score is causal;
  - a 1-epoch smoke run passes for each arm, with finite losses.
- **Cost:** 0.4-0.55 s per epoch at 3 threads. With the amendment to 1000 epochs, about 1.5 h for all 10 runs (5 arm settings x 2 seeds).
- **Not yet run:** the experiment. It waits for the Stage 0 report (7.34.4); Stage 0 is running.

## Issue 1: the toy may not reproduce the collapse it is meant to test

- **Arm (i)'s target is too weak a copy of pass2's.** In pass2, the target was causally z-scored within the song over 30 s, on real songs of about
  3-5 minutes. In the toy, the same 30 s time constant runs on 40 s songs. So the z-score barely acts: the slow dims keep 0.43 of their
  between-song sd (0.99 -> 0.43, measured by the builder). The hypothesis says arm (i) collapses because the z-score hides between-song
  differences. With 43 % surviving, arm (i) may not collapse, and then the comparison tests nothing.
- **The JS distance saturates.** On the toy's 24 x 24 grid of 5 cm cells, the untrained policy already gives between-song JS about 0.9,
  against a half-song control of about 0.06. JS is capped at 1. So "(iv) >= 3x (i)" can only pass if arm (i) falls below about 0.33,
  i.e. if arm (i) actually collapses.

**Q1. Make the toy's arm (i) match pass2's setting?**

Options:
- (a) scale the z-score time constant to the toy's song length: 30 s of a ~4 min song is 1/8, so 5 s on 40 s songs;
- (b) lengthen the toy songs to 240 s and keep 30 s (about 6x the compute, about 9 h serial, or 3-4 h with runs in parallel);
- (c) keep as is.

Recommend (a). Also report the surviving between-song sd of the slow dims under arm (i)'s target, before the run.

**Q2. What if arm (i) does not collapse?**

Options:
- (a) add a precondition, reported before the verdict: "the toy reproduces the collapse" means arm (i)'s trained between-song JS
  <= 1/3 of the untrained policy's, and its distinct postures <= 1/3 of the untrained's. If that fails, stop and report; no verdict on
  (ii)-(iv);
- (b) change the pass measure to a non-saturating one (MMD between hand-position distributions, RBF 0.1 m) and keep "3x" on it;
- (c) no precondition; run and judge.

Recommend (a), plus MMD reported as a secondary column only. The pass rule stays as ruled.

**Q3. Record the builder's pre-run amendments?**

The amendments:
- 1000 epochs per run instead of 300, since the runs are cheap;
- an epoch is 8 batches, each a random anchor song plus its 7 tempo- and gain-matched nearest train songs;
- an own L2 logistic regression, because the body environment has no sklearn. The overseer will ask for a test against scipy's optimiser.

Recommend: record all three.
