"""WO38 T1a stop measures (rules docs/T1A_RULES.md section 5; BRAIN_SPEC 7.59.4.1, 7.60.4). Brain env (torch CPU); gates need mujoco (also in the brain env).

    t1a_eval.py recon K           reconstruct the test windows with k<K>/best.pt -> t1a/k<K>/recon_test.npy (N, 2000, 5) gesture in degrees; jitter / range measures -> k<K>/measures.json
    t1a_eval.py gates K [PROCS]   gates at 1.25 of the reconstructed test windows (K = 0: the original windows, the control) -> k<K>/gates.json
    t1a_eval.py report            codebook-size rule + docs/T1A_REPORT.md (numbers only)
"""
import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t1a_data as DD  # noqa: E402

OUT, T0 = DD.OUT, DD.T0
JN = ("base_yaw", "shoulder", "elbow", "wrist_bend", "wrist_roll")
METRICS = ("acc_sign_changes_per_s", "p_gt3")
PRE = 150                                                                 # 1.5 s pre-roll rows at 100 Hz
COPIES = DD.COPIES


def measures(orig, recon, src, jitter_fn):
    """orig, recon (N, 2001 or 2000, 5) deg: posture + gesture rows of the test windows; src (N,) 0 FineDance / 1 AIOZ. -> per source ("all", "finedance", "aioz") per joint:
    median over windows of each jitter metric for the original and the reconstruction, their ratio, and the p5-p95 range of the pooled rows with its ratio"""
    out = {}
    for name, m in (("all", np.ones(len(src), bool)), ("finedance", src == 0), ("aioz", src == 1)):
        if not m.any():
            continue
        jo = [jitter_fn(o) for o in orig[m]]
        jr = [jitter_fn(r) for r in recon[m]]
        res = {}
        for i, j in enumerate(JN):
            e = {}
            for k in METRICS:
                a, b = float(np.median([x[i][k] for x in jo])), float(np.median([x[i][k] for x in jr]))
                e[k] = dict(original=a, recon=b, ratio=b / a if a > 0 else None)
            po, pr = np.percentile(orig[m][:, :, i], [5, 95]), np.percentile(recon[m][:, :, i], [5, 95])
            e["range_p5_p95"] = dict(original=float(po[1] - po[0]), recon=float(pr[1] - pr[0]), ratio=float((pr[1] - pr[0]) / (po[1] - po[0])))
            res[j] = e
        out[name] = res
    return out


def jitter_rows(x):
    import jitter_diag as J
    d = J.all_joints(np.asarray(x, float), 100.0, JN)
    return [d[j] for j in JN]


def test_rows():
    """posture rows (N, 2001, 5) and original target rows of the test windows, from the T0 npz (cached t1a/test_rows.npz)"""
    p = OUT / "test_rows.npz"
    if p.exists():
        z = np.load(p)
        return z["post"], z["tgt"]
    z = np.load(OUT / "windows_test.npz")
    names, dancer, copy, win = z["dancers"], z["dancer"], z["copy"], z["win"]
    post, tgt = np.zeros((len(win), 2001, 5), np.float32), np.zeros((len(win), 2001, 5), np.float32)
    for n in np.unique(dancer):
        for c in np.unique(copy[dancer == n]):
            m = np.flatnonzero((dancer == n) & (copy == c))
            f = np.load(next((T0 / "seq").glob(f"*/{names[n]}__{COPIES[c]}.npz")))
            for i in m:
                a = int(win[i]) * DD.WIN_ROWS
                post[i], tgt[i] = f["posture"][a:a + 2001], f["targets"][a:a + 2001]
    np.savez(p, post=post, tgt=tgt)
    return post, tgt


def cmd_recon(k):
    import torch
    import t1a_train as TR
    torch.set_num_threads(8)
    sd = DD.scale()
    te = DD.load("test")
    model = TR.make(int(k))
    model.load_state_dict(torch.load(OUT / f"k{k}" / "best.pt"))
    model.eval()
    g = torch.from_numpy(te["g"] / sd)
    rec = []
    with torch.no_grad():
        for i in range(0, len(g), 64):
            rec.append(model(g[i:i + 64])["recon"].numpy())
    rec = np.concatenate(rec) * sd
    np.save(OUT / f"k{k}" / "recon_test.npy", rec.astype(np.float32))
    post, tgt = test_rows()
    recon_t = post.copy()
    recon_t[:, :2000] += rec
    recon_t[:, 2000] += rec[:, -1]                                          # the window's 2001st row takes the last reconstructed gesture row
    res = measures(tgt, recon_t, te["src"], jitter_rows)
    (OUT / f"k{k}" / "measures.json").write_text(json.dumps(res, indent=1))
    print(k, {s: {j: round(res[s][j]["p_gt3"]["ratio"] or 0, 3) for j in JN} for s in res})


# ---------------------------------------------------------------------------------------------------- gates
def gate_one(args):
    """one window: rows (2001, 5) window start deg (posture + gesture), preroll (150, 5) original target rows before the window (or None), var -> dict(passed, parts, guard_share)"""
    rows, pre, var = args
    import make_arm_v2p as P
    import motornet as M
    import retarget as RT
    import retarget_limiter as FX
    import retarget_run as RR
    RR.patch_gates()
    K = RT.to_commands(np.zeros((1, 5)), var)[0]                              # command of the zero-referenced angle: the value yaw and roll start from in a window
    sh = np.zeros(5)
    sh[[0, 4]] = (rows[0] - K)[[0, 4]]
    pre = np.repeat(rows[:1], PRE, 0) if pre is None else pre
    G0 = np.concatenate([pre, rows]) - sh                                     # yaw and roll re-referenced to the window start (as T0)
    G, gs = P.guard(G0)
    q50, contacts = FX.simulate_goals(M.spinal(G))
    g = RR.gates_v2p(q50, contacts, gs)
    return dict(passed=bool(g["passed"]), parts={k: bool(v) for k, v in g["parts"].items()}, guard_share=float(gs))


def cmd_gates(k, procs=8):
    k = int(k)
    te = DD.load("test")
    post, tgt = test_rows()
    z = np.load(OUT / "windows_test.npz")
    names, dancer, copy, win = z["dancers"], z["dancer"], z["copy"], z["win"]
    if k:
        rec = np.load(OUT / f"k{k}" / "recon_test.npy")
        rows = post.copy()
        rows[:, :2000] += rec
        rows[:, 2000] += rec[:, -1]
    else:
        rows = tgt
    jobs, cache = [], {}
    for i in range(len(rows)):
        key = (dancer[i], copy[i])
        if key not in cache:
            cache[key] = np.load(next((T0 / "seq").glob(f"*/{names[dancer[i]]}__{COPIES[copy[i]]}.npz")))["targets"]
        a = int(win[i]) * DD.WIN_ROWS
        pre = cache[key][a - PRE:a].astype(float) if a >= PRE else None
        jobs.append((rows[i].astype(float), pre, COPIES[copy[i]][:2]))
    with mp.get_context("spawn").Pool(procs) as pool:
        res = pool.map(gate_one, jobs, chunksize=8)
    out = dict(k=k, n=len(res), pass_share=float(np.mean([r["passed"] for r in res])), per_source={}, failed_parts={})
    for s, n in ((0, "finedance"), (1, "aioz")):
        m = [r for r, x in zip(res, te["src"]) if x == s]
        out["per_source"][n] = dict(n=len(m), pass_share=float(np.mean([r["passed"] for r in m])))
    for p in res[0]["parts"]:
        out["failed_parts"][p] = int(sum(not r["parts"][p] for r in res))
    out["passed_flags"] = [r["passed"] for r in res]
    (OUT / f"k{k}" / "gates.json").parent.mkdir(exist_ok=True)
    (OUT / f"k{k}" / "gates.json").write_text(json.dumps(out))
    print(k, "gate pass share", out["pass_share"], out["per_source"], flush=True)


# ---------------------------------------------------------------------------------------------------- report
def pick_size(best):
    """rules 5: the smallest K whose best validation error is within 5 % of the next larger K's; none -> the largest. best: {K: error}"""
    ks = sorted(best)
    for a, b in zip(ks, ks[1:]):
        if best[a] <= 1.05 * best[b]:
            return a
    return ks[-1]


def cmd_report():
    sizes = (128, 256, 512, 1024)
    logs = {k: json.loads((OUT / f"k{k}" / "log.json").read_text()) for k in sizes}
    best = {k: min(e["err_weighted"] for e in logs[k]) for k in sizes}
    chosen = pick_size(best)
    L = ["# T1a report (work order 38, BRAIN_SPEC 7.59.3.1 / 7.59.4.1 / 7.60.4; numbers only, no verdict)", "",
         "Rules `T1A_RULES.md`. Training: 4 threads per unit, two units in parallel (K = 1024 and 512, then 256 and 128). Errors are in scaled gesture units.", "",
         "## Validation reconstruction error and code usage (best epoch)", "", "| K | epochs | stopped | best err (weighted) | FineDance err | AIOZ err | code usage | FineDance usage | AIOZ usage |", "|---|---|---|---|---|---|---|---|---|"]
    for k in sizes:
        b = min(logs[k], key=lambda e: e["err_weighted"])
        dn = json.loads((OUT / f"k{k}" / "done.json").read_text())
        L.append(f"| {k} | {len(logs[k])} | {dn['stopped']} | {b['err_weighted']:.4f} | {b.get('err_finedance', float('nan')):.4f} | {b.get('err_aioz', float('nan')):.4f} | {b['code_usage']:.3f} | {b.get('code_usage_finedance', float('nan')):.3f} | {b.get('code_usage_aioz', float('nan')):.3f} |")
    L += ["", f"Size rule (smallest K within 5 % of the next larger): **K = {chosen}**. Errors by K: " + ", ".join(f"{k}: {best[k]:.4f}" for k in sizes) + ". Ratios to the next larger: " +
          ", ".join(f"{a} vs {b}: {best[a] / best[b]:.3f}" for a, b in zip(sizes, sizes[1:])) + ".", ""]
    ctl = json.loads((OUT / "k0" / "gates.json").read_text()) if (OUT / "k0" / "gates.json").exists() else None
    L += ["## Stop measures on the test windows (all four sizes; stop rules: usage >= 0.60, jitter ratio <= 1.1, range ratio within 0.9-1.1, gates at 1.25)", "",
          "| K | usage (val) | gate pass share (recon) | FineDance | AIOZ | control (original) | worst jitter ratio (acc sign changes) | worst p_gt3 ratio | range ratio min / max |", "|---|---|---|---|---|---|---|---|---|"]
    for k in sizes:
        m = json.loads((OUT / f"k{k}" / "measures.json").read_text())["all"]
        g = json.loads((OUT / f"k{k}" / "gates.json").read_text())
        ra = [m[j]["acc_sign_changes_per_s"]["ratio"] for j in JN]
        rp = [m[j]["p_gt3"]["ratio"] for j in JN]
        rr = [m[j]["range_p5_p95"]["ratio"] for j in JN]
        u = min(logs[k], key=lambda e: e["err_weighted"])["code_usage"]
        L.append(f"| {k} | {u:.3f} | {g['pass_share']:.3f} | {g['per_source']['finedance']['pass_share']:.3f} | {g['per_source']['aioz']['pass_share']:.3f} | {ctl['pass_share'] if ctl else float('nan'):.3f} | {max(ra):.3f} | {max(x or 0 for x in rp):.3f} | {min(rr):.3f} / {max(rr):.3f} |")
    for k in sizes:
        mm = json.loads((OUT / f"k{k}" / "measures.json").read_text())
        L += ["", f"### K = {k}: per joint and source (ratio recon / original; range = p5-p95 in degrees)", "", "| source | joint | acc sign changes ratio | power > 3 Hz ratio | range original | range recon | range ratio |", "|---|---|---|---|---|---|---|"]
        for s, r in mm.items():
            for j in JN:
                e = r[j]
                L.append(f"| {s} | {j} | {e['acc_sign_changes_per_s']['ratio']:.3f} | {(e['p_gt3']['ratio'] or float('nan')):.3f} | {e['range_p5_p95']['original']:.1f} | {e['range_p5_p95']['recon']:.1f} | {e['range_p5_p95']['ratio']:.3f} |")
    if ctl:
        L += ["", f"Control: the original test windows through the same gate function pass {ctl['pass_share']:.3f} (FineDance {ctl['per_source']['finedance']['pass_share']:.3f}, AIOZ {ctl['per_source']['aioz']['pass_share']:.3f}); T0 itself kept them all by construction."]
    (DOCS := HERE.parents[1] / "docs" / "T1A_REPORT.md").write_text("\n".join(L) + "\n")
    print("chosen K", chosen, "report written")


if __name__ == "__main__":
    a = sys.argv[1:]
    {"recon": lambda: cmd_recon(a[1]), "gates": lambda: cmd_gates(a[1], int(a[2]) if len(a) > 2 else 8), "report": cmd_report}[a[0]]()
