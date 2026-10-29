"""B2 core (docs/BRAIN_SPEC.md 4.1, untrained): four complex diagonal LRU layers, slow on top.

Fixed here, before any result:
  inputs     44 standardised fast features (clipped to +-CLIP) + grid phase (cos, sin) = 46 columns at 100 Hz.
             The no-phase mode zeroes the two phase columns; parameters and init are identical.
  layer      x' = x + Wc q                        (q: coupling, below; layer 1 has none)
             u  = B ln1(x') * sqrt(1 - |lam|^2)   (complex B, N = 256 modes)
             h_t = lam h_{t-1} + u_t              (diagonal, complex)
             x  = x' + C [Re h, Im h] + D x'      then  x = x + gatedMLP(ln2(x))
  modes      lam = exp(-nu + i theta); theta = 2 pi f dt, nu = dt / tau; f log-uniform in the layer's band,
             tau = Q / (pi f), Q log-uniform in 2..8. `clamp_modes` clamps f to the band (nu stays free > 0).
  heads      per layer: Gaussian mean and log-variance (44 each) of the mean of the features over
             [t + h, t + 2h), h = 10, 50, 200, 800 frames (+100 ms, +0.5 s, +2 s, +8 s).
  coupling   err_i[t]  = mean(f[t-h+1 .. t]) - head_mean_i[t-2h+1]    (the prediction made 2h-1 frames ago, now scored;
                         0 until 2h frames exist). Layer i+1 receives, at step t, q = err_i[t-1] * prec_{i+1}[t-1],
                         through a Linear(44, 128). prec_{i+1} = exp(-logvar), logvar from a Linear(128, 44) on layer
                         i+1's own input (before coupling) at t-1. It reads the input, not layer i+1's recurrent
                         state, so that the scan stays parallel.
State carried across chunks: modes, last coupling q per layer, and the feature / head-mean history the errors need.
All randomness comes from a torch.Generator seeded with SEED. Inference only; use torch.no_grad().
"""
import math

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

SEED = 20261030
DT = 0.01
FEAT = 44
N_IN = FEAT + 2
D = 128
N = 256
HID = 256
CLIP = 10.0
BANDS = ((8.0, 20.0), (4.0, 8.0), (0.5, 4.0), (0.01, 0.5))
HORIZONS = (10, 50, 200, 800)        # frames at 100 Hz: +0.1, +0.5, +2, +8 s
LOGVAR_MIN, LOGVAR_MAX = -8.0, 4.0
SCAN_BLOCK = 75


def _lin(g, n_in, n_out, bias=True):
    """nn.Linear with the torch default bound 1/sqrt(n_in), drawn from generator `g`."""
    m = nn.Linear(n_in, n_out, bias=bias)
    b = 1.0 / math.sqrt(n_in)
    with torch.no_grad():
        m.weight.copy_(torch.empty(n_out, n_in).uniform_(-b, b, generator=g))
        if bias:
            m.bias.copy_(torch.empty(n_out).uniform_(-b, b, generator=g))
    return m


def scan(lam_log, u, h0, block=SCAN_BLOCK):
    """h_t = exp(lam_log) h_{t-1} + u_t. Two-level scan: sequential inside blocks (batched over blocks), then over block ends."""
    B, T, M = u.shape
    pad = (-T) % block
    if pad:
        u = torch.cat([u, u.new_zeros(B, pad, M)], 1)
    nb = u.shape[1] // block
    lam = torch.exp(lam_log)
    ub = u.reshape(B * nb, block, M)
    h, loc = torch.zeros(B * nb, M, dtype=u.dtype), []
    for k in range(block):
        h = lam * h + ub[:, k]
        loc.append(h)
    loc = torch.stack(loc, 1).reshape(B, nb, block, M)
    lam_block = torch.exp(lam_log * block)
    carry, carries = h0, []
    for c in range(nb):
        carries.append(carry)
        carry = lam_block * carry + loc[:, c, -1]
    carries = torch.stack(carries, 1)
    pw = torch.exp(lam_log[None, :] * torch.arange(1, block + 1, dtype=torch.float32)[:, None])
    out = (loc + pw[None, None] * carries[:, :, None]).reshape(B, nb * block, M)[:, :T]
    return out, out[:, -1]


def sample_modes(g, band, n=N):
    """(theta, nu) for n modes: f log-uniform in band, Q log-uniform in 2..8."""
    lo, hi = band
    f = torch.exp(torch.empty(n).uniform_(math.log(lo), math.log(hi), generator=g))
    q = torch.exp(torch.empty(n).uniform_(math.log(2.0), math.log(8.0), generator=g))
    tau = q / (math.pi * f)
    return 2 * math.pi * f * DT, DT / tau


class Layer(nn.Module):
    def __init__(self, g, band, coupled):
        super().__init__()
        self.band = band
        theta, nu = sample_modes(g, band)
        self.theta = nn.Parameter(theta)
        self.nu_log = nn.Parameter(torch.log(nu))
        self.ln1, self.ln2 = nn.LayerNorm(D), nn.LayerNorm(D)
        self.inp = _lin(g, D, 2 * N, bias=False)
        self.out = _lin(g, 2 * N, D, bias=False)
        self.skip = nn.Parameter(torch.empty(D).uniform_(-0.1, 0.1, generator=g))
        self.mlp_in = _lin(g, D, 2 * HID)
        self.mlp_out = _lin(g, HID, D)
        self.head = _lin(g, D, 2 * FEAT)
        self.couple = _lin(g, FEAT, D, bias=False) if coupled else None
        self.prec = _lin(g, D, FEAT) if coupled else None

    def lam_log(self):
        return torch.complex(-torch.exp(self.nu_log), self.theta)

    @torch.no_grad()
    def clamp_modes(self):
        lo, hi = self.band
        self.theta.clamp_(2 * math.pi * lo * DT, 2 * math.pi * hi * DT)

    def freqs_hz(self):
        return (self.theta / (2 * math.pi * DT)).detach()

    def forward(self, x, h0, q_shift):
        if self.couple is not None:
            x = x + self.couple(q_shift)
        ll = self.lam_log()
        z = self.inp(self.ln1(x))
        gain = torch.sqrt(1 - torch.exp(2 * ll.real))
        h, hT = scan(ll, torch.complex(z[..., :N], z[..., N:]) * gain, h0)
        x = x + self.out(torch.cat([h.real, h.imag], -1)) + self.skip * x
        g, v = self.mlp_in(self.ln2(x)).chunk(2, -1)
        x = x + self.mlp_out(F.gelu(g) * v)
        mean, logvar = self.head(x).chunk(2, -1)
        return x, h, hT, mean, logvar.clamp(LOGVAR_MIN, LOGVAR_MAX)


class Core(nn.Module):
    def __init__(self, seed=SEED, phase=True):
        super().__init__()
        g = torch.Generator().manual_seed(seed)
        self.phase = phase
        self.embed = _lin(g, N_IN, D)
        self.layers = nn.ModuleList(Layer(g, b, i > 0) for i, b in enumerate(BANDS))

    def n_params(self):
        return sum(p.numel() for p in self.parameters())

    def clamp_modes(self):
        for L in self.layers:
            L.clamp_modes()

    def init_state(self, B=1):
        return {"n": 0,
                "h": [torch.zeros(B, N, dtype=torch.complex64) for _ in BANDS],
                "q": [torch.zeros(B, FEAT) for _ in BANDS],
                "f": torch.zeros(B, HORIZONS[-1], FEAT),
                "mean": [torch.zeros(B, 2 * h, FEAT) for h in HORIZONS]}

    def forward(self, f, state):
        """f: (B, T, 46) -> (out, state). out: per layer dict h (B,T,N complex), mean, logvar, err (B,T,44)."""
        if not self.phase:
            f = torch.cat([f[..., :FEAT], torch.zeros_like(f[..., FEAT:])], -1)
        B, T, _ = f.shape
        n0, hf = state["n"], state["f"].shape[1]
        fh = torch.cat([state["f"], f[..., :FEAT]], 1)
        cs = torch.cat([torch.zeros(B, 1, FEAT), fh.cumsum(1)], 1)
        idx = torch.arange(T)
        x, q, out, st = self.embed(f), None, [], {"h": [], "q": [], "mean": []}
        for i, (L, hz) in enumerate(zip(self.layers, HORIZONS)):
            q_shift = None
            if i > 0:
                q_shift = torch.cat([state["q"][i][:, None], q[:, :-1]], 1)
                st["q"].append(q[:, -1])
            else:
                st["q"].append(state["q"][0])
            x, h, hT, mean, logvar = L(x, state["h"][i], q_shift)
            # err: the prediction made 2h-1 frames ago, scored against the window of the last h frames; 0 until 2h frames exist
            m_all = torch.cat([state["mean"][i], mean], 1)
            win = (cs[:, hf + idx + 1] - cs[:, hf + idx + 1 - hz]) / hz
            err = (win - m_all[:, 1:1 + T]) * ((n0 + idx) >= 2 * hz - 1).float()[None, :, None]
            out.append({"h": h, "mean": mean, "logvar": logvar, "err": err})
            st["h"].append(hT)
            st["mean"].append(m_all[:, -2 * hz:])
            if i + 1 < len(self.layers):
                q = err * torch.exp(-self.layers[i + 1].prec(x).clamp(LOGVAR_MIN, LOGVAR_MAX))
        st["n"], st["f"] = n0 + T, fh[:, -state["f"].shape[1]:]
        return out, st
