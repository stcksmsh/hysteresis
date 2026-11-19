"""WO12 step 1: the three danced songs' B7 lanes in exactly the K5 format. Brain env (/secondary/hyst-env/brain). Provisional servo model. One arm.

    k5_video_lanes.py export [--out DIR] [--threads N]    DIR/<song>.npz, default /secondary/hyst-data/body/k5/danced/lanes (existing files are kept)
    k5_video_lanes.py check  [SONG_ID]                     re-derive one check-split song's lanes through the export path and compare with the stored file

The export uses k5_data.song_lanes unchanged (same model, same chunking, same keys: frames, y, phi_end, omega, s10, arousal_b7, power10). Only the way x is built differs:
a danced song comes from braindump.danced_inputs(name); a check-split song (the test) from its corpus feature and grid files, exactly as k5_data.cmd_lanes does.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE))
import k5_data as D  # noqa: E402

SONGS = ("instant-crush", "five-years", "presence")
OUT = D.OUT / "danced" / "lanes"


def load_model():
    import braindump as bd
    import train_b7
    model, _ = train_b7.load_model7(bd.CKPT)
    return model


def corpus_inputs(sid):
    """x for a corpus song, as k5_data.cmd_lanes builds it."""
    import b2
    import braindump as bd
    mean, std = bd.stats()
    feats = np.load(D.CORPUS / "features" / f"{sid}.npy").astype(np.float32)
    return b2.build_inputs(feats, json.loads((D.CORPUS / "grids" / f"{sid}.json").read_text())["beats"], mean, std)


def lanes_of(model, x):
    z = D.song_lanes(model, x)
    return {"frames": len(x), **z}


def save(path, z):
    tmp = Path(str(path) + ".tmp.npz")
    np.savez_compressed(tmp, **z)
    tmp.replace(path)


def cmd_export(out, threads):
    import torch
    import braindump as bd
    torch.set_num_threads(threads)
    out.mkdir(parents=True, exist_ok=True)
    model = load_model()
    for name in SONGS:
        p = out / f"{name}.npz"
        if p.exists():
            print(name, "exists, kept", flush=True)
            continue
        x = bd.danced_inputs(name)
        save(p, lanes_of(model, x))
        z = np.load(p)
        print(name, f"{len(x) / 100:.1f} s", "blocks", z["y"].shape[0], flush=True)


def compare(a, b):
    """-> (keys equal, max abs difference over all arrays, bit-identical)"""
    ka, kb = sorted(a), sorted(b)
    assert ka == kb, (ka, kb)
    d = max(float(np.max(np.abs(np.asarray(a[k], float) - np.asarray(b[k], float)))) if np.size(a[k]) else 0.0 for k in ka)
    same = all(np.array_equal(a[k], b[k], equal_nan=True) for k in ka)
    return ka, d, same


def cmd_check(sid, threads):
    import torch
    torch.set_num_threads(threads)
    if sid is None:
        sid = sorted(p.stem for p in (D.OUT / "lanes" / "check").glob("*.npz"))[0]
    stored = np.load(D.OUT / "lanes" / "check" / f"{sid}.npz")
    mine = lanes_of(load_model(), corpus_inputs(sid))
    keys, d, same = compare({k: stored[k] for k in stored.files}, {k: np.asarray(v) for k, v in mine.items()})
    print(json.dumps({"song": sid, "keys": keys, "max_abs_diff": d, "bit_identical": same}))
    return 0 if same or d == 0 else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=("export", "check"))
    ap.add_argument("song", nargs="?")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--threads", type=int, default=6)
    a = ap.parse_args()
    if a.what == "export":
        cmd_export(Path(a.out), a.threads)
    else:
        sys.exit(cmd_check(a.song, a.threads))


if __name__ == "__main__":
    main()
