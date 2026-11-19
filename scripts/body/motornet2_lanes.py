"""WO30B step 2 (brain env): per song the B7 L4 state and arousal_b7 at 10 Hz, same model, chunking and frame choice as k5_data.song_lanes.

    motornet2_lanes.py          writes OUT/<song>.npz: l4 (nb10, 512) float32 = [real, imag] of L4's complex state at frames 9::10, arousal_b7 (nb10,),
                                and checks arousal_b7 against the stored round-1 lanes (danced: k5 danced lanes; check songs: motornet_toy/work3 lanes).
Songs: the 3 danced songs and the 5 check songs (beats and wav from WO29C's work3/). Audio stays outside git.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
OUT = Path("/secondary/hyst-data/body/motornet_toy2/lanes")
W3 = Path("/secondary/hyst-data/body/motornet_toy/work3")
DANCED = ("instant-crush", "five-years", "presence")
CHECK = ("blue-lagoon", "schizoid-man", "epitaph", "breathe", "one-of-these-days")
CHUNK = 6000


def l4_lanes(model, x):
    import torch
    st = model.init_state(1)
    h4, ar = [], []
    with torch.no_grad():
        for a in range(0, len(x), CHUNK):
            out, st = model(torch.from_numpy(x[a:a + CHUNK])[None], st)
            h = out[3]["h"][0]
            h4.append(torch.cat([h.real, h.imag], -1).numpy())
            ar.append(out[0]["arousal"][0].numpy())
    h4, ar = np.concatenate(h4), np.concatenate(ar)
    nb10 = len(x) // 10
    return h4[9:nb10 * 10:10].astype(np.float32), ar[9:nb10 * 10:10].astype(np.float32)


def main():
    import torch
    torch.set_num_threads(6)
    import b2
    import braindump as bd
    import fast_features as ff
    import k5_video_lanes as V
    OUT.mkdir(parents=True, exist_ok=True)
    model = V.load_model()
    mean, std = bd.stats()
    for name in DANCED + CHECK:
        p = OUT / f"{name}.npz"
        if p.exists():
            print(name, "exists, kept", flush=True)
            continue
        if name in DANCED:
            x = bd.danced_inputs(name)
            ref = np.load(f"/secondary/hyst-data/body/k5/danced/lanes/{name}.npz")["arousal_b7"]
        else:
            x = b2.build_inputs(ff.fast_features(ff.load_mono(str(W3 / "wav" / f"{name}.wav"))), json.loads((W3 / f"{name}.beats.json").read_text())["beats"], mean, std)
            ref = np.load(W3 / f"{name}.lanes.npz")["arousal_b7"]
        l4, ar = l4_lanes(model, x)
        same = bool(np.array_equal(ar, ref))
        d = float(np.abs(ar - ref).max())
        np.savez_compressed(p, l4=l4, arousal_b7=ar)
        print(name, f"{len(x) / 100:.1f} s", "l4", l4.shape, "arousal equals stored lanes:", same, "max diff", d, flush=True)


if __name__ == "__main__":
    main()
