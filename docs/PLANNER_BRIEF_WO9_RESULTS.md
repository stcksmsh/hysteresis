# Planner brief: work order 9 results, and the K5 launch (2026-11-05, evening)

Answers `docs/BRAIN_SPEC.md` §7.20. Numbers marked (R) were recomputed or re-read by the overseer from the saved files. One arm; argmax for
every pass/fail.

## 1. 60 s cerebellum check (7.20 point 4): no state drift; not a stop (R)

Frozen K1 round-2 cerebellum (JAX port) run continuously over 60 s.
- **Closed loop, 16 held-out toy episodes, try 1 policy:** squared error per 5 s bin 0.0536 (start-up from zero state), then 0.0054 for 5–25 s,
  then 0.0070–0.0113 after about 25 s, while the arm's RMS speed stays flat. The pre-stated rule (slope, or last 10 s vs first 10 s) says no
  growth, but its first-10 s baseline contains the start-up bin; the builder flagged the step up and stopped to check.
- **Same run, state reset every 200 steps:** late vs early +10 % (continuous +60 %), but the reset level is about 4× higher and the trajectories
  differ (the policy sees the cerebellum), so this alone was not conclusive.
- **Open loop on the cerebellum's own distribution (32 held-out babble trajectories × 60 s), continuous vs reset, the first 20 steps of each
  200-step window excluded from both:** continuous 0.0051–0.0054 in every bin, flat, and below the reset run in every bin; late − early
  +2e-5 [−6e-5, 1e-4]. So no state drift. The closed-loop rise is consistent with the trained policy's movements leaving the babble
  distribution the cerebellum was trained on.
- v47 open loop: one trajectory flat after 30 s; the rough one noisy, worst late, not monotone.

## 2. Ablations (7.20 point 2): no mechanism is credited (R)

One retraining each from scratch, as try 1 (λ 0.03, lr 1e-3, 40 epochs, seed 0), 16 held-out episodes, WO7 observer procedure per decoder.
Rule, written before the runs: credited = paired (a)_try1 − (a)_ablation interval above 0, external, argmax. Try 1: external 0.991,
internal 0.951 (argmax). Tests 15 OK (rerun by the overseer at 7430377: 15 OK), including "defaults reproduce try 1" to 1e-9.

| Ablation | external (a) argmax | internal (a) argmax | paired try1 − ablation, external, argmax | internal, argmax |
|---|---|---|---|---|
| A1 closed-loop inputs off | 0.894 | 0.738 | 0.097 [−0.037, 0.235] | **0.213 [0.076, 0.356]** |
| A2 dopamine gating off | 1.077 | 1.035 | −0.086 [−0.210, 0.046] | −0.085 [−0.168, −0.003] |
| A3 internal observer out of the loss | 0.879 | 0.671 | 0.112 [−0.017, 0.255] | **0.279 [0.160, 0.407]** |

Sampled (reported only), external: A1 0.090 [0.005, 0.179], A2 −0.086 [−0.199, 0.038], A3 0.160 [0.066, 0.262].

- By the rule, none is credited: closed-loop inputs, dopamine gating and the internal observer are all "present" (7.20 point 2).
- The internal decoding drops, with intervals above 0, when the closed-loop inputs are off or the internal observer leaves the loss.
- Without dopamine gating both decodings are higher (point estimates); internal argmax difference −0.085 [−0.168, −0.003].
- Builder's caveat: one training run and one seed per arm; the paired interval covers the 16 evaluation episodes, not run-to-run training
  variation, so differences of this size may be seed noise (no second seed of try 1 was run).

## 3. K5 path and launch (7.20 point 1)

Speed check (R, from the saved result files), M3e's recipe, 16 windows per round: laptop CPU 6 threads 61.1 s per round (one pass + validation
+ check ≈ 17.4 h, inside the 24 h box); Kaggle T4 free tier 452 s per round (≈ 124 h, 7.4× slower: float64 and a batch too small for the GPU).
At 256 windows per step the T4 reaches about 2.4× the laptop's throughput, but that changes training (fewer, larger steps), so it is not used.
Path: the laptop. Try 1 is being launched on the user's go (the pause/stop tests were still running when this brief was written), with the user's requirement that it can be paused or stopped at any moment and resumed
without loss (checkpoint after every round, atomic; tested bit-identical). Early stopping: validation on the 217 validation windows every
200 rounds, stop after two non-improving validations in a row; K5 scores `best.pkl`.

## Questions

1. **Ablation wording.** No mechanism passes the credit rule, so the monitor and story name none of them as "used to". The internal decoding
   does depend on the closed-loop inputs and on the internal observer being in the loss.
   - (a) Keep the rule as written: all three "present", nothing more.
   - (b) Allow mechanism credit for the internal decoding only ("its own reading of its body depends on its sense of its joints"), since
     that is what the internal decoding measures.
   - Recommendation: (a) for now; (b) only after a second seed of try 1 and of A1/A3 shows the same sign (the single-seed caveat).
2. **Dopamine.** Gating off gives slightly better decoding (one seed). Keep it ("present", as built), or remove it from the machine?
   Recommendation: keep it as present (7.20 point 2 keeps mechanisms that do not measurably matter); revisit with a second seed.
3. **Seed variation.** Should a second seed of try 1 and the three ablations run on the laptop after K5 (about 7 h), so wording rests on
   more than one training run? Recommendation: yes, after K5, not before.
4. **Try 2 recipe (only if K5 try 1 fails).** A large-batch Kaggle GPU recipe (256 windows per step) is about 2.4× faster than the laptop but
   changes training. Allow it for a try 2, or keep M3e's recipe on the laptop? Recommendation: keep the recipe; decide only if try 1 fails.
