"""Numeric check of the flash2 material + markdown table. Brain env.   pulse_flash2_check.py
Every clip 30 s with an audio stream; flash count equals the event count in the window."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pulse_flash2 as P  # noqa: E402

D = P.OUT
key = json.loads((D / "key.json").read_text())["items"]
bad = 0
for cid, k in key.items():
    st = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json", str(D / f"{cid}.mp4")],
                                   capture_output=True, text=True).stdout)["streams"]
    d = {s["codec_type"]: float(s["duration"]) for s in st}
    _, ev, lib, _ = P.load(k["song"])
    e = ev if k["source"] == "pulse" else lib
    n = int(((e >= k["start_s"]) & (e < k["start_s"] + 30)).sum())
    ok = abs(d.get("video", 0) - 30) < 0.05 and abs(d.get("audio", 0) - 30) < 0.1 and n == k["n_flashes"]
    bad += not ok
    if not ok:
        print("BAD", cid, d, n, k)
print("items", len(key), "bad", bad)
print("| song | role | dataset | whole ratio (level) | excerpt start s | excerpt ratio (level) | pulse flashes | librosa flashes |")
print("|---|---|---|---|---|---|---|---|")
for s in json.loads((D / "selection.json").read_text()):
    fl = {v["source"]: v["n_flashes"] for v in key.values() if v["song"] == s["song"]}
    print(f"| {s['song']} | {s['role']} | {s['dataset']} | {s['whole_ratio']:.3f} ({s['whole_level']}) | {s['start']:.0f} | {s['ratio']:.3f} ({s['level']}) | {fl['pulse']} | {fl['lib']} |")
