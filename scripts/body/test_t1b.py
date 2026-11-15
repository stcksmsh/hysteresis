"""WO41 tests: causality, carried state, counts. Run: /secondary/hyst-env/brain/bin/python -m pytest scripts/body/test_t1b.py -q"""
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t1b_model as M

torch.set_num_threads(2)


def avg50(x100):
    return x100.reshape(x100.shape[0], -1, 2, x100.shape[-1]).mean(2)


def test_listener_causal():
    torch.manual_seed(0)
    L = M.Listener().eval()
    x = torch.randn(1, 600, M.WIDTH)                      # 100 Hz frames
    y = x.clone()
    j = 100
    y[:, 2 * j + 2:] = torch.randn_like(y[:, 2 * j + 2:])  # change everything after frame 2j+1
    a, _ = L(avg50(x)); b, _ = L(avg50(y))
    assert torch.equal(a[:, :j + 1], b[:, :j + 1]) and not torch.equal(a[:, j + 1:], b[:, j + 1:])


def test_carried_state_equals_one_pass():
    torch.manual_seed(1)
    L = M.Listener().eval()
    x = torch.randn(2, 300, M.WIDTH)
    full, _ = L(x)
    a, h = L(x[:, :120]); b, _ = L(x[:, 120:], h)
    assert torch.allclose(full, torch.cat([a, b], 1), atol=1e-6)


def tok(B, N, n_post=(256,)):
    g = torch.Generator().manual_seed(2)
    return dict(c1=torch.randint(0, 1024, (B, N), generator=g), c2=torch.randint(0, 1024, (B, N), generator=g), v=torch.randint(0, 32, (B, N), generator=g),
                p=torch.stack([torch.randint(0, n, (B, N), generator=g) for n in n_post], -1))


def test_planner_causal_in_listener_rows():
    """token k's loss does not change when listener states after its decision step change"""
    torch.manual_seed(3)
    m = M.Model().eval()
    N = 40
    lis = torch.randn(1, N, 256)
    t = tok(1, N)
    ce1, _, _ = M.run_window(m, lis, t, m.planner.zero_state(1), None)
    k = 20
    lis2 = lis.clone(); lis2[:, k + 1:] = torch.randn_like(lis2[:, k + 1:])
    ce2, _, _ = M.run_window(m, lis2, t, m.planner.zero_state(1), None)
    for h in ce1:
        assert torch.equal(ce1[h][:, :k + 1], ce2[h][:, :k + 1])


def test_step_of_token():
    assert [M.step_of_token(k) for k in (0, 1, 2, 120)] == [-13, 12, 37, 2987]
    for k in range(2, 50):
        assert (2 * M.step_of_token(k) + 1) / 100 == 0.5 * k - 0.25


def test_planner_window_carry_equals_one_pass():
    torch.manual_seed(4)
    m = M.Model().eval()
    N = 50
    lis = torch.randn(2, N, 256); t = tok(2, N)
    full, _, _ = M.run_window(m, lis, t, m.planner.zero_state(2), None)
    cut = lambda d, a, b: {k: v[:, a:b] for k, v in d.items()}
    c1, s, pv = M.run_window(m, lis[:, :30], cut(t, 0, 30), m.planner.zero_state(2), None)
    c2, _, _ = M.run_window(m, lis[:, 30:], cut(t, 30, N), s, pv)
    for h in full:
        assert torch.allclose(full[h], torch.cat([c1[h], c2[h]], 1), atol=1e-5)


def test_two_stage_posture_runs():
    m = M.Model(n_post=(256, 256)).eval()
    ce, _, _ = M.run_window(m, torch.randn(1, 5, 256), tok(1, 5, (256, 256)), m.planner.zero_state(1), None)
    assert ce["post"].shape == (1, 5)


def test_counts():
    c = M.Model().counts()
    print(c)
    assert c["total"] < 2_000_000 and c["listener_projection"] == 2105 * 128 + 128


def test_tiny_overfit():
    torch.manual_seed(5)
    m = M.Model()
    x = torch.randn(1, 600, M.WIDTH)
    N = 12
    t = tok(1, N)
    opt = torch.optim.Adam(m.parameters(), 3e-3)
    first = None
    for i in range(40):
        s, _ = m.listener(x)
        lis = s[:, 24::50][:, :N]                       # any causal-looking read; this test only checks the loss falls
        ce, _, _ = M.run_window(m, lis, t, m.planner.zero_state(1), None)
        loss = sum(v.mean() for v in ce.values())
        first = first or float(loss)
        opt.zero_grad(); loss.backward(); opt.step()
    assert float(loss) < 0.5 * first
