# Planner brief: E1 baseline results (T1b + T2) (2026-11-16)

TO: planner. FROM: overseer, via Kosta. WO41 is done: T1B READY 0efb447 (merged into body). E1 = 7.63-7.71: listener (rhythm 192 / affect
64) over the frozen cortex + 44 ear features, planner GRU 256 over the frozen 2 x 1024 gesture vocabulary, vigour 32 bins, residual
2 x 256 posture; FineDance only (153 train / 26 val / 23 test sequences; fd_192 dropped: 17 s, shorter than one 20 s window); 3 seeds
(41101-41103); 1.93 M parameters. Stopped before T3; no clips made. Full report `docs/T1B_REPORT.md`, tables `docs/T1B_T2_TABLES.md`.

## 1. Training

- Early stopping on total validation cross-entropy (patience 5): best epoch 4 / 5 / 5; ~20 min per epoch.
- Validation at the best epoch vs uniform chance: gesture code 1 6.67-6.68 (chance 6.93); **gesture code 2 7.06-7.12 (worse than chance)**;
  vigour 2.64-2.66 (3.47); posture 1 4.39-4.45 (5.55); posture 2 4.81 (5.55).
- Overfitting from epoch 1: train-subset code losses fall to 5.1-5.8 while validation rises; total train/validation gap 0.01-0.25 at
  epoch 0 -> 1.9-2.7 at the best epoch -> 4.1-4.9 at the end.
- Reading (numbers only): the model learns vigour and posture; it does not learn which gesture comes next.

## 2. T2 STOP rules (overseer recomputed from the saved per-song values)

| STOP | seed 41101 | seed 41102 | seed 41103 |
|---|---|---|---|
| swapped music: mean gap true vs 3 tempo-matched swaps, nats (bootstrap 95 % by song) | +0.137 (-0.02, +0.29) STOP | -0.066 (-0.51, +0.21) STOP | +0.030 (-0.26, +0.23) STOP |
| frozen pose (songs with hand < 0.05 m/s for > 3 s, of 17) | 3 STOP | 7 STOP | 8 STOP |
| jitter (power > 3 Hz, ratio to human, worst joint) | 3.96 STOP | 4.91 STOP | 7.02 STOP |
| joint range (worst joint / human) | 0.56 ok | 0.48 STOP (base yaw) | 1.20 ok |
| repetition (8 s self-similarity) and identical-shape repeat | ok | ok | ok |

14 of 17 held-out songs had swap partners (3 none; none needed half/double tempo). Hand speed: model 0.25 / 0.12 / 0.22 m/s, human 0.47.
Builder: posture drifts to joint limits in 28 % of rows (not recomputed by the overseer).

## 3. Controls (same held-out songs, same body pipeline; overseer recompute)

| | frozen songs | hand speed m/s | mean power > 3 Hz over joints | 16-token self-similarity |
|---|---|---|---|---|
| human (retargeted) | - | 0.47 | 3.97e-3 (1.0x) | - |
| E1 model (seed 41101) | 3 | 0.25 | 5.43e-3 (1.4x) | 0.43 |
| retrieval control (7.64.8) | 5 | 0.45 | 8.03e-3 (2.0x) | 0.27 |
| random human chunks (7.66.3) | 0 | 0.49 | 9.78e-3 (2.5x) | 0.02 |

Reading (numbers only): human chunks re-joined at 0.5 s boundaries (retrieval, random) carry 2-2.5x the human high-frequency power, more
than the model; the jitter STOP therefore measures the chunk joining as much as the planner. Retrieval also freezes (5 songs).

Report-only items: vigour and posture-height correlation with ear energy is near 0 for model and human alike. Not run: AIOZ held-out and
the AIOZ-only code share (extra data preparation; AIOZ is not in E1's training).

## Questions

**Q1. Next step after the swapped-music STOP.** The music does not change the model's likelihood; the gesture-code heads do not learn.
- (a) More data first: E-data (7.69.5) with PhantomDance (19.3 usable h over 4 copies) + Motorica (9.7 h) on top of FineDance, same
  architecture, 3 seeds. Needs Kosta's 12-clip look check first (ready). **[recommended]**: overfitting from epoch 1 on ~150 songs is the
  clearest symptom; 7.63.5's caveat named it.
- (b) A coarser gesture target for the planner: e.g. the planner predicts one of ~64 families of the 1024 codes (clusters of code
  embeddings), the residual chosen by the decoder or by nearest match; one change against E1.
- (c) Stronger regularisation only (dropout, weight decay, smaller planner); one change against E1.
- (d) (a) and (b) as two separate variants against E1.

**Q2. Jitter STOP.** Re-joined human chunks exceed the threshold themselves (2-2.5x).
- (a) Measure jitter against the retrieval control's level on the same songs (ratio to re-joined human chunks), and fix chunk joining
  separately later (report-only now). **[recommended]**
- (b) Keep the threshold against continuous human motion; fix the joins (longer crossfade at token boundaries) before the next run.

**Q3. Frozen pose and posture drift** (posture-change accumulation drifts to the joint limits in 28 % of rows).
- (a) Report-only until Q1's variant is in; a later variant predicts posture as an absolute target relative to neutral. **[recommended]**
- (b) Change it now (posture as absolute target) alongside Q1's variant (breaks one-change-at-a-time).

**Q4. T3.** Stop rules fired on all seeds. (a) No Kosta viewing of E1 [recommended]; (b) a short look anyway (2-3 clips, for intuition).

**Q5. AIOZ held-out report** (skipped): (a) skip, AIOZ is not trained on [recommended]; (b) run it.

**Q6.** Record as 7.72.
