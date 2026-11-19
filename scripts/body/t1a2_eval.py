"""WO39 T1a2 evaluation (rules docs/T1A2_RULES.md section 5). Brain env.

    t1a2_eval.py recon A|B        reconstruct validation + test windows; variance explained, jitter / range measures -> t1a2/run<X>/{recon_test.npy, recon_val.npy, measures.json, variance.json}
    t1a2_eval.py gates A|B [P]    gates at 1.25 of the reconstructed test windows (T0 gate code via t1a_eval.gate_one) -> t1a2/run<X>/gates.json
    t1a2_eval.py report           docs/T1A2_REPORT.md (numbers only)
The control gate (original test windows) is t1a/k0/gates.json from T1a.
"""
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

OUT = TR2.OUT
JN = E.JN
GATE_MIN = 0.95                                                          # (default) the rules say "gates at 1.25"; a run passes at >= 0.95 reconstructed-window pass share


def var_explained(g, r):
    gf, e = g.reshape(-1, 5), (r - g).reshape(-1, 5)
    return (1 - e.var(0) / gf.var(0)).tolist()


def recon_of(model, g, sd):
    import torch
    x, out = torch.from_numpy(g / sd), []
    with torch.no_grad():
        for i in range(0, len(x), 64):
            out.append(model(x[i:i + 64])["recon"].numpy())
    return np.concatenate(out) * sd


def cmd_recon(run):
    import torch
    torch.set_num_threads(8)
    sd, d = DD.scale(), OUT / f"run{run}"
    model = TR2.make(run)
    model.load_state_dict(torch.load(d / "best.pt"))
    model.eval()
    var = {}
    for split in ("validation", "test"):
        data = DD.load(split)
        r = recon_of(model, data["g"], sd)
        np.save(d / f"recon_{'val' if split == 'validation' else 'test'}.npy", r.astype(np.float32))
        for s, n in ((0, "finedance"), (1, "aioz")):
            m = data["src"] == s
            var[f"{split}|{n}"] = var_explained(data["g"][m], r[m])
        if split == "test":
            te, rec = data, r
    (d / "variance.json").write_text(json.dumps(var, indent=1))
    post, tgt = E.test_rows()
    rt = post.copy()
    rt[:, :2000] += rec
    rt[:, 2000] += rec[:, -1]
    res = E.measures(tgt, rt, te["src"], E.jitter_rows)
    (d / "measures.json").write_text(json.dumps(res, indent=1))
    print(run, {k: [round(x, 3) for x in v] for k, v in var.items()})


def cmd_gates(run, procs=8):
    d = OUT / f"run{run}"
    te = DD.load("test")
    post, tgt = E.test_rows()
    z = np.load(DD.OUT / "windows_test.npz")
    names, dancer, copy, win = z["dancers"], z["dancer"], z["copy"], z["win"]
    rec = np.load(d / "recon_test.npy")
    rows = post.copy()
    rows[:, :2000] += rec
    rows[:, 2000] += rec[:, -1]
    jobs, cache = [], {}
    for i in range(len(rows)):
        key = (dancer[i], copy[i])
        if key not in cache:
            cache[key] = np.load(next((DD.T0 / "seq").glob(f"*/{names[dancer[i]]}__{E.COPIES[copy[i]]}.npz")))["targets"]
        a = int(win[i]) * DD.WIN_ROWS
        pre = cache[key][a - E.PRE:a].astype(float) if a >= E.PRE else None
        jobs.append((rows[i].astype(float), pre, E.COPIES[copy[i]][:2]))
    with mp.get_context("spawn").Pool(procs) as pool:
        res = pool.map(E.gate_one, jobs, chunksize=8)
    out = dict(n=len(res), pass_share=float(np.mean([r["passed"] for r in res])), per_source={}, failed_parts={})
    for s, n in ((0, "finedance"), (1, "aioz")):
        m = [r for r, x in zip(res, te["src"]) if x == s]
        out["per_source"][n] = dict(n=len(m), pass_share=float(np.mean([r["passed"] for r in m])))
    for p in res[0]["parts"]:
        out["failed_parts"][p] = int(sum(not r["parts"][p] for r in res))
    (d / "gates.json").write_text(json.dumps(out))
    print(run, "gate pass share", out["pass_share"], out["per_source"], flush=True)


def rules_check(run, log):
    d = OUT / f"run{run}"
    m = json.loads((d / "measures.json").read_text())["all"]
    var = json.loads((d / "variance.json").read_text())
    g = json.loads((d / "gates.json").read_text())
    b = min(log, key=lambda e: e["err_weighted"])
    usage = [b["code_usage"]] + ([b["code_usage_stage2"]] if "code_usage_stage2" in b else [])
    chk = dict(usage=min(usage) >= 0.60, jitter=all((m[j][k]["ratio"] or 0) <= 1.1 for j in JN for k in E.METRICS), range=all(0.9 <= m[j]["range_p5_p95"]["ratio"] <= 1.1 for j in JN),
               gates=g["pass_share"] >= GATE_MIN, variance=all(x >= 0.85 for x in var["validation|finedance"]))
    chk["all"] = all(chk.values())
    return chk, m, var, g, b, usage


def cmd_report():
    L = ["# T1a2 report (work order 39, BRAIN_SPEC 7.61; numbers only, no verdict)", "",
         "Rules `T1A2_RULES.md`; Step 1 `T1A2_STEP1.md`. Both runs: AIOZ capped at 50 % of train weight (factor " + f"{json.loads((OUT / 'weights.json').read_text())['aioz_factor']:.3f}" + "), Bailando loss, spline decoder, 80-epoch cap, 4 threads each. "
         f"Gate rule applied as pass share >= {GATE_MIN} (default).", ""]
    summary = {}
    ctl = json.loads((DD.OUT / "k0" / "gates.json").read_text())
    for run, title in (("A", "Run A: K = 1024 single codebook"), ("B", "Run B: 2 x 1024 residual")):
        log = json.loads((OUT / f"run{run}" / "log.json").read_text())
        done = json.loads((OUT / f"run{run}" / "done.json").read_text())
        chk, m, var, g, b, usage = rules_check(run, log)
        summary[run] = chk
        L += [f"## {title}", "", f"Epochs {len(log)} ({done['stopped']}); best validation error (weighted MSE, scaled, capped weights) {b['err_weighted']:.4f}; FineDance {b.get('err_finedance', float('nan')):.4f}, AIOZ {b.get('err_aioz', float('nan')):.4f}; "
              f"code usage (validation) {', '.join(f'{u:.3f}' for u in usage)}{' (stage 1, stage 2)' if len(usage) > 1 else ''}.", "",
              "| rule | value | passes |", "|---|---|---|",
              f"| code usage >= 0.60 | {min(usage):.3f} | {chk['usage']} |",
              f"| jitter ratios <= 1.1 (worst acc sign changes / worst power > 3 Hz) | {max(m[j]['acc_sign_changes_per_s']['ratio'] for j in JN):.2f} / {max((m[j]['p_gt3']['ratio'] or 0) for j in JN):.2f} | {chk['jitter']} |",
              f"| joint ranges within 10 % (min / max ratio) | {min(m[j]['range_p5_p95']['ratio'] for j in JN):.3f} / {max(m[j]['range_p5_p95']['ratio'] for j in JN):.3f} | {chk['range']} |",
              f"| gates at 1.25 (reconstructed pass share; FineDance / AIOZ; control {ctl['pass_share']:.3f}) | {g['pass_share']:.3f} ({g['per_source']['finedance']['pass_share']:.3f} / {g['per_source']['aioz']['pass_share']:.3f}) | {chk['gates']} |",
              f"| variance explained >= 0.85 on every joint, FineDance validation (min) | {min(var['validation|finedance']):.3f} | {chk['variance']} |", "",
              "### Variance explained per joint", "", "| split | dataset | " + " | ".join(JN) + " |", "|---|---|" + "---|" * 5]
        for k, v in var.items():
            L.append("| " + k.replace("|", " | ") + " | " + " | ".join(f"{x:.3f}" for x in v) + " |")
        L += ["", "### Jitter and range ratios (recon / original, test windows; medians over windows)", "", "| source | joint | acc sign changes ratio | power > 3 Hz ratio | range ratio |", "|---|---|---|---|---|"]
        for s, r in json.loads((OUT / f"run{run}" / "measures.json").read_text()).items():
            for j in JN:
                e = r[j]
                L.append(f"| {s} | {j} | {e['acc_sign_changes_per_s']['ratio']:.3f} | {(e['p_gt3']['ratio'] or float('nan')):.3f} | {e['range_p5_p95']['ratio']:.3f} |")
        L.append("")
    L += ["## Result by rule", "", "| run | usage | jitter | ranges | gates | variance >= 0.85 | all |", "|---|---|---|---|---|---|---|"]
    for run, c in summary.items():
        L.append(f"| {run} | {c['usage']} | {c['jitter']} | {c['range']} | {c['gates']} | {c['variance']} | {c['all']} |")
    cand = next((r for r in ("A", "B") if summary[r]["all"]), None)
    L += ["", f"S1 candidate (smaller passing model, A before B): **{cand or 'none: neither run passes; report and hold'}**."]
    (HERE.parents[1] / "docs" / "T1A2_REPORT.md").write_text("\n".join(L) + "\n")
    print("report written; candidate", cand)


if __name__ == "__main__":
    a = sys.argv[1:]
    {"recon": lambda: cmd_recon(a[1]), "gates": lambda: cmd_gates(a[1], int(a[2]) if len(a) > 2 else 8), "report": cmd_report}[a[0]]()
