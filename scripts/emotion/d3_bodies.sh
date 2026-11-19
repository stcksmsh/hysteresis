#!/bin/bash
# d3_bodies.sh FINAL_DIR OUT_DIR: bodyTrack sidecars of the three danced songs for both encodings.
# FINAL_DIR holds final_maps.py's output; OUT_DIR gets <song>.<encoding>.sidecar.json (the notes sidecar
# the planner reads, plus bodyTrack) and mind-<song>-<encoding>.json (the emotion sidecar plus mindState).
# Run from scripts/emotion with the emotion environment's python first on PATH.
set -eo pipefail
D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
FINAL=$1
OUT=$2
mkdir -p "$OUT"
for song in "ic instant-crush instant-crush" "fy five-years-steady five-years-steady" "pr presence presence"; do
  set -- $song
  for enc in stage1 baseline49; do
    python mindstate.py "$D/$3.emotion.sidecar.json" "$FINAL/$enc.model.npz" "$OUT/mind-$1-$enc.json"
    python bodytrack.py "$D/$2.notes.sidecar.json" "$OUT/mind-$1-$enc.json" "$FINAL/$enc.map.npz" "$OUT/$1.$enc.sidecar.json"
  done
done
