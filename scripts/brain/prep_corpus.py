#!/usr/bin/env python3
"""Feature cache for B3: per track the raw fast features (T, 44 float32, .npy) and the offline analysis grid's beats (.json), plus
manifest.json (id, audio, feats, beats, split) and stats.npz (mean, std of the training split). Idempotent: existing files are kept.

  prep_corpus.py corpus  [OUT]   tracks of /secondary/hyst-data/brain/corpus/selection.csv whose audio file exists
  prep_corpus.py mp3dir DIR OUT  every mp3 in DIR; the last 4 (sorted) are held out. Smoke use; 20 tracks of measure/mp3.
Beats: scripts/analyze analyze_mix (pure Python, about 8 s per 4 min track), so this runs in a process pool (WORKERS).
Statistics are written here for the smoke test. The committed training-side statistics of the real corpus come from the corpus builder.
"""
import csv
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


def main(argv):
    if argv[0] == "corpus":
        out = Path(argv[1]) if len(argv) > 1 else CORPUS
        rows = [r for r in csv.DictReader(open(CORPUS / "selection.csv", newline="")) if (CORPUS / "audio" / f"{int(r['id']):06d}.mp3").exists()]
        prep([(f"{int(r['id']):06d}", CORPUS / "audio" / f"{int(r['id']):06d}.mp3", "heldout" if r["split"] == "heldout" else "train") for r in rows], out)
    elif argv[0] == "mp3dir":
        files = sorted(Path(argv[1]).glob("*.mp3"))
        prep([(p.stem, p, "heldout" if i >= len(files) - 4 else "train") for i, p in enumerate(files)], argv[2])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
