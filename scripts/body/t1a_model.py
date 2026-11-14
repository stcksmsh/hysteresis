"""WO38 T1a model (rules docs/T1A_RULES.md sections 2-4): VQ autoencoder over 0.5 s gesture chunks. Brain env (torch CPU)."""
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

CH, WIN_CH, D = 50, 40, 64
FLOOR = 0.05
BOX = 7                                                                   # +-7 steps smoothing of the amplitude series (right reach 7)
DECAY, EPS, COMMIT = 0.99, 1e-5, 0.25
RESET_EVERY, RESET_FRAC = 100, 0.05


def vigour(x):
    """x (..., 50, 5) scaled chunks -> (a, a_n, u): RMS, floored RMS, normalised chunk u = x / a_n"""
    a = x.pow(2).mean((-2, -1)).sqrt()
    a_n = a.clamp_min(FLOOR)
    return a, a_n, x / a_n[..., None, None]


class VQ(nn.Module):
    def __init__(self, k, d=D):
        super().__init__()
        self.k, self.d = k, d
        self.register_buffer("cb", torch.zeros(k, d))
        self.register_buffer("count", torch.ones(k))
        self.register_buffer("sums", torch.zeros(k, d))
        self.register_buffer("init", torch.zeros(()))

    def nearest(self, z):
        return torch.cdist(z, self.cb).argmin(1)

    def forward(self, z, gen=None):
        """z (N, d) -> (zq straight-through, idx, commitment loss). In training: first-batch init, EMA update"""
        if self.training:
            if not self.init:
                i = torch.randperm(len(z), generator=gen)[:self.k]
                if len(i) < self.k:
                    i = torch.cat([i, torch.randint(len(z), (self.k - len(i),), generator=gen)])
                self.cb.copy_(z.detach()[i])
                self.sums.copy_(self.cb)
                self.init.fill_(1)
        idx = self.nearest(z.detach())
        e = self.cb[idx]
        commit = F.mse_loss(z, e.detach())
        if self.training:
            self.ema(z.detach(), idx)
        return z + (e - z).detach(), idx, commit

    @torch.no_grad()
    def ema(self, z, idx):
        oh = F.one_hot(idx, self.k).float()
        self.count.mul_(DECAY).add_(oh.sum(0), alpha=1 - DECAY)
        self.sums.mul_(DECAY).add_(oh.t() @ z, alpha=1 - DECAY)
        n = self.count.sum()
        cs = (self.count + EPS) / (n + self.k * EPS) * n
        self.cb.copy_(self.sums / cs[:, None])

    @torch.no_grad()
    def reset_dead(self, z, gen=None, noise=0.01):
        """rules 3: a code whose EMA count is below RESET_FRAC x (chunks per batch / K) takes a random encoder output (plus noise); count -> uniform value, sum -> count x vector. -> number reset"""
        uni = len(z) / self.k
        dead = (self.count < RESET_FRAC * uni).nonzero().flatten()
        if len(dead):
            i = torch.randint(len(z), (len(dead),), generator=gen)
            v = z[i] + noise * torch.randn(len(dead), self.d, generator=gen)
            self.cb[dead] = v
            self.count[dead] = uni
            self.sums[dead] = uni * v
        return int(len(dead))


class Encoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.c = nn.Sequential(nn.Conv1d(5, 64, 5, padding=2), nn.GELU(), nn.Conv1d(64, 128, 5, stride=2, padding=2), nn.GELU(), nn.Conv1d(128, 128, 5, stride=2, padding=2), nn.GELU())
        self.fc = nn.Linear(128 * 13, D)

    def forward(self, u):
        """u (N, 50, 5) -> (N, D)"""
        return self.fc(self.c(u.transpose(1, 2)).flatten(1))


class Decoder(nn.Module):
    """whole windows: e (B, T, D) token vectors, a_n (B, T) amplitudes -> (B, T * 50, 5). Right reach 5 + 5 + 4 + BOX = 21 steps"""

    def __init__(self):
        super().__init__()
        self.inp = nn.Linear(D, 64)
        self.c1, self.c2, self.c3 = nn.Conv1d(64, 128, 11), nn.Conv1d(128, 128, 11), nn.Conv1d(128, 5, 9)

    def forward(self, e, a_n):
        x = self.inp(e).repeat_interleave(CH, 1).transpose(1, 2)
        x = F.gelu(self.c1(F.pad(x, (5, 5))))
        x = F.gelu(self.c2(F.pad(x, (5, 5))))
        x = self.c3(F.pad(x, (4, 4)))
        a = a_n.repeat_interleave(CH, 1)[:, None]
        a = F.avg_pool1d(F.pad(a, (BOX, BOX)), 2 * BOX + 1, stride=1)         # box filter, zero padded
        return (x * a).transpose(1, 2)


class VQAE(nn.Module):
    def __init__(self, k):
        super().__init__()
        self.enc, self.vq, self.dec = Encoder(), VQ(k), Decoder()

    def forward(self, w, gen=None):
        """w (B, 2000, 5) scaled windows -> dict(recon (B, 2000, 5), idx (B*40,), commit, a_n (B, 40))"""
        B = len(w)
        x = w.reshape(B * WIN_CH, CH, 5)
        _, a_n, u = vigour(x)
        zq, idx, commit = self.vq(self.enc(u), gen)
        return dict(recon=self.dec(zq.reshape(B, WIN_CH, D), a_n.reshape(B, WIN_CH)), idx=idx, commit=commit, a_n=a_n.reshape(B, WIN_CH), z=zq)
