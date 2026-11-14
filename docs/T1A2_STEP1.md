# T1a retrain, Step 1 (work order 39, BRAIN_SPEC 7.61.2-3; report only, numbers only)

Round-1 K = 1024 model (`t1a/k1024/best.pt`), T0 data. Variance explained = 1 - var(recon - gesture) / var(gesture) per joint, pooled over all rows of the split's kept windows, degrees, unweighted.

## Variance explained per joint

| split | dataset | base_yaw | shoulder | elbow | wrist_bend | wrist_roll |
|---|---|---|---|---|---|---|
| validation | finedance | 0.736 | 0.627 | 0.671 | 0.704 | 0.708 |
| validation | aioz | 0.791 | 0.741 | 0.713 | 0.540 | 0.609 |
| test | finedance | 0.744 | 0.619 | 0.659 | 0.671 | 0.677 |
| test | aioz | 0.776 | 0.723 | 0.711 | 0.518 | 0.616 |

## Gesture amplitude, train split (deg): FineDance vs kept AIOZ

| dataset | stat | base_yaw | shoulder | elbow | wrist_bend | wrist_roll |
|---|---|---|---|---|---|---|
| finedance | rms | 2.61 | 6.15 | 12.60 | 13.51 | 19.85 |
| finedance | p5 | -4.33 | -10.30 | -20.97 | -21.91 | -32.83 |
| finedance | p95 | 4.34 | 9.93 | 21.41 | 22.08 | 31.61 |
| finedance | p5_p95_range | 8.67 | 20.23 | 42.38 | 43.99 | 64.45 |
| aioz | rms | 1.75 | 4.80 | 8.69 | 6.19 | 10.08 |
| aioz | p5 | -2.90 | -7.63 | -14.68 | -10.35 | -16.87 |
| aioz | p95 | 2.90 | 7.42 | 14.63 | 10.06 | 16.76 |
| aioz | p5_p95_range | 5.80 | 15.05 | 29.31 | 20.40 | 33.63 |
| ratio | AIOZ rms / FineDance rms | 0.67 | 0.78 | 0.69 | 0.46 | 0.51 |

## Effective weight share (sum of npz weight x chunks per dataset / total)

| split | FineDance | AIOZ |
|---|---|---|
| train | 0.423 | 0.577 |
| validation | 0.568 | 0.432 |
| test | 0.285 | 0.715 |

## Rule 7.61.3 (kept-AIOZ gesture RMS below 70 % of FineDance's on 3 or more joints -> AIOZ capped at 50 % of total training weight)

Joints below 70 %: 4 of 5 (base_yaw, elbow, wrist_bend, wrist_roll). **The rule APPLIES.**
