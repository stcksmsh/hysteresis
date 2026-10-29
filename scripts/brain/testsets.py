"""Test sets for B1 (docs/BRAIN_SPEC.md 1.3), evaluation only: Ballroom and GTZAN (with Marchand's beat annotations).
SMC was not obtained (see /secondary/hyst-data/brain/testsets/SOURCES.md). Data lives outside git.

  python testsets.py hash     write scripts/brain/testsets/{ballroom,gtzan}.sha256 (sha256 of every audio and annotation file used)
  python testsets.py verify   check the files on disk against those lists
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


def gtzan_clips():
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
        for c in gtzan_clips():
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
    {"hash": write_lists, "verify": verify_lists}[sys.argv[1]]()
