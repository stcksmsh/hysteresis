# B7 code: notes (BRAIN_SPEC 7)

Status: code, tests, toy tests and the smoke run only. No training run and no result on the held-out songs. Every rule below was fixed
before any result; the same rules are in the docstrings of `core_b7.py`, `toy_b7.py` and `check_b7.py`.

## Files

| File | What |
|---|---|
| `core_b7.py` | `Core7`: B3 core + hippocampus (7.1a), relay (7.1b), acting neuromodulation (7.1c); `to_double` |
| `core.py` | B3 core with default-`None` hooks (`Layer.forward(add, head_add, gain, expo)`, `Core.forward(extra)`); B3 outputs unchanged |
| `train_b7.py` | warm start from B3 round 2 epoch 12 and `train.fit` (8 epochs, patience 2, 24 h) |
| `check_b7.py` | C1 to C5 (+ PAC, DEAM/MERP reported) on a checkpoint, reusing `check_b3.py` |
| `toy_b7.py` | T1 recall, T2 relay (script, prints JSON, exit 1 on fail); T3 is `test_core_b7.py` |
| `smoke_b7.py`, `smoke_b7.sh` | identity check on 10 held-out songs; peak RAM and time per step |
| `launch_b7.sh` | train, then C1 to C5 (not started until the overseer says go) |
| `test_core_b7.py`, `test_check_b7.py` | unit tests |

`check_b3.py` got two default-off hooks: `habituation(hook=)` and `splice(extra=)`.

## Where the spec is silent (fixed here)

**Blocks.** The network runs in 0.5 s blocks (50 frames), in sequence, parallel inside a block. Anything "known at t" is what earlier blocks
produced. A chunk has to start on a block edge.

**Hippocampus.**
- One entry per block j: key from the L3 + L4 modes (real and imaginary parts, layer-normed, 1,024 values) at the block's first frame, and the
  block's mean features. value_j = mean of blocks j..j+3 = the 44 features over [t, t + 2 s), t = 0.5 j.
- Eligible when the entry is at least 8 s old at the start of the block that reads (J - j >= 16 blocks).
- One read per block, with the query from the L3 + L4 modes of the last frame of the previous block. The spec's "current state" is a cycle
  (the current state needs the relay input, which needs the read); this is the freshest causal state. All frames of a block share the read,
  so recognition, novelty and the recall source are piecewise constant over 0.5 s.
- top-k = 4 by cosine, softmax(sim / tau), tau = exp(log_tau) learned, init 0.1. Fewer than 4 eligible: softmax over those; none: recognition 0,
  novelty 1, retrieved value zeros, source time -1.
- Gradients: the store of earlier chunks is detached at the chunk edge. Values are input features and carry no gradient anyway. Keys of the
  current chunk get gradients.

**Relay.** Layer input += `Linear(91 -> 128, no bias)` of [44 features, grid phase (2), retrieved value (44), recognition (1)]. Head skip:
`Linear(44 -> 88, no bias)` of the current 44 features added to every head's output (mean and log-variance).

**Neuromodulation.**
- arousal: per frame from the L1 and L2 surprisal of predictions whose target window ended at t (sum over the layers that have a value),
  one-pole with rise tau 1 s, decay tau 8 s, at 100 Hz, under `no_grad`. Running mean: causal exponential, tau 60 s, started at the song's
  first arousal value. dev = arousal - mean at the previous block's last frame (0 in the first block).
- gain g = 1 + w_g dev on the drive; exponent e = clamp(1 + w_tau dev, 0.1, 10); |lam_eff| = |lam|^e = exp(-nu e) < 1 always; theta untouched.
- Effective time constant per layer and block: median over modes of -dt / ln|lam_eff| = median(dt / nu) / e.

**Zero init, with one exception.** Every relay, skip, w_g and w_tau weight is zero, so B7 at step 0 equals B3. The key and query projections
are not zero: with both at zero the gradient to each is multiplied by the other, a saddle no gradient leaves. They start as the same random
matrix (seed 20261101), separate parameters afterwards. Independent random matrices would make the cosine of two identical states about 0.
They do not touch the outputs while the relay is zero.

**Ablations at evaluation time, same weights.** relay off = relay input and head skip zero. Retrieval off (and "hippocampus off") =
retrieved value and recognition zeroed at the relay input; novelty is still computed. Modulation frozen = dev 0 (with the arousal frozen at any
constant the running mean started at its first value equals it, so the song mean itself does not matter).

**C1 to C5.** See the `check_b7.py` docstring. The ones the spec leaves open:
- C1(b): the top-1 entry's time t lies in [0, 16] s; the share is pooled over all 10 Hz bins inside the second S of all songs in H; a bin with
  no eligible entry counts as not pointing.
- C2: the surprisal SD is the full-song total of the full model.
- C4(b): quartiles by the arousal known at the block start; rel = (top - bottom) / bottom of the median tau; a layer passes when the absolute
  median over songs >= 0.10 and >= 70 % of songs have its sign; (b) needs all four layers with one common sign (the direction named in the
  claim).
- C5: the MSE condition is against ridge AR (check_b3's gate also reports the best baseline); baselines fitted as in round 2.

**Toy tests.** See the `toy_b7.py` docstring (T1 error = L1 and L2 squared error of the predicted mean on frames whose prediction and target
window lie inside the passage).

## Float32 and the identity check

B7 at step 0 equals B3 exactly in the maths: in float64 the two differ by about 1e-14 (unit test `test_identity_in_double_is_exact`, and the
smoke run). In float32 the two scans are rounded differently (B3: 75-frame blocks plus a carry; B7: 50-frame blocks with the state carried
directly), so the deep layers differ by float32 noise (about 1e-5 of the activation scale on noise input). The smoke run reports the real
numbers on 10 held-out songs.
