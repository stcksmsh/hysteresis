"""B7 lanes into `mindState` (work order 2, phase 3). For a song that already has a mindState (core-2b mood lanes, scripts/emotion/mindstate.py), run B7
epoch 6 over it (braindump.run_song) and add an additive `brain` object INSIDE the mindState. mood.* stays as it was (energy from core-2b). The reserved
bands / surprise / neuromod arrays stay empty: the Rust reader (hyst-compile/src/mind_state.rs, version 1) rejects anything else there and ignores unknown
keys, so `brain` reads clean and the planner is untouched. Moving the lanes into the reserved names needs mindState version 2 and a Rust change (FOR USER).

`brain` (mechanism names only; all lanes on 0.1 s bins, bin k = frames [10 k, 10 k + 10), stamped at frame 10 k + 9; null = undefined there):
  source                 "b7-epoch6"; hopSeconds 0.1
  surprisal              {L1, L2, L3, L4, total}: per layer, mean over the 44 features of the Gaussian NLL (nats) of the prediction whose window completes at the
                         stamp frame (horizons 0.1, 0.5, 2, 8 s); total = sum over the layers that have a value
  smoothedSurprisal      one-pole of total surprisal, rise 1 s, decay 8 s (the lane the authoring page called "arousal")
  arousalSignal          B7's own arousal value (one-pole of L1 + L2 surprisal) that sets the gain, at the stamp frame
  l4PredictedVariance    mean over the 44 features of exp(L4 log-variance), one-pole 8 s (the lane the authoring page called "tension")
  surprisalSlope30s      least-squares slope per second of total surprisal over the past 30 s (positive = rising); 0 for the first bin
  bandPower              {L1..L4}: mean over the layer's 256 modes of |h|^2, averaged over the bin
  gain, exponent         {L1..L4}: the 2 s block's gain 1 + w_g dev and |lambda| exponent
  selfSimilarity         braindump.py's lane (1 - max cosine against codes >= 17 s old), null until defined
  coherence              {L1..L4}: braindump.py's windowed phase order parameter, bin k = the window ending at frame 10 k + 9 (null before 1 s)
  crossing               {thresholds, minLayers, times}: window-end times (s) where >= 3 layers exceed their own threshold
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b2  # noqa: E402
import braindump as bd  # noqa: E402
import core  # noqa: E402
import core_b7  # noqa: E402
import train_b7  # noqa: E402

MIND_DIR = Path("/secondary/hyst-data/emotion/a2/a3r2/after")
OUT = Path("/secondary/hyst-data/brain/mindstate")
LAYERS = b2.LAYERS


def _lane(a, nd=5):
    return [None if not np.isfinite(v) else round(float(v), nd) for v in a]


def brain_field(res, z, thresholds):
    """Per-frame run results (braindump.run_song) + the standardised features z (T, 44) -> the `brain` object."""
    T = len(z)
    nb = T // 10
    s = np.arange(nb) * 10 + 9
    sur = {n: bd.surprisal(res["err"][i], res["logvar"][i], h)[s] for i, (n, h) in enumerate(zip(LAYERS, core.HORIZONS))}
    total = np.nansum(np.stack([sur[n] for n in LAYERS]), 0)
    var4 = np.exp(res["logvar"][3]).mean(1)[s]
    blk = s // core_b7.BLOCK
    code = np.concatenate([bd.pooled(z, res["ticks"]), res["tick_state"]], 1)
    import torch
    import torch.nn.functional as F
    codes = F.normalize(torch.from_numpy(code).float() @ bd.projection(), dim=-1).numpy()
    ss = bd.selfsim_lane(codes, res["ticks"], T)[s]
    coh = bd.window_means(np.stack(res["coh"], 1))
    cross = bd.crossings(coh, thresholds) if len(coh) else np.zeros(0, bool)
    cbin = np.full((nb, 4), np.nan, np.float32)
    k = np.arange(nb)
    ok = (k >= 9) & (k - 9 < len(coh))
    cbin[ok] = coh[k[ok] - 9]
    per_layer = lambda name: {n: _lane(name(i)) for i, n in enumerate(LAYERS)}
    return {
        "source": "b7-epoch6", "hopSeconds": 0.1,
        "surprisal": {**{n: _lane(sur[n]) for n in LAYERS}, "total": _lane(total)},
        "smoothedSurprisal": _lane(b2.one_pole(total, 1.0, 8.0)),
        "arousalSignal": _lane(res["arousal"][s]),
        "l4PredictedVariance": _lane(b2.one_pole(var4, 8.0, 8.0)),
        "surprisalSlope30s": _lane(b2.slope(total)),
        "bandPower": per_layer(lambda i: res["pw"][i][:nb * 10].reshape(nb, 10).mean(1)),
        "gain": per_layer(lambda i: res["gain"][i][blk]),
        "exponent": per_layer(lambda i: res["expo"][i][blk]),
        "selfSimilarity": _lane(ss),
        "coherence": per_layer(lambda i: cbin[:, i]),
        "crossing": {"thresholds": [float(t) for t in thresholds], "minLayers": bd.MIN_LAYERS, "times": [round((m + 10) / 10, 1) for m in np.flatnonzero(cross)]},
    }


def write_song(name, model, x, out=OUT):
    doc = json.loads((MIND_DIR / f"mind-{name}.json").read_text())
    ms = doc["mindState"]
    if "brain" in ms:
        raise ValueError("mindState already has brain")
    if ms["hopSeconds"] != 0.5:
        raise ValueError("mood.energy is expected at 0.5 s steps")
    res = bd.run_song(model, x)
    ms["brain"] = brain_field(res, x[:, :core.FEAT], bd.load_thresholds())
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"mind-{name}.json").write_text(json.dumps(doc, separators=(",", ":")))
    return out / f"mind-{name}.json", len(ms["brain"]["smoothedSurprisal"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--threads", type=int, default=6)
    a = ap.parse_args(argv)
    import torch
    torch.set_num_threads(a.threads)
    model, _ = train_b7.load_model7(bd.CKPT)
    for name in a.names or list(b2.SONG_FILES):
        print(name, *write_song(name, model, bd.danced_inputs(name), a.out), flush=True)


if __name__ == "__main__":
    main()
