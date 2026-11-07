"""Pack corpus features into a portable, hashed folder (the private Kaggle dataset "hyst-features").

    python pack_features.py --manifest /secondary/hyst-data/brain/corpus/manifest.json \
        --stats /secondary/hyst-data/brain/corpus/feature_stats.npz --out /secondary/hyst-data/brain/pack/features \
        [--dtype float16] [--slug USER/hyst-features] [--splits train,heldout,val]

Input manifest: the JSON list written by prep_corpus.py, entries {id, audio, feats, beats, split, ...}.
Output folder:
    feats/<id>.npy      fast features, cast to --dtype (default float16; loaders must cast back to float32)
    beats/<id>.<ext>    the beats file, copied as is (if present)
    manifest.json       same entries, with feats/beats as paths RELATIVE to the folder and audio set to null
    feature_stats.npz   copied as is
    HYST_DATASET.json   {"name": "hyst-features", "dtype": ..., "n": ...}: lets launchers find the folder by search
    dataset-metadata.json   for `kaggle datasets create -p DIR` (private by default); written only with --slug
    MANIFEST.sha256     built last
Reports the float16 round-trip error (max abs, on standardised scale) so the cast is a measured choice.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest as mf  # noqa: E402


def pack(manifest_path, stats_path, out, dtype="float16", slug=None, splits=None):
    out = Path(out)
    (out / "feats").mkdir(parents=True, exist_ok=True)
    (out / "beats").mkdir(parents=True, exist_ok=True)
    entries = json.loads(Path(manifest_path).read_text())
    base = Path(manifest_path).resolve().parent
    stats = np.load(stats_path)
    mean = stats["mean"] if "mean" in stats else 0.0
    std = stats["std"] if "std" in stats else stats["sd"] if "sd" in stats else 1.0   # the corpus builder's file calls it `sd`
    new, max_err = [], 0.0
    for e in entries:
        if splits and e.get("split") not in splits:
            continue
        src = Path(e["feats"])
        src = src if src.is_absolute() else base / src
        x = np.load(src)
        y = x.astype(dtype)
        err = float(np.max(np.abs((y.astype(np.float32) - x) / np.where(std == 0, 1, std)))) if x.size else 0.0
        max_err = max(max_err, err)
        np.save(out / "feats" / f"{e['id']}.npy", y)
        ne = dict(e)
        ne["feats"] = f"feats/{e['id']}.npy"
        ne["audio"] = None
        if e.get("beats"):
            b = Path(e["beats"])
            b = b if b.is_absolute() else base / b
            dst = out / "beats" / f"{e['id']}{b.suffix}"
            shutil.copy2(b, dst)
            ne["beats"] = f"beats/{dst.name}"
        new.append(ne)
    (out / "manifest.json").write_text(json.dumps(new, indent=1))
    shutil.copy2(stats_path, out / "feature_stats.npz")
    (out / "HYST_DATASET.json").write_text(json.dumps({"name": "hyst-features", "dtype": dtype, "n": len(new),
                                                       "max_abs_cast_error_std_units": max_err}, indent=1))
    if slug:
        (out / "dataset-metadata.json").write_text(json.dumps(
            {"title": slug.split("/")[-1], "id": slug, "licenses": [{"name": "other"}]}, indent=1))
    mf.build(out)
    return len(new), max_err


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--stats", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dtype", default="float16", choices=["float16", "float32"])
    ap.add_argument("--slug")
    ap.add_argument("--splits", help="comma list; default all")
    a = ap.parse_args(argv)
    n, err = pack(a.manifest, a.stats, a.out, a.dtype, a.slug, a.splits.split(",") if a.splits else None)
    print(f"{n} tracks packed; max cast error {err:.2e} std units")
    return 0


if __name__ == "__main__":
    sys.exit(main())
