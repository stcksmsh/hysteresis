# Night log, branch body-acc (WO23: acceleration / speed cap probe, report only)

## MORNING SUMMARY
(in progress; chain launched 2026-11-09 09:41 CET, ETA about 4.4 h) Options `--acc-share` / `--speed-share` added, defaults = today; unit test against origin/body's cpg.py passes; identity control passed. Four runs (B, A1, S1, AS) are training; the report follows.

## Log
- Branch body-acc from origin/body 7f1baee. `cpg.SPEED_SHARE` replaces the two 0.8 literals (cpg.py, m3d_jax.py, s0_ceiling.py); run_m3f.py sets `cpg.ACC_SHARE` / `cpg.SPEED_SHARE` from the options before tracing. Tests: `test_acc_share.py`.
- Report script `acc_probe_report.py` (s0_measure's cell functions are copied in because s0_measure imports sklearn, which the body env lacks; JS checked equal to scipy's).
- rerun4/seed0 args equal the defaults (checked), but it is NOT used as baseline (overseer ruling): B is retrained with today's code; rerun4 is a reference column only.
- Identity control (one epoch, defaults, 3 cores each): origin/body code and body-acc code give identical epoch-0 lines (dec_e 1.9956, dec_i 2.0061, energy_rel 1.3353, rms_speed 56.5851, every printed field except secs). The change is bit-identical at defaults.
- Why epoch 0 differs from rerun4: the same code gives dec_e 1.9956 at 3 threads, 1.9924 at 6 threads, and rerun4 (8 threads) 1.9983. Calibration (E0 1.09171, observers) is identical at every thread count. Cause: thread count (reduction order in training); every commit after 7d8dfdb under scripts/body only adds files.
- Timing: calibration 118 s, epoch 0 357 s (compile), later epochs expected 80-100 s at 6 threads (rerun4: 64-74 s at 8 threads). Per run about 1 h; four runs about 4.4 h.
- Chain `hyst-wo23-chain` (/secondary/hyst-data/body/acc/chain.sh): A1 (resumes from the timing epoch), B (resumes from the timing default epoch), S1, AS, 6 threads, cores 12-17, then end-stop and report.
- FOR USER: an episode's source in toy.npz is a synthetic 8-dim latent trajectory `y` (40 episodes, 120 blocks) generated from `seeds[i]`; the 16 held-out episodes have seeds 900-915, all distinct, so two held-out episodes cannot share a source. They stand in for songs.
- Baseline note: rerun4's realised base-yaw speed max is 1.004x its limit (the report flags any joint > 1.0x, so B may carry that flag too).
