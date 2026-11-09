"""WO23 report (BRAIN_SPEC 7.37.3): the same measures, applied identically to each setting, from its held-out (16 episodes) argmax rollout. Report only; no recommendation.

    acc_probe_report.py --out DIR --run B=/path/to/try1 --run A1=/path/to/A1 ...   [--no-caps]

Per run directory (holds result.json, rollouts/trained_argmax_4.npz, ckpt.pkl, optionally endstop.json):
  * realised joint speed / acceleration from the simulated q (100 Hz as saved, and every 2nd row = 50 Hz; central differences, np.gradient): p99 and max of |.| per joint as a share of the
    LIMITS of make_arm.py; flag = any joint above 1.0 x its limit;
  * share of control steps on each generator cap, per joint (s0_ceiling.shares, which needs the generator state): the held-out episodes are re-rolled from ckpt.pkl with cfg["diag"] and the run's own
    ACC_SHARE / SPEED_SHARE; the re-rolled q is compared with the saved rollout (max abs difference reported);
  * occupied cells (5 cm grid of the 50 Hz hand point, pooled over the 16 episodes, 6000 steps each = equal durations) and the entropy (bits) of the pooled cell distribution;
  * between-episode JS (median and mean of the 120 pairwise JS distances of per-episode cell distributions) and the half-episode JS control (first vs second half of each episode, median), and the ratio;
  * decoding: argmax ext and int (a) gap mean and CI (result.json);  hand metrics: e'1 (hand acc p99 mean), e'2 (share hand speed > 1 m/s), hand speed p99/max (50 Hz), floor breaches, end-stop events,
    contact share (result.json, endstop.json).
"""
import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np

import cpg
import make_arm as MA
import m3f_report as R

# the cell measures of s0_measure.py (same definitions; copied because that module imports sklearn, which the body env lacks)
CELL = 0.05


class S:
    CELL = CELL

    @staticmethod
    def hand(q):
        return R.fk_points(np.asarray(q, float))[:, 5]

    @staticmethod
    def cells(p, size):
        return np.floor(np.asarray(p) / size).astype(np.int64)

    @staticmethod
    def cell_dist(q, size=CELL):
        c = S.cells(S.hand(q), size)
        u, n = np.unique(c, axis=0, return_counts=True)
        return {tuple(k): v / len(c) for k, v in zip(u.tolist(), n)}

    @staticmethod
    def _js(a, b):
        m = 0.5 * (a + b)
        kl = lambda x, y: float((x[x > 0] * np.log2(x[x > 0] / y[x > 0])).sum())
        return float(np.sqrt(max(0.5 * kl(a, m) + 0.5 * kl(b, m), 0.0)))      # Jensen-Shannon distance, base 2

    @staticmethod
    def js_dist(p, q):
        keys = sorted(set(p) | set(q))
        return S._js(np.array([p.get(k, 0.0) for k in keys]), np.array([q.get(k, 0.0) for k in keys]))

    @staticmethod
    def js_between(D):
        ids = sorted(D)
        return np.array([S.js_dist(D[a], D[b]) for i, a in enumerate(ids) for b in ids[i + 1:]])

    @staticmethod
    def split_halves(q):
        n = len(q) // 2
        return q[:n], q[n:2 * n]


V = np.array([v for v, _ in MA.LIMITS])
A = np.array([a for _, a in MA.LIMITS])
JN = ("base_yaw", "shoulder", "elbow", "wrist_bend", "wrist_roll")


def realised(q100):
    """q100 (E, T, 5) deg -> {rate: {speed/acc: {limit, p99, max, p99_share, max_share}}} per joint, absolute values pooled over episodes."""
    out = {}
    for hz, st in ((100, 1), (50, 2)):
        q = q100[:, ::st]
        v = np.gradient(q, axis=1) * hz
        a = np.gradient(v, axis=1) * hz
        r = {}
        for name, x, lim in (("speed_deg_s", v, V), ("acc_deg_s2", a, A)):
            x = np.abs(x).reshape(-1, 5)
            p99, mx = np.percentile(x, 99, 0), x.max(0)
            r[name] = {"limit": lim.tolist(), "p99": p99.tolist(), "max": mx.tolist(), "p99_share": (p99 / lim).tolist(), "max_share": (mx / lim).tolist()}
        out[f"{hz}Hz"] = r
    return out


def cap_shares(run, args):
    """Re-roll the held-out episodes with the generator state recorded -> (shares per joint, max |q - saved q|)."""
    import jax
    import m3e_jax as M
    import m3f
    import run_m3f as RM
    import s0_ceiling as C
    a = argparse.Namespace(**args)
    cpg.ACC_SHARE, cpg.SPEED_SHARE = a.acc_share, a.speed_share
    toy = m3f.ToyF(a.toy)
    Cb = M.load_cb()
    cfg, tr = RM.build(a, toy, Cb, lambda s: None)
    tr.load(pickle.loads((Path(run) / "ckpt.pkl").read_bytes()))
    dcfg = {**cfg, "diag": True}
    fns = m3f.make_fns(Cb, dcfg, tr.opts)
    r = m3f.rollout(fns, dcfg, Cb, tr.P, toy, toy.sets["held"], "argmax", jax.random.PRNGKey(7), a.chunk_blocks, 4242)
    saved = np.load(Path(run) / "rollouts" / "trained_argmax_4.npz")["q"]
    diff = float(np.abs(r["q"] - saved).max())
    g = {k: r["dg_" + k].reshape(-1, 5) for k in ("centre", "amp", "freq")}
    return C.shares(g), diff


def cells_js(q100):
    hands = [S.hand(e[::2]) for e in q100]
    c = S.cells(np.concatenate(hands), S.CELL)
    u, n = np.unique(c, axis=0, return_counts=True)
    p = n / n.sum()
    D = {i: S.cell_dist(e[::2]) for i, e in enumerate(q100)}
    allp = S.js_between(D)
    halves = []
    for e in q100:
        a, b = S.split_halves(e[::2])
        halves.append(S.js_dist(S.cell_dist(a), S.cell_dist(b)))
    w = float(np.median(halves))
    return {"occupied_cells_pooled": int(len(u)), "occupied_cells_per_episode_mean": float(np.mean([len(d) for d in D.values()])), "cell_entropy_bits": float(-(p * np.log2(p)).sum()),
            "js_between_median": float(np.median(allp)), "js_between_mean": float(allp.mean()), "js_half_median": w, "js_ratio_median_over_half": float(np.median(allp) / w) if w > 0 else None}


def hand_speed(q100):
    sp = np.concatenate([np.linalg.norm(np.gradient(S.hand(e[::2]), axis=0) * 50.0, axis=1) for e in q100])
    return {"p99_m_s": float(np.percentile(sp, 99)), "max_m_s": float(sp.max())}


def one(name, run, caps):
    run = Path(run)
    res = json.loads((run / "result.json").read_text())
    r = res["result"]["argmax"]
    q = np.load(run / "rollouts" / "trained_argmax_4.npz")["q"]
    q = q.reshape(q.shape[0], -1, 5)
    args = res["args"]
    out = {"name": name, "run": str(run), "acc_share": args.get("acc_share", 0.25), "speed_share": args.get("speed_share", 0.8), "realised": realised(q), **cells_js(q), "hand_speed_50Hz": hand_speed(q),
           "decoding": {"ext_a": r["ext"]["a_gap_mean"], "ext_ci": r["ext"]["a_ci"], "int_a": r["int"]["a_gap_mean"], "int_ci": r["int"]["a_ci"]},
           "hand": {"e1_acc_p99_mean": r["eprime"]["acc_p99_mean"], "e2_fast_mean": r["eprime"]["fast_mean"], "contact_mean": r["eprime"]["contact_mean"],
                    "floor_breach_episodes": r["breaches"]["floor_m"]["episodes_with_breach"]}, "programs_used": r["programs_used"]}
    es = run / "endstop.json"
    if es.exists():
        e = json.loads(es.read_text())["trained"]["argmax"]
        out["end_stop"] = e.get("summary", {k: v for k, v in e.items() if k != "per_episode"})
    if caps:
        out["cap_share"], out["cap_reroll_max_abs_q_diff_deg"] = cap_shares(run, args)
    out["limit_exceeded"] = [f"{rate} {k} {JN[j]} max {d['max_share'][j]:.2f}x" for rate, rr in out["realised"].items() for k, d in rr.items() for j in range(5) if d["max_share"][j] > 1.0]
    return out


def table(rs):
    L = [f"{'':50s}" + "".join(f"{r['name']:>14s}" for r in rs)]

    def row(lab, f):
        L.append(f"{lab:50s}" + "".join(f"{f(r):>14s}" for r in rs))

    row("ACC_SHARE / SPEED_SHARE", lambda r: f"{r['acc_share']}/{r['speed_share']}")
    for rate in ("100Hz", "50Hz"):
        for k, lab in (("speed_deg_s", "speed"), ("acc_deg_s2", "acc")):
            for stat in ("p99_share", "max_share"):
                for j, jn in enumerate(JN):
                    row(f"realised {lab} {stat.split('_')[0]}/limit {jn} {rate}", lambda r, rate=rate, k=k, stat=stat, j=j: f"{r['realised'][rate][k][stat][j]:.3f}")
    row("any joint > 1.0 x its limit", lambda r: "YES" if r["limit_exceeded"] else "no")
    if "cap_share" in rs[0]:
        for key, lab in (("acc_cap", "acc"), ("speed_cap", "speed")):
            for jn in JN:
                row(f"steps on {lab} cap {jn}", lambda r, jn=jn, key=key: f"{r['cap_share'][jn][key]:.3f}")
        row("re-roll vs saved q, max abs deg", lambda r: f"{r['cap_reroll_max_abs_q_diff_deg']:.2g}")
    row("occupied cells, pooled (5 cm)", lambda r: str(r["occupied_cells_pooled"]))
    row("occupied cells per episode, mean", lambda r: f"{r['occupied_cells_per_episode_mean']:.0f}")
    row("cell entropy (bits)", lambda r: f"{r['cell_entropy_bits']:.3f}")
    row("JS between episodes, median", lambda r: f"{r['js_between_median']:.3f}")
    row("JS half-episode control, median", lambda r: f"{r['js_half_median']:.3f}")
    row("JS ratio", lambda r: f"{r['js_ratio_median_over_half']:.2f}")
    row("decoding ext (a)", lambda r: f"{r['decoding']['ext_a']:.3f}")
    row("decoding int (a)", lambda r: f"{r['decoding']['int_a']:.3f}")
    row("e'1 hand acc p99 (m/s^2)", lambda r: f"{r['hand']['e1_acc_p99_mean']:.2f}")
    row("e'2 share hand speed > 1 m/s", lambda r: f"{r['hand']['e2_fast_mean']:.4f}")
    row("hand speed p99 / max (m/s)", lambda r: f"{r['hand_speed_50Hz']['p99_m_s']:.2f}/{r['hand_speed_50Hz']['max_m_s']:.2f}")
    row("floor-breach episodes (of 16)", lambda r: str(r["hand"]["floor_breach_episodes"]))
    row("contact share", lambda r: f"{r['hand']['contact_mean']:.4f}")
    row("programs used", lambda r: str(r["programs_used"]))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--run", action="append", required=True, help="NAME=DIR")
    ap.add_argument("--no-caps", action="store_true")
    a = ap.parse_args()
    rs = []
    for s in a.run:
        n, d = s.split("=", 1)
        print("measuring", n, flush=True)
        rs.append(one(n, d, not a.no_caps))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(rs, indent=1))
    (out / "report.txt").write_text(table(rs) + "\n")
    print(table(rs))


if __name__ == "__main__":
    sys.exit(main())
