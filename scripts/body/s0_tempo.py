"""WO19 Stage 0: tempo per held-out song (BRAIN_SPEC 7.34 operationalisation). Brain env.
omega route: median of the B7 lane's `omega` (rad/s) -> BPM = omega * 60 / 2 pi. Sanity check on 20 songs against librosa.beat.beat_track on the mp3: BPMs agree if within 5 % after allowing a factor
2 or 1/2; if they disagree on more than 4 of the 20, librosa is used for all songs (logged as a deviation). Writes tempo.json (both tempi per song, the route used, the sanity numbers).
    s0_tempo.py --out DIR [--n-check 20]
"""
import argparse
import json
from pathlib import Path

import numpy as np

K5 = Path("/secondary/hyst-data/body/k5")
AUDIO = Path("/secondary/hyst-data/brain/corpus/audio")


def omega_bpm(song):
    z = np.load(K5 / "lanes" / "check" / f"{song}.npz")
    return float(np.median(z["omega"]) * 60.0 / (2 * np.pi))


def librosa_bpm(song):
    import librosa
    y, sr = librosa.load(AUDIO / f"{song}.mp3", sr=22050, mono=True)
    t, _ = librosa.beat.beat_track(y=y, sr=sr)
    return float(np.atleast_1d(t)[0])


def agree(a, b, tol=0.05):
    return any(abs(a * f - b) <= tol * b for f in (1.0, 2.0, 0.5))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/secondary/hyst-data/body/s0")
    ap.add_argument("--n-check", type=int, default=20)
    a = ap.parse_args()
    ids = json.loads((K5 / "splits.json").read_text())["check"]["ids"]
    rng = np.random.default_rng(0)
    sub = [ids[i] for i in sorted(rng.choice(len(ids), a.n_check, replace=False))]
    ob = {s: omega_bpm(s) for s in ids}
    lb = {s: librosa_bpm(s) for s in sub}
    dis = [s for s in sub if not agree(ob[s], lb[s])]
    use = "omega" if len(dis) <= 4 else "librosa"
    if use == "librosa":
        for s in ids:
            if s not in lb:
                lb[s] = librosa_bpm(s)
    res = {"route": use, "sanity_songs": sub, "disagree": dis, "n_disagree": len(dis), "omega_bpm": ob, "librosa_bpm": lb,
           "tempo": {s: (ob[s] if use == "omega" else lb[s]) for s in ids}}
    Path(a.out, "tempo.json").write_text(json.dumps(res))
    print(f"route {use}; {len(dis)} of {len(sub)} disagree; omega-bpm median {np.median(list(ob.values())):.2f}; sanity pairs:", [(round(ob[s], 1), round(lb[s], 1)) for s in sub[:8]])


if __name__ == "__main__":
    main()
