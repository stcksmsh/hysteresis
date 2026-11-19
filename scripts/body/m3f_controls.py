"""M3f controls, report only (WO7 set, as m3e_controls.py): the selected try scored again with (i) the untrained policy (this try's initial weights, kappa as initialised) and (ii) the
trained policy with kappa forced to 0, same cfg, same WO7 observer procedure on the held-out episodes. Paired (a)_trained - (a)_control per episode, 95 % bootstrap over the episodes
(10,000 resamples), external and internal, argmax and sampled; (e) of each policy alongside. Provisional servo model (Feetech STS3215 12 V assumed).

    m3f_controls.py --try DIR [--toy toy.npz]      DIR holds ckpt.pkl and result.json of the scored try; writes DIR/controls/{policy}.json and summary.json (resume-safe).
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import m3d_controls as K
import m3e_jax as M
import m3f
import m3f_jax as F

MODES = ("argmax", "sample")


def initial_policy(cfg, seed=0):
    """The policy m3f.Trainer(seed) starts from."""
    return F.init_policy(jax.random.split(jax.random.PRNGKey(seed), 7)[1], cfg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--try", dest="tdir", required=True)
    ap.add_argument("--toy", default="/secondary/hyst-data/body/m3d/toy.npz")
    a = ap.parse_args()
    tdir = Path(a.tdir)
    out = tdir / "controls"
    (out / "rollouts").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:7.0f}s] {s}", flush=True)
    toy = m3f.ToyF(a.toy)
    C = M.load_cb()
    info = json.loads((tdir / "result.json").read_text())
    cfg = info["cfg"]
    ck = pickle.loads((tdir / "ckpt.pkl").read_bytes())
    stats = ck["stats"]
    trained = jax.tree_util.tree_map(jnp.asarray, ck["P"])
    fns = m3f.make_fns(C, cfg, {"internal": True, "pen": False, "jerk": False, "sw": False})
    pols = {"trained": trained, "i_untrained": initial_policy(cfg, info["args"]["seed"]), "ii_trained_kappa0": K.with_kappa(trained, np.zeros(5))}
    for name, P in pols.items():
        f = out / f"{name}.json"
        if f.exists():
            continue
        log(f"policy {name}")
        res, _ = m3f.score_policy(fns, cfg, C, P, toy, stats, "held", 8, rolldir=str(out / "rollouts"), name=name, log=log)
        f.write_text(json.dumps(res, indent=1))
    res = {n: json.loads((out / f"{n}.json").read_text()) for n in pols}
    summary = {"table": {}, "paired": {}}
    for n, r in res.items():
        summary["table"][n] = {m: {"ext_a": r[m]["ext"]["a_gap_mean"], "ext_ci": r[m]["ext"]["a_ci"], "int_a": r[m]["int"]["a_gap_mean"], "int_ci": r[m]["int"]["a_ci"], "e": r[m]["e"]["mean"],
                                   **{k: r[m][k] for k in ("b_rms_nonroll", "c_mi", "c_null_mean", "c_p", "programs_used", "kappa_mean")}} for m in MODES}
    for n in list(pols)[1:]:
        summary["paired"][n] = {m: {d: K.paired_difference(res["trained"][m][d]["a_gaps"], res[n][m][d]["a_gaps"]) for d in ("ext", "int")} for m in MODES}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    log("done")


if __name__ == "__main__":
    sys.exit(main())
