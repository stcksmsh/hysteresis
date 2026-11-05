# Night log, builder (body-parity), work order 7, MJX one-iteration vs full MuJoCo (2026-11-05)

## MORNING SUMMARY

Provisional servo model: Feetech STS3215 12 V assumed. No pass bar was set; numbers only, no claim.

- Setup: 10 trajectories of 60 s (6,000 control steps): 4 argmax + 4 Gumbel-sampled try-1 (`/secondary/hyst-data/body/m3d/try1/ckpt.pkl`) pattern-generator target streams on held-out toy episodes 0-7 (distinct episodes), plus 2 v47 segments (`v47set.npz` indices 0 and 62: ic arm 0 seg 0, pr arm 2 seg 0). Same start pose and same raw target stream into each arm; each applies its own copy of the same limiter.
- Arms: `mjx1` = M3d's MJX (`opt.iterations = 1`); `mujoco` = `arm_sim.ArmSim` (default: Newton, 100 iterations; the reference); `mjxfull` = MJX with the default 100 iterations (extra, separates solver iterations from MJX-vs-MuJoCo implementation).
- **MJX with full iterations matches MuJoCo to float64 rounding (angle max 2.3e-13 deg, velocity max 3.0e-12 deg/s over 60 s).** All difference of `mjx1` is therefore the single solver iteration.
- `mjx1` vs MuJoCo: identical to rounding (<= 6e-14 deg) in 8 of 10 trajectories. Two diverge: held episode 1 (argmax; first difference > 1e-6 deg at 17.1 s, elbow at 110.1 deg, i.e. at the +-110 deg limit) and v47 (2,2,0) (first at 41.7 s, elbow 110.1 deg again, wrist roll turning past 1,100 deg). Per-trajectory max angle difference: 2.8e-14, 1.3e-02, 2.8e-14, 2.8e-14, 1.4e-14, 2.8e-14, 1.4e-14, 2.8e-14, 1.1e-13, 2.8e-02 deg. The cause matches the log of the M3d work (limits enforced by one iteration), consistent with the data above; not separately isolated.
- Descriptors (31, per 0.5 s block from block 4, relative |a-b|/max(|b|,1e-3), mjx1 vs MuJoCo): overall median 0, worst per-descriptor median 2.5e-13, overall max 1.0e-01 (descriptor index 11, joint 1 third-difference p90, one block, a trajectory that touched the limit). `mjx1` vs `mjxfull` overall max the same 1.0e-01.
- Tests: `test_parity_wo7.py`, 4 tests (MJX deterministic, MuJoCo deterministic, zero-difference, descriptor windows on a full 60 s trajectory), OK in 23 s.
- Bug found and fixed on the way: `block_descriptors` windows were off by one frame and ran past the end of a 60 s trajectory (first run crashed after the simulations; the unit still reported success because the last command was an echo). The simulated trajectories are now saved first (`traj.npz`) and reused on rerun.
- FOR USER: none. Data `/secondary/hyst-data/body/parity/` (`parity.json`, `traj.npz`, `table.md`, logs).


**mjx1_vs_mujoco, joint angle difference (deg), max / RMS**

| window | base_yaw | shoulder | elbow | wrist_bend | wrist_roll |
|---|---|---|---|---|---|
| 0-1s | 7.11e-15 / 7.41e-16 | 1.42e-14 / 5.27e-15 | 1.42e-14 / 2.44e-15 | 1.42e-14 / 1.63e-15 | 7.11e-15 / 1.47e-15 |
| 0-10s | 2.84e-14 / 4.09e-15 | 2.84e-14 / 4.96e-15 | 2.84e-14 / 3.74e-15 | 1.42e-14 / 2.03e-15 | 5.68e-14 / 4.99e-15 |
| 0-60s | 7.24e-05 / 5.95e-07 | 2.65e-03 / 2.57e-05 | 2.77e-02 / 4.42e-04 | 3.76e-03 / 3.85e-05 | 3.61e-07 / 3.70e-09 |

**mjx1_vs_mujoco, joint velocity difference (deg/s), max / RMS**

| window | base_yaw | shoulder | elbow | wrist_bend | wrist_roll |
|---|---|---|---|---|---|
| 0-1s | 2.84e-14 / 4.06e-15 | 1.14e-13 / 2.16e-14 | 7.90e-14 / 1.61e-14 | 1.42e-13 / 1.57e-14 | 8.53e-14 / 1.73e-14 |
| 0-10s | 1.42e-13 / 1.57e-14 | 2.01e-13 / 1.97e-14 | 1.56e-13 / 2.55e-14 | 2.20e-13 / 2.24e-14 | 7.51e-13 / 5.56e-14 |
| 0-60s | 3.72e-03 / 2.28e-05 | 4.66e-01 / 2.75e-03 | 1.79e+00 / 1.19e-02 | 7.10e-01 / 4.27e-03 | 2.04e-05 / 1.60e-07 |

**mjxfull_vs_mujoco, joint angle difference (deg), max / RMS**

| window | base_yaw | shoulder | elbow | wrist_bend | wrist_roll |
|---|---|---|---|---|---|
| 0-1s | 7.11e-15 / 7.41e-16 | 1.42e-14 / 5.27e-15 | 1.42e-14 / 2.44e-15 | 1.42e-14 / 1.63e-15 | 7.11e-15 / 1.47e-15 |
| 0-10s | 2.84e-14 / 4.09e-15 | 2.84e-14 / 4.96e-15 | 2.84e-14 / 3.74e-15 | 1.42e-14 / 2.03e-15 | 5.68e-14 / 4.99e-15 |
| 0-60s | 2.27e-13 / 1.41e-14 | 2.84e-14 / 4.52e-15 | 2.84e-14 / 4.00e-15 | 1.42e-14 / 2.39e-15 | 2.27e-13 / 9.24e-15 |

**mjxfull_vs_mujoco, joint velocity difference (deg/s), max / RMS**

| window | base_yaw | shoulder | elbow | wrist_bend | wrist_roll |
|---|---|---|---|---|---|
| 0-1s | 2.84e-14 / 4.06e-15 | 1.14e-13 / 2.16e-14 | 7.90e-14 / 1.61e-14 | 1.42e-13 / 1.57e-14 | 8.53e-14 / 1.73e-14 |
| 0-10s | 1.42e-13 / 1.57e-14 | 2.01e-13 / 1.97e-14 | 1.56e-13 / 2.55e-14 | 2.20e-13 / 2.24e-14 | 7.51e-13 / 5.56e-14 |
| 0-60s | 1.20e-12 / 5.78e-14 | 2.01e-13 / 2.00e-14 | 5.61e-13 / 2.83e-14 | 2.49e-13 / 2.57e-14 | 3.04e-12 / 1.09e-13 |

**Descriptors (31), mjx1 vs mujoco, relative |a-b|/max(|b|,1e-3), blocks 4..119, 10 trajectories:** overall median 0.00e+00, overall max 1.00e-01; per-descriptor worst max 1.00e-01 (index 11); worst median 2.54e-13.