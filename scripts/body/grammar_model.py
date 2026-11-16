"""WO45 model of A, the motor grammar (docs/A_RULES.md section 2). Brain env (torch CPU).

Per token k of a 40-token window: GRU 256 over [control feature (temporal conv over tokens k .. k+H-1), style, previous token (gesture codes, a_n bin, posture codes), motif state];
heads: gesture code 1, code 2 | code 1, a_n bin, posture code 1, posture code 2 | posture code 1. No music input anywhere.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

CD = 18                    # control vector size (controls_lib.CTL_DIM)
H = 4                      # control horizon: the conv at token k reads controls k .. k + H - 1 (current token + next 1.5 s)
MOTIF_EVERY = 4            # motif update every 4 tokens = 2 s
N_TOKENS = 40              # tokens per window
D, DM, DS = 256, 64, 64    # GRU, motif, style sizes
K_CODE, N_VIG, N_POST = 1024, 32, 256
EMB = (32, 16, 32)         # code, vigour-bin, posture embeddings


class Grammar(nn.Module):
    def __init__(self, n_ds=4, n_copy=4, n_genre=8):
        super().__init__()
        ec, ev, ep = EMB
        self.e_ds, self.e_copy, self.e_genre = nn.Embedding(n_ds, 16), nn.Embedding(n_copy, 16), nn.Embedding(n_genre, 16)
        self.style = nn.Linear(48, DS)
        self.h0 = nn.Linear(DS, D)
        self.conv = nn.Conv1d(CD + 1, 64, H)
        self.e_c1, self.e_c2, self.e_v = nn.Embedding(K_CODE, ec), nn.Embedding(K_CODE, ec), nn.Embedding(N_VIG, ev)
        self.e_p1, self.e_p2 = nn.Embedding(N_POST, ep), nn.Embedding(N_POST, ep)
        self.gru = nn.GRUCell(64 + DS + 2 * ec + ev + 2 * ep + DM, D)
        self.motif = nn.GRUCell(D, DM)
        self.h_c1, self.h_c2, self.h_v = nn.Linear(D, K_CODE), nn.Linear(D + ec, K_CODE), nn.Linear(D, N_VIG)
        self.h_p1, self.h_p2 = nn.Linear(D, N_POST), nn.Linear(D + ep, N_POST)

    def style_vec(self, ds, copy, genre):
        return torch.tanh(self.style(torch.cat([self.e_ds(ds), self.e_copy(copy), self.e_genre(genre)], -1)))

    def ctl_feat(self, ctl, present):
        """ctl (B, N, CD), present (B, N) float {0, 1} -> (B, N, 64); output k depends on ctl[k .. k + H - 1] only (right zero padding, present = 0 there)"""
        x = torch.cat([ctl * present[..., None], present[..., None]], -1).transpose(1, 2)
        return F.gelu(self.conv(F.pad(x, (0, H - 1)))).transpose(1, 2)

    def zero_state(self, style):
        B = len(style)
        return dict(h=torch.tanh(self.h0(style)), m=torch.zeros(B, DM), hs=torch.zeros(B, MOTIF_EVERY, D), k=0)

    def step(self, st, feat, style, prev):
        """feat (B, 64) control feature of this token; prev = (c1, c2, v, p1, p2) long (B,) of the previous token or None (window start: zero embedding) -> (f (B, D), new state)"""
        B = len(feat)
        m, k = st["m"], st["k"]
        if k > 0 and k % MOTIF_EVERY == 0:
            m = self.motif(st["hs"].mean(1), m)                                       # every 2 s from the mean of the last 4 hidden states
        if prev is None:
            pe = torch.zeros(B, 2 * EMB[0] + EMB[1] + 2 * EMB[2])
        else:
            c1, c2, v, p1, p2 = prev
            pe = torch.cat([self.e_c1(c1), self.e_c2(c2), self.e_v(v), self.e_p1(p1), self.e_p2(p2)], -1)
        h = self.gru(torch.cat([feat, style, pe, m], -1), st["h"])
        hs = torch.cat([st["hs"][:, 1:], h[:, None]], 1)
        return h, dict(h=h, m=m, hs=hs, k=k + 1)

    def heads(self, f, c1=None, p1=None):
        out = dict(c1=self.h_c1(f), v=self.h_v(f), p1=self.h_p1(f))
        if c1 is not None:
            out["c2"] = self.h_c2(torch.cat([f, self.e_c1(c1)], -1))
        if p1 is not None:
            out["p2"] = self.h_p2(torch.cat([f, self.e_p1(p1)], -1))
        return out

    def counts(self):
        n = lambda *ms: sum(p.numel() for m in ms for p in m.parameters())
        parts = dict(style_embeddings_and_linear=n(self.e_ds, self.e_copy, self.e_genre, self.style) + n(self.h0), control_conv=n(self.conv), token_embeddings=n(self.e_c1, self.e_c2, self.e_v, self.e_p1, self.e_p2),
                     gru=n(self.gru), motif_gru=n(self.motif), head_code1=n(self.h_c1), head_code2=n(self.h_c2), head_vigour=n(self.h_v), head_posture1=n(self.h_p1), head_posture2=n(self.h_p2))
        parts["total"] = n(self)
        return parts


def corrupt_controls(ctl, pool, p_drop, p_corr, gen=None):
    """ctl (B, N, CD) float -> (ctl', present (B, N)). Corruption first: each token's whole control vector is replaced, with probability p_corr, by a whole vector drawn uniformly from `pool`
    (M, CD) = other training tokens (a realistic JOINT sample, never per-control). Then dropout: with probability p_drop the whole vector is removed (present = 0). Independent per token."""
    B, N, _ = ctl.shape
    out = ctl.clone()
    cm = torch.rand(B, N, generator=gen) < p_corr
    if cm.any():
        out[cm] = pool[torch.randint(0, len(pool), (int(cm.sum()),), generator=gen)]
    present = (torch.rand(B, N, generator=gen) >= p_drop).float()
    return out, present


def expected_controls(logits, mean):
    """logits (B, K), mean (K, CD) per-code control means -> (B, CD) expected controls under the softmax"""
    return F.softmax(logits, -1) @ mean


def aux_loss(exp_list, req, valid, sd, present):
    """exp_list: expected-control tensors (B, CD) of the four code sources at one token; req (B, CD) requested controls; valid (B, CD) bool defined-ness of the requested entries; sd (CD,) global sd;
    present (B,) float. Mean over the four sources of the mean over valid dims of ((E - req) / sd)^2, zero where the vector was dropped -> (B,)"""
    v = valid.float() * present[:, None]
    per = [((e - req) / sd).pow(2).mul(v).sum(-1) / v.sum(-1).clamp_min(1.0) for e in exp_list]
    return sum(per) / len(per)
