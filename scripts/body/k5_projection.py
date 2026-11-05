"""K5 wall-time projection for one try on the laptop (work order 8, step 4). Inputs, all measured earlier and read from files:
 - M3d training cost per 60 s window: try 1's per-epoch wall seconds (hist[].secs, median of the epochs after the first, 8 threads) / 16 training episodes.
 - M3d evaluation cost per window and mode: (1,614 s total - 1,558 s training compute) / (16 held-out episodes x 2 modes), from the night log.
 - Window counts: windows.json. Brain-side lanes are precomputed (no B7 in the training loop), so no B7 cost enters; lane export time is reported separately.
Not included: M3e's closed loop (proprioception, cerebellum, critic, self-observer) will cost more than M3d per window; the multiplier is a parameter, 1.0 = M3d as is.
    k5_projection.py [--mult 1.0]  -> prints and writes /secondary/hyst-data/body/k5/projection.json
"""
import argparse
import json
import statistics
from pathlib import Path

K5 = Path("/secondary/hyst-data/body/k5")
TRY1 = Path("/secondary/hyst-data/body/m3d/try1/result.json")
EVAL_S_PER_WINDOW_MODE = (1614 - 1558) / (16 * 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mult", type=float, default=1.0)
    a = ap.parse_args()
    hist = json.loads(TRY1.read_text())["hist"]
    ep = statistics.median(h["secs"] for h in hist[1:])
    per_win = ep / 16
    w = json.loads((K5 / "windows.json").read_text())
    n_tr, n_ck = len(w["train"]), len(w["check"])
    songs = len({r[0] for r in w["train"]})
    res = {"inputs": {"m3d_epoch_s_median": ep, "windows_per_epoch": 16, "train_s_per_window": per_win, "eval_s_per_window_per_mode": EVAL_S_PER_WINDOW_MODE,
                      "train_windows_stride30": n_tr, "train_songs_with_a_window": songs, "check_windows": n_ck, "mult": a.mult},
           "passes": {}}
    # policy under test: 1 hard (argmax) rollout of the trained policy + 1 of the untrained one = 2 rollouts per check window; the shifted control needs no simulation
    check_h = 2 * n_ck * EVAL_S_PER_WINDOW_MODE * a.mult / 3600
    for name, n in (("one pass over all stride-30 windows", n_tr), ("one window per song (random start)", songs)):
        h = n * per_win * a.mult / 3600
        res["passes"][name] = {"windows": n, "train_h": h, "plus_check_h": h + check_h}
    res["check_h"] = check_h
    res["windows_in_8h_box"] = int((8 * 3600 - check_h * 3600) / (per_win * a.mult))
    res["passes_in_8h_box_stride30"] = res["windows_in_8h_box"] / n_tr
    (K5 / "projection.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
