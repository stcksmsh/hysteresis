"""WO39 T1a2 model (rules docs/T1A2_RULES.md sections 3-4): spline-head decoder, residual quantiser, VQAE2 (Run A single codebook, Run B 2 x 1024). Brain env (torch CPU)."""
import torch
import torch.nn as nn
import torch.nn.functional as F

import t1a_model as M

CH, WIN_CH, D, BOX = M.CH, M.WIN_CH, M.D, M.BOX
ROWS = CH * WIN_CH                                                       # 2000
STEP = 4                                                                 # control point every 4 rows (40 ms)
NCTRL = ROWS // STEP + 3                                                 # control points j = -1 .. 501
_t = torch.arange(STEP) / STEP
BASIS = torch.stack([(1 - _t) ** 3 / 6, (3 * _t ** 3 - 6 * _t ** 2 + 4) / 6, (-3 * _t ** 3 + 3 * _t ** 2 + 3 * _t + 1) / 6, _t ** 3 / 6], 1)   # (phase, tap m = -1..2)
TOK_OF_CTRL = ((torch.arange(NCTRL) - 1) * STEP // CH).clamp(0, WIN_CH - 1)                                                                   # token of control point j = k - 1


class SplineDecoder(nn.Module):
    """e (B, 40, D) token vectors, a_n (B, 40) amplitudes -> (B, 2000, 5). Right reach: convs 4 control points (16 rows) + spline 2 (8 rows) = 24 rows <= 25"""

    def __init__(self):
        super().__init__()
        self.inp = nn.Linear(D, 64)
        self.c1, self.c2, self.c3 = nn.Conv1d(64, 128, 5), nn.Conv1d(128, 128, 5), nn.Conv1d(128, 5, 3)

    def forward(self, e, a_n):
        x = self.inp(e)[:, TOK_OF_CTRL].transpose(1, 2)                 # (B, 64, 503)
        x = F.gelu(self.c1(F.pad(x, (2, 2))))
        x = F.gelu(self.c2(F.pad(x, (2, 2))))
        c = self.c3(F.pad(x, (2, 0)))                                    # (B, 5, 503) control values, index k = j + 1
        y = torch.einsum("bcin,pn->bcip", c.unfold(-1, 4, 1), BASIS).reshape(len(c), 5, ROWS)      # row 4 i + p uses controls k = i .. i + 3 (j = i-1 .. i+2)
        a = a_n.repeat_interleave(CH, 1)[:, None]
        a = F.avg_pool1d(F.pad(a, (BOX, BOX)), 2 * BOX + 1, stride=1)
        return (y * a).transpose(1, 2)


class ResVQ(nn.Module):
    """2-stage residual quantiser: stage 1 quantises z, stage 2 the residual z - e1 (each an EMA VQ with dead-code reset); output value e1 + e2, straight-through to z"""

    def __init__(self, k):
        super().__init__()
        self.vq1, self.vq2 = M.VQ(k), M.VQ(k)
        self.k = k

    def forward(self, z, gen=None):
        _, i1, c1 = self.vq1(z, gen)
        e1 = self.vq1.cb[i1]
        r = z - e1.detach()
        _, i2, c2 = self.vq2(r, gen)
        e2 = self.vq2.cb[i2]
        return z + (e1 + e2 - z).detach(), (i1, i2), c1 + c2

    @torch.no_grad()
    def reset_dead(self, z, gen=None):
        e1 = self.vq1.cb[self.vq1.nearest(z)]
        return self.vq1.reset_dead(z, gen) + self.vq2.reset_dead(z - e1, gen)


class VQAE2(nn.Module):
    def __init__(self, k, residual=False):
        super().__init__()
        self.enc, self.dec, self.residual = M.Encoder(), SplineDecoder(), residual
        self.vq = ResVQ(k) if residual else M.VQ(k)
        self.k = k

    def forward(self, w, gen=None):
        B = len(w)
        _, a_n, u = M.vigour(w.reshape(B * WIN_CH, CH, 5))
        zq, idx, commit = self.vq(self.enc(u), gen)
        return dict(recon=self.dec(zq.reshape(B, WIN_CH, D), a_n.reshape(B, WIN_CH)), idx=idx, commit=commit, a_n=a_n.reshape(B, WIN_CH))
