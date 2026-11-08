"""WO19 Stage 0, step 1: pass2 (k5p2 best.pkl, round 600) continuous full-song argmax rollout of the held-out check songs. Body env. Imports k5p2_eval; edits nothing.

    s0_roll.py --out DIR [--songs a,b,...] [--max-songs N] [--max-blocks N]
Same body, options and recipe as `k5p2_eval.py songs` (episode_inputs, pad_chunks, rollout_song, start seed 4242, chunk 8); lanes from k5/lanes/check. Per song DIR/<id>.npz:
rows50 (25 nb + 1, 5) joint angles deg at 50 Hz (row 0 = start pose), pi (nb, programs) per-block program probabilities, prog (nb,) argmax program, nb. The hand position is computed
in the measuring step (m3f_report.fk_points). Resume-safe (finished npz kept); SIGTERM stops after the current song.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

import k5p2_eval as EV
import k5_train as T
import k5_video_roll as VR

LANES = T.K5 / "lanes" / "check"


def check_songs():
    return json.loads((T.K5 / "splits.json").read_text())["check"]["ids"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--policy", default="/secondary/hyst-data/body/k5p2/run/best.pkl")
    ap.add_argument("--out", default="/secondary/hyst-data/body/s0/pass2")
    ap.add_argument("--lanes", default=str(LANES))
    ap.add_argument("--songs")
    ap.add_argument("--max-songs", type=int)
    ap.add_argument("--max-blocks", type=int, help="test only")
    a = ap.parse_args()
    T.install_signals()
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:7.0f}s] {s}", flush=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    songs = a.songs.split(",") if a.songs else check_songs()
    songs = songs[:a.max_songs] if a.max_songs else songs
    C = EV.M.load_cb()
    P, stats, cfg = EV.load_policy(a.policy)
    fns = EV.make_fns(C, cfg)
    done_t = []
    for i, name in enumerate(songs):
        T.check()
        T.wait_mains(log)
        f = out / f"{name}.npz"
        if f.exists():
            continue
        z = np.load(Path(a.lanes) / f"{name}.npz")
        inps, yz = EV.episode_inputs(z["y"], z["phi_end"], z["omega"])
        if a.max_blocks:
            inps = {k: v[:, :a.max_blocks] for k, v in inps.items()}
        padded, nb = EV.pad_chunks(inps, VR.CB)
        ts = time.time()
        r = EV.rollout_song(fns, cfg, C, P, padded)
        q = r["q"][:nb]
        rows = VR.csv_rows(q, r["q0"])
        pi = r["pi"][:nb]
        tmp = Path(str(f) + ".tmp.npz")
        np.savez_compressed(tmp, rows50=rows.astype(np.float32), pi=pi.astype(np.float32), prog=np.argmax(pi, -1), nb=nb)
        tmp.replace(f)
        done_t.append((time.time() - ts, nb))
        rate = sum(t for t, _ in done_t) / sum(n for _, n in done_t)
        left = sum(max(1, np.load(Path(a.lanes) / f"{s}.npz")["y"].shape[0]) for s in songs[i + 1:] if not (out / f"{s}.npz").exists())
        log(f"{i + 1}/{len(songs)} {name}: {nb} blocks in {done_t[-1][0]:.0f} s; projection for the rest ~{rate * left / 3600:.2f} h")


if __name__ == "__main__":
    try:
        main()
    except T.Interrupted:
        print("interrupted; rerun to resume", flush=True)
        sys.exit(0)
