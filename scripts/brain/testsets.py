"""Test sets for B1 (docs/BRAIN_SPEC.md 1.3), evaluation only: Ballroom and GTZAN (with Marchand's beat annotations).
SMC was not obtained (see /secondary/hyst-data/brain/testsets/SOURCES.md). Data lives outside git.

  python testsets.py hash     write scripts/brain/testsets/{ballroom,gtzan}.sha256 (sha256 of every audio and annotation file used)
  python testsets.py verify   check the files on disk against those lists
  python testsets.py dedupe   write testsets/gtzan_exact_duplicates.txt
"""
import hashlib
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

ROOT = "/secondary/hyst-data/brain/testsets"
HERE = os.path.dirname(os.path.abspath(__file__))
TRIPLE_STYLES = ("Waltz", "VienneseWaltz")  # BRAIN_SPEC 2.2 gate 3: the rest are duple


def ballroom_clips():
    """[{id, set, audio, beats, style}], sorted by id. Style = the folder of the audio; `nada` has no style label."""
    audio_root = f"{ROOT}/ballroom/audio/BallroomData"
    ann_root = f"{ROOT}/ballroom/annotations/BallroomAnnotations-master"
    out = []
    for style in sorted(os.listdir(audio_root)):
        d = os.path.join(audio_root, style)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith(".wav"):
                continue
            stem = name[:-4]
            beats = np.loadtxt(f"{ann_root}/{stem}.beats", usecols=0, ndmin=1)
            out.append({"id": f"ballroom/{stem}", "set": "ballroom", "audio": os.path.join(d, name), "beats": beats, "style": style})
    return sorted(out, key=lambda c: c["id"])


def gtzan_beats(path):
    """Beat times of one Marchand xml: markers whose beat number is not 0 (0 marks a tatum, the swing subdivision)."""
    beats = []
    for seg in ET.parse(path).getroot().iter():
        if seg.tag.endswith("segment"):
            child = list(seg)[0]
            if "beat" in child.attrib and int(child.get("beat")) != 0:
                beats.append(float(seg.get("time")))
    return np.array(beats)


GTZAN_SKIP = ("gtzan/jazz.00054",)   # does not decode (the known corrupt file); skipped, ruling 2026-10-29


def gtzan_removed_duplicates():
    """{removed id: kept id}: exact-duplicate audio (identical decoded samples), the first copy by id is kept.
    Read from testsets/gtzan_exact_duplicates.txt, written by `python testsets.py dedupe` and committed before any check."""
    path = os.path.join(HERE, "testsets", "gtzan_exact_duplicates.txt")
    if not os.path.exists(path):
        return {}
    return dict(line.split() for line in open(path) if line.strip() and not line.startswith("#"))


def gtzan_clips(all_files=False):
    """GTZAN clips. By default the exact duplicates (all but the first copy) and the undecodable file are left out;
    `all_files=True` returns every audio file (used for the hash list)."""
    clips = _gtzan_all()
    if all_files:
        return clips
    drop = set(gtzan_removed_duplicates()) | set(GTZAN_SKIP)
    return [c for c in clips if c["id"] not in drop]


def _gtzan_all():
    audio_root = f"{ROOT}/gtzan/audio/genres"
    ann_root = f"{ROOT}/gtzan/annotations/GTZAN-Rhythm_v2_ismir2015_lbd/xml"
    xml = {f: os.path.join(ann_root, kind, f) for kind in sorted(os.listdir(ann_root)) for f in os.listdir(os.path.join(ann_root, kind))}
    out = []
    for genre in sorted(os.listdir(audio_root)):
        d = os.path.join(audio_root, genre)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.endswith(".wav") and not name.startswith("._"):
                out.append({"id": f"gtzan/{name[:-4]}", "set": "gtzan", "audio": os.path.join(d, name),
                            "beats": gtzan_beats(xml[name + ".xml"]), "style": genre})
    return sorted(out, key=lambda c: c["id"])


def files_to_hash(name):
    """Every audio and annotation file a set uses, as paths relative to ROOT (macOS `._` and `.DS_Store` debris skipped)."""
    out = []
    if name == "ballroom":
        for c in ballroom_clips():
            out.append(os.path.relpath(c["audio"], ROOT))
            out.append(f"ballroom/annotations/BallroomAnnotations-master/{c['id'].split('/')[1]}.beats")
    else:
        ann = f"{ROOT}/gtzan/annotations/GTZAN-Rhythm_v2_ismir2015_lbd"
        for c in gtzan_clips(all_files=True):
            out.append(os.path.relpath(c["audio"], ROOT))
        for kind in sorted(os.listdir(f"{ann}/xml")):
            for f in sorted(os.listdir(f"{ann}/xml/{kind}")):
                out.append(f"gtzan/annotations/GTZAN-Rhythm_v2_ismir2015_lbd/xml/{kind}/{f}")
        out += [f"gtzan/annotations/GTZAN-Rhythm_v2_ismir2015_lbd/{f}" for f in ("stats.csv", "GTZANindex.txt", "README.txt")]
    return sorted(out)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def list_path(name):
    return os.path.join(HERE, "testsets", f"{name}.sha256")


def write_duplicates():
    """Exact-duplicate GTZAN audio by the sha256 of the decoded samples; first copy (lowest id) kept."""
    import soundfile as sf
    seen, lines = {}, ["# removed  kept   (exact duplicates by decoded samples; undecodable files are in GTZAN_SKIP)"]
    for c in gtzan_clips(all_files=True):
        if c["id"] in GTZAN_SKIP:
            continue
        digest = hashlib.sha256(sf.read(c["audio"], dtype="int16", always_2d=True)[0].tobytes()).hexdigest()
        if digest in seen:
            lines.append(f"{c['id']} {seen[digest]}")
        else:
            seen[digest] = c["id"]
    with open(os.path.join(HERE, "testsets", "gtzan_exact_duplicates.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print(len(lines) - 1, "exact duplicates listed")


def write_lists():
    for name in ("ballroom", "gtzan"):
        with open(list_path(name), "w") as f:
            for rel in files_to_hash(name):
                f.write(f"{sha256(os.path.join(ROOT, rel))}  {rel}\n")
        print(name, len(files_to_hash(name)), "files ->", list_path(name))


def verify_lists():
    bad = 0
    for name in ("ballroom", "gtzan"):
        for line in open(list_path(name)):
            digest, rel = line.rstrip("\n").split("  ", 1)
            if sha256(os.path.join(ROOT, rel)) != digest:
                print("MISMATCH", rel)
                bad += 1
    print("verified" if not bad else f"{bad} mismatches")
    return bad


if __name__ == "__main__":
    {"hash": write_lists, "verify": verify_lists, "dedupe": write_duplicates}[sys.argv[1]]()
