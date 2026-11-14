"""WO39 Step 1 (report-only, BRAIN_SPEC 7.61.2-3, 7.61.7): variance explained of the round-1 K = 1024 reconstruction per joint, dataset and split; gesture amplitude FineDance vs kept AIOZ (train);
effective weight share. Applies the dataset share rule mechanically. Brain env.  python -u t1a2_step1.py -> /secondary/hyst-data/body/t1a2/step1.json + docs/T1A2_STEP1.md"""
import json
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t1a_data as DD  # noqa: E402
import t1a_train as TR  # noqa: E402

OUT = Path("/secondary/hyst-data/body/t1a2")
JN = ("base_yaw", "shoulder", "elbow", "wrist_bend", "wrist_roll")
NAMES = {0: "finedance", 1: "aioz"}


def recon(model, g, sd):
    x = torch.from_numpy(g / sd)
    out = []
    with torch.no_grad():
        for i in range(0, len(x), 64):
            out.append(model(x[i:i + 64])["recon"].numpy())
    return np.concatenate(out) * sd


def var_explained(g, r):
    """1 - var(recon - gesture) / var(gesture) per joint, pooled over all rows of the windows, degrees, unweighted"""
    gf, e = g.reshape(-1, 5), (r - g).reshape(-1, 5)
    return (1 - e.var(0) / gf.var(0)).tolist()


def main():
    torch.set_num_threads(8)
    OUT.mkdir(parents=True, exist_ok=True)
    sd = DD.scale()
    model = TR.make(1024)
    model.load_state_dict(torch.load(DD.OUT / "k1024" / "best.pt"))
    model.eval()
    res = dict(variance_explained={}, amplitude={}, weight_share={})
    for split in ("validation", "test"):
        d = DD.load(split)
        r = recon(model, d["g"], sd)
        for s, n in NAMES.items():
            m = d["src"] == s
            res["variance_explained"][f"{split}|{n}"] = var_explained(d["g"][m], r[m])
    tr = DD.load("train")
    for s, n in NAMES.items():
        g = tr["g"][tr["src"] == s].reshape(-1, 5)
        res["amplitude"][n] = dict(rms=np.sqrt((g ** 2).mean(0)).tolist(), p5=np.percentile(g, 5, 0).tolist(), p95=np.percentile(g, 95, 0).tolist(), p5_p95_range=(np.percentile(g, 95, 0) - np.percentile(g, 5, 0)).tolist())
    for split in ("train", "validation", "test"):
        d = tr if split == "train" else DD.load(split)
        tot = float((d["w"] * 40).sum())
        res["weight_share"][split] = {n: float((d["w"][d["src"] == s] * 40).sum() / tot) for s, n in NAMES.items()}
    a, f = np.array(res["amplitude"]["aioz"]["rms"]), np.array(res["amplitude"]["finedance"]["rms"])
    ratio = a / f
    n_low = int((ratio < 0.70).sum())
    res["rule_7_61_3"] = dict(aioz_over_finedance_rms=ratio.tolist(), joints_below_70_percent=n_low, applies=bool(n_low >= 3))
    (OUT / "step1.json").write_text(json.dumps(res, indent=1))
    L = ["# T1a retrain, Step 1 (work order 39, BRAIN_SPEC 7.61.2-3; report only, numbers only)", "",
         "Round-1 K = 1024 model (`t1a/k1024/best.pt`), T0 data. Variance explained = 1 - var(recon - gesture) / var(gesture) per joint, pooled over all rows of the split's kept windows, degrees, unweighted.", "",
         "## Variance explained per joint", "", "| split | dataset | " + " | ".join(JN) + " |", "|---|---|" + "---|" * 5]
    for k, v in res["variance_explained"].items():
        L.append("| " + k.replace("|", " | ") + " | " + " | ".join(f"{x:.3f}" for x in v) + " |")
    L += ["", "## Gesture amplitude, train split (deg): FineDance vs kept AIOZ", "", "| dataset | stat | " + " | ".join(JN) + " |", "|---|---|" + "---|" * 5]
    for n in ("finedance", "aioz"):
        for st in ("rms", "p5", "p95", "p5_p95_range"):
            L.append(f"| {n} | {st} | " + " | ".join(f"{x:.2f}" for x in res["amplitude"][n][st]) + " |")
    L += ["| ratio | AIOZ rms / FineDance rms | " + " | ".join(f"{x:.2f}" for x in ratio) + " |", "", "## Effective weight share (sum of npz weight x chunks per dataset / total)", "", "| split | FineDance | AIOZ |", "|---|---|---|"]
    for k, v in res["weight_share"].items():
        L.append(f"| {k} | {v['finedance']:.3f} | {v['aioz']:.3f} |")
    L += ["", "## Rule 7.61.3 (kept-AIOZ gesture RMS below 70 % of FineDance's on 3 or more joints -> AIOZ capped at 50 % of total training weight)", "",
          f"Joints below 70 %: {n_low} of 5 ({', '.join(j for j, x in zip(JN, ratio) if x < 0.70) or 'none'}). **The rule {'APPLIES' if res['rule_7_61_3']['applies'] else 'does NOT apply'}.**"]
    (HERE.parents[1] / "docs" / "T1A2_STEP1.md").write_text("\n".join(L) + "\n")
    print(json.dumps(res["rule_7_61_3"]), res["weight_share"]["train"])


if __name__ == "__main__":
    main()
