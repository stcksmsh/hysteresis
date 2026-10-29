#!/usr/bin/env python3
"""Attach an exported bodyTrack to a sidecar, and optionally compile the arm preview.

usage: attach.py SIDECAR BODYTRACK.json OUT_SIDECAR [--preview OUT.html AUDIO_URL]

SIDECAR is the interpreted sidecar the planner reads. BODYTRACK.json is what the authoring page's Export writes
({"bodyTrack": {...}}, body_track.rs version 1). OUT_SIDECAR is SIDECAR plus that field; it must be a different file, and
SIDECAR must not already have a bodyTrack. With --preview it then runs, from the repo root:
  cargo run --release -p hyst-previz --example ensemble_preview -- OUT.html AUDIO_URL OUT_SIDECAR --body layered --clock music
AUDIO_URL is resolved relative to OUT.html (as in crates/hyst-previz/README.md); serve both with serve.py's range support.
"""
import json
import subprocess
import sys
from pathlib import Path

DIMS = ["curl_extension", "height", "arch", "time", "weight", "flow", "space", "succession_direction",
        "succession_delay", "initiation", "breath_depth", "breath_rate", "size", "energy", "rhythm"]


def check(track):
    """The same checks as body_track.rs parse, so a bad export fails here with a message."""
    if track.get("version") != 1 or track.get("dims") != DIMS or track.get("authored") != []:
        raise ValueError("bodyTrack: version, dims or authored is wrong")
    if not track.get("source") or not track.get("map"):
        raise ValueError("bodyTrack: source or map is missing")
    last = None
    for p in track["phrases"]:
        if not p["end"] > p["start"] or (last is not None and p["start"] < last - 1e-6):
            raise ValueError("bodyTrack: phrases must be in order, each ending after it starts")
        if len(p["body"]) != 15 or not all(0.0 <= v <= 1.0 for v in p["body"]):
            raise ValueError("bodyTrack: body needs 15 values in 0..1")
        last = p["end"]
    if not track["phrases"]:
        raise ValueError("bodyTrack: no phrases")
    return track


def attach(sidecar_path, track_path, out_path):
    sidecar_path, out_path = Path(sidecar_path).resolve(), Path(out_path).resolve()
    if out_path == sidecar_path:
        raise ValueError("output must be a different file from the input")
    sidecar = json.loads(sidecar_path.read_text())
    if "bodyTrack" in sidecar:
        raise ValueError("input sidecar already has bodyTrack")
    track = check(json.loads(Path(track_path).read_text())["bodyTrack"])
    out_path.write_text(json.dumps(dict(sidecar, bodyTrack=track), separators=(",", ":")))
    return track


def main(argv):
    preview = None
    if "--preview" in argv:
        i = argv.index("--preview")
        preview, argv = argv[i + 1:i + 3], argv[:i]
    if len(argv) != 3 or (preview is not None and len(preview) != 2):
        raise SystemExit(__doc__)
    track = attach(*argv)
    print(f"wrote {argv[2]} with {len(track['phrases'])} bodyTrack spans")
    if preview:
        root = Path(__file__).resolve().parents[2]
        cmd = ["cargo", "run", "--release", "-p", "hyst-previz", "--example", "ensemble_preview", "--",
               preview[0], preview[1], argv[2], "--body", "layered", "--clock", "music"]
        raise SystemExit(subprocess.run(cmd, cwd=root).returncode)


if __name__ == "__main__":
    main(sys.argv[1:])
