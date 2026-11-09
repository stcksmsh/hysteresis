"""Stage 3 tempo and RMS for every song (work order 26A; docs/STAGE3_RULES_DATA_EVAL.md section 2). Brain env.

    s3_tempo_rms.py [--workers 6]      /secondary/hyst-data/body/s3/tempo_rms.json  {id: {"bpm", "log_rms"}}; per-song cache in s3/tempo_rms_cache/ (resume-safe)
bpm = s0_tempo.librosa_bpm exactly; log_rms = log(sqrt(mean(y^2))) of the whole song (mono, 22,050 Hz). The bpm of the check songs is taken from s0/tempo.json when its route is librosa and 5 recomputed songs agree.
"""
import argparse
import json
import math
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s0_tempo as S0  # noqa: E402

K5 = Path("/secondary/hyst-data/body/k5")
S3 = Path("/secondary/hyst-data/body/s3")
CACHE = S3 / "tempo_rms_cache"


def one(args):
    sid, use_bpm = args
    f = CACHE / f"{sid}.json"
    if f.exists():
        return sid, json.loads(f.read_text())
    import librosa
    y, sr = librosa.load(S0.AUDIO / f"{sid}.mp3", sr=22050, mono=True)
    r = {"log_rms": float(math.log(max(float(np.sqrt(np.mean(y.astype(np.float64) ** 2))), 1e-12)))}
    if use_bpm is None:
        t, _ = librosa.beat.beat_track(y=y, sr=sr)
        r["bpm"] = float(np.atleast_1d(t)[0])
    else:
        r["bpm"] = use_bpm
    f.write_text(json.dumps(r))
    return sid, r


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    sp = json.loads((K5 / "splits.json").read_text())
    ids = [s for k in ("check", "train", "val") for s in sp[k]["ids"]]
    tj = json.loads((Path("/secondary/hyst-data/body/s0/tempo.json")).read_text())
    reuse = {}
    if tj["route"] == "librosa":
        chk = sp["check"]["ids"][:5]
        ok = all(abs(S0.librosa_bpm(s) - tj["tempo"][s]) < 1e-6 for s in chk)
        print("s0/tempo.json reuse check on 5 songs:", ok, flush=True)
        if ok:
            reuse = {s: tj["tempo"][s] for s in sp["check"]["ids"]}
    with Pool(a.workers) as p:
        res = {}
        for i, (sid, r) in enumerate(p.imap_unordered(one, [(s, reuse.get(s)) for s in ids], chunksize=4)):
            res[sid] = r
            if i % 100 == 0:
                print(i, len(ids), flush=True)
    out = {s: res[s] for s in ids}
    (S3 / "tempo_rms.json").write_text(json.dumps(out))
    print("done", len(out), "songs; bpm median", float(np.median([v["bpm"] for v in out.values()])))


if __name__ == "__main__":
    main()
