"""M3 tests. Identity: with the proprioceptive relay at zero, the cortex outputs equal B7 epoch 6 (BRAIN_SPEC §7.13 / work order 2 phase 3: float64 max
difference <= 1e-9; float32 is logged). Needs /secondary/hyst-data/brain/b7/ckpt/phase/epoch_006.pt.
    cd scripts/body && /secondary/hyst-env/brain/bin/python -m unittest -v test_m3
"""
import copy
import unittest

import torch

import m3_cortex as M

torch.set_num_threads(4)


def run(model, f, prop=None, wrapped=None):
    with torch.no_grad():
        if wrapped is None:
            return model(f, model.init_state(f.shape[0]))[0]
        return wrapped(f, prop, model.init_state(f.shape[0]))[0]


def maxdiff(a, b):
    return max(float((x[k] - y[k]).abs().max()) for x, y in zip(a, b) for k in ("mean", "logvar", "x", "err"))


class Identity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b7 = M.load_epoch()
        g = torch.Generator().manual_seed(1)
        cls.f = torch.randn(2, 400, 46, generator=g)
        cls.prop = torch.randn(2, 400, M.P, generator=g)

    def check(self, dtype):
        model = copy.deepcopy(self.b7)
        wrapped = M.Cortex(model)
        if dtype == torch.float64:
            wrapped.double()
        f, prop = self.f.to(dtype), self.prop.to(dtype)
        ref = run(wrapped.core, f)                       # hooks are inert while no prop is given
        got = run(wrapped.core, f, prop, wrapped)        # zero relays, non-zero proprioception
        return maxdiff(ref, got), wrapped, f, prop

    def test_zero_relay_equals_b7_epoch6_float64(self):
        d, *_ = self.check(torch.float64)
        print("identity float64 max diff", d)
        self.assertLessEqual(d, 1e-9)

    def test_zero_relay_float32_logged(self):
        d, *_ = self.check(torch.float32)
        print("identity float32 max diff", d)
        self.assertLessEqual(d, 1e-4)

    def test_relay_gets_gradient_and_changes_output_when_nonzero(self):
        _, w, f, prop = self.check(torch.float32)
        w.freeze_cortex()
        out = w(f, prop, w.core.init_state(2))[0]
        M.row_surprisal(out, f, "row").sum().backward()
        # layer 4 (+8 s horizon) has no valid target window in 400 frames, so its relay gets exactly zero here; the other three must not
        self.assertTrue(all(p.grad is not None and p.grad.abs().sum() > 0 for p in list(w.prop.parameters())[:3]))
        self.assertTrue(all(p.grad is None for p in w.core.parameters()))
        with torch.no_grad():
            for p in w.prop:
                p.weight.add_(0.01)
        moved = run(w.core, f, prop, w)
        self.assertGreater(maxdiff(run(w.core, f), moved), 1e-6)


if __name__ == "__main__":
    unittest.main()
