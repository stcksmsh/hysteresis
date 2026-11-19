"""H4 (docs/BRAIN_SPEC.md 7.16 point 3): uncertainty-based arbitration between the cortex and the hippocampal replay, after Daw, Niv & Dayan, "Uncertainty-based
competition between prefrontal and dorsolateral striatal systems for behavioral control", Nature Neuroscience 8(12):1704-1711, 2005 (reference from memory,
NOT verified against the paper). Nothing is trained: the cortex is the frozen toy cortex of H3, the code and store are H2's (fixed sparse random code, one-shot
store, 17 s eligibility, top-4 softmax), the replay is the B7 pointer replay of that horizon's target from the top-k sources.

Per layer i (horizon h frames), the prediction made at frame t is for the window [t + h, t + 2h). Its target has arrived at frame t + 2h - 1. Both systems are scored
on arrived targets only:
  err_c[u]  the cortex's error at frame u (the model's own err: window mean ending at u minus the cortex mean made at u - 2h + 1), valid for u >= 2h - 1
  err_h[u]  = err_c[u] + (mu_c - replay)[s], s = u - 2h + 1: the window mean minus the replay made at s; valid where a source existed at s (has[s])
  q_c[u], q_h[u]  mean over the 44 features of the squared errors
  e_c[t]  = mean of q_c[u] over the last WINDOW frames u in (t - WINDOW, t], u valid (WINDOW = 100, i.e. 1 s; try 2: 200)
  e_h[t]  = mean of q_h[u] over the same frames, u valid for the hippocampus. If no u is valid in the window, w[t] = 0 (no evidence: cortex only).
Causal: w[t] uses errors at frames u <= t, which score predictions made at s <= t - 2h + 1, with targets that ended by u <= t; no target after t enters.
  w = (1/e_h) / (1/e_h + 1/e_c) = e_c / (e_c + e_h), each e floored at EPS = 1e-6
  mean = (1 - w) mu_c + w replay; var = (1 - w) var_c + w VAR_H + w (1 - w) (mu_c - replay)^2 with VAR_H = 0.05, logvar clamped (H3's blend, same formula);
  err of the blend = err_c + (mu_c - mu)[s] for u >= 2h - 1 (as H3).
out[i] keeps mean_c / logvar_c / err_c and adds w (B, T, 1), e_c, e_h (B, T). A single call from the initial state.
"""
import torch

import core
import hippo_h2
import hippo_h3

EPS = 1e-6
WINDOW = 100


def running_mean(q, valid, window):
    """q (B, T) values, valid (B, T) bool -> (B, T) mean of q over the valid entries among the last `window` frames (t - window, t]; count (B, T)."""
    z = torch.where(valid, q, torch.zeros_like(q))
    cs = torch.cat([torch.zeros_like(z[:, :1]), z.cumsum(1)], 1)
    cn = torch.cat([torch.zeros_like(z[:, :1]), valid.float().cumsum(1)], 1)
    T = q.shape[1]
    t = torch.arange(T)
    lo = (t + 1 - window).clamp(min=0)
    num, cnt = cs[:, t + 1] - cs[:, lo], cn[:, t + 1] - cn[:, lo]
    return num / cnt.clamp(min=1), cnt


def arbitrate_layer(err_c, mu_c, rep, has, hz, window):
    """One layer. err_c, mu_c, rep (B, T, 44); has (B, T) bool -> w (B, T), e_c (B, T), e_h (B, T) as the module doc defines them."""
    T = has.shape[1]
    valid_c = torch.arange(T)[None].expand_as(has) >= 2 * hz - 1
    q_c = (err_c ** 2).mean(-1)
    q_h = torch.zeros_like(q_c)
    valid_h = torch.zeros_like(valid_c)
    if T >= 2 * hz:
        err_h = err_c[:, 2 * hz - 1:] + (mu_c - rep)[:, :T - 2 * hz + 1]
        q_h[:, 2 * hz - 1:] = (err_h ** 2).mean(-1)
        valid_h[:, 2 * hz - 1:] = has[:, :T - 2 * hz + 1]
    e_c, _ = running_mean(q_c, valid_c, window)
    e_h, n_h = running_mean(q_h, valid_h, window)
    e_c, e_h = e_c.clamp(min=EPS), e_h.clamp(min=EPS)
    return e_c / (e_c + e_h) * (n_h > 0).float(), e_c, e_h


class Core7H4(hippo_h2.Core7H2):
    def __init__(self, *a, window=WINDOW, **kw):
        super().__init__(*a, **kw)
        self.window = window
        self.arbitrate = True
        self.retrieval_on = False
        self.tap_replay = True

    def freeze_all(self):
        for p in self.parameters():
            p.requires_grad_(False)
        return self

    def forward(self, f, state, return_replay=False):
        if int(state["n"].max()) != 0:
            raise ValueError("H4's error bookkeeping needs a single call from the initial state")
        out, st = super().forward(f, state, return_replay)
        has = (out[0]["hippo"]["source_t"] >= 0)                              # (B, T)
        rep = out[0]["replay_true"]                                           # (B, T, 4, 44)
        T = has.shape[1]
        for i, hz in enumerate(core.HORIZONS):
            o = out[i]
            mu_c, lv_c, err_c = o["mean"], o["logvar"], o["err"]
            delta = mu_c - rep[:, :, i]                                       # at the frame the prediction was made
            w, e_c, e_h = arbitrate_layer(err_c, mu_c, rep[:, :, i], has, hz, self.window)
            w = (w * float(self.arbitrate))[..., None]
            mu = (1 - w) * mu_c + w * rep[:, :, i]
            var = (1 - w) * torch.exp(lv_c) + w * hippo_h3.VAR_H + w * (1 - w) * delta ** 2
            err = err_c.clone()
            if T >= 2 * hz:
                err[:, 2 * hz - 1:] = err_c[:, 2 * hz - 1:] + (mu_c - mu)[:, :T - 2 * hz + 1]
            o.update(mean_c=mu_c, logvar_c=lv_c, err_c=err_c, w=w, e_c=e_c, e_h=e_h, mean=mu,
                     logvar=torch.log(var).clamp(core.LOGVAR_MIN, core.LOGVAR_MAX), err=err)
        return out, st
