# Night log, builder 1 (body-m1m3), work order 2, 2026-11-04

Provisional servo model throughout: Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5, acceleration share 0.25 (until the user chooses a servo).

## MORNING SUMMARY

(in progress; phases 0 and 1 below)

## Log

### Phase 0: D4, Kaggle verify of `hyst-features`
Kernel `kostavukicevic/hyst-job-verify-features-001` (CPU, no GPU) pushed; it attaches `hyst-code` and `hyst-features` and runs `manifest.py verify` on the features. Result: pending.
(Mains power: `/sys/class/power_supply/ADP1/online` = 1; the `AC*` path in the prompt does not exist on this machine.)

### Phase 1: M1 toy
- `scripts/body/babble.py`: OU commands (tau 1 s, 10 Hz, stationary N(0,1) squashed by the normal CDF to the full command ranges), own seed and own start pose per trajectory, logs obs (15 = pos, vel, load as the sim returns them, one step old) and the generator target (pre-limiter) at 100 Hz. `test_babble.py`: reproducible from a seed, OU autocorrelation, shapes.
- `scripts/body/cerebellum.py`: GRU(128) + linear skip path from the inputs; inputs = proprioception + current target + last 10 targets; Gaussian outputs for the change of proprioception at +10/+50/+100 ms, standardised by the training SD of that change; beta-NLL (0.5). Baselines: persistence (zero change, constant fitted variance), ridge (alpha 1.0, same inputs, constant fitted variance).
- Toy (1 h train, 10 min held out, 20 epochs, 12 threads, 111 s): mean per-trajectory (NLL, MSE) in standardised units, model / ridge / persistence:
  +10 ms (-0.001, 0.230) / (-0.132, 0.165) / (1.410, 0.983); +50 ms (-0.107, 0.229) / (-0.424, 0.192) / (1.416, 0.994); +100 ms (0.044, 0.216) / (-0.180, 0.224) / (1.417, 0.997).
  Toy bar (beats persistence at +100 ms): PASS. The model does not yet beat ridge on NLL at 1 h of data; that is K1's question at 20 h.
- Without the skip path, the same toy gave +100 ms (0.064, 0.219): the skip path was added before the K1 check was committed.
