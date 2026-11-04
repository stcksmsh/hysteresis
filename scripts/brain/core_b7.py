"""B7 core (docs/BRAIN_SPEC.md 7.1 as ruled in 7.10): the B3 core plus a hippocampus (pointer replay, centred keys), a thalamic relay and acting
neuromodulation. All causal. Rulings R1 and R2 of 2026-11-02 replace the first version (stored 2 s means, 0.5 s blocks), which did not learn.

Fixed here, before any result (7.10 is silent on all of these; B7_NOTES.md has the same list):
  blocks      The network runs in blocks of BLOCK = 200 frames (2 s), blocks in sequence, frames inside a block in parallel. A chunk must start on
              a block edge (n % 200 == 0); only the last chunk of a song may end inside a block.
  buffer      Per row, the cumulative sum of the 44 raw features by song frame (float64, cs[r, k] = sum of frames < k): any window mean is two reads.
              No gradient (the features are inputs). A new song (reset_rows) starts that row's buffer again from frame 0 (n = 0).
  keys        Every TICK = 50 frames (0.5 s) one entry: raw key k_j = Linear(44 + 4 N -> 64, no bias) of [the raw features pooled over the last 2 s
              (frames t - 200 .. t - 1, zero-padded before the song), layer norm of the [Re, Im] modes of L3 and L4 at frame t], t = 50 j. The
              running mean m of the raw keys of the song (all entries written so far) centres them: the key used in a read is normalised(k_j - m),
              the query normalised(q - m), q = its own Linear of the same kind of input built at the block start (pooled over the last 2 s, the L3 + L4
              modes of the last frame of the previous block). Key and query projections start as the same random matrix (seed SEED_B7).
  read        Once per block, cosine against entries at least MIN_AGE = 1,700 frames (17 s) old at the block start (50 j <= n0 - 1700), top-k 4,
              softmax(sim / tau), tau = exp(log_tau) learned (init 0.1). Fewer than 4 eligible: softmax over those; none: recognition 0, replay zeros,
              source time -1. recognition = the best cosine, novelty = 1 - recognition, source time = 0.5 s x the top-1 entry's index.
  replay      For source entry j (frame s = 50 j), frame o of the block (0..199) and horizon h in HORIZONS: the raw features averaged over
              [s + o + h, s + o + 2 h), mixed with the softmax weights: (B, 200, 4, 44). All of it lies before the frame being served
              (s + o + 1600 <= n0 + o - 100).
  relay       layer input += Linear(223 -> 128, no bias) of [44 features, grid phase (2), the 4 x 44 replay, recognition]. Head skip:
              Linear(44 * SKIP_TAPS -> 88, no bias) of the current features (skip_taps = 10: the last 10 frames; R4 fallback for T2) added to each head output.
  arousal     as the first version (L1 + L2 surprisal of predictions whose target window ended, one-pole rise 1 s decay 8 s at 100 Hz, running mean tau 60 s
              from the first value, no_grad); dev is read at the block start from the previous block's last frame.
  modulation  per layer and block (2 s): gain g = 1 + w_g dev on the drive; exponent e = clamp(1 + w_tau dev, E_MIN, E_MAX) on |lam|, |lam_eff| =
              exp(-nu e) < 1 always; theta never changes. Effective time constant = median(dt / nu) / e.
  zero init   relay, skip, w_g, w_tau are zero, so B7 at step 0 equals B3. The key / query projection start as one random matrix (a pair of zero
              projections is a saddle).
  switches    `relay_on` (relay input and head skip zero), `retrieval_on` (replay and recognition zero at the relay input; novelty still computed),
              `modulation` ("on" or "frozen": dev = 0), `oracle` (callable n0 (B,) -> source frame (B,) or -1; replaces the read: weight 1 on that frame).
  hippocampus `hippocampus` (default True; saved in the checkpoint as the buffer `hippo_flag`). False = DROPPED (overnight order, decision tree 1c, after
              the toy tests could not pass T1b): no buffer, no keys, no read; replay and recognition are zeros, novelty 1, source -1. The relay (features +
              grid phase), the head skip and the modulation stay; the unused key / query weights get no gradient.
State: the B3 state plus lv, the buffer cs, the entries (kr raw keys, kj tick index, kv valid), ksum / kcnt (running key mean), qs, a, amean.
"""
import math

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

import core

SEED_B7 = 20261101
BLOCK = 200
TICK = 50
POOL = 200
KEY_DIM = 64
TOP_K = 4
MIN_AGE = 1700               # frames (17 s)
TAU_INIT = 0.1
E_MIN, E_MAX = 0.1, 10.0
TAU_RISE, TAU_FALL, TAU_MEAN = 1.0, 8.0, 60.0
N_REL = core.FEAT + 2 + 4 * core.FEAT + 1
AROUSAL_LAYERS = (0, 1)


def _arousal_rates():
    return (1 - math.exp(-core.DT / TAU_RISE), 1 - math.exp(-core.DT / TAU_FALL), 1 - math.exp(-core.DT / TAU_MEAN))


def to_double(x):
    """A model, state or tensor tree in float64 / complex128 (the exact-identity check of B7 against B3 runs in double)."""
    if isinstance(x, nn.Module):
        return x.double()
    if torch.is_tensor(x):
        return x.double() if x.is_floating_point() else (x.to(torch.complex128) if x.is_complex() else x)
    if isinstance(x, dict):
        return {k: to_double(v) for k, v in x.items()}
    if isinstance(x, list):
        return [to_double(v) for v in x]
    return x


def window_mean(cs, lo, hi, width):
    """cs (B, L, 44) cumulative sums; lo, hi (B, K) frame indices -> (B, K, 44) means over [lo, hi) divided by `width`. Indices are clamped to the buffer."""
    L = cs.shape[1]
    g = lambda idx: torch.gather(cs, 1, idx.clamp(0, L - 1)[..., None].expand(-1, -1, cs.shape[2]))
    return (g(hi) - g(lo)) / width


class Core7(core.Core):
    def __init__(self, seed=core.SEED, phase=True, head_norm=True, skip_taps=1, hippocampus=True):
        super().__init__(seed, phase, head_norm)
        self.register_buffer("hippo_flag", torch.tensor(1.0 if hippocampus else 0.0))
        g = torch.Generator().manual_seed(SEED_B7)
        d_in = core.FEAT + 4 * core.N
        self.key_proj = core._lin(g, d_in, KEY_DIM, bias=False)
        self.query_proj = core._lin(g, d_in, KEY_DIM, bias=False)
        with torch.no_grad():
            self.query_proj.weight.copy_(self.key_proj.weight)
        self.log_tau = nn.Parameter(torch.tensor(math.log(TAU_INIT)))
        nl = len(core.BANDS)
        self.skip_taps = skip_taps
        self.relay = nn.ModuleList(nn.Linear(N_REL, core.D, bias=False) for _ in range(nl))
        self.skip = nn.ModuleList(nn.Linear(core.FEAT * skip_taps, 2 * core.FEAT, bias=False) for _ in range(nl))
        for m in (*self.relay, *self.skip):
            nn.init.zeros_(m.weight)
        self.w_g = nn.Parameter(torch.zeros(nl))
        self.w_tau = nn.Parameter(torch.zeros(nl))
        self.relay_on, self.retrieval_on, self.modulation, self.oracle = True, True, "on", None
        # H1 (all off by default: with them off the module is unchanged). hind: hindsight retrieval loss, returned in out[0]["hind"] and weighted by
        # the caller. oracle_p: scheduled sampling, the per-row, per-read probability of taking the oracle pointer (1 = pure oracle, 0 = retrieval).
        # novelty_lane: 1 - max cosine against the eligible store at every tick (0.5 s), no gradient, independent of the block read.
        self.hind, self.oracle_p, self.novelty_lane, self.hind_gate = False, 1.0, False, False
        self.sched_gen = torch.Generator().manual_seed(SEED_B7)

    # ---- state ------------------------------------------------------------------------------------------------------

    def init_state(self, B=1):
        st = super().init_state(B)
        st.update({"lv": [torch.zeros(B, 2 * core.HORIZONS[i], core.FEAT) for i in AROUSAL_LAYERS],
                   "cs": torch.zeros(B, 1, core.FEAT, dtype=torch.float64),
                   "kr": torch.zeros(B, 0, KEY_DIM), "kj": torch.zeros(B, 0, dtype=torch.long), "kv": torch.zeros(B, 0, dtype=torch.bool),
                   "ksum": torch.zeros(B, KEY_DIM), "kcnt": torch.zeros(B), "qs": torch.zeros(B, 4 * core.N),
                   "a": torch.zeros(B), "amean": torch.zeros(B)})
        return st

    @staticmethod
    def detach_state(state):
        """Graph cut at the chunk edge; the entries are trimmed to the columns some row still needs."""
        st = core.Core.detach_state(state)
        kv = state["kv"]
        first = int(kv.any(0).nonzero()[0]) if kv.any() else kv.shape[1]
        st.update({"lv": [v.detach() for v in state["lv"]], "cs": state["cs"], "kr": state["kr"].detach()[:, first:], "kj": state["kj"][:, first:],
                   "kv": kv[:, first:], "ksum": state["ksum"].detach(), "kcnt": state["kcnt"], "qs": state["qs"].detach(), "a": state["a"], "amean": state["amean"]})
        return st

    @staticmethod
    def reset_rows(state, rows):
        st = core.Core.reset_rows(state, rows)
        keep = torch.ones(state["n"].shape[0], dtype=torch.bool)
        keep[rows] = False
        k1 = keep.view(-1, 1)
        cs = state["cs"].clone()
        cs[~keep] = 0
        st.update({"lv": [v * k1.unsqueeze(-1).to(v.dtype) for v in state["lv"]], "cs": cs, "kr": state["kr"], "kj": state["kj"], "kv": state["kv"] & k1,
                   "ksum": state["ksum"] * k1.float(), "kcnt": state["kcnt"] * keep.float(), "qs": state["qs"] * k1.float(),
                   "a": state["a"] * keep.float(), "amean": state["amean"] * keep.float()})
        return st

    # ---- hippocampus -------------------------------------------------------------------------------------------------

    def _pooled(self, cs, t):
        """(B, 44): mean of the raw features over the POOL frames before song frame t (B,), zero-padded before the song."""
        return window_mean(cs, (t - POOL)[:, None].clamp(min=0), t[:, None], POOL)[:, 0].float()

    def _centre(self, v, ksum, kcnt):
        m = ksum / kcnt.clamp(min=1)[:, None]
        return F.normalize(v - (m[:, None] if v.dim() == 3 else m), dim=-1)

    def read(self, st, new_k, new_j, n0, ksum, kcnt, cs, hind_ctx=None):
        """One read for every row at the block start (song frames n0 (B,)). -> replay (B, BLOCK, 4, 44), recognition (B,), source frame (B,) (-1:
        none), weights (B, k), the top-1 column and the hindsight loss (sum, count) or None. hind_ctx = (cl, local0, T): the chunk's cumulative sums
        of the raw features (B, T + 1, 44, float64) and the block start inside the chunk, so the true targets of this block can be looked up (training only)."""
        B = n0.shape[0]
        zero = torch.zeros(B, BLOCK, 4, core.FEAT)
        K0, Kn = st["kr"].shape[1], len(new_k)
        pure = self.oracle is not None and self.oracle_p > 0 and (self.oracle_p >= 1 or K0 + Kn == 0)
        if (K0 + Kn == 0 and not pure) or not float(self.hippo_flag):
            return zero, torch.zeros(B), -torch.ones(B, dtype=torch.long), None, None, None
        hind = None
        if pure:
            src = self.oracle(n0).long()
            has = src >= 0
            w = has.float()[:, None]
            srcs = src.clamp(min=0)[:, None]
            rec = has.float()
            top = None
        else:
            kr = torch.cat([st["kr"]] + ([torch.stack(new_k, 1)] if new_k else []), 1)
            kj = torch.cat([st["kj"]] + ([torch.stack(new_j, 1)] if new_j else []), 1)
            kv = torch.cat([st["kv"]] + ([torch.ones(B, Kn, dtype=torch.bool)] if new_k else []), 1)
            pooled = self._pooled(cs, n0)
            qin = torch.cat([pooled, F.layer_norm(st["qs"], (4 * core.N,))], -1)
            q = self._centre(self.query_proj(qin), ksum, kcnt)
            kc = self._centre(kr, ksum, kcnt)
            sim = torch.einsum("bd,bkd->bk", q, kc)
            elig = kv & (kj * TICK <= (n0[:, None] - MIN_AGE))
            top_sim, top_idx = torch.where(elig, sim, torch.full_like(sim, -2.0)).topk(min(TOP_K, sim.shape[1]), dim=1)
            top_ok = torch.gather(elig, 1, top_idx)
            w = torch.softmax(torch.where(top_ok, top_sim / torch.exp(self.log_tau), torch.full_like(top_sim, -1e9)), 1) * top_ok
            has = top_ok[:, 0]
            rec = torch.where(has, top_sim[:, 0], torch.zeros_like(top_sim[:, 0]))
            srcs = torch.gather(kj, 1, top_idx) * TICK
            src = torch.where(has, srcs[:, 0], -torch.ones_like(srcs[:, 0]))
            top = top_idx[:, 0]
            if hind_ctx is not None and self.hind:
                hind = self._hindsight(sim, elig, kj, n0, cs, hind_ctx)
            if self.oracle is not None and self.oracle_p > 0:               # scheduled sampling: some rows take the oracle pointer, rec stays retrieved
                osrc = self.oracle(n0).long()
                use = (torch.rand(B, generator=self.sched_gen) < self.oracle_p) & (osrc >= 0)
                one = torch.zeros_like(w)
                one[:, 0] = 1.0
                w = torch.where(use[:, None], one, w)
                srcs = torch.cat([torch.where(use, osrc, srcs[:, 0])[:, None], srcs[:, 1:]], 1)
                src = torch.where(use, osrc, src)
        k = srcs.shape[1]
        o = torch.arange(BLOCK)
        rep = []
        for h in core.HORIZONS:
            base = (srcs[:, :, None] + o[None, None]).reshape(B, k * BLOCK)
            m = window_mean(cs, base + h, base + 2 * h, h).float().reshape(B, k, BLOCK, core.FEAT)
            rep.append((w[:, :, None, None] * m).sum(1))
        return torch.stack(rep, 2), rec, src, w, top, hind

    def _hindsight(self, sim, elig, kj, n0, cs, ctx):
        """Hindsight retrieval loss of one read. No gradient in the target: per eligible entry, the squared error between its replay and the block's
        true targets (every 20th frame of the block, all four horizons whose target window lies inside the chunk). Cross-entropy of the query's
        softmax(sim / tau) over the eligible entries toward the entry with the lowest error. -> (sum over rows, rows counted, the target entry's frame)."""
        cl, local0, T = ctx
        B, K = sim.shape
        Os = torch.arange(0, BLOCK, 20)
        with torch.no_grad():
            err = torch.zeros(B, K)
            zerr = torch.zeros(B)
            ok_any = False
            for h in core.HORIZONS:
                Oo = Os[local0 + Os + 2 * h <= T]
                if not len(Oo):
                    continue
                ok_any = True
                lo = (local0 + Oo + h)[None].expand(B, -1)
                tgt = window_mean(cl, lo, lo + h, h).float()
                base = (kj[:, :, None] * TICK + Oo[None, None]).reshape(B, K * len(Oo))
                m = window_mean(cs, base + h, base + 2 * h, h).float().reshape(B, K, len(Oo), core.FEAT)
                err = err + ((m - tgt[:, None]) ** 2).mean(-1).sum(-1)
                zerr = zerr + (tgt ** 2).mean(-1).sum(-1)
            if not ok_any:
                return None
            best = torch.where(elig, err, torch.full_like(err, float("inf"))).argmin(1)
        logp = torch.log_softmax(torch.where(elig, sim / torch.exp(self.log_tau), torch.full_like(sim, -1e9)), 1)
        rows = elig.any(1)
        if self.hind_gate:                                   # only where the best replay beats a zero replay
            rows = rows & (err.gather(1, best[:, None])[:, 0] < zerr)
        rows = rows.float()
        return (-(logp.gather(1, best[:, None])[:, 0]) * rows).sum(), rows.sum(), torch.gather(kj, 1, best[:, None])[:, 0] * TICK

    # ---- forward -----------------------------------------------------------------------------------------------------

    def forward(self, f, state, return_replay=False):
        """f: (B, T, 46) -> (out, state) as core.Core.forward, with per layer also "tau_eff" and "expo" (B, nblocks) and, in out[0], "hippo"
        {recognition, novelty, source_t (s, -1 none): (B, T) per frame (a block shares one read)}, "arousal" (B, T), "dev" (B, nblocks) and, with
        `return_replay`, "replay" (B, T, 4, 44)."""
        if not self.phase:
            f = torch.cat([f[..., :core.FEAT], torch.zeros_like(f[..., core.FEAT:])], -1)
        B, T, _ = f.shape
        if int(state["n"][0]) % BLOCK:
            raise ValueError(f"a B7 chunk must start on a block edge (n a multiple of {BLOCK})")
        base = {k: state[k] for k in ("n", "f", "h", "q", "mean")}
        lv, qs, a, am = list(state["lv"]), state["qs"], state["a"], state["amean"]
        ksum, kcnt = state["ksum"], state["kcnt"]
        cs = state["cs"]
        need = int(state["n"].max()) + T + 1
        if cs.shape[1] < need and bool(float(self.hippo_flag)):
            cs = torch.cat([cs, torch.zeros(B, max(need - cs.shape[1], cs.shape[1] // 2), core.FEAT, dtype=torch.float64)], 1)
        new_k, new_j = [], []
        hip = bool(float(self.hippo_flag))
        ra, rd, rm = _arousal_rates()
        nl = len(self.layers)
        blocks, tau_e, expo_l, dev_l, ar_l, rep_l = [], [[] for _ in range(nl)], [[] for _ in range(nl)], [], [], []
        hippo = {"recognition": [], "novelty": [], "source_t": []}
        f64 = f[..., :core.FEAT].double()
        cl = torch.cat([torch.zeros(B, 1, core.FEAT, dtype=torch.float64), f64.cumsum(1)], 1) if self.hind else None
        hs, hc = 0.0, 0.0
        nov_t, nov_v = [], []
        for s0 in range(0, T, BLOCK):
            fb = f[:, s0:s0 + BLOCK]
            Tb = fb.shape[1]
            n0 = base["n"]
            # the raw buffer: this block's features go in first (every read below looks strictly at earlier frames)
            if hip:
                tot = torch.gather(cs, 1, n0[:, None, None].expand(-1, 1, core.FEAT))[:, 0]
                cum = tot[:, None] + f64[:, s0:s0 + Tb].cumsum(1)
                for r in range(B):
                    cs[r, int(n0[r]) + 1:int(n0[r]) + 1 + Tb] = cum[r]
            st_read = {"kr": state["kr"], "kj": state["kj"], "kv": state["kv"], "qs": qs}
            replay, rec, src, _, _, hb = self.read(st_read, new_k, new_j, n0, ksum, kcnt, cs, (cl, s0, T) if self.hind else None)
            if hb is not None:
                hs, hc = hs + hb[0], hc + hb[1]
            nov = 1.0 - rec
            replay, rec_in = replay[:, :Tb], rec
            if not self.retrieval_on:
                replay, rec_in = torch.zeros_like(replay), torch.zeros_like(rec)
            rel_in = torch.cat([fb[..., :core.FEAT], fb[..., core.FEAT:], replay.reshape(B, Tb, 4 * core.FEAT), rec_in[:, None, None].expand(-1, Tb, 1)], -1)
            dev = (a - am) if self.modulation == "on" else torch.zeros_like(a)
            if self.skip_taps > 1:
                hist = torch.cat([base["f"][:, -(self.skip_taps - 1):], fb[..., :core.FEAT]], 1)
                skip_in = hist.unfold(1, self.skip_taps, 1).transpose(2, 3).reshape(B, Tb, self.skip_taps * core.FEAT)
            else:
                skip_in = fb[..., :core.FEAT]
            add, head_add, gain, expo = [], [], [], []
            for i in range(nl):
                add.append(self.relay[i](rel_in) if self.relay_on else None)
                head_add.append(self.skip[i](skip_in) if self.relay_on else None)
                gain.append(1.0 + self.w_g[i] * dev)
                expo.append((1.0 + self.w_tau[i] * dev).clamp(E_MIN, E_MAX))
            out, base = core.Core.forward(self, fb, base, {"add": add, "head_add": head_add, "gain": gain, "expo": expo})
            with torch.no_grad():
                idx = torch.arange(Tb)
                s_t = torch.zeros(B, Tb)
                for j, i in enumerate(AROUSAL_LAYERS):
                    hz = core.HORIZONS[i]
                    lv_all = torch.cat([lv[j], out[i]["logvar"]], 1)
                    lvp = lv_all[:, 1:1 + Tb]
                    e = 0.5 * (lvp + out[i]["err"] ** 2 * torch.exp(-lvp) + math.log(2 * math.pi)).mean(-1)
                    s_t = s_t + e * ((n0[:, None] + idx[None]) >= 2 * hz - 1).float()
                    lv[j] = lv_all[:, -2 * hz:]
                sn, an, amn, first = s_t.numpy(), a.numpy().copy(), am.numpy().copy(), (n0.numpy() == 0)
                ar = np.empty((B, Tb), np.float32)
                for t in range(Tb):
                    sv = sn[:, t]
                    an = an + np.where(sv > an, ra, rd) * (sv - an)
                    amn = np.where(first & (t == 0), an, amn + rm * (an - amn))
                    ar[:, t] = an
                a, am = torch.from_numpy(an.astype(np.float32)), torch.from_numpy(amn.astype(np.float32))
                ar_l.append(torch.from_numpy(ar))
            # four entries (one per 0.5 s), from the L3 + L4 modes at the tick frame and the raw features of the last 2 s
            h3, h4 = out[2]["h"], out[3]["h"]
            for i in range(0, Tb if hip else 0, TICK):
                t_song = n0 + i
                st_vec = F.layer_norm(torch.cat([h3[:, i].real, h3[:, i].imag, h4[:, i].real, h4[:, i].imag], -1), (4 * core.N,))
                key = self.key_proj(torch.cat([self._pooled(cs, t_song), st_vec], -1))
                new_k.append(key)
                new_j.append(t_song // TICK)
                ksum, kcnt = ksum + key, kcnt + 1
                if self.novelty_lane:
                    with torch.no_grad():
                        kr_all = torch.cat([state["kr"]] + [torch.stack(new_k, 1)], 1).detach()
                        kj_all = torch.cat([state["kj"]] + [torch.stack(new_j, 1)], 1)
                        kv_all = torch.cat([state["kv"], torch.ones(B, len(new_k), dtype=torch.bool)], 1)
                        kc = self._centre(kr_all, ksum.detach(), kcnt)
                        qn = self._centre(key.detach(), ksum.detach(), kcnt)
                        sm = torch.einsum("bd,bkd->bk", qn, kc)
                        el = kv_all & (kj_all * TICK <= (t_song[:, None] - MIN_AGE))
                        mx = torch.where(el, sm, torch.full_like(sm, -2.0)).max(1).values
                        nov_v.append(torch.where(el.any(1), 1.0 - mx, torch.ones(B)))
                        nov_t.append(t_song)
            qs = torch.cat([h3[:, -1].real, h3[:, -1].imag, h4[:, -1].real, h4[:, -1].imag], -1)
            blocks.append(out)
            for i in range(nl):
                e_i = expo[i].detach()
                expo_l[i].append(e_i)
                tau_e[i].append(torch.median(core.DT / torch.exp(self.layers[i].nu_log.detach())) / e_i)
            dev_l.append(dev)
            hippo["recognition"].append(rec[:, None].expand(-1, Tb))
            hippo["novelty"].append(nov[:, None].expand(-1, Tb))
            hippo["source_t"].append(torch.where(src >= 0, src.float() / 100.0, -torch.ones(B))[:, None].expand(-1, Tb))
            if return_replay:
                rep_l.append(replay)
        outs = [{k: torch.cat([blk[i][k] for blk in blocks], 1) for k in ("h", "mean", "logvar", "err", "x")} for i in range(nl)]
        for i in range(nl):
            outs[i]["tau_eff"] = torch.stack(tau_e[i], 1)
            outs[i]["expo"] = torch.stack(expo_l[i], 1)
        outs[0]["hippo"] = {k: torch.cat(v, 1) for k, v in hippo.items()}
        outs[0]["arousal"] = torch.cat(ar_l, 1)
        outs[0]["dev"] = torch.stack(dev_l, 1)
        if return_replay:
            outs[0]["replay"] = torch.cat(rep_l, 1)
        if self.hind:
            outs[0]["hind"] = hs / max(float(hc), 1.0) if hc else torch.zeros(())
        if nov_v:
            outs[0]["novelty_lane"] = {"t": torch.stack(nov_t, 1), "novelty": torch.stack(nov_v, 1)}
        kr = torch.cat([state["kr"]] + ([torch.stack(new_k, 1)] if new_k else []), 1)
        kj = torch.cat([state["kj"]] + ([torch.stack(new_j, 1)] if new_j else []), 1)
        kv = torch.cat([state["kv"]] + ([torch.ones(B, len(new_k), dtype=torch.bool)] if new_k else []), 1)
        st = {**base, "lv": lv, "cs": cs, "kr": kr, "kj": kj, "kv": kv, "ksum": ksum, "kcnt": kcnt, "qs": qs, "a": a, "amean": am}
        return outs, st
