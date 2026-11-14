"""WO39 T1a2 tests (brain env): python -m pytest scripts/body/test_t1a2.py"""
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t1a2_model as M2  # noqa: E402
import t1a2_train as TR2  # noqa: E402


def test_bspline_basis_partition_of_unity_and_constant_reproduction():
    assert torch.allclose(M2.BASIS.sum(1), torch.ones(4), atol=1e-6)
    c = torch.full((1, 5, M2.NCTRL), 3.0)
    y = torch.einsum("bcin,pn->bcip", c.unfold(-1, 4, 1), M2.BASIS).reshape(1, 5, M2.ROWS)
    assert torch.allclose(y, torch.full_like(y, 3.0), atol=1e-5)
    ramp = torch.arange(M2.NCTRL, dtype=torch.float32)[None, None].repeat(1, 5, 1)             # linear controls -> a linear curve (B-spline reproduces linear data)
    r = torch.einsum("bcin,pn->bcip", ramp.unfold(-1, 4, 1), M2.BASIS).reshape(1, 5, M2.ROWS)[0, 0]
    assert torch.allclose(r[1:] - r[:-1], torch.full((M2.ROWS - 1,), 0.25), atol=1e-4)


def test_spline_decoder_causality_and_reach():
    torch.manual_seed(0)
    dec = M2.SplineDecoder().eval()
    e = torch.randn(1, 40, M2.D)
    a = torch.rand(1, 40) + 0.5
    base = dec(e, a)
    assert base.shape == (1, 2000, 5)
    for j in (5, 20, 39):
        e2, a2 = e.clone(), a.clone()
        e2[0, j] += 3.0
        a2[0, j] += 1.0
        d = (dec(e2, a2) - base).abs().amax((0, 2))
        start = j * 50
        assert d[:start - 25].max() == 0.0                                          # nothing earlier than 0.25 s before the token's chunk changes
        assert d[start - 24:start + 50].max() > 0.0                                 # but it reaches back (up to 24 rows) and its own chunk


def test_residual_quantiser_shapes_ema_and_reset():
    torch.manual_seed(0)
    q = M2.ResVQ(8)
    q.train()
    g = torch.Generator().manual_seed(1)
    z = torch.randn(256, 64) * 2
    z.requires_grad_(True)
    zq, (i1, i2), c = q(z, g)
    assert zq.shape == z.shape and i1.shape == (256,) and i2.shape == (256,) and c.item() > 0
    assert torch.allclose(zq.detach(), q.vq1.cb[i1] + q.vq2.cb[i2], atol=1e-5)
    zq.sum().backward()
    assert z.grad is not None                                                       # straight-through
    before = q.vq2.cb.clone()
    for _ in range(50):
        q(z.detach(), g)
    assert not torch.equal(before, q.vq2.cb)                                       # stage 2 codebook moved (EMA)
    err0 = (z.detach() - q.vq1.cb[q.vq1.nearest(z.detach())]).pow(2).mean()
    zq2, _, _ = q(z.detach(), g)
    assert (z.detach() - zq2).pow(2).mean() < err0                                  # the second stage reduces the residual
    assert q.reset_dead(z.detach(), g) >= 0


def test_weight_cap_sums():
    r = np.random.default_rng(0)
    d = dict(w=r.uniform(0.2, 1.0, 100).astype(np.float32), src=np.array([0] * 30 + [1] * 70, np.int8))
    f = TR2.cap_factor(d)
    w = np.where(d["src"] == 1, d["w"] * f, d["w"])
    assert abs(w[d["src"] == 1].sum() - w[d["src"] == 0].sum()) < 1e-4 and abs(w[d["src"] == 1].sum() / w.sum() - 0.5) < 1e-6


def test_bailando_loss_terms():
    r = torch.randn(3, 2000, 5)
    assert TR2.bailando_loss(r, r).abs().max() == 0
    x = torch.randn(1, 6, 5)
    y = x + 0.5                                                                      # constant offset: L1 0.5, velocity and acceleration differences 0
    assert abs(TR2.bailando_loss(y, x).item() - 0.5) < 1e-6
    ramp = torch.arange(6, dtype=torch.float32)[None, :, None].repeat(1, 1, 5)
    assert abs(TR2.bailando_loss(ramp * 2, ramp).item() - (ramp.mean().item() + 1.0)) < 1e-5     # recon L1 mean(ramp) + velocity |2-1| = 1 + acceleration 0


def test_vqae2_both_runs_shapes_and_gradients():
    torch.manual_seed(0)
    w = torch.randn(2, 2000, 5)
    for res in (False, True):
        m = M2.VQAE2(16, residual=res)
        o = m(w, torch.Generator().manual_seed(0))
        assert o["recon"].shape == (2, 2000, 5)
        (TR2.bailando_loss(o["recon"], w).mean() + o["commit"]).backward()
        assert all(p.grad is not None for p in m.enc.parameters())
