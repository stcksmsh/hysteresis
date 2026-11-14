"""WO37 T0 report (body env): docs/T0_REPORT.md + t0/numbers.json from the npz files, split.json and the catalogues. Numbers only, no verdict. python -u t0_report.py"""
import collections
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jitter_diag as J  # noqa: E402
import retarget_run as RR  # noqa: E402
import t0_chain as C  # noqa: E402
import t0_lib as T  # noqa: E402

OUT = Path("/secondary/hyst-data/body/t0")
DOCS = Path(__file__).resolve().parents[2] / "docs"


def med(v):
    return float(np.median(v)) if len(v) else None


def main():
    cat = json.loads((OUT / "catalogue_fd.json").read_text()) + json.loads((OUT / "catalogue_aioz.json").read_text())
    byk = {c["key"]: c for c in cat}
    sp = json.loads((OUT / "split.json").read_text())
    group_split = {k: (r["group"], r["split"]) for r in sp["groups"] for k in r["members"]}
    rows = collections.defaultdict(lambda: collections.defaultdict(float))                  # (dataset, copy, split) -> counters
    gen = collections.defaultdict(lambda: collections.defaultdict(float))                   # (dataset, genre, copy) -> counters
    jit = collections.defaultdict(list)                                                    # (dataset, variant) -> per-dancer joint measures
    weights = collections.defaultdict(list)
    missing = []
    for k, c in byk.items():
        if k not in group_split:
            continue
        for copy in C.COPIES:
            p = OUT / "seq" / c["dataset"] / f"{k}__{copy}.npz"
            if not p.exists():
                missing.append(p.name)
                continue
            z = np.load(p)
            ds, spl = c["dataset"], group_split[k][1]
            n, ok = int(z["n_win"]), z["win_pass"]
            tail = (c["t30"] - 1) / T.FPS - n * T.WIN_S
            for key, counters in (((ds, copy, spl), rows), ((ds, c["genre"], copy), gen)):
                r = counters[key]
                r["dancers"] += 1
                r["windows"] += n
                r["windows_kept"] += int(ok.sum())
                r["hours_usable"] += int(ok.sum()) * T.WIN_S / 3600
                r["tails_dropped"] += int(tail > 1e-9)
                r["tail_hours"] += tail / 3600
                r["tokens"] += len(z["tokens"])
                r["tokens_masked"] += int(z["token_mask"].sum())
                r["weighted_hours_usable"] += float(z["weight"]) * int(ok.sum()) * T.WIN_S / 3600
                for pn, col in zip(z["win_part_names"], np.asarray(z["win_parts"]).T if n else []):
                    r["failed_" + str(pn)] += int((~col).sum())
            if copy == "V1":
                weights[ds].append(float(z["weight"]))
            if copy in ("V1", "V2") and len(z["targets"]) > 200:
                jit[(ds, copy)].append(J.all_joints(np.asarray(z["targets"], float), 100.0, RR.JN))
    out = dict(missing=missing, by_dataset_copy_split={"|".join(k): dict(v) for k, v in rows.items()}, by_dataset_genre_copy={"|".join(k): dict(v) for k, v in gen.items()},
               weights={ds: dict(n=len(w), mean=float(np.mean(w)), min=float(np.min(w)), capped_dancers=int(sum(1 for x in w if x < 1.0))) for ds, w in weights.items()},
               jitter={f"{ds}|{v}": {j: {m: med([d[j][m] for d in L]) for m in ("acc_sign_changes_per_s", "p_gt3")} for j in RR.JN} for (ds, v), L in jit.items()})
    log = OUT / "seq.log"
    if log.exists():
        e = re.findall(r"elapsed (\d+)s", log.read_text())
        out["run_seconds_sequences"] = int(e[-1]) if e else None
    est = OUT / "estimate.json"
    if est.exists():
        out["estimate"] = json.loads(est.read_text())
    out["split_groups"] = {s: sum(1 for r in sp["groups"] if r["split"] == s) for s in ("train", "validation", "test")}
    out["token_norm"] = {k: v for k, v in json.loads((OUT / "token_norm.json").read_text()).items() if k.startswith("n_")}
    (OUT / "numbers.json").write_text(json.dumps(out, indent=1))
    L = ["# T0 report (work order 37, BRAIN_SPEC 7.59 / 7.60; numbers only, no verdict)", "",
         f"Rules `T0_RULES.md`. Groups per split: {out['split_groups']}. Missing npz: {len(missing)}. Run time of the sequence stage: {out.get('run_seconds_sequences')} s. Data: `t0/numbers.json`.", "",
         "## Per dataset, copy and split", "", "| dataset | copy | split | dancers | windows | kept | usable h | weighted usable h | tails dropped | tokens | masked tokens | failed parts |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for (ds, copy, spl), r in sorted(rows.items()):
        fp = ", ".join(f"{k[7:]} {int(v)}" for k, v in r.items() if k.startswith("failed_") and v)
        L.append(f"| {ds} | {copy} | {spl} | {int(r['dancers'])} | {int(r['windows'])} | {int(r['windows_kept'])} | {r['hours_usable']:.2f} | {r['weighted_hours_usable']:.2f} | {int(r['tails_dropped'])} | {int(r['tokens'])} | {int(r['tokens_masked'])} | {fp or '-'} |")
    L += ["", "## Per dataset, genre and copy", "", "| dataset | genre | copy | dancers | windows | kept | usable h | failed parts |", "|---|---|---|---|---|---|---|---|"]
    for (ds, g, copy), r in sorted(gen.items()):
        fp = ", ".join(f"{k[7:]} {int(v)}" for k, v in r.items() if k.startswith("failed_") and v)
        L.append(f"| {ds} | {g} | {copy} | {int(r['dancers'])} | {int(r['windows'])} | {int(r['windows_kept'])} | {r['hours_usable']:.2f} | {fp or '-'} |")
    L += ["", "## Weights (V1 copy; 1.0 = uncapped)", ""] + [f"- {ds}: {w}" for ds, w in out["weights"].items()]
    L += ["", "## Jitter of the stored targets (median over dancers; 100 Hz; V1, V2 copies; report only, AIOZ vs FineDance)", "", "| variant | joint | FineDance acc sign changes /s | AIOZ | FineDance power > 3 Hz | AIOZ |", "|---|---|---|---|---|---|"]
    for v in ("V1", "V2"):
        for j in RR.JN:
            a, b = out["jitter"].get(f"finedance|{v}", {}).get(j), out["jitter"].get(f"aioz|{v}", {}).get(j)
            if a and b:
                L.append(f"| {v} | {j} | {a['acc_sign_changes_per_s']:.2f} | {b['acc_sign_changes_per_s']:.2f} | {a['p_gt3']:.4f} | {b['p_gt3']:.4f} |")
    L += ["", "## Notes", "", "- Token coverage: a masked token has at least one surprisal layer undefined (clip starts; the deeper layers have longer horizons); its undefined columns are 0 after standardising.",
          "- Gate parts count windows that failed that part (a window can fail several). Usable hours = kept windows x 20 s.", "- Estimate from one long FineDance sequence: see `numbers.json` key `estimate`."]
    (DOCS / "T0_REPORT.md").write_text("\n".join(L) + "\n")
    print("report written; missing", len(missing))


if __name__ == "__main__":
    main()
