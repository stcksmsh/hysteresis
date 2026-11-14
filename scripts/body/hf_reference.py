"""WO13A steps 2-3: (e) of the v47 Off hexagon (six arms per danced song), and, report only, K5 try 1 and the fallback. Body env.

    hf_reference.py v47        reads /secondary/hyst-data/body/hf/v47/<song>-arm<N>.csv -> v47_reference.json (+ the copy docs/hf_v47_reference.json via --docs)
    hf_reference.py report     K5 try 1 CSVs (and the fallback's, if hf/fallback/<song>.csv exist) -> report.json
(e) = hf_share.hf_share. Per-song value = mean over the six arms (all six kept); reference = mean of the three per-song values; limit = 1.25 x each value.
"""
import json
import sys
from pathlib import Path

import numpy as np

import hf_share as H

HF = Path("/secondary/hyst-data/body/hf")
K5 = Path("/secondary/hyst-data/body/k5/danced")
SONGS = ("instant-crush", "five-years", "presence")


def v47_reference(hf=HF):
    songs = {}
    for s in SONGS:
        arms = [H.hf_share_csv(hf / "v47" / f"{s}-arm{n}.csv") for n in range(6)]
        songs[s] = {"arms": arms, "mean": float(np.mean(arms)), "limit_1.25x": 1.25 * float(np.mean(arms))}
    ref = float(np.mean([v["mean"] for v in songs.values()]))
    return {"definition": "hf_share.hf_share: joint velocity (central difference of the 50 Hz CSV), Welch 4 s Hann 50 % overlap mean removed, power above 3 Hz / power above 0 Hz summed over base_yaw, shoulder, elbow, wrist_bend",
            "source": "v47 Off hexagon score of each danced song (ensemble_preview --ring 6,0.8 --score), hyst score-csv --mode off --agent 0..5, 50 Hz",
            "songs": songs, "reference_mean_of_song_means": ref, "limit_1.25x": 1.25 * ref}


def report(hf=HF):
    res = {"definition": "same as v47_reference.json", "k5_try1": {}, "fallback": {}}
    for s in SONGS:
        res["k5_try1"][s] = H.hf_share_csv(K5 / f"{s}.k5.csv")
        f = hf / "fallback" / f"{s}.csv"
        if f.exists():
            res["fallback"][s] = H.hf_share_csv(f)
    for k in ("k5_try1", "fallback"):
        if res[k]:
            res[k]["mean"] = float(np.mean([v for n, v in res[k].items() if n in SONGS]))
    return res


if __name__ == "__main__":
    HF.mkdir(parents=True, exist_ok=True)
    if sys.argv[1] == "v47":
        r = v47_reference()
        (HF / "v47_reference.json").write_text(json.dumps(r, indent=1))
        if "--docs" in sys.argv:
            (Path(__file__).resolve().parents[2] / "docs" / "hf_v47_reference.json").write_text(json.dumps(r, indent=1))
    else:
        r = report()
        (HF / "report.json").write_text(json.dumps(r, indent=1))
    print(json.dumps(r, indent=1))
