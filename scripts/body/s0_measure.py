"""WO19 Stage 0 measures (BRAIN_SPEC 7.34 and its overseer operationalisation). Brain env (numpy, scipy, sklearn). Imports m3f_report.fk_points and hf_share.read_csv; edits nothing. One arm.

Library (all inputs are joint trajectories q (T, 5) deg at 50 Hz, the CSV joint order):
    hand(q)                        last point of the rig forward kinematics (m3f_report.fk_points)
    cells(p, size)                 floor(p / size) as integer rows
    cell_dist(q, size=0.05)        {cell: share of rows}
    js_dist(p, q)                  Jensen-Shannon DISTANCE (sqrt of the divergence), base 2, of two share dicts
    song_measures(q, prog=None)    cell count, postures (cells with dwell >= 0.5 %), shoulder sd, peak hand speed (max central-difference 50 Hz speed), program entropy (bits, 8 programs)
    tempo_pairs(tempo, artist, eligible, tol=5)   greedy one-to-one pairs, different artists, |dBPM| <= tol (closest first)
    clip_features(q)               10 cm ball-cell histogram + per-joint mean and sd of angle and of speed
    pair_2afc(qa, qb, ...)         the machine 2AFC of one song pair: clips of 30 s, L2 logistic regression (C = 1, standardised), train on the first-half clips, test on the second-half clips
CLI:  s0_measure.py --s0 /secondary/hyst-data/body/s0   writes summary.json (needs pass2/, tempo.json, optionally v47/).
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.distance import jensenshannon
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hf_share  # noqa: E402
import m3f_report as R  # noqa: E402

HZ = 50
CLIP_S = 30
DWELL = 0.005
CELL = 0.05
CELL_CLIP = 0.10
N_PROG = 8


def hand(q):
    return R.fk_points(np.asarray(q, float))[:, 5]


def cells(p, size):
    return np.floor(np.asarray(p) / size).astype(np.int64)


def cell_dist(q, size=CELL):
    c = cells(hand(q), size)
    u, n = np.unique(c, axis=0, return_counts=True)
    return {tuple(k): v / len(c) for k, v in zip(u.tolist(), n)}


def js_dist(p, q):
    keys = sorted(set(p) | set(q))
    a = np.array([p.get(k, 0.0) for k in keys])
    b = np.array([q.get(k, 0.0) for k in keys])
    return float(jensenshannon(a, b, base=2))


def program_entropy(prog, n=N_PROG):
    c = np.bincount(np.asarray(prog, int), minlength=n).astype(float)
    p = c[c > 0] / c.sum()
    return float(-(p * np.log2(p)).sum())


def song_measures(q, prog=None):
    h = hand(q)
    d = cell_dist(q)
    speed = np.linalg.norm(np.gradient(h, axis=0) * HZ, axis=1)
    out = {"cells": len(d), "postures": int(sum(v >= DWELL for v in d.values())), "shoulder_sd_deg": float(np.std(q[:, 1])), "peak_hand_speed": float(speed.max()), "seconds": len(q) / HZ}
    if prog is not None:
        out["program_entropy_bits"] = program_entropy(prog)
    return out


def split_halves(q):
    n = len(q) // 2
    return q[:n], q[n:2 * n]


def tempo_pairs(tempo, artist, eligible, tol=5.0):
    """tempo/artist dicts id -> value; eligible: ids that may be used. Greedy one-to-one, closest |dBPM| first, different artists, |dBPM| <= tol -> [(a, b, dbpm)]."""
    ids = sorted(eligible)
    cand = sorted((abs(tempo[a] - tempo[b]), a, b) for i, a in enumerate(ids) for b in ids[i + 1:] if artist[a] != artist[b] and abs(tempo[a] - tempo[b]) <= tol)
    used, out = set(), []
    for d, a, b in cand:
        if a in used or b in used:
            continue
        used.update((a, b))
        out.append((a, b, float(d)))
    return out


# ---------------------------------------------------------------------------------------------------------------- machine 2AFC
def clip_features(q, vocab=None):
    """q (T, 5) deg -> (cell histogram share over `vocab` (a list of cell tuples), per-joint mean and sd of angle, and of speed (deg/s))."""
    h = hand(q)
    c = [tuple(r) for r in cells(h, CELL_CLIP).tolist()]
    hist = np.zeros(len(vocab))
    idx = {k: i for i, k in enumerate(vocab)}
    for k in c:
        if k in idx:
            hist[idx[k]] += 1
    hist /= len(c)
    v = np.abs(np.gradient(q, axis=0)) * HZ
    return np.concatenate([hist, q.mean(0), q.std(0), v.mean(0), v.std(0)])


def clips_of(q, half):
    """Non-overlapping 30 s clips lying wholly in the first half (half = 0) or the second half (half = 1) of the song."""
    L = CLIP_S * HZ
    n = len(q)
    lo, hi = (0, n // 2) if half == 0 else (n // 2, n)
    return [q[s:s + L] for s in range(lo, hi - L + 1, L)]


def pair_2afc(qa, qb, rng=None, n_shuffle=0, min_clips=2):
    """-> dict(acc, n_test, shuffled (list of accuracies of label-shuffled training), n_train) or None if a song has fewer than min_clips clips per half."""
    ca = [clips_of(qa, 0), clips_of(qa, 1)]
    cb = [clips_of(qb, 0), clips_of(qb, 1)]
    if min(len(ca[0]), len(ca[1]), len(cb[0]), len(cb[1])) < min_clips:
        return None
    n0, n1 = min(len(ca[0]), len(cb[0])), min(len(ca[1]), len(cb[1]))          # equal clips per song and half: otherwise the majority class lifts accuracy (and the shuffled control) above 50 %
    ca, cb = [ca[0][:n0], ca[1][:n1]], [cb[0][:n0], cb[1][:n1]]
    tr = ca[0] + cb[0]
    te = ca[1] + cb[1]
    ytr = np.r_[np.zeros(len(ca[0])), np.ones(len(cb[0]))]
    yte = np.r_[np.zeros(len(ca[1])), np.ones(len(cb[1]))]
    vocab = sorted({tuple(k) for c in tr for k in cells(hand(c), CELL_CLIP).tolist()})
    Xtr = np.stack([clip_features(c, vocab) for c in tr])
    Xte = np.stack([clip_features(c, vocab) for c in te])
    sc = StandardScaler().fit(Xtr)
    Xtr, Xte = sc.transform(Xtr), sc.transform(Xte)

    def acc(y):
        m = LogisticRegression(C=1.0, max_iter=2000).fit(Xtr, y)
        return float((m.predict(Xte) == yte).mean())

    out = {"acc": acc(ytr), "n_train": len(tr), "n_test": len(te), "shuffled": []}
    for _ in range(n_shuffle):
        out["shuffled"].append(acc(rng.permutation(ytr)))
    return out


def boot_mean(x, n=10000, seed=0):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), (n, len(x)))].mean(1)
    return {"mean": float(x.mean()), "lo": float(np.percentile(m, 2.5)), "hi": float(np.percentile(m, 97.5)), "n": int(len(x))}


def afc_over_pairs(Q, pairs, n_shuffle=5, seed=0):
    """Q: id -> q (T, 5); pairs [(a, b, ...)] -> mean accuracy over usable pairs with bootstrap interval and the shuffled control."""
    rng = np.random.default_rng(seed)
    accs, shuf, used = [], [], []
    for a, b, *_ in pairs:
        r = pair_2afc(Q[a], Q[b], rng, n_shuffle)
        if r is None:
            continue
        accs.append(r["acc"])
        shuf.append(float(np.mean(r["shuffled"])) if r["shuffled"] else np.nan)
        used.append((a, b))
    if not accs:
        return {"n": 0}
    out = boot_mean(accs, seed=seed)
    out["pairs_used"] = used
    out["per_pair"] = accs
    out["shuffled_control"] = boot_mean([s for s in shuf if s == s], seed=seed) if n_shuffle else None
    return out


# ---------------------------------------------------------------------------------------------------------------- whole-set measures
def js_between(D, ids=None, pairs=None):
    """Median JS distance over song pairs (all pairs of `ids`, or the given pairs), from the share dicts D."""
    if pairs is None:
        ids = sorted(ids if ids is not None else D)
        pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]]
    keys = sorted({k for d in D.values() for k in d})
    ix = {k: i for i, k in enumerate(keys)}
    M = {}
    for s, d in D.items():
        v = np.zeros(len(keys))
        for k, x in d.items():
            v[ix[k]] = x
        M[s] = v
    vals = np.array([jensenshannon(M[a[0]], M[a[1]], base=2) for a in pairs])
    return vals


def summarize(per_song, key):
    x = np.array([m[key] for m in per_song.values()], float)
    return {"mean": float(x.mean()), "median": float(np.median(x)), "sd": float(x.std(ddof=1)) if len(x) > 1 else None, "min": float(x.min()), "max": float(x.max()), "n": int(len(x))}


def measure_set(Q, progs, pairs, label):
    """Q id -> q (T, 5). Returns every measure for the set."""
    per = {s: song_measures(q, progs.get(s) if progs else None) for s, q in Q.items()}
    D = {s: cell_dist(q) for s, q in Q.items()}
    ids = sorted(Q)
    allp = js_between(D, ids)
    mp = [(a, b) for a, b, *_ in pairs]
    out = {"label": label, "n_songs": len(ids), "seconds": summarize(per, "seconds"), "postures": summarize(per, "postures"), "cells": summarize(per, "cells"),
           "shoulder_sd_deg": summarize(per, "shoulder_sd_deg"), "peak_hand_speed": summarize(per, "peak_hand_speed"),
           "js_between_all_pairs": {"median": float(np.median(allp)), "n_pairs": int(len(allp))}}
    if mp:
        v = js_between(D, pairs=mp)
        out["js_between_tempo_pairs"] = {"median": float(np.median(v)), "n_pairs": int(len(v))}
    HD = {}
    for s, q in Q.items():
        a, b = split_halves(q)
        HD[s] = js_dist(cell_dist(a), cell_dist(b))
    w = float(np.median(list(HD.values())))
    out["js_half_control"] = {"median": w}
    out["js_ratio_between_over_half"] = float(np.median(allp) / w) if w > 0 else None
    if progs:
        out["program_entropy_bits"] = summarize(per, "program_entropy_bits")
    return out, per


def load_pass2(d, ids):
    Q, P = {}, {}
    for s in ids:
        f = Path(d) / f"{s}.npz"
        if f.exists():
            z = np.load(f)
            Q[s], P[s] = z["rows50"].astype(float), z["prog"]
    return Q, P


def load_v47(d):
    return {f.name[:-9]: hf_share.read_csv(f)[0] for f in sorted(Path(d).glob("*-arm0.csv"))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--s0", default="/secondary/hyst-data/body/s0")
    ap.add_argument("--v47", help="dir of <id>-arm0.csv held-out v47 exports (default s0/v47) ")
    ap.add_argument("--danced-v47", default="/secondary/hyst-data/body/hf/v47")
    ap.add_argument("--danced-pass2", default="/secondary/hyst-data/body/k5p2/check/songs")
    a = ap.parse_args()
    s0 = Path(a.s0)
    K5 = Path("/secondary/hyst-data/body/k5")
    ids = json.loads((K5 / "splits.json").read_text())["check"]["ids"]
    tj = json.loads((s0 / "tempo.json").read_text())
    tempo = tj["tempo"]
    art = {str(int(r["id"])).zfill(6): r["artist_id"] for r in csv.DictReader(open("/secondary/hyst-data/brain/corpus/final_corpus.csv"))}
    Q, P = load_pass2(s0 / "pass2", ids)
    eligible = [s for s in Q if min(len(clips_of(Q[s], 0)), len(clips_of(Q[s], 1))) >= 2]
    pairs = tempo_pairs(tempo, art, eligible)
    res = {"tempo_route": tj["route"], "tempo_sanity": {"n_disagree": tj["n_disagree"], "of": len(tj["sanity_songs"])}, "n_pass2_songs": len(Q), "n_eligible_ge2_clips_per_half": len(eligible),
           "n_tempo_pairs_all": len(pairs)}
    m2, per2 = measure_set(Q, P, pairs, "pass2 held-out (all)")
    m2["afc_all_pairs"] = afc_over_pairs(Q, pairs)
    res["pass2"] = m2
    res["pass2_per_song"] = per2
    vdir = Path(a.v47) if a.v47 else s0 / "v47"
    if vdir.exists() and list(vdir.glob("*-arm0.csv")):
        QV = load_v47(vdir)
        vp_file = vdir / "pairs.json"
        vpairs = [tuple(x) for x in json.loads(vp_file.read_text())] if vp_file.exists() else []
        mv, perv = measure_set(QV, None, vpairs, "v47 held-out subset")
        mv["afc_v47_pairs"] = afc_over_pairs(QV, vpairs)
        res["v47_heldout"] = mv
        res["v47_heldout_per_song"] = perv
        sub = [p for p in vpairs if p[0] in Q and p[1] in Q]
        res["pass2_on_v47_pairs"] = afc_over_pairs(Q, sub)
        res["pass2_on_v47_songs"], _ = measure_set({s: Q[s] for s in QV if s in Q}, {s: P[s] for s in QV if s in Q}, sub, "pass2 on the v47 subset songs")
    dv = Path(a.danced_v47)
    danced = ["instant-crush", "five-years", "presence"]
    QD = {s: hf_share.read_csv(dv / f"{s}-arm0.csv")[0] for s in danced if (dv / f"{s}-arm0.csv").exists()}
    QP = {s: hf_share.read_csv(Path(a.danced_pass2) / f"{s}.pass2.csv")[0] for s in danced if (Path(a.danced_pass2) / f"{s}.pass2.csv").exists()}
    dp = [(x, y) for i, x in enumerate(sorted(QD)) for y in sorted(QD)[i + 1:]]
    if QD:
        res["danced_v47"], res["danced_v47_per_song"] = measure_set(QD, None, dp, "v47 arm 0, the three danced songs")
        res["danced_pass2"], res["danced_pass2_per_song"] = measure_set(QP, None, dp, "pass2, the three danced songs")
        res["danced_afc_v47_not_tempo_matched"] = afc_over_pairs(QD, dp)
        res["danced_afc_pass2_not_tempo_matched"] = afc_over_pairs(QP, dp)
    (s0 / "measures.json").write_text(json.dumps(res, default=float))
    print(json.dumps({k: v for k, v in res.items() if not k.endswith("per_song")}, default=float)[:3000])


if __name__ == "__main__":
    main()
