"""WO30B step 2 (brain env): ear-energy lanes (WO30A's ear_energy.py, unchanged) of the 3 danced and the 5 check songs -> lanes/<song>.energy.npz
(raw: 10 Hz raw lane; net: standardised network input). Prints the pooled mean/sd of the danced songs' network input as a check (0 / 1 by construction)."""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
import ear_energy as E  # noqa: E402
import motornet2_lanes as L  # noqa: E402


def main():
    import b2
    import fast_features as ff
    nets = []
    for name in L.DANCED + L.CHECK:
        if name in L.DANCED:
            audio, _ = b2.SONG_FILES[name]
            f = ff.fast_features(b2.decode(b2.SONGS / audio))
        else:
            f = ff.fast_features(ff.load_mono(str(L.W3 / "wav" / f"{name}.wav")))
        raw, net = E.lane(f), E.network_input(f)
        np.savez_compressed(L.OUT / f"{name}.energy.npz", raw=raw.astype(np.float32), net=net.astype(np.float32))
        if name in L.DANCED:
            nets.append(net)
        print(name, f.shape, "lane", raw.shape, "raw mean", float(raw.mean()), flush=True)
    z = np.concatenate(nets)
    print("danced pooled network input mean", float(z.mean()), "sd", float(z.std()), "(clipped)")


if __name__ == "__main__":
    main()
