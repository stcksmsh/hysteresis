"""T-M3 toy world (docs/BODY_BRAIN_PLAN.md §6): synthetic pulse-train music with slow tempo drift, the reduced cortex, a batch of arms, the online cerebellum.

TOY ONLY. Importing this module sets `core.N = 16` (16 modes per layer) and `core_b7.BLOCK = 50` (a 0.5 s block, so the cortex and a policy decision share one
epoch); do not import it in a process that also needs the real B7 epoch 6. Provisional servo model (Feetech STS3215 12 V assumed; kp, rotor inertia,
damping 1.5, acceleration share 0.25).
"""
import math
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from scipy.signal import lfilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "brain"))
import core  # noqa: E402
import core_b7  # noqa: E402

core.N = 16
core_b7.BLOCK = 50
import arm_sim  # noqa: E402
import babble  # noqa: E402
import cerebellum as CB  # noqa: E402
import cpg  # noqa: E402
from make_arm import NEUTRAL_DEG  # noqa: E402

DT = 0.01
BLOCK = 50
P = 30
FEAT = core.FEAT
HZ_L = core.HORIZONS


# ---------------------------------------------------------------------------------------------------------------- music
class PulseMusic:
    """Endless 44-channel feature stream at 100 Hz: a pulse train whose log-tempo is an OU process (time constant 30 s, SD 0.12) around `bpm0`,
    every 4th pulse stronger; channels 0-21 carry the pulse envelope (decay 60 ms) plus noise, channels 22-43 noise only. `pulse_phase` is the pulse
    cycle in radians (the truth the phase-locking check uses). Standardised with fixed constants."""
    MU, SD = None, None

    def __init__(self, seed, bpm0=110.0):
        self.rng = np.random.default_rng(seed)
        self.bpm0, self.x, self.phase, self.env, self.k = bpm0, 0.0, 0.0, 0.0, 0
        self.gain = np.random.default_rng(777).uniform(0.5, 1.5, 22)

    def next(self, n):
        a = math.exp(-DT / 30.0)
        # OU log-tempo (vectorised AR(1))
        noise = math.sqrt(1 - a * a) * 0.12 * self.rng.standard_normal(n)
        x, _ = lfilter([1.0], [1.0, -a], noise, zi=[a * self.x])
        self.x = float(x[-1])
        bpm = np.clip(self.bpm0 * np.exp(x), 70.0, 160.0)
        ph = self.phase + np.cumsum(bpm / 60.0 * DT)
        idx = np.floor(ph).astype(int)
        prev = np.concatenate([[math.floor(self.phase)], idx[:-1]])
        onset = idx > prev
        amp = np.where(idx % 4 == 0, 1.0, 0.6) * onset
        env, _ = lfilter([1.0], [1.0, -math.exp(-DT / 0.06)], amp, zi=[self.env * math.exp(-DT / 0.06)])
        self.env, self.phase = float(env[-1]), float(ph[-1])
        f = np.empty((n, FEAT), np.float32)
        f[:, :22] = env[:, None] * self.gain[None] + 0.3 * self.rng.standard_normal((n, 22))
        f[:, 22:] = 0.3 * self.rng.standard_normal((n, 22))
        if PulseMusic.MU is None:
            ref = PulseMusic.__new__(PulseMusic)
            PulseMusic.__init__(ref, 12345)
            PulseMusic.MU, PulseMusic.SD = 0.0, 1.0
            r = ref.next(60000)
            PulseMusic.MU, PulseMusic.SD = r[0].mean(0), r[0].std(0) + 1e-6
        f = (f - PulseMusic.MU) / PulseMusic.SD
        return f.astype(np.float32), (2 * np.pi * ph).astype(np.float64), bpm


def cortex_input(f):
    """(B, T, 44) -> (B, T, 46): the two grid-phase columns are zero in the toy (phase=False zeroes them anyway)."""
    return torch.cat([f, torch.zeros(*f.shape[:2], 2, dtype=f.dtype)], -1)


# ---------------------------------------------------------------------------------------------------------------- cortex
def make_cortex(seed=0):
    torch.manual_seed(seed)
    return core_b7.Core7(seed=core.SEED + seed, phase=False, skip_taps=10, hippocampus=False)


def pretrain_cortex(model, steps=300, batch=8, chunk=2400, lr=1e-3, seed=1, log=print):
    """Brief training on the synthetic stream (beta-NLL, beta 0.5), then freeze. Fresh state per chunk (a chunk starts on a block edge)."""
    opt = torch.optim.Adam(model.parameters(), lr)
    music = [PulseMusic(seed * 1000 + i, bpm0=float(np.random.default_rng(seed + i).uniform(80, 140))) for i in range(batch)]
    model.grad_checkpoint = True
    model.train()
    for s in range(steps):
        x = cortex_input(torch.from_numpy(np.stack([m.next(chunk)[0] for m in music])))
        out, _ = model(x, model.init_state(batch))
        loss = music_loss(out, x)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        model.clamp_modes()
        if s % 25 == 0 or s == steps - 1:
            log(f"pretrain {s + 1}/{steps} loss {float(loss):.4f}")
    for p in model.parameters():
        p.requires_grad_(False)
    model.eval()
    model.grad_checkpoint = False
    return model


def music_loss(out, x, beta=0.5):
    """Mean over layers of the beta-NLL of the four heads against the future windows of x (B, T, >=44) that lie inside it (train.chunk_terms
    without its look-ahead frames: a target window needs t + 2h <= T)."""
    B, T = x.shape[:2]
    cs = torch.cat([torch.zeros(B, 1, FEAT), x[..., :FEAT].cumsum(1)], 1)
    t = torch.arange(T)
    total = 0.0
    for o, hz in zip(out, HZ_L):
        m = T - 2 * hz + 1
        if m <= 0:
            continue
        y = (cs[:, t[:m] + 2 * hz] - cs[:, t[:m] + hz]) / hz
        lv = o["logvar"][:, :m]
        e = 0.5 * (lv + (y - o["mean"][:, :m]) ** 2 * torch.exp(-lv) + math.log(2 * math.pi))
        total = total + (e * torch.exp(beta * lv).detach()).mean()
    return total


def causal_surprisal(out, lv_state, n0):
    """Per frame and row: the sum over the four layers of the plain Gaussian NLL of the prediction that was made 2h-1 frames ago, scored now
    (`out[i]['err']` against the earlier log-variance), zero until 2h frames exist. lv_state: list of (B, 2h, 44) or None (first block); returns
    (S (B, Tb), new lv_state)."""
    B, Tb = out[0]["err"].shape[:2]
    idx = torch.arange(Tb)
    s = torch.zeros(B, Tb)
    new = []
    for i, hz in enumerate(HZ_L):
        prev = lv_state[i] if lv_state is not None else torch.zeros(B, 2 * hz, FEAT)
        lv_all = torch.cat([prev, out[i]["logvar"]], 1)
        lvp = lv_all[:, 1:1 + Tb]
        e = 0.5 * (lvp + out[i]["err"] ** 2 * torch.exp(-lvp) + math.log(2 * math.pi)).mean(-1)
        s = s + e * ((n0[:, None] + idx[None]) >= 2 * hz - 1).float()
        new.append(lv_all[:, -2 * hz:])
    return s, new


# ---------------------------------------------------------------------------------------------------------------- body
def rest_proprio():
    """The proprioception of the arm at rest in the neutral pose (position, velocity, load), settled."""
    sim = arm_sim.ArmSim()
    sim.reset(NEUTRAL_DEG)
    for _ in range(400):
        p = sim.step(NEUTRAL_DEG)
    return np.concatenate([p["pos_deg"], p["vel_deg_s"], p["load_nm"]]).astype(np.float32)


class ArmBatch:
    """E arms with their pattern generators. `command(u)` sets every generator from u (E, 4, 5) in [0, 1]; `step()` runs one 0.1 s (10 control steps)."""

    def __init__(self, E, seed):
        self.E = E
        rng = np.random.default_rng(seed)
        self.sims, self.gens = [arm_sim.ArmSim() for _ in range(E)], [cpg.CPG() for _ in range(E)]
        for sim, gen in zip(self.sims, self.gens):
            start = np.array(NEUTRAL_DEG) + rng.uniform(-10, 10, 5)
            sim.reset(start)
            gen.reset(start)
        self.last = np.zeros((E, 15), np.float32)

    def command(self, u):
        for g, ue in zip(self.gens, u):
            g.command(*babble.to_command(ue))

    def step(self, n=10):
        obs = np.empty((self.E, n, 15), np.float32)
        tgt = np.empty((self.E, n, 5), np.float32)
        energy = np.zeros(self.E)
        for e, (sim, gen) in enumerate(zip(self.sims, self.gens)):
            for k in range(n):
                t = gen.step()
                p = sim.step(t)
                obs[e, k] = np.concatenate([p["pos_deg"], p["vel_deg_s"], p["load_nm"]])
                tgt[e, k] = t
                energy[e] += sim.power_w * DT
        self.last = obs[:, -1]
        return obs, tgt, energy


# ---------------------------------------------------------------------------------------------------------------- cerebellum (online)
class OnlineCerebellum:
    """The M1 bundle run one control step at a time for E arms, with the same inputs as training (obs, target, last 10 targets). `error` is the h = +10 ms
    prediction error of the previous step in standardised units (15), `nll` its mean Gaussian NLL (the self-surprisal). `learn()` takes one Adam
    step on the last `window` steps (online learning; this is what the learning progress measures)."""

    def __init__(self, bundle, E, lr=3e-4, window=500):
        self.net, self.st, _, _ = CB.load_bundle(bundle)
        self.net.train()
        self.opt = torch.optim.Adam(self.net.parameters(), lr)
        self.E, self.window = E, window
        self.h = torch.zeros(1, E, self.net.rnn.hidden_size)
        self.hist = []                       # per step: (x (E, NIN), obs (E, 15))
        self.prev = None                     # (mean_h1 (E, 15), logvar_h1 (E, 15)) predicted at the previous step, with obs_prev
        self.omu, self.osd = torch.from_numpy(self.st.omu).float(), torch.from_numpy(self.st.osd).float()
        self.eff = np.zeros((E, CB.EFF, 5), np.float32)
        self.dsd1 = torch.from_numpy(self.st.dsd[0]).float()

    def _x(self, obs, tgt):
        o = (torch.from_numpy(obs) - self.omu) / self.osd
        t = (torch.from_numpy(tgt) - torch.from_numpy(self.st.tmu).float()) / torch.from_numpy(self.st.tsd).float()
        eff = (torch.from_numpy(self.eff) - torch.from_numpy(self.st.tmu).float()) / torch.from_numpy(self.st.tsd).float()
        return torch.cat([o, t, eff.flatten(1)], -1)

    @torch.no_grad()
    def step(self, obs, tgt):
        """obs, tgt: (E, 15), (E, 5) at this control step. -> error (E, 15), nll (E,); then predicts the next step."""
        x = self._x(obs, tgt)
        err, nll = torch.zeros(self.E, 15), torch.zeros(self.E)
        if self.prev is not None:
            o_prev, m, lv = self.prev
            y = ((torch.from_numpy(obs) - o_prev) / self.dsd1)
            err = (y - m).clamp(-5, 5)
            nll = (0.5 * (lv + (y - m) ** 2 * torch.exp(-lv) + math.log(2 * math.pi))).mean(-1)
        h, self.h = self.net.rnn(torch.tanh(self.net.inp(x))[:, None], self.h)
        o = (self.net.head(h[:, 0]) + self.net.skip(x)).view(self.E, len(CB.HORIZONS), 15, 2)
        self.prev = (torch.from_numpy(obs).clone(), o[:, 0, :, 0], o[:, 0, :, 1].clamp(-8, 4))
        self.eff = np.concatenate([tgt[:, None].astype(np.float32), self.eff[:, :-1]], 1)
        self.hist.append((x, torch.from_numpy(obs).clone()))
        self.hist = self.hist[-(self.window + 10):]
        return err, nll

    def learn(self):
        """One online gradient step on the stored window (training mode, zero start state, loss after the first CB.WARM steps)."""
        if len(self.hist) < CB.WARM + 30:
            return None
        X = torch.stack([h[0] for h in self.hist], 1)                    # (E, T, NIN)
        O = torch.stack([h[1] for h in self.hist], 1)
        T = X.shape[1]
        Y = torch.zeros(self.E, T, len(CB.HORIZONS), 15)
        M = torch.zeros(self.E, T)
        for i, hz in enumerate(CB.HORIZONS):
            Y[:, :T - hz, i] = (O[:, hz:] - O[:, :T - hz]) / torch.from_numpy(self.st.dsd[i]).float()
        M[:, CB.WARM:T - max(CB.HORIZONS)] = 1.0
        mean, lv = self.net(X)
        loss = CB.beta_nll(mean, lv, Y, M)
        self.opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.net.parameters(), 1.0)
        self.opt.step()
        return float(loss)
