"""M3b toy (docs/BRAIN_SPEC.md §7.14 point 2): T-M3 with a timing-only reward. TOY ONLY. T-M3 (tm3.py) is untouched and stays reproducible.

Changes against T-M3, nothing else:
  reward     r = (S_shifted - S_moving) + beta*LP - lambda*E - c_sw*[switch] (tm3.reward_terms, same relative scales). S_shifted = the cortex fed the SAME
             environment's relay input (proprioception + cerebellum error) delayed by Delta_e seconds, Delta_e ~ U(2, 8) s per environment from a fixed
             seed (SHIFT_SEED_A in training and in (a); SHIFT_SEED_B for the second-shift control). A delay is a circular shift of a stationary stream;
             an episode here is endless, so it is causal: frames before Delta_e have no history (zeros) and get reward 0 (evaluation skips 10 s > 8 s).
             No S_still anywhere: the twin pass has the rows [moving, shifted].
  wrist roll excluded from the relay input (CortexB zeroes its six columns), from (b), and from the dominant joint of (c). It still costs energy and the
             cerebellum still sees it (so does the policy's input z).
  selection  entropy bonus cfg.ent on the program choice (tm3.ppo_update: loss = clip loss + 0.5 value loss - ent * H; advantages are normalised to unit SD
             per update, H = mean Shannon entropy of the 8-way program softmax over decision rows, max ln 8 = 2.079 nats); (d) at least 4 programs, each
             chosen in >= 5 % of decisions, from the policy's mean action (argmax) as in T-M3; the sampling policy's probabilities are reported alongside.
Provisional servo model (Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5, acceleration share 0.25).
"""
import copy

import numpy as np
import torch
from scipy.signal import butter, hilbert, sosfiltfilt

import m3_cortex as M
import tm3
import tm3_world as W

ROLL = 4                                                    # wrist_roll in make_arm.JOINTS
ROLL_COLS = [ROLL + 5 * i for i in range(6)]                # relay input = (pos, vel, load, err pos, err vel, err load) x 5 joints
NON_ROLL = [0, 1, 2, 3]
SHIFT_SEED_A, SHIFT_SEED_B = 11, 22
SHIFT_RANGE_S = (2.0, 8.0)
BUF = 900                                                   # frames of relay-input history (8 s shift + 0.5 s block + margin)
K = tm3.K


def make_shifts(seed, E):
    """Per-environment delays in frames (100 Hz), U(2, 8) s, fixed by `seed`."""
    return np.round(np.random.default_rng(seed).uniform(*SHIFT_RANGE_S, E) * 100).astype(int)


def delay(prop, shifts):
    """(E, T, P) -> out[e, t] = prop[e, t - shifts[e]], zeros before the shift."""
    out = torch.zeros_like(prop)
    for e, s in enumerate(shifts):
        s = int(s)
        if s < prop.shape[1]:
            out[e, s:] = prop[e, :prop.shape[1] - s]
    return out


class CortexB(M.Cortex):
    """B7 + relays as in M3, with the wrist roll absent from the relay input."""

    def forward(self, f, prop, state):
        if prop is not None:
            keep = torch.ones(prop.shape[-1], dtype=prop.dtype)
            keep[ROLL_COLS] = 0
            prop = prop * keep
        return super().forward(f, prop, state)


class RunB(tm3.Run):
    def __init__(self, cfg, cortex, bundle, cal=None, seed=None, shift_seed=SHIFT_SEED_A):
        super().__init__(cfg, cortex, bundle, cal, seed)
        self.shifts = make_shifts(shift_seed, cfg.E)
        self.pbuf = torch.zeros(cfg.E, BUF, W.P)
        self.f0 = 0                                          # frames elapsed

    @torch.no_grad()
    def block(self, deterministic=False, learn_cb=True, record=None):
        E, cfg = self.cfg.E, self.cfg
        feats, ph, bpm = zip(*[m.next(W.BLOCK) for m in self.music])
        f = torch.from_numpy(np.stack(feats))
        steps = []
        obs_b, err_b, nll_b, en_b = [], [], [], []
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
            a_mc = mu if deterministic else mu + std * torch.randn(E, 20)
            logp_mc = torch.distributions.Normal(mu, std).log_prob(a_mc).sum(-1)
            self.arms.command(tm3.executed_u(self.a_p, a_mc).numpy())
            obs, tgt, en = self.arms.step(tm3.STEP)
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
            steps.append({"z": z, "k": self.k_cur.clone(), "a_p": self.a_p.clone(), "a_mc": a_mc, "decide": decide, "switch": switch,
                          "logp": logp_dec + logp_mc, "value": self.pol.critic(z)[:, 0]})
        obs = np.concatenate(obs_b, 1)
        err = torch.cat(err_b, 1)
        prop = torch.cat([(torch.from_numpy(obs) - self.cb.omu) / self.cb.osd, err], -1)          # (E, 50, 30), roll still in; CortexB drops it
        self.pbuf = torch.cat([self.pbuf, prop], 1)[:, -BUF:]
        prop_sh = torch.stack([self.pbuf[e, BUF - W.BLOCK - int(d):BUF - int(d)] for e, d in enumerate(self.shifts)])
        x = W.cortex_input(f)
        out, st = self.cortex(torch.cat([x, x]), torch.cat([prop, prop_sh]), self.state)         # rows [moving, shifted]
        s_all, self.lv = W.causal_surprisal(out, self.lv, self.state["n"])
        self.state = self.cortex.core.detach_state(st)
        valid = (self.f0 + torch.arange(W.BLOCK))[None] >= torch.from_numpy(self.shifts)[:, None]        # shifted row has history
        d = ((s_all[E:] - s_all[:E]) * valid).reshape(E, tm3.BLOCK_STEPS, tm3.STEP).mean(-1)            # S_shifted - S_moving per 0.1 s
        self.f0 += W.BLOCK
        self.zx = torch.cat([out[2]["x"][:E, -1], out[3]["x"][:E, -1]], -1)
        vel = obs[..., 5:10]
        self.vel_hist = np.concatenate([self.vel_hist[:, W.BLOCK:], vel], 1)
        self.h3_hist = np.concatenate([self.h3_hist[:, W.BLOCK:], out[2]["h"][:E].numpy()], 1)
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
        res = {"steps": steps, "d": d, "lp": torch.from_numpy(lp).float(), "en": torch.from_numpy(np.stack(en_b, 1)).float(), "sync": torch.zeros(E),
               "f": f, "prop": prop, "prop_shifted": prop_sh, "obs": obs, "pulse_phase": np.stack(ph), "nll": torch.stack(nll_b, 1)}
        if record is not None:
            record.append(res)
        return res


# ---------------------------------------------------------------------------------------------------------------- statistics
def selection_stats(ks, n_prog=K, min_share=0.05, min_programs=4):
    """ks (E, decisions) int program choices (0.5 s apart). (d): at least `min_programs` programs each chosen in >= `min_share` of all decisions."""
    cnt = torch.bincount(ks.reshape(-1), minlength=n_prog).float()
    pr = cnt / cnt.sum()
    ent = float(-(pr[pr > 0] * pr[pr > 0].log()).sum())
    n_ep, n_dec = ks.shape
    sw = float((ks[:, 1:] != ks[:, :-1]).float().sum() / n_ep / (n_dec * 0.5 / 60.0))
    big = int((pr >= min_share).sum())
    return {"programs_used": int((cnt > 0).sum()), "programs_above_5pct": big, "program_counts": cnt.tolist(), "switches_per_min": sw,
            "selection_entropy_nats": ent, "d_pass": bool(big >= min_programs)}


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


def evaluate(run, n_ep=8, secs=90.0, skip=10.0, seed=999, surrogates=1000):
    """Fresh arms and songs, the policy's mean action, cerebellum not learning, relay as trained. (a) S_shifted - S_moving (shift A) per episode with a
    bootstrap interval over episodes; (b) RMS joint speed over the four non-roll joints; (c) 1:1 phase-locking of the dominant non-roll joint's velocity to
    the pulse against circular-shift surrogates; (d) selection. Control: S_shifted - S_moving again with the independent shift B, offline on the same
    recorded episodes (shift A offline as a consistency check)."""
    cfg = copy.deepcopy(run.cfg)
    cfg.E = n_ep
    ev = RunB(cfg, run.cortex, run.cb_bundle, run.cal, seed=seed)
    ev.pol.load_state_dict(run.pol.state_dict())
    ev.cb.net.load_state_dict(run.cb.net.state_dict())
    rec = []
    for _ in range(int(secs / 0.5)):
        ev.block(deterministic=True, learn_cb=False, record=rec)
    sk = int(skip / 0.5)
    assert skip >= SHIFT_RANGE_S[1]
    d = torch.cat([r["d"] for r in rec], 1)[:, sk * tm3.BLOCK_STEPS:]
    per_ep = d.mean(1).numpy()
    a_lo, a_hi = boot_ci(per_ep)
    vel = np.concatenate([r["obs"][..., 5:10] for r in rec], 1)[:, sk * W.BLOCK:]
    ph = np.concatenate([r["pulse_phase"] for r in rec], 1)[:, sk * W.BLOCK:]
    rms, per_joint, dom = nonroll_stats(vel)
    sos = butter(2, [0.3, 4.0], btype="band", fs=100, output="sos")
    vph = [np.angle(hilbert(sosfiltfilt(sos, vel[e, :, dom[e]]))) for e in range(n_ep)]
    pph = [ph[e] % (2 * np.pi) for e in range(n_ep)]
    obs_plv = tm3.plv(np.concatenate(vph), np.concatenate(pph))
    rng = np.random.default_rng(0)
    sur = []
    for _ in range(surrogates):
        sh = [np.roll(v, int(rng.integers(len(v) // 10, 9 * len(v) // 10))) for v in vph]
        sur.append(tm3.plv(np.concatenate(sh), np.concatenate(pph)))
    p = (1 + sum(s >= obs_plv for s in sur)) / (1 + surrogates)
    ks = torch.cat([torch.stack([s["k"] for s in r["steps"] if s["decide"]], 1) for r in rec], 1)
    sel = selection_stats(ks)
    with torch.no_grad():
        zs = torch.stack([s["z"] for r in rec for s in r["steps"] if s["decide"]])                 # (decisions, E, DIN)
        pk = torch.softmax(ev.pol.scores(zs), -1)
        pol_entropy = float(-(pk * pk.clamp(min=1e-12).log()).sum(-1).mean())
        pol_probs = pk.mean((0, 1)).tolist()
        F = torch.cat([r["f"] for r in rec], 1)
        PR = torch.cat([r["prop"] for r in rec], 1)
        x = W.cortex_input(F)
        T = x.shape[1]
        out, _ = ev.cortex(torch.cat([x, x, x]), torch.cat([PR, delay(PR, ev.shifts), delay(PR, make_shifts(SHIFT_SEED_B, n_ep))]), ev.cortex.core.init_state(3 * n_ep))
        s3, _ = W.causal_surprisal(out, None, torch.zeros(3 * n_ep, dtype=torch.long))
        s3 = s3[:, int(skip * 100):].mean(1).reshape(3, n_ep)
    dA, dB = (s3[1] - s3[0]).numpy(), (s3[2] - s3[0]).numpy()
    bl, bh = boot_ci(dB)
    res = {"a_mean": float(per_ep.mean()), "a_lo": a_lo, "a_hi": a_hi, "a_pass": bool(a_lo > 0), "a_per_episode": per_ep.tolist(),
           "b_rms_deg_s_nonroll": rms, "b_per_joint_deg_s": per_joint, "b_pass": bool(rms >= 10.0),
           "c_plv": obs_plv, "c_surrogate_mean": float(np.mean(sur)), "c_surrogate_max": float(np.max(sur)), "c_p": float(p), "c_pass": bool(p < 0.01),
           "dominant_joints": dom, **sel, "policy_mean_entropy_nats": pol_entropy, "policy_mean_probs": pol_probs,
           "control_shiftA_offline": float(dA.mean()), "control_shiftB_mean": float(dB.mean()), "control_shiftB_lo": bl, "control_shiftB_hi": bh,
           "control_shiftB_per_episode": dB.tolist(), "shifts_A_s": (ev.shifts / 100).tolist(), "shifts_B_s": (make_shifts(SHIFT_SEED_B, n_ep) / 100).tolist()}
    res["pass"] = res["a_pass"] and res["b_pass"] and res["c_pass"] and res["d_pass"]
    return res
