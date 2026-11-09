"""Stage 3 observers (rules section 2 point 1 and the dated entry of 2026-11-09): spectral-norm Lipschitz MLPs, the external observer's input = a causal 1.5 s window of forward-kinematics
positions in metres (elbow, wrist, hand), the D definition per stream."""
import jax
import jax.numpy as jnp
import numpy as np

import m3d
import m3d_jax as J
import m3e
import m3f_jax as F

G_OUT = 4.0                     # output gain: the observers are G_OUT-Lipschitz in their input units
N_OUT = 17
PTS = (2, 3, 5)                 # fk_all points: elbow (end of link 1), wrist (end of link 2), hand (end of link 4)
WIN_N, WIN_STEP = 15, 10        # 15 samples at 10 Hz = 1.5 s, newest first; the 100 Hz joint trajectory is read every 10th sample
N_EXT = WIN_N * len(PTS) * 3    # 135
BLOCK_SAMPLES = J.BLOCK         # 50 control steps per block
PAD = (WIN_N - 1) * WIN_STEP    # 140 samples of history a block's window needs before its first... end sample
HIST = 150                      # samples of the carry buffer that a chunk's windows can reach (block end - 140 .. , rounded up to a whole 10 Hz grid)


# ---------------------------------------------------------------------------------------------------------------- Lipschitz MLP
def spec(W):
    return W / jnp.maximum(1.0, jnp.linalg.norm(W, 2))                    # exact SVD, recomputed at every call


def lip_apply(O, x):
    """O = [(W, b)] x (n, ..., n_in) -> (..., 17). tanh hidden layers, every W divided by max(1, sigma_max(W)), output times G_OUT: G_OUT-Lipschitz in x (2-norm)."""
    ws = [(spec(W), b) for W, b in O]
    for i, (W, b) in enumerate(ws):
        x = x @ W + b
        if i < len(ws) - 1:
            x = jnp.tanh(x)
    return G_OUT * x


def init_obs(key, n_in):
    return m3e.init_observer(key, n_in, n_out=N_OUT)


@jax.jit
def _obs_step(O, st, x, y):
    def loss(O):
        return ((lip_apply(O, x) - y) ** 2).mean()
    l, g = jax.value_and_grad(loss)(O)
    O, st, _ = J.adam_step(O, g, st, m3d.OBS_LR, clip=10.0, wd=m3d.OBS_WD)
    return O, st, l


def train_obs(O, x, y, steps, seed=0):
    """m3d.train_observer through the Lipschitz apply. -> O, last batch loss."""
    st = J.adam_init(O)
    rng = np.random.default_rng(seed)
    x, y = jnp.asarray(x), jnp.asarray(y)
    l = None
    for _ in range(steps):
        i = rng.integers(0, len(x), m3d.OBS_BATCH)
        O, st, l = _obs_step(O, st, x[i], y[i])
    return O, float(l)


# ---------------------------------------------------------------------------------------------------------------- external input: forward-kinematics positions, metres
def _windows(P, j_end, global0):
    """P (E, N, 3 points, 3) metres at 10 Hz; j_end (nb,) indices of each block's newest sample; global0: global 10 Hz index of P[:, 0]. -> (E, nb, 135), samples before the episode start are 0."""
    idx = j_end[:, None] - jnp.arange(WIN_N)[None]                           # (nb, 15) newest first
    w = P[:, idx]                                                             # (E, nb, 15, 3, 3)
    valid = (global0 + idx) >= 0
    w = jnp.where(valid[None, :, :, None, None], w, 0.0)
    return w.reshape(w.shape[0], w.shape[1], -1)


def _fk_pts(q_deg):
    """q_deg (E, N, 5) -> (E, N, 3, 3) metres, base frame."""
    return jax.vmap(F.fk_all)(q_deg)[:, :, jnp.asarray(PTS)]


def ext_features(q):
    """Whole-episode version (numpy in/out): q (E, nb, 50, 5) deg at 100 Hz -> (E, nb, 135). The 10 Hz grid is the samples 9, 19, ... of the episode (block ends are samples 49, 99, ...)."""
    E, nb = q.shape[:2]
    seq = jnp.asarray(q).reshape(E, nb * BLOCK_SAMPLES, 5)[:, WIN_STEP - 1::WIN_STEP]
    P = _fk_pts(seq)
    j_end = jnp.arange(nb) * (BLOCK_SAMPLES // WIN_STEP) + (BLOCK_SAMPLES // WIN_STEP - 1)
    return np.asarray(_windows(P, j_end, 0))


def ext_features_chunk(buf, q, c0):
    """In-loss version: buf (E, 200, 5) the carry buffer before the chunk (last 200 samples of earlier blocks), q (E, nb, 50, 5) the chunk, c0 the global index of the chunk's first block (float).
    Equals ext_features(whole episode)[:, c0:c0 + nb] (test)."""
    E, nb = q.shape[:2]
    seq = jnp.concatenate([buf[:, -HIST:], q.reshape(E, nb * BLOCK_SAMPLES, 5)], 1)           # sample s of seq has global index c0 * 50 + s - HIST
    sub = seq[:, WIN_STEP - 1::WIN_STEP]                                                     # grid points 9, 19, ...: global index c0 * 50 + 10 j + 9 - HIST
    P = _fk_pts(sub)
    j_end = HIST // WIN_STEP + jnp.arange(nb) * (BLOCK_SAMPLES // WIN_STEP) + (BLOCK_SAMPLES // WIN_STEP - 1)
    # global 10 Hz index of sub[:, 0] is (c0 * 50 + 9 - HIST - 9) / 10 = c0 * 5 - HIST / 10  -> sample j has global index c0 * 5 - HIST/10 + j (grid index of the episode)
    return _windows(P, j_end, c0 * (BLOCK_SAMPLES // WIN_STEP) - HIST // WIN_STEP)


# ---------------------------------------------------------------------------------------------------------------- D per stream
def shifted_D(pred, tgt, dims, start=8, min_shift=16, n_shifts=20, seed=0):
    """pred, tgt (E, NB, 17). D = 1 - L_matched / L_shifted on the output columns `dims` (rules section 2 point 3): L_matched = mean squared error over blocks >= start, L_shifted the same against
    tgt rolled circularly by a shift in [min_shift, NB - min_shift] blocks (20 per window from default_rng(seed)); ratio of the means over the windows."""
    rng = np.random.default_rng(seed)
    E, T = pred.shape[:2]
    pd, td = pred[..., dims], tgt[..., dims]
    lm = ((pd - td) ** 2).mean(-1)[:, start:].mean(1)
    ls = np.zeros(E)
    for e in range(E):
        v = []
        for _ in range(n_shifts):
            k = int(rng.integers(min_shift, T - min_shift + 1))
            v.append(((pd[e] - np.roll(td[e], k, 0)) ** 2).mean(-1)[start:].mean())
        ls[e] = np.mean(v)
    return float(1.0 - lm.mean() / ls.mean())
