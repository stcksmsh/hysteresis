# Chunk joining report (WO44, BRAIN_SPEC 7.73 parallel task)

Rules: `docs/JOIN_RULES.md` (pushed before results; test 2 wording simplified before any result, methods unchanged). 37 songs (20 validation, 17 test), 60 s dances,
realised stage, every condition through the same simulation (no pre-roll data, also for human). Code `scripts/body/join_{lib,run,report}.py`, tests `test_join.py` (5 pass).
Per-song values: `/secondary/hyst-data/body/join/measures.json`, `summary.json`; tables regenerate with `join_report.py` (`docs/JOIN_TABLES.md`).
Target (fixed beforehand): the condition's across-song mean lamp `p_gt3` lies inside [P10, P90] of the per-song continuous-human lamp `p_gt3`.
"Ratio of means" is the E1 statistic; it reproduces E1 (A0 raw: retrieval 2.03, random 2.59, model A1 1.37 per-joint; lamp 2.03 / 2.51 / 2.50).

Human interval (lamp p_gt3, P10-P90 / mean), 37 songs: 0.0008-0.0035 / 0.0020; 17 test songs: 0.0008-0.0036 / 0.0022 (used for the model rows).

| material / method | n | lamp p_gt3 mean | ratio to H, mean [95 % boot by song] | ratio median | ratio of means, lamp / joint-mean | in interval | joint-mean ratio (mean of per-song) | hand jerk ratio | frozen share | cmd-vs-real RMS (deg) | decode s per 60 s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| continuous human | 37 | 0.0020 | 1.00 | 1.00 | 1.00 / 1.00 | yes | 1.00 | 1.00 | 0.095 | 16.72 | - |
| human re-joined, A1 blocks | 37 | 0.0016 | 0.88 [0.81, 0.97] | 0.82 | 0.79 / 0.62 | yes | 0.71 | 0.90 | 0.100 | 14.59 | - |
| human re-joined, B overlap | 37 | 0.0015 | 0.86 [0.79, 0.94] | 0.81 | 0.77 / 0.59 | yes | 0.68 | 0.89 | 0.100 | 14.61 | - |
| retrieval, A0 raw (as E1) | 37 | 0.0041 | 2.51 [2.10, 2.97] | 2.26 | 2.03 / 2.03 | no | 2.55 | 1.56 | 0.107 | 20.35 | - |
| retrieval, C offset ramp | 37 | 0.0026 | 1.43 [1.24, 1.63] | 1.39 | 1.30 / 1.29 | yes | 1.50 | 1.30 | 0.108 | 18.24 | 0.00 |
| retrieval, A1 blocks | 37 | 0.0058 | 3.65 [2.37, 5.47] | 1.71 | 2.91 / 2.58 | no | 3.31 | 0.95 | 0.254 | 16.63 | 0.01 |
| retrieval, B overlap | 37 | 0.0041 | 2.88 [2.16, 3.71] | 1.57 | 2.02 / 1.46 | no | 1.94 | 0.95 | 0.254 | 16.65 | 0.01 |
| random chunks, A0 raw (as E1) | 37 | 0.0050 | 3.50 [2.79, 4.31] | 2.49 | 2.51 / 2.59 | no | 3.48 | 2.00 | 0.023 | 17.39 | - |
| random chunks, C offset ramp | 37 | 0.0027 | 1.91 [1.52, 2.36] | 1.36 | 1.37 / 1.16 | yes | 1.55 | 1.55 | 0.023 | 14.76 | 0.00 |
| random chunks, A1 blocks | 37 | 0.0067 | 4.47 [3.66, 5.40] | 3.69 | 3.36 / 1.89 | no | 2.49 | 1.32 | 0.224 | 14.32 | 0.01 |
| random chunks, B overlap | 37 | 0.0067 | 4.44 [3.63, 5.36] | 3.62 | 3.34 / 1.88 | no | 2.48 | 1.31 | 0.225 | 14.38 | 0.01 |
| model seed 41101, A1 blocks (as E1) | 17 | 0.0055 | 4.43 [2.12, 7.87] | 2.47 | 2.50 / 1.37 | no | 2.24 | 0.82 | 0.166 | 18.87 | 0.01 |
| model seed 41101, B overlap | 17 | 0.0053 | 4.35 [2.05, 7.82] | 2.46 | 2.44 / 1.33 | no | 2.18 | 0.82 | 0.166 | 18.88 | 0.01 |

Which meet the target (lamp, interval rule): human re-joined with A1 and with B; controls with C (raw chunks + offset ramp). Not met: raw A0 controls (as E1), every decoded
control (A1, B), the model (A1, B).

## Findings (numbers above; no verdict)

1. **Human chunks re-joined through the decoder are at human level** (lamp ratio 0.88 A1, 0.86 B; ratio of means 0.79 / 0.77). Decoder and vocabulary add no high-frequency power by themselves.
2. **Overlap decoding (B) matches blocks (A1) on human and model** (0.86 vs 0.88; model 2.44 vs 2.50 ratio of means; tests: identical away from window edges, decoder reach 24 rows).
   It lowers decoded retrieval (ratio of means 2.91 → 2.02) but not decoded random chunks (3.36 → 3.34). Neither reaches the interval for controls or model.
3. **Raw joins explain most of the raw control excess.** C (jump removed over 0.5 s, no training) takes retrieval 2.03 → 1.30 and random 2.51 → 1.37 (ratio of means, lamp), inside the interval
   (mean-of-ratios 1.43 / 1.91).
4. **Decoded controls and the model stay high at the lamp (ratio of means 2.0-3.4, model 2.4-2.5), while per-joint model is 1.3-1.4.** Frozen-pose share is 0.17-0.25 for decoded
   controls/model against 0.095 for human. The excess is therefore not in the joins but in token sequences that do not form one human movement (decoded gesture plus posture-knot sequences),
   seen mostly at the lamp (FK sum of the joints). A joining method does not remove it; this analysis does not separate posture-knot from gesture contributions.
5. Compute: building one 60 s dance from tokens, one core, torch 1 thread: about 0.01 s (median over songs; B uses 5 windows, A1 3); C and A0 negligible. The realised simulation (about 4 s per
   60 s) dominates and is not part of joining.

## Open / FOR USER

- Interval = P10-P90 of 37 per-song human values on the mean; a narrower or per-song criterion changes which rows count as meeting.
- The model's lamp ratio of means (2.4-2.5) is higher than the per-joint 1.4x quoted for E1; both are in the table.
- C exists only for raw chunks; there is no analogue on model tokens (a posture-knot smoothing of token sequences would be a different untrained method, not built).
- Decoded-control rebuild uses the picked chunk's quantised posture deltas from the song's `post0`, as the model path does; a different posture rule was not tried.
