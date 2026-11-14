"""M3e: export the frozen K1 round-2 cerebellum (m1_r2.pt) for the JAX port (m3e_jax.py), plus a parity reference. Runs in /secondary/hyst-env/brain (torch).

    export_cb.py OUT_DIR

Writes OUT_DIR/cb_r2.npz (weights, standardisers) and OUT_DIR/cb_parity.npz (2 real 12 s trajectories of held2h.npz; torch outputs run CONTINUOUSLY over the 1200
steps from a zero state, and the same net run in 200-step chunks restarted from zero, as it was trained) and prints how far the continuous run drifts from the
chunked one (the in-loop cerebellum runs continuously).
"""
import sys
from pathlib import Path

import numpy as np
import torch

import cerebellum as cb

BUNDLE = "/secondary/hyst-data/body/runs/m1-r2/m1_r2.pt"
HELD = "/secondary/hyst-data/body/held2h.npz"


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    net, st, _, _ = cb.load_bundle(BUNDLE)
    sd = {k: v.numpy() for k, v in net.state_dict().items()}
    np.savez(out / "cb_r2.npz", **{k.replace(".", "_"): v for k, v in sd.items()}, omu=st.omu, osd=st.osd, tmu=st.tmu, tsd=st.tsd, dsd=st.dsd)
    d = np.load(HELD)
    obs, tgt = d["obs"][[3, 77], :1200], d["tgt"][[3, 77], :1200]
    X = cb.features(obs, tgt, st)
    with torch.no_grad():
        m_c, lv_c = net(torch.from_numpy(X))                                              # continuous, zero initial state
        parts = [net(torch.from_numpy(X[:, s:s + 200])) for s in range(0, 1200, 200)]       # chunks restarted from zero
        m_k = torch.cat([p[0] for p in parts], 1)
    Y, valid = cb.labels(obs, st)
    keep = valid.copy()
    keep[:, :20] = False
    err = lambda m, i: float(((m.numpy()[:, :, i] - Y[:, :, i]) ** 2).mean(-1)[keep].mean())
    print("MSE vs label (standardised), continuous | chunked-restart, per horizon:", [(round(err(m_c, i), 4), round(err(m_k, i), 4)) for i in range(3)])
    np.savez(out / "cb_parity.npz", obs=obs, tgt=tgt, mean_cont=m_c.numpy(), logvar_cont=lv_c.numpy(), mean_chunk=m_k.numpy())


if __name__ == "__main__":
    main(sys.argv[1])
