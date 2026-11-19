"""WO39 follow-up (report only): jitter at the REALISED stage (guard, spinal H1, limiter, servo, v2p; the gate's own simulation, q50 at 50 Hz) of the test windows: original vs Run A vs Run B rebuilds.
Per joint and source: median over windows of acceleration sign changes per second and power above 3 Hz; gate share by source. Appends a section to docs/T1A2_REPORT.md. Brain env.
    python -u t1a2_realised.py [PROCS]"""
import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t1a_data as DD  # noqa: E402
import t1a_eval as E  # noqa: E402
import t1a2_train as TR2  # noqa: E402

JN, OUT = E.JN, TR2.OUT


def sim_one(args):
    """as t1a_eval.gate_one, but also returns the realised rows q50 (50 Hz) -> (passed, q50 float32)"""
    rows, pre, var = args
    import make_arm_v2p as P
    import motornet as M
    import retarget as RT
    import retarget_limiter as FX
    import retarget_run as RR
    RR.patch_gates()
    K = RT.to_commands(np.zeros((1, 5)), var)[0]
    sh = np.zeros(5)
    sh[[0, 4]] = (rows[0] - K)[[0, 4]]
    pre = np.repeat(rows[:1], E.PRE, 0) if pre is None else pre
    G, gs = P.guard(np.concatenate([pre, rows]) - sh)
    q50, contacts = FX.simulate_goals(M.spinal(G))
    g = RR.gates_v2p(q50, contacts, gs)
    return bool(g["passed"]), np.asarray(q50, np.float32)


def realised(rows, procs):
    z = np.load(DD.OUT / "windows_test.npz")
    names, dancer, copy, win = z["dancers"], z["dancer"], z["copy"], z["win"]
    jobs, cache = [], {}
    for i in range(len(rows)):
        key = (dancer[i], copy[i])
        if key not in cache:
            cache[key] = np.load(next((DD.T0 / "seq").glob(f"*/{names[dancer[i]]}__{E.COPIES[copy[i]]}.npz")))["targets"]
        a = int(win[i]) * DD.WIN_ROWS
        jobs.append((rows[i].astype(float), cache[key][a - E.PRE:a].astype(float) if a >= E.PRE else None, E.COPIES[copy[i]][:2]))
    with mp.get_context("spawn").Pool(procs) as pool:
        res = pool.map(sim_one, jobs, chunksize=8)
    return np.array([r[0] for r in res]), np.stack([r[1] for r in res])


def stats(q, src):
    """per source (all / finedance / aioz) and joint: median over windows of both jitter measures at 50 Hz"""
    import jitter_diag as J
    per = [J.all_joints(w.astype(float), 50.0, JN) for w in q]
    out = {}
    for name, m in (("all", np.ones(len(src), bool)), ("finedance", src == 0), ("aioz", src == 1)):
        out[name] = {j: {k: float(np.median([per[i][j][k] for i in np.flatnonzero(m)])) for k in E.METRICS} for j in JN}
    return out


def main(procs=8):
    te = DD.load("test")
    post, tgt = E.test_rows()
    sets = {"original": tgt}
    for run in ("A", "B"):
        rec = np.load(OUT / f"run{run}" / "recon_test.npy")
        r = post.copy()
        r[:, :2000] += rec
        r[:, 2000] += rec[:, -1]
        sets[f"run{run}"] = r
    res, gate = {}, {}
    for name, rows in sets.items():
        ok, q = realised(rows, procs)
        res[name] = stats(q, te["src"])
        gate[name] = {s: float(ok[m].mean()) for s, m in (("all", np.ones(len(ok), bool)), ("finedance", te["src"] == 0), ("aioz", te["src"] == 1))}
        print(name, gate[name], flush=True)
    (OUT / "realised.json").write_text(json.dumps(dict(stats=res, gate=gate), indent=1))
    L = ["", "## Realised-stage jitter (appended; report only)", "",
         "Stage: after guard, spinal layer (H1), limiter, servo and v2p body (the gate's own simulation, `q50` at 50 Hz), test windows (2,455), medians over windows; the rebuilds go through the same chain as the original windows (Run A / Run B reconstructions).", "",
         "| source | joint | metric | original | Run A | Run B | A / original | B / original |", "|---|---|---|---|---|---|---|---|"]
    for s in ("all", "finedance", "aioz"):
        for j in JN:
            for k, title in (("acc_sign_changes_per_s", "acc sign changes /s"), ("p_gt3", "power > 3 Hz")):
                o, a, b = (res[n][s][j][k] for n in ("original", "runA", "runB"))
                L.append(f"| {s} | {j} | {title} | {o:.4f} | {a:.4f} | {b:.4f} | {a / o:.2f} | {b / o:.2f} |")
    L += ["", "Gate share (realised simulation, same windows): " + "; ".join(f"{n}: all {g['all']:.3f}, FineDance {g['finedance']:.3f}, AIOZ {g['aioz']:.3f}" for n, g in gate.items()) + "."]
    p = HERE.parents[1] / "docs" / "T1A2_REPORT.md"
    t = p.read_text()
    p.write_text(t.split("\n## Realised-stage jitter")[0].rstrip("\n") + "\n" + "\n".join(L) + "\n")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
