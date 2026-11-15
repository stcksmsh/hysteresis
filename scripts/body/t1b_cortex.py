"""WO41 T1b cortex precompute (docs/T1B_RULES.md section 1). Brain env.

    t1b_cortex.py width                       print the per-frame layout and the storage numbers (no audio)
    t1b_cortex.py song KEY WAV [OUTDIR]       one song -> OUTDIR/KEY.npy (T, 2105) float16 + beats/KEY.json (default /secondary/hyst-data/body/t1b/cortex)
    t1b_cortex.py list THREADS                all FineDance songs of t0/lanes_list_fd.json, resumable (an existing .npy is skipped)
    t1b_cortex.py repro KEY WAV               recompute one song and compare with the T0 lane (ear, h_abs, s10, arousal_b7), max abs difference

Layout of a frame (width 2105), same recipe, model and chunking as t0_lanes (6000-frame chunks, carried state, B7 epoch 6):
  0..2047    h of layers L1..L4 as [real(256), imag(256)] per layer
  2048..2051 surprisal per layer (braindump.surprisal on err/logvar at 100 Hz), NaN -> 0
  2052..2055 surprisal valid bits (1 where defined)
  2056..2059 log-precision per layer = - mean over the 44 channels of logvar
  2060       arousal (B7)
  2061..2104 the 44 standardised ear features (the first 44 columns of the core input)
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))
T0 = Path("/secondary/hyst-data/body/t0")
OUT = Path("/secondary/hyst-data/body/t1b/cortex")
CHUNK = 6000
NL, NM = 4, 256
PARTS = (("h", 2 * NL * NM), ("surprisal", NL), ("surprisal_valid", NL), ("log_precision", NL), ("arousal", 1), ("ear", 44))
WIDTH = sum(n for _, n in PARTS)
OFF = {}
_o = 0
for _n, _w in PARTS:
    OFF[_n] = (_o, _o + _w)
    _o += _w
assert WIDTH == 2105


def mono_wav(src, dst):
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "44100", str(dst)], check=True)


def frames_of(model, x):
    """x (T, 46) core input -> (T, 2105) float32 and the lanes used for the repro check"""
    import torch
    import braindump as bd
    import core
    T = len(x)
    h, lv, er, ar = [[] for _ in range(NL)], [[] for _ in range(NL)], [[] for _ in range(NL)], []
    st = model.init_state(1)
    with torch.no_grad():
        for a in range(0, T, CHUNK):
            out, st = model(torch.from_numpy(x[a:a + CHUNK])[None], st)
            for i, o in enumerate(out):
                hh = o["h"][0]
                h[i].append(torch.cat([hh.real, hh.imag], -1).numpy())
                lv[i].append(o["logvar"][0].numpy())
                er[i].append(o["err"][0].numpy())
            ar.append(out[0]["arousal"][0].numpy())
    cat = lambda v: np.concatenate(v, 0)
    sur = np.stack([bd.surprisal(cat(er[i]), cat(lv[i]), hz) for i, hz in enumerate(core.HORIZONS)], 1)
    prec = np.stack([-cat(lv[i]).mean(-1) for i in range(NL)], 1)
    f = np.concatenate([np.concatenate([cat(h[i]) for i in range(NL)], 1), np.nan_to_num(sur, nan=0.0), np.isfinite(sur).astype(np.float32), prec, cat(ar)[:, None], x[:, :44]], 1)
    assert f.shape == (T, WIDTH), f.shape
    return f.astype(np.float32), dict(sur=sur, arousal=cat(ar))


def core_input(wav, tmp):
    import b2
    import braindump as bd
    import fast_features as ff
    from analyze.structure import analyze_mix
    from analyze.wav import DecodedWav
    m = Path(tmp)
    mono_wav(wav, m)
    y = b2.load_mono(m)
    beats = analyze_mix(DecodedWav(44100, [y], len(y) / 44100))["beats"]
    mean, std = bd.stats()
    feats = ff.fast_features(ff.load_mono(str(m)))
    x = b2.build_inputs(feats, beats, mean, std)
    m.unlink()
    return x, [float(b) for b in beats]


def song(key, wav, outdir=OUT):
    import k5_video_lanes as V
    outdir = Path(outdir)
    (outdir / "beats").mkdir(parents=True, exist_ok=True)
    p = outdir / f"{key}.npy"
    if p.exists():
        return p
    x, beats = core_input(wav, outdir / f"{key}.tmp.wav")
    f, _ = frames_of(V.load_model(), x)
    b = np.asarray(beats)
    gap = np.diff(b) if len(b) > 1 else np.zeros(0)
    t = np.arange(len(x)) / 100.0
    ix = np.searchsorted(b, t, side="right")                                       # index of the next beat after each frame
    look = np.where(ix < len(b), b[ix.clip(max=max(len(b) - 1, 0))] - t, 0.0) if len(b) else np.zeros_like(t)
    (outdir / "beats" / f"{key}.json").write_text(json.dumps(dict(beats=beats, n_frames=len(x), ibi_median=float(np.median(gap)) if len(gap) else None,
                                                                  ibi_max=float(gap.max()) if len(gap) else None, next_beat_lookahead_mean=float(look.mean()),
                                                                  next_beat_lookahead_max=float(look.max()))))
    np.save(str(p) + ".tmp.npy", f.astype(np.float16))
    Path(str(p) + ".tmp.npy").replace(p)
    return p


def cmd_list(threads):
    import torch
    torch.set_num_threads(threads)
    for it in json.loads((T0 / "lanes_list_fd.json").read_text()):
        if (OUT / f"{it['key']}.npy").exists():
            continue
        song(it["key"], it["wav"])
        print("cortex", it["key"], flush=True)


def cmd_repro(key, wav):
    import torch
    import k5_video_lanes as V
    torch.set_num_threads(8)
    x, _ = core_input(wav, OUT / f"{key}.repro.wav")
    f, aux = frames_of(V.load_model(), x)
    ref = np.load(T0 / "lanes" / f"{key}.npz")
    n10 = len(x) // 10
    d = {}
    d["ear"] = float(np.abs(f[:, OFF["ear"][0]:] - ref["ear"]).max())
    h = f[:, :2 * NL * NM].reshape(len(f), NL, 2, NM)
    habs = np.sqrt(h[:, :, 0] ** 2 + h[:, :, 1] ** 2).reshape(len(f), NL, 8, 32).mean(-1).reshape(len(f), 32)[9:n10 * 10:10]
    d["h_abs"] = float(np.abs(habs - ref["h_abs"]).max())
    d["arousal_b7"] = float(np.abs(aux["arousal"][9:n10 * 10:10] - ref["arousal_b7"]).max())
    s10 = aux["sur"][9:n10 * 10:10]
    d["s10_layers"] = float(np.nanmax(np.abs(s10 - ref["s10"][:, :4])))
    d["s10_nan_pattern_equal"] = bool(np.array_equal(np.isnan(s10), np.isnan(ref["s10"][:, :4])))
    d["float16_roundtrip_max_abs_h"] = float(np.abs(f[:, :2048].astype(np.float16).astype(np.float32) - f[:, :2048]).max())
    print(json.dumps(d))
    (OUT / "repro.json").write_text(json.dumps(d))


def cmd_width():
    for n, w in PARTS:
        print(f"{n:16s} {w:5d} cols  [{OFF[n][0]}:{OFF[n][1]}]")
    print("width", WIDTH)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "width":
        cmd_width()
    elif a[0] == "song":
        song(a[1], a[2], *a[3:])
    elif a[0] == "list":
        cmd_list(int(a[1]))
    else:
        cmd_repro(a[1], a[2])
