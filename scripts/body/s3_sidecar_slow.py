"""Slow-stream lanes (13 columns) of Instant Crush for the round-400 clip (docs/STAGE3_SIDECAR_RULES.md section 3). Brain env (/secondary/hyst-env/brain), cores 12-17 by the caller.

    s3_sidecar_slow.py --out FILE.npz
The danced song's core input `braindump.danced_inputs("instant-crush")` through `s3_slow.l4_blocks`, then the columns exactly as `s3_slow.raw_columns` + `s3_slow.load_norm` (corpus PCA and
column normalisation), with the song's own lanes (`k5/danced/lanes/instant-crush.npz`: surprisal lane s10[:, 4], y[:, 4:8]). Nothing is edited; the output is a new file.
"""
import argparse
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
import s3_slow as S  # noqa: E402

LANES = Path("/secondary/hyst-data/body/k5/danced/lanes/instant-crush.npz")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--threads", type=int, default=6)
    a = ap.parse_args()
    import torch
    import braindump as bd
    import train_b7
    torch.set_num_threads(a.threads)
    model, _ = train_b7.load_model7(bd.CKPT)
    x = bd.danced_inputs("instant-crush")
    raw = S.l4_blocks(model, x).astype(np.float64)
    z = np.load(LANES)
    nb = len(z["y"])
    assert len(raw) == nb, (len(raw), nb)
    comp, mu, cm, csd = S.load_norm()
    cols = np.concatenate([(raw - mu) @ comp.T, S.surprisal_integral(z["s10"][:, 4], nb)[:, None], np.asarray(z["y"][:, 4:8], np.float64)], 1)
    slow = ((cols - cm) / csd).astype(np.float32)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(out) + ".tmp.npz")
    np.savez_compressed(tmp, slow=slow)
    tmp.replace(out)
    print("slow", slow.shape, "mean", slow.mean(0).round(2).tolist(), "sd", slow.std(0).round(2).tolist(), flush=True)


if __name__ == "__main__":
    main()
