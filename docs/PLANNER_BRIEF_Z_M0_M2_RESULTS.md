# Planner brief: first work order results (Z1–Z5, M0, M2), 2026-11-04

Branch `body` at 948a6fa (merged from `body-z`). The overseer reran every test and recomputed the numbers marked (R) from the saved files.
H1 is still running (separate brief when it ends).

## What ran

One builder, two sessions (the first stopped at a usage limit). All local except two Kaggle kernels (T4, about 0.07 GPU h of the 30 h weekly
quota). No paid service. Audio never uploaded.

## Results

**Tests (R):** `scripts/brain` 155 OK (1 skipped: cuda), `scripts/body` 10 OK, `scripts/compute` 13 OK.

**Z1, GPU flag.** `--device {cpu,cuda}` in `train.py` and `train_b7.py`. CPU results unchanged (the golden and identity tests pass).
**Not done** in `check_*.py` and `b2.py`: their baseline models are built on CPU, so a default-device switch would mix devices. Checks stay CPU.

**Z2, mid-epoch checkpoints.** Saved every 30 min and on SIGTERM. Toy kill-and-resume against an uninterrupted run: max parameter difference
0.0 (R, test rerun). A SIGTERM during validation is implemented but not tested.

**Z3, data.** 3,176 tracks (2,819 train + 357 held-out), float16, 5.8 GB, max cast error 0.0191 std units (the `sd` fix applied). No audio in the
folder. `manifest.py verify` OK locally. Private Kaggle dataset `kostavukicevic/hyst-features`. Only one file was downloaded back and compared
(byte-identical); the whole upload is not re-verified. Evaluation sets not packed.

**Z4, code.** Private dataset `kostavukicevic/hyst-code`. First-use finding: Kaggle unpacks an uploaded `.tar.gz` itself; `make_kernel.py` now
handles both forms.

**Z5, benchmarks (R, from the results.json files).** B7 step = batch 8 x 180 s = 0.4 audio hours; fresh-initialised Core7, 10 taps, synthetic input.

| B7, seconds per audio hour | Laptop CPU, 8 threads | Kaggle T4 |
|---|---|---|
| Forward only | 8.7 (4.5 GB RAM) | 4.2 (3.8 GB GPU) |
| Train, gradient checkpointing | 39.6 (9.0 GB RAM) | 16.4 (6.4 GB GPU) |
| Train, no checkpointing | killed at the 20 GB cap | CUDA out of memory (14.6 GB) |

So a B7-size training epoch over the 175 h corpus is about 1.9 h on the laptop and about 0.8 h on a T4. Forward-only runs at 0.24 % (laptop)
of real time, so a live forward mode is not limited by compute.

| Physics, million steps/s (2 ms steps) | 1 env | 64 | 512 | 1,024 | 4,096 |
|---|---|---|---|---|---|
| MuJoCo CPU, laptop (20 threads) | 0.16 | 1.13 | 1.61 | 1.83 | 2.24 |
| MJX on CPU, laptop | 0.021 | 0.042 | 0.054 | 0.070 | 0.094 |
| MuJoCo CPU, Kaggle (4 cores) | 0.21 | 0.45 | 0.45 | 0.44 | 0.45 |
| MJX on the T4 | 0.0019 | 0.092 | 0.59 | 1.00 | 2.77 |

The laptop CPU is faster than the T4 at 1,024 environments or fewer. At 4,096 the T4 is 1.2x faster. 20 h of babbling (M1) is 36 M steps:
about 16 s of physics on the laptop.

**M0, the body.** `scripts/body/` (`make_arm.py` generates `arm.xml`; `arm_sim.py`; `BODY_NOTES.md` with every mass's basis).
- Servo: Feetech STS3215 12 V (30 kg·cm class, 55 g, 12-bit encoder), **provisional** (no servo chosen). Stall 2.94 N·m. Implement: the mirror
  ball (default from the check brief, no answer yet).
- Arm mass 0.448 kg (R).
- Holding torque at rest (settled), shoulder / elbow / wrist: neutral 1.40 / 0.78 / 0.25 N·m; straight out 1.75 / 0.78 / 0.24 N·m. At most
  59 % of stall. The overseer's static computation from `arm.xml` gives straight-out shoulder 1.76 N·m (R).
- Sag: shoulder 4.7° (neutral), 5.9° (straight out). The sag is torque / kp, and kp (stall torque per 10°) is an assumption.
- 60 s full-range random commands: speed at most 0.87 and acceleration at most 0.91 of the limits.
- MuJoCo CPU against MJX (CPU JAX), 10 s: max joint difference 0.0001° (tolerance 0.1°, set before the run).
- Forward kinematics match the Rust rig to 4e-16 m. Mean mechanical power 0.46 W on the check run.
- `hyst check-csv` accepts a 60 s physics run.

**M2, pattern generators.** `scripts/body/cpg.py`. Tests: largest target step 0.91 of speed limit x dt under random commands; limits held;
±180° cap on the continuous joints; coupling sign (neighbour trails 0.82 s, commanded 0.83 s). Two values were tuned to pass the limits:
servo damping ratio 1.5 and the generator's acceleration share 0.25.

## Questions

1. **Next step.** M1 (cerebellum, check K1) is next in the plan's order. Babbling physics is cheap on the laptop CPU (above). The training
   run's size is not known yet. Recommendation: build M1 locally with a toy first. Use Kaggle only if the training run projects past about
   4 h on the laptop.
2. **`check_*.py` stay on CPU** (Z1 gap). Recommendation: accept. Checks are short, and moving them would need a device change in the
   baseline code.
3. **Servo assumptions** (kp = stall torque per 10°, rotor inertia, damping ratio 1.5) shape the sag and the speed of response. They matter for
   M1 and M3. Recommendation: keep them provisional, and state them in every result until the user picks a servo.
4. **The three questions of `PLANNER_BRIEF_BODY_PLAN_CHECK.md`** (implement, ±180° cap, B7 lane export) are unanswered. The defaults are in use.
