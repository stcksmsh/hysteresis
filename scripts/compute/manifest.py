"""SHA-256 manifests for data that moves between machines.

    python manifest.py build DIR        writes DIR/MANIFEST.sha256 ("<hash>  <relative path>", sorted)
    python manifest.py verify DIR       exit 0 if every listed file exists with the same hash, else prints mismatches, exit 1

MANIFEST.sha256 itself and dataset-metadata.json (Kaggle consumes it on upload) are never listed or checked. No third-party dependencies.
"""
import hashlib
import sys
from pathlib import Path

NAME = "MANIFEST.sha256"
SKIP = (NAME, "dataset-metadata.json")


def sha256(path, block=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def build(root):
    root = Path(root)
    lines = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name not in SKIP and not p.name.endswith(".tmp"):
            lines.append(f"{sha256(p)}  {p.relative_to(root).as_posix()}")
    (root / NAME).write_text("\n".join(lines) + "\n")
    return len(lines)


def verify(root):
    root = Path(root)
    bad = []
    for line in (root / NAME).read_text().splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        if rel in SKIP:
            continue
        p = root / rel
        if not p.is_file():
            bad.append(f"missing {rel}")
        elif sha256(p) != digest:
            bad.append(f"changed {rel}")
    return bad


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] not in ("build", "verify"):
        print(__doc__)
        return 2
    if argv[0] == "build":
        print(f"{build(argv[1])} files hashed")
        return 0
    bad = verify(argv[1])
    for b in bad:
        print(b)
    print("OK" if not bad else f"{len(bad)} problems")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
