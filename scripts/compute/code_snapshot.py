"""Snapshot the repo at a commit into a folder for the private Kaggle dataset "hyst-code".

    python code_snapshot.py --repo . --commit HEAD --out /secondary/hyst-data/pack/code [--slug USER/hyst-code]

Writes code.tar.gz (git archive of that commit: committed files only, so every run is reproducible from a hash),
COMMIT (the full hash), HYST_DATASET.json ({"name": "hyst-code", "commit": ...}), MANIFEST.sha256, and with --slug a
dataset-metadata.json. Upload: first time `kaggle datasets create -p OUT`, then `kaggle datasets version -p OUT -m <hash>`.
Refuses a dirty working tree unless --allow-dirty (uncommitted changes would not be in the archive anyway).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest as mf  # noqa: E402


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def snapshot(repo, commit, out, slug=None, allow_dirty=False):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not allow_dirty and git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("working tree has uncommitted changes; commit first or pass --allow-dirty")
    full = git(repo, "rev-parse", commit)
    subprocess.run(["git", "-C", str(repo), "archive", "--format=tar.gz", "-o", str((out / "code.tar.gz").resolve()), full],
                   check=True)
    (out / "COMMIT").write_text(full + "\n")
    (out / "HYST_DATASET.json").write_text(json.dumps({"name": "hyst-code", "commit": full}, indent=1))
    if slug:
        (out / "dataset-metadata.json").write_text(json.dumps(
            {"title": slug.split("/")[-1], "id": slug, "licenses": [{"name": "other"}]}, indent=1))
    mf.build(out)
    return full


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--commit", default="HEAD")
    ap.add_argument("--out", required=True)
    ap.add_argument("--slug")
    ap.add_argument("--allow-dirty", action="store_true")
    a = ap.parse_args(argv)
    print(snapshot(a.repo, a.commit, a.out, a.slug, a.allow_dirty))
    return 0


if __name__ == "__main__":
    sys.exit(main())
