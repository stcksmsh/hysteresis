"""WO47 V3 extras (docs/BEATV_RULES.md section 2): mean cross-correlation curve over files for raw FineDance (k = -30..30 frames) and the realised stage (lamp speed and summed |joint velocity|, V1/V2,
onset envelope at 50 Hz, k = -50..50 samples) with per-file best offsets -> beatv/v3.json. Brain env. Errors per file logged to beatv/v3_failed.txt."""
import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import beatv_lib as BL  # noqa: E402

B = Path("/secondary/hyst-data/body")
OUT = B / "beatv"
FD = Path("/secondary/hyst-data/datasets/finedance/data/finedance")


def one(n):
    try:
        import librosa
        y, sr = librosa.load(str(FD / "music_wav" / f"{n}.wav"), sr=22050)
        res = dict(n=n)
        rng = np.random.default_rng(47103 + int(n))
        m = np.load(FD / "motion" / f"{n}.npy").astype(float)
        e30 = librosa.onset.onset_strength(y=y, sr=sr, hop_length=735)
        en = BL.angle_speed(BL.local_rots(m), 30).sum(1)
        M = min(len(en), len(e30))
        k, c, z, p95, cc = BL.sync_scan(en[:M], e30[:M], 30, rng)
        res["raw"] = dict(k=k, cmax=c, z=z, p95=p95, c=cc.tolist())
        e50 = librosa.onset.onset_strength(y=y, sr=sr, hop_length=441)
        for var in ("V1", "V2"):
            p = B / "metric/q50/finedance" / f"fd_{n}__{var}.npz"
            if not p.exists():
                continue
            z_ = np.load(p)
            q, lamp = z_["q50"].astype(float), z_["lamp"].astype(float)
            lsp = np.linalg.norm(np.gradient(lamp, axis=0) * 50, axis=1)
            jsp = np.abs(np.gradient(q, axis=0) * 50).sum(1)
            for nm, a in (("lamp", lsp), ("joints", jsp)):
                M = min(len(a), len(e50))
                k, c, zz, p95, cc = BL.sync_scan(a[:M], e50[:M], 50, rng, min_shift_frames=250)
                res[f"{var}_{nm}"] = dict(k=k, cmax=c, z=zz, p95=p95, c=cc.tolist())
        return n, res
    except Exception as e:
        with open(OUT / "v3_failed.txt", "a") as f:
            f.write(f"{n} {type(e).__name__}: {e}\n")
        return n, None


def main(procs=6):
    ns = sorted(p.stem for p in (FD / "motion").glob("*.npy") if (B / "t1b/cortex/beats" / f"fd_{p.stem}.json").exists())
    out = {}
    with mp.get_context("spawn").Pool(procs) as pool:
        for i, (n, r) in enumerate(pool.imap_unordered(one, ns)):
            if r is not None:
                out[n] = r
            if i % 20 == 0:
                print(i, "/", len(ns), flush=True)
    (OUT / "v3.json").write_text(json.dumps(out))
    print("V3 DONE", len(out), flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
