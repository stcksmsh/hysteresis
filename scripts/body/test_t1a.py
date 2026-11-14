"""WO38 T1a tests (brain env): python -m pytest scripts/body/test_t1a.py"""
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t1a_data as DD  # noqa: E402
import t1a_model as M  # noqa: E402


def test_chunking_only_in_kept_windows():
    t = 6000
    g = np.arange(t * 5, dtype=np.float32).reshape(t, 5)
    z = dict(win_pass=np.array([True, False, True]), gesture=g)
    w, keep = DD.kept_windows(z)
    assert keep.tolist() == [0, 2] and w.shape == (2, 2000, 5)
    assert np.array_equal(w[1], g[4000:6000])                                     # window 2 rows, nothing from the dropped window 1
    ch = DD.to_chunks(w)
    assert ch.shape == (2, 40, 50, 5) and np.array_equal(ch[1, 3], g[4150:4200])  # chunk 3 of window 2
    assert DD.kept_windows(dict(win_pass=np.array([False]), gesture=g[:2000]))[0].shape == (0, 2000, 5)


def test_vigour_round_trip_and_floor():
    r = np.random.default_rng(0)
    x = torch.tensor(r.normal(0, 1, (6, 50, 5)), dtype=torch.float32)
    x[0] *= 0.001                                                                  # a still chunk
    x[1] *= 7
    a, a_n, u = M.vigour(x)
    assert torch.allclose(u * a_n[:, None, None], x, atol=1e-6)
    assert a_n[0] == M.FLOOR and a[0] < M.FLOOR and u[0].pow(2).mean().sqrt() < 0.1
    assert abs(u[2].pow(2).mean().sqrt().item() - 1.0) < 1e-5 and abs(u[1].pow(2).mean().sqrt().item() - 1.0) < 1e-5


def test_decoder_causality_and_reach():
    torch.manual_seed(0)
    dec = M.Decoder().eval()
    e = torch.randn(1, 40, M.D)
    a = torch.rand(1, 40) + 0.5
    base = dec(e, a)
    for j in (5, 20, 39):                                                          # perturb token j (code and amplitude)
        e2, a2 = e.clone(), a.clone()
        e2[0, j] += 3.0
        a2[0, j] += 1.0
        d = (dec(e2, a2) - base).abs().amax((0, 2))
        start = j * M.CH
        assert d[:start - 25].max() == 0.0                                         # nothing earlier than 0.25 s before the token's chunk changes
        assert d[start - 21:start + M.CH + 21].max() > 0.0                         # but it does reach 21 steps back and its own chunk


def test_ema_update_and_dead_code_reset():
    torch.manual_seed(1)
    vq = M.VQ(4, 2)
    vq.train()
    pts = torch.cat([torch.randn(200, 2) * 0.05 + torch.tensor([3.0, 0.0]), torch.randn(200, 2) * 0.05 + torch.tensor([-3.0, 0.0])])
    g = torch.Generator().manual_seed(2)
    for _ in range(300):
        vq(pts, g)
    used = vq.nearest(pts).unique()
    assert len(used) <= 4 and (vq.cb[used].abs().amax(1) > 1.0).all()              # used codes sit on the two clusters
    assert abs(vq.cb[vq.nearest(pts[:200])[0]][0].item() - 3.0) < 0.2
    unused = set(range(4)) - set(vq.nearest(pts).tolist())
    n = vq.reset_dead(pts, g)
    assert n >= len(unused) and len(unused) >= 1 or n == 0
    for i in unused:                                                               # a reset code now sits on the data
        assert vq.cb[i].abs().amax() > 1.0
    assert vq.count.min() > 0


def test_full_model_shapes_and_straight_through_grad():
    torch.manual_seed(0)
    m = M.VQAE(16)
    w = torch.randn(2, 2000, 5)
    o = m(w, torch.Generator().manual_seed(0))
    assert o["recon"].shape == (2, 2000, 5) and o["idx"].shape == (80,)
    loss = (o["recon"] - w).pow(2).mean() + o["commit"]
    loss.backward()
    assert all(p.grad is not None for p in m.enc.parameters())                    # gradient reaches the encoder through the quantiser


def test_measures_identity_smoothing_and_sources():
    import t1a_eval as E
    r = np.random.default_rng(0)
    t = np.arange(2001) / 100.0
    orig = np.stack([np.stack([np.sin(2 * np.pi * (0.5 + 0.1 * i) * t) * 10 + r.normal(0, 0.3, 2001) for i in range(5)], 1) for _ in range(6)])
    src = np.array([0, 0, 0, 1, 1, 1])
    jit = lambda x: [dict(acc_sign_changes_per_s=float(np.sum(np.diff(np.sign(np.diff(x[:, i], 2))) != 0)) / 20.0, p_gt3=float(np.var(np.diff(x[:, i])))) for i in range(5)]
    same = E.measures(orig, orig, src, jit)
    assert set(same) == {"all", "finedance", "aioz"}
    assert all(abs(same["all"][j]["range_p5_p95"]["ratio"] - 1) < 1e-12 and abs(same["aioz"][j]["acc_sign_changes_per_s"]["ratio"] - 1) < 1e-12 for j in E.JN)
    k = np.ones(9) / 9
    sm = np.stack([np.stack([np.convolve(o[:, i], k, "same") for i in range(5)], 1) for o in orig])
    res = E.measures(orig, sm, src, jit)
    assert all(res["all"][j]["acc_sign_changes_per_s"]["ratio"] < 1.0 and res["all"][j]["range_p5_p95"]["ratio"] <= 1.0 for j in E.JN)


def test_codebook_size_rule():
    import t1a_eval as E
    assert E.pick_size({128: 1.04, 256: 1.0, 512: 0.9, 1024: 0.8}) == 128           # 128 within 5 % of 256
    assert E.pick_size({128: 1.30, 256: 1.04, 512: 1.0, 1024: 0.8}) == 256
    assert E.pick_size({128: 2.0, 256: 1.5, 512: 1.2, 1024: 1.0}) == 1024           # none qualifies: the largest


def test_training_resumes_from_checkpoint(tmp_path, monkeypatch):
    import json
    import t1a_train as TR
    r = np.random.default_rng(0)
    d = dict(g=r.normal(0, 3, (8, 2000, 5)).astype(np.float32), w=np.ones(8, np.float32), src=np.array([0, 1] * 4, np.int8))
    monkeypatch.setattr(TR.DD, "load", lambda s: d)
    monkeypatch.setattr(TR.DD, "scale", lambda: np.ones(5, np.float32))
    monkeypatch.setattr(TR, "OUT", tmp_path)
    monkeypatch.setattr(TR, "BATCH", 4)
    monkeypatch.setattr(TR, "EPOCH_CAP", 1)
    TR.cmd_train(16, 2)
    assert (tmp_path / "k16" / "ckpt.pt").exists() and (tmp_path / "k16" / "done.json").exists()
    (tmp_path / "k16" / "done.json").unlink()
    monkeypatch.setattr(TR, "EPOCH_CAP", 2)
    TR.cmd_train(16, 2)
    log = json.loads((tmp_path / "k16" / "log.json").read_text())
    assert [e["epoch"] for e in log] == [0, 1]
