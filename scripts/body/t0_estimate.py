"""WO37 step 4 (body env): time the full chain (4 copies, all windows gated) on the longest FineDance sequence; project the FineDance total. python -u t0_estimate.py"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t0_chain as C  # noqa: E402
import t0_lib as T  # noqa: E402

OUT = Path("/secondary/hyst-data/body/t0")
FD = Path("/secondary/hyst-data/datasets/finedance/data/finedance")


def main():
    cat = json.loads((OUT / "catalogue_fd.json").read_text())
    c = max(cat, key=lambda x: x["t30"])
    rot, trans = T.load_rot(FD / "motion" / f"{c['seq']}.npy")
    mrot, _ = T.mirror(rot, trans)
    t0 = time.time()
    per, nwin = {}, 0
    for copy in C.COPIES:
        t1 = time.time()
        r = C.process(mrot if copy.endswith("m") else rot, trans, copy)
        per[copy] = dict(seconds=time.time() - t1, windows=r["n_win"], passed=int(r["win_pass"].sum()))
        nwin += r["n_win"]
    sec = time.time() - t0
    total_win = sum(T.n_windows(x["t30"]) for x in cat)
    proj = sec / nwin * total_win * 4 / 8                                  # 8 processes, same per-window cost (single process measured)
    res = dict(seq=c["seq"], frames=c["t30"], windows_per_copy=nwin // 4, seconds=sec, seconds_per_window=sec / nwin, finedance_windows_per_copy=total_win,
               projected_finedance_hours_8_procs=proj / 3600, per_copy=per)
    (OUT / "estimate.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res))


if __name__ == "__main__":
    main()
