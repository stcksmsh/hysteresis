"""M3d toy brain states (docs/BRAIN_SPEC.md 7.16 point 2). TOY ONLY. Provisional servo model elsewhere (Feetech STS3215 12 V assumed).

Generator, stated before the first run. An episode is 60 s of 44-channel synthetic features at 100 Hz, cut into 12 s segments. Per segment: a tempo bpm ~ U(80, 140)
(the pulse train of tm3_world.PulseMusic, every 4th pulse stronger, envelope decay 60 ms), a base log pulse gain ~ N(0, 0.5) and a base log noise gain ~ N(0, 0.2). Within a
segment two independent Ornstein-Uhlenbeck swings (SD 0.5 in log pulse gain, 0.25 in log noise gain, time constants tau ~ U(1, 4) s, one for the pulse gain, one for the noise gain) multiply the pulse
(channels 0-21) and the noise level (0.3 x gain, all 44 channels). Unpredictable noise raises the cortex's surprisal and so its arousal; the pulse gain moves the band power; the
tempo moves the L3 phase rate. Features are standardised with PulseMusic's constants. The brain state per 0.5 s block is the frozen T-M3 cortex's (tm3c.brain_state): arousal,
mean total surprisal, cos and sin of the L3 phase, log band power L1..L4 (8 numbers); the cortex listens to the song only.

    python m3d_toy.py OUT.npz [--n-train 16 --n-held 16]
"""
import argparse

import numpy as np
import torch
from scipy.signal import lfilter

import tm3_world as W
import tm3c

SEG, SECS = 12.0, 60.0
N_BLOCK = int(SECS / 0.5)


def _ou(rng, n, tau, sd=0.5):
    a = np.exp(-W.DT / tau)
    x = lfilter([1.0], [1.0, -a], np.sqrt(1 - a * a) * sd * rng.standard_normal(n))
    return x


def episode_features(seed):
    """-> (n, 44) float32 standardised features, truth dict (bpm, log pulse gain, log noise gain per frame)."""
    W.PulseMusic(1).next(10)                                    # sets PulseMusic.MU / SD
    rng = np.random.default_rng(seed)
    n, seg = int(SECS / W.DT), int(SEG / W.DT)
    k = int(np.ceil(n / seg))
    bpm = np.repeat(rng.uniform(80, 140, k), seg)[:n]
    la = np.repeat(rng.normal(0, 0.5, k), seg)[:n] + _ou(rng, n, rng.uniform(1, 4))
    ln = np.repeat(rng.normal(0, 0.2, k), seg)[:n] + _ou(rng, n, rng.uniform(1, 4), 0.25)
    ph = np.cumsum(bpm / 60.0 * W.DT)
    idx = np.floor(ph).astype(int)
    onset = idx > np.concatenate([[0], idx[:-1]])
    env = lfilter([1.0], [1.0, -np.exp(-W.DT / 0.06)], np.where(idx % 4 == 0, 1.0, 0.6) * onset)
    gain = np.random.default_rng(777).uniform(0.5, 1.5, 22)
    f = np.empty((n, W.FEAT), np.float32)
    f[:, :22] = (env * np.exp(la))[:, None] * gain[None] + 0.3 * np.exp(ln)[:, None] * rng.standard_normal((n, 22))
    f[:, 22:] = 0.3 * np.exp(ln)[:, None] * rng.standard_normal((n, 22))
    f = (f - W.PulseMusic.MU) / W.PulseMusic.SD
    return f.astype(np.float32), {"bpm": bpm, "log_pulse": la, "log_noise": ln}


@torch.no_grad()
def brain_states(cortex, feats):
    """feats (E, n, 44) -> y (E, blocks, 8), phi_end (E, blocks), omega (E, blocks) (L3 phase at the block end, rad, and its rate, rad/s)."""
    E = len(feats)
    x_all = W.cortex_input(torch.from_numpy(feats))
    state, lv, arousal = cortex.init_state(E), None, torch.zeros(E)
    ys, ph, om = [], [], []
    for b in range(feats.shape[1] // W.BLOCK):
        out, st = cortex(x_all[:, b * W.BLOCK:(b + 1) * W.BLOCK], state)
        s_all, lv = W.causal_surprisal(out, lv, state["n"])
        state = cortex.detach_state(st)
        y, arousal, p, o = tm3c.brain_state(out, s_all, arousal)
        ys.append(y)
        ph.append(p)
        om.append(o)
    return torch.stack(ys, 1).numpy(), torch.stack(ph, 1).numpy(), torch.stack(om, 1).numpy()


def build(cortex_pt, n_train, n_held):
    cortex = W.make_cortex(0)
    cortex.load_state_dict(torch.load(cortex_pt))
    cortex.eval()
    seeds = [100 + i for i in range(n_train)] + [900 + i for i in range(n_held)]
    feats = np.stack([episode_features(s)[0] for s in seeds])
    y, phi, om = brain_states(cortex, feats)
    return dict(seeds=np.array(seeds), y=y, phi=phi, omega=om, n_train=n_train)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--cortex", default="/secondary/hyst-data/body/m3c/cortex.pt")
    ap.add_argument("--n-train", type=int, default=16)
    ap.add_argument("--n-held", type=int, default=16)
    a = ap.parse_args()
    torch.set_num_threads(4)
    d = build(a.cortex, a.n_train, a.n_held)
    np.savez(a.out, **d)
    y = d["y"]
    print("y", y.shape, "mean", y.mean((0, 1)).round(3), "sd", y.std((0, 1)).round(3))
    print("within-episode sd (mean over episodes)", y.std(1).mean(0).round(3))
