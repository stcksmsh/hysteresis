"""M1: the cerebellum, a forward model of the arm's own proprioception (docs/BODY_BRAIN_PLAN.md §5; D1 of BRAIN_SPEC §7.13).

Command = the servo target (5 angles, 100 Hz). Input at step k: proprioception obs_k (15), the current target tgt_k (5), the last 10 targets
tgt_{k-10..k-1} (50, the efference copy, 100 ms). Output: Gaussian predictions of the change of proprioception obs_{k+h} - obs_k, h = 1, 5, 10 steps
(+10, +50, +100 ms), in units of the training SD of that change. Model: GRU + linear heads, beta-NLL (beta = 0.5). Baselines on the same inputs:
persistence (zero change) and ridge (alpha 1.0); both carry a constant per-dimension residual variance fitted on the training data.
Provisional servo model (Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5, acceleration share 0.25).
Runs in /secondary/hyst-env/brain (torch). Data from babble.py.
"""
import math
import time

import numpy as np
import torch
import torch.nn as nn

HORIZONS = (1, 5, 10)
EFF = 10
CHUNK = 200
WARM = 20            # steps of each chunk used to warm the GRU state; no loss or score there
NIN = 15 + 5 + 5 * EFF
HNAMES = ("+10ms", "+50ms", "+100ms")


class Stats:
    """Standardisers fitted on training data only."""

    def __init__(self, obs, tgt):
        o, t = obs.reshape(-1, 15), tgt.reshape(-1, 5)
        self.omu, self.osd = o.mean(0), o.std(0) + 1e-6
        self.tmu, self.tsd = t.mean(0), t.std(0) + 1e-6
        self.dsd = np.stack([np.concatenate([(obs[:, h:] - obs[:, :-h]).reshape(-1, 15)]).std(0) + 1e-6 for h in HORIZONS])    # (3, 15)


def features(obs, tgt, st):
    """-> X (N, T, NIN) float32."""
    n, T, _ = obs.shape
    o = (obs - st.omu) / st.osd
    t = (tgt - st.tmu) / st.tsd
    pad = np.concatenate([np.repeat(t[:, :1], EFF, 1), t], 1)                                    # pad[:, j] = t[:, j - EFF]
    eff = np.concatenate([pad[:, EFF - j - 1: EFF - j - 1 + T] for j in range(EFF)], -1)         # tgt_{k-1}, tgt_{k-2}, ... tgt_{k-10}
    return np.concatenate([o, t, eff], -1).astype(np.float32)


def labels(obs, st):
    """-> Y (N, T, 3, 15) standardised changes, valid (N, T) = k + 10 < T."""
    n, T, _ = obs.shape
    Y = np.zeros((n, T, len(HORIZONS), 15), np.float32)
    for i, h in enumerate(HORIZONS):
        Y[:, :T - h, i] = (obs[:, h:] - obs[:, :T - h]) / st.dsd[i]
    valid = np.zeros((n, T), bool)
    valid[:, :T - max(HORIZONS)] = True
    return Y, valid


def chunked(a, off=0):
    """(N, T, ...) -> (N * (T - off) // CHUNK, CHUNK, ...)"""
    n, T = a.shape[:2]
    m = (T - off) // CHUNK
    return a[:, off: off + m * CHUNK].reshape(n * m, CHUNK, *a.shape[2:])


def score_mask(valid):
    m = chunked(valid).copy()
    m[:, :WARM] = False
    return m


class Cerebellum(nn.Module):
    def __init__(self, hidden=128, layers=1):
        super().__init__()
        self.inp = nn.Linear(NIN, hidden)
        self.rnn = nn.GRU(hidden, hidden, layers, batch_first=True)
        self.head = nn.Linear(hidden, len(HORIZONS) * 15 * 2)
        self.skip = nn.Linear(NIN, len(HORIZONS) * 15 * 2)      # linear path from the inputs (the ridge baseline's reach is the model's floor)

    def forward(self, x):
        h, _ = self.rnn(torch.tanh(self.inp(x)))
        o = (self.head(h) + self.skip(x)).view(*x.shape[:2], len(HORIZONS), 15, 2)
        return o[..., 0], o[..., 1].clamp(-8, 4)           # mean, logvar


def beta_nll(mean, logvar, y, mask, beta=0.5):
    var = logvar.exp()
    nll = 0.5 * (logvar + (y - mean) ** 2 / var)
    w = var.detach() ** beta
    return ((nll * w).mean(dim=(-1, -2)) * mask).sum() / mask.sum()


def gauss_nll(mean, logvar, y):
    """Per-element plain Gaussian NLL (numpy/torch arrays, same shapes)."""
    return 0.5 * (logvar + (y - mean) ** 2 / np.exp(logvar) + math.log(2 * math.pi))


def train(Xtr, Ytr, Vtr, epochs, hidden=128, layers=1, lr=2e-3, batch=64, seed=0, log=print, deadline_s=None, ckpt=None):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    net = Cerebellum(hidden, layers)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    t0 = time.time()
    for ep in range(epochs):
        off = int(rng.integers(0, CHUNK))
        X, Y, M = chunked(Xtr, off), chunked(Ytr, off), chunked(Vtr, off).copy()
        M[:, :WARM] = False
        perm = rng.permutation(len(X))
        tot = 0.0
        for b in range(0, len(X) - batch + 1, batch):
            i = perm[b: b + batch]
            x, y, m = torch.from_numpy(X[i]), torch.from_numpy(Y[i]), torch.from_numpy(M[i]).float()
            mean, lv = net(x)
            loss = beta_nll(mean, lv, y, m)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            tot += loss.item()
        sched.step()
        log(f"epoch {ep + 1}/{epochs} loss {tot / max(1, len(X) // batch):.4f} t {time.time() - t0:.0f}s")
        if ckpt:
            torch.save({"net": net.state_dict(), "epoch": ep + 1}, ckpt)
        if deadline_s and time.time() - t0 > deadline_s:
            log("deadline reached; stopping early")
            break
    return net


@torch.no_grad()
def predict(net, X, batch=256):
    """-> mean, logvar (n_chunks, CHUNK, 3, 15) numpy over the chunked layout."""
    Xc = chunked(X)
    ms, ls = [], []
    for b in range(0, len(Xc), batch):
        m, l = net(torch.from_numpy(Xc[b: b + batch]))
        ms.append(m.numpy())
        ls.append(l.numpy())
    return np.concatenate(ms), np.concatenate(ls)


class Ridge:
    """Ridge on [X, 1] -> the 45 standardised changes; constant residual variance per output."""

    def __init__(self, alpha=1.0):
        self.alpha = alpha

    def fit(self, X, Y, V):
        x = X[V].astype(np.float64)
        x = np.concatenate([x, np.ones((len(x), 1))], 1)
        y = Y[V].reshape(len(x), -1).astype(np.float64)
        A = x.T @ x + self.alpha * np.eye(x.shape[1])
        self.W = np.linalg.solve(A, x.T @ y)
        self.var = ((y - x @ self.W) ** 2).mean(0).reshape(len(HORIZONS), 15)
        return self

    def predict(self, X):
        n, T = X.shape[:2]
        x = np.concatenate([X.reshape(-1, X.shape[-1]).astype(np.float64), np.ones((n * T, 1))], 1)
        return (x @ self.W).reshape(n, T, len(HORIZONS), 15).astype(np.float32)


def persistence_var(Y, V):
    return (Y[V].astype(np.float64) ** 2).mean(0)          # (3, 15)


def evaluate(net, X, Y, V, ridge, pvar, hnames=HNAMES):
    """Per-trajectory mean NLL and MSE (standardised units, mean over the 15 dims), at each horizon, for model, ridge and persistence.
    Returns dict name -> {'nll': (n_traj, 3), 'mse': (n_traj, 3)} scored on the same steps (chunk step >= WARM, k + 10 < T)."""
    n, T = X.shape[:2]
    mc = score_mask(V)                                                  # (n * m, CHUNK)
    per = mc.shape[0] // n
    m, lv = predict(net, X)
    yc = chunked(Y)
    rc = chunked(ridge.predict(X))
    out = {}
    cands = {
        "model": (m, np.broadcast_to(lv, m.shape)),
        "ridge": (rc, np.broadcast_to(np.log(ridge.var), m.shape)),
        "persistence": (np.zeros_like(m), np.broadcast_to(np.log(pvar), m.shape)),
    }
    w = mc[..., None].astype(np.float64)
    for name, (mean, logv) in cands.items():
        nll = gauss_nll(mean, logv, yc).mean(-1)                          # (rows, CHUNK, 3)
        mse = ((mean - yc) ** 2).mean(-1)
        red = lambda a: ((a * w).reshape(n, per, CHUNK, 3).sum((1, 2)) / w.reshape(n, per, CHUNK, 1).sum((1, 2)))
        out[name] = {"nll": red(nll), "mse": red(mse)}
    return out


def bootstrap_mean(x, rng, resamples=10000):
    """x (n,) per-unit values -> (mean, lo, hi) 95 % percentile interval of the mean over resamples of the units."""
    idx = rng.integers(0, len(x), (resamples, len(x)))
    b = x[idx].mean(1)
    return float(x.mean()), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))
