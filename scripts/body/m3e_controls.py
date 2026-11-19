"""M3e controls, report only (WO7 set; docs/NIGHT_LOG_body-m3e.md item 7). Provisional servo model (Feetech STS3215 12 V assumed).

    m3e_controls.py --try DIR [--toy toy.npz]     DIR holds ckpt.pkl of a scored try; writes DIR/controls/{policy}.json and summary.json (resume-safe).

Policies, each scored with the WO7 observer procedure (external and internal separately, both modes) on the 16 held-out episodes:
  trained | (i) untrained (this try's initial weights, kappa as initialised) | (ii) trained, kappa forced to 0 | (iii) untrained, kappa fixed at the trained per-joint means.
Paired (a)_trained - (a)_control per episode with a 95 % bootstrap over the 16 episodes (10,000 resamples), external and internal.
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
import m3e
import m3e_jax as M

MODES = ("argmax", "sample")


def initial_policy(seed=0):
    """The policy m3e.Trainer(seed) starts from."""
    return M.init_policy(jax.random.split(jax.random.PRNGKey(seed), 7)[1])


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
    toy = m3e.ToyE(a.toy)
    C = M.load_cb()
    ck = pickle.loads((tdir / "ckpt.pkl").read_bytes())
    stats = ck["stats"]
    trained = jax.tree_util.tree_map(jnp.asarray, ck["P"])
    kap = json.loads((tdir / "result.json").read_text())["result"]["argmax"]["kappa_mean"]
    log(f"trained per-joint kappa means (result.json, held-out argmax): {kap}")
    fns = m3e.make_fns(C)
    pols = {"trained": trained, "i_untrained": initial_policy(), "ii_trained_kappa0": K.with_kappa(trained, np.zeros(5)),
            "iii_untrained_kappa_trained_means": K.with_kappa(initial_policy(), kap)}
    for name, P in pols.items():
        f = out / f"{name}.json"
        if f.exists():
            continue
        log(f"policy {name}")
        res, _ = m3e.score_policy(fns, C, P, toy, stats, "held", 8, rolldir=str(out / "rollouts"), name=name, log=log)
        f.write_text(json.dumps(res, indent=1))
    res = {n: json.loads((out / f"{n}.json").read_text()) for n in pols}
    summary = {"kappa_trained_means": kap, "table": {}, "paired": {}}
    for n, r in res.items():
        summary["table"][n] = {m: {"ext_a": r[m]["ext"]["a_gap_mean"], "ext_ci": r[m]["ext"]["a_ci"], "int_a": r[m]["int"]["a_gap_mean"], "int_ci": r[m]["int"]["a_ci"],
                                   **{k: r[m][k] for k in ("b_rms_nonroll", "c_mi", "c_null_mean", "c_p", "programs_used", "kappa_mean")}} for m in MODES}
    for n in list(pols)[1:]:
        summary["paired"][n] = {m: {d: K.paired_difference(res["trained"][m][d]["a_gaps"], res[n][m][d]["a_gaps"]) for d in ("ext", "int")} for m in MODES}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    log("done")


if __name__ == "__main__":
    sys.exit(main())
