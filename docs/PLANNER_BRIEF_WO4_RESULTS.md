# Planner brief: work order 4 results, and a correction to the WO2 brief (2026-11-04, late)

Branch `body` at 10c7fd7 (merges of `body-h3`, `body-m3c`, `body-m3b`). Tests rerun by the overseer: scripts/brain 182 OK (1 cuda skip);
M3c's test_bdesc 4 and test_tm3c 11 OK; H3's test_h3 6 OK. Numbers marked (R) recomputed from the saved files. The laptop was powered off
from 19:36 to 23:05 (a normal shutdown with the lid closed, not a crash). The fallback order had produced nothing by then and was re-sent at
23:20; it is running now.

## 1. Correction: the "selection collapse" in T-M3, M3b and M3c is most likely an evaluation artefact

`tm3.py` `evaluate()` runs the policy with `deterministic=True`, so the program is `logits.argmax()`, with no sampling. Training samples from
the softmax. T-M3's training log shows about 90 switches a minute and a selection entropy of about 1.5 nats, close to uniform over 8 programs
(ln 8 = 2.08). In evaluation the argmax of nearly flat logits picks the same program almost every time. Evidence (R):
- the counts are identical, 8 and 1,432 of 1,440 decisions, in T-M3 try 1, T-M3 try 2, M3c try 1 and M3c try 2, under different rewards and with
  and without an entropy bonus;
- M3c's random-policy diagnostic gives 1,440 of 1,440 on one program.

So (d) and the "2 programs, entropy 0.034 nats" lines in the WO2 brief describe the argmax, not what the policy does. The overseer reported
"selection collapsed" in the WO2 brief and did not catch this when verifying. (a), (b) and (c) were also measured under the argmax policy, not
the sampled one the training optimised. Question 1.

## 2. H3 (blend memory) (R): fails T1b in both tries; the hippocampus stays off

Ratio repeat / first (≤ 0.5), A | B | C: try 1 0.921 | 0.681 | 0.520; try 2 0.921 | 0.699 | 0.552. Cortex only (w = 0): 0.881 | 0.656 | 0.566.
T1a passes on all three designs in both tries (source share 0.812 | 0.830 | 0.955). Oracle 0.327 | 0.440 | 0.348. Try 2's change (learning
rate, steps, initial b) was committed before its runs. Variance blend, fixed before run 1: var = (1 − w)·var_c + w·0.05 + w(1 − w)(μ_c − replay)².
The blend is worse than the cortex alone on A and B. Builder's reading (not tested): the toy cortex alone already reaches 0.57–0.88, and on A
recognition barely separates repeat from non-repeat (0.853 against 0.808). kNN-LM citation (Khandelwal et al., ICLR 2020, arXiv 1911.00172):
not verified.

## 3. M3c (legibility reward) (R): fails (a) in both tries

- Descriptors ported to Python: 31 of 37 (the roll's 6 excluded); parity with Rust on 3 clips, max relative difference 2.6e-8.
- Observer: MLP 31 → 64 → 64 → 8 (try 2: 16 hidden).
- Grid, 24 runs: no (a) interval above 0. Chosen λ 1, β 0.1, entropy 0.01, c_sw 0.
- Try 1: (a) +0.0005 [−0.0010, +0.0019] fail; (b) 28.3 °/s pass; (c) fail (argmax, see section 1); κ never used.
- Try 2 (observer width 16): (a) −0.0003 [−0.0018, +0.0011] fail; (b) 28.1 °/s pass.
- Random-movement diagnostic: (a) +0.0005 [−0.0026, +0.0037]. The observer does not beat the shuffled control even before any learning. It
  memorises training episodes (training loss 0.43 against 1.04 on fresh episodes).
- Builder's reading (not tested): in the toy the brain state is a slow function of the synthetic song; the movement descriptors do not carry it
  across songs; the reward as defined pays for episode identity.

## Questions

1. **Re-evaluation with sampled selection.** The saved T-M3 and M3c policies can be evaluated again with the program sampled (as trained), with no
   retraining and nothing tuned. Is that a measurement fix (allowed, both rounds stand as they are), or does it need a new pre-registration?
   Recommendation: allow it as a fix of the evaluation; report both versions; no pass is claimed from it without your ruling.
2. **M3c's reward.** The diagnostic suggests the observer has nothing to learn across songs in this toy. A redesign would change the reward
   definition (for example, an observer scored on held-out episodes inside the reward). Close M3c, or redesign? Recommendation: decide after
   question 1's numbers.
3. **H3.** Close the hippocampus for this plan (H1, H2, H3 all failed T1b while T1a passes), or rule on the toy's room under the bar (the cortex
   alone at 0.57–0.88)? Recommendation: close it.
