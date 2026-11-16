"""WO42 band-limit check (BRAIN_SPEC 7.69 overseer note). Brain env. Report only, nothing is changed.

PhantomDance audio is 16 kHz (nothing above 8 kHz); FineDance has content above. Question: which of the 44 ear columns / 46 cortex input columns depend on content above 8 kHz and by how much do
the lanes move. Method: 5 FineDance songs (seed 42003 over the sorted catalogue; first 120 s of each), features and cortex lanes of the original against the same audio low-passed at 8 kHz
(zero-phase Butterworth order 8, sosfiltfilt, at 44.1 kHz). Also: power share above 8 kHz of the audio of each source (20 songs each), to see whether Motorica is band-limited too.
Output: /secondary/hyst-data/body/t0_phantom/bandlimit.json
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))
FD_OUT = Path("/secondary/hyst-data/body/t0")
OUT = Path("/secondary/hyst-data/body/t0_phantom/bandlimit.json")
SEC = 120


def beats_of(y):
    from analyze.structure import analyze_mix
    from analyze.wav import DecodedWav
    return analyze_mix(DecodedWav(44100, [y], len(y) / 44100))["beats"]


def share_above(y, hz=8000):
    import fast_features as ff
    S = np.abs(__import__("librosa").stft(y, n_fft=2048, hop_length=2048)) ** 2
    f = np.linspace(0, ff.SR / 2, S.shape[0])
    return float(S[f >= hz].sum() / (S.sum() + 1e-20))


def main():
    import torch
    torch.set_num_threads(2)
    import b2
    import braindump as bd
    import fast_features as ff
    import k5_video_lanes as V
    import t0_lanes as L
    mean, std = bd.stats()
    model = V.load_model()
    cat = json.loads((FD_OUT / "catalogue_fd.json").read_text())
    fd_wav = lambda c: f"/secondary/hyst-data/datasets/finedance/data/finedance/music_wav/{c['seq']}.wav"
    idx = sorted(np.random.default_rng(42003).choice(len(cat), 5, replace=False))
    sos = butter(8, 8000, fs=44100, output="sos")
    cols46 = ff.COLUMNS + ["beat_a", "beat_b"]
    per_song, diffs, lane_diffs = [], [], {k: [] for k in ("arousal_b7", "s10", "ee", "h_abs", "y")}
    for i in idx:
        c = cat[int(i)]
        y0 = ff.load_mono(fd_wav(c))[:SEC * ff.SR]
        y1 = sosfiltfilt(sos, y0).astype(np.float32)
        x0 = b2.build_inputs(ff.fast_features(y0), beats_of(y0), mean, std)
        x1 = b2.build_inputs(ff.fast_features(y1), beats_of(y1), mean, std)
        n = min(len(x0), len(x1))
        d = x1[:n] - x0[:n]
        diffs.append(dict(rms=np.sqrt((d ** 2).mean(0)).tolist(), corr=[float(np.corrcoef(x0[:n, j], x1[:n, j])[0, 1]) if x0[:n, j].std() > 0 else float("nan") for j in range(x0.shape[1])]))
        z0, h0 = L.lanes_of(model, x0[:n])
        z1, h1 = L.lanes_of(model, x1[:n])
        from k5_data import song_lanes  # noqa: F401  (lanes_of already uses it)
        import ear_energy as EE
        e0, e1 = EE.lane(ff.fast_features(y0))[:n // 10], EE.lane(ff.fast_features(y1))[:n // 10]
        m = min(len(z0["arousal_b7"]), len(z1["arousal_b7"]))
        lane_diffs["arousal_b7"].append([float(np.nanmean(np.abs(z0["arousal_b7"][:m] - z1["arousal_b7"][:m]))), float(np.nanstd(z0["arousal_b7"][:m])), float(np.corrcoef(z0["arousal_b7"][:m], z1["arousal_b7"][:m])[0, 1])])
        lane_diffs["s10"].append([float(np.nanmean(np.abs(z0["s10"][:m] - z1["s10"][:m]))), float(np.nanstd(z0["s10"][:m]))])
        lane_diffs["h_abs"].append([float(np.abs(h0[:m] - h1[:m]).mean()), float(h0[:m].std())])
        k = min(len(e0), len(e1))
        lane_diffs["ee"].append([float(np.abs(e0[:k] - e1[:k]).mean()), float(np.std(e0[:k]))])
        kk = min(len(z0["y"]), len(z1["y"]))
        lane_diffs["y"].append([float(np.abs(z0["y"][:kk] - z1["y"][:kk]).mean()), float(np.std(z0["y"][:kk]))])
        per_song.append(c["key"])
        print("song", c["key"], flush=True)
    rms = np.mean([d["rms"] for d in diffs], 0)
    corr = np.nanmean([d["corr"] for d in diffs], 0)
    # source audio: power share above 8 kHz, 20 songs each
    shares = {}
    for name, cat_path in (("finedance", FD_OUT / "catalogue_fd.json"), ("phantom", Path("/secondary/hyst-data/body/t0_phantom/catalogue.json")), ("motorica", Path("/secondary/hyst-data/body/t0_motorica/catalogue.json"))):
        cc = json.loads(cat_path.read_text())
        sel = [cc[int(j)] for j in np.linspace(0, len(cc) - 1, min(20, len(cc))).astype(int)]
        v = [share_above(ff.load_mono(fd_wav(c) if name == "finedance" else c["wav"])[:60 * ff.SR]) for c in sel]
        shares[name] = dict(median=float(np.median(v)), p90=float(np.percentile(v, 90)), max=float(np.max(v)), n=len(v))
        print("share above 8 kHz", name, shares[name], flush=True)
    res = dict(songs=per_song, seconds_each=SEC, columns=cols46, rms_diff_standardised=dict(zip(cols46, map(float, rms))), corr=dict(zip(cols46, map(float, corr))),
               lane_shift=lane_diffs, share_power_above_8k=shares)
    OUT.write_text(json.dumps(res, indent=1))
    print("columns with rms diff > 0.1:", [c for c, r in zip(cols46, rms) if r > 0.1])


if __name__ == "__main__":
    main()
