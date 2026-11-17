# Internal pulse report (WO48, BRAIN_SPEC 7.78 2.1)

Rules: `docs/PULSE_RULES.md` (pushed in `daf0ec3` before any song was run). Code `scripts/body/pulse_lib.py`, `pulse_run.py`, `pulse_flash.py`;
tests `test_pulse.py` (6) and `test_dialstudy_wo48.py` (1), all pass, as do the older dialstudy tests (8 in total). Full tables: `docs/PULSE_TABLES.md`.
Report only; no verdict, no motor clock, no coupling, no A or B change.

## Run

- Inputs scanned first: 1,341 songs (FineDance 203, AIOZ 804, PhantomDance 260, Motorica 74), audio, librosa beats and project grid present
  for all, 0 bad (`pulse/scan.json`). Whole songs, causal, one pass each. **0 failures.**
- Per song: `/secondary/hyst-data/body/pulse/songs/<key>.npz` (100 Hz: rate, phase, amp, sel, freq, plus events, f_max, frame RMS) and
  `<key>.json` (events and every per-item check value of rules section 5; for the 10 V4 songs also the excerpt values and the judged level).
  Deviation from the rules' file naming: the per-item check values are in `songs/<key>.json`, not a separate `check/` folder. Aggregates:
  `pulse/summary.json`.
- Arm limit used for selection: f_max = 2.466 Hz (147.9 BPM), shoulder acceleration binding (A = 5 degree swing).

## Numeric check, the 10 V4 songs (30 s excerpts of `beatv/clicks_visual`)

| song | pulse BPM | librosa | grid | pulse / librosa | Kosta's level | pulse / judged | regularity ms pulse / lib / grid | longest gap in IOIs pulse / lib / grid |
|---|---|---|---|---|---|---|---|---|
| fd_018 | 87.4 | 142.9 | 139.7 | 0.612 | half of librosa (71.5) | 1.22 | 2.4 / 7.5 / 24.7 | 1.01 / 1.19 / 1.54 |
| fd_053 | 134.8 | 136.4 | 129.2 | 0.989 | librosa | 0.99 | 0.5 / 6.6 / 125.6 | 1.00 / 1.09 / 3.38 |
| fd_183 | 110.0 | 125.0 | 110.0 | 0.880 | librosa | 0.88 | 2.1 / 7.5 / 171.5 | 1.19 / 1.08 / 8.40 |
| aioz_8JQ0 | 131.0 | 142.9 | 139.7 | 0.917 | librosa | 0.92 | 2.4 / 5.6 / 11.4 | 2.00 / 1.05 / 5.19 |
| aioz_SZhU | 112.5 | 150.0 | 89.1 | 0.750 | slower than librosa, not stated | n/a | 2.3 / 7.5 / 81.9 | 1.69 / 1.05 / 1.31 |
| ph_084 | 120.0 | 120.0 | 117.5 | 1.000 | librosa | 1.00 | 0.5 / 9.7 / 160.2 | 1.00 / 1.08 / 3.57 |
| ph_102 | 138.6 | 142.9 | 123.0 | 0.971 | librosa | 0.97 | 1.3 / 6.0 / 174.0 | 4.48 / 1.05 / 7.45 |
| ph_137 | 127.6 | 130.4 | 127.6 | 0.978 | librosa | 0.98 | 0.8 / 5.6 / 25.8 | 1.01 / 1.04 / 1.14 |
| Motorica jazz | 113.7 | 111.1 | 114.8 | 1.023 | not stated | n/a | 1.5 / 18.2 / 84.5 | 1.01 / 1.11 / 1.89 |
| Motorica street | 95.2 | 93.7 | 100.3 | 1.016 | librosa | 1.02 | 1.4 / 15.1 / 66.1 | 1.01 / 1.12 / 4.16 |

- **Tempo / level:** at Kosta's judged level within 3 % on 5 of 8 songs with a stated level (fd_053, ph_084, ph_102, ph_137, street); fd_183 0.88 and
  aioz_8JQ0 0.92 (the pulse lags librosa by 8-12 %, inside the same level but not locked to it: whole song, aioz_8JQ0 is 0.976); **fd_018 is at
  87.4 BPM, neither librosa's 143 nor the judged 71.5 (1.22 x judged, about 0.61 x librosa)**. aioz_SZhU: 112.5 in the excerpt (0.75 x librosa),
  75.6 whole song (0.50 x librosa), i.e. slower than librosa as Kosta asked, but switching level within the song.
- **Regularity:** the pulse is the most regular series on every song (median 8-event line residual 0.5-2.4 ms; librosa 5.6-18.2; grid 11-174).
- **Gaps:** in the excerpts the pulse's longest gap is about one IOI on 6 songs; 1.7-2.0 IOIs on two (aioz), 4.5 IOIs (1.94 s) on ph_102. Whole
  songs: longest pulse gaps 0.7-4.5 s (ph_137 4.47 s, ph_084 3.16 s); librosa never exceeds 1.34 IOIs; the grid 1.1-16 IOIs. **The pulse's long
  gaps come from level jumps (no event at the jump frame, phase restarts on another oscillator) and the 1 s rate window, not from dropouts in the
  music.**
- **Persistence (whole songs, 10 songs):** quiet passages 11, kept by pulse / librosa / grid 10 / 7 / 10; grid dropouts 114, kept by pulse /
  librosa 109 / 113 (by construction the grid never keeps its own dropouts). Pulse amplitude at the end of a quiet passage over its start:
  median 0.85-1.43 per song.
- **Stability / following:** jumps 0.23-1.85 per minute; share of frames within 6 % of the song's median rate 0.41-0.99. Octave-folded
  agreement with librosa's local tempo (regular windows): median deviation 0.1-1.2 % on 6 songs, 3.6-24.8 % on 4 (fd_018 24.8, fd_183 14.2,
  jazz 8.0, aioz_8JQ0 5.6). Only Motorica jazz has a varying librosa tempo (correlation -0.13).

## All songs (1,341)

| dataset | pulse BPM q5/50/95 | librosa q5/50/95 | grid q5/50/95 | pulse < 80 BPM | pulse > 150 | pulse longest gap s q50/q90/max | pulse longest gap in IOIs q50/q90 (lib, grid) | regularity ms q50 pulse / lib / grid |
|---|---|---|---|---|---|---|---|---|
| FineDance | 84.9 / 114.8 / 138.1 | 90.9 / 120.0 / 166.7 | 94.9 / 117.5 / 147.7 | 1.0 % | 0 | 1.30 / 2.93 / 6.85 | 2.50 / 6.07 (1.13 / 1.29; 4.31 / 20.0) | 2.0 / 7.6 / 67.1 |
| AIOZ | 60.8 / 112.5 / 142.5 | 93.8 / 125.0 / 150.0 | 92.3 / 117.5 / 136.0 | 11.8 % | 0 | 1.00 / 2.11 / 7.43 | 1.98 / 4.07 | 2.3 / 6.6 / 70.6 |
| PhantomDance | 80.7 / 120.0 / 140.9 | 96.8 / 125.0 / 150.4 | 92.3 / 120.2 / 136.0 | 3.5 % | 0 | 1.84 / 4.61 / 7.98 | 3.72 / 9.45 | 1.8 / 6.2 / 93.5 |
| Motorica | 89.6 / 118.0 / 144.3 | 90.9 / 100.0 / 155.8 | 92.3 / 114.8 / 161.5 | 0 | 0 | 1.33 / 2.04 / 4.36 | 2.48 / 4.61 | 2.1 / 18.3 / 64.4 |
| all | 71.7 / 113.8 / 142.4 | 93.7 / 120.0 / 150.0 | 92.3 / 117.5 / 139.7 | 7.9 % | 0 (impossible above 147.9) | 1.20 / 3.03 / 7.98 | 2.18 / 6.03 (1.10 / 1.26; 3.71 / 13.47) | 2.1 / 6.7 / 72.6 |

- **Level against librosa (whole-song tempo ratio, nearest simple ratio, all songs):** 1 : 64.2 %, 1/2 : 2.1 %, **2/3 : 18.6 %, 3/2 : 14.2 %**,
  others < 0.2 %. Against the grid: 1 : 70.1 %, 2/3 : 13.9 %, 3/2 : 12.5 %. **About a third of songs sit at a 3:2 relation to both trackers**,
  which no metrical reading of a 4/4 song supports (it means a pulse event on every other beat and a half, i.e. off the beat half the time).
  This is the mode-locking of the canonical model at integer ratios (Velasco & Large 2011 section 1.3: responses at 2f/3, 3f/2) combined with the
  prior and the arm limit; it was not seen in the synthetic tests. Octave-folded local agreement with librosa: median 9.9 % deviation, 33 % of
  windows within 4 % (median over songs).
- **Persistence:** quiet passages 580: kept by pulse 86.2 %, librosa 64.7 %, grid 82.6 %; pulse amplitude ratio over a quiet passage median 0.97.
  Grid dropouts 7,149: kept by pulse 93.4 %, librosa 96.9 %.
- **Stability:** level jumps per minute median 1.95 (q90 4.80); share of frames within 6 % of the song's median rate median 0.72 (q10 0.32).
- **Tempo following:** 212 songs have a varying librosa local tempo; correlation of pulse and librosa local tempo median 0.05 (librosa's tight
  tempo prior makes its own local tempo nearly constant, so this is weak evidence either way). The synthetic ramp 100 -> 120 BPM is followed
  with a 4-5 % lag (test 4).

## Flash-check material (prepared, NOT served)

`/secondary/hyst-data/body/pulse/flash/`: Q00..Q19 (20 singles: 10 at pulse events, 10 at librosa beats again), same excerpts and rendering as
`beatv/clicks_visual` (`beatv_clicks_visual.render`, whose audio-flash sync was checked in WO47), ids in seeded random order (48101),
`manifest.json` with two questions per item ("Is the flash on the beat?" yes / partly / no; "Is it the right speed?" right / too fast / too slow),
`key.json` (source per id, flashes per item). `dialstudy_session.py` gained the manifest field `questions` (answers stored as "a|b"), with a test.
Build with `dialstudy_session.py --clips /secondary/hyst-data/body/pulse/flash/manifest.json --out <session dir>`. Motorica items (4 of 20) stay local.

## What the numbers say (no verdict)

1. The pulse is far more regular than both trackers and keeps going through quiet passages and grid dropouts.
2. On 5 of the 8 V4 songs with a stated level it sits at Kosta's level; on fd_018 (the slow-song case) it moves off librosa's fast level but lands at
   87 BPM, not the judged 71.5.
3. Across all songs about a third of pulses are at 2/3 or 3/2 of both trackers' tempo, and long pulse gaps (median 2.2 IOIs per song) come from
   level jumps. Both bear directly on "on the beat?" in the flash check.

## FOR USER

- Defaults of `PULSE_RULES.md`: 73 oscillators (24 per octave); drive weights 1.0 / 0.5 / 0.5 and the 30 ms causal delay; A = 5 degrees
  (f_max 147.9 BPM); prior sigma 1 octave; local following +-2 oscillators plus B1's 20 % / 2 s jump rule; persistence definitions.
- Velasco & Large 2011 Eq. (3) reconstructed (image in the local copy; detuning 0; P A stimulus form); Large et al. 2010 not read. The overseer checks
  the equations against the papers.
- The 3:2 locking share (about a third of songs) is a measured property of the model as ruled; nothing was changed after seeing it.
