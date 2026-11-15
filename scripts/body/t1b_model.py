"""WO41 T1b model (docs/T1B_RULES.md section 3): listener (rhythm 192 / affect 64) + planner (GRU 256, attention over 32 tokens, categorical heads). Brain env (torch CPU)."""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F

WIDTH, STEP_HZ, DT = 2105, 50, 0.02
NR, NA = 192, 64
LAG = 13                       # planner for token k reads listener step 25 k - 13 (docs/T1B_CAUSAL.md section D)
MEM = 32


def step_of_token(k):
    return 25 * k - LAG


class Listener(nn.Module):
    """x (B, T, WIDTH) at 50 Hz (standardised) -> states (B, T, 256), carried state h. Leaky tanh units, learned per-unit time constants, full recurrent matrix (cross-connections)."""

    def __init__(self, d_in=WIDTH, d_proj=128, p_drop=0.2):
        super().__init__()
        n = NR + NA
        self.proj, self.drop, self.U = nn.Linear(d_in, d_proj), nn.Dropout(p_drop), nn.Linear(d_proj, n)
        self.W = nn.Linear(n, n, bias=False)
        nn.init.orthogonal_(self.W.weight, 0.9)
        lt = torch.cat([torch.empty(NR).uniform_(math.log(0.1), math.log(1.0)), torch.empty(NA).uniform_(math.log(2.0), math.log(30.0))])
        self.log_tau = nn.Parameter(lt)

    def forward(self, x, h=None):
        B, T, _ = x.shape
        u = self.U(self.drop(self.proj(x)))
        a = 1 - torch.exp(-DT / torch.exp(self.log_tau))
        h = torch.zeros(B, NR + NA) if h is None else h
        out = []
        for t in range(T):
            h = (1 - a) * h + a * torch.tanh(self.W(h) + u[:, t])
            out.append(h)
        return torch.stack(out, 1), h


class Planner(nn.Module):
    """One step per token. Inputs: listener state (256), embeddings of the previous token's (code stages, vigour bin, posture stages); GRUCell 256; single-head attention over the
    last MEM hidden states of its own tokens; heads: code stage 1, code stage 2 | stage 1, vigour bin, posture stage(s) (stage 2 | stage 1 when posture has 2 stages)."""

    def __init__(self, k_code=1024, n_vig=32, n_post=(256,), d=256, emb=(32, 16, 32)):
        super().__init__()
        self.k_code, self.n_vig, self.n_post, self.d = k_code, n_vig, tuple(n_post), d
        ec, ev, ep = emb
        self.e_c1, self.e_c2, self.e_v = nn.Embedding(k_code, ec), nn.Embedding(k_code, ec), nn.Embedding(n_vig, ev)
        self.e_p = nn.ModuleList(nn.Embedding(n, ep) for n in self.n_post)
        self.gru = nn.GRUCell(NR + NA + 2 * ec + ev + ep * len(self.n_post), d)
        self.q, self.k, self.v, self.o = (nn.Linear(d, d) for _ in range(4))
        self.ln = nn.LayerNorm(d)
        self.h_c1, self.h_c2, self.h_v = nn.Linear(d, k_code), nn.Linear(d + ec, k_code), nn.Linear(d, n_vig)
        self.h_p = nn.ModuleList(nn.Linear(d + (ep if i else 0), n) for i, n in enumerate(self.n_post))
        self.ec, self.ep = ec, ep

    def zero_state(self, B):
        return dict(h=torch.zeros(B, self.d), mem=torch.zeros(B, 0, self.d), prev=None)

    def forward_step(self, s, lis, prev):
        """s state, lis (B, 256), prev = (c1, c2, v, p) long tensors (B,) / p (B, stages), or None at the start -> (features (B, d), new state)"""
        B = len(lis)
        if prev is None:
            pe = torch.zeros(B, 2 * self.ec + self.e_v.embedding_dim + self.ep * len(self.n_post))
        else:
            c1, c2, v, p = prev
            pe = torch.cat([self.e_c1(c1), self.e_c2(c2), self.e_v(v)] + [e(p[:, i]) for i, e in enumerate(self.e_p)], -1)
        h = self.gru(torch.cat([lis, pe], -1), s["h"])
        mem = s["mem"]
        if mem.shape[1]:
            att = torch.softmax((self.q(h)[:, None] * self.k(mem)).sum(-1) / math.sqrt(self.d), 1)
            ctx = self.o((att[..., None] * self.v(mem)).sum(1))
        else:
            ctx = torch.zeros_like(h)
        f = self.ln(h + ctx)
        mem = torch.cat([mem, h[:, None]], 1)[:, -MEM:]
        return f, dict(h=h, mem=mem)

    def logits(self, f, c1, p=None):
        """heads given the gold (or sampled) earlier stages: code stage 2 needs c1; posture stage 2 needs its stage 1"""
        out = dict(c1=self.h_c1(f), v=self.h_v(f))
        if c1 is not None:
            out["c2"] = self.h_c2(torch.cat([f, self.e_c1(c1)], -1))
        out["p"] = [self.h_p[0](f)]
        if p is not None and len(self.n_post) > 1:
            out["p"].append(self.h_p[1](torch.cat([f, self.e_p[0](p[:, 0])], -1)))
        return out


class Model(nn.Module):
    def __init__(self, n_post=(256,)):
        super().__init__()
        self.listener, self.planner = Listener(), Planner(n_post=n_post)

    def counts(self):
        n = lambda m: sum(p.numel() for p in m.parameters())
        pl = self.planner
        parts = dict(listener_projection=n(self.listener.proj), listener_input_U=n(self.listener.U), listener_recurrent_W_and_tau=n(self.listener.W) + self.listener.log_tau.numel(),
                     planner_embeddings=n(pl.e_c1) + n(pl.e_c2) + n(pl.e_v) + n(pl.e_p), planner_gru=n(pl.gru), planner_attention=n(pl.q) + n(pl.k) + n(pl.v) + n(pl.o) + n(pl.ln),
                     head_code1=n(pl.h_c1), head_code2=n(pl.h_c2), head_vigour=n(pl.h_v), head_posture=n(pl.h_p))
        parts["total"] = n(self)
        return parts


def run_window(model, lis, tok, state, prev, noise_p=0.0, gen=None):
    """lis (B, N, 256); tok c1, c2, v (B, N), p (B, N, S) -> ce dict of (B, N) tensors, new state, new prev (the last gold token)."""
    pl = model.planner
    B, N = lis.shape[:2]
    ce = dict(code=[], vig=[], post=[])
    for k in range(N):
        fed = prev
        if fed is not None and noise_p > 0:                                    # input-noise rule: each fed-back component is replaced by a random index with probability noise_p
            r = lambda x, n: torch.where(torch.rand(x.shape, generator=gen) < noise_p, torch.randint(0, n, x.shape, generator=gen), x)
            fed = (r(fed[0], pl.k_code), r(fed[1], pl.k_code), r(fed[2], pl.n_vig), torch.stack([r(fed[3][:, i], n) for i, n in enumerate(pl.n_post)], 1))
        f, state = pl.forward_step(state, lis[:, k], fed)
        c1, c2, v, p = tok["c1"][:, k], tok["c2"][:, k], tok["v"][:, k], tok["p"][:, k]
        lg = pl.logits(f, c1, p)
        ce["code"].append(F.cross_entropy(lg["c1"], c1, reduction="none") + F.cross_entropy(lg["c2"], c2, reduction="none"))
        ce["vig"].append(F.cross_entropy(lg["v"], v, reduction="none"))
        ce["post"].append(sum(F.cross_entropy(l, p[:, i], reduction="none") for i, l in enumerate(lg["p"])))
        prev = (c1, c2, v, p)
    return {k: torch.stack(v, 1) for k, v in ce.items()}, state, prev
