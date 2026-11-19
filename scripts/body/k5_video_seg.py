"""WO12 step 4 (report only): external and internal (a) per consecutive 60 s segment of each song's continuous K5 rollout, ARGMAX. Body env. Provisional servo model. One arm.

    k5_video_seg.py [--out /secondary/hyst-data/body/k5/danced/segments.json]

Observers: exactly the K5 check's for the trained policy (m3e.fresh_observers: init key 0, 64 hidden, 600 Adam steps, seed 999) on the 4 cached trained-argmax observer-training rollouts
`run1/eval/rollouts/trained_argmax_{0..3}_b0.npz` and the causal targets of the same 16 seeded training windows (k5_train.obs_windows); fitted once, not per song.
(a) of a segment = mean over its blocks of [loss against the targets circularly shifted by s blocks] - [matched loss], for each of 20 seeded shifts s in [8, len - 8] blocks (>= 4 s),
as m3d.time_shuffled_gap with the same seed; blocks scored: all of a segment except, for the first segment of a song, the first 8 (EVAL_FROM: the causal normalisation and the
descriptor window need 4 s). Targets are the song's own causal z-score (not restarted per segment), predictions the observers' output on the rollout's descriptors.
Reported per segment: mean gap over the shifts, the 2.5-97.5 percentile range of the 20 per-shift gaps, and a bootstrap 95 % interval of the mean over the shifts (10,000 resamples,
m3d.boot_ci). A last partial segment shorter than 40 blocks (20 s) is not scored (its length is reported). Nothing here is a pass/fail.
"""
import argparse
import json
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import k5_train as T
import k5_video_roll as R
import m3d
import m3e
import m3e_jax as M

SEG = 120
MIN_BLOCKS = 40
CHECK_REF = {"ext": 0.625, "int": 0.636}


def segment_bounds(nb, seg=SEG):
    return [(a, min(a + seg, nb)) for a in range(0, nb, seg)]


def shift_gaps(pred, yz, start, n_shifts=20, seed=0, min_shift=8):
    """pred, yz (T, 8) -> the n_shifts per-shift gaps (same draws as m3d.time_shuffled_gap with this seed); their mean is its gap."""
    rng = np.random.default_rng(seed)
    n = len(pred)
    matched = ((pred - yz) ** 2).mean(-1)[start:].mean()
    out = []
    for _ in range(n_shifts):
        s = int(rng.integers(min_shift, n - min_shift + 1))
        out.append(((pred - np.roll(yz, s, axis=0)) ** 2).mean(-1)[start:].mean() - matched)
    return np.array(out)


def fit_observers(k5=T.K5, evaldir=T.K5 / "run1" / "eval", policy=R.POLICY):
    _, stats = R.load_policy(policy)
    w = json.loads((Path(k5) / "windows.json").read_text())
    toy = T.build_toy(k5, "train", T.obs_windows(T.train_order(w["train"])))
    rolls = []
    for k in range(4):
        d = np.load(Path(evaldir) / "rollouts" / f"trained_argmax_{k}_b0.npz")
        rolls.append({x: d[x] for x in d.files})
        assert rolls[-1]["desc"].shape[0] == len(toy.y), "cached observer-training rollout does not match the 16 training windows"
    Oe, Oi = m3e.fresh_observers(rolls, toy.yz, stats)
    return Oe, Oi, stats


def decode(O, desc, mu, sd):
    return np.asarray(jax.vmap(lambda x: m3e.J.observer_apply(O, x))(jnp.asarray(m3d.std_desc(desc, mu, sd))))


def song_segments(r, yz, Oe, Oi, stats):
    nb = len(yz)
    pe, pi = decode(Oe, r["desc"], stats["dmu"], stats["dsd"]), decode(Oi, r["idesc"], stats["imu"], stats["isd"])
    out = []
    for a, b in segment_bounds(nb):
        seg = {"start_s": a / 2, "end_s": b / 2, "blocks": b - a, "partial": (b - a) < SEG}
        if b - a >= MIN_BLOCKS:
            for name, p in (("ext", pe), ("int", pi)):
                g = shift_gaps(p[a:b], yz[a:b], 8 if a == 0 else 0)
                lo, hi = m3d.boot_ci(g)
                seg[name] = {"gap": float(g.mean()), "shift_range": [float(np.percentile(g, 2.5)), float(np.percentile(g, 97.5))], "boot_ci": [lo, hi], "n_shifts": len(g),
                             "k5_check": CHECK_REF[name]}
        else:
            seg["note"] = f"shorter than {MIN_BLOCKS} blocks, not scored"
        out.append(seg)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(R.DANCED / "segments.json"))
    ap.add_argument("--songs", default=",".join(R.SONGS))
    a = ap.parse_args()
    Oe, Oi, stats = fit_observers()
    res = {"observers": "m3e.fresh_observers on run1/eval/rollouts/trained_argmax_{0..3}_b0.npz (the K5 check's trained-argmax observer-training rollouts), fitted once", "mode": "argmax",
           "k5_check_values": CHECK_REF, "songs": {}}
    for name in a.songs.split(","):
        z = np.load(R.DANCED / f"{name}.k5.npz")
        res["songs"][name] = {"blocks": int(len(z["yz"])), "segments": song_segments({k: z[k] for k in ("desc", "idesc")}, z["yz"], Oe, Oi, stats)}
    Path(a.out).write_text(json.dumps(res, indent=1))
    print("segment | " + " | ".join(("song", "t (s)", "len", "ext gap [boot 95%]", "int gap [boot 95%]")))
    for n, s in res["songs"].items():
        for g in s["segments"]:
            f = lambda d: f"{d['gap']:.3f} [{d['boot_ci'][0]:.3f}, {d['boot_ci'][1]:.3f}]" if d else "-"
            print(f"{n} | {g['start_s']:.0f}-{g['end_s']:.0f} | {g['blocks'] / 2:.0f} s | {f(g.get('ext'))} | {f(g.get('int'))}")


if __name__ == "__main__":
    main()
