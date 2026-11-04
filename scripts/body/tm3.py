"""T-M3 (docs/BODY_BRAIN_PLAN.md §6): basal ganglia, dopamine and PPO on the toy world of tm3_world.py. TOY ONLY.

Per 0.5 s block (= one cortex block, one program decision) and per 0.1 s step (10 Hz motor-cortex modulation, one reward, one value):
  program   striatum scores Go - NoGo per program from z; softmax picks one (keeping the current one is free, a switch costs c_sw * R0 in the reward);
            gating is literal: only the chosen program's vector (a_p = theta_k + sigma_p * eps, learned with the policy) reaches the generators.
  motor     the motor cortex adds a modulation of at most +-20 % of each command range at 10 Hz: u = clip(sigmoid(a_p) + 0.2 * tanh(a_mc), 0, 1).
  reward    r = (S_still - S_moving) + beta * R0 * LP / LP0 - lambda * R0 * E / E0 - c_sw * R0 [switch]  (+ gamma * R0 * SYNC / SYNC0 with the flag on),
            R0, LP0, E0, SYNC0 = mean magnitudes measured at initialisation (calibration), so beta, lambda, c_sw, gamma are relative to the toy's
            mean |S_still - S_moving| there.
  dopamine  delta_t = r_t + gamma V_{t+1} - V_t (logged).
PPO: hybrid action (program, program vector, modulation), clip 0.2, GAE lambda 0.95, gamma 0.99 per 0.1 s.
Provisional servo model (Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5, acceleration share 0.25).
"""
import copy
import json
import math
import time
from dataclasses import asdict, dataclass, field

import numpy as np
import torch
import torch.nn as nn
from scipy.signal import hilbert, sosfiltfilt, butter

import babble
import m3_cortex as M
import tm3_world as W

K = 8
DIN = 2 * 128 + 15 + 15 + 1
SIGMA_P = 0.3
MOD = 0.2
STEP = 10                     # control steps per 0.1 s
BLOCK_STEPS = 5               # 0.1 s steps per 0.5 s block


@dataclass
class Config:
    beta: float = 0.0
    lam: float = 0.0
    csw: float = 0.0
    gamma_sync: float = 0.0
    sync: bool = False
    E: int = 8
    H: int = 300              # 0.1 s steps per iteration (30 s)
    iters: int = 100
    seed: int = 0
    lr: float = 3e-4
    relay_lr: float = 1e-3
    ent: float = 0.01
    ppo_epochs: int = 4
    clip: float = 0.2
    gae_lambda: float = 0.95
    gamma: float = 0.99


# ---------------------------------------------------------------------------------------------------------------- policy
class Policy(nn.Module):
    def __init__(self, seed=0):
        super().__init__()
        g = torch.Generator().manual_seed(seed)
        mlp = lambda i, o: nn.Sequential(nn.Linear(i, 128), nn.Tanh(), nn.Linear(128, o))
        self.go, self.nogo, self.critic = mlp(DIN, K), mlp(DIN, K), mlp(DIN, 1)
        self.mc = mlp(DIN + K, 20)
        self.logstd = nn.Parameter(torch.full((20,), -1.0))
        # programs: K babbling commands (fixed seed), as logits of the unit command cube
        u0 = np.clip(np.stack([babble.ou_commands(np.random.default_rng(1234 + i), 1)[0] for i in range(K)]), 0.02, 0.98)       # fixed seeds, (K, 4, 5)
        self.theta = nn.Parameter(torch.from_numpy(np.log(u0 / (1 - u0))).float().reshape(K, 20))
        self.go[-1].weight.data.mul_(0.1)
        self.nogo[-1].weight.data.mul_(0.1)

    def scores(self, z):
        return self.go(z) - self.nogo(z)

    def mc_mean(self, z, k):
        return self.mc(torch.cat([z, nn.functional.one_hot(k, K).float()], -1))


def executed_u(a_p, a_mc):
    """(.., 20), (.., 20) -> u (.., 4, 5): the only path from a policy action to a generator command."""
    u = torch.sigmoid(a_p) + MOD * torch.tanh(a_mc)
    return u.clamp(0, 1).reshape(*u.shape[:-1], 4, 5)


def reward_terms(d, lp, en, switch, cal, cfg, sync=None):
    """The reward of one 0.1 s step from its pieces (all arrays of the same shape); `cal` = {R0, LP0, E0, SYNC0}."""
    r = d + cfg.beta * cal["R0"] * lp / cal["LP0"] - cfg.lam * cal["R0"] * en / cal["E0"] - cfg.csw * cal["R0"] * switch
    if cfg.sync and sync is not None:
        r = r + cfg.gamma_sync * cal["R0"] * sync / cal["SYNC0"]
    return r


def sync_value(vel, h3):
    """Phase-locking value over a window between the dominant joint's velocity phase and the phase of the L3 mode with the largest mean magnitude.
    vel (T, 5) deg/s, h3 (T, 16) complex. Returns a float in [0, 1]."""
    j = int(np.argmax((vel ** 2).sum(0)))
    v = vel[:, j] - vel[:, j].mean()
    if np.abs(v).max() < 1e-6:
        return 0.0
    m = int(np.argmax(np.abs(h3).mean(0)))
    return float(np.abs(np.mean(np.exp(1j * (np.angle(hilbert(v)) - np.angle(h3[:, m]))))))


# ---------------------------------------------------------------------------------------------------------------- state helpers
def rows(state, idx):
    """Slice batch rows of a (nested) cortex state."""
    B = len(state["n"])
    f = lambda v: [f(x) for x in v] if isinstance(v, list) else (v[idx] if torch.is_tensor(v) and v.dim() > 0 and v.shape[0] == B else v)
    return {k: f(v) for k, v in state.items()}


def cat_rows(a, b):
    f = lambda x, y: [f(p, q) for p, q in zip(x, y)] if isinstance(x, list) else (torch.cat([x, y]) if torch.is_tensor(x) and x.dim() > 0 else x)
    return {k: f(a[k], b[k]) for k in a}


# ---------------------------------------------------------------------------------------------------------------- the run
class Run:
    def __init__(self, cfg, cortex, bundle, cal=None, seed=None):
        self.cfg, self.cal = cfg, cal
        s = cfg.seed if seed is None else seed
        E = cfg.E
        self.rng = np.random.default_rng(s)
        self.cortex = cortex
        self.arms = W.ArmBatch(E, s)
        self.music = [W.PulseMusic(10_000 + 97 * s + i, bpm0=float(self.rng.uniform(85, 135))) for i in range(E)]
        self.cb_bundle = bundle
        self.cb = W.OnlineCerebellum(bundle, E)
        self.pol = Policy(s)
        self.opt = torch.optim.Adam(self.pol.parameters(), cfg.lr)
        self.relay_opt = torch.optim.Adam(cortex.prop.parameters(), cfg.relay_lr)
        self.still = torch.cat([(torch.from_numpy(W.rest_proprio()) - self.cb.omu) / self.cb.osd, torch.zeros(15)])
        self.state = cortex.core.init_state(2 * E)
        self.lv = None
        self.zx = torch.zeros(E, 256)
        self.prop_last, self.err_last, self.nll_last = torch.zeros(E, 15), torch.zeros(E, 15), torch.zeros(E)
        self.k_prev = torch.full((E,), -1, dtype=torch.long)
        self.a_p = self.pol.theta.detach()[torch.zeros(E, dtype=torch.long)].clone()
        self.nll_hist = [[] for _ in range(E)]          # per 0.1 s, per env: the cerebellum's mean NLL
        self.vel_hist = np.zeros((E, 200, 5), np.float32)
        self.h3_hist = np.zeros((E, 200, 16), np.complex64)
        self.t = 0

    # -- one block (0.5 s)
    @torch.no_grad()
    def block(self, deterministic=False, learn_cb=True, record=None):
        E, cfg = self.cfg.E, self.cfg
        feats, ph, bpm = zip(*[m.next(W.BLOCK) for m in self.music])
        f = torch.from_numpy(np.stack(feats))
        steps = []
        obs_b, err_b, nll_b, en_b = [], [], [], []
        for s in range(BLOCK_STEPS):
            prop_std = (torch.from_numpy(self.arms.last) - self.cb.omu) / self.cb.osd if self.t or s else torch.zeros(E, 15)
            z = torch.cat([self.zx, prop_std[:, :15], self.err_last, self.nll_last[:, None]], -1)
            decide = s == 0
            if decide:
                logits = self.pol.scores(z)
                dist = torch.distributions.Categorical(logits=logits)
                k = logits.argmax(-1) if deterministic else dist.sample()
                logp_k = dist.log_prob(k)
                eps = torch.zeros(E, 20) if deterministic else SIGMA_P * torch.randn(E, 20)
                self.a_p = self.pol.theta[k] + eps
                logp_p = torch.distributions.Normal(self.pol.theta[k], SIGMA_P).log_prob(self.a_p).sum(-1)
                switch = (k != self.k_prev).float() * (self.k_prev >= 0).float()
                self.k_prev, self.k_cur = k, k
                logp_dec = logp_k + logp_p
            else:
                switch, logp_dec = torch.zeros(E), torch.zeros(E)
            mu = self.pol.mc_mean(z, self.k_cur)
            std = self.pol.logstd.exp()
            a_mc = mu if deterministic else mu + std * torch.randn(E, 20)
            logp_mc = torch.distributions.Normal(mu, std).log_prob(a_mc).sum(-1)
            self.arms.command(executed_u(self.a_p, a_mc).numpy())
            obs, tgt, en = self.arms.step(STEP)
            errs, nlls = [], []
            for c in range(STEP):
                e, n = self.cb.step(obs[:, c], tgt[:, c])
                errs.append(e)
                nlls.append(n)
            errs, nlls = torch.stack(errs, 1), torch.stack(nlls, 1)
            self.err_last, self.nll_last = errs[:, -1], nlls[:, -1]
            obs_b.append(obs)
            err_b.append(errs)
            nll_b.append(nlls.mean(1))
            en_b.append(en)
            steps.append({"z": z, "k": self.k_cur.clone(), "a_p": self.a_p.clone(), "a_mc": a_mc, "decide": decide, "switch": switch,
                          "logp": logp_dec + logp_mc, "value": self.pol.critic(z)[:, 0]})
        obs = np.concatenate(obs_b, 1)                                                  # (E, 50, 15)
        err = torch.cat(err_b, 1)
        prop = torch.cat([(torch.from_numpy(obs) - self.cb.omu) / self.cb.osd, err], -1)
        x = W.cortex_input(f)
        out, st = self.cortex(torch.cat([x, x]), torch.cat([prop, self.still.expand(E, W.BLOCK, 30)]), self.state)
        s_all, self.lv = W.causal_surprisal(out, self.lv, self.state["n"])
        self.state = self.cortex.core.detach_state(st)
        d = (s_all[E:] - s_all[:E]).reshape(E, BLOCK_STEPS, STEP).mean(-1)                # S_still - S_moving per 0.1 s
        self.zx = torch.cat([out[2]["x"][:E, -1], out[3]["x"][:E, -1]], -1)
        vel = obs[..., 5:10]
        self.vel_hist = np.concatenate([self.vel_hist[:, W.BLOCK:], vel], 1)
        self.h3_hist = np.concatenate([self.h3_hist[:, W.BLOCK:], out[2]["h"][:E].numpy()], 1)
        sync = np.zeros(E)
        if cfg.sync:
            sync = np.array([sync_value(self.vel_hist[e], self.h3_hist[e]) for e in range(E)])
        # learning progress: mean NLL over the previous 10 s minus over the last 10 s, floored at 0 (per 0.1 s step)
        lp = np.zeros((E, BLOCK_STEPS))
        for e in range(E):
            self.nll_hist[e].extend(torch.stack(nll_b, 1)[e].tolist())
            h = self.nll_hist[e]
            for j in range(BLOCK_STEPS):
                n = len(h) - BLOCK_STEPS + j + 1
                if n >= 200:
                    lp[e, j] = max(0.0, float(np.mean(h[n - 200:n - 100]) - np.mean(h[n - 100:n])))
        if learn_cb and (self.t + 1) % 10 == 0:
            self.cb.learn()
        self.t += 1
        res = {"steps": steps, "d": d, "lp": torch.from_numpy(lp).float(), "en": torch.from_numpy(np.stack(en_b, 1)).float(), "sync": torch.from_numpy(sync).float(),
               "f": f, "prop": prop, "obs": obs, "pulse_phase": np.stack(ph), "nll": torch.stack(nll_b, 1)}
        if record is not None:
            record.append(res)
        return res


def collect(run, H, deterministic=False):
    """H 0.1 s steps (H divisible by 5) -> dict of tensors (T, E, ..) and the cortex inputs of the window."""
    blocks = [run.block(deterministic) for _ in range(H // BLOCK_STEPS)]
    cfg, cal = run.cfg, run.cal
    z, k, a_p, a_mc, dec, sw, lp_, v, d, lp, en, sy, logp = ([] for _ in range(13))
    for b in blocks:
        for j, s in enumerate(b["steps"]):
            z.append(s["z"]); k.append(s["k"]); a_p.append(s["a_p"]); a_mc.append(s["a_mc"]); dec.append(torch.tensor(float(s["decide"])))
            sw.append(s["switch"]); logp.append(s["logp"]); v.append(s["value"])
            d.append(b["d"][:, j]); lp.append(b["lp"][:, j]); en.append(b["en"][:, j]); sy.append(b["sync"])
    T = lambda x: torch.stack(x)
    out = {"z": T(z), "k": T(k), "a_p": T(a_p), "a_mc": T(a_mc), "dec": T(dec), "logp": T(logp), "value": T(v), "d": T(d), "lp": T(lp), "en": T(en),
           "switch": T(sw), "sync": T(sy)}
    out["f"] = torch.cat([b["f"] for b in blocks], 1)
    out["prop"] = torch.cat([b["prop"] for b in blocks], 1)
    out["nll"] = torch.cat([b["nll"] for b in blocks], 1)
    if cal is not None:
        out["r"] = reward_terms(out["d"], out["lp"], out["en"], out["switch"], cal, cfg, out["sync"])
    return out


def gae(r, v, last_v, gamma, lam):
    T = len(r)
    adv, g = torch.zeros_like(r), torch.zeros_like(last_v)
    for t in reversed(range(T)):
        nv = last_v if t == T - 1 else v[t + 1]
        delta = r[t] + gamma * nv - v[t]
        g = delta + gamma * lam * g
        adv[t] = g
    return adv, adv + v, None


def ppo_update(run, roll):
    cfg, pol = run.cfg, run.pol
    with torch.no_grad():
        last_v = pol.critic(torch.cat([run.zx, (torch.from_numpy(run.arms.last) - run.cb.omu) / run.cb.osd, run.err_last, run.nll_last[:, None]], -1))[:, 0]
    adv, ret, _ = gae(roll["r"], roll["value"], last_v, cfg.gamma, cfg.gae_lambda)
    delta = roll["r"] + cfg.gamma * torch.cat([roll["value"][1:], last_v[None]]) - roll["value"]
    T, E = roll["r"].shape
    z, k, a_p, a_mc, dec, old = (x.reshape(T * E, *x.shape[2:]) if x.dim() > 2 else x.reshape(T * E) for x in
                                 (roll["z"], roll["k"], roll["a_p"], roll["a_mc"], roll["dec"][:, None].expand(T, E), roll["logp"]))
    adv_f, ret_f = adv.reshape(-1), ret.reshape(-1)
    adv_f = (adv_f - adv_f.mean()) / (adv_f.std() + 1e-8)
    stats = {}
    for ep in range(cfg.ppo_epochs):
        perm = torch.randperm(T * E)
        for mb in perm.split(max(1, (T * E) // 4)):
            logits = pol.scores(z[mb])
            dist = torch.distributions.Categorical(logits=logits)
            kk = k[mb]
            lp_dec = dist.log_prob(kk) + torch.distributions.Normal(pol.theta[kk], SIGMA_P).log_prob(a_p[mb]).sum(-1)
            mu = pol.mc_mean(z[mb], kk)
            lp_mc = torch.distributions.Normal(mu, pol.logstd.exp()).log_prob(a_mc[mb]).sum(-1)
            new = lp_mc + lp_dec * dec[mb]
            ratio = torch.exp(new - old[mb])
            a = adv_f[mb]
            pl = -torch.min(ratio * a, ratio.clamp(1 - cfg.clip, 1 + cfg.clip) * a).mean()
            vl = 0.5 * (pol.critic(z[mb])[:, 0] - ret_f[mb]).pow(2).mean()
            ent = (dist.entropy() * dec[mb]).sum() / dec[mb].sum().clamp(min=1)
            loss = pl + 0.5 * vl - cfg.ent * ent
            run.opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(pol.parameters(), 0.5)
            run.opt.step()
    stats = {"policy_loss": float(pl), "value_loss": float(vl), "entropy": float(ent), "delta_mean": float(delta.mean()), "delta_abs": float(delta.abs().mean())}
    return stats


def train_relay(run, roll, state0):
    """One music-loss step on the proprioceptive relays: the moving rows over the whole window, cortex frozen."""
    cx = run.cortex
    x = W.cortex_input(roll["f"])
    st = copy.deepcopy(state0)
    cx.core.grad_checkpoint = True
    out, _ = cx(x, roll["prop"], st)
    loss = W.music_loss(out, x)
    run.relay_opt.zero_grad()
    loss.backward()
    run.relay_opt.step()
    cx.core.grad_checkpoint = False
    return float(loss)


def iteration(run, learn_policy=True):
    state0 = rows(run.state, torch.arange(run.cfg.E))
    roll = collect(run, run.cfg.H)
    # the moving rows' state at the window start (the cortex state continues across iterations)
    relay_loss = train_relay(run, roll, state0)
    info = {"relay_loss": relay_loss, "d_mean": float(roll["d"].mean()), "d_abs": float(roll["d"].abs().mean()), "lp_mean": float(roll["lp"].mean()),
            "en_mean": float(roll["en"].mean()), "sw_per_min": float(roll["switch"].sum() / run.cfg.E / (roll["d"].shape[0] / 600.0)),
            "cb_nll": float(roll["nll"].mean()), "sync_mean": float(roll["sync"].mean())}
    if learn_policy and run.cal is not None:
        info.update(ppo_update(run, roll))
        info["r_mean"] = float(roll["r"].mean())
    info["prog_hist"] = torch.bincount(roll["k"][roll["dec"] > 0].reshape(-1), minlength=K).tolist()
    return info, roll


# ---------------------------------------------------------------------------------------------------------------- evaluation
def plv(a, b):
    return float(np.abs(np.mean(np.exp(1j * (a - b)))))


def evaluate(run, n_ep=16, secs=120.0, skip=10.0, seed=999, surrogates=1000):
    """Fresh arms and songs, the policy's mean action (argmax program, no noise), cerebellum not learning, relay as trained.
    (a) S_still - S_moving per episode, bootstrap interval over episodes; (b) RMS joint speed; (c) pooled 1:1 phase-locking of the dominant joint's velocity
    to the pulse against circular-shift surrogates. Also programs used, switches per minute, selection entropy."""
    cfg = copy.deepcopy(run.cfg)
    cfg.E = n_ep
    ev = Run(cfg, run.cortex, run.cb_bundle, run.cal, seed=seed)
    ev.pol.load_state_dict(run.pol.state_dict())
    ev.cb.net.load_state_dict(run.cb.net.state_dict())
    rec = []
    for _ in range(int(secs / 0.5)):
        ev.block(deterministic=True, learn_cb=False, record=rec)
    sk = int(skip / 0.5)
    d = torch.cat([r["d"] for r in rec], 1)[:, sk * BLOCK_STEPS:]                         # (E, steps)
    per_ep = d.mean(1).numpy()
    rng = np.random.default_rng(0)
    bs = np.array([rng.choice(per_ep, len(per_ep)).mean() for _ in range(10000)])
    vel = np.concatenate([r["obs"][..., 5:10] for r in rec], 1)[:, sk * W.BLOCK:]          # (E, T, 5) deg/s
    ph = np.concatenate([r["pulse_phase"] for r in rec], 1)[:, sk * W.BLOCK:]
    rms = float(np.sqrt((vel ** 2).mean()))
    sos = butter(2, [0.3, 4.0], btype="band", fs=100, output="sos")
    vph, pph, dom = [], [], []
    for e in range(n_ep):
        j = int(np.argmax((vel[e] ** 2).sum(0)))
        dom.append(j)
        vph.append(np.angle(hilbert(sosfiltfilt(sos, vel[e, :, j]))))
        pph.append(ph[e] % (2 * np.pi))
    obs_plv = float(np.abs(np.mean(np.exp(1j * (np.concatenate(vph) - np.concatenate(pph))))))
    sur = []
    for _ in range(surrogates):
        sh = [np.roll(v, int(rng.integers(len(v) // 10, 9 * len(v) // 10))) for v in vph]
        sur.append(float(np.abs(np.mean(np.exp(1j * (np.concatenate(sh) - np.concatenate(pph)))))))
    p = (1 + sum(s >= obs_plv for s in sur)) / (1 + surrogates)
    ks = torch.cat([torch.stack([s["k"] for s in r["steps"] if s["decide"]], 1) for r in rec], 1)       # (E, decisions)
    cnt = torch.bincount(ks.reshape(-1), minlength=K).float()
    pr = cnt / cnt.sum()
    ent = float(-(pr[pr > 0] * pr[pr > 0].log()).sum())
    sw = float((ks[:, 1:] != ks[:, :-1]).float().sum() / n_ep / (secs / 60.0))
    res = {"a_mean": float(per_ep.mean()), "a_lo": float(np.percentile(bs, 2.5)), "a_hi": float(np.percentile(bs, 97.5)), "a_pass": bool(np.percentile(bs, 2.5) > 0),
           "b_rms_deg_s": rms, "b_per_joint": np.sqrt((vel ** 2).mean((0, 1))).tolist(), "b_pass": bool(rms >= 10.0),
           "c_plv": obs_plv, "c_surrogate_mean": float(np.mean(sur)), "c_surrogate_max": float(np.max(sur)), "c_p": float(p), "c_pass": bool(p < 0.01),
           "programs_used": int((cnt > 0).sum()), "program_counts": cnt.tolist(), "switches_per_min": sw, "selection_entropy_nats": ent,
           "dominant_joints": dom}
    res["pass"] = res["a_pass"] and res["b_pass"] and res["c_pass"]
    return res


def calibrate(run, iters=15, log=print):
    """Initialisation reference: the random initial policy for `iters` windows with the relay (and the cerebellum) learning but no policy update.
    R0 = mean |S_still - S_moving| per 0.1 s over the last third, LP0 = mean learning progress, E0 = mean energy per 0.1 s (Joule), SYNC0 = mean SYNC."""
    d_abs, lp, en, sy = [], [], [], []
    for i in range(iters):
        info, roll = iteration(run, learn_policy=False)
        log(f"calib {i + 1}/{iters} " + json.dumps({k: round(v, 5) for k, v in info.items() if isinstance(v, float)}))
        if i >= 2 * iters // 3:
            d_abs.append(info["d_abs"]); lp.append(info["lp_mean"]); en.append(info["en_mean"]); sy.append(info["sync_mean"])
    return {"R0": max(float(np.mean(d_abs)), 1e-4), "LP0": max(float(np.mean(lp)), 1e-6), "E0": max(float(np.mean(en)), 1e-6), "SYNC0": max(float(np.mean(sy)), 1e-3),
            "R0_raw": float(np.mean(d_abs))}
