#!/bin/bash
# d3_export.sh BODIES_DIR: one-arm previews of the three songs: Off, and Layered with each encoding's
# bodyTrack (d3_bodies.sh output). Files go to $D/d3/<song>.<off|stage1|baseline49>.{html,score.json,txt}
# (the txt is the exporter's stderr: limits against body.rs, clock lag). Needs a release build of
# ensemble_preview in this worktree.
set -eo pipefail
D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
W=$(cd "$(dirname "$0")/../.." && pwd)
X=$W/target/release/examples/ensemble_preview
BODIES=$1
mkdir -p "$D/d3"
cd "$D/d3"
for song in "ic instant-crush.m4a instant-crush.notes.sidecar.json" "fy five-years.m4a five-years-steady.notes.sidecar.json" "pr presence.m4a presence.notes.sidecar.json"; do
  set -- $song
  "$X" "$D/d3/$1.off.html" "../$2" "$D/$3" --score "$D/d3/$1.off.score.json" > /dev/null 2> "$D/d3/$1.off.txt"
  for enc in stage1 baseline49; do
    "$X" "$D/d3/$1.$enc.html" "../$2" "$BODIES/$1.$enc.sidecar.json" --body layered --score "$D/d3/$1.$enc.score.json" > /dev/null 2> "$D/d3/$1.$enc.txt"
  done
done
