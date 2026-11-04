"""M3c toy (docs/BRAIN_SPEC.md §7.15): learning to move by legibility. TOY ONLY; T-M3 (tm3.py) is untouched.

Reward r = legibility - lambda*E (+ beta*LP), per 0.1 s step (tm3.reward_terms with R0 = 1: legibility is in standardised units, where the mean predictor's loss is 1).
  brain state (target of the observer, per 0.5 s block, 8 numbers, standardised by the calibration's mean and SD): arousal (total surprisal through a rise tau 1 s /
             decay tau 8 s follower, value at the block end), mean total surprisal, cos and sin of the L3 phase (the phase of the L3 mode with the largest block-mean
             magnitude, frames averaged), log band power of L1..L4 (mean over the 16 modes of |h|^2, block mean). The cortex is the frozen toy cortex of tm3_world
             listening to the synthetic song only (no proprioception, relays zero).
  observer   MLP 31 -> 64 -> 64 -> 8 (tanh), mean squared error on the standardised targets, Adam 1e-3, batch 128, 30 steps per iteration from a replay buffer of the
             last 4,000 training blocks (training episodes only), descriptors standardised by the calibration's mean and SD. Input = the 31 body-study descriptors
             (bdesc.py, wrist roll excluded) of the last 2 s of joint positions; nothing from the brain reaches it. Legibility of a block = -(its loss under the observer as it
             stands at the start of the iteration); before 2 s of movement exist a block gets the mean predictor's value, -1.
  spinal     tm3_world's generators plus phase coupling to L3: dphase_i/dt += kappa_i * sin(phi_L3 - phase_i), kappa_i = KAPPA_MAX * relu(tanh(a_i)) in [0, KAPPA_MAX],
             KAPPA_MAX = 2 pi rad/s (a 1 Hz capture range), a = five extra outputs of the motor cortex (bias -2 at start, so kappa is mostly 0). phi_L3 is the last
             measured phase extrapolated at its last measured rate (causal). kappa = 0 is exactly the old generator (CPGK.step adds 0.0).
Kept: 8 programs with Go/NoGo selection, switch cost, entropy bonus, (d)-style program check, critic, dopamine delta (tm3.ppo_update unchanged).
selection_stats, nonroll_stats and boot_ci are copied from body-m3b commit d160afd (tm3b.py).
Provisional servo model (Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5, acceleration share 0.25).
"""
import copy
import math

import numpy as np
import torch
import torch.nn as nn
from scipy.signal import butter, hilbert, sosfiltfilt

import bdesc
import cpg
import m3_cortex as M
import tm3
import tm3_world as W

ROLL = 4
NON_ROLL = [0, 1, 2, 3]
KAPPA_MAX = 2 * math.pi
K = tm3.K
N_Y = 8
OBS_HIDDEN = 64                                              # try 2 sets 16 (run_tm3c.py --obs-hidden)
OBS_LR, OBS_BATCH, OBS_STEPS, OBS_BUF = 1e-3, 128, 30, 4000
READY_FRAMES = 201                                          # 2.00 s of 100 Hz positions
BASELINE_LEG = -1.0                                         # the mean predictor's loss on standardised targets


# ---------------------------------------------------------------------------------------------------------------- spinal coupling
class CPGK(cpg.CPG):
    def step(self, phi=None, kappa=None):
        if phi is not None and kappa is not None:
            self.phase = self.phase + self.dt * np.asarray(kappa, float) * np.sin(phi - self.phase)
        return super().step()


class ArmBatchC(W.ArmBatch):
    def __init__(self, E, seed):
        super().__init__(E, seed)
        rng = np.random.default_rng(seed)                   # the parent's start poses (one draw per environment, in order), for the coupled generators
        self.gens = [CPGK() for _ in range(E)]
        for gen in self.gens:
            gen.reset(np.array(W.NEUTRAL_DEG) + rng.uniform(-10, 10, 5))

    def step(self, n=10, phi=None, omega=None, kappa=None):
        obs = np.empty((self.E, n, 15), np.float32)
        tgt = np.empty((self.E, n, 5), np.float32)
        energy = np.zeros(self.E)
        for e, (sim, gen) in enumerate(zip(self.sims, self.gens)):
            for k in range(n):
                t = gen.step(None if phi is None else phi[e] + omega[e] * W.DT * (k + 1), None if kappa is None else kappa[e])
                p = sim.step(t)
                obs[e, k] = np.concatenate([p["pos_deg"], p["vel_deg_s"], p["load_nm"]])
                tgt[e, k] = t
                energy[e] += sim.power_w * W.DT
        self.last = obs[:, -1]
        return obs, tgt, energy


class PolicyC(tm3.Policy):
    """tm3.Policy with the motor cortex's output widened from 20 to 25: the last five are the coupling a (bias -2)."""

    def __init__(self, seed=0):
        super().__init__(seed)
        g = torch.Generator().manual_seed(seed + 1)
        self.mc = nn.Sequential(nn.Linear(tm3.DIN + K, 128), nn.Tanh(), nn.Linear(128, 25))
        self.mc[-1].bias.data[20:] = -2.0
        self.logstd = nn.Parameter(torch.full((25,), -1.0))


def kappa_of(a):
    """(.., 5) motor cortex output -> coupling strength rad/s in [0, KAPPA_MAX]."""
    return KAPPA_MAX * torch.relu(torch.tanh(a))


class Observer(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(bdesc.N_DESC, OBS_HIDDEN), nn.Tanh(), nn.Linear(OBS_HIDDEN, OBS_HIDDEN), nn.Tanh(), nn.Linear(OBS_HIDDEN, N_Y))

    def forward(self, x):
        return self.net(x)


# ---------------------------------------------------------------------------------------------------------------- brain state
def brain_state(out, s_frames, arousal):
    """One block of cortex outputs -> (y (E, 8) raw, new arousal (E,), L3 phase at the block end (E,), L3 rate rad/s (E,)). s_frames (E, 50) total surprisal."""
    E, T = s_frames.shape
    a = arousal.clone()
    for t in range(T):
        s = s_frames[:, t]
        tau = torch.where(s > a, torch.tensor(1.0), torch.tensor(8.0))
        a = a + (s - a) * (W.DT / tau)
    h3 = out[2]["h"]                                                       # (E, T, 16) complex
    m = h3.abs().mean(1).argmax(-1)
    hm = h3[torch.arange(E), :, m]                                         # (E, T)
    ang = torch.angle(hm)
    unw = torch.from_numpy(np.unwrap(ang.numpy(), axis=1))
    omega = (unw[:, -1] - unw[:, 0]) / ((T - 1) * W.DT)
    power = torch.stack([(o["h"].abs() ** 2).mean(-1).mean(1) for o in out], -1).clamp(min=1e-8).log()      # (E, 4)
    y = torch.cat([a[:, None], s_frames.mean(1)[:, None], torch.cos(ang).mean(1)[:, None], torch.sin(ang).mean(1)[:, None], power], -1)
    return y, a, ang[:, -1], omega.clamp(-2 * math.pi * 4, 2 * math.pi * 4)


class RunC(tm3.Run):
    def __init__(self, cfg, cortex, bundle, cal=None, seed=None):
        super().__init__(cfg, cortex, bundle, cal, seed)
        E = cfg.E
        s = cfg.seed if seed is None else seed
        self.arms = ArmBatchC(E, s)
        self.pol = PolicyC(s)
        self.opt = torch.optim.Adam(self.pol.parameters(), cfg.lr)
        self.state = cortex.core.init_state(E)
        self.obs = Observer()
        self.obs_opt = torch.optim.Adam(self.obs.parameters(), OBS_LR)
        self.stats = None                                   # {dmu, dsd, ymu, ysd} numpy, set by calibration
        self.pending = []                                   # (raw desc (n, 31), raw y (n, 8)) of the blocks since the last observer update
        self.buf_x, self.buf_y = torch.zeros(0, bdesc.N_DESC), torch.zeros(0, N_Y)
        self.collect_obs = True
        self.pos_hist = np.zeros((E, READY_FRAMES, 5), np.float32)
        self.frames = 0
        self.arousal = torch.zeros(E)
        self.phi, self.omega = np.zeros(E), np.zeros(E)

    def std_desc(self, d):
        return torch.from_numpy(((d - self.stats["dmu"]) / self.stats["dsd"]).clip(-8, 8)).float()

    def std_y(self, y):
        return ((y - torch.from_numpy(self.stats["ymu"]).float()) / torch.from_numpy(self.stats["ysd"]).float()).clamp(-8, 8)

    @torch.no_grad()
    def block(self, deterministic=False, learn_cb=True, record=None):
        E, cfg = self.cfg.E, self.cfg
        feats, ph, bpm = zip(*[m.next(W.BLOCK) for m in self.music])
        f = torch.from_numpy(np.stack(feats))
        steps = []
        obs_b, err_b, nll_b, en_b, kap_b = [], [], [], [], []
        for s in range(tm3.BLOCK_STEPS):
            prop_std = (torch.from_numpy(self.arms.last) - self.cb.omu) / self.cb.osd if self.t or s else torch.zeros(E, 15)
            z = torch.cat([self.zx, prop_std[:, :15], self.err_last, self.nll_last[:, None]], -1)
            decide = s == 0
            if decide:
                logits = self.pol.scores(z)
                dist = torch.distributions.Categorical(logits=logits)
                k = logits.argmax(-1) if deterministic else dist.sample()
                logp_k = dist.log_prob(k)
                eps = torch.zeros(E, 20) if deterministic else tm3.SIGMA_P * torch.randn(E, 20)
                self.a_p = self.pol.theta[k] + eps
                logp_p = torch.distributions.Normal(self.pol.theta[k], tm3.SIGMA_P).log_prob(self.a_p).sum(-1)
                switch = (k != self.k_prev).float() * (self.k_prev >= 0).float()
                self.k_prev, self.k_cur = k, k
                logp_dec = logp_k + logp_p
            else:
                switch, logp_dec = torch.zeros(E), torch.zeros(E)
            mu = self.pol.mc_mean(z, self.k_cur)
            std = self.pol.logstd.exp()
            a_mc = mu if deterministic else mu + std * torch.randn(E, 25)
            logp_mc = torch.distributions.Normal(mu, std).log_prob(a_mc).sum(-1)
            kappa = kappa_of(a_mc[:, 20:])
            self.arms.command(tm3.executed_u(self.a_p, a_mc[:, :20]).numpy())
            obs, tgt, en = self.arms.step(tm3.STEP, self.phi + self.omega * 0.1 * s, self.omega, kappa.numpy())
            errs, nlls = [], []
            for c in range(tm3.STEP):
                e, n = self.cb.step(obs[:, c], tgt[:, c])
                errs.append(e)
                nlls.append(n)
            errs, nlls = torch.stack(errs, 1), torch.stack(nlls, 1)
            self.err_last, self.nll_last = errs[:, -1], nlls[:, -1]
            obs_b.append(obs)
            err_b.append(errs)
            nll_b.append(nlls.mean(1))
            en_b.append(en)
            kap_b.append(kappa)
            steps.append({"z": z, "k": self.k_cur.clone(), "a_p": self.a_p.clone(), "a_mc": a_mc, "decide": decide, "switch": switch,
                          "logp": logp_dec + logp_mc, "value": self.pol.critic(z)[:, 0]})
        obs = np.concatenate(obs_b, 1)                                                  # (E, 50, 15)
        # the brain listens to the song only
        x = W.cortex_input(f)
        out, st = self.cortex(x, None, self.state)
        s_all, self.lv = W.causal_surprisal(out, self.lv, self.state["n"])
        self.state = self.cortex.core.detach_state(st)
        y, self.arousal, phi_end, om = brain_state(out, s_all, self.arousal)
        self.phi, self.omega = phi_end.numpy().astype(float), om.numpy().astype(float)
        self.zx = torch.cat([out[2]["x"][:, -1], out[3]["x"][:, -1]], -1)
        # the observer reads the movement of the last 2 s
        self.pos_hist = np.concatenate([self.pos_hist, obs[..., :5]], 1)[:, -READY_FRAMES:]
        self.frames += W.BLOCK
        ready = self.frames >= READY_FRAMES
        desc = np.zeros((E, bdesc.N_DESC))
        leg = torch.full((E,), BASELINE_LEG)
        if ready:
            fr = bdesc.window_frames(self.pos_hist)
            desc = np.stack([bdesc.descriptors(fr[e]) for e in range(E)])
            if self.stats is not None:
                with torch.no_grad():
                    leg = -((self.obs(self.std_desc(desc)) - self.std_y(y)) ** 2).mean(-1)
        if ready and self.collect_obs:
            self.pending.append((desc, y.numpy().copy()))
        vel = obs[..., 5:10]
        self.vel_hist = np.concatenate([self.vel_hist[:, W.BLOCK:], vel], 1)
        lp = np.zeros((E, tm3.BLOCK_STEPS))
        for e in range(E):
            self.nll_hist[e].extend(torch.stack(nll_b, 1)[e].tolist())
            h = self.nll_hist[e]
            for j in range(tm3.BLOCK_STEPS):
                n = len(h) - tm3.BLOCK_STEPS + j + 1
                if n >= 200:
                    lp[e, j] = max(0.0, float(np.mean(h[n - 200:n - 100]) - np.mean(h[n - 100:n])))
        if learn_cb and (self.t + 1) % 10 == 0:
            self.cb.learn()
        self.t += 1
        res = {"steps": steps, "d": leg[:, None].expand(E, tm3.BLOCK_STEPS).clone(), "lp": torch.from_numpy(lp).float(),
               "en": torch.from_numpy(np.stack(en_b, 1)).float(), "sync": torch.zeros(E), "f": f, "prop": torch.zeros(E, W.BLOCK, 1), "obs": obs,
               "pulse_phase": np.stack(ph), "nll": torch.stack(nll_b, 1), "desc": desc, "y": y, "ready": ready, "kappa": torch.stack(kap_b, 1)}
        if record is not None:
            record.append(res)
        return res


# ---------------------------------------------------------------------------------------------------------------- observer training
def set_stats(run, raw_x, raw_y):
    run.stats = {"dmu": raw_x.mean(0), "dsd": raw_x.std(0) + 1e-6, "ymu": raw_y.mean(0), "ysd": raw_y.std(0) + 1e-6}


def train_observer(run, steps=OBS_STEPS):
    """Add the pending blocks to the replay buffer and take `steps` minibatch steps. Returns the mean loss over the steps (nan if nothing to train on)."""
    if run.pending:
        x = run.std_desc(np.concatenate([p[0] for p in run.pending]))
        y = run.std_y(torch.from_numpy(np.concatenate([p[1] for p in run.pending])).float())
        run.buf_x, run.buf_y = torch.cat([run.buf_x, x])[-OBS_BUF:], torch.cat([run.buf_y, y])[-OBS_BUF:]
        run.pending = []
    n = len(run.buf_x)
    if n == 0:
        return float("nan")
    losses = []
    for _ in range(steps):
        idx = torch.randint(0, n, (min(OBS_BATCH, n),))
        loss = ((run.obs(run.buf_x[idx]) - run.buf_y[idx]) ** 2).mean()
        run.obs_opt.zero_grad()
        loss.backward()
        run.obs_opt.step()
        losses.append(float(loss))
    return float(np.mean(losses))


def run_iteration(run, learn_policy=True):
    """One window: collect, update the observer, then (optionally) the policy. Returns the info dict."""
    roll = tm3.collect(run, run.cfg.H)
    kap = kappa_of(roll["a_mc"][..., 20:])
    obs_loss = train_observer(run)
    info = {"leg_mean": float(roll["d"].mean()), "obs_loss": obs_loss, "lp_mean": float(roll["lp"].mean()), "en_mean": float(roll["en"].mean()),
            "sw_per_min": float(roll["switch"].sum() / run.cfg.E / (roll["d"].shape[0] / 600.0)), "cb_nll": float(roll["nll"].mean()),
            "kappa_mean": float(kap.mean()), "kappa_active": float((kap > 0).float().mean())}
    if learn_policy and run.cal is not None:
        info.update(tm3.ppo_update(run, roll))
        info["r_mean"] = float(roll["r"].mean())
    info["prog_hist"] = torch.bincount(roll["k"][roll["dec"] > 0].reshape(-1), minlength=K).tolist()
    return info


def calibrate(run, iters=15, stats_after=6, log=print):
    """Random initial policy, cerebellum learning. Windows 0..stats_after-1 only collect raw blocks (their mean/SD standardise descriptors and brain state);
    the observer then trains on them and every later window is scored. LP0 and E0 = means over the last third. R0 = 1 by construction."""
    raw_x, raw_y, lp, en, leg = [], [], [], [], []
    for i in range(iters):
        if i == stats_after:
            set_stats(run, np.concatenate(raw_x), np.concatenate(raw_y))
            train_observer(run, 300)
        roll = tm3.collect(run, run.cfg.H)
        if run.stats is None:
            raw_x += [p[0] for p in run.pending]
            raw_y += [p[1] for p in run.pending]
            run.pending = []
            obs_loss = float("nan")
        else:
            obs_loss = train_observer(run)
        info = {"leg_mean": float(roll["d"].mean()), "obs_loss": obs_loss, "lp_mean": float(roll["lp"].mean()), "en_mean": float(roll["en"].mean())}
        log(f"calib {i + 1}/{iters} " + str({k: round(v, 5) for k, v in info.items()}))
        if i >= 2 * iters // 3:
            lp.append(info["lp_mean"]); en.append(info["en_mean"]); leg.append(info["leg_mean"])
    return {"R0": 1.0, "LP0": max(float(np.mean(lp)), 1e-6), "E0": max(float(np.mean(en)), 1e-6), "SYNC0": 1.0, "leg_calib_mean": float(np.mean(leg)),
            "stats": {k: v.tolist() for k, v in run.stats.items()}}


# ---------------------------------------------------------------------------------------------------------------- statistics (from body-m3b d160afd)
def selection_stats(ks, n_prog=K, min_share=0.05, min_programs=4):
    """ks (E, decisions) int program choices (0.5 s apart). (c): at least `min_programs` programs each chosen in >= `min_share` of all decisions."""
    cnt = torch.bincount(ks.reshape(-1), minlength=n_prog).float()
    pr = cnt / cnt.sum()
    ent = float(-(pr[pr > 0] * pr[pr > 0].log()).sum())
    n_ep, n_dec = ks.shape
    sw = float((ks[:, 1:] != ks[:, :-1]).float().sum() / n_ep / (n_dec * 0.5 / 60.0))
    big = int((pr >= min_share).sum())
    return {"programs_used": int((cnt > 0).sum()), "programs_above_5pct": big, "program_counts": cnt.tolist(), "switches_per_min": sw,
            "selection_entropy_nats": ent, "c_pass": bool(big >= min_programs)}


def nonroll_stats(vel):
    """vel (E, T, 5) deg/s -> (b) RMS over the four non-roll joints, per-joint RMS (all five, for the report), the dominant non-roll joint per episode."""
    rms = float(np.sqrt((vel[..., NON_ROLL] ** 2).mean()))
    per = np.sqrt((vel ** 2).mean((0, 1))).tolist()
    dom = [NON_ROLL[int(np.argmax((v[:, NON_ROLL] ** 2).sum(0)))] for v in vel]
    return rms, per, dom


def boot_ci(x, n=10000):
    rng = np.random.default_rng(0)
    bs = np.array([rng.choice(x, len(x)).mean() for _ in range(n)])
    return float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def shuffle_partner(n, seed=0):
    """Fixed partner j != i for every episode i (a derangement, from a fixed seed)."""
    rng = np.random.default_rng(seed)
    while True:
        p = rng.permutation(n)
        if (p != np.arange(n)).all():
            return p


def decode_losses(obs, xd, y, partner):
    """xd (E, B, 31) standardised descriptors, y (E, B, 8) standardised targets -> per-episode mean loss with matched pairs and with episode i's state paired to
    episode partner[i]'s movement (the song-shuffled control)."""
    with torch.no_grad():
        pred = obs(xd)
        matched = ((pred - y) ** 2).mean((1, 2))
        shuffled = ((pred[partner] - y) ** 2).mean((1, 2))
    return matched.numpy(), shuffled.numpy()


# ---------------------------------------------------------------------------------------------------------------- evaluation
def evaluate(run, n_ep=8, secs=90.0, skip=10.0, seed=999, surrogates=1000):
    """Fresh arms and songs, the policy's mean action, cerebellum and observer not learning. (a) per-episode mean loss of the song-shuffled control minus the matched
    loss (positive: movement carries the brain state), bootstrap interval over episodes; (b) RMS joint speed over the four non-roll joints; (c) programs; report:
    1:1 phase locking of the dominant non-roll joint's velocity to the pulse (K3-style), kappa used."""
    cfg = copy.deepcopy(run.cfg)
    cfg.E = n_ep
    ev = RunC(cfg, run.cortex, run.cb_bundle, run.cal, seed=seed)
    ev.pol.load_state_dict(run.pol.state_dict())
    ev.cb.net.load_state_dict(run.cb.net.state_dict())
    ev.obs.load_state_dict(run.obs.state_dict())
    ev.stats = run.stats
    ev.collect_obs = False
    rec = []
    for _ in range(int(secs / 0.5)):
        ev.block(deterministic=True, learn_cb=False, record=rec)
    sk = int(skip / 0.5)
    rdy = rec[sk:]
    xd = torch.stack([ev.std_desc(r["desc"]) for r in rdy], 1)                     # (E, B, 31)
    yy = torch.stack([ev.std_y(r["y"]) for r in rdy], 1)
    partner = shuffle_partner(n_ep)
    matched, shuffled = decode_losses(ev.obs, xd, yy, partner)
    diff = shuffled - matched
    lo, hi = boot_ci(diff)
    vel = np.concatenate([r["obs"][..., 5:10] for r in rec], 1)[:, sk * W.BLOCK:]
    ph = np.concatenate([r["pulse_phase"] for r in rec], 1)[:, sk * W.BLOCK:]
    rms, per_joint, dom = nonroll_stats(vel)
    sos = butter(2, [0.3, 4.0], btype="band", fs=100, output="sos")
    vph = [np.angle(hilbert(sosfiltfilt(sos, vel[e, :, dom[e]]))) for e in range(n_ep)]
    pph = [ph[e] % (2 * np.pi) for e in range(n_ep)]
    obs_plv = tm3.plv(np.concatenate(vph), np.concatenate(pph))
    rng = np.random.default_rng(0)
    sur = [tm3.plv(np.concatenate([np.roll(v, int(rng.integers(len(v) // 10, 9 * len(v) // 10))) for v in vph]), np.concatenate(pph)) for _ in range(surrogates)]
    p = (1 + sum(s >= obs_plv for s in sur)) / (1 + surrogates)
    ks = torch.cat([torch.stack([s["k"] for s in r["steps"] if s["decide"]], 1) for r in rec], 1)
    sel = selection_stats(ks)
    with torch.no_grad():
        zs = torch.stack([s["z"] for r in rec for s in r["steps"] if s["decide"]])
        pk = torch.softmax(ev.pol.scores(zs), -1)
        pol_entropy = float(-(pk * pk.clamp(min=1e-12).log()).sum(-1).mean())
        kap = torch.cat([r["kappa"] for r in rec], 1)                              # (E, steps, 5)
    res = {"a_mean": float(diff.mean()), "a_lo": lo, "a_hi": hi, "a_pass": bool(lo > 0), "a_per_episode": diff.tolist(), "loss_matched": float(matched.mean()),
           "loss_shuffled": float(shuffled.mean()), "partner": partner.tolist(),
           "b_rms_deg_s_nonroll": rms, "b_per_joint_deg_s": per_joint, "b_pass": bool(rms >= 10.0), **sel, "policy_mean_entropy_nats": pol_entropy,
           "k3_plv_report_only": obs_plv, "k3_surrogate_mean": float(np.mean(sur)), "k3_surrogate_max": float(np.max(sur)), "k3_p": float(p), "dominant_joints": dom,
           "kappa_mean_per_joint": kap.mean((0, 1)).tolist(), "kappa_active_share": float((kap > 0).float().mean()), "kappa_max": KAPPA_MAX}
    res["pass"] = res["a_pass"] and res["b_pass"] and res["c_pass"]
    return res
