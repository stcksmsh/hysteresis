"""M3 listening side: B7 epoch 6 (frozen) plus new zero-initialised proprioceptive relays (docs/BODY_BRAIN_PLAN.md §6).

`Cortex(core7)` adds, per layer, Linear(P -> 128, no bias), P = 30 = standardised proprioception (position, velocity, load: 15) + the cerebellum's
prediction error (15), zero-initialised, joined to the layer input exactly where B7's own relay joins it (a forward hook on `core7.relay[i]`), so
at step 0 the outputs equal B7 epoch 6 exactly. Only these relays are meant to train (`freeze_cortex`). B7's own weights are never touched.

The twin pass (`surprisal_twin`): rows 0..E-1 get the arm's real proprioception, rows E..2E-1 the same music with the arm at rest in its neutral
pose (S_moving, S_still). Surprisal per frame and row = plain Gaussian NLL of the four heads, summed over layers (mean over the 44 features),
where the target window is valid (the first 2 * horizon frames of a song have none).
Provisional servo model (Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5, acceleration share 0.25).
"""
import math
import sys
from pathlib import Path

import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "brain"))
import core  # noqa: E402
import core_b7  # noqa: E402

P = 30
EPOCH6 = "/secondary/hyst-data/brain/b7/ckpt/phase/epoch_006.pt"


def load_epoch(path=EPOCH6):
    ck = torch.load(path, weights_only=False, map_location="cpu")
    taps = ck["model"]["skip.0.weight"].shape[1] // core.FEAT
    model = core_b7.Core7(phase=ck["meta"]["phase"], head_norm=ck["meta"].get("head_norm", True), skip_taps=taps)
    model.load_state_dict(ck["model"])
    return model.eval()


class Cortex(nn.Module):
    def __init__(self, model):
        super().__init__()
        self.core = model
        self.prop = nn.ModuleList(nn.Linear(P, core.D, bias=False) for _ in model.relay)
        for m in self.prop:
            nn.init.zeros_(m.weight)
        self._x, self._cur = None, [0] * len(model.relay)
        for i, r in enumerate(model.relay):
            r.register_forward_hook(self._hook(i))

    def _hook(self, i):
        def hook(_m, _inp, out):
            if self._x is None:
                return out
            k, tb = self._cur[i], out.shape[1]
            self._cur[i] = k + tb
            return out + self.prop[i](self._x[:, k:k + tb])
        return hook

    def freeze_cortex(self):
        for p in self.core.parameters():
            p.requires_grad_(False)

    def forward(self, f, prop, state):
        """f (B, T, 46) standardised features; prop (B, T, P) or None; state from core.init_state. -> out, state (core_b7.Core7.forward)."""
        self._x, self._cur = prop, [0] * len(self.prop)
        try:
            return self.core(f, state)
        finally:
            self._x = None


def row_surprisal(out, f, per="frame"):
    """Plain NLL per row, summed over the four layers, mean over features. f (B, T, >=44) the features that were fed (targets are windows of them).
    per='frame' -> (B, T) with zeros where a layer has no valid target window; per='row' -> (B,) mean over frames."""
    B, T = f.shape[:2]
    cs = torch.cat([torch.zeros(B, 1, core.FEAT, dtype=f.dtype), f[..., :core.FEAT].cumsum(1)], 1)
    t = torch.arange(T)
    s = torch.zeros(B, T, dtype=f.dtype)
    for o, hz in zip(out, core.HORIZONS):
        end = (t + 2 * hz).clamp(max=T)
        y = (cs[:, end] - cs[:, (t + hz).clamp(max=T)]) / hz
        valid = (t + 2 * hz <= T).to(f.dtype)
        lv = o["logvar"]
        e = 0.5 * (lv + (y - o["mean"]) ** 2 * torch.exp(-lv) + math.log(2 * math.pi))
        s = s + e.mean(-1) * valid
    return s if per == "frame" else s.mean(1)
