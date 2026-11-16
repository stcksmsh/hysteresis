# Posture-vs-gesture diagnostic rules (WO46 part 1, BRAIN_SPEC 7.74 Q4) — written before any result

Question: in the WO44 material, how much of the lamp power above 3 Hz and of the frozen-pose share comes from the posture knots, and how much
from the gesture codes? Report only; no training, no verdict. One arm. Frozen decoder A1 (`t1a2/runB/best.pt`, three independent 40-token
blocks, `join_lib.build_rows(..., "blocks")`), realised stage (`t1b_t2b.sim_full`), no pre-roll, same chain as WO44 (`docs/JOIN_RULES.md`).

## Material

The 37 usable FineDance songs of WO44 (20 validation, 17 test), 60 s dances = tokens 20..139 (120 tokens of 50 rows). Token = (c1, c2, v, p):
gesture codes = (c1, c2, v), posture = p (quantised posture deltas; posture knots = `post0` + cumsum of the deltas; commanded rows = pchip
through the knots + decoded gesture).

## Conditions (per song)

| id | gesture codes | posture knots |
|---|---|---|
| H | continuous human rows (reference, mean of the 4 copies V1, V1m, V2, V2m) | - |
| HJ | human (rebuilt tokens, A1) | human |
| RT, RN | retrieval / random-chunk control, as WO44 (A1) | control |
| RT-hp, RN-hp (i) | control | **human** |
| RT-hg, RN-hg (ii) | **human** | control |
| M, M-hp, M-hg | E1 seed 41101 sample 0 tokens, same three variants (test songs only, 17) | as above |

Human tokens = V1 copy's window tokens (`T2.human_window(key)["V1"]["tok"]`); the swaps use V1 only (controls and model are V1). `post0` =
the human window's `post0` for every condition (as WO44). The HJ row is the mean over the four copies as in WO44 (reported for reference);
the comparison row for swaps is HJ V1 as well (stated alongside).

**Time alignment of a swap:** both sequences have 120 tokens of the same song and window; token slot i of the control (picked or generated for
the music of slot i) is paired with token slot i of the human (the same 0.5 s of the same song). No resampling, no shift. The swap exchanges the
fields `p` (posture entries) versus `c1, c2, v` (gesture) token by token; the posture knots are then rebuilt from the exchanged `p` with the
same `post0` exactly as `build_rows` does.

## Measures (as WO44, section 4)

Per song and condition: lamp `p_gt3` (primary), joint-mean `p_gt3`, frozen share (hand speed < 0.05 m/s). Per-song ratio to continuous human
`r = p_gt3(condition)/p_gt3(H)`; reported: mean of per-song ratios with a 95 % song bootstrap (2,000 resamples, seed 46001) and the ratio of
means; same for joint-mean `p_gt3` and for frozen share (difference to H). Medians alongside. Test-only rows (M) use the 17 test songs; the
other rows are also given for those 17 for comparison.

## Reading rule (fixed now)

No threshold and no verdict. The tables answer: with human posture, does a control's excess fall towards HJ (then it sits in posture knots), and
with human gestures does it stay at the control's level (then it sits in gesture codes), and vice versa. Both directions are shown side by side.

## Tests

`scripts/body/test_diag.py`: swapping a token sequence with itself changes nothing; swap (i) then (ii) of two sequences are complementary
(posture of one, gesture of the other, exact field equality); HJ rebuilt by the diag path equals WO44's A1 rows exactly for one song.

## Outputs

`/secondary/hyst-data/body/diag/{rows,q50}/<song>.npz`, `measures.json`; `docs/DIAG_REPORT.md`; night log `docs/NIGHT_LOG_body-diag.md`.
