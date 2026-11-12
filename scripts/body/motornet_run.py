"""WO29A driver. Body env. Rules: docs/MOTORNET_RULES.md.

    motornet_run.py sample      draw settings (seed 29011), simulate silent, gate, write work/<id>.{csv,json,activity.npy} + settings.json
    motornet_run.py manifest    copy files next to the rendered videos and write clips/manifest.json
(render: motornet_render.sh, music path test: motornet_music.py)
"""
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

import arm_sim
import dialstudy as D
import motornet as M

ROOT = Path("/secondary/hyst-data/body/motornet_toy")
W, C = ROOT / "work", ROOT / "clips"
SEED_DRAW, SEED_P4 = 29011, 29041
NKEEP, MAXDRAW = 10, 400
R1 = Path("/secondary/hyst-data/body/dialstudy")


def save(cid, q, r, g, effector, setting, vals):
    (W / f"{cid}.csv").write_text(arm_sim.csv_text(q, D.HZ, name=cid))
    np.save(W / f"{cid}.activity.npy", r)
    (W / f"{cid}.json").write_text(json.dumps(dict(id=cid, effector=effector, setting=setting, setting_values=vals, gates=g), indent=1))


def cmd_sample():
    W.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED_DRAW)
    lo, hi = np.log(M.C_LO), np.log(M.C_HI)
    settings, discards, kept, t0 = [], [], 0, time.time()
    for d in range(1, MAXDRAW + 1):
        c = np.exp(rng.uniform(lo, hi, M.NCTRL))
        q, r, g = M.run_setting(c)
        failed = [k for k, v in g["parts"].items() if not v]
        if not failed:
            kept += 1
            sid = f"S{kept:02d}"
            settings.append(dict(id=sid, values=[float(x) for x in c], draw_index=d))
            save(f"P1_{sid}", q, r, g, "lamp", sid, [float(x) for x in c])
            if kept <= 2:
                save(f"P2_{sid}_ball", q, r, g, "ball", sid, [float(x) for x in c])
        else:
            discards.append(dict(draw_index=d, values=[float(x) for x in c], failed=failed, extent_m=g["values"]["extent_m"]))
        print(f"draw {d:3d} {'keep ' + sid if not failed else 'DISCARD ' + ','.join(failed)}  {time.time() - t0:.0f}s", flush=True)
        if kept == NKEEP:
            break
    extremes = []
    for sid, v in (("S11", M.C_LO), ("S12", M.C_HI)):
        c = np.full(M.NCTRL, v)
        q, r, g = M.run_setting(c)
        failed = [k for k, x in g["parts"].items() if not x]
        extremes.append(dict(id=sid, values=[float(v)] * M.NCTRL, passed=not failed, failed=failed))
        if not failed:
            save(f"P1_{sid}", q, r, g, "lamp", sid, [float(v)] * M.NCTRL)
            settings.append(dict(id=sid, values=[float(v)] * M.NCTRL, draw_index=None))
        print(sid, "PASS" if not failed else f"FAIL {failed}", flush=True)
    per_gate = {}
    for x in discards:
        for k in x["failed"]:
            per_gate[k] = per_gate.get(k, 0) + 1
    out = dict(seed=SEED_DRAW, c_range=[M.C_LO, M.C_HI], draws=d, kept=kept, settings=settings, discards=discards, discards_per_gate=per_gate, extremes=extremes)
    (ROOT / "settings.json").write_text(json.dumps(out, indent=1))
    print("draws", d, "kept", kept, "discards", len(discards), per_gate)


def cmd_manifest():
    C.mkdir(parents=True, exist_ok=True)
    st = json.loads((ROOT / "settings.json").read_text())
    items = []
    for j in sorted(W.glob("P*.json")):
        r = json.loads(j.read_text())
        cid = r["id"]
        mp4 = C / f"{cid}.mp4"
        if not (r["gates"]["passed"] and mp4.exists()):
            continue
        for ext in (".csv", ".activity.npy"):
            shutil.copy(W / f"{cid}{ext}", C / f"{cid}{ext}")
        items.append(dict(id=cid, part=1 if cid.startswith("P1") else 2, file=mp4.name, csv=f"{cid}.csv", activity=f"{cid}.activity.npy", effector=r["effector"],
                          setting=r["setting"], setting_values=r["setting_values"], gates=dict(passed=True, values=r["gates"]["values"], thresholds=r["gates"]["thresholds"])))
    r1 = json.loads((R1 / "clips" / "manifest.json").read_text())
    ids = sorted(np.random.default_rng(SEED_P4).choice([c["id"] for c in r1], 4, replace=False).tolist())
    for cid in ids:
        c = next(x for x in r1 if x["id"] == cid)
        items.append(dict(id=f"P4_{cid}", part=4, file=str(R1 / "clips" / c["file"]), csv=str(R1 / "clips" / c["csv"]), round1_id=cid, effector=c["effector"],
                          gates=c["gates"], seed=SEED_P4))
    (C / "manifest.json").write_text(json.dumps(items, indent=1))
    print(len(items), "items;", "part 4:", ids)


if __name__ == "__main__":
    {"sample": cmd_sample, "manifest": cmd_manifest}[sys.argv[1]]()
