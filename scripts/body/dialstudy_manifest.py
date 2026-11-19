"""WO28A: build clips/manifest.json from the gated work dir and the rendered mp4s; copy CSV + dial values next to each video.
    python dialstudy_manifest.py        # reads work/<id>.json, clips/<id>.mp4
Only clips whose gates passed AND whose mp4 exists are listed."""
import json
import shutil
from pathlib import Path

D = Path("/secondary/hyst-data/body/dialstudy")
W, C = D / "work", D / "clips"
FIVE = ("vigour", "stiffness", "roundness", "lag", "posture")
out = []
for j in sorted(W.glob("*.json")):
    r = json.loads(j.read_text())
    mp4 = C / f"{r['id']}.mp4"
    if not (r["gates"]["passed"] and mp4.exists()):
        continue
    shutil.copy(W / f"{r['id']}.csv", C / f"{r['id']}.csv")
    (C / f"{r['id']}.dials.json").write_text(json.dumps(r["dials"], indent=1))
    out.append(dict(id=r["id"], set=r["set"], file=mp4.name, csv=f"{r['id']}.csv", effector=r.get("effector", "ball"), intent=r["intent"],
                    dials={k: r["dials"][k] for k in FIVE},
                    gates=dict(passed=True, values=r["gates"]["values"], thresholds=r["gates"]["thresholds"])))
(C / "manifest.json").write_text(json.dumps(out, indent=1))
print(len(out), "clips in manifest")
