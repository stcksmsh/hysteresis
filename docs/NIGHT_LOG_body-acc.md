# Night log, branch body-acc (WO23: acceleration / speed cap probe, report only)

## MORNING SUMMARY
(done) Chain 09:41 to 16:23 (6 h 42 min; a run took about 1.6 h, not the 1 h projected). Report in /secondary/hyst-data/body/acc/report.{json,txt}. Within / outside the servo limits (realised max, 100 and 50 Hz): B within; S1 within (wrist roll speed max 1.000x); A1 OUTSIDE (wrist bend speed max 1.006x); AS OUTSIDE (elbow and wrist bend speed max 1.001x); rerun4 (8 threads, reference) outside (base yaw 1.004x). No setting exceeds an acceleration limit (largest realised max 0.87x, A1 wrist bend). The exceedances are at most 0.6 % over the speed limit. 0 end-stop events everywhere. Options `--acc-share` / `--speed-share` added, defaults = today; unit test against origin/body's cpg.py passes; identity control passed.

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

## Report (report.txt; rerun4_8thr = reference only, 8 threads, cores 0-7, old code path)

```
                                                               B            A1            S1            AS   rerun4_8thr
ACC_SHARE / SPEED_SHARE                                 0.25/0.8       0.4/0.8     0.25/0.95      0.4/0.95      0.25/0.8
realised speed p99/limit base_yaw 100Hz                    0.638         0.638         0.658         0.770         0.882
realised speed p99/limit shoulder 100Hz                    0.550         0.266         0.582         0.362         0.329
realised speed p99/limit elbow 100Hz                       0.465         0.778         0.619         0.839         0.657
realised speed p99/limit wrist_bend 100Hz                  0.725         0.790         0.642         0.935         0.747
realised speed p99/limit wrist_roll 100Hz                  0.776         0.788         0.977         0.920         0.729
realised speed max/limit base_yaw 100Hz                    0.911         0.668         0.893         0.985         1.004
realised speed max/limit shoulder 100Hz                    0.649         0.338         0.681         0.531         0.403
realised speed max/limit elbow 100Hz                       0.673         0.820         0.750         1.001         0.771
realised speed max/limit wrist_bend 100Hz                  0.820         1.006         0.919         1.001         0.857
realised speed max/limit wrist_roll 100Hz                  0.887         0.886         1.000         0.998         0.880
realised acc p99/limit base_yaw 100Hz                      0.345         0.265         0.304         0.338         0.280
realised acc p99/limit shoulder 100Hz                      0.287         0.277         0.293         0.339         0.268
realised acc p99/limit elbow 100Hz                         0.230         0.283         0.286         0.455         0.273
realised acc p99/limit wrist_bend 100Hz                    0.236         0.297         0.245         0.338         0.225
realised acc p99/limit wrist_roll 100Hz                    0.204         0.157         0.270         0.267         0.242
realised acc max/limit base_yaw 100Hz                      0.770         0.413         0.693         0.786         0.773
realised acc max/limit shoulder 100Hz                      0.805         0.691         0.640         0.640         0.746
realised acc max/limit elbow 100Hz                         0.414         0.446         0.553         0.730         0.562
realised acc max/limit wrist_bend 100Hz                    0.352         0.871         0.452         0.516         0.490
realised acc max/limit wrist_roll 100Hz                    0.319         0.228         0.755         0.455         0.430
realised speed p99/limit base_yaw 50Hz                     0.638         0.638         0.658         0.769         0.882
realised speed p99/limit shoulder 50Hz                     0.550         0.266         0.582         0.362         0.329
realised speed p99/limit elbow 50Hz                        0.465         0.778         0.618         0.839         0.657
realised speed p99/limit wrist_bend 50Hz                   0.725         0.790         0.642         0.935         0.747
realised speed p99/limit wrist_roll 50Hz                   0.776         0.788         0.976         0.920         0.728
realised speed max/limit base_yaw 50Hz                     0.910         0.668         0.892         0.984         1.004
realised speed max/limit shoulder 50Hz                     0.648         0.337         0.681         0.531         0.403
realised speed max/limit elbow 50Hz                        0.673         0.819         0.750         1.001         0.770
realised speed max/limit wrist_bend 50Hz                   0.819         1.006         0.919         1.001         0.856
realised speed max/limit wrist_roll 50Hz                   0.886         0.886         1.000         0.998         0.880
realised acc p99/limit base_yaw 50Hz                       0.343         0.265         0.301         0.337         0.278
realised acc p99/limit shoulder 50Hz                       0.287         0.277         0.293         0.336         0.268
realised acc p99/limit elbow 50Hz                          0.229         0.281         0.283         0.452         0.272
realised acc p99/limit wrist_bend 50Hz                     0.235         0.295         0.243         0.334         0.224
realised acc p99/limit wrist_roll 50Hz                     0.203         0.156         0.268         0.265         0.240
realised acc max/limit base_yaw 50Hz                       0.759         0.396         0.678         0.777         0.758
realised acc max/limit shoulder 50Hz                       0.541         0.432         0.610         0.619         0.498
realised acc max/limit elbow 50Hz                          0.386         0.432         0.521         0.711         0.533
realised acc max/limit wrist_bend 50Hz                     0.343         0.847         0.413         0.488         0.444
realised acc max/limit wrist_roll 50Hz                     0.283         0.214         0.708         0.418         0.400
any joint > 1.0 x its limit                                   no           YES            no           YES           YES
steps on acc cap base_yaw                                  0.994         0.496         0.996         0.869         0.145
steps on acc cap shoulder                                  0.997         0.996         0.997         0.996         0.997
steps on acc cap elbow                                     0.996         0.029         0.993         0.970         0.994
steps on acc cap wrist_bend                                0.899         0.020         0.995         0.121         0.621
steps on acc cap wrist_roll                                0.030         0.015         0.045         0.024         0.829
steps on speed cap base_yaw                                0.000         0.499         0.000         0.127         0.852
steps on speed cap shoulder                                0.000         0.000         0.000         0.000         0.000
steps on speed cap elbow                                   0.000         0.960         0.000         0.020         0.000
steps on speed cap wrist_bend                              0.096         0.973         0.000         0.872         0.374
steps on speed cap wrist_roll                              0.965         0.978         0.950         0.969         0.165
re-roll vs saved q, max abs deg                                0             0             0             0       2.7e-10
occupied cells, pooled (5 cm)                                920          1029          1221          1160          1725
occupied cells per episode, mean                             338           443           340           348           573
cell entropy (bits)                                        8.595         9.115         8.749         8.562         9.800
JS between episodes, median                                0.611         0.599         0.620         0.586         0.720
JS half-episode control, median                            0.781         0.753         0.766         0.740         0.830
JS ratio                                                    0.78          0.80          0.81          0.79          0.87
decoding ext (a)                                           1.172         1.098         1.107         1.076         1.050
decoding int (a)                                           1.174         1.129         1.168         1.084         1.072
e'1 hand acc p99 (m/s^2)                                    2.55          3.86          3.03          4.51          3.35
e'2 share hand speed > 1 m/s                              0.0013        0.0334        0.0023        0.0478        0.0067
hand speed p99 / max (m/s)                             0.82/1.14     1.06/1.32     0.90/1.08     1.18/1.59     0.98/1.14
floor-breach episodes (of 16)                                  0             0             0             0             0
contact share                                             0.0000        0.0000        0.0000        0.0000        0.0000
programs used                                                  2             1             2             4             2
```
- The report step first crashed on the rerun4 run (its saved args lack acc_share/speed_share); fixed by defaulting to 0.25/0.8, report step rerun alone (unit hyst-wo23-report2).
- Cap-share re-roll reproduces the saved held-out q exactly for B, A1, S1, AS (max abs diff 0) and to 2.7e-10 deg for rerun4.
