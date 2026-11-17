# A rules: motor grammar conditioned on controls (work order 45; BRAIN_SPEC 7.73 "THEN: A", 7.74, 7.76 points 2 and 3)

Written and pushed before any training. A only: no listener (B), no teacher, no lookahead selection (7.74 "planned stage", 7.76.5), no music-fit critic (7.76.7). No music input exists anywhere in A.
One arm. Code: `scripts/body/grammar_{data,model,train}.py`, controls version 2 in `controls_lib.py`. Data and models: `/secondary/hyst-data/body/grammar/` (outside git; Motorica-derived
files stay on this laptop, no per-file Motorica numbers in git). Defaults taken where the spec is open are marked **(default)** and listed under FOR USER in the night log.

## 1. Controls version 2 (7.74; `controls_lib.VERSION = 2` or `finalise(..., version=2)` adds `ctl`; version 1 output is unchanged, WO43 values stay reproducible)

Source trajectory, token grid, filters, normalisation constants (`controls/norm.json`, FineDance train) and height bounds [-0.569, 0.770] m: as `CONTROLS_RULES.md` with addenda 1-2 (realised stage).
The version-2 vector has 18 entries per token, computed from the stored per-token controls by `ctl_v2` (no new simulation):

| index | name | rule |
|---|---|---|
| 0 | vigour | combined vigour (first principal component of the z-scored log joint RMS and lamp RMS), clipped to +-6 |
| 1 | height | clip((mean lamp z - z_lo) / (z_hi - z_lo), 0, 1) |
| 2-9 | accent pattern | u_i / mean(u), u_i = 8 sub-slot accent strengths of 62.5 ms (CONTROLS_RULES 3.3). **Near-zero token mean rule:** if mean(u) < 1e-3 (normalised units) the pattern is the flat vector 1 and `acc_ok` = 0. The mean of a valid pattern is exactly 1, so the level (accent density) is not in the control (7.74 Q1) |
| 10 | sharpness | share of lamp-acceleration energy above 3 Hz (CONTROLS_RULES 3.4). **Undefined tokens** (lamp acceleration RMS < 0.05 m/s^2, stored NaN) get 0 and `sharp_ok` = 0 |
| 11-13 | direction | unit 3-D mean lamp velocity (rig frame); below 0.02 m/s the zero vector and `dir_ok` = 0 (mirror copies as realised) |
| 14 | pause probability | share of the token's samples inside a lamp-speed < 0.05 m/s run of >= 13 samples (7.74 Q2: activity is not a control) |
| 15, 16, 17 | `sharp_ok`, `dir_ok`, `acc_ok` | flags 0/1 |

Not controls: activity, accent level (accent mean), movement lead. In the model input the entries 0-14 are standardised with the train mean and sd of their defined values (undefined entries become 0), flags stay 0/1.
Counts per dataset (flat accent / undefined sharpness / zero direction / non-finite) are logged as "CONTROLS V2". All 17,863 windows pass the input scan (`grammar/scan.json`: finite, kept, rows long enough, copy suffix valid).

## 2. Posture vocabulary on absolute posture (7.73 Step 0a, 7.74 Q6)

- Quantity: **absolute posture of the token** = mean of the 50 rows (100 Hz) of the posture target of the token (5 joints, degrees), with base yaw and wrist roll taken **relative to the first row of the 20 s window** (the realised
  stage re-references yaw and roll to the window start the same way; absolute yaw has no meaning for a dancer). Shoulder, elbow, wrist bend are absolute. Not a change, not accumulated: no drift is possible.
- Vocabulary: residual 2 x 256 like 7.70 (k-means on the per-joint standardised 5-vector, stage 2 = k-means of the stage-1 residual), fitted on the **train split only**, seed 45001, all four datasets, all kept windows (the same train tokens
  as A trains on). STOP of 7.63.8 if the variance explained (standardised, residual stage) falls below 0.9 on train or validation. Reported: train and validation variance explained, per joint, stage 1 alone; entries used.
- Decoding to rows: posture knots at the token centres (row 50 k + 25) with the first and last token value repeated to the window edges, interpolated by pchip, plus the A1 gesture (7.74 Q4: `join_lib.build_rows` blocks method = the 40-token decoder window, so one generated window is one decoder window). Yaw and roll knots are
  window-relative; the realised stage's own re-referencing (`sh`) is therefore the identity.
- Vigour bin (`a_n` of the frozen run-B encoder, 32 log bins between the pooled train p0.5 and p99.5) stays a head because the decoder needs the chunk amplitude; it is not a control and is not given to A as input at the current token.
- Per-code control statistics (`grammar/stats.npz`): for gesture code stage 1, gesture code stage 2 (marginal over stage 1), posture stage 1, posture stage 2: count, mean (per dimension over the tokens where the dimension is defined) and
  covariance (undefined entries filled with the global mean) of the 18-vector, **train split only**. Codes with fewer than 5 tokens are shrunk to the global mean with weight 5 (n / (n + 5)); unused codes take the global mean.

## 3. Architecture and loss (`grammar_model.py`)

Window = 40 tokens of 0.5 s (a T0 kept 20 s window; the sample unit of training, splits as T0: train / validation / test by song group; all four copies V1, V2, V1m, V2m of one performance share its group). The GRU starts every window at
`tanh(Linear(style))` (no state carried across windows: windows are separate samples).

- **Control input (small temporal convolution):** the controls of token k and the next three tokens: tokens k .. k + 3, i.e. **horizon H = 4 tokens = current 0.5 s plus the next 1.5 s**. Conv1d(19 -> 64, kernel 4) over the 18 controls plus a "present"
  channel, right zero padding (a control beyond the window end is zero with present 0), GELU. The output at k depends only on controls k .. k + 3 (tested).
- **Style / movement-mode embedding (7.76.2):** persistent per window: dataset (4 x 16), copy V1 / V2 / V1m / V2m (4 x 16), genre (n x 16: FineDance `style1` from the label files, Motorica `style` street / jazz, others "unlabelled") concatenated, Linear 48 -> 64, tanh;
  fed to the GRU at every step and to its initial state. **Sampled per song at generation:** a (dataset, copy, genre) triple is drawn from the empirical joint distribution of the train windows (a random train window's triple), once per song and held for the whole song;
  evaluation runs pin it to the held-out window's own triple unless a check says otherwise. The copy is a style input only (V1 vs V2: 7.75 pending: which copy generation defaults to is set after that ruling; `copy` is a parameter of every generation call).
- **Motif state (7.76.2):** latent vector of 64, updated **every 4 tokens (2 s)**, not every token: at token k = 4, 8, 12, ... `m <- GRUCell_m(mean of the last four GRU hidden states, m)` (input 256, size 64), starting at zero; fed to the main GRU at every step.
- **Token GRU:** GRUCell, hidden 256, input = [control feature 64, style 64, embeddings of the previous token: gesture code 1 (32), code 2 (32), vigour bin (16), posture code 1 (32), posture code 2 (32), motif 64] = 336. No attention, no music.
  The previous token is zero at the window start.
- **Heads (token likelihood, five cross-entropies, equal weights as E1):** gesture code 1 (1024), gesture code 2 given code 1 (1024), vigour bin (32), posture code 1 (256), posture code 2 given posture code 1 (256). Teacher forced in training.
- **Accent input is token-relative** (the 8-slot pattern over the token mean, 7.74 Q1); beat-relative accent timing is B's job later.
- Parameter counts (printed by `Grammar.counts()`, 8 genre labels): style embeddings + linear + initial state 20,032; control conv 4,928; token embeddings 82,432; GRU 456,192; motif GRU 61,824; heads: code 1 263,168, code 2 295,936,
  vigour 8,224, posture 1 65,792, posture 2 73,984; **total 1,332,512** (about 1.33 M).
- **Auxiliary control loss:** for each of the four code sources s (code 1, code 2, posture 1, posture 2) the expected control vector under the head's predicted distribution, `E_s = sum_k softmax(logits_s)_k * mean_s[k]` (per-code means of section 2, standardised
  like the inputs); aux = mean over s of the mean, over the defined dimensions of the **requested** vector (indices 0-14 whose flag is 1, flags excluded), of `(E_s - requested)^2` (standardised units). "Requested" is the control vector actually fed at that token
  (after corruption), zero weight where the vector was dropped. **Weight lambda = 1.0, fixed** (the five cross-entropies are of order 1-7 nats, aux of order 1). Total loss = sum of the five head cross-entropies + 1.0 x aux, weighted per window by the T0 weight and normalised by the weight sum.
- **Control dropout 15 %** of whole vectors, per token (the vector is zeroed and `present` = 0). **Control corruption 10 %** per token (default): the token's whole 18-vector is replaced by a whole vector drawn uniformly from the standardised vectors of other train tokens
  (a sample of the real joint control distribution, flags with it; never one control at a time). Corruption is applied first, then dropout; both in training only. Tested: rates, whole-vector replacement.
- **Fed-back token noise** (as E1): each component of the previous token replaced by a random index with probability 0.10, training only.

## 4. Training

Data: FineDance + AIOZ (calibrated keep list, as T0) + PhantomDance + Motorica, **all on** by default (Kosta's look check 2026-11-16: 11 yes, 1 partly; `docs/T0_PHANTOM_LOOK_RESULT.md`); per-dataset switch: environment variable `HYST_A_DATASETS` (comma list), default all four.
Kept windows only (the T0 gate, windows with `win_pass`); counts: FineDance 3,396, AIOZ 9,257, PhantomDance 3,471, Motorica 1,739 windows (all copies). Splits as T0; a song-level bootstrap everywhere (resampling songs, not windows or copies).
Batch 64 windows; AdamW lr 1e-3, weight decay 0.01, gradient clip 1.0; lr halved after 2 epochs without validation improvement; early stopping on the validation **sum of the five head cross-entropies** (no controls dropped), patience 5, **epoch cap 40**. Seeds 45101, 45102, 45103
(initialisation, shuffle, noise, corruption and dropout streams derived from the seed and the epoch: resumable per epoch from `ckpt.pt`). Reported per epoch: noisy train loss, train loss of the model in evaluation mode on a fixed 1,500-window train subset, validation loss, the gap per head,
the auxiliary term, and the validation loss with all controls withheld.

## 5. Tests (`scripts/body/test_grammar.py`, synthetic)

Version-2 control rules (flat accent, undefined sharpness, mean-1 pattern, flags, version flag keeps version 1); causality of the control window (changing a control beyond k + 3 leaves token k unchanged, nothing before k - 0 or after j changes); control dropout rate 0.15 and
corruption rate 0.10 within 0.01, corrupted vectors are whole pool rows; per-code statistics round-trip (known mean per code, undefined entries excluded); auxiliary loss zero at equality, masks respected; a tiny overfit run (8 windows, 60 steps, loss falls below half); parameter counts add up.

## 6. A checks (after training, numbers only; formulas fixed here)

Held-out = validation + test splits, all four datasets reported separately and pooled (FineDance is the headline). Generation = 40-token window, nucleus p = 0.9 on every head (head order code 1, code 2, vigour bin, posture 1, posture 2), the first 4 tokens
teacher-forced from the human window (history), the remaining 36 sampled with the requested controls; decoding A1 -> pchip posture -> realised stage (`join_run`/`t1a2_realised.sim_one`: guard, spinal, limiter, servo, v2p; no pre-roll rows, rows[0] repeated) -> controls V2 of the
realised q50 (`controls_lib.raw_window` + `finalise(version=2)` with `controls/norm.json`). Bootstrap by song: 2,000 resamples, seed 45002, 95 % percentile intervals. Starts: 200 held-out windows (fixed seed 45003, at most 2 per song, FineDance 100, AIOZ 50, other 25 + 25), 2 samples each.

1. **Residual-code utilisation.** Share of the 1024 stage-2 codes used and perplexity exp(H(c2)) on validation tokens; the empirical conditional entropy H(c2 | c1) (plug-in from train counts, nats) against H(c2); mutual information I = H(c2) - H(c2 | c1); the model's mean predictive entropy of the code-2 head
   given the gold code 1 (nats); and the decoded effect of the residual stage: RMS (deg) of the gesture decoded with both stages minus the gesture decoded with stage 1 only, divided by the RMS of the gesture. Reported; the 7.73 question (keep the residual stage?) is the overseer's.
2. **Intervention matrix.** Reference controls R = the window's own controls, tokens 4..39. For control c in {vigour, height, accent pattern, sharpness, direction, pause}: level low = train p10, high = train p90 (vigour, height, sharpness, pause: the scalar replaced over tokens 4..39; accent pattern: front-loaded
   vs back-loaded ramp (slot i weight 1.5 - 1.0 i/7 vs the reverse, mean 1); direction: unit vectors (0, 0, -1) vs (0, 0, +1), `dir_ok` 1), all other entries from R. Joint combinations (held-out): vigour x height, vigour x sharpness, height x pause, sharpness x pause, each of the 4 sign
   combinations. Output measure per token of the realised trajectory (tokens 8..39 averaged): vigour, height, sharpness, pause probability, accent-pattern centre of mass (slot-index mean of the pattern weighted by its values), direction z. Effect = mean(output | high) - mean(output | low) in train-sd units of that measure,
   expected sign positive for every control (accent: back minus front centre of mass); reported per control with the song-bootstrap interval, the off-diagonal effects (cross-talk, effect of varying control c on measure d), and the same for the human windows' own variation as the reference scale.
3. **Control substitution.** Same starts; sequences of requested controls for tokens 4..39: own, another held-out performance's (a window of the same dataset from another song, fixed seed), shuffled (the own tokens in random order), constant (the own window mean of the defined entries, flags kept). Control match
   per sequence = mean over the six measures of the standardised absolute error between the requested and the realised per-token value (lower is better; sharpness and direction only where the request defines them), and for the three non-constant sequences the mean per-measure Pearson correlation over tokens 8..39; the output of the
   "own" sequence against the human window's realised controls is the oracle reference. Does the output follow each sequence: match to its own request against the match to the other three requests (same output).
4. **Jitter and frozen share against re-joined human A1** (the 7.74 Q4 reference, HJ in `JOIN_RULES.md`: the human window's tokens re-decoded by A1): lamp power above 3 Hz (`v3_lib.pos_measures` p_gt3, per window, ratio of A to HJ with the song-bootstrap interval, medians and means), per-joint p_gt3 mean, hand jerk RMS,
   and the frozen share: share of generated windows with a lamp-speed < 0.05 m/s run longer than 3 s, and the share of frames in such runs, A against HJ. Human level is the HJ interval of `JOIN_REPORT.md`.
5. **Coherence over 2-4 s (7.76.2).** For each window the standardised control sequence (vigour, height, sharpness (0 when undefined), pause; indices 0, 1, 10, 14) of the realised output and the gesture-family sequence (code 1 grouped into 32 families by k-means of the run-B stage-1 codebook, seed 45004):
   (a) mean cosine similarity between the control vectors of tokens k and k + L, L = 4 (2 s) and L = 8 (4 s), over all k; (b) the share of tokens whose gesture family equals that of the token L earlier; both for A (own oracle controls), A with a motif state reset to zero at every token update (ablation), and the human window,
   with the ratio A / human and the song-bootstrap interval.

Every number goes to `docs/A_REPORT.md`; no verdict, no STOP rule is invented beyond the two inherited ones (posture variance explained < 0.9; the 7.65.1 identical-shape repetition and 7.63.8 jitter STOPs are reported as measured, not applied as bars).

## 7. S-B clip candidates (not served)

Held-out FineDance (validation + test) songs, 8 s excerpts (16 tokens inside a kept window, from a token multiple of 4), conditions: human; A with its own oracle controls; A with another performance's controls; A with shuffled controls; A with constant controls; same start, same style triple, same sampling seed per
condition; rendered with the WO43 clip chain (`controls_clips.py` / `retarget_render.sh` under `RETARGET_ROOT=/secondary/hyst-data/body/grammar/look`, lamp head, 1280x720, the song's audio excerpt); manifest only (`look/manifest.json`), the excerpt choice follows 7.75 Q3 once ruled.

## FOR USER (defaults taken)

1. Absolute posture = mean of the token's posture rows, yaw and roll relative to the window start.
2. Near-zero accent token mean (< 1e-3): flat pattern, flag 0. Undefined sharpness: 0, flag 0. Zero direction: zero vector, flag 0.
3. Control horizon 4 tokens (current + next 1.5 s); motif update every 4 tokens, size 64; style = dataset + copy + genre, sampled jointly from the train windows.
4. Auxiliary weight 1.0; requested vector = the vector actually fed (corrupted); corruption 10 % per token, dropout 15 %.
5. Training sample = one 40-token window, no state carried between windows; token noise 0.10 as E1.
6. Vigour bin kept as a head (decoder needs the amplitude), not a control.
7. Pooled-train vigour bins (all four datasets), not the FineDance-only bins of E1.

## Addendum 1 (2026-11-16, overseer GO, BRAIN_SPEC 7.75; pushed before training; 7.75 and 7.77 text and `DIAG_RULES.md` were not yet read in full when this was written, so items 2-4 follow the overseer's message literally)

1. Intervention matrix (section 6.2) also reports two further output measures on the realised trajectory: direction-change rate (changes of the lamp velocity direction per second, as `endpoint_jerk_dirchanges`) and base-rotation speed (RMS of the base-yaw angular speed, deg/s). Same effect-size and bootstrap treatment.
2. No V1 default: the style triple including the copy is sampled per song at generation (section 3). S-B candidates add a sharpness-matched V1 vs V2 comparison: pairs of the same held-out start, one V1 and one V2 style, matched so that the sharpness of the generated realised motion differs by less than 0.05 (token mean) where possible, chosen by seeded search over samples; the residual difference is reported.
3. S-B excerpts only where the song's RMS in the excerpt is >= the song's own median RMS and not in the first or last 10 s; the same excerpt across all conditions.
4. A check added: the posture/gesture split of 7.74 Q4: lamp power above 3 Hz and frozen share for A's posture + human gestures, and A's gestures + human posture, by the DIAG method (`docs/DIAG_RULES.md`), against A and the re-joined human.

## Addendum 2 (2026-11-17, fixes to A READY d3b0d94, pushed before rerunning; report-only, no retraining)

1. **Pause levels.** Train pause probability has p10 = p90 = 0.000 (pause > 0 in only 4-8 % of tokens), so section 6.2's low = p10 / high = p90 made low = high and every pause effect exactly 0. Pause is now low = 0 and high = 1.0 (a full pause request over tokens 4..39), also in the height x pause and sharp x pause combinations; an extra condition high = train p99 is reported next to it. The other controls keep p10 / p90.
2. **S-B V1 vs V2 match.** The pair is matched on the REALISED sharpness (token mean over the excerpt of the sharpness of the rendered, realised q50 of each candidate), not on requested controls; both the requested-control sharpness and the realised sharpness of the chosen pair are reported, and the selection is re-run (only the clips that change are re-rendered). If V1 and V2 samples turn out identical the cause is reported.
3. **Coherence ratios.** "A / human" is the ratio of the means over songs (mean over songs of A's value divided by mean over songs of the human value), with the song-bootstrap interval of that ratio (songs resampled, ratio recomputed per resample); not a mean of per-song ratios.
4. **Per-start values saved.** `grammar/checks/seed<S>_values.npz` holds, for every condition, the per-start window measures (8), window scalars (dirchg, base speed, lamp p_gt3, frozen flag, frozen share), the per-token measures (n, 40, 6), the group (song) and dataset of every start, the per-start intervention differences, the substitution errors and correlations, and the per-start coherence values, so every table can be recomputed.

## Addendum 3 (2026-11-17, WO49, BRAIN_SPEC 7.78 section 4 Q3-Q6; pushed before training; retrain A to convergence, rerun every check)

Everything of sections 1-7 and addenda 1-2 stays (architecture, data, vocabularies, controls version 2, auxiliary weight 1.0, dropout 15 %, corruption 10 %, token noise 0.10), except:

1. **Training length.** Epoch cap 100 (was 40); early stopping as ruled (validation sum of the five head cross-entropies, no controls dropped, patience 5; learning rate halved after 2 epochs without improvement). Seeds **49101, 49102, 49103** (new; the first run, seeds 45101-45103, stays untouched and comparable). Outputs under `/secondary/hyst-data/body/grammar2/` (`HYST_A_OUT`, default); the first run's data, vocabularies, stats and models are read-only inputs. Checks, per-start values (addendum 2.4) and S-B clips are rerun with the same starts and check seeds (45002-45004), now reading the new models.
2. **Pause up-weighting (7.78 Q4).** A train window containing any token with pause probability > 0 (raw control 14) has its T0 loss weight multiplied by f_d = max(1, W_other / W_pause) of its dataset d, W = sum of T0 weights over the train windows of that dataset (so pause windows are half of the effective weight per dataset where this is an up-weight). Train numbers: pause windows are 41.5 % (FineDance), 43.8 % (AIOZ), 54.1 % (Phantom), 34.1 % (Motorica) of windows; **f = 1.471, 1.268, 1.000 (computed 0.848, floored), 1.935**. The floor is a **(default)**: the ruling says up-weight, and Phantom's pause windows are already over half. The weighting changes training only; the validation loss, the early-stopping sum and the checks use the unchanged T0 weights, so first and second run stay comparable.
3. **Pause request treatment.** Current code (WO45) already treats the pause request exactly like the others: it is entry 14 of the 18-vector, so corruption replaces the whole vector (pause included, 10 % per token, a whole pool vector) and dropout removes the whole vector (15 %, `present` = 0), pause included; the auxiliary loss counts it always (defined for every token). Nothing in that rule changes; two things are pinned by tests instead: pause is never corrupted or dropped on its own, and the corruption/dropout rates measured on entry 14 equal those on entry 0. The pool rows hold pause > 0 in the same 4-8 % of tokens as the data, so corrupted tokens rarely ask for a pause; this is not changed.
4. **Q5 / Q6.** Cross-talk stays report-only (judged by eye in S-B); the residual gesture stage is kept; no change to code.
5. **S-B clips.** As section 7 and addenda 1-2 (same excerpts; human; A own / other / shuffled / constant; V1 vs V2 matched on realised sharpness) on the new A. The manifest keeps room for the motor-clock pairs of 7.78 Q7 (none rendered now).
6. **Tests** (`scripts/body/test_grammar.py`): the pause weight factor per dataset (half of the effective weight, floored at 1); pause entry corrupted and dropped with the whole vector at the same rates as the others.

FOR USER (WO49): the floor f >= 1 on Phantom (above); validation and early stopping use the unchanged weights (no pause boost).
