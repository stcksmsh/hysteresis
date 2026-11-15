"""WO41 T2, part 4: diversity, aggregation over seeds, STOP checks, report tables (docs/T1B_RULES.md section 6). Brain env.

    t1b_t2d.py diversity SEED [--run DIR]     8-sample diversity and nearest-style shares -> DIR/t2/diversity.json
    t1b_t2d.py report [SEEDS...]              reads DIR/t2/{measures,swap,diversity,affect}.json of every seed -> t1b/t2/summary.json + docs/T1B_T2_TABLES.md
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t1b_t2 as T2  # noqa: E402

OUT, TR = T2.OUT, T2.TR
SEEDS = TR.SEEDS
JN = ("base_yaw", "shoulder", "elbow", "wrist_bend", "wrist_roll")


def rmsd(a, b, sd):
    return float(np.sqrt((((a - b) / sd) ** 2).mean()))


def cmd_diversity(seed, run):
    sd = np.asarray(json.loads(Path("/secondary/hyst-data/body/t1a/scale.json").read_text())["sd"], np.float32)
    res = {}
    for f in sorted((Path(run) / "t2" / "gen").glob("fd_*.npz")):
        key = f.stem
        g = np.load(f)
        n = len([k for k in g.files if k.startswith("rows_")])
        s = [g[f"rows_{i}"] for i in range(n)]
        h = T2.human_window(key)
        hc = {c: h[c]["rows"] for c in TR.COPIES}
        pair_s = [rmsd(s[i], s[j], sd) for i in range(n) for j in range(i + 1, n)]
        cs = list(TR.COPIES)
        pair_h = [rmsd(hc[cs[i]], hc[cs[j]], sd) for i in range(4) for j in range(i + 1, 4)]
        near = [cs[int(np.argmin([rmsd(x, hc[c], sd) for c in cs]))] for x in s]
        res[key] = dict(pairwise_samples=float(np.mean(pair_s)), pairwise_human_copies=float(np.mean(pair_h)), nearest={c: near.count(c) / n for c in cs})
    agg = dict(songs=res, mean_pairwise_samples=float(np.mean([v["pairwise_samples"] for v in res.values()])), mean_pairwise_human=float(np.mean([v["pairwise_human_copies"] for v in res.values()])),
               nearest_share={c: float(np.mean([v["nearest"][c] for v in res.values()])) for c in TR.COPIES})
    (Path(run) / "t2" / "diversity.json").write_text(json.dumps(agg, indent=1))
    print({k: v for k, v in agg.items() if k != "songs"})


def flat(d, prefix=""):
    """nested dict of numbers / lists -> {path: float} (lists expanded as path[i])"""
    out = {}
    for k, v in d.items():
        p = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flat(v, p + "."))
        elif isinstance(v, (list, tuple)):
            for i, x in enumerate(v):
                if isinstance(x, (int, float)) and x is not None:
                    out[f"{p}[{i}]"] = float(x)
        elif isinstance(v, (int, float)) and v is not None and not isinstance(v, bool):
            out[p] = float(v)
    return out


def per_system(meas, systems):
    """{system: {metric: mean over songs}}; the 'human' system averages the 4 copies inside each song first"""
    acc = {s: {} for s in systems}
    for key, e in meas.items():
        for s in systems:
            if s == "human":
                fl = [flat(e[f"human_{c}"]) for c in TR.COPIES if f"human_{c}" in e]
                v = {k: float(np.nanmean([f[k] for f in fl if k in f])) for k in fl[0]} if fl else {}
            else:
                v = flat(e[s]) if s in e else {}
            for k, x in v.items():
                acc[s].setdefault(k, []).append(x)
    return {s: {k: float(np.nanmean(v)) for k, v in d.items()} for s, d in acc.items()}


def stops(ps, swap, meas, ps_per_song_model_frozen):
    """the STOP list with values and thresholds; ps = per_system result of one seed"""
    h, m = ps["human"], ps["model"]
    out = {}
    out["swapped_music"] = dict(value=swap["mean_gap_nats"], ci95=swap["ci95"], threshold="95 % interval of the mean gap must exclude 0", stop=bool(swap["stop_swapped"]))
    r = {w: (m[f"selfsim_{w}tok"], h[f"selfsim_{w}tok"]) for w in (4, 16, 60)}
    out["repetition_selfsim_8s"] = dict(value=r[16][0], human=r[16][1], threshold="below half the human value", stop=bool(r[16][0] < 0.5 * r[16][1]))
    jr = {j: m[f"joint_range[{i}]"] / h[f"joint_range[{i}]"] for i, j in enumerate(JN)}
    out["joint_range"] = dict(value=jr, threshold="any joint < 0.5 of human", stop=bool(min(jr.values()) < 0.5))
    jit = {}
    for j in JN:
        for k in ("acc_sign_changes_per_s", "p_gt3"):
            jit[f"{j}.{k}"] = m[f"jitter.{j}.{k}"] / h[f"jitter.{j}.{k}"]
    out["jitter"] = dict(value=jit, threshold="any ratio > 1.5 (human copies on the same windows, realised stage)", stop=bool(max(jit.values()) > 1.5))
    out["frozen_pose"] = dict(value=ps_per_song_model_frozen, threshold="hand speed < 0.05 m/s for > 3 s anywhere (songs with such a stretch)", stop=bool(ps_per_song_model_frozen > 0))
    out["identical_shape_repeat"] = dict(value=m["ident_repeat"], human=h["ident_repeat"], threshold="> 2x human mean", stop=bool(m["ident_repeat"] > 2 * h["ident_repeat"]))
    return out


def cmd_report(seeds):
    systems = ("human", "model", "retrieval", "random")
    per_seed, st = {}, {}
    for s in seeds:
        run = OUT / "e1" / f"seed{s}" / "t2"
        meas = json.loads((run / "measures.json").read_text())
        swap = json.loads((run / "swap.json").read_text())
        ps = per_system(meas, systems)
        frozen = sum(1 for e in meas.values() if e["model"]["frozen_longest_s"] > 3.0)
        per_seed[s] = dict(ps=ps, swap={k: v for k, v in swap.items() if k != "songs"}, frozen_songs=frozen, n_songs=len(meas))
        st[s] = stops(ps, swap, meas, frozen)
        for extra in ("diversity", "affect"):
            if (run / f"{extra}.json").exists():
                per_seed[s][extra] = json.loads((run / f"{extra}.json").read_text())
    summ = dict(seeds=list(seeds), stops=st, per_seed={s: {k: v for k, v in d.items()} for s, d in per_seed.items()})
    keys = sorted(per_seed[seeds[0]]["ps"]["model"])
    spread = {}
    for sysn in systems:
        spread[sysn] = {k: [per_seed[s]["ps"][sysn].get(k) for s in seeds] for k in keys}
    summ["metric_by_seed"] = spread
    (OUT / "t2").mkdir(exist_ok=True)
    (OUT / "t2" / "summary.json").write_text(json.dumps(summ, indent=1))
    L = ["# T1b E1 T2 tables (generated by t1b_t2d.py)", "", "Mean over held-out songs; model = mean over seeds with min / max over seeds; human = 4 copies averaged inside each song first.", "",
         "## STOP checks (per seed)", "", "| check | threshold | " + " | ".join(f"seed {s}" for s in seeds) + " |", "|---|---|" + "---|" * len(seeds)]
    for c in st[seeds[0]]:
        vals = []
        for s in seeds:
            v = st[s][c]
            val = v["value"]
            vs = ("%.3f" % val) if isinstance(val, float) else (json.dumps({k: round(x, 2) for k, x in val.items()}) if isinstance(val, dict) else str(val))
            vals.append(f"{vs} **{'STOP' if v['stop'] else 'ok'}**")
        L.append(f"| {c} | {st[seeds[0]][c]['threshold']} | " + " | ".join(vals) + " |")
    L += ["", "## Measures", "", "| measure | human | retrieval | random | model mean | model min | model max |", "|---|---|---|---|---|---|---|"]
    f = lambda x: "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.4g}"
    for k in keys:
        mv = [x for x in spread["model"][k] if x is not None]
        row = [np.mean([x for x in spread[sysn][k] if x is not None]) if any(x is not None for x in spread[sysn][k]) else None for sysn in ("human", "retrieval", "random")]
        L.append(f"| {k} | {f(row[0])} | {f(row[1])} | {f(row[2])} | {f(np.mean(mv))} | {f(min(mv))} | {f(max(mv))} |")
    (HERE.parents[1] / "docs" / "T1B_T2_TABLES.md").write_text("\n".join(L) + "\n")
    print("report written", {s: [c for c, v in st[s].items() if v["stop"]] for s in seeds})


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "diversity":
        seed = int(a[1])
        cmd_diversity(seed, a[a.index("--run") + 1] if "--run" in a else str(OUT / "e1" / f"seed{seed}"))
    else:
        cmd_report([int(x) for x in a[1:]] or list(SEEDS))
