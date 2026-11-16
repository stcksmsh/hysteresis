"""WO46 part 2 step 4 (docs/METRIC_RULES.md section 7): by-ear spot check material, prepared only. Brain env.   metric_spotcheck.py
10 songs (seed 46108; FineDance 3, AIOZ 2, PhantomDance 3, Motorica 2; audio >= 90 s where available), music-side ear-feature novelty boundaries at the 8 s scale (half-width 16 tokens),
at most 6 strongest per song, excerpts +-8 s around each -> metric/spotcheck/<song>/b<time>.wav + manifest.json. Not served."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))
import controls_stats as CS  # noqa: E402
import metric_run as R  # noqa: E402

B = Path("/secondary/hyst-data/body")
OUT = B / "metric" / "spotcheck"
LISTS = {"finedance": B / "t0/lanes_list_fd.json", "aioz": B / "t0/lanes_list_aioz.json", "phantom": B / "t0_phantom/lanes_list.json", "motorica": B / "t0_motorica/lanes_list.json"}
NPER = {"finedance": 3, "aioz": 2, "phantom": 3, "motorica": 2}
HALF = 16


def main():
    rng = np.random.default_rng(46108)
    man = []
    for ds, n in NPER.items():
        items = [it for it in json.loads(LISTS[ds].read_text()) if (CS.LANES[ds] / f"{it['key']}.npz").exists()]
        info = []
        for it in items:
            T = int(np.load(CS.LANES[ds] / f"{it['key']}.npz")["n_frames"])
            info.append((it, T / 100.0))
        long = [x for x in info if x[1] >= 90] or sorted(info, key=lambda x: -x[1])[:max(n, 5)]
        pick = rng.choice(len(long), min(n, len(long)), replace=False)
        for i in sorted(pick):
            it, dur = long[i]
            lk = it["key"]
            F = R.music_feat(ds, lk, False)
            nv, pk = R.peaks_of(F, HALF)
            pk = sorted(pk, key=lambda t: -nv[t])[:6]
            d = OUT / lk
            d.mkdir(parents=True, exist_ok=True)
            ex = []
            for k in sorted(pk):
                t = k * 0.5
                a = max(t - 8, 0.0)
                f = d / f"boundary_{t:07.1f}s.wav"
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{a:.2f}", "-t", f"{t + 8 - a:.2f}", "-i", it["wav"], "-ac", "1", str(f)], check=True)
                ex.append(dict(boundary_s=t, strength=float(nv[k]), excerpt=str(f.relative_to(OUT)), excerpt_from_s=a, excerpt_to_s=t + 8))
            man.append(dict(song=lk, dataset=ds, duration_s=dur, wav=it["wav"], boundaries=ex, local_only=(ds == "motorica")))
            print(lk, ds, f"{dur:.0f}s", [e["boundary_s"] for e in ex], flush=True)
    (OUT / "manifest.json").write_text(json.dumps(dict(seed=46108, scale="ear-feature novelty, half-width 16 tokens (8 s)", note="boundaries are music-side estimates, not ground truth; Motorica excerpts stay on this laptop", songs=man), indent=1))
    print("SPOTCHECK READY", len(man), "songs")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    main()
