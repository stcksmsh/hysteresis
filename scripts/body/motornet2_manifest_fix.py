"""WO30B manifest fix: clips/manifest.json in the session tool's format (Part A singles with `file`; Part B pairs with `files`), from manifest_perclip.json + numbers.json."""
import json
import shutil
from pathlib import Path

R = Path("/secondary/hyst-data/body/motornet_toy2")
C = R / "clips"
if not (C / "manifest_perclip.json").exists():
    shutil.copy(C / "manifest.json", C / "manifest_perclip.json")
pc = json.loads((C / "manifest_perclip.json").read_text())
num = json.loads((R / "numbers.json").read_text())
by = {x["id"]: x for x in pc}
pop2, pop1 = [0] * 100 + [1] * 100, [0] * 200
out = []
for i in range(1, 9):
    x = by[f"A_S{i:02d}"]
    out.append(dict(id=x["id"], part="A", file=x["files"][0], csv=x["csv"], activity=x["activity"], setting=x["setting"], population=pop2, gates=x["gates"]))
for k in range(1, 6):
    n, s = by[f"B{k}_new"], by[f"B{k}_s03"]
    sg = num["songs"][n["song"]]
    out.append(dict(id=f"B{k}", part="B", files=[n["files"][0], s["files"][0]], setting=[n["setting"], "R1_S03"], csv=[n["csv"], s["csv"]],
                    activity=[n["activity"], s["activity"]], population=[pop2, pop1], song=n["song"], excerpt_start_s=n["excerpt_start_s"],
                    ear_energy=sg["ear_energy_raw"], arousal_raw=sg["arousal_raw"], arousal_std=sg["arousal_input"],
                    hand_speed=[num["clips"][f"B{k}_new"]["hand_speed"], num["clips"][f"B{k}_s03"]["hand_speed"]], gates=[n["gates"], s["gates"]]))
(C / "manifest.json").write_text(json.dumps(out, indent=1))
print(len(out), [(o["id"], o["part"]) for o in out])
