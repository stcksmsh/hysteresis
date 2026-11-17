"""AIST++ BAS cross-check (docs/AIST_BAS_RULES.md). Brain env.
    aist_bas.py run      per-sequence BAS/chance -> bas/per_sequence.csv
    aist_bas.py report   aggregate -> docs/AIST_BAS_REPORT.md"""
import csv
import sys
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import beatv_lib as BL  # noqa: E402
from aist_load import load_pkl  # noqa: E402

A = Path("/secondary/hyst-data/datasets/aist")
FPS = 60
SR = 22050
CSV = A / "bas/per_sequence.csv"
VARIANTS = {"main": (5.0, 0.1), "literal": (2.5, 3 / 60)}     # (smoothing sigma in frames at 30 fps -> time-scaled, BAS sigma s)
COLS = [f"{k}_{src}_{v}" for src in ("optim", "raw") for v in VARIANTS for k in ("bas_music", "chance_music", "bas_kin", "chance_kin")]


def music_beats(mid, cache={}):
    if mid not in cache:
        import librosa
        y, sr = librosa.load(str(A / "music" / f"{mid}.wav"), sr=SR)
        env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=441)
        _, b = librosa.beat.beat_track(onset_envelope=env, sr=sr, hop_length=441, units="time")
        cache[mid] = np.asarray(b, float)
    return cache[mid]


def seq_names():
    ign = set((A / "splits/ignore_list.txt").read_text().split())
    names = sorted(p.stem for p in (A / "data/keypoints3d").glob("*.pkl"))
    return [n for n in names if n not in ign], len(names) - len([n for n in names if n not in ign])


def speed(k3, fps=FPS):
    return np.r_[np.linalg.norm(np.diff(k3, axis=0), axis=2).mean(1), 0] * fps


def one(i, name):
    mid = name.split("_")[4]
    mb = music_beats(mid)
    d = load_pkl(A / "data/keypoints3d" / f"{name}.pkl")
    dur = len(d["keypoints3d_optim"]) / FPS
    row = dict(seq=name, music=mid, dur=dur, n_music_beats=len(mb))
    rng = np.random.default_rng(47102 + i)
    for src, key in (("optim", "keypoints3d_optim"), ("raw", "keypoints3d")):
        sp = speed(np.asarray(d[key], float))
        sp[-1] = sp[-2]
        for v, (sm, sg) in VARIANTS.items():
            kb = BL.kin_beats(sp, FPS, sm)
            for mode, tag in (("music", "music"), ("kin", "kin")):
                row[f"bas_{tag}_{src}_{v}"] = BL.bas(mb, kb, dur, sigma=sg, mode=mode)
                row[f"chance_{tag}_{src}_{v}"] = BL.bas_chance(mb, kb, dur, rng, sigma=sg, mode=mode)
    return row


def run():
    CSV.parent.mkdir(parents=True, exist_ok=True)
    names, _ = seq_names()
    allnames = sorted(p.stem for p in (A / "data/keypoints3d").glob("*.pkl"))
    rows = []
    for n in allnames:                                          # index by position in the full list (stable seed); ignored sequences are marked, not dropped from the file
        i = allnames.index(n)
        r = one(i, n)
        r["ignored"] = int(n not in set(names))
        rows.append(r)
        if i % 100 == 0:
            print(i, n, flush=True)
    with open(CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("RUN DONE", len(rows), flush=True)


def read():
    with open(CSV) as f:
        return list(csv.DictReader(f))


def boot_groups(vals, groups, nb=2000, seed=47101):
    """mean over sequences with 95 % percentile bootstrap resampling whole groups (music IDs)"""
    ug = sorted(set(groups))
    g = np.array([np.mean([v for v, gg in zip(vals, groups) if gg == u]) for u in ug])
    w = np.array([sum(1 for gg in groups if gg == u) for u in ug])
    rng = np.random.default_rng(seed)
    b = []
    for _ in range(nb):
        s = rng.integers(len(ug), size=len(ug))
        b.append((g[s] * w[s]).sum() / w[s].sum())
    return np.percentile(b, 2.5), np.percentile(b, 97.5)


def report():
    from beatv_report import boot
    rows = [r for r in read() if not int(r["ignored"])]
    n_all = len(read())
    zf = zipfile.ZipFile(A / "splits/splits.zip")
    sets = {"full": None}
    for nm in ("crossmodal_test", "pose_test"):
        sets[nm] = set(zf.read(f"splits/{nm}.txt").decode().split())
    L = ["# AIST++ BAS cross-check report (rules: `docs/AIST_BAS_RULES.md`)", "",
         f"Sequences: {n_all} keypoints3d files, {n_all - len(rows)} dropped by the AIST++ ignore list, {len(rows)} used. Per-sequence values: `{CSV}`. BAS = mean over sequences; chance = shifted-beat chance (20 draws); difference = per-sequence BAS minus chance, "
         "mean with 95 % bootstrap over sequences [A] and over music IDs [B] (2,000 resamples, seed 47101). Report only; no verdict.", ""]
    for src in ("optim", "raw"):
        for v in VARIANTS:
            for tag in ("music", "kin"):
                L += [f"### motion `{src}`, constants `{v}`, BAS sum over {tag} beats", "", "| set | n seq | n music IDs | BAS | chance | difference [A: by sequence] | difference [B: by music ID] |", "|---|---|---|---|---|---|---|"]
                for sn, ss in sets.items():
                    rr = [r for r in rows if ss is None or r["seq"] in ss]
                    if not rr:
                        continue
                    b = np.array([float(r[f"bas_{tag}_{src}_{v}"]) for r in rr])
                    c = np.array([float(r[f"chance_{tag}_{src}_{v}"]) for r in rr])
                    ok = np.isfinite(b) & np.isfinite(c)
                    b, c = b[ok], c[ok]
                    ids = [r["music"] for r, k in zip(rr, ok) if k]
                    d = b - c
                    a = boot(d, np.mean)
                    lo, hi = boot_groups(list(d), ids)
                    L.append(f"| {sn} | {len(b)} | {len(set(ids))} | {b.mean():.4f} | {c.mean():.4f} | {a[0]:+.4f} [{a[1]:+.4f}, {a[2]:+.4f}] | {d.mean():+.4f} [{lo:+.4f}, {hi:+.4f}] |")
                L.append("")
    L += ["Mean music beats per second: " + f"{np.mean([float(r['n_music_beats']) / float(r['dur']) for r in rows]):.2f}; mean sequence duration {np.mean([float(r['dur']) for r in rows]):.1f} s.", ""]
    out = HERE.parents[1] / "docs/AIST_BAS_REPORT.md"
    out.write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    {"run": run, "report": report}[sys.argv[1]]()
