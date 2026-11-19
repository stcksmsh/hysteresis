"""K5 check (work order 9; docs/BRAIN_SPEC.md 7.18 point 2, 7.19 A and C). Provisional servo model (Feetech STS3215 12 V assumed). One arm.

    k5_eval.py --policy best.pkl --out DIR [--k5 ...] [--modes argmax,sample] [--max-windows N]      resume-safe: a policy with its json is skipped

The 1,071 check windows of windows.json (3 per held-out song, 25 / 50 / 75 %), each an M3e episode with real state. The WO7 observer procedure for every scored policy and mode: fresh external
and internal observers (init key 0, 64 hidden, 600 Adam steps, seed 999) trained on 4 hard rollouts of 16 seeded TRAINING windows (Gumbel keys 100..103, start seed 100) by the scored fixed
policy; held-out rollouts key 7, start seed 4242. Pass/fail is ARGMAX; sampled is reported only. (a) = the time-shifted-control gap of each window (20 seeded circular shifts >= 4 s);
windows of one song are averaged to a per-song gap, and every interval is a bootstrap over the 357 songs, 10,000 resamples (paired intervals: per-song difference of two policies on the same windows).
Policies: trained | untrained (the initial weights, seed 0, kappa as initialised) | trained with kappa forced to 0 (the 7.19 A1 report). K5 passes (7.18 point 2) only if, in argmax and for the
external decoder, the (a) interval is above 0 (beats the time-shifted control) AND the paired (a)_trained - (a)_untrained interval is above 0. The kappa = 0 difference is reported for the
phase-coupling wording. Internal decoder: same numbers, reported with its own flags.
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import k5_train as T
import m3d
import m3d_controls as K
import m3e
import m3e_controls as MC
import m3e_jax as M


def per_song(gaps, songs):
    """Per-window gaps and their song ids (same order) -> (unique song ids in first-seen order, mean gap per song)."""
    order = list(dict.fromkeys(songs))
    g = np.asarray(gaps, float)
    return order, np.array([g[[i for i, s in enumerate(songs) if s == u]].mean() for u in order])


def song_stats(gaps, songs):
    order, v = per_song(gaps, songs)
    lo, hi = m3d.boot_ci(v)
    return {"a_song_mean": float(v.mean()), "a_ci": [lo, hi], "a_pass": bool(lo > 0), "n_songs": len(order), "per_song": v.tolist()}


def paired_songs(g_trained, g_control, songs):
    _, a = per_song(g_trained, songs)
    _, b = per_song(g_control, songs)
    return K.paired_difference(a, b)


def evaluate(P, name, combo, songs, stats, C, fns, modes, outdir, log):
    f = outdir / f"{name}.json"
    if f.exists():
        return json.loads(f.read_text())
    res = T.score_modes(fns, C, P, stats, combo, modes, str(outdir / "rollouts"), name, log)
    for m in res.values():
        for d in ("ext", "int"):
            m[d]["song"] = song_stats(m[d]["a_gaps"], songs)
    f.write_text(json.dumps(res))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--policy", required=True, help="best.pkl (or ckpt.pkl) of a K5 run")
    ap.add_argument("--out", required=True)
    ap.add_argument("--k5", default=str(T.K5))
    ap.add_argument("--modes", default="argmax,sample")
    ap.add_argument("--max-windows", type=int, help="test only: the first N check windows")
    a = ap.parse_args()
    T.install_signals()
    out = Path(a.out)
    (out / "rollouts").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:7.0f}s] {s}", flush=True)
    k5 = Path(a.k5)
    w = json.loads((k5 / "windows.json").read_text())
    order = T.train_order(w["train"])
    chk = [(r[0], r[2]) for r in w["check"]][:a.max_windows]
    songs = [s for s, _ in chk]
    combo = T.combine(T.build_toy(k5, "train", T.obs_windows(order)), T.build_toy(k5, "check", chk))
    C = M.load_cb()
    d = pickle.loads(Path(a.policy).read_bytes())
    P = jax.tree_util.tree_map(jnp.asarray, d["P"] if "P" in d else d["trainer"]["P"])
    stats = d["stats"] if "stats" in d else d["trainer"]["stats"]
    fns = m3e.make_fns(C)
    modes = tuple(a.modes.split(","))
    res = {"trained": evaluate(P, "trained", combo, songs, stats, C, fns, modes, out, log)}
    kap = np.array(res["trained"]["argmax"]["kappa_mean"]) if "argmax" in res["trained"] else np.array(next(iter(res["trained"].values()))["kappa_mean"])
    for name, Q in (("untrained", MC.initial_policy()), ("trained_kappa0", K.with_kappa(P, np.zeros(5)))):
        res[name] = evaluate(Q, name, combo, songs, stats, C, fns, modes, out, log)
    summ = {"n_songs": len(set(songs)), "n_windows": len(chk), "kappa_trained_means": kap.tolist(), "modes": {}}
    for m in modes:
        s = {}
        for dec in ("ext", "int"):
            tr = res["trained"][m][dec]
            s[dec] = {"trained": {k: tr["song"][k] for k in ("a_song_mean", "a_ci", "a_pass")},
                      **{f"paired_vs_{c}": {k: v for k, v in paired_songs(tr["a_gaps"], res[c][m][dec]["a_gaps"], songs).items() if k != "per_episode"} for c in ("untrained", "trained_kappa0")}}
            s[dec]["beats_untrained"] = bool(s[dec]["paired_vs_untrained"]["ci"][0] > 0)
            s[dec]["beats_kappa0"] = bool(s[dec]["paired_vs_trained_kappa0"]["ci"][0] > 0)
        t = res["trained"][m]
        s["b_rms_nonroll"], s["c_mi"], s["c_p"] = t["b_rms_nonroll"], t["c_mi"], t["c_p"]
        s["k5_pass"] = bool(s["ext"]["trained"]["a_pass"] and s["ext"]["beats_untrained"]) if m == "argmax" else None
        summ["modes"][m] = s
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    log("summary: " + json.dumps({m: {"k5_pass": v["k5_pass"], "ext_a": v["ext"]["trained"]["a_song_mean"], "ext_a_ci": v["ext"]["trained"]["a_ci"], "beats_untrained": v["ext"]["beats_untrained"],
                                       "beats_kappa0": v["ext"]["beats_kappa0"]} for m, v in summ["modes"].items()}))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except T.Interrupted:
        print("interrupted; finished batches are kept, rerun the same command to resume", flush=True)
        sys.exit(0)
