# Chunk joining rules (WO44, BRAIN_SPEC 7.73 parallel task) — written before any result

Question: in E1/T2, power above 3 Hz at the lamp (realised stage) relative to continuous human motion was 2.0x (retrieval control), 2.5x (random
chunks), 1.4x (model). The controls concatenate raw human chunks with no decoder. Does a joining method exist under which re-joined human chunks
reach human-level high-frequency power? Report only; no verdict, no training (the frozen vocabulary and decoder `t1a2/runB/best.pt` are untouched),
no clips, no viewing. One arm. Cores 14-19.

## 1. Facts about the existing chain (read from code)

- A token is 50 rows (0.5 s at 100 Hz). Dance = tokens 20..139 (60 s, 6001 rows). Commanded rows = pchip(posture knots) + decoded gesture
  (`t1b_t2.decode_rows`). Posture knots = `post0` + cumulative quantised posture deltas of the tokens.
- The decoder (`SplineDecoder`) takes a window of 40 tokens (2000 rows), reaches at most 24 rows (< half a token) across token borders, and zero-pads
  at the window edges. E1 decodes a dance as three independent 40-token blocks (tokens 0-39, 40-79, 80-119 of the dance).
- E1 controls: Viterbi over 8 nearest train tokens x 4 copies, raw `rows[:50]` of each chosen chunk concatenated (no decoder).

## 2. Methods (every method outputs commanded rows (6001, 5) deg from a token sequence or a chunk list)

- **A0, as E1 ran it (raw):** the chosen raw chunks concatenated, no smoothing. For continuous human this is the original rows. Controls only.
- **A1, blocks:** token sequence decoded in three independent 40-token blocks (E1's decoder path, `decode_rows`). Model and rebuilt controls/human.
- **B, overlap:** the whole token sequence decoded in one pass: 40-token windows starting every 20 tokens (starts 0, 20, 40, 60, 80), each 2000-row
  output weighted by a raised-cosine (Hann) window `w(r) = sin^2(pi (r + 0.5) / 2000)`, weights summed and normalised per row; rows covered by only
  one window (the first/last 10 tokens of the sequence) take weight 1. Posture knots exactly as A1 (the posture does not depend on the decoder).
- **C, offset ramp (no training, raw chunks only):** the raw chunks of A0, with each join's position jump `d = first row of chunk i - row 50 of chunk i-1`
  (row 50 is the true continuation of the previous chunk) removed by subtracting `d * 0.5 (1 + cos(pi r / 50))` from chunk i, rows r = 0..49 (the
  offset is exactly zero from row 50, so later joins see uncorrected data). Answers "do the position jumps alone explain the excess".
  Raw chunk rows have no decoder; C does not apply to model tokens.

## 3. Test material

FineDance songs that are `usable` (audio >= 70 s, token files cover tokens 0..139): validation 20, test 17 (37 songs); dance window tokens 20..139.

| id | material | methods |
|---|---|---|
| H | continuous human rows, 4 copies (V1, V1m, V2, V2m) | none (reference) |
| HJ | the same songs cut into the E1 chunk length (tokens) and re-joined in original order: token codes of the human window (c1, c2, vigour bin, posture entries) rebuilt | A1, B (A0 = H, C = H: no jump) |
| RT | retrieval control (E1 settings: `t1b_t2b.chain`, seed 36101; test songs reuse E1's stored picks, validation songs built identically) | A0, A1, B, C |
| RN | random-chunk control (seed 36102, same) | A0, A1, B, C |
| M | E1 seed 41101 model, sample 0 token sequences (`t2/gen`, test songs only; sampled tokens, not rows) | A1, B |

A1/B on controls rebuild the tokens of the picked chunks (code1, code2, vigour bin, posture entry from the `t1b/tokens` file of the chosen
train token and copy) and decode them with the method; posture start = the human window's `post0` of the song (as E1's model). All dances run
through the same realised simulation (`t1b_t2b.sim_full`: guard, spinal, limiter, servo, v2p; 50 Hz `q50`), no pre-roll data (rows[0] repeated) for every
condition including H, so the chain is identical.

## 4. Measures (per song and condition; condition value = mean over the 4 human copies for H and HJ)

1. `p_gt3` at the lamp: share of speed-vector power above 3 Hz of the hand/lamp point (`bdesc.hand_points(q50)`, `v3_lib.pos_measures`, Welch, Hann, 5 s) — **primary**.
2. `p_gt3` per joint (`jitter_diag.all_joints`) and their mean over joints (the overseer's `e1_t2check.py` figure).
3. Hand jerk RMS (`endpoint_jerk_dirchanges`), frozen-pose share (share of frames with hand speed < 0.05 m/s), commanded vs realised RMS (E1's `cmd_vs_real_rms`, mean over joints).
4. Decode/join compute time per minute of motion (wall-clock of rows construction on one core, torch threads 1, median over songs; realised simulation not included).

## 5. Target, fixed before computing

Per song ratio `r = p_gt3(condition) / p_gt3(H)`, H = mean over the song's 4 copies. Human level = the condition's across-song **mean lamp `p_gt3`
lies inside the interval [P10, P90] of the per-song continuous-human lamp `p_gt3` (mean over copies) over the 37 songs** (np.percentile, linear). Equivalent
ratio statements are reported next to it. Also reported: bootstrap by song (2,000 resamples of songs, seed 44001) 95 % interval of the mean ratio, the
same rule for the mean of per-joint `p_gt3`, and per-material medians. A method "meets the target" for a material if the interval rule holds for the lamp.
Songs are not dropped; the test-only M rows use the 17 test songs and the interval from those 17 H values (stated alongside the 37-song one).

## 6. Tests (`scripts/body/test_join.py`)

1. Raw rows cut at one point and re-joined (A0 and C): identical to the original everywhere (jump is zero, ramp adds nothing).
2. Decoded sequence cut into two token halves and joined by B overlap on a shared range equals the one-pass B decode away from the join, and B equals A1 further
   than 30 rows from every 40-token block border and from the sequence ends (the decoder reach is 24 rows).
3. A constant token sequence decoded by B gives gesture speed power above 3 Hz no larger than the same sequence decoded by A1 (1 % tolerance).
4. A1 reproduces `t1b_t2.decode_rows` exactly; C on a continuous-with-jump toy removes the jump (value at join equals the continuation).

## 7. Outputs

`/secondary/hyst-data/body/join/` : `rows/<song>.npz` (commanded rows per condition/method), `q50/<song>.npz`, `measures.json` (per-song per-condition values).
`docs/JOIN_REPORT.md`: ratios per method and material, intervals, which methods meet the target, compute cost. Night log `docs/NIGHT_LOG_body-join.md`.
Defaults taken, open choices for the overseer are logged "FOR USER" in the night log.
