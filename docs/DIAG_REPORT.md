# Posture-vs-gesture diagnostic report (WO46 part 1, BRAIN_SPEC 7.74 Q4)

Rules: `docs/DIAG_RULES.md` (pushed before any result). 37 songs (20 validation, 17 test), 60 s dances, decoder A1, realised stage, no pre-roll. Code
`scripts/body/diag_{lib,run,report}.py`, tests `test_diag.py` (4 pass). Per-song values: `/secondary/hyst-data/body/diag/measures.json`; summary `summary.json`;
full tables (37 and 17 songs) `docs/DIAG_TABLES.md`. Ratio = per-song lamp `p_gt3` over the continuous human of the same song (4-copy mean); bootstrap by song, 2,000 resamples, seed 46001.
Swap (i) = control gesture codes with HUMAN posture knots; swap (ii) = HUMAN gesture codes with the control's posture knots; token slot i paired with token slot i of the human (same 0.5 s of the same song).

All 37 songs (model rows: the 17 test songs; their own comparison is in `DIAG_TABLES.md`):

| condition | n | lamp ratio mean [95 % boot] | median | ratio of means | joint-mean ratio | frozen share (H 0.095) |
|---|---|---|---|---|---|---|
| human re-joined A1 (4-copy mean) | 37 | 0.88 [0.81, 0.97] | 0.82 | 0.79 | 0.71 | 0.100 |
| retrieval A1 | 37 | 3.65 [2.41, 5.49] | 1.71 | 2.91 | 3.31 | 0.254 |
| retrieval gesture + human posture (i) | 37 | 1.46 [1.13, 1.84] | 1.06 | 1.09 | 1.01 | 0.064 |
| human gesture + retrieval posture (ii) | 37 | 2.52 [1.87, 3.22] | 1.75 | 1.90 | 1.51 | 0.161 |
| random A1 | 37 | 4.47 [3.68, 5.36] | 3.69 | 3.36 | 2.49 | 0.224 |
| random gesture + human posture (i) | 37 | 1.99 [1.54, 2.49] | 1.51 | 1.43 | 1.18 | 0.033 |
| human gesture + random posture (ii) | 37 | 2.93 [2.41, 3.48] | 2.49 | 2.29 | 2.05 | 0.164 |
| model 41101 A1 (17 test songs) | 17 | 4.43 [2.21, 7.95] | 2.47 | 2.50 | 2.24 | 0.166 |
| model gesture + human posture (i) | 17 | 1.71 [1.20, 2.34] | 1.38 | 1.24 | 1.18 | 0.030 |
| human gesture + model posture (ii) | 17 | 2.35 [1.40, 3.66] | 1.61 | 1.62 | 1.38 | 0.149 |

## Findings (numbers above; no verdict)

1. **Human posture knots remove most of the excess.** With human posture the lamp ratio of retrieval falls 3.65 → 1.46 (ratio of means 2.91 → 1.09), random 4.47 → 1.99 (3.36 → 1.43), model 4.43 → 1.71 (2.50 → 1.24); the joint-mean ratio goes to 1.0-1.2. Frozen share falls to 0.03-0.06, below the human 0.095.
2. **Human gestures with the control's posture keep a large part of the excess**: retrieval 2.52, random 2.93, model 2.35 (ratio of means 1.9 / 2.3 / 1.6); frozen share 0.15-0.16 (human 0.095). So the posture-knot sequence of a control or model carries the larger share of the lamp power above 3 Hz and of the frozen-pose share; the gesture codes carry a smaller one (ratio 1.0-2.0 with human posture; random chunks 1.99 [1.54, 2.49] does not reach 1).
3. Each stream alone restores part of the way (both swap directions land between the control and the human), so the excess is partly an interaction of the two token streams; the split is not decomposed further here.
4. Medians are well below means (retrieval 1.71 vs 3.65): a few songs carry a large excess; the model's interval is wide (17 songs).
5. Consistent with WO44's finding that the excess is in token sequences that do not form one movement; this adds that most of it sits in the **posture-knot** sequence.

## Limits

- Mirror copies are not used by the swaps (V1 only, as the WO44 controls). The model rows use the 17 test songs only. The human re-joined V1 row (0.97) is next to the 4-copy mean (0.88) in `DIAG_TABLES.md`.
- "Posture" here = the quantised posture-delta entries `p` of the token with `post0` fixed to the human's; swapping changes the whole knot path, not just local values.
- A swapped sequence is decoded exactly like a normal one (A1, three 40-token blocks); no other smoothing was added.
