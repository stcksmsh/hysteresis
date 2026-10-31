"""B3 round 2 validation split (docs/BRAIN_SPEC.md 4.7): 10 % of the training artists, chosen at artist level with a fixed seed.

`val_split.py choose [CSV] [OUT.json]` reads the corpus list (columns id, split, artist_id), draws the artists from the training side only
(held-out artists are never read for this), and writes the artist list and their track ids. The JSON is committed (val_artists.json).
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

SEED = 20261105
FRAC = 0.10
CORPUS_CSV = Path("/secondary/hyst-data/brain/corpus/final_corpus.csv")
ARTISTS_JSON = Path(__file__).resolve().parent / "val_artists.json"


def choose(rows, seed=SEED, frac=FRAC):
    """rows: [(track_id, split, artist_id)] -> sorted artist ids: round(frac * n) of the training-side artists, drawn with `seed`."""
    artists = sorted({a for _, split, a in rows if split == "train"})
    k = max(1, round(frac * len(artists)))
    return sorted(int(a) for a in np.random.default_rng(seed).choice(artists, size=k, replace=False))


def track_ids(rows, artists):
    """Training-side track ids (ints) of the given artists."""
    a = set(artists)
    return sorted(int(t) for t, split, art in rows if split == "train" and int(art) in a)


def read_rows(path=CORPUS_CSV):
    with open(path, newline="") as f:
        return [(int(r["id"]), r["split"], int(r["artist_id"])) for r in csv.DictReader(f)]


def load(path=ARTISTS_JSON):
    """-> set of validation track ids (ints)."""
    return set(json.loads(Path(path).read_text())["track_ids"])


def split_tracks(tracks, val_ids):
    """Train tracks (Track objects whose id parses as an int) -> (fit side, validation side)."""
    fit = [t for t in tracks if int(t.id) not in val_ids]
    return fit, [t for t in tracks if int(t.id) in val_ids]


if __name__ == "__main__":
    csv_path = Path(sys.argv[2]) if len(sys.argv) > 2 else CORPUS_CSV
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else ARTISTS_JSON
    rows = read_rows(csv_path)
    arts = choose(rows)
    ids = track_ids(rows, arts)
    out.write_text(json.dumps({"seed": SEED, "frac": FRAC, "n_train_artists": len({a for _, s, a in rows if s == "train"}),
                               "artists": arts, "track_ids": ids}, indent=1) + "\n")
    print(f"{len(arts)} artists, {len(ids)} tracks -> {out}")
