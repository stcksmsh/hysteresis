# Stage 3 rules: data, limit thresholds and the bar evaluation (work order 26A)

Written 2026-11-09 before any long run. Branch `body-s3d`. Binding sources: BRAIN_SPEC 7.39, 7.40 (and 7.34-7.36, 7.27-7.33). One arm.
Amendments only as dated entries at the end. Every long run: 6 threads, `taskset -c 6-11`, detached `systemd-run --user` unit, MemoryMax 12G, mains power only.

## 1. Slow-stream lanes (`scripts/body/s3_slow.py`, brain env)

Same songs and splits as `k5/splits.json` (train 2,602, val 217, check 357). Same B7 epoch-6 model, same inputs and chunking (6,000 frames, state carried) as `k5_data.song_lanes`.

1. Raw pass (resume-safe, one file per song): for every block b (0.5 s = 50 frames at 100 Hz, `nb = frames // 50`, the partial last block dropped, **the same
   indexing as `k5/lanes`**: block b = frames [50 b, 50 b + 50)) the mean over the 50 frames of the real part and of the imaginary part of the L4 state
   `out[3]["h"]` (256 complex modes) -> `raw` (nb, 512) float32, columns 0..255 real, 256..511 imaginary. Stored in `/secondary/hyst-data/body/s3/raw_l4/<split>/<id>.npy`.
2. PCA: fitted on **train songs only** (all their blocks, 2,602 songs): mean (512), covariance in float64, eigen-decomposition (`numpy.linalg.eigh`), the top 8 eigenvectors by
   eigenvalue, sign fixed so the largest-|.| entry of each component is positive. Projection `pc = (raw - mean) @ comp.T` (nb, 8). Explained variance ratio per component and the
   cumulative top-8 share are reported. Components, mean and variances are stored in `norm.json`.
3. Per block b, `slow` has **13 columns**, in this order (names in `norm.json`):
   `l4_pc1..l4_pc8` (the 8 PCs of block b); `surp_int8` (the 8 s surprisal integral); `logpow_L1..logpow_L4` (`k5/lanes` `y[:, 4:8]`).
   - `surp_int8[b]` = the causal sum of the 10 Hz total-surprisal samples `s10[:, 4]` (nats) over the last 8 s ending at the block's last frame: samples
     `5 b + 4 - 79 .. 5 b + 4` (80 samples; stamps 10 k + 9, so sample `5 b + 4` is stamped at frame 50 b + 49), samples before the song start are absent, **NaN counts as 0**. The value is the plain sum of the samples (not a mean).
   - Each of the 13 columns is z-scored by the **train-corpus** mean and standard deviation of that column (all train blocks of all train songs; `ddof = 0`; an sd below 1e-8 is set to 1): one fixed affine map, **no within-song normalisation**. Mean and sd are in `norm.json` (`col_mean`, `col_sd`).
4. Output: `slow/<split>/<id>.npz` with `slow` (nb, 13) float32; `slow/norm.json` (PCA components (8, 512), pca mean (512), eigenvalues, explained variance ratio, col mean/sd, column names, checkpoint, git commit).
5. Tests (`test_s3_slow.py`): block count equals `k5/lanes` y for 10 songs (all three splits); the PCA projection reproduces on a reload of `norm.json`; surprisal-integral definition on a hand-made sequence (NaN as 0, causal, 80-sample window); z-score columns have ~0 mean / ~1 sd over the train blocks.

## 2. Tempo and RMS (`scripts/body/s3_tempo_rms.py`, brain env)

For every song in train, val and check: `bpm` = `s0_tempo.librosa_bpm` exactly (22,050 Hz mono, `librosa.beat.beat_track`, first value of the tempo array);
`log_rms` = `log(sqrt(mean(y^2)))` of the whole song, same mono 22,050 Hz load. `tempo_rms.json`: `{song_id: {"bpm", "log_rms"}}`. For the 357 check songs `s0/tempo.json` is reused if its route is `librosa`
and 5 songs recomputed here agree to 1e-6 (then the bpm is copied, the RMS is still computed); otherwise all are recomputed. Up to 6 worker processes pinned to cores 6-11. Resume-safe (per-song results cached).

## 3. Energy and jerk thresholds (`scripts/body/s3_thresholds.py`, body env) - BRAIN_SPEC 7.40.2

- Reference: the v47 hexagon exports `/secondary/hyst-data/body/v47/{ic,fy,pr}-0.csv` (100 Hz, `hyst score-csv --hz 100 --agent 0`, mode Off): arm 0 of the three danced songs. Reference data only; one arm only.
- Replay: the CSV joint angles are the servo targets, one per 100 Hz control step, on the **v2f** body with the pass2 configuration `k5p2_train.CFG` (raised plane, contact tc 0.006, hard clip, end stops), through
  `m3f_jax.arm_step` with the carry `m3f_jax.init_carry` (initial pose = first target). Whole 0.5 s blocks (50 steps); the tail is dropped.
- Per block, exactly as the policy's `m3f_jax.make_block_fn` outputs: `energy = p.sum() * J.DT` (`p` = per-step mean over `J.SUB` substeps of `sum |actuator_force * qvel|`); `jerk` =
  `penalties(full, plane)["jerk"]` with `full` the realised 100 Hz joint trajectory in degrees (buffer of the previous 200 samples + the block; the first block has no 53-sample history, so blocks from the 2nd on are used).
- **energy threshold** = mean block energy over all used blocks of the three songs (pooled blocks). **jerk threshold** = 1.25 x the pooled mean block jerk. `thresholds.json` also carries per-song means and `method: "v47-v2f"`.
- Fallback if the replay cannot run: FOR USER with the reason and `method: "pass2x1.5"`: 1.5 x the mean of `energy` and `jerk` over pass2's (`best.pkl`) training windows.
- Units: the per-block `energy` and `jerk` outputs of `m3f_jax` (`p.sum() * DT`; jerk deg^2/s^6).

## 4. Bar evaluation (`scripts/body/s3_eval.py`)

Input: a policy pickle (`k5p2_eval.load_policy` format) and optionally existing rollouts. Output one JSON `bars.json`. Songs: the 357 check songs, argmax, one continuous episode per song
(`s0_roll.py` recipe, start seed 4242; a rollout is reused if `--rollouts DIR` has `<id>.npz`).

- **(a)** `k5p2_eval.py check` on the 1,071 held-out windows, argmax: external (a) 95 % interval above 0 and paired vs untrained above 0 (`check.json`'s `k5_pass`). Reused if the check dir already holds `check.json`.
- **(b)** machine 2AFC on tempo-matched pairs: `s0_measure.tempo_pairs(tempo, artist, eligible, tol=5)` (|dBPM| <= 5, different artists, greedy closest first; tempo = librosa bpm of `tempo_rms.json`).
  **Interleaved** (BRAIN_SPEC 7.36.3): each song's joint trajectory is cut into 30 s clips **with a 30 s gap between clips** (clip starts at 0, 60, 120 s, ...); the 1st, 3rd, ... clips are
  **train**, the 2nd, 4th, ... are **test** (odd train, even test); equal clips per song and role (min); a pair needs >= 2 train and >= 2 test clips per song.
  Features and classifier exactly as `s0_measure.clip_features` / `pair_2afc` (10 cm hand-cell vocab from train clips, per-joint mean/sd of angle and speed, standardised, L2 logistic C=1). Reported: mean accuracy over pairs with bootstrap CI (10,000, seed 0),
  and the label-shuffled control. Bar: >= 0.75.
  The pass2 reference with this interleaved definition is computed in the reference run (the 49 % in the spec comes from Stage 0's half/half definition).
- **(c)** between-song JS / within-song JS. JS distance = `s0_measure.js_dist` base 2 on 5 cm hand-cell shares. Between = median over **all pairs of check songs** (`js_between`). Within = per song, JS between the cell shares of its
  odd clips (1st, 3rd, ...) and its even clips (2nd, 4th, ..., same clip layout as (b)); median over songs (songs with < 2 clips skipped). Ratio = between/within. Bar: >= 2.
- **(d)** occupied 5 cm cells per song at equal duration: each song's rows cut to its first **120 s** (songs shorter than 120 s skipped for (d)), cells = unique 5 cm hand cells over those rows; the median over songs.
  Bar: median >= 1.5 x the pass2 reference median (same definition, reference run).
- **(e)** share of songs whose shoulder joint (column 1) standard deviation over the whole rollout is >= 8 deg. Bar: >= 0.70.
- **(f)** the three danced songs: `k5p2_eval.py songs` (check-csv accepted on each; (e'1) = `acc_p99` <= `limit_acc` and (e'2) = `fast` <= `limit_gt1` against `docs/hf_v47_eprime_reference.json`, whose limits are the 1.25 x v47 rule) plus the **per-joint limit report**:
  for each joint the p99 and the max of the realised speed and acceleration by central differences (`np.gradient`, 50 Hz CSV rows x 50), in deg/s and deg/s^2 and as a share of
  `arm_sim.LIM_V` / `LIM_A`. A single-sample max above a limit is a **flag**, not a failure. Reused if the songs dir already holds results.
- Reported only: decoding D per stream (fast, slow) if the policy pickle carries it (else `null`); the kappa-0 control (`check.json` `paired_vs_trained_kappa0`); program usage (counts, entropy bits, top share);
  Burger-style contrasts: **shoulder amplitude vs pulse clarity** = Spearman correlation across songs of the per-song shoulder sd (deg) with the song's pulse clarity = mean of `y[:, 2]**2 + y[:, 3]**2` (L3 order parameter squared, `k5/lanes`);
  **wrist bend vs low-band flux** = Spearman correlation across songs of the per-song wrist-bend (column 3) sd with the song's mean positive block-to-block change of `logpow_L3` (`y[:, 6]`; `mean(max(diff, 0))`). Two numbers with n, no claim.
- Pass/fail per bar is written next to each value (`pass`: true/false; null for report-only, and for (d) when no reference exists).

## 5. Reference run

`s3_eval.py` on pass2 `best.pkl` (r600) with the existing `s0/pass2` rollouts and the existing `k5p2/check` results; output `/secondary/hyst-data/body/s3/eval_pass2/bars.json`.
Expected (sanity only): 2AFC about 49 %, JS ratio about 0.69, shoulder sd about 3-4 deg. A number far from this is investigated and reported, not tuned.

## Amendments
- **2026-11-09, overseer (report-only change to the Burger contrast):** "low-band flux" in "wrist bend vs low-band flux" means the AUDIO's low-frequency spectral flux, not B7's L3 power.
  Per check song: librosa STFT of the mono 22,050 Hz audio (n_fft 2048, hop 512), magnitude in the 50-200 Hz bins, half-wave-rectified frame-to-frame difference summed over those bins, mean over frames;
  Spearman with the per-song wrist-bend (column 3) sd. The pulse-clarity proxy (L3 order parameter squared, from B7) stays, labelled as a B7-derived proxy. The `logpow_L3` definition in section 4 is superseded for this contrast.
- **2026-11-09, thresholds obtained:** v47 replay on v2f ran (arm 0 of ic/fy/pr, 1,784 blocks after dropping each song's first): energy 0.3747, jerk threshold 4.748e6 (= 1.25 x mean 3.799e6). Written to `s3/thresholds.json`, method `v47-v2f`.
