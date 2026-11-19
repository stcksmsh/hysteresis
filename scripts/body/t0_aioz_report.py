"""WO37B: docs/T0_AIOZ_CHECK.md from aioz_measures.json (+ contact sheet of 3 dropped, 3 kept; looked at, never used to change a rule). Body env.
python -u t0_aioz_report.py OUT.md"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t0_aioz as A  # noqa: E402

D = json.loads((A.OUT / "aioz_measures.json").read_text())
rows = D["rows"]
ref = json.loads((A.OUT / "aioz_ref.json").read_text())
N = len(rows)


def hours(rs):
    return sum(r["frames"] / r["fps_derived"] for r in rs) / 3600


L = []
for key, name in (("drop", "literal rule (binding)"), ("drop_cal", "calibrated variant (FOR USER)")):
    kept = [r for r in rows if not r.get(key, ["fps"])]
    c = Counter(k for r in rows for k in r.get(key, ["fps"]))
    L += [f"## {name}", "", f"Kept {len(kept)} of {N} person-sequences ({len(kept) / N:.1%}), {hours(kept):.2f} h of {hours(rows):.2f} h. 30 % rule: "
          + ("**HOLD aioz %.1f %%**" % (100 * len(kept) / N) if len(kept) / N < 0.3 else "passes."), "",
          "Drops per reason (a person can have several): " + ", ".join(f"{k} {v}" for k, v in c.most_common()), "", "| style | persons | kept | share |", "|---|---|---|---|"]
    for s in sorted({r["style"] for r in rows}):
        rs = [r for r in rows if r["style"] == s]
        k = sum(1 for r in rs if not r.get(key, ["fps"]))
        L.append(f"| {s} | {len(rs)} | {k} | {k / len(rs):.1%} |")
    L.append("")
m = [r for r in rows if "p3_wrist" in r]


def q(k):
    return np.percentile([r[k] for r in m], [5, 50, 95]).round(4).tolist()


L += ["## Distributions vs FineDance (AIOZ p5 / median / p95)", "",
      f"- wrist power > 3 Hz: {q('p3_wrist')} (FineDance median {ref['p3_wrist_median']:.3f}, p95 {ref['p3_wrist_p95']:.3f})",
      f"- head power > 3 Hz: {q('p3_head')} (FineDance median {ref['p3_head_median']:.3f}, p95 {ref['p3_head_p95']:.3f})",
      f"- share of frames over a joint p99.9: {q('share_ang_over')} (FineDance median {ref['fd_share_any_joint_over_p999_median']:.4f}, p95 {ref['fd_share_joint_p95']:.4f})",
      f"- share of frames over root p99.9: {q('share_root_over')} (FineDance p95 {ref['fd_share_root_p95']:.4f})",
      f"- frozen share: {q('share_frozen')}", f"- mean head height (m): {q('mean_head_height')}; vertical drift (m/s): {q('head_height_drift_m_per_s')}",
      f"- derived fps: mode {D['mode_fps']}; sequences off the mode by more than 2 % (dropped): {sum(1 for r in rows if r['drop'] == ['fps'])}", "",
      "Lamp-path power above 3 Hz after the low-pass: not computed here (AIOZ is not retargeted by this builder; A does it).", "",
      "Contact sheet `contact_sheet.png` (in `t0/`, outside git): 3 dropped (top row), 3 kept (bottom row), frame at 10 s."]
Path(sys.argv[1]).write_text("\n".join(L) + "\n")

rng = np.random.default_rng(1)
groups = [("drop", [r for r in m if r["drop"]]), ("keep", [r for r in m if not r["drop"]] or [r for r in m if not r["drop_cal"]])]
sheet = []
for tag, pool in groups:
    for idx in rng.choice(len(pool), 3, replace=False):
        r = pool[idx]
        d = A.load_pkl(A.AIOZ / "motions_smpl" / f"{r['id']}.pkl")
        k = min(int(10 * r["fps_derived"]), r["frames"] - 1)
        P = A.fk_mats(A.aa_to_mats(d["smpl_poses"][r["person"]][k:k + 1]), d["root_trans"][r["person"]][k:k + 1])[0]
        sheet.append(dict(title=f"{tag} {r['id'][:6]}/{r['person']} {','.join(r['drop']) or 'cal-kept'}", P=P.tolist()))
(A.OUT / "contact_sheet.json").write_text(json.dumps(dict(parent=A.L.PARENT.tolist() if hasattr(A.L.PARENT, "tolist") else list(A.L.PARENT), sheet=sheet)))
