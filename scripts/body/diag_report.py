"""WO46 part 1 tables (docs/DIAG_RULES.md) from /secondary/hyst-data/body/diag/measures.json -> summary.json + docs/DIAG_TABLES.md. Brain env."""
import json
from pathlib import Path

import numpy as np

OUT = Path("/secondary/hyst-data/body/diag")
DOCS = Path(__file__).resolve().parents[2] / "docs"
COPIES = ("V1", "V1m", "V2", "V2m")
SEED, NBOOT = 46001, 2000
ROWS = [("H", "continuous human (4-copy mean)"), ("HJ4", "human re-joined A1 (4-copy mean)"), ("HJ|V1", "human re-joined A1, V1"),
        ("RT|A1", "retrieval, A1"), ("RT|hp", "retrieval gesture + human posture (i)"), ("RT|hg", "human gesture + retrieval posture (ii)"),
        ("RN|A1", "random chunks, A1"), ("RN|hp", "random gesture + human posture (i)"), ("RN|hg", "human gesture + random posture (ii)"),
        ("M|A1", "model 41101, A1"), ("M|hp", "model gesture + human posture (i)"), ("M|hg", "human gesture + model posture (ii)")]


def val(c, name, m):
    if name == "H":
        return float(np.mean([c[f"H|{k}"][m] for k in COPIES]))
    if name == "HJ4":
        return float(np.mean([c[f"HJ|{k}"][m] for k in COPIES]))
    return float(c[name][m])


def boot(x):
    rng = np.random.default_rng(SEED)
    b = [x[rng.integers(len(x), size=len(x))].mean() for _ in range(NBOOT)]
    return float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def main():
    res = json.loads((OUT / "measures.json").read_text())
    songs = sorted(res)
    test = [k for k in songs if res[k]["split"] == "test"]
    summ, lines = {}, []
    for label, ks in (("all 37 songs (M: 17 test only)", songs), ("17 test songs", test)):
        lines += [f"### {label}", "", "| condition | n | lamp p_gt3 mean | ratio to H mean [95 % boot] | ratio median | ratio of means | joint-mean ratio (mean of per-song) | frozen share | frozen - H |", "|---|---|---|---|---|---|---|---|---|"]
        for name, desc in ROWS:
            ok = [k for k in ks if name == "H" or name == "HJ4" or name in res[k]["cond"]]
            if not ok:
                continue
            g = lambda m, n=name: np.array([val(res[k]["cond"], n, m) for k in ok])   # noqa: E731
            h = lambda m: np.array([val(res[k]["cond"], "H", m) for k in ok])          # noqa: E731
            r, rj = g("lamp_p_gt3") / h("lamp_p_gt3"), g("joint_mean_p_gt3") / h("joint_mean_p_gt3")
            lo, hi = boot(r)
            fz, fh = g("frozen_share"), h("frozen_share")
            lines.append(f"| {desc} | {len(ok)} | {g('lamp_p_gt3').mean():.4f} | {r.mean():.2f} [{lo:.2f}, {hi:.2f}] | {np.median(r):.2f} | {g('lamp_p_gt3').mean() / h('lamp_p_gt3').mean():.2f} | {rj.mean():.2f} | {fz.mean():.3f} | {(fz - fh).mean():+.3f} |")
            summ[f"{label}|{name}"] = dict(n=len(ok), lamp=float(g("lamp_p_gt3").mean()), ratio_mean=float(r.mean()), ci=[lo, hi], ratio_median=float(np.median(r)), ratio_of_means=float(g("lamp_p_gt3").mean() / h("lamp_p_gt3").mean()),
                                           joint_ratio=float(rj.mean()), frozen=float(fz.mean()))
        lines.append("")
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1))
    (DOCS / "DIAG_TABLES.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
