#!/usr/bin/env python3
"""Feature cache for B3: per track the raw fast features (T, 44 float32, .npy) and the offline analysis grid's beats (.json), plus
manifest.json (id, audio, feats, beats, split) and stats.npz (mean, std of the training split). Idempotent: existing files are kept.

  prep_corpus.py corpus FINAL_LIST.csv [--hashes H] [--out DIR]
        the corpus builder's final list (columns id, split) with its features and statistics taken as they are:
        CORPUS/features/<id:06d>.npy, CORPUS/feature_stats.npz (+ .json with sha256_npz). Nothing is recomputed. Checks every file
        against the hashes (the list's own `sha256` column, of the audio, and/or --hashes in sha256sum format, `<hex>  <path>`, matched on the file name; a listed file with no hash entry fails)
        and the stats npz against feature_stats.json; then adds only the offline-grid beats (process pool) and writes DIR/manifest.json
        (default DIR = CORPUS). Train with --stats CORPUS/feature_stats.npz.
  prep_corpus.py mp3dir DIR OUT  every mp3 in DIR; the last 4 (sorted) are held out. Smoke use; 20 tracks of measure/mp3.
Beats: scripts/analyze analyze_mix (pure Python, about 8 s per 4 min track), so this runs in a process pool (WORKERS).
In `mp3dir` mode statistics are computed here (smoke test only); for the real corpus they come from the corpus builder.
"""
import csv
import hashlib
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import b2  # noqa: E402
from fast_features import SR, fast_features  # noqa: E402

CORPUS = Path("/secondary/hyst-data/brain/corpus")
WORKERS = 8


def one(job):
    tid, audio, out = job
    out = Path(out)
    f, g = out / "feats" / f"{tid}.npy", out / "grids" / f"{tid}.json"
    if f.exists() and g.exists():
        return tid
    from analyze.structure import analyze_mix
    from analyze.wav import DecodedWav
    y = b2.decode(audio)
    f.parent.mkdir(parents=True, exist_ok=True)
    g.parent.mkdir(parents=True, exist_ok=True)
    d = analyze_mix(DecodedWav(SR, [y], len(y) / SR))
    g.write_text(json.dumps({"beats": d["beats"], "tempo": d["tempo"]}))
    np.save(f, fast_features(y))
    return tid


def prep(tracks, out, workers=WORKERS):
    """tracks: [(id, audio path, split)] -> manifest list. Writes manifest.json and stats.npz in `out`."""
    out = Path(out)
    with Pool(workers) as p:
        done = set(p.map(one, [(t, str(a), str(out)) for t, a, _ in tracks], chunksize=1))
    manifest = [{"id": t, "audio": str(a), "feats": str(out / "feats" / f"{t}.npy"), "beats": str(out / "grids" / f"{t}.json"), "split": s}
                for t, a, s in tracks if t in done]
    n, s1, s2 = 0, 0.0, 0.0
    for m in manifest:
        if m["split"] == "train":
            f = np.load(m["feats"]).astype(np.float64)
            n, s1, s2 = n + len(f), s1 + f.sum(0), s2 + (f ** 2).sum(0)
    mean = s1 / n
    np.savez(out / "stats.npz", mean=mean, std=np.sqrt(np.maximum(s2 / n - mean ** 2, 0)))
    (out / "manifest.json").write_text(json.dumps(manifest))
    return manifest


def read_list(path):
    """Final list csv (columns id, split) -> [(id as 6 digits, split)]; the split is `train` or `heldout`."""
    rows = [(f"{int(r['id']):06d}", r["split"]) for r in csv.DictReader(open(path, newline=""))]
    bad = {s for _, s in rows} - {"train", "heldout"}
    if bad or not rows:
        raise ValueError(f"list: splits must be train or heldout, got {sorted(bad)}; rows {len(rows)}")
    return rows


def list_hashes(path):
    """The list's own `sha256` column (the builder's final_corpus.csv has one, of the audio files) -> {id.mp3: hex}; {} if absent."""
    return {f"{int(r['id']):06d}.mp3": r["sha256"].lower() for r in csv.DictReader(open(path, newline="")) if r.get("sha256")}


def read_hashes(path):
    """sha256sum-format file -> {file name: hex digest}."""
    out = {}
    for line in Path(path).read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            digest, name = line.split(None, 1)
            out[Path(name.strip().lstrip("*")).name] = digest.lower()
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify(rows, hashes, corpus=CORPUS, require=(".mp3",)):
    """Every list track must have its features file. Every file (features, audio) with a hash entry must match it, and an audio file
    must have one. Returns the number of files checked; raises ValueError listing what failed."""
    bad, n = [], 0
    for tid, _ in rows:
        feats = Path(corpus) / "features" / f"{tid}.npy"
        if not feats.exists():
            bad.append(f"missing features {tid}")
            continue
        for p in (feats, Path(corpus) / "audio" / f"{tid}.mp3"):
            if not p.exists():
                continue
            if p.name not in hashes:
                if p.suffix in require:
                    bad.append(f"no hash for {p.name}")
                continue
            if sha256(p) != hashes[p.name]:
                bad.append(f"hash mismatch {p.name}")
            n += 1
    if bad:
        raise ValueError(f"{len(bad)} problems, first: {bad[:5]}")
    return n


def verify_stats(corpus=CORPUS):
    """feature_stats.npz against the sha256 in feature_stats.json; returns the json."""
    meta = json.loads((Path(corpus) / "feature_stats.json").read_text())
    if sha256(Path(corpus) / "feature_stats.npz") != meta["sha256_npz"]:
        raise ValueError("feature_stats.npz does not match feature_stats.json")
    return meta


def grid_one(job):
    tid, audio, out = job
    g = Path(out) / "grids" / f"{tid}.json"
    if g.exists():
        return tid
    from analyze.structure import analyze_mix
    from analyze.wav import DecodedWav
    y = b2.decode(audio)
    g.parent.mkdir(parents=True, exist_ok=True)
    d = analyze_mix(DecodedWav(SR, [y], len(y) / SR))
    g.write_text(json.dumps({"beats": d["beats"], "tempo": d["tempo"]}))
    return tid


def prep_final(list_csv, hashes_path=None, out=CORPUS, corpus=CORPUS, workers=WORKERS):
    """The corpus builder's list, features and statistics as they are; adds the grids and the manifest. -> manifest list."""
    rows = read_list(list_csv)
    hashes = {**list_hashes(list_csv), **(read_hashes(hashes_path) if hashes_path else {})}
    if not hashes:
        raise ValueError("no hashes: the list has no sha256 column and no --hashes file was given")
    print(f"verified {verify(rows, hashes, corpus)} files against the committed hashes")
    verify_stats(corpus)
    out = Path(out)
    with Pool(workers) as p:
        p.map(grid_one, [(t, str(Path(corpus) / "audio" / f"{t}.mp3"), str(out)) for t, _ in rows], chunksize=1)
    manifest = [{"id": t, "audio": str(Path(corpus) / "audio" / f"{t}.mp3"), "feats": str(Path(corpus) / "features" / f"{t}.npy"),
                 "beats": str(out / "grids" / f"{t}.json"), "split": s} for t, s in rows]
    (out / "manifest.json").write_text(json.dumps(manifest))
    return manifest


def main(argv):
    if argv[0] == "corpus":
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("list")
        ap.add_argument("--hashes")
        ap.add_argument("--out", default=str(CORPUS))
        a = ap.parse_args(argv[1:])
        prep_final(a.list, a.hashes, a.out)
    elif argv[0] == "mp3dir":
        files = sorted(Path(argv[1]).glob("*.mp3"))
        prep([(p.stem, p, "heldout" if i >= len(files) - 4 else "train") for i, p in enumerate(files)], argv[2])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
