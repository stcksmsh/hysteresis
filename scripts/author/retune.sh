#!/bin/bash
# retune.sh SONG MAPPING.json [START_S DURATION_S]
#   SONG: instant-crush | five-years | presence.  MAPPING.json: a mapping saved or exported by the authoring page (or mappings/example-sketch.json).
# mapping -> bodyTrack -> attached to the interpreted sidecar -> one-arm preview page -> mp4 with the song's audio for that window.
# No START/DURATION: the whole song at 1080p, original audio copied (the full-quality render). With START and DURATION: that window, quick settings
# (1280x720, x264 veryfast, audio re-encoded). Set FULL=1 to keep 1080p for a window. Output: $OUT (default /secondary/hyst-data/brain/author/tuning).
# Needs build.py to have been run once (data.json). Prints the mp4 path and the seconds each step took.
set -euo pipefail
SONG=${1:?song}; MAP=${2:?mapping json}; START=${3:-}; DUR=${4:-}
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
A=/secondary/hyst-data/brain/author; OUT=${OUT:-$A/tuning}
M=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
export PATH=/secondary/hyst-env/brain/bin:$PATH
export CARGO_TARGET_DIR=${CARGO_TARGET_DIR:-/secondary/hyst-data/cargo-target-tuning}
case $SONG in
  instant-crush) SC=instant-crush.interpreted.sidecar.json; TM="";;
  five-years)    SC=five-years-steady.interpreted.sidecar.json; TM=$M/five-years.tempomap.json;;
  presence)      SC=presence.interpreted.sidecar.json; TM="";;
  *) echo "song must be instant-crush, five-years or presence" >&2; exit 2;;
esac
[ -f "$A/data.json" ] || { echo "run: python3 $HERE/build.py" >&2; exit 2; }
NAME=$(basename "$MAP" .json); TAG=$SONG-$NAME${START:+-${START}s-${DUR}s}
mkdir -p "$OUT/work"; W=$OUT/work/$TAG
T0=$(date +%s.%N); lap() { local n=$(date +%s.%N); printf "%-10s %6.1f s\n" "$1" "$(echo "$n - $T0" | bc)" >&2; T0=$n; }
node "$HERE/export_cli.cjs" "$MAP" "$A/data.json" "$SONG" phrase > "$W.bodytrack.json"
python3 "$HERE/attach.py" "$M/$SC" "$W.bodytrack.json" "$W.sidecar.json" > /dev/null; lap bodytrack
(cd "$ROOT" && cargo build -q --release -p hyst-previz --example ensemble_preview); lap build
"$CARGO_TARGET_DIR/release/examples/ensemble_preview" "$W.html" "../audio/$SONG.m4a" "$W.sidecar.json" --body layered --clock music > "$W.log" 2>&1; lap compile
if [ -n "$START" ]; then
  [ -n "$DUR" ] || DUR=20
  [ "${FULL:-0}" = 1 ] || export HYST_FAST=1
else
  unset HYST_FAST
fi
[ -z "$TM" ] || export HYST_TEMPO_MAP=$TM
MP4=$OUT/$TAG.mp4
node "$HERE/record_ensemble.cjs" "$W.html" "$A/audio/$SONG.m4a" "$MP4" ${START:+$START $DUR} > "$W.record.log"; lap render
echo "$MP4"
