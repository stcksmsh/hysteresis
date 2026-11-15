"""WO41 lookups and checks while E1 trains (7.66.2 a-d, 7.67.2 sync check, 7.67.3 two feature forms). Brain env. Writes t1b/facts.json; docs/T1B_FACTS.md is written from it by hand.

    t1b_facts.py genres | sync | forms
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.ndimage import uniform_filter1d

T0 = Path("/secondary/hyst-data/body/t0")
OUT = Path("/secondary/hyst-data/body/t1b")
FD = Path("/secondary/hyst-data/datasets/finedance/data/finedance")
LAG = 25                                                     # +-0.25 s at 100 Hz (half a beat at 120 bpm: a wider window locks onto other beats of a periodic signal)


def split_of():
    return {m: g["split"] for g in json.loads((T0 / "split.json").read_text())["groups"] if "finedance" in g["dataset"] for m in g["members"]}


def genres():
    sp = split_of()
    rows = []
    for k, s in sorted(sp.items()):
        j = json.loads((FD / "label_json" / f"{k.split('_')[1]}.json").read_text())
        rows.append(dict(seq=k, split=s, name=j["name"], style1=j["style1"], style2=j["style2"], frames=j["frames"]))
    res = dict(sequences=len(rows), per_split=Counter(r["split"] for r in rows), style1_by_split={s: Counter(r["style1"] for r in rows if r["split"] == s) for s in ("train", "validation", "test")},
               style2_by_split={s: Counter(r["style2"] for r in rows if r["split"] == s) for s in ("train", "validation", "test")},
               distinct_names=len({r["name"] for r in rows}), note="label_json has no dancer id: one sequence = one performance; 22 songs are danced twice; dancer identity is not recorded")
    return rows, json.loads(json.dumps(res))


def xcorr_lag(a, b):
    """lag (s) of the maximum of the cross-correlation of z-scored a (music onset) and b (movement speed) within +-0.25 s; positive = movement after music"""
    a = (a - a.mean()) / (a.std() + 1e-9)
    b = (b - b.mean()) / (b.std() + 1e-9)
    n = len(a)
    c = [float((a[max(0, -l):n - max(0, l)] * b[max(0, l):n - max(0, -l)]).mean()) for l in range(-LAG, LAG + 1)]
    i = int(np.argmax(c))
    return (i - LAG) / 100.0, c[i]


def sync():
    rows, _ = genres()
    out = []
    for r in rows:
        k = r["seq"]
        z = np.load(T0 / "seq" / "finedance" / f"{k}__V1.npz")
        ear = np.load(T0 / "lanes" / f"{k}.npz")["ear"][:, 40]
        wav = sf.info(str(FD / "music_wav" / f"{k.split('_')[1]}.wav")).duration
        tg = np.asarray(z["targets"], np.float64)
        sp = np.linalg.norm(np.diff(tg, axis=0) * 100 / tg.std(0), axis=1)
        sp = uniform_filter1d(sp, 10)
        on = uniform_filter1d(ear[:len(sp)], 10)
        T = min(len(sp), len(on))
        mot = (r["frames"]) / 30.0
        d = dict(seq=k, split=r["split"], audio_s=wav, motion_s=mot, audio_minus_motion_s=wav - mot, lanes_s=len(ear) / 100.0)
        if T >= 12000:
            w = 6000
            l1, c1 = xcorr_lag(on[:w], sp[:w])
            l2, c2 = xcorr_lag(on[T - w:T], sp[T - w:T])
        elif T >= 6000:
            h = T // 2
            l1, c1 = xcorr_lag(on[:h], sp[:h])
            l2, c2 = xcorr_lag(on[T - h:T], sp[T - h:T])
        else:
            l1 = c1 = l2 = c2 = None
        d.update(first_lag_s=l1, first_corr=c1, last_lag_s=l2, last_corr=c2, drift_s=(None if l1 is None else l2 - l1))
        out.append(d)
    return out


def forms():
    """per ear feature: share of variance between songs (global form carries it) and agreement of the global form with the causal within-song form (trailing 30 s z-score)"""
    sp = split_of()
    tr = [k for k, s in sp.items() if s == "train"]
    mats = [np.load(T0 / "lanes" / f"{k}.npz")["ear"] for k in tr]
    allx = np.concatenate(mats)
    gm, gs = allx.mean(0), allx.std(0)
    between = np.concatenate([np.repeat(m.mean(0, keepdims=True), len(m), 0) for m in mats]).var(0) / allx.var(0)
    W = 3000
    cors = []
    for m in mats[::4]:
        c = np.cumsum(np.vstack([np.zeros((1, 44)), m]), 0)
        c2 = np.cumsum(np.vstack([np.zeros((1, 44)), m ** 2]), 0)
        i = np.arange(1, len(m) + 1)
        lo = np.maximum(i - W, 0)
        mu = (c[i] - c[lo]) / (i - lo)[:, None]
        sd = np.sqrt(np.maximum((c2[i] - c2[lo]) / (i - lo)[:, None] - mu ** 2, 1e-6))
        rel = (m - mu) / sd
        cors.append([np.corrcoef(m[3000:, j], rel[3000:, j])[0, 1] for j in range(44)])
    return dict(global_mean=gm.tolist(), global_sd=gs.tolist(), between_song_variance_share=between.tolist(), corr_global_vs_trailing30s=np.nanmean(np.array(cors), 0).tolist(), n_train_songs=len(tr))


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "genres":
        _, r = genres()
        (OUT / "facts_genres.json").write_text(json.dumps(r, indent=1))
        print(json.dumps(r))
    elif what == "sync":
        r = sync()
        (OUT / "facts_sync.json").write_text(json.dumps(r, indent=1))
        dr = [x["drift_s"] for x in r if x["drift_s"] is not None]
        print(len(r), "seqs", "drift abs median", np.median(np.abs(dr)), "p95", np.percentile(np.abs(dr), 95), "max", np.max(np.abs(dr)))
    else:
        r = forms()
        (OUT / "facts_forms.json").write_text(json.dumps(r, indent=1))
        print("between share", np.round(r["between_song_variance_share"], 2).tolist())
