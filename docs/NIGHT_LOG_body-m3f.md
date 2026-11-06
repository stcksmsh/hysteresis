# Night log, builder (body-m3f), work order 13B, M3e toy with the new body and movement changes (2026-11-06)

Provisional servo model throughout: Feetech STS3215 12 V assumed. The installation is ONE arm.

## MORNING SUMMARY

Started. Nothing run yet. Worktree `.claude/worktrees/body-m3f`, branch `body-m3f` from origin/body 90607c5. Order: `docs/BUILDER_PROMPT_WO13B_M3F_TOY.md`.
Plan: (1) new body in `make_arm_v2.py` + MJX contact cost measured and pass2 projected; (2) movement switches 1-4 in new files `m3f_jax.py`, `m3f.py`; (3) grid on tune; (4) try 1 held-out; (5) ablations. Old paths untouched (test: M3e try 1 first epoch unchanged).
FOR USER: none.

## Log

### Phase 1: code, contact cost, pass2 projection (2026-11-06)
Code (all new files; `m3d*`, `m3e*`, `make_arm.py`, `arm_sim.py`, `arm.xml` untouched): `make_arm_v2.py` (the M0 arm text plus table plane z = 0, link capsules r 0.01, base column, mirror-ball sphere r 0.06 = DISC_M; contype/conaffinity bits so the column stands on the table and everything else collides with everything except MuJoCo's parent-child pairs; servo boxes stay non-colliding, flagged), `m3f_jax.py` (block with the switches `obs_lp`, `phase_lp`, `xfade`; body "v1" / "v2" / "v2f"), `m3f.py` (loss, Trainer, scoring), `m3f_report.py` ((e) and check-csv-style breaches), `run_m3f.py`, `test_m3f.py`.
Design numbers fixed before any recorded run: lambda 0.03, lr 1e-3, 40 epochs, seed 0 (Trainer), the same toy and observer procedure. Loss = dec_ext + dec_int + 0.03 x (energy/E0 + hand-speed hinge + jolt hinge + limit cost) + W_JERK x jerk + W_SWITCH x switch. Limit cost = mean relu(|q| - 100 deg)/10 deg over the three bends. Hinges are on the 50 Hz hand trajectory of the 100 Hz joint positions (one boundary jolt per block is not counted). Jerk = mean squared 3rd difference of all five joints. The switch cost is the mean total variation of the program weights per scored block. Descriptors removed for movement 2: external idx 4,5,10,11,16,17,22,23 (the 3rd-difference mean and p90 of joints 0-3) -> 23 inputs; internal the same 8 plus the roll's 2 (idx 35, 36) -> 27 inputs. Phase low-pass: unit vector, tau 0.2 s, angle advanced by atan(om x tau) (removes the filter's steady lag); coupling x R where R = |(mean cos, mean sin)| of the previous block from the toy state.
Contact cost, steady epoch on the 16 training episodes, 8 threads (first epoch of a process about 210 s with compile): M3e try 1 old body 39.4 s (its history, epochs 1-39); "v2" (condim 3) 91.3 s; "v2" with all four movement switches 91.3 s; "v2f" (frictionless, condim 1) 62.9 s. Ratios 2.32 / 1.60. K5-pass2 projection from K5 try 1's 61.1 s x 977 rounds = 13.15 h: 30.6 h (v2), 21.1 h (v2f), both upper bounds (they scale the whole round). Reported to the overseer.
DEVIATION (approved by the overseer): the default body is v2f, frictionless table and self contacts. Reason: a passing policy keeps 5-11 cm clearance (check-csv), so contact only ever acts as a stop. FOR USER: friction is off.
Observation: on v2 the untrained policy shows contact jerk spikes (mean squared jerk 1.07e9 deg2/s6 on the calibration episodes against about 2e6 on v1 in the first blocks). Overseer ruling: the jerk, hand-speed and jolt terms (and the limit cost) are divided by the untrained policy's value on the OLD body (v1, same calibration episodes), not on the new one. Both values are logged at calibration.
