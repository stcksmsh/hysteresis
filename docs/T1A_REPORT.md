# T1a report (work order 38, BRAIN_SPEC 7.59.3.1 / 7.59.4.1 / 7.60.4; numbers only, no verdict)

Rules `T1A_RULES.md`. Training: 4 threads per unit, two units in parallel (K = 1024 and 512, then 256 and 128). Errors are in scaled gesture units.

## Validation reconstruction error and code usage (best epoch)

| K | epochs | stopped | best err (weighted) | FineDance err | AIOZ err | code usage | FineDance usage | AIOZ usage |
|---|---|---|---|---|---|---|---|---|
| 128 | 27 | early_stop | 0.5906 | 0.7414 | 0.2934 | 1.000 | 1.000 | 1.000 |
| 256 | 40 | cap | 0.5133 | 0.6454 | 0.2525 | 1.000 | 1.000 | 1.000 |
| 512 | 40 | cap | 0.4592 | 0.5757 | 0.2264 | 1.000 | 1.000 | 0.998 |
| 1024 | 40 | cap | 0.4158 | 0.5200 | 0.2052 | 0.999 | 0.999 | 0.992 |

Size rule (smallest K within 5 % of the next larger): **K = 1024**. Errors by K: 128: 0.5906, 256: 0.5133, 512: 0.4592, 1024: 0.4158. Ratios to the next larger: 128 vs 256: 1.151, 256 vs 512: 1.118, 512 vs 1024: 1.104.

## Stop measures on the test windows (all four sizes; stop rules: usage >= 0.60, jitter ratio <= 1.1, range ratio within 0.9-1.1, gates at 1.25)

| K | usage (val) | gate pass share (recon) | FineDance | AIOZ | control (original) | worst jitter ratio (acc sign changes) | worst p_gt3 ratio | range ratio min / max |
|---|---|---|---|---|---|---|---|---|
| 128 | 1.000 | 0.982 | 0.943 | 0.990 | 1.000 | 9.692 | 104.013 | 0.915 / 1.000 |
| 256 | 1.000 | 0.982 | 0.938 | 0.991 | 1.000 | 10.026 | 109.486 | 0.929 / 1.000 |
| 512 | 1.000 | 0.980 | 0.958 | 0.984 | 1.000 | 10.051 | 108.153 | 0.939 / 1.000 |
| 1024 | 0.999 | 0.980 | 0.951 | 0.986 | 1.000 | 10.154 | 110.563 | 0.946 / 1.000 |

### K = 128: per joint and source (ratio recon / original; range = p5-p95 in degrees)

| source | joint | acc sign changes ratio | power > 3 Hz ratio | range original | range recon | range ratio |
|---|---|---|---|---|---|---|
| all | base_yaw | 9.692 | 104.013 | 166.3 | 166.2 | 1.000 |
| all | shoulder | 8.360 | 45.977 | 48.7 | 46.4 | 0.952 |
| all | elbow | 8.730 | 56.512 | 72.3 | 67.9 | 0.939 |
| all | wrist_bend | 7.009 | 17.226 | 54.3 | 49.7 | 0.915 |
| all | wrist_roll | 7.103 | 17.460 | 112.6 | 107.0 | 0.950 |
| finedance | base_yaw | 11.284 | 211.168 | 472.9 | 472.9 | 1.000 |
| finedance | shoulder | 9.526 | 82.778 | 53.5 | 50.7 | 0.948 |
| finedance | elbow | 9.688 | 67.519 | 98.5 | 91.7 | 0.931 |
| finedance | wrist_bend | 8.580 | 29.870 | 96.0 | 87.4 | 0.911 |
| finedance | wrist_roll | 8.389 | 24.440 | 185.8 | 176.6 | 0.950 |
| aioz | base_yaw | 9.220 | 78.578 | 83.4 | 83.3 | 0.999 |
| aioz | shoulder | 7.750 | 31.892 | 47.2 | 45.2 | 0.957 |
| aioz | elbow | 8.355 | 53.478 | 66.4 | 62.3 | 0.937 |
| aioz | wrist_bend | 6.699 | 14.125 | 41.6 | 36.9 | 0.888 |
| aioz | wrist_roll | 6.795 | 15.092 | 101.5 | 96.8 | 0.954 |

### K = 256: per joint and source (ratio recon / original; range = p5-p95 in degrees)

| source | joint | acc sign changes ratio | power > 3 Hz ratio | range original | range recon | range ratio |
|---|---|---|---|---|---|---|
| all | base_yaw | 10.026 | 109.486 | 166.3 | 166.2 | 1.000 |
| all | shoulder | 8.764 | 45.342 | 48.7 | 46.5 | 0.955 |
| all | elbow | 8.876 | 54.215 | 72.3 | 69.0 | 0.953 |
| all | wrist_bend | 7.213 | 17.148 | 54.3 | 50.5 | 0.929 |
| all | wrist_roll | 7.579 | 17.185 | 112.6 | 108.2 | 0.961 |
| finedance | base_yaw | 11.694 | 217.223 | 472.9 | 472.7 | 1.000 |
| finedance | shoulder | 9.955 | 83.103 | 53.5 | 51.0 | 0.954 |
| finedance | elbow | 9.875 | 64.405 | 98.5 | 93.3 | 0.948 |
| finedance | wrist_bend | 8.830 | 29.515 | 96.0 | 89.2 | 0.929 |
| finedance | wrist_roll | 8.967 | 24.354 | 185.8 | 177.6 | 0.956 |
| aioz | base_yaw | 9.537 | 82.865 | 83.4 | 83.4 | 1.000 |
| aioz | shoulder | 8.125 | 31.360 | 47.2 | 45.3 | 0.959 |
| aioz | elbow | 8.505 | 51.353 | 66.4 | 63.3 | 0.953 |
| aioz | wrist_bend | 6.894 | 14.055 | 41.6 | 37.5 | 0.903 |
| aioz | wrist_roll | 7.250 | 14.825 | 101.5 | 97.7 | 0.963 |

### K = 512: per joint and source (ratio recon / original; range = p5-p95 in degrees)

| source | joint | acc sign changes ratio | power > 3 Hz ratio | range original | range recon | range ratio |
|---|---|---|---|---|---|---|
| all | base_yaw | 10.051 | 108.153 | 166.3 | 166.3 | 1.000 |
| all | shoulder | 8.607 | 45.225 | 48.7 | 46.9 | 0.963 |
| all | elbow | 8.798 | 53.269 | 72.3 | 69.5 | 0.961 |
| all | wrist_bend | 7.093 | 17.018 | 54.3 | 51.0 | 0.939 |
| all | wrist_roll | 7.252 | 17.202 | 112.6 | 108.6 | 0.965 |
| finedance | base_yaw | 11.694 | 211.219 | 472.9 | 472.8 | 1.000 |
| finedance | shoulder | 9.782 | 82.528 | 53.5 | 51.5 | 0.962 |
| finedance | elbow | 9.788 | 63.458 | 98.5 | 94.0 | 0.955 |
| finedance | wrist_bend | 8.670 | 29.272 | 96.0 | 90.3 | 0.941 |
| finedance | wrist_roll | 8.589 | 24.303 | 185.8 | 178.4 | 0.960 |
| aioz | base_yaw | 9.561 | 82.256 | 83.4 | 83.5 | 1.001 |
| aioz | shoulder | 7.990 | 31.299 | 47.2 | 45.7 | 0.967 |
| aioz | elbow | 8.419 | 50.375 | 66.4 | 63.8 | 0.961 |
| aioz | wrist_bend | 6.788 | 13.958 | 41.6 | 38.0 | 0.914 |
| aioz | wrist_roll | 6.929 | 14.865 | 101.5 | 97.9 | 0.965 |

### K = 1024: per joint and source (ratio recon / original; range = p5-p95 in degrees)

| source | joint | acc sign changes ratio | power > 3 Hz ratio | range original | range recon | range ratio |
|---|---|---|---|---|---|---|
| all | base_yaw | 10.154 | 110.563 | 166.3 | 166.2 | 1.000 |
| all | shoulder | 8.685 | 44.761 | 48.7 | 47.1 | 0.968 |
| all | elbow | 8.899 | 53.284 | 72.3 | 69.7 | 0.964 |
| all | wrist_bend | 7.241 | 17.029 | 54.3 | 51.4 | 0.946 |
| all | wrist_roll | 7.664 | 16.962 | 112.6 | 109.1 | 0.969 |
| finedance | base_yaw | 11.851 | 221.019 | 472.9 | 472.9 | 1.000 |
| finedance | shoulder | 9.923 | 80.837 | 53.5 | 51.7 | 0.966 |
| finedance | elbow | 9.925 | 62.956 | 98.5 | 94.0 | 0.955 |
| finedance | wrist_bend | 8.864 | 29.313 | 96.0 | 90.9 | 0.947 |
| finedance | wrist_roll | 9.089 | 23.981 | 185.8 | 178.6 | 0.962 |
| aioz | base_yaw | 9.659 | 83.684 | 83.4 | 83.4 | 1.000 |
| aioz | shoulder | 8.042 | 31.029 | 47.2 | 45.8 | 0.970 |
| aioz | elbow | 8.516 | 50.501 | 66.4 | 64.0 | 0.964 |
| aioz | wrist_bend | 6.929 | 13.960 | 41.6 | 38.4 | 0.923 |
| aioz | wrist_roll | 7.321 | 14.645 | 101.5 | 98.3 | 0.969 |

Control: the original test windows through the same gate function pass 1.000 (FineDance 1.000, AIOZ 1.000); T0 itself kept them all by construction.
