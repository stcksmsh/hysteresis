# Pulse v2 report (WO51, BRAIN_SPEC 7.80 Q1)

Rules: `docs/PULSE2_RULES.md` (pushed in `0e79aef` before any song was run). Code `scripts/body/pulse2_lib.py`, `pulse2_run.py`,
`pulse2_view.py`, `pulse2_score.py`; tests `test_pulse2.py` (13), `test_pulse2_score.py` (1), all pass, as do v1's `test_pulse.py` (6) and
`test_dialstudy_wo48.py` (1). Full tables: `docs/PULSE2_TABLES.md`. Report only; no verdict, no motor clock, no event detector.

## Run

- 1,341 songs (the v1 set), whole songs, causal, one pass each, unit `hyst-wo51-run1` (cores 14-19, 6 processes), **0 failures**.
- Per song: `/secondary/hyst-data/body/pulse2/songs/<key>.npz` (100 Hz: period, rate, phase, conf, freq, sel, amp, prom, coh, novelty; events,
  event_conf, boundaries, switches, f_max, rms) and `<key>.json` (all check values, events with their confidence). Aggregates `pulse2/summary.json`.
- Summaries use the 1,270 songs of at least 12 s (71 shorter songs left out, 7.79 Q4); v1 is recomputed on the same set.

## Headline, v1 vs v2 (all songs >= 12 s)

| measure | v1 | v2 |
|---|---|---|
| level switches per minute, median / q90 | 1.87 / 4.14 | 1.25 / 2.56 |
| share of switches made near a novelty boundary | n/a | 0.10 |
| share of frames with rate within 6 % of the song's median rate (median) | 0.73 | 0.80 |
| **3:2 share** (whole-song level 2/3 or 3/2 vs librosa) | 0.327 | 0.257 |
| of which 2/3 / 3/2 | 0.185 / 0.142 | 0.172 / 0.086 |
| same level as librosa (1) | 0.651 | 0.711 |
| 1/2 or 2 of librosa | 0.021 | 0.031 |
| 3:2 share vs the project grid | 0.269 | 0.243 |
| pulse BPM q5 / q50 / q95 | 80.0 / 116.2 / 142.4 | 80.1 / 113.7 / 138.9 |
| longest gap in own IOIs, median / q90 | 2.23 / 6.11 | 2.04 / 6.49 |
| regularity (8-event line residual) ms, median | 2.1 | 2.2 |
| quiet passages kept / grid dropouts kept | 0.862 / 0.934 | 0.902 / 0.946 |
| octave-folded deviation from librosa's local tempo, median % | 9.0 | 1.3 |

Per dataset (table 1 of `PULSE2_TABLES.md`): switches fall on every dataset (FineDance 1.37 -> 0.60, AIOZ 2.40 -> 1.76, Phantom 1.27 -> 0.61,
Motorica 1.04 -> 0.56 per minute); the 3:2 share falls on every dataset (FineDance 0.345 -> 0.271, AIOZ 0.318 -> 0.236, Phantom 0.296 -> 0.273,
Motorica 0.473 -> 0.378). The fall in 3:2 comes mostly from 3/2 (pulse faster than librosa: 0.142 -> 0.086); 2/3 barely moves (0.185 -> 0.172).
The folded-deviation drop (9.0 % -> 1.3 %) means that where v2 sits at some simple ratio of librosa's tempo it is much closer to that exact ratio.

## Confidence by passage type (v2)

Passage rules: rules section 6 (silence = v1 quiet passages, dropout = v1 grid dropouts, beatless = low-band periodicity < 0.3 for >= 4 s,
beat = periodicity >= 0.5 and none of the others; from 10 s on).

| type | songs | seconds | median confidence (median over songs) | q25 / q75 | share of frames < 0.5 | paired beat minus type (songs with both) |
|---|---|---|---|---|---|---|
| beat | 357 | 4,864 | 0.376 | 0.202 / 0.561 | 0.729 | n/a |
| silence | 330 | 3,151 | 0.132 | 0.078 / 0.222 | 1.000 | +0.155 (103) |
| beatless | 743 | 24,048 | 0.176 | 0.116 / 0.272 | 0.990 | +0.130 (201) |
| dropout | 916 | 22,879 | 0.170 | 0.105 / 0.256 | 1.000 | +0.107 (256) |

- Confidence is lower in silence, beatless and dropout passages than in beat passages within the same songs (paired medians +0.11 to +0.16;
  Motorica beatless is the exception, -0.05 over 8 songs).
- **Confidence is low overall on real songs:** per-song median confidence 0.20 (q25 0.13, q75 0.30); even beat passages have a median of 0.38.
  The limiting factor is the drive term: its per-song median is 0.36 (the coherent drive on real songs is about 0.2 of the long-term drive,
  against 0.53-0.75 on the synthetic backbeat the constant 0.6 was set on); the prominence term's per-song median is 0.70. Nothing was changed.
- The "beat" label (periodicity >= 0.5 on 6 s of 30-200 Hz flux) is strict on real music: only 357 of 1,270 songs have any beat second.

## The 20 viewing excerpts (tempo / librosa tempo inside the 30 s window)

| check | song | v1 ratio (level) | v2 ratio (level) | v2 median confidence | v2 switches |
|---|---|---|---|---|---|
| flash | fd_053 | 0.989 (1) | 0.989 (1) | 0.34 | 0 |
| flash | aioz_8JQ0 | 0.917 (1) | 0.891 (1) | 0.12 | 0 |
| flash | fd_183 | 0.880 (1) | 0.880 (1) | 0.09 | 0 |
| flash | fd_018 | 0.612 (2/3) | 0.612 (2/3) | 0.15 | 0 |
| flash | ph_137 | 0.978 (1) | 0.978 (1) | 0.26 | 0 |
| flash | ph_084 | 1.000 (1) | 1.000 (1) | 0.26 | 0 |
| flash | ph_102 | 0.970 (1) | 0.970 (1) | 0.09 | 0 |
| flash | Motorica jazz | 1.024 (1) | 1.020 (1) | 0.14 | 1 |
| flash | Motorica street (yougonnaregretit) | 1.016 (1) | 1.016 (1) | 0.14 | 0 |
| flash | aioz_SZhU | 0.750 (2/3) | 0.755 (2/3) | 0.25 | 0 |
| flash2 | aioz_8JQ0 | 0.936 (1) | 0.974 (1) | 0.18 | 0 |
| flash2 | aioz_SZhU | 0.502 (1/2) | 0.755 (2/3) | 0.14 | 1 |
| flash2 | ph_157 | 1.249 (3/2) | 1.249 (3/2) | 0.67 | 0 |
| flash2 | ph_224 | 0.764 (2/3) | 0.764 (2/3) | 0.19 | 0 |
| flash2 | mo_gPO funk | 1.229 (3/2) | 1.001 (1) | 0.21 | 1 |
| flash2 | fd_034 | 0.631 (2/3) | 0.507 (1/2) | 0.10 | 0 |
| flash2 | mo_gLH (mLH6) | 0.701 (2/3) | 0.567 (1/2) | 0.18 | 0 |
| flash2 | aioz_ULrc | 1.516 (3/2) | 1.515 (3/2) | 0.16 | 1 |
| flash2 | aioz_iOoW | 0.625 (2/3) | 0.988 (1) | 0.20 | 0 |
| flash2 | fd_100 | 1.230 (3/2) | 1.230 (3/2) | 0.47 | 0 |

- 15 of 20 excerpts have the same tempo as v1 (within 1 %); 5 change: mo_gPO funk 3/2 -> 1, aioz_iOoW 2/3 -> 1, aioz_SZhU (flash2) 1/2 -> 2/3,
  fd_034 and mo_gLH 2/3 -> about 1/2.
- Three of the four 3/2 excerpts Kosta judged too fast (fd_100 was judged right but "too fast" in its note) keep their v1 ratio
  (ph_157, aioz_ULrc, fd_100 at 1.23-1.52); only mo_gPO funk moves to librosa's level.
- Median confidence inside the excerpts is 0.09-0.67 (median about 0.18): most pulse v2 flashes will show near the 0.15 floor.

## What the numbers say (no verdict)

1. Fewer level switches (median 1.87 -> 1.25 per minute) and a steadier rate (share within 6 %: 0.73 -> 0.80).
2. The 3:2 share falls from 33 % to 26 %, mostly from fewer 3/2 (too fast) songs; about a quarter of songs still sit at 2/3 or 3/2 of both trackers.
3. Confidence separates beat passages from silence, beatless and dropout passages within songs, but its level on real songs is low, so the
   viewing material's pulse v2 flashes are mostly dim. This is a consequence of the drive-term constant set on synthetic signals, reported
   here, not tuned.

## FOR USER

- All defaults of `PULSE2_RULES.md` (listed there), in particular the confidence = prominence x coherent drive in place of the default
  normalisation, and the bank extended to 0.25-8 Hz for the readout.
- Confidence on real songs is low (per-song median 0.20; beat passages 0.38) because COH_FULL = 0.6 was set on synthetic beats; in the viewing
  material most pulse v2 flashes will be dim (brightness 0.15 + 0.85 x confidence). A different constant would be a rule change for the planner.
- Synthetic finding (rules section 3): a strong low-band 3-stream over a 2 Hz kick makes v2 read 1.5 Hz where v1 reads 2 Hz.
