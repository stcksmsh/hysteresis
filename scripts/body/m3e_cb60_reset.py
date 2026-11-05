"""WO9 Part 1 diagnostic: the same held-out closed-loop run as m3e_cb60.py but with the cerebellum's GRU state reset to zero every 4 blocks (200 steps), the length it was trained
on. If the late rise of the prediction error in the continuous run is state drift, it should vanish here; if it is the content of the movement, it stays. Reports the
per-5 s bin squared error (mean over the 16 episodes) for continuous and reset side by side, plus the RMS joint speed per bin. The reset run's first 20 steps of every 200
carry the GRU warm-up (excluded from training), so compare the SHAPE over time, not the level."""
import json
import pickle
import sys
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import m3e
import m3e_cb60 as B
import m3e_jax as M

D = Path("/secondary/hyst-data/body/m3e")


def main():
    toy = m3e.ToyE("/secondary/hyst-data/body/m3d/toy.npz")
    C = M.load_cb()
    P = jax.tree_util.tree_map(jnp.asarray, pickle.loads((D / "try1/ckpt.pkl").read_bytes())["P"])
    fns = m3e.make_fns(C)
    out = {}
    for name, re in (("continuous", None), ("reset_every_200_steps", 4)):
        r = m3e.rollout(fns, C, P, toy, toy.sets["held"], "argmax", jax.random.PRNGKey(7), 8, 4242, reset_every=re)
        out[name] = {"sq_bins": B.bins(r["cb_sq"], 10).mean(0).tolist(), "nll_bins": B.bins(r["cb_nll"], 10).mean(0).tolist(),
                     "rms_speed_bins": np.sqrt(B.bins(r["ms"].mean(-1), 10).mean(0)).tolist()}
        print(name, {k: np.round(v, 4).tolist() for k, v in out[name].items()}, flush=True)
    (D / "cb60" / "reset_diagnostic.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    sys.exit(main())
