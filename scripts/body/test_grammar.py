"""WO45 tests (docs/A_RULES.md section 5). Run: /secondary/hyst-env/brain/bin/python -m pytest scripts/body/test_grammar.py -q"""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import controls_lib as C
import grammar_data as GD
import grammar_model as GM
import grammar_train as GT


def fake_final(n=6, sharp=None, acc_mean=None):
    slots = np.tile(np.arange(1, 9, dtype=float), (n, 1))
    return dict(vigour=np.linspace(-1, 1, n), height=np.full(n, 0.5), accent_slots=slots, accent_mean=slots.mean(1) if acc_mean is None else acc_mean,
                sharp=np.full(n, 0.3) if sharp is None else sharp, dir=np.tile([0.0, 0.6, 0.8], (n, 1)), dir_ok=np.ones(n, np.int8), pause_prob=np.full(n, 0.1))


def test_ctl_v2_rules():
    c = fake_final(acc_mean=np.array([4.5, 4.5, 0.0, 4.5, 4.5, 4.5]), sharp=np.array([0.3, np.nan, 0.3, 0.3, 0.3, 0.3]))
    v = C.ctl_v2(c)
    assert v.shape == (6, C.CTL_DIM) and np.isfinite(v).all()
    assert np.allclose(v[0, 2:10].mean(), 1.0)                       # pattern mean is 1
    assert np.allclose(v[2, 2:10], 1.0) and v[2, 17] == 0 and v[0, 17] == 1   # near-zero token mean: flat pattern, flag 0
    assert v[1, 10] == 0 and v[1, 15] == 0 and v[0, 15] == 1          # undefined sharpness: 0 and flag 0
    assert np.allclose(v[0, 11:14], [0, 0.6, 0.8]) and v[0, 16] == 1
    assert C.CTL_NAMES[10] == "sharp" and C.CTL_NAMES[14] == "pause" and len(C.CTL_NAMES) == C.CTL_DIM == 18


def test_finalise_version_flag_keeps_v1():
    assert C.VERSION == 1
    N = C.NTOK * C.TOK + 1
    t = np.arange(N) / C.FS
    lamp = np.stack([0.2 * t, np.zeros(N), 0.3 + np.zeros(N)], 1)
    norm = dict(vj=dict(median=0.0, mad=1.0), vl=dict(median=0.0, mad=1.0), vigour=dict(loadings=[0.7, 0.7], sd=1.0), accent=dict(A=1.0, J=1.0))
    r = C.raw_window(np.zeros((N, 5)), lamp)
    assert "ctl" not in C.finalise(r, norm)
    c2 = C.finalise(r, norm, version=2)
    assert c2["ctl"].shape == (C.NTOK, C.CTL_DIM) and np.allclose(c2["ctl"][:, 11:14], [1, 0, 0], atol=1e-6)


def test_causality_of_control_window():
    torch.manual_seed(0)
    m = GM.Grammar(n_genre=3)
    m.eval()
    ctl = torch.randn(2, GM.N_TOKENS, GM.CD)
    pres = torch.ones(2, GM.N_TOKENS)
    base = m.ctl_feat(ctl, pres)
    for j in (7, 20, 39):
        c2 = ctl.clone()
        c2[:, j] += 5.0
        d = (m.ctl_feat(c2, pres) - base).abs().amax((0, 2))
        assert (d[: max(0, j - GM.H + 1)] == 0).all(), j                   # tokens whose window ends before j do not change
        assert (d[j + 1:] == 0).all()                                      # nothing after j changes (no look back either: the conv at k reads k .. k + H - 1)
        assert d[j] > 0
    # full step output at token k: perturb a control beyond the horizon -> identical logits at k
    style = m.style_vec(torch.zeros(2, dtype=torch.long), torch.zeros(2, dtype=torch.long), torch.zeros(2, dtype=torch.long))
    outs = []
    for bump in (0.0, 9.0):
        c2 = ctl.clone()
        c2[:, 12:] += bump
        f = m.ctl_feat(c2, pres)
        st, prev, fs = m.zero_state(style), None, []
        for k in range(8):                                                 # k + H - 1 = 10 < 12
            h, st = m.step(st, f[:, k], style, prev)
            fs.append(h)
            prev = tuple(torch.zeros(2, dtype=torch.long) for _ in range(5))
        outs.append(torch.stack(fs))
    assert torch.equal(outs[0], outs[1])


def test_dropout_and_corruption_rates():
    g = torch.Generator().manual_seed(1)
    ctl = torch.zeros(200, 40, GM.CD)
    pool = torch.arange(1, 501, dtype=torch.float32)[:, None].repeat(1, GM.CD)       # every pool row constant k: a corrupted token is a whole row
    out, pres = GM.corrupt_controls(ctl, pool, GT.P_DROP, GT.P_CORR, g)
    assert abs((1 - pres.mean().item()) - GT.P_DROP) < 0.01
    corrupted = (out[..., 0] != 0)
    assert abs(corrupted.float().mean().item() - GT.P_CORR) < 0.01
    assert (out[corrupted] == out[corrupted][:, :1]).all()                          # whole vectors from the pool, never mixed per control
    assert abs(corrupted.float().mean().item() - GT.P_CORR) < 0.01 and GT.P_DROP == 0.15


def test_code_stats_round_trip():
    rng = np.random.default_rng(0)
    n, K = 300, 4
    codes = rng.integers(0, K, (n, 40))
    ctl = np.zeros((n, 40, GD.CD), np.float32)
    ctl[..., 0] = codes * 1.0 + 0.01 * rng.standard_normal((n, 40))                 # vigour = code (+ small noise)
    ctl[..., 1] = 0.5
    ctl[..., 2:10] = 1.0
    ctl[..., 14] = 0.2
    ctl[..., 15:] = 1.0
    ctl[..., 10] = 0.4
    ctl[..., 12] = 1.0
    ctl[(codes == 2), 15] = 0                                                        # sharp undefined for every token of code 2
    tr = dict(ctl=ctl, code1=codes, code2=codes, p1=codes, p2=codes)
    s = GD.compute_stats(tr, ks=K)
    for k in range(K):
        assert abs(s["c1_mean"][k, 0] - k) < 0.02
        assert s["c1_n"][k] == (codes == k).sum()
        assert s["c1_cov"][k, 0, 0] < 1e-3
    assert abs(s["c1_mean"][0, 10] - 0.4) < 1e-6 and abs(s["global_mean"][10] - 0.4) < 1e-6   # undefined entries never enter a mean


def tiny_data(n=8, seed=0):
    rng = np.random.default_rng(seed)
    ctl = rng.standard_normal((n, 40, GM.CD)).astype(np.float32)
    ctl[..., 15:] = 1.0
    c1 = rng.integers(0, 6, (n, 40))
    d = SimpleNamespace(n=n, c1=torch.from_numpy(c1), c2=torch.from_numpy(rng.integers(0, 6, (n, 40))), v=torch.from_numpy(rng.integers(0, 4, (n, 40))), p1=torch.from_numpy(rng.integers(0, 6, (n, 40))),
                        p2=torch.from_numpy(rng.integers(0, 6, (n, 40))), cn=torch.from_numpy(ctl), ds=torch.zeros(n, dtype=torch.long), copy=torch.zeros(n, dtype=torch.long),
                        genre=torch.zeros(n, dtype=torch.long), w=torch.ones(n))
    d.valid = torch.from_numpy(np.concatenate([np.ones((n, 40, 15), bool), np.zeros((n, 40, 3), bool)], -1))
    return d


def test_tiny_overfit():
    torch.manual_seed(0)
    d = tiny_data()
    m = GM.Grammar(n_genre=2)
    means = {k: torch.zeros(GM.K_CODE if k[0] == "c" else GM.N_POST, GM.CD) for k in ("c1", "c2", "p1", "p2")}
    opt = torch.optim.Adam(m.parameters(), lr=3e-3)
    idx = torch.arange(d.n)
    g = torch.Generator().manual_seed(0)
    old = (GT.P_DROP, GT.P_CORR, GT.P_NOISE)
    GT.P_DROP = GT.P_CORR = GT.P_NOISE = 0.0
    try:
        first = last = None
        for i in range(60):
            o, _ = GT.run_batch(m, d, idx, means, d.cn.reshape(-1, GM.CD), g)
            loss = GT.total(o) + GT.LAMBDA * o["aux"]
            opt.zero_grad()
            loss.backward()
            opt.step()
            first = float(GT.total(o)) if first is None else first
            last = float(GT.total(o))
        assert last < 0.5 * first, (first, last)
    finally:
        GT.P_DROP, GT.P_CORR, GT.P_NOISE = old


def test_aux_loss_zero_when_expected_equals_request_and_respects_masks():
    req = torch.randn(3, GM.CD)
    e = [req.clone() for _ in range(4)]
    valid = torch.ones(3, GM.CD, dtype=torch.bool)
    assert float(GM.aux_loss(e, req, valid, torch.ones(GM.CD), torch.ones(3)).abs().max()) < 1e-9
    e2 = [x + 1.0 for x in e]
    full = GM.aux_loss(e2, req, valid, torch.ones(GM.CD), torch.ones(3))
    assert torch.allclose(full, torch.ones(3))
    pres = torch.tensor([1.0, 0.0, 1.0])
    assert GM.aux_loss(e2, req, valid, torch.ones(GM.CD), pres)[1] == 0                # dropped vector: no auxiliary term
    valid2 = valid.clone()
    valid2[:, 5:] = False
    assert torch.allclose(GM.aux_loss(e2, req, valid2, torch.ones(GM.CD), torch.ones(3)), torch.ones(3))   # masked dims do not dilute


def test_parameter_counts_printable():
    c = GM.Grammar(n_genre=8).counts()
    assert c["total"] == sum(v for k, v in c.items() if k != "total")


def test_generate_batch_sizes():
    import grammar_checks as GC
    torch.manual_seed(0)
    d = tiny_data(n=5)
    m = GM.Grammar(n_genre=2)
    m.eval()
    fake = SimpleNamespace(model=m, te=d, idx=np.arange(5))
    for idx in (np.arange(5), np.array([2]), np.array([1, 3])):
        t = GC.Setup.generate(fake, d.cn[idx], 1, idx=idx)
        assert t["c1"].shape == (len(idx), 40)
    try:
        GC.Setup.generate(fake, d.cn, 1, idx=np.array([2]))
    except AssertionError:
        return
    raise AssertionError("mismatched batch accepted")
