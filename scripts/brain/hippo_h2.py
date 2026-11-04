"""H2 (docs/BODY_BRAIN_PLAN.md 4): a hippocampus built the way a hippocampus works. Core7 with its learned key / query projection replaced by

  dentate gyrus  a FIXED random projection (a buffer, seed SEED_H2, never trained) of [raw features pooled over 2 s, layer norm of the L3 + L4 modes]
                 to DG_DIM = 2,048 dimensions, top-k by value kept (K_SPARSE = 64), the rest zero, L2-normalised. No centring.
  CA3            one-shot storage: the base class appends one entry every TICK (0.5 s); the key is detached, so storing is not learned.
  retrieval      cosine against entries >= MIN_AGE (17 s) old, top-k 4, softmax(sim / tau) with a FIXED tau (log_tau frozen).
  CA1            the base relay (the pointer replay of the four horizon targets + recognition); it trains with the rest of the toy model.
Query and key use the same projection and the same input kind, so no gradient reaches the code (it is detached) and nothing about the code is learned.
Everything else is Core7 unchanged (read, replay, relay, novelty lane).
"""
import math

import torch
import torch.nn.functional as F

import core
import core_b7

SEED_H2 = 20261104
DG_DIM = 2048
K_SPARSE = 64
TAU_H2 = 0.05


class Core7H2(core_b7.Core7):
    def __init__(self, *a, k_sparse=K_SPARSE, tau=TAU_H2, dg_dim=DG_DIM, **kw):
        super().__init__(*a, **kw)
        d_in = core.FEAT + 4 * core.N
        g = torch.Generator().manual_seed(SEED_H2)
        self.register_buffer("dg_proj", torch.randn(d_in, dg_dim, generator=g) / math.sqrt(d_in))
        self.k_sparse = k_sparse
        for p in (self.key_proj.weight, self.query_proj.weight, self.log_tau):         # the H1 key machinery is not used here
            p.requires_grad_(False)
        with torch.no_grad():
            self.log_tau.fill_(math.log(tau))

    def init_state(self, B=1):
        st = super().init_state(B)
        st["kr"] = torch.zeros(B, 0, self.dg_proj.shape[1])
        st["ksum"] = torch.zeros(B, self.dg_proj.shape[1])
        return st

    def _code(self, x):
        with torch.no_grad():
            z = x.detach() @ self.dg_proj
            top = z.topk(self.k_sparse, dim=-1)
            return F.normalize(torch.zeros_like(z).scatter(-1, top.indices, top.values), dim=-1)

    def _key_of(self, x):
        return self._code(x)

    def _query_of(self, x):
        return self._code(x)

    def _centre(self, v, ksum, kcnt):
        return F.normalize(v, dim=-1)
