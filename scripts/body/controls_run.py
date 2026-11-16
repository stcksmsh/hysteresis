"""WO43 driver. Rules: docs/CONTROLS_RULES.md. Out: /secondary/hyst-data/body/controls/ (outside git; Motorica stays on this laptop).

    controls_run.py sim [PROCS]        body env: realised q50 (50 Hz) + lamp of every kept window of every copy -> controls/q50/<dataset>/<name>.npz  (resumable)
    controls_run.py norm               brain env: constants from FineDance train kept tokens -> controls/norm.json
    controls_run.py controls [PROCS]   brain env: the six controls per token -> controls/<dataset>/<name>.npz  (resumable)
"""
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
B = Path("/secondary/hyst-data/body")
OUT = B / "controls"
ROOTS = {"finedance": B / "t0/seq/finedance", "aioz": B / "t0/seq/aioz", "phantom": B / "t0_phantom/seq", "motorica": B / "t0_motorica/seq"}
PRE, WIN_ROWS = 150, 2000


def files(ds):
    return sorted(ROOTS[ds].glob("*.npz"))


def sim_file(args):
    """one T0 npz -> controls/q50/<ds>/<name>.npz with win, q50 (n, 1001, 5) float32, lamp (n, 1001, 3) float64, gate_again (n,)"""
    ds, path = args
    dst = OUT / "q50" / ds / path.name
    if dst.exists():
        return path.name, 0, 0.0
    import make_arm_v2p as P
    import motornet as M
    import retarget as RT
    import retarget_limiter as FX
    import retarget_run as RR
    import m3f_report as R
    RR.patch_gates()
    t0 = time.time()
    z = np.load(path)
    var = path.stem.split("__")[1][:2]
    K = RT.to_commands(np.zeros((1, 5)), var)[0]
    tg = z["targets"].astype(float)
    keep = np.flatnonzero(z["win_pass"])
    qs, lamps, ok = [], [], []
    for w in keep:
        a = int(w) * WIN_ROWS
        rows = tg[a:a + WIN_ROWS + 1]
        pre = tg[a - PRE:a] if a >= PRE else np.repeat(rows[:1], PRE, 0)
        sh = np.zeros(5)
        sh[[0, 4]] = (rows[0] - K)[[0, 4]]
        G, gs = P.guard(np.concatenate([pre, rows]) - sh)
        q50, contacts = FX.simulate_goals(M.spinal(G))
        g = RR.gates_v2p(q50, contacts, gs)
        qs.append(np.asarray(q50, np.float32))
        lamps.append(R.fk_points(np.asarray(q50, float))[:, 5])
        ok.append(bool(g["passed"]))
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, win=keep.astype(np.int32), q50=np.array(qs, np.float32).reshape(len(keep), -1, 5), lamp=np.array(lamps, float).reshape(len(keep), -1, 3),
                        gate_again=np.array(ok, bool), split=str(z["split"]), group=str(z["group"]), weight=float(z["weight"]))
    tmp.replace(dst)
    return path.name, len(keep), time.time() - t0


def cmd_sim(procs=8):
    jobs = [(ds, p) for ds in ROOTS for p in files(ds)]
    t0, nw = time.time(), 0
    with mp.get_context("spawn").Pool(procs) as pool:
        for i, (name, n, s) in enumerate(pool.imap_unordered(sim_file, jobs, chunksize=2)):
            nw += n
            if i % 200 == 0:
                print(f"{i}/{len(jobs)} files, {nw} windows, elapsed {time.time() - t0:.0f}s, last {name} {n} win {s:.1f}s", flush=True)
    print("SIM DONE", len(jobs), "files", nw, "windows", f"{time.time() - t0:.0f}s", flush=True)


def load_q(ds, name):
    z = np.load(OUT / "q50" / ds / name)
    return {k: z[k] for k in z.files}


def cmd_norm():
    import controls_lib as C
    raws = []
    for p in files("finedance"):
        z = np.load(OUT / "q50" / "finedance" / p.name)
        if str(z["split"]) != "train":
            continue
        for q, l in zip(z["q50"], z["lamp"]):
            raws.append(C.raw_window(q.astype(float), l))
    nm = C.fit_norm(raws)
    nm["n_windows"], nm["n_tokens"] = len(raws), len(raws) * C.NTOK
    (OUT / "norm.json").write_text(json.dumps(nm, indent=1))
    print("norm from", len(raws), "windows", json.dumps({k: v for k, v in nm.items() if k != "p90_abs_w"}), flush=True)


def ctl_file(args):
    ds, name = args
    import controls_lib as C
    dst = OUT / ds / name
    if dst.exists():
        return name, 0
    nm = json.loads((OUT / "norm.json").read_text())
    z = np.load(OUT / "q50" / ds / name)
    acc = {}
    for q, l in zip(z["q50"], z["lamp"]):
        c = C.finalise(C.raw_window(q.astype(float), l, p90=nm["p90_abs_w"]), nm)
        for k, v in c.items():
            acc.setdefault(k, []).append(v)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, win=z["win"], split=z["split"], group=z["group"], gate_again=z["gate_again"], **{k: np.array(v) for k, v in acc.items()})
    tmp.replace(dst)
    return name, len(z["win"])


def cmd_controls(procs=8):
    jobs = [(ds, p.name) for ds in ROOTS for p in files(ds) if (OUT / "q50" / ds / p.name).exists()]
    cnt = {}
    t0 = time.time()
    with mp.get_context("spawn").Pool(procs) as pool:
        for i, (name, n) in enumerate(pool.imap_unordered(ctl_file, jobs, chunksize=4)):
            if i % 500 == 0:
                print(f"{i}/{len(jobs)} {time.time() - t0:.0f}s", flush=True)
    for ds in ROOTS:
        ws = [np.load(p)["win"] for p in (OUT / ds).glob("*.npz")]
        cnt[ds] = dict(files=len(ws), windows=int(sum(len(w) for w in ws)), tokens=int(40 * sum(len(w) for w in ws)))
    (OUT / "counts.json").write_text(json.dumps(cnt, indent=1))
    print("CONTROLS COMPUTED", json.dumps(cnt), flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    {"sim": cmd_sim, "norm": cmd_norm, "controls": cmd_controls}[a[0]](*[int(x) for x in a[1:]])
