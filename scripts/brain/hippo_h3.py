"""H3 (docs/BRAIN_SPEC.md 7.15): blend memory. After kNN-LM (Khandelwal, Levy, Jurafsky, Zettlemoyer, Lewis, "Generalization through Memorization: Nearest
Neighbor Language Models", ICLR 2020, arXiv 1911.00172; reference from memory, NOT verified against the paper).

Core7H3 = Core7H2 (H2's fixed sparse random code, one-shot store, 17 s eligibility, top-4 softmax; unchanged and untrained) whose cortex is left as it is
(`retrieval_on` False: no replay or recognition reaches the relay) and whose per-layer prediction is a blend with the hippocampus's own prediction.
Per layer i, frame t (the prediction made at t for the window [t + h, t + 2h)):
  rec     the recognition of the block's read (top-1 cosine); has = a source exists (an eligible entry, read source frame >= 0)
  w       = has * sigmoid(a_i * (rec - b_i))                                       a_i, b_i: the ONLY trained parameters (8 numbers)
  replay  the B7 pointer replay of that horizon's target from the top-k sources (the oracle's path), mu_r
  mean    = (1 - w) * mu_c + w * mu_r
  var     = (1 - w) * var_c + w * VAR_H + w * (1 - w) * (mu_c - mu_r)^2           moment-matched two-component mixture; var_c = exp(cortex logvar);
                                                                                    VAR_H = 0.05 fixed (the replay carries no variance of its own)
  logvar  = clamp(log var, LOGVAR_MIN, LOGVAR_MAX)
  err     = the error of the blended prediction, scored when its window completes: err_c[t] + (mu_c - mu)[t - 2h + 1] for t >= 2h - 1, else 0
          (the cortex's own err is the window mean minus mu_c[t - 2h + 1]; the cortex's internal coupling still uses err_c: the cortex is unchanged).
out[i] keeps the cortex's values as mean_c / logvar_c / err_c and adds w (B, T, 1); out[i]["mean" | "logvar" | "err"] are the blend's, so train.chunk_terms and
toy_b7.t1_eval score the blend unchanged. A single call from the initial state (the err shift needs no history across calls).
"""
import math

import torch
import torch.nn as nn

import core
import hippo_h2

VAR_H = 0.05
A_INIT, B_INIT = 8.0, 0.5
TRAINED = ("blend_a", "blend_b")


class Core7H3(hippo_h2.Core7H2):
    def __init__(self, *a, a_init=A_INIT, b_init=B_INIT, **kw):
        super().__init__(*a, **kw)
        nl = len(core.BANDS)
        self.blend_a = nn.Parameter(torch.full((nl,), float(a_init)))
        self.blend_b = nn.Parameter(torch.full((nl,), float(b_init)))
        self.retrieval_on = False
        self.tap_replay = True

    def freeze_all_but_blend(self):
        for n, p in self.named_parameters():
            p.requires_grad_(n in TRAINED)
        return self

    def forward(self, f, state, return_replay=False):
        if int(state["n"].max()) != 0:
            raise ValueError("H3's err shift needs a single call from the initial state")
        out, st = super().forward(f, state, return_replay)
        rec = out[0]["hippo"]["recognition"]                                 # (B, T)
        has = (out[0]["hippo"]["source_t"] >= 0).float()
        rep = out[0]["replay_true"]                                          # (B, T, 4, 44)
        T = rec.shape[1]
        for i, hz in enumerate(core.HORIZONS):
            o = out[i]
            w = (has * torch.sigmoid(self.blend_a[i] * (rec - self.blend_b[i])))[..., None]
            mu_c, lv_c, err_c = o["mean"], o["logvar"], o["err"]
            mu = (1 - w) * mu_c + w * rep[:, :, i]
            var = (1 - w) * torch.exp(lv_c) + w * VAR_H + w * (1 - w) * (mu_c - rep[:, :, i]) ** 2
            err = err_c.clone()
            if T >= 2 * hz:
                err[:, 2 * hz - 1:] = err_c[:, 2 * hz - 1:] + (mu_c - mu)[:, :T - 2 * hz + 1]
            o.update(mean_c=mu_c, logvar_c=lv_c, err_c=err_c, w=w, mean=mu, logvar=torch.log(var).clamp(core.LOGVAR_MIN, core.LOGVAR_MAX), err=err)
        return out, st
