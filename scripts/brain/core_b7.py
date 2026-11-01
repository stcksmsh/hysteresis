"""B7 core (docs/BRAIN_SPEC.md 7.1): the B3 core plus a hippocampus, a thalamic relay and acting neuromodulation. All causal.

Fixed here, before any result (the spec is silent on all of these; B7_NOTES.md has the same list):
  blocks      The network runs in blocks of BLOCK = 50 frames (0.5 s), blocks in sequence, frames inside a block in parallel. Everything that
              needs a value "known at t" uses what the previous blocks produced. A chunk must start on a block edge (n % 50 == 0); only the
              last chunk of a song may end inside a block.
  store       Per row, entries in arrival order, one per block j (song block index): key_j from the L3 + L4 modes at the block's first frame,
              and the block's mean features m_j (44). value_j = mean(m_j .. m_{j+3}) = the features over [t, t + 2 s), t = 0.5 j. The entry is
              eligible at block J when t <= 0.5 J - 8 s (age >= 8 s at the block start, i.e. J - j >= 16), so its value (2 s) is long known.
              A new song (reset_rows) empties that row. Store tensors are detached at the chunk edge (detach_state), so gradients reach only keys of the
              current chunk; the values are input features and carry no gradient anyway.
  read        Once per block, with the query from the L3 + L4 modes of the LAST frame of the previous block (the current frame's state needs
              the relay's input, which needs the read: a cycle; this is the freshest causal state). All frames of a block share the read.
              query / key = L2-normalised Linear(4 N -> 64, no bias) of the layer-normed [Re, Im] modes of L3 and L4 (1,024 values).
              top-k = 4 by cosine, softmax(sim / tau), tau = exp(log_tau) learned (init 0.1). Empty store (no eligible entry): recognition 0,
              novelty 1, retrieved value zeros. Partial store (< 4 eligible): the softmax runs over the eligible ones.
  relay       layer input = layer input + Linear(91 -> 128, no bias) of [44 features, grid phase (2), retrieved value (44), recognition (1)].
              Head skip: Linear(44 -> 88, no bias) of the current 44 features added to each head's output (mean and log-variance).
  arousal     per frame, from the L1 and L2 surprisal of predictions whose target window ended at t (zero until it exists; the sum over the
              layers that have a value), through a one-pole with rise tau 1 s and decay tau 8 s at 100 Hz; under no_grad. Running mean: a causal
              exponential mean, tau 60 s, started at the first arousal value of the song. dev = arousal - mean, both from the last frame of the
              previous block (0 in the first block).
  modulation  per layer and block: gain g = 1 + w_g dev on the drive u; exponent e = clamp(1 + w_tau dev, E_MIN, E_MAX) on |lam|, |lam_eff| =
              |lam|^e = exp(-nu e) < 1 always; theta (frequency) never changes. w_g, w_tau per layer, zero at init. Effective time constant
              of a layer in a block: median over modes of -dt / ln|lam_eff| = median(dt / nu) / e (reported per block as out[i]["tau_eff"]).
  zero init   every relay, skip, w_g, w_tau weight is zero, so B7 at step 0 equals B3. EXCEPTION: the key and query projections get a random
              init (seed SEED_B7), the same matrix for both (separate parameters, free to part). With both at zero, d sim / d W_q and d sim / d W_k
              are both zero (each is multiplied by the other projection's output): a saddle that no gradient leaves. With independent random
              matrices the cosine of two identical states is random (about 0), so a stored passage would not stand out when it returns. The
              projections do not touch the outputs while the relay weights are zero.
  switches    evaluation-time ablations on the same weights: `relay_on` (relay input and head skip zero), `retrieval_on` (retrieved value and
              recognition zero at the relay input; novelty is still computed), `modulation` ("on", or "frozen": dev = 0. With the arousal
              frozen at any constant, the running mean started at its first value equals it, so the modulation is the identity: the song
              mean itself does not matter).
State: the B3 state plus lv (L1, L2 log-variance history), the store (sk, sm, sj, sv), qs (query source), a, amean (arousal, mean).
"""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F

import core

SEED_B7 = 20261101
BLOCK = 50
KEY_DIM = 64
TOP_K = 4
MIN_AGE_BLOCKS = 16          # 8 s
VALUE_BLOCKS = 4             # 2 s
TAU_INIT = 0.1
E_MIN, E_MAX = 0.1, 10.0
TAU_RISE, TAU_FALL, TAU_MEAN = 1.0, 8.0, 60.0
N_REL = core.FEAT + 2 + core.FEAT + 1
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


class Core7(core.Core):
    def __init__(self, seed=core.SEED, phase=True, head_norm=True):
        super().__init__(seed, phase, head_norm)
        g = torch.Generator().manual_seed(SEED_B7)
        d_state = 4 * core.N
        self.key_proj = core._lin(g, d_state, KEY_DIM, bias=False)
        self.query_proj = core._lin(g, d_state, KEY_DIM, bias=False)
        with torch.no_grad():
            self.query_proj.weight.copy_(self.key_proj.weight)          # tied at init, separate after: identical states then match (see the docstring)
        self.log_tau = nn.Parameter(torch.tensor(math.log(TAU_INIT)))
        nl = len(core.BANDS)
        self.relay = nn.ModuleList(nn.Linear(N_REL, core.D, bias=False) for _ in range(nl))
        self.skip = nn.ModuleList(nn.Linear(core.FEAT, 2 * core.FEAT, bias=False) for _ in range(nl))
        for m in (*self.relay, *self.skip):
            nn.init.zeros_(m.weight)
        self.w_g = nn.Parameter(torch.zeros(nl))
        self.w_tau = nn.Parameter(torch.zeros(nl))
        self.relay_on, self.retrieval_on, self.modulation = True, True, "on"

    # ---- state ------------------------------------------------------------------------------------------------------

    def init_state(self, B=1):
        st = super().init_state(B)
        st.update({"lv": [torch.zeros(B, 2 * core.HORIZONS[i], core.FEAT) for i in AROUSAL_LAYERS],
                   "sk": torch.zeros(B, 0, KEY_DIM), "sm": torch.zeros(B, 0, core.FEAT), "sj": torch.zeros(B, 0, dtype=torch.long),
                   "sv": torch.zeros(B, 0, dtype=torch.bool), "qs": torch.zeros(B, 4 * core.N),
                   "a": torch.zeros(B), "amean": torch.zeros(B)})
        return st

    @staticmethod
    def detach_state(state):
        """Graph cut at the chunk edge; the store is also trimmed to the columns some row still needs (rows' old songs are invalid)."""
        st = core.Core.detach_state(state)
        sv = state["sv"]
        first = int(sv.any(0).nonzero()[0]) if sv.any() else sv.shape[1]
        st.update({"lv": [v.detach() for v in state["lv"]], "sk": state["sk"].detach()[:, first:], "sm": state["sm"].detach()[:, first:],
                   "sj": state["sj"][:, first:], "sv": sv[:, first:], "qs": state["qs"].detach(), "a": state["a"], "amean": state["amean"]})
        return st

    @staticmethod
    def reset_rows(state, rows):
        st = core.Core.reset_rows(state, rows)
        keep = torch.ones(state["n"].shape[0], dtype=torch.bool)
        keep[rows] = False
        k1 = keep.view(-1, 1)
        st.update({"lv": [v * k1.unsqueeze(-1).to(v.dtype) for v in state["lv"]], "sk": state["sk"], "sm": state["sm"], "sj": state["sj"],
                   "sv": state["sv"] & k1, "qs": state["qs"] * k1.to(state["qs"].dtype), "a": state["a"] * keep.float(),
                   "amean": state["amean"] * keep.float()})
        return st

    # ---- hippocampus -------------------------------------------------------------------------------------------------

    def _read(self, st, new_k, new_m, new_j, jr):
        """One read for every row. st: store tensors; new_*: this chunk's entries so far (lists, (B, .)); jr: (B,) song block index of the
        block being read. -> retrieved (B, 44), recognition (B,), source time in s (B,) (-1 where nothing is eligible), top-1 column (B,)."""
        B = jr.shape[0]
        if st["sk"].shape[1] + len(new_k) == 0:
            return torch.zeros(B, core.FEAT), torch.zeros(B), -torch.ones(B), None
        ms = torch.cat([st["sm"]] + ([torch.stack(new_m, 1)] if new_m else []), 1)
        js = torch.cat([st["sj"]] + ([torch.stack(new_j, 1)] if new_j else []), 1)
        vs = torch.cat([st["sv"]] + ([torch.ones(B, len(new_k), dtype=torch.bool)] if new_k else []), 1)
        q = F.normalize(self.query_proj(st["qs"]), dim=-1)
        sim = torch.cat([torch.einsum("bd,bkd->bk", q, st["sk"])] + ([torch.einsum("bd,bkd->bk", q, torch.stack(new_k, 1))] if new_k else []), 1)
        elig = vs & (js <= (jr[:, None] - MIN_AGE_BLOCKS))
        top_sim, top_idx = torch.where(elig, sim, torch.full_like(sim, -2.0)).topk(min(TOP_K, sim.shape[1]), dim=1)
        top_ok = torch.gather(elig, 1, top_idx)
        logits = torch.where(top_ok, top_sim / torch.exp(self.log_tau), torch.full_like(top_sim, -1e9))
        w = torch.softmax(logits, 1) * top_ok
        # value of column c = mean of the block means of columns c .. c + 3 (consecutive blocks of the same song)
        cols = (top_idx[..., None] + torch.arange(VALUE_BLOCKS)).clamp(max=ms.shape[1] - 1)
        val = torch.gather(ms, 1, cols.reshape(B, -1, 1).expand(-1, -1, core.FEAT)).reshape(B, top_idx.shape[1], VALUE_BLOCKS, core.FEAT).mean(2)
        retrieved = (w[..., None] * val).sum(1)
        has = top_ok[:, 0]
        rec = torch.where(has, top_sim[:, 0], torch.zeros_like(top_sim[:, 0]))
        src = torch.where(has, 0.5 * torch.gather(js, 1, top_idx[:, :1])[:, 0].float(), -torch.ones(B))
        return retrieved, rec, src, top_idx[:, 0]

    # ---- forward -----------------------------------------------------------------------------------------------------

    def forward(self, f, state):
        """f: (B, T, 46) -> (out, state) as core.Core.forward, with per layer also "tau_eff" and "expo" (B, nblocks) and, in out[0], "hippo"
        {recognition, novelty, source_t: (B, T) per frame (a block shares one read)} and "arousal" (B, T), "dev" (B, nblocks)."""
        if not self.phase:
            f = torch.cat([f[..., :core.FEAT], torch.zeros_like(f[..., core.FEAT:])], -1)
        B, T, _ = f.shape
        if int(state["n"][0]) % BLOCK:
            raise ValueError("a B7 chunk must start on a block edge (n a multiple of 50)")
        base = {k: state[k] for k in ("n", "f", "h", "q", "mean")}
        lv, qs, a, am = list(state["lv"]), state["qs"], state["a"], state["amean"]
        new_k, new_m, new_j = [], [], []
        ra, rd, rm = _arousal_rates()
        nl = len(self.layers)
        blocks, tau_e, expo_l, dev_l, ar_l, hippo = [], [[] for _ in range(nl)], [[] for _ in range(nl)], [], [], {"recognition": [], "novelty": [], "source_t": []}
        for s0 in range(0, T, BLOCK):
            fb = f[:, s0:s0 + BLOCK]
            Tb = fb.shape[1]
            n0 = base["n"]
            jr = n0 // BLOCK
            retrieved, rec, src, _ = self._read(state, new_k, new_m, new_j, jr)
            nov = 1.0 - rec
            if not self.retrieval_on:
                retrieved, rec_in = torch.zeros_like(retrieved), torch.zeros_like(rec)
            else:
                rec_in = rec
            rel_in = torch.cat([fb[..., :core.FEAT], fb[..., core.FEAT:], retrieved[:, None].expand(-1, Tb, -1), rec_in[:, None, None].expand(-1, Tb, 1)], -1)
            dev = (a - am) if self.modulation == "on" else torch.zeros_like(a)
            add, head_add, gain, expo = [], [], [], []
            for i in range(nl):
                if self.relay_on:
                    add.append(self.relay[i](rel_in))
                    head_add.append(self.skip[i](fb[..., :core.FEAT]))
                else:
                    add.append(None)
                    head_add.append(None)
                gain.append(1.0 + self.w_g[i] * dev)
                expo.append((1.0 + self.w_tau[i] * dev).clamp(E_MIN, E_MAX))
            out, base = core.Core.forward(self, fb, base, {"add": add, "head_add": head_add, "gain": gain, "expo": expo})
            # arousal from L1 and L2 surprisal of predictions whose target window ended inside this block
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
                ar = []
                for t in range(Tb):
                    sv = s_t[:, t]
                    a = a + torch.where(sv > a, ra, rd) * (sv - a)
                    am = torch.where(n0 + t == 0, a, am + rm * (a - am))
                    ar.append(a)
                ar_l.append(torch.stack(ar, 1))
            # write this block's entry and carry the query source
            h3, h4 = out[2]["h"], out[3]["h"]
            key_src = F.layer_norm(torch.cat([h3[:, 0].real, h3[:, 0].imag, h4[:, 0].real, h4[:, 0].imag], -1), (4 * core.N,))
            new_k.append(F.normalize(self.key_proj(key_src), dim=-1))
            new_m.append(fb[..., :core.FEAT].mean(1))
            new_j.append(jr)
            qs = F.layer_norm(torch.cat([h3[:, -1].real, h3[:, -1].imag, h4[:, -1].real, h4[:, -1].imag], -1), (4 * core.N,))
            state = {**state, "qs": qs}
            blocks.append(out)
            for i in range(nl):
                e_i = expo[i].detach()
                expo_l[i].append(e_i)
                tau_e[i].append(torch.median(core.DT / torch.exp(self.layers[i].nu_log.detach())) / e_i)
            dev_l.append(dev)
            hippo["recognition"].append(rec[:, None].expand(-1, Tb))
            hippo["novelty"].append(nov[:, None].expand(-1, Tb))
            hippo["source_t"].append(src[:, None].expand(-1, Tb))
        outs = [{k: torch.cat([blk[i][k] for blk in blocks], 1) for k in ("h", "mean", "logvar", "err", "x")} for i in range(nl)]
        for i in range(nl):
            outs[i]["tau_eff"] = torch.stack(tau_e[i], 1)
            outs[i]["expo"] = torch.stack(expo_l[i], 1)
        outs[0]["hippo"] = {k: torch.cat(v, 1) for k, v in hippo.items()}
        outs[0]["arousal"] = torch.cat(ar_l, 1)
        outs[0]["dev"] = torch.stack(dev_l, 1)
        # carry: B3 state from the last block; store = old store + this chunk's entries
        sk = torch.cat([state["sk"]] + ([torch.stack(new_k, 1)] if new_k else []), 1)
        sm = torch.cat([state["sm"]] + ([torch.stack(new_m, 1)] if new_m else []), 1)
        sj = torch.cat([state["sj"]] + ([torch.stack(new_j, 1)] if new_j else []), 1)
        sv = torch.cat([state["sv"]] + ([torch.ones(B, len(new_k), dtype=torch.bool)] if new_k else []), 1)
        st = {**base, "lv": lv, "sk": sk, "sm": sm, "sj": sj, "sv": sv, "qs": state["qs"], "a": a, "amean": am}
        return outs, st
