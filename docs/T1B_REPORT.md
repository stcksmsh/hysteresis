# T1b E1 report (work order 41; BRAIN_SPEC 7.63-7.71)

No verdict (Kosta decides). One arm. FineDance only (4 copies), pooled V1/V2/mirrored, ear + cortex listener (rhythm 192 / affect 64), planner over the frozen 2 x 1024 vocabulary with a residual 2 x 256 posture head (7.70).
Rules: `docs/T1B_RULES.md`. Causality: `docs/T1B_CAUSAL.md`. Facts: `docs/T1B_FACTS.md`. All T2 numbers: `docs/T1B_T2_TABLES.md` (generated; copied below). Per-song values: `t1b/e1/seed*/t2/measures.json`, `swap.json`, `diversity.json`.
Seeds 41101, 41102, 41103; every T2 number is the mean over held-out songs, with the seed mean and the min / max over seeds. STOP = a stop rule of the spec; reported as is, nothing was tuned after seeing it.

## 1. STOP checks (value and threshold, per seed)

| check | threshold | seed 41101 | seed 41102 | seed 41103 |
|---|---|---|---|---|
| swapped_music | 95 % interval of the mean gap must exclude 0 | 0.137 **STOP** | -0.066 **STOP** | 0.030 **STOP** |
| repetition_selfsim_8s | below half the human value | 0.428 **ok** | 0.415 **ok** | 0.413 **ok** |
| joint_range | any joint < 0.5 of human | {"base_yaw": 0.56, "shoulder": 1.13, "elbow": 1.22, "wrist_bend": 1.54, "wrist_roll": 1.96} **ok** | {"base_yaw": 0.48, "shoulder": 0.63, "elbow": 0.68, "wrist_bend": 0.82, "wrist_roll": 0.79} **STOP** | {"base_yaw": 1.23, "shoulder": 1.2, "elbow": 1.35, "wrist_bend": 1.28, "wrist_roll": 2.33} **ok** |
| jitter | any ratio > 1.5 (human copies on the same windows, realised stage) | {"base_yaw.acc_sign_changes_per_s": 1.1, "base_yaw.p_gt3": 3.78, "shoulder.acc_sign_changes_per_s": 1.11, "shoulder.p_gt3": 3.96, "elbow.acc_sign_changes_per_s": 1.05, "elbow.p_gt3": 2.94, "wrist_bend.acc_sign_changes_per_s": 0.9, "wrist_bend.p_gt3": 1.44, "wrist_roll.acc_sign_changes_per_s": 0.95, "wrist_roll.p_gt3": 0.91} **STOP** | {"base_yaw.acc_sign_changes_per_s": 1.12, "base_yaw.p_gt3": 2.97, "shoulder.acc_sign_changes_per_s": 1.15, "shoulder.p_gt3": 4.91, "elbow.acc_sign_changes_per_s": 1.11, "elbow.p_gt3": 2.21, "wrist_bend.acc_sign_changes_per_s": 1.03, "wrist_bend.p_gt3": 1.76, "wrist_roll.acc_sign_changes_per_s": 1.06, "wrist_roll.p_gt3": 0.82} **STOP** | {"base_yaw.acc_sign_changes_per_s": 1.02, "base_yaw.p_gt3": 2.76, "shoulder.acc_sign_changes_per_s": 1.08, "shoulder.p_gt3": 7.02, "elbow.acc_sign_changes_per_s": 0.85, "elbow.p_gt3": 2.38, "wrist_bend.acc_sign_changes_per_s": 0.92, "wrist_bend.p_gt3": 1.54, "wrist_roll.acc_sign_changes_per_s": 0.95, "wrist_roll.p_gt3": 0.86} **STOP** |
| frozen_pose | hand speed < 0.05 m/s for > 3 s anywhere (songs with such a stretch) | 3 **STOP** | 7 **STOP** | 8 **STOP** |
| identical_shape_repeat | > 2x human mean | 0.000 **ok** | 0.001 **ok** | 0.000 **ok** |

Reading (numbers only):
- **Swapped music** (7.64.6 / 7.68.5, 3 tempo-matched partners from the validation pool, 14 of 17 songs had at least one partner, 3 had none, none needed half / double tempo): the mean log-likelihood gap is
  +0.137 nats (95 % interval -0.02 to +0.29), -0.066 nats (95 % interval -0.49 to +0.21), +0.030 nats (95 % interval -0.24 to +0.23) for the three seeds; every interval includes 0 -> STOP on all three seeds.
- Stops that fired: {"41101": ["swapped_music", "jitter", "frozen_pose"], "41102": ["swapped_music", "joint_range", "jitter", "frozen_pose"], "41103": ["swapped_music", "jitter", "frozen_pose"]}.
- Training validation per head (section 2) shows the cause that the data supports: the two gesture-code heads barely beat, and for code 2 fall below, a uniform guess on validation, while vigour and posture heads learned; the model overfits the code stages (train-subset code losses 5.8-6.3 vs validation 6.7-7.1).

## 2. Training (E1)

Early stopping on validation total cross-entropy (patience 5, lr halved after 2 stale epochs, cap 60); train-subset = fixed 16 train songs in evaluation mode. Chance per head (uniform): code1 6.931, code2 6.931, vigour 3.466, posture1 5.545, posture2 5.545.
Train sequences per FineDance genre (style1; 153 train sequences after dropping fd_192, 17 s, no 20 s window): {"Street": 60, "Mix": 35, "Classic": 36, "Folk": 22}.
Parameters: 1,926,944 (listener 0.37 M, planner 1.56 M; `docs/T1B_FACTS.md` section c).

### Seed 41101 (best epoch 4, 10 epochs, 21.5 min per epoch)

| epoch | val total | train-subset total | gap | val code1 | val code2 | val vigour | val posture1 | val posture2 | train code1 | train code2 | train vigour | train posture1 | train posture2 | lr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 26.668 | 26.414 | 0.254 | 6.893 | 7.007 | 2.960 | 4.830 | 4.978 | 6.748 | 6.878 | 2.841 | 4.925 | 5.021 | 0.001 |
| 1 | 26.275 | 25.813 | 0.462 | 6.853 | 7.004 | 2.825 | 4.713 | 4.880 | 6.644 | 6.797 | 2.672 | 4.798 | 4.902 | 0.001 |
| 2 | 25.866 | 25.211 | 0.655 | 6.741 | 6.992 | 2.704 | 4.596 | 4.834 | 6.462 | 6.674 | 2.620 | 4.655 | 4.800 | 0.001 |
| 3 | 25.736 | 24.404 | 1.331 | 6.698 | 7.020 | 2.670 | 4.520 | 4.827 | 6.206 | 6.504 | 2.549 | 4.447 | 4.699 | 0.001 |
| 4 * | 25.659 | 23.787 | 1.872 | 6.673 | 7.060 | 2.664 | 4.448 | 4.815 | 6.024 | 6.347 | 2.488 | 4.315 | 4.614 | 0.001 |
| 5 | 25.730 | 23.229 | 2.501 | 6.699 | 7.116 | 2.678 | 4.416 | 4.820 | 5.841 | 6.205 | 2.482 | 4.164 | 4.538 | 0.001 |
| 6 | 25.708 | 22.643 | 3.065 | 6.698 | 7.168 | 2.676 | 4.346 | 4.820 | 5.653 | 6.060 | 2.445 | 4.030 | 4.455 | 0.001 |
| 7 | 25.687 | 22.151 | 3.536 | 6.697 | 7.202 | 2.649 | 4.321 | 4.818 | 5.495 | 5.940 | 2.414 | 3.906 | 4.396 | 0.0005 |
| 8 | 25.721 | 21.846 | 3.875 | 6.718 | 7.241 | 2.639 | 4.298 | 4.825 | 5.394 | 5.864 | 2.397 | 3.834 | 4.357 | 0.0005 |
| 9 | 25.756 | 21.640 | 4.115 | 6.727 | 7.261 | 2.643 | 4.293 | 4.831 | 5.331 | 5.814 | 2.376 | 3.786 | 4.332 | 0.00025 |

### Seed 41102 (best epoch 5, 11 epochs, 20.1 min per epoch)

| epoch | val total | train-subset total | gap | val code1 | val code2 | val vigour | val posture1 | val posture2 | train code1 | train code2 | train vigour | train posture1 | train posture2 | lr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 26.555 | 26.489 | 0.066 | 6.865 | 6.993 | 2.983 | 4.765 | 4.948 | 6.782 | 6.886 | 2.811 | 4.969 | 5.042 | 0.001 |
| 1 | 26.188 | 25.684 | 0.504 | 6.815 | 6.984 | 2.769 | 4.719 | 4.901 | 6.617 | 6.746 | 2.640 | 4.784 | 4.897 | 0.001 |
| 2 | 25.997 | 25.120 | 0.877 | 6.769 | 7.001 | 2.721 | 4.643 | 4.862 | 6.426 | 6.599 | 2.643 | 4.642 | 4.810 | 0.001 |
| 3 | 25.692 | 24.292 | 1.400 | 6.680 | 7.021 | 2.665 | 4.504 | 4.822 | 6.176 | 6.456 | 2.533 | 4.426 | 4.701 | 0.001 |
| 4 | 25.691 | 23.689 | 2.003 | 6.693 | 7.070 | 2.653 | 4.460 | 4.815 | 5.993 | 6.291 | 2.505 | 4.292 | 4.608 | 0.001 |
| 5 * | 25.661 | 23.010 | 2.651 | 6.683 | 7.121 | 2.657 | 4.394 | 4.807 | 5.788 | 6.140 | 2.444 | 4.122 | 4.517 | 0.001 |
| 6 | 25.729 | 22.502 | 3.227 | 6.694 | 7.181 | 2.677 | 4.360 | 4.817 | 5.601 | 5.991 | 2.449 | 4.017 | 4.445 | 0.001 |
| 7 | 25.747 | 21.935 | 3.812 | 6.714 | 7.238 | 2.660 | 4.319 | 4.816 | 5.427 | 5.855 | 2.407 | 3.869 | 4.377 | 0.001 |
| 8 | 25.804 | 21.575 | 4.229 | 6.738 | 7.277 | 2.664 | 4.302 | 4.823 | 5.320 | 5.767 | 2.369 | 3.786 | 4.332 | 0.0005 |
| 9 | 25.892 | 21.256 | 4.636 | 6.765 | 7.320 | 2.676 | 4.298 | 4.834 | 5.214 | 5.680 | 2.358 | 3.715 | 4.289 | 0.0005 |
| 10 | 25.902 | 21.041 | 4.861 | 6.765 | 7.340 | 2.673 | 4.288 | 4.836 | 5.136 | 5.631 | 2.344 | 3.666 | 4.264 | 0.00025 |

### Seed 41103 (best epoch 5, 11 epochs, 20.1 min per epoch)

| epoch | val total | train-subset total | gap | val code1 | val code2 | val vigour | val posture1 | val posture2 | train code1 | train code2 | train vigour | train posture1 | train posture2 | lr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 26.622 | 26.610 | 0.012 | 6.873 | 7.001 | 2.968 | 4.808 | 4.972 | 6.801 | 6.900 | 2.852 | 5.008 | 5.051 | 0.001 |
| 1 | 26.268 | 25.857 | 0.411 | 6.841 | 6.977 | 2.806 | 4.747 | 4.898 | 6.661 | 6.778 | 2.669 | 4.830 | 4.920 | 0.001 |
| 2 | 26.121 | 25.293 | 0.828 | 6.757 | 7.000 | 2.851 | 4.639 | 4.874 | 6.444 | 6.648 | 2.643 | 4.708 | 4.851 | 0.001 |
| 3 | 25.771 | 24.344 | 1.427 | 6.710 | 7.021 | 2.676 | 4.529 | 4.834 | 6.199 | 6.470 | 2.536 | 4.436 | 4.703 | 0.001 |
| 4 | 25.669 | 23.743 | 1.926 | 6.686 | 7.068 | 2.645 | 4.450 | 4.820 | 6.014 | 6.336 | 2.477 | 4.303 | 4.613 | 0.001 |
| 5 * | 25.642 | 23.064 | 2.578 | 6.682 | 7.110 | 2.642 | 4.393 | 4.814 | 5.797 | 6.175 | 2.434 | 4.132 | 4.525 | 0.001 |
| 6 | 25.761 | 22.647 | 3.115 | 6.721 | 7.166 | 2.684 | 4.367 | 4.823 | 5.675 | 6.050 | 2.440 | 4.024 | 4.457 | 0.001 |
| 7 | 25.720 | 21.991 | 3.729 | 6.712 | 7.221 | 2.651 | 4.317 | 4.820 | 5.451 | 5.887 | 2.394 | 3.879 | 4.380 | 0.001 |
| 8 | 25.757 | 21.632 | 4.125 | 6.726 | 7.255 | 2.646 | 4.305 | 4.825 | 5.325 | 5.809 | 2.372 | 3.791 | 4.334 | 0.0005 |
| 9 | 25.799 | 21.367 | 4.432 | 6.740 | 7.294 | 2.648 | 4.286 | 4.832 | 5.235 | 5.738 | 2.361 | 3.729 | 4.304 | 0.0005 |
| 10 | 25.857 | 21.140 | 4.717 | 6.756 | 7.318 | 2.656 | 4.289 | 4.838 | 5.165 | 5.683 | 2.342 | 3.677 | 4.273 | 0.00025 |


## 3. T2 measures (copied from `T1B_T2_TABLES.md`)

## Measures

| measure | human | retrieval | random | model mean | model min | model max |
|---|---|---|---|---|---|---|
| approx_repeat | 0.8658 | 0.9081 | 1.176 | 0.6213 | 0.2945 | 0.8225 |
| beat_alignment | 0.3867 | 0.3943 | 0.3988 | 0.3918 | 0.3883 | 0.3978 |
| cmd_vs_real_rms[0] | 6.179 | 17.16 | 7.325 | 7.323 | 2.997 | 10.51 |
| cmd_vs_real_rms[1] | 12.96 | 12.95 | 14.71 | 9.048 | 5.161 | 11.46 |
| cmd_vs_real_rms[2] | 21.04 | 20.94 | 21.69 | 19.36 | 6.537 | 29.74 |
| cmd_vs_real_rms[3] | 17.76 | 19.25 | 20.3 | 18.39 | 6.885 | 24.51 |
| cmd_vs_real_rms[4] | 25.37 | 31.31 | 22.95 | 17.73 | 8.125 | 26.08 |
| event_energy | 0.008022 | -0.1555 | -0.00629 | -0.006446 | -0.06181 | 0.02295 |
| event_onset | 0.0008732 | 0.001434 | -0.008625 | 0.0006435 | -5.123e-05 | 0.00136 |
| event_slow | -0.01028 | 0.08103 | 0.02189 | 0.001654 | -0.03153 | 0.02183 |
| frozen_longest_s | 0.6797 | 5.069 | 0.3 | 4.266 | 3.956 | 4.842 |
| gate_share | 0.701 | 0.5294 | 0.6667 | 0.3791 | 0.2157 | 0.6078 |
| guard_share | 2.869e-05 | 0.0003443 | 0 | 0.07981 | 0.0216 | 0.1095 |
| hand_dir_changes_per_s | 1.19 | 1.123 | 1.649 | 1.09 | 0.737 | 1.394 |
| hand_jerk | 33.81 | 37.62 | 45.68 | 21.3 | 13.45 | 26.55 |
| hand_speed_mean | 0.4658 | 0.4526 | 0.4945 | 0.1985 | 0.1244 | 0.2487 |
| ident_repeat | 0.003309 | - | - | 0.0003268 | 0 | 0.0009804 |
| jitter.base_yaw.acc_sign_changes_per_s | 2.087 | 2.25 | 3.116 | 2.254 | 2.124 | 2.341 |
| jitter.base_yaw.jerk_rms | 396.3 | 802.5 | 1110 | 428.1 | 306.3 | 496.3 |
| jitter.base_yaw.p_gt3 | 0.0002672 | 0.002917 | 0.004632 | 0.0008465 | 0.0007364 | 0.00101 |
| jitter.base_yaw.p_gt6 | 3.553e-06 | 5.12e-05 | 4.453e-05 | 1.933e-05 | 1.401e-05 | 2.683e-05 |
| jitter.elbow.acc_sign_changes_per_s | 2.589 | 3.022 | 3.449 | 2.605 | 2.211 | 2.876 |
| jitter.elbow.jerk_rms | 2676 | 3112 | 4196 | 2181 | 1311 | 2755 |
| jitter.elbow.p_gt3 | 0.001078 | 0.002379 | 0.002953 | 0.002709 | 0.002386 | 0.003175 |
| jitter.elbow.p_gt6 | 2.174e-05 | 5.947e-05 | 6.734e-05 | 0.0001023 | 5.381e-05 | 0.0001309 |
| jitter.shoulder.acc_sign_changes_per_s | 2.435 | 2.876 | 3.132 | 2.719 | 2.632 | 2.812 |
| jitter.shoulder.jerk_rms | 966.6 | 1252 | 1306 | 1114 | 745.1 | 1313 |
| jitter.shoulder.p_gt3 | 0.0008598 | 0.002844 | 0.00161 | 0.004554 | 0.003401 | 0.00604 |
| jitter.shoulder.p_gt6 | 2.693e-05 | 0.0001515 | 4.7e-05 | 0.000984 | 0.0007618 | 0.00127 |
| jitter.wrist_bend.acc_sign_changes_per_s | 3.366 | 3.936 | 4.332 | 3.203 | 3.044 | 3.479 |
| jitter.wrist_bend.jerk_rms | 6314 | 7594 | 9618 | 4545 | 2815 | 5710 |
| jitter.wrist_bend.p_gt3 | 0.006606 | 0.01321 | 0.0164 | 0.01043 | 0.009503 | 0.01165 |
| jitter.wrist_bend.p_gt6 | 0.0001644 | 0.0002295 | 0.0002902 | 0.0002401 | 0.0002321 | 0.0002517 |
| jitter.wrist_roll.acc_sign_changes_per_s | 3.409 | 4.082 | 4.598 | 3.354 | 3.222 | 3.603 |
| jitter.wrist_roll.jerk_rms | 8901 | 1.155e+04 | 1.424e+04 | 7151 | 4108 | 9200 |
| jitter.wrist_roll.p_gt3 | 0.01105 | 0.01877 | 0.02332 | 0.009559 | 0.009108 | 0.01009 |
| jitter.wrist_roll.p_gt6 | 0.0001843 | 0.0003695 | 0.000562 | 0.0002103 | 0.0001968 | 0.0002228 |
| joint_range[0] | 139.8 | 191.2 | 94.74 | 106.3 | 67.77 | 172.5 |
| joint_range[1] | 43.28 | 45.29 | 40.51 | 42.71 | 27.07 | 52.12 |
| joint_range[2] | 75.66 | 66.48 | 60.73 | 82 | 51.56 | 102.3 |
| joint_range[3] | 72.81 | 82.05 | 68.42 | 88.33 | 59.77 | 112 |
| joint_range[4] | 113.7 | 158.7 | 104.1 | 192.6 | 89.93 | 265.4 |
| limit_hit_share | 0.01359 | 0.007278 | 0 | 0.2809 | 0.1224 | 0.3967 |
| n_events[0] | 171.1 | 171.1 | 171.1 | 171.1 | 171.1 | 171.1 |
| n_events[1] | 0.3529 | 0.3529 | 0.3529 | 0.3529 | 0.3529 | 0.3529 |
| n_events[2] | 2.471 | 2.471 | 2.471 | 2.471 | 2.471 | 2.471 |
| posture_change_per_token | 3.478 | 4.462 | 3.097 | 2.185 | 1.259 | 2.942 |
| posture_height_energy_corr | 0.00787 | 0.09956 | 0.04012 | 0.001024 | -0.02608 | 0.05358 |
| posture_range[0] | 141.1 | 190.7 | 87 | 110 | 68.27 | 173.2 |
| posture_range[1] | 37.36 | 39.55 | 26.67 | 53.8 | 34.06 | 67.17 |
| posture_range[2] | 66.3 | 56.73 | 46.52 | 119.1 | 57.48 | 170.4 |
| posture_range[3] | 58.89 | 70.06 | 53.03 | 118.9 | 65.84 | 154.6 |
| posture_range[4] | 94.68 | 142.6 | 84.98 | 193.6 | 87.01 | 261.2 |
| selfsim_16tok | 0.3413 | 0.2675 | 0.02042 | 0.4186 | 0.4133 | 0.4277 |
| selfsim_4tok | 0.2226 | 0.1817 | 0.02493 | 0.3487 | 0.3435 | 0.3545 |
| selfsim_60tok | 0.5548 | 0.477 | -0.007983 | 0.5353 | 0.5184 | 0.5518 |
| speed_sat_share | 0.2612 | 0.2456 | 0.2756 | 0.06208 | 0.01192 | 0.08904 |
| triples_per_min | 120 | - | - | 120 | 120 | 120 |
| vigour_energy_corr | 0.06035 | - | - | 0.09632 | 0.06575 | 0.1335 |


## 4. Reports named in the work order

- **Diversity (7.63.8, 8 samples per song):** mean pairwise sample distance 21.1, 14.7, 26.8 (seeds) vs 24.0 between the 4 human copies of the same song (RMS in scaled units over the 60 s). Nearest-human-copy share of samples (V1 / V2 / V1m / V2m), seed 41101: V1 0.24, V2 0.19, V1m 0.26, V2m 0.30; the other seeds are in `diversity.json`.
- **2 s history truncation (7.64.6):** mean change of the per-token cross-entropy when the listener hears only the last 2 s: -0.007 nats, -0.028 nats, -0.007 nats (negative = the truncated listener fits slightly better).
- **Event response, emotion-channel correlations, self-similarity at 2 / 8 / 30 s, beat alignment, endpoint jerk and direction changes, approximate repetition, commanded vs realised, gate shares, controls:** in the measures table (rows `event_*`, `vigour_energy_corr`, `posture_height_energy_corr`, `selfsim_*tok`, `beat_alignment`, `hand_jerk`, `hand_dir_changes_per_s`, `approx_repeat`, `cmd_vs_real_rms`, `gate_share`); columns human / retrieval / random / model.
  Self-similarity windows 4, 16, 60 tokens = 2, 8, 30 s. Gate share = share of the three 20 s windows of each dance that pass the 1.25 gates through the full body pipeline; guard_share, limit_hit_share and speed_sat_share are the guard, joint-limit and limiter-saturation shares.
- **Held-out set:** 17 of the 23 FineDance test songs (60 s dance from 10 s needs 70 s of audio and tokens; the others are shorter).

## 5. What was not done, and deviations (flagged)

- **AIOZ held-out (report-only, 7.63.3) and the AIOZ-only code share (7.66.3) were NOT run:** the cortex states for the 41 AIOZ test groups and the token encoding of AIOZ dancers were not built (extra scope; not needed for the FineDance result). Say if you want them.
- **Music-label probes** dropped by 7.71; replaced by the two report-only correlations (vigour vs ear energy, posture height vs ear energy: rows in the table).
- **Audio shorter than motion** (fd_043, fd_059) and the zero-token song fd_192: tokens past the audio end dropped; fd_192 skipped (`T1B_FACTS.md`, night log).
- **Jitter STOP baseline:** the rule says "the training data's"; the human copies of the same held-out windows, realised through the same simulation, were used (the T1a2 realised numbers cover other windows). The model's power above 3 Hz is higher than human on several joints; acceleration sign changes are close to human.
- **Human reference** keeps all rows regardless of the T0 gate (most human windows fail some gate: human gate share in the table); the likelihood tests are masked by the T0 `ok` flag.
- **Controls** (retrieval, random chunks) are single runs (seeded), identical across the model seeds. They concatenate raw training chunks (no decoder), so token-code measures are empty for them.
- **Posture** is integrated from sampled posture-change entries with no feedback to the human posture; ranges grow beyond the human's in 2 of 3 seeds (section 3 rows `posture_range`), and `limit_hit_share` / `guard_share` show how often the commanded rows reach the joint limits / the guard.
- **Event detection** (report-only): onsets = ear column 40 above its song 95th percentile, local maxima within +-0.1 s, ties and neighbours closer than 0.1 s counted once; energy jumps = the 3 s trailing mean of the standardised RMS column rises by more than 1.0 (corpus sd) over the previous 3 s; slow changes = cosine distance of layer-4 mean states over 1 s blocks above the song 95th percentile. Counts per dance are in `n_events`; energy jumps are rare (0.35 per dance), so `event_energy` is poorly determined.
- Numbers are not comparable to AIOZ; no viewing, no clips of generated dance, no T3.
