"""WO46 part 2 step 1: beat grids (docs/METRIC_RULES.md section 1). Brain env.
    metric_grids.py check      analyze_mix on 10 FineDance songs (seeded) vs the stored grids -> metric/grids_check.json
    metric_grids.py run [P]    analyze_mix for AIOZ, PhantomDance, Motorica songs (P processes, resumable) -> metric/beats/<key>.json
"""
import json
import multiprocessing as mp
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))
B = Path("/secondary/hyst-data/body")
OUT = B / "metric"
LISTS = {"finedance": B / "t0/lanes_list_fd.json", "aioz": B / "t0/lanes_list_aioz.json", "phantom": B / "t0_phantom/lanes_list.json", "motorica": B / "t0_motorica/lanes_list.json"}
STORED = B / "t1b/cortex/beats"


def beats_of(wav):
    import b2
    from analyze.structure import analyze_mix
    from analyze.wav import DecodedWav
    with tempfile.TemporaryDirectory(dir="/secondary/hyst-data/body/metric") as d:
        m = Path(d) / "m.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-ar", "44100", str(m)], check=True)
        y = b2.load_mono(m)
        r = analyze_mix(DecodedWav(44100, [y], len(y) / 44100))
    return [float(b) for b in r["beats"]], float(len(y) / 44100)


def one(it):
    dst = OUT / "beats" / f"{it['key']}.json"
    if dst.exists():
        return it["key"], 0
    b, dur = beats_of(it["wav"])
    tmp = dst.with_suffix(".tmp")
    tmp.write_text(json.dumps(dict(beats=b, duration=dur, source="analyze_mix")))
    tmp.replace(dst)
    return it["key"], len(b)


def cmd_check():
    items = json.loads(LISTS["finedance"].read_text())
    items = [it for it in items if (STORED / f"{it['key']}.json").exists()]
    pick = np.random.default_rng(46002).choice(len(items), 10, replace=False)
    res = {}
    for i in sorted(pick):
        it = items[i]
        a = np.array(json.loads((STORED / f"{it['key']}.json").read_text())["beats"])
        b = np.array(beats_of(it["wav"])[0])
        d = None
        if len(a) == len(b):
            d = float(np.abs(a - b).max())
        else:                                                              # unequal counts: nearest-beat distances
            d = float(np.abs(a[:, None] - b[None]).min(1).max()) if len(b) else None
        res[it["key"]] = dict(n_stored=len(a), n_new=len(b), max_abs_diff_s=d)
        print(it["key"], res[it["key"]], flush=True)
    (OUT / "grids_check.json").write_text(json.dumps(res, indent=1))


def cmd_run(procs=6):
    (OUT / "beats").mkdir(parents=True, exist_ok=True)
    items = [it for ds in ("aioz", "phantom", "motorica") for it in json.loads(LISTS[ds].read_text())]
    with mp.get_context("spawn").Pool(procs) as pool:
        for i, (k, n) in enumerate(pool.imap_unordered(one, items)):
            if i % 25 == 0:
                print(i, "/", len(items), k, n, flush=True)
    print("GRIDS DONE", len(items), flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    {"check": cmd_check, "run": cmd_run}[a[0]](*[int(x) for x in a[1:]])
