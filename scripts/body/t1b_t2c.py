"""WO41 T2, part 3: affect probe and passage test (docs/T1B_RULES.md section 6; BRAIN_SPEC 7.65.2, 7.66.3, 7.68.6). Brain env. Report only.

    t1b_t2c.py affect SEED LABELS.json [--run DIR]
LABELS.json = {"<passage id, e.g. fd_002_p1>": "calm|sad|tense|energetic|light"} supplied by the overseer after Kosta's session (never read from the answers file by the builder).
Passage feature = mean of the listener's affect units (192..255) over the passage's 15 s (listener run from song start). Probe: song label = majority of its 3 passages (ties dropped and counted),
song feature = mean over its passages; 5-fold cross-validated multinomial logistic regression (standardised, C = 1), folds grouped by song, vs 100 shuffled-label runs (seed 36301).
Passage test: passage pairs of different songs matched on tempo (5 %) and RMS (10 %); statistic = mean affect-state distance of different-label pairs minus same-label pairs; shuffled-label control.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))
import t1b_model as M  # noqa: E402
import t1b_t2 as T2  # noqa: E402

OUT, TR = T2.OUT, T2.TR
SEED = 36301


def passage_features(model, passages, norm):
    """-> {id: (64,) mean affect state, tempo bpm, rms}"""
    import braindump as bd
    mean, std = bd.stats()
    out, cache = {}, {}
    last = {}
    for p in passages:
        last[p["seq"]] = max(last.get(p["seq"], 0), int((p["start_s"] + 15) * 100))
    for p in passages:
        key, st = p["seq"], p["start_s"]
        end = int((st + 15) * 100)
        if key not in cache:
            x = np.load(OUT / "cortex" / f"{key}.npy", mmap_mode="r")
            ear = np.asarray(x[:, 2061 + 41])
            xs = np.clip((np.asarray(x[:min(len(x), last[key] + 2000)], np.float32) - norm[0]) / norm[1], -TR.CLIP_X, TR.CLIP_X)
            xs = torch.from_numpy(xs[:len(xs) // 2 * 2].reshape(len(xs) // 2, 2, -1).mean(1))[None]
            with torch.no_grad():
                s, _ = model.listener(xs)
            cache[key] = (s[0, :, M.NR:].numpy(), ear)
        s, ear = cache[key]
        a, b = int(st * 50), int((st + 15) * 50)
        rms = float(np.mean(np.clip(ear[int(st * 100):end] * std[41] + mean[41], 0, None)))
        out[p["id"]] = (s[a:b].mean(0), T2.tempo_bpm(key), rms)
    return out


def logreg_cv(x, y, groups, seed):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    acc = []
    for tr, te in GroupKFold(5).split(x, y, groups):
        if len(set(y[tr])) < 2:
            continue
        m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=500)).fit(x[tr], y[tr])
        acc.append((m.predict(x[te]) == y[te]).mean() * len(te))
    return float(np.sum(acc) / len(y))


def analyse(feats, passages, labels):
    ids = [p["id"] for p in passages if p["id"] in labels]
    song = {p["id"]: p["group"] for p in passages}
    by = {}
    for i in ids:
        by.setdefault(song[i], []).append(i)
    sx, sy, sg, ties = [], [], [], 0
    for g, ps in by.items():
        c = Counter(labels[i] for i in ps).most_common()
        if len(c) > 1 and c[0][1] == c[1][1]:
            ties += 1
            continue
        sx.append(np.mean([feats[i][0] for i in ps], 0))
        sy.append(c[0][0])
        sg.append(g)
    sx, sy, sg = np.array(sx), np.array(sy), np.array(sg)
    rng = np.random.default_rng(SEED)
    acc = logreg_cv(sx, sy, sg, SEED)
    shuf = [logreg_cv(sx, rng.permutation(sy), sg, SEED) for _ in range(100)]
    probe = dict(n_songs=int(len(sy)), n_ties_dropped=ties, label_counts=dict(Counter(sy.tolist())), accuracy=acc, shuffled_mean=float(np.mean(shuf)), shuffled_p95=float(np.percentile(shuf, 95)),
                 p_value=float((np.sum(np.array(shuf) >= acc) + 1) / 101), majority_baseline=float(Counter(sy.tolist()).most_common(1)[0][1] / len(sy)))
    pairs = []
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            i, j = ids[a], ids[b]
            if song[i] == song[j]:
                continue
            (fa, ta, ra), (fb, tb, rb) = feats[i], feats[j]
            if ta and tb and ra > 0 and rb > 0 and abs(ta / tb - 1) <= 0.05 and abs(ra / rb - 1) <= 0.10:
                pairs.append((i, j, float(np.linalg.norm(fa - fb))))
    diff = [d for i, j, d in pairs if labels[i] != labels[j]]
    same = [d for i, j, d in pairs if labels[i] == labels[j]]
    stat = float(np.mean(diff) - np.mean(same)) if diff and same else None
    null = []
    if stat is not None:
        lab = np.array([labels[i] for i in ids])
        for _ in range(100):
            pl = dict(zip(ids, rng.permutation(lab)))
            dd = [d for i, j, d in pairs if pl[i] != pl[j]]
            ss = [d for i, j, d in pairs if pl[i] == pl[j]]
            if dd and ss:
                null.append(np.mean(dd) - np.mean(ss))
    passage = dict(n_matched_pairs=len(pairs), n_different_label=len(diff), n_same_label=len(same), statistic=stat, shuffled_mean=float(np.mean(null)) if null else None,
                   p_value=float((np.sum(np.array(null) >= stat) + 1) / (len(null) + 1)) if null and stat is not None else None, conclusion_allowed=bool(len(diff) >= 10))
    return dict(probe=probe, passage_test=passage)


if __name__ == "__main__":
    a = sys.argv[1:]
    seed = int(a[1])
    run = a[a.index("--run") + 1] if "--run" in a else str(OUT / "e1" / f"seed{seed}")
    labels = json.loads(Path(a[2]).read_text())
    passages = json.loads((OUT / "labels" / "passages.json").read_text())
    torch.set_num_threads(4)
    model = T2.load_model(run)
    feats = passage_features(model, passages, TR.load_norm())
    res = analyse(feats, passages, labels)
    (Path(run) / "t2").mkdir(parents=True, exist_ok=True)
    (Path(run) / "t2" / "affect.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res))
