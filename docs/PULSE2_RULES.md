# Pulse v2 rules (WO51, BRAIN_SPEC 7.80 Q1) — written and pushed before any song result

The pulse is the TEMPO source only: period, phase, confidence. No motor clock, no event detector, no verdict. One arm.
Code `scripts/body/pulse2_lib.py` (model), `pulse2_run.py` (run + numeric check v1 vs v2), `pulse2_view.py` (viewing material),
`pulse2_score.py` (scorer); tests `test_pulse2.py`, `test_pulse2_score.py`. `beatv_clicks_visual.render` gains an optional per-flash brightness
(default unchanged). Out: `/secondary/hyst-data/body/pulse2/`; v1's `pulse/` is read only. Defaults are marked **(default)** and listed under FOR USER.
Before this note was pushed only synthetic signals were run (the tests of section 7 and the synthetic probes quoted below). No song audio
was passed through pulse v2.

## 1. What is kept from v1 (`docs/PULSE_RULES.md`)

Unchanged: the model (canonical oscillator, Velasco & Large 2011 Eq. 3 as reconstructed in v1, alpha 0, beta1 -1, beta2 -0.25, eps 1,
detuning 0, P A stimulus form), the integrator (`grfnn._run`, RK4 5 ms, z0 = 0.001, clip 0.95), the drive (`pulse_lib.drive`: columns 32/33/40
weights 1.0/0.5/0.5, running z-score 10 s, C_IN 0.05, X_MAX 0.5, 30 ms causal delay), the arm cap (f_max = 2.466 Hz, A = 5 degrees), the prior
(log-Gaussian, centre 2 Hz, sigma 1 octave), local following (+-2 oscillators, free), rate (mean phase advance over 1 s), pulse events (upward
phase-zero crossings of the selected oscillator, none in a switch frame), whole songs, causal, one pass.

## 2. Change 1: support oscillators (bank 0.25-8 Hz)

The bank gains one octave of oscillators on each side on the same grid: f_i = 0.5 * 2^(i/24), i = -24..96, **121 oscillators, 0.25-8 Hz**.
The oscillators are uncoupled, so v1's 73 oscillators (i = 0..72) are the same numbers bit for bit (tested); the new ones only feed the
readout. Selection stays restricted to 0.5 Hz <= f <= f_max, as in v1.
**Why it is needed:** the harmonic score below reads A(2f) and A(f/2). With v1's bank (0.5-4 Hz) every candidate above 2 Hz (120-148 BPM, the
most common tempo region) would get A(2f) = 0 and every candidate below 1 Hz A(f/2) = 0, a bias against fast and slow tempi that comes from
the bank's edges, not from the music. With the extension every admissible candidate (0.5-2.466 Hz) has both neighbours inside the bank
(0.25-4.93 Hz). "Outside the bank, 0" still holds as stated; it is never reached for an admissible candidate.

## 3. (b) Harmonic-support readout

    H_i(t) = A(f_i, t) + 0.5 A(2 f_i, t) + 0.5 A(f_i / 2, t)        (weights 0.5 / 0.5, **default**)
    S_i(t) = H_i(t) * P(f_i),   i with 0.5 <= f_i <= f_max

A(q) is read by linear interpolation on the log2-frequency grid (`pulse2_lib.amp_at`); 0 outside the bank. With 24 oscillators per octave,
2f and f/2 fall exactly on grid points, so the interpolation is exact.

**Source, stated exactly:** Velasco & Large 2011 (ISMIR, PS2-3), section 1 (local text copy): "a nonlinear oscillator with frequency f
responds to harmonics (2f, 3f, ...), subharmonics (f/2, f/3, ...) and integer ratios (2f/3, 3f/4, ...) of f"; section 3 (Experiment 2): a
second network whose "internal connectivity coupled patches of oscillators to other patches exhibiting small integer ratio frequency
relationships, 1:3, 1:2, 1:1, 2:1, 3:1", "assumed to be learned by exposure to Western rhythms". **The formula above is not an equation of that
paper**: it is a readout-side stand-in for the 1:2 / 2:1 part of that learned connectivity (the work order's formula), with no oscillator
coupling added. Large's "metrical readout = harmonic support across related frequencies" is taken from the work order; no further equation is
quoted.

**How it favours binary levels over 3:2:** in a duple meter the levels f/2 (half bar), f (beat) and 2f (eighths) are all driven by the music, so
the true beat collects support from both neighbours. A candidate at 3/2 or 2/3 of the beat has neighbours at 3 or 3/4 (resp. 4/3 or 1/3) of the
beat, which are not metrical levels of a duple meter and carry only the bank's weaker higher-order responses. The 1:3 / 3:1 relations of the
paper are deliberately not added (they would support triple readings).

**Synthetic probe, reported before any song (not used to set any value):** 2 Hz kicks with a loud 3 Hz stream: noise hats at up to 4x the test
level -> v1 and v2 both 2 Hz. A 3 Hz stream of low tom hits (100 Hz sine) at or above the kick's level -> **v2 picks 1.5 Hz** (half of the toms,
supported by the toms at 3 Hz) while v1 picks 2 Hz; at 300 Hz both pick 2 Hz. So the readout can create a 3:4 reading when a strong low-band
3-stream exists. Nothing was changed after seeing this; it is reported so the song results can be read with it.

## 4. (s) Stability

- **Global level change:** to the current argmax of S only after S_best > **1.35** x S_current (margin M = 35 %) on consecutive frames for
  **H = 4 s** (400 frames) **(default)** (v1: 20 %, 2 s). The run resets when the condition fails for one frame.
- **Near a boundary:** H is lowered to **1.5 s** when a novelty boundary (below) lies within **+-1 s** of the first frame of the evidence run.
  Causal: a boundary at frame p is known from p + 0.5 s; with H = 1.5 s the latest usable boundary (run start + 1 s) is known by the time it is
  used. The margin stays 35 %.
- **Local following** (+-2 oscillators, +-5.9 %) stays free, as v1.
- **Start of a song:** as v1, the first frame's argmax, then the rules above (so the first global switch comes after at least 4 s, or 1.5 s
  near a boundary; boundaries need 10 s of history, so in practice 4 s).
- **Novelty detector** (after `cortexev.py`'s E-change, made causal): every one of the 44 fast-feature columns as a running z-score
  (`grfnn.standardise_causal`, 10 s, SD floor 1e-3), delayed 3 frames like the drive; c(t) = |mean z over (t - 1 s, t] - mean z over
  (t - 2 s, t - 1 s]| / sqrt(44). A **boundary** is a frame p where c(p) is the maximum of c over [p - 1 s, p + 0.5 s] and above every value in
  [p - 1 s, p), c(p) >= the 90th percentile of c over the 60 s before p (threshold updated once a second, needs at least 10 s of history),
  and p is at least 4 s after the previous boundary **(default)**. No phrase-boundary detector is used.

## 5. (c) Confidence

The pulse always runs; phase keeps integrating through low confidence (the oscillators are not reset or gated).

    conf(t) = Pi(t) * G(t),   both in [0, 1]
    Pi(t) = clip( (S_sel(t) / median_band S(t) - 1) / (4 - 1), 0, 1 )        prominence: selected harmonic score over the bank's median score
    G(t)  = clip( |EMA_2s( x(t) e^{-i phi_sel(t)} )| / EMA_30s( x(t) ) / 0.6, 0, 1 )   coherent drive at the selected oscillator's phase

(EMA = exponential moving average with that time constant, causal; x = the bank's drive; phi_sel = the selected oscillator's phase;
denominator floored at 1e-6, so digital silence from the start gives G = 0.)

**Why not the default normalisation:** "score over the bank's 95th-percentile score over the last 8 s, clipped" was measured on a synthetic
signal (120 BPM kicks; 4 s digital silence; 12 s random-time kicks; 12 s noise bed): the selected score over the pooled 95th percentile of all
candidates' scores over 8 s was 4.07 in the beat, 3.55 at the end of the silence, 1.44 in random kicks, 1.37 in the noise bed, so clipped it is 1
everywhere. Read instead as the selected score over the 95th percentile over time of the top score over 8 s, it was 0.99 / 0.74 / 0.62 / 0.88:
it falls little in silence and returns towards 1 once a beatless stretch fills the window. The cause: the critical oscillators (alpha 0) decay
slowly without input (selected amplitude 0.33 -> 0.24 over 4 s of silence) and all together, so any amplitude-only, bank-relative measure stays
high in silence. 7.80 requires "low-band periodic drive absent -> confidence falls", so a drive term G is added: the drive that arrives in phase
with the selected oscillator, relative to the song's own recent drive level. Pi keeps the ruled "amplitude relative to the bank" part.

**Constants** (set on synthetic signals only, **default**): PROM_FULL = 4 (Pi = 1 at prominence 4; measured: clean beat 7-11, random kicks 3.2-4.3,
noise bed 2.8-3.3); COH_FULL = 0.6 (G = 1 at coherence 0.6; measured coherence: kick train 0.77-0.92, a synthetic backbeat of kick on 1/3, snare
on 2/4, hats on eighths 0.53 / 0.65 / 0.75 at 90 / 120 / 140 BPM, 4 s silence end 0.13, random kicks 0.25-0.45, noise bed 0.05-0.12).
Resulting synthetic confidence: backbeat 0.89-1.0, kick train 1.0, end of 4 s silence 0.23, noise bed below 0.3.

**Outputs per song** (`pulse2/songs/<key>.npz`, 100 Hz, frame t at t/100 s): `period` (s, 1/rate), `rate` (Hz), `phase` (rad), `conf`, `freq`
(natural frequency of the selected oscillator), `sel` (index in the 121-grid), `amp`, `prom`, `coh`, `novelty`, plus `events` (s),
`event_conf` (each event's confidence = conf at the event's frame), `boundaries` (s), `switches` (frame, from, to, near-boundary flag), `f_max`,
`rms`. `pulse2/songs/<key>.json`: the check values (section 6), events and their confidence.

## 6. Numeric check (v1 vs v2)

Everything of v1's section 5 (tempo, level vs librosa and grid, gaps, regularity, persistence in quiet passages and grid dropouts, stability,
tempo following, the 10 V4 excerpts), computed by the same code (`pulse_run.check_song`) for v2; v1's values are read from `pulse/songs/`.
**Songs under 12 s are left out of every summary** (7.79 Q4; v1 is recomputed on the same set). Added:
- **level switches per minute** v1 vs v2: frames where the selected index moves by more than 2 (v1's "jumps"; local following moves at most
  2), plus v2's rule switches per minute and the share of them made near a boundary;
- **3:2 share**: share of songs whose whole-song level against librosa (and against the grid) is 2/3 or 3/2, v1 vs v2, and the full level
  distribution;
- **confidence by passage type** (v2), per second s of a song (frames 100 s .. 100 s + 99), only s >= 10 s:
  - *silence* = inside a v1 quiet passage (1 s moving RMS below half the song's median for >= 2 s);
  - *dropout* = inside a v1 grid dropout (grid IOI > 2 x its median), not silence;
  - *beatless* = low-band periodicity p(s) < 0.3 on at least 4 consecutive seconds, not silence; p(s) = the maximum over lags 0.25-2 s of the
    autocorrelation (normalised at lag 0) of the mean-removed 30-200 Hz flux (column 32) in the 6 s window centred on s + 0.5 s (0 if the window
    has no variance) **(default)**;
  - *beat* = p(s) >= 0.5 and none of the above;
  - per song: median confidence over the frames of each type and the share of frames below 0.5; reported: median and quartiles over songs,
    and the paired difference beat minus type within songs that have both;
- **the 20 viewing excerpts** (section 8): v2 / librosa tempo ratio next to v1's, from the events inside each 30 s window, plus v2's median
  confidence and rule switches inside it.
No bootstrap (description, no claim).

## 7. Tests (`test_pulse2.py`, synthetic audio through `fast_features` and the whole pulse v2)

v1's tests carried over: 120 BPM click train (rate within 2 % of 2 Hz after 15 s, events within +-50 ms, SD < 20 ms; plus median confidence
> 0.8 after 10 s); 60 BPM kicks + 240 BPM hats (admissible level); tempo ramp 100 -> 120 BPM (same tolerances); causality (drive, novelty,
rate, phase, amp, sel, conf before 12 s unchanged by changing later audio). v1's own `test_pulse.py` still runs on v1 unchanged.
New:
1. **3:2 trap:** 2 Hz kicks, hats at 3 Hz at 4x the test hat level: median rate after 20 s within 2 % of 2 Hz or 1 Hz.
2. **1 s fill:** 2 Hz kicks, a loud 1 s fill of 100 Hz tom hits at 3 Hz (20-21 s): no rule switch after 10 s; selection within +-2 oscillators
   of 2 Hz throughout 10-40 s.
3. **Silence:** 4 s digital silence (16-20 s) in a 120 BPM train: median confidence 10-16 s > 0.8; **mean confidence over 19-20 s < 0.3**;
   events continue (longest IOI in 14-24 s <= 0.55 s); every event in 20-24 s within **+-50 ms** of the continued click grid.
4. **Noise bed:** 10 s of kicks then 20 s of the noise bed alone: median confidence over 20-30 s < 0.3.
5. Readout units: interpolation exact on grid points and 0 outside; v1's frequencies a bit-identical subset; the harmonic score picks the
   candidate with octave support over an equal-amplitude 3:4 candidate; the switch rule (4 s; 1.5 s with a boundary 0.5 s after the run start;
   4 s with a boundary 3 s after; no switch below the 35 % margin); a texture change gives one boundary within 2 s.
6. Passage labels on a synthetic song (kicks = beat, random kicks = beatless, digital silence = silence, nothing before 10 s).
`test_pulse2_score.py`: the scorer on synthetic answers (counts, rule met and not met, earlier answers matched).

## 8. Viewing material (prepared, NOT served)

The 20 excerpts of the two flash checks (`pulse/flash/key.json`, `pulse/flash2/key.json`: same songs, same starts), each with pulse v2 events
and with librosa beats: 40 items, same rendering (`beatv_clicks_visual.render`: 640x360, 60 fps, white disc, 120 ms linear fade, music without
clicks, 30 s). **Brightness:** a pulse v2 flash peaks at 0.15 + 0.85 x that event's confidence (so 0.15 at confidence 0, 1 at confidence 1;
minimum visible brightness 0.15); librosa flashes peak at 1. Two questions per item: "Is it the right speed?" (right / too fast / too slow), "Is
it steady?" (yes / switches). Ids Q00..Q39 in a seeded random order (seed 51101); `pulse2/view/key.json` records source, song, check, start.
Session built with `dialstudy_session.py --clips pulse2/view/manifest.json --out pulse2/view/session_<date> --seed 51102`, not served.
Motorica items stay local (`local_only`).

## 9. Scorer (`pulse2_score.py SESSION_DIR`)

The 7.80 decision rule as the overseer note states it: per source, count of "right" and count of "yes" (steady) over the 20 excerpts; **met when
pulse v2 >= librosa on both counts**. A per-item table puts each answer next to Kosta's earlier answer for the same excerpt (librosa item vs the
earlier librosa item; pulse v2 item vs the earlier v1 pulse item), from the two earlier sessions. Writes `score.json` and `score.md` into the
session folder.

## FOR USER (defaults taken)

- Bank extended to 0.25-8 Hz (121 oscillators) for the readout only; v1's oscillators unchanged.
- Harmonic weights 0.5 / 0.5; no 1:3 / 3:1 terms.
- Margin 35 %, hold 4 s, 1.5 s within +-1 s of a novelty boundary; novelty = causal ear change (1 s vs 1 s, 90th percentile of the past 60 s,
  4 s apart).
- Confidence = prominence x coherent drive, PROM_FULL 4, COH_FULL 0.6, EMAs 2 s / 30 s, **instead of the default "score over the bank's 95th
  percentile over 8 s"**, which stays at 1 in silence on synthetic signals (section 5).
- Beatless = low-band periodicity below 0.3 for at least 4 s; beat = at least 0.5.
- Flash brightness 0.15 + 0.85 x confidence.
- Synthetic finding: a strong low-band 3 Hz stream over 2 Hz kicks makes v2 pick 1.5 Hz where v1 picks 2 Hz (section 3).
