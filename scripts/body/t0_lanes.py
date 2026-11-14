"""WO37 T0 lanes (brain env). Rules: docs/T0_RULES.md section 5. Same recipe, model, chunking and frame choice as k5_data.song_lanes / motornet2_lanes, plus the mode amplitudes and the ear energy.

    t0_lanes.py song KEY WAV [OUTDIR]     one song -> OUTDIR/KEY.npz (default /secondary/hyst-data/body/t0/lanes)
    t0_lanes.py list LIST.json            [{"key", "wav"}, ...] resumable (skips an existing npz); one process, 8 threads
    t0_lanes.py repro                     recompute arousal_b7 and s10 of one check song and one danced song, compare with the stored lanes (HOLD lanes if > 1e-4)
Stored: ear (T, 44) standardised + clipped fast features (the core input's first 44 columns), y (blocks, 8) as k5 lanes, s10 (n10, 5) = 4 layers + total, arousal_b7 (n10,),
h_abs (n10, 32) = |h| of each layer's 256 modes in 8 contiguous groups of 32, mean over the group, ee (n10,) ear energy (raw lane), n_frames. Stamps are frames 9::10.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))
OUT = Path("/secondary/hyst-data/body/t0")
CHUNK, BLOCK = 6000, 50
W3 = Path("/secondary/hyst-data/body/motornet_toy/work3")


def mono_wav(src, dst):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "44100", str(dst)], check=True)


def lanes_of(model, x):
    """x (T, 46) core input -> the k5 lane dict (via k5_data.song_lanes, one pass) plus h_abs (n10, 32). song_lanes does not expose h, so the same loop is run once here for h only
    (cost: one more cortex pass; the lanes of the dict are not recomputed from this pass)."""
    import torch
    import k5_data as D
    z = D.song_lanes(model, x)
    nb10 = len(x) // 10
    habs = []
    st = model.init_state(1)
    with torch.no_grad():
        for a in range(0, len(x), CHUNK):
            out, st = model(torch.from_numpy(x[a:a + CHUNK])[None], st)
            cols = []
            for o in out:
                h = o["h"][0].abs()[9::10]                                   # frames a + 9, a + 19, ... (CHUNK % 10 == 0)
                cols.append(h.reshape(len(h), 8, 32).mean(-1).numpy())
            habs.append(np.concatenate(cols, 1))
    habs = np.concatenate(habs)[:nb10]
    return z, habs.astype(np.float32)


def song(key, wav, outdir=OUT / "lanes", tmp=OUT / "tmp"):
    import ear_energy as EE
    import b2
    import braindump as bd
    import fast_features as ff
    import k5_video_lanes as V
    from analyze.structure import analyze_mix
    from analyze.wav import DecodedWav
    outdir.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    p = outdir / f"{key}.npz"
    if p.exists():
        return p
    m = tmp / f"{key}.wav"
    mono_wav(wav, m)
    y = b2.load_mono(m)
    beats = analyze_mix(DecodedWav(44100, [y], len(y) / 44100))["beats"]
    mean, std = bd.stats()
    feats = ff.fast_features(ff.load_mono(str(m)))
    x = b2.build_inputs(feats, beats, mean, std)
    z, habs = lanes_of(V.load_model(), x)
    n10 = len(x) // 10
    np.savez_compressed(str(p) + ".tmp.npz", ear=x[:, :44].astype(np.float32), y=z["y"], s10=z["s10"], arousal_b7=z["arousal_b7"], h_abs=habs,
                        ee=EE.lane(feats)[:n10].astype(np.float32), n_frames=len(x))
    Path(str(p) + ".tmp.npz").replace(p)
    m.unlink()
    return p


def cmd_list(path):
    import torch
    torch.set_num_threads(8)
    for it in json.loads(Path(path).read_text()):
        if (OUT / "lanes" / f"{it['key']}.npz").exists():
            continue
        song(it["key"], it["wav"])
        print("lanes", it["key"], flush=True)


def cmd_repro():
    import torch
    torch.set_num_threads(8)
    import b2
    import braindump as bd
    import fast_features as ff
    import k5_video_lanes as V
    import k5_data as D
    model = V.load_model()
    mean, std = bd.stats()
    res = {}
    cases = {"blue-lagoon": (W3 / "wav/blue-lagoon.wav", W3 / "blue-lagoon.beats.json", np.load(W3 / "blue-lagoon.lanes.npz")),
             "instant-crush": (None, None, np.load("/secondary/hyst-data/body/k5/danced/lanes/instant-crush.npz"))}
    for name, (wav, bj, ref) in cases.items():
        x = bd.danced_inputs(name) if wav is None else b2.build_inputs(ff.fast_features(ff.load_mono(str(wav))), json.loads(bj.read_text())["beats"], mean, std)
        z = D.song_lanes(model, x)
        res[name] = {k: float(np.nanmax(np.abs(z[k] - ref[k]))) for k in ("arousal_b7", "s10") if k in ref.files and k in z}
        res[name]["nan_pattern_equal"] = bool(np.array_equal(np.isnan(z["s10"]), np.isnan(ref["s10"])))
        l4 = np.load(f"/secondary/hyst-data/body/motornet_toy2/lanes/{name}.npz")["l4"]                  # stored L4 state: [real, imag] (nb10, 512)
        stored = np.abs(l4[:, :256] + 1j * l4[:, 256:]).reshape(len(l4), 8, 32).mean(-1)
        _, habs = lanes_of(model, x)
        res[name]["l4_abs_groups"] = float(np.abs(habs[:len(stored), 24:32] - stored[:len(habs)]).max())
        print(name, res[name], flush=True)
    worst = max(v for d in res.values() for k, v in d.items() if k != "nan_pattern_equal")
    print("max abs diff", worst, "HOLD lanes" if worst > 1e-4 else "lanes reproduce")
    (OUT / "lanes_repro.json").write_text(json.dumps(res))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "song":
        song(a[1], a[2], *(Path(x) for x in a[3:]))
    elif a[0] == "list":
        cmd_list(a[1])
    else:
        cmd_repro()
