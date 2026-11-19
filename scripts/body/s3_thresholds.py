"""Stage 3 energy and jerk hinge thresholds (work order 26A; docs/STAGE3_RULES_DATA_EVAL.md section 3; BRAIN_SPEC 7.40.2). Body env (JAX CPU, MuJoCo). Imports k5p2_train / m3f_jax; edits none.

    s3_thresholds.py [--csv-dir /secondary/hyst-data/body/v47] [--songs ic,fy,pr] [--out /secondary/hyst-data/body/s3/thresholds.json] [--max-blocks N]
The v47 arm-0 joint trajectories (100 Hz) are replayed as servo targets on the v2f body with the pass2 configuration, in 0.5 s blocks; per block the same `energy` (p.sum() * DT) and `jerk`
(m3f_jax.penalties, mean squared third difference over the last 53 realised samples) the policy's block function outputs. energy threshold = pooled mean block energy; jerk threshold = 1.25 x pooled mean block jerk.
"""
import argparse
import json
import sys
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import k5p2_train as P2  # noqa: E402
import m3d_jax as J  # noqa: E402
import m3e_jax as M  # noqa: E402
import m3f_jax as F  # noqa: E402

BLOCK = 50
BUF = 200


def load_csv(path):
    """-> (n, 5) degrees of a 100 Hz `hyst score-csv` joint CSV."""
    rows = [l for l in Path(path).read_text().splitlines() if l and l[0] != "#" and not l.startswith("time_s")]
    return np.array([[float(v) for v in r.split(",")][1:] for r in rows])


def make_block(cfg):
    """One 0.5 s block of the replay: carry (d, tgt, tv, buf (200, 5)), the block's 50 targets (deg) -> (carry, energy, jerk)."""
    plane = cfg.get("plane")

    def block(c, tg):
        def step(cc, t):
            d, tgt, tv = cc
            d, tgt, tv, p = F.arm_step(cfg, d, tgt, tv, t)
            return (d, tgt, tv), (jnp.degrees(d.qpos), p)
        (d, tgt, tv), (q, p) = jax.lax.scan(step, (c["d"], c["tgt"], c["tv"]), tg)
        full = jnp.concatenate([c["buf"], q])
        pen = F.penalties(full, plane)
        return {"d": d, "tgt": tgt, "tv": tv, "buf": full[-BUF:]}, p.sum() * J.DT, pen["jerk"]
    return jax.jit(block)


def replay(tg_deg, cfg, block, max_blocks=None):
    """tg_deg (n, 5) -> per-block (energy, jerk) arrays; the first block has no 53-sample history and is dropped from the means by the caller."""
    d, tgt, tv = F.arm_init(cfg, tg_deg[0])
    c = {"d": d, "tgt": tgt, "tv": tv, "buf": jnp.repeat(jnp.asarray(tg_deg[:1], jnp.float32), BUF, 0)}
    nb = len(tg_deg) // BLOCK
    nb = min(nb, max_blocks) if max_blocks else nb
    en, je = [], []
    for b in range(nb):
        c, e, j = block(c, jnp.asarray(tg_deg[b * BLOCK:(b + 1) * BLOCK], jnp.float32))
        en.append(float(e))
        je.append(float(j))
    return np.array(en), np.array(je)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv-dir", default="/secondary/hyst-data/body/v47")
    ap.add_argument("--songs", default="ic,fy,pr")
    ap.add_argument("--out", default="/secondary/hyst-data/body/s3/thresholds.json")
    ap.add_argument("--max-blocks", type=int, help="test only")
    a = ap.parse_args()
    cfg = P2.CFG
    block = make_block(cfg)
    per, E, Jk = {}, [], []
    for s in a.songs.split(","):
        tg = load_csv(Path(a.csv_dir) / f"{s}-0.csv")
        en, je = replay(tg, cfg, block, a.max_blocks)
        per[s] = {"blocks": int(len(en) - 1), "energy_mean": float(en[1:].mean()), "jerk_mean": float(je[1:].mean()), "energy_p99": float(np.percentile(en[1:], 99)), "jerk_p99": float(np.percentile(je[1:], 99))}
        E.append(en[1:])
        Jk.append(je[1:])
        print(s, per[s], flush=True)
    E, Jk = np.concatenate(E), np.concatenate(Jk)
    res = {"energy": float(E.mean()), "jerk": float(1.25 * Jk.mean()), "method": "v47-v2f", "v47_mean_energy": float(E.mean()), "v47_mean_jerk": float(Jk.mean()), "jerk_factor": 1.25,
           "n_blocks": int(len(E)), "per_song": per, "reference": f"{a.csv_dir}/<song>-0.csv (arm 0, 100 Hz)", "cfg": {k: (v if isinstance(v, (int, float, str, bool)) else str(v)) for k, v in cfg.items()},
           "units": "m3f_jax per-block outputs: energy = p.sum() * DT, jerk = mean squared third difference (deg^2/s^6)"}
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("energy", "jerk", "method", "n_blocks")}))


if __name__ == "__main__":
    main()
