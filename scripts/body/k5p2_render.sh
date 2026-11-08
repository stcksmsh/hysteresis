#!/bin/bash
# k5p2_render.sh [SONG ...]   (default: the three danced songs)  WO18 step 2: the K5-pass2 joint CSV (check/songs/<song>.pass2.csv) drawn with the one-arm camera of the fallback videos.
#   page   = ensemble_preview --joint-csv (same page, camera, rig geometry, implement as k5_render.sh); the page's label "K5 policy" is replaced by "K5-pass2 policy" (v47 panel: "v47 one arm")
#   1080p  = scripts/author/record_ensemble.cjs, whole song, original audio stream copied     -> $V/<song>-k5p2.mp4
#   720p   = size loop of wo7_renders.sh (< 30 MiB)                                            -> $V/<song>-k5p2-720p.mp4
#   v47    = the same page and recorder on the v47 hexagon's arm 0 (hf/v47/<song>-arm0.csv), 720p < 30 MiB (work file, used for the three-panel only)
#   three  = v47 one arm | fallback | K5-pass2, each 1280x720, 3840x720, audio of the fallback, < 30 MiB -> $V/<song>-three-panel-720p.mp4
# Resume-safe: a finished file is kept. Waits while the machine is on battery. Run detached with absolute paths. K5P2_TEST="START DUR" renders only that window of the pass2 1080p step into $V/test/.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
K=/secondary/hyst-data/body/k5p2/check/songs; V=/secondary/hyst-data/body/k5p2/video; A=/secondary/hyst-data/brain/author
HF=/secondary/hyst-data/body/hf/v47
FB=$A/tuning/720p-cam
export PATH=/secondary/hyst-env/brain/bin:$PATH
export CARGO_TARGET_DIR=${CARGO_TARGET_DIR:-/secondary/hyst-data/cargo-target-wo12}
mkdir -p "$V/work" "$V/test"
SONGS=("$@"); [ ${#SONGS[@]} -gt 0 ] || SONGS=(instant-crush five-years presence)
dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }
mp4_720() {  # IN OUT: size loop of wo7_renders.sh
  local FD VK SZ; FD=$(dur "$1"); VK=$(python3 -I -c "print(int(27*8388.6/$FD-96))")
  while :; do
    ffmpeg -v error -y -i "$1" -vf scale=1280:720 -c:v libx264 -preset slow -b:v ${VK}k -maxrate $((VK*3/2))k -bufsize $((VK*3))k -pix_fmt yuv420p -c:a aac -b:a 96k -movflags +faststart "$2"
    SZ=$(stat -c %s "$2"); [ "$SZ" -lt 31457280 ] && break; VK=$((VK*9/10))
  done
}
page() {  # CSV OUT_HTML LABEL SONG
  "$CARGO_TARGET_DIR/release/examples/ensemble_preview" "$2" "../audio/$4.m4a" --joint-csv "$1" > "$V/work/$4-$(basename "$2" .html).log" 2>&1 || return 1
  sed -i "s/K5 policy/$3/g" "$2"
}
(cd "$ROOT" && cargo build -q --release -p hyst-previz --example ensemble_preview) || exit 2
for S in "${SONGS[@]}"; do
  while [ "$(cat /sys/class/power_supply/ADP1/online)" != 1 ]; do sleep 30; done
  P=$V/work/$S-k5p2.html
  [ -f "$K/$S.pass2.csv" ] || { echo "$S: no pass2 csv" >&2; continue; }
  page "$K/$S.pass2.csv" "$P" "K5-pass2 policy" "$S" || { echo "$S page failed" >&2; continue; }
  if [ -n "${K5P2_TEST:-}" ]; then
    HYST_FAST=1 node "$ROOT/scripts/author/record_ensemble.cjs" "$P" "$A/audio/$S.m4a" "$V/test/$S-k5p2-test.mp4" $K5P2_TEST > "$V/work/$S-test.log" 2>&1; echo "$V/test/$S-k5p2-test.mp4"; continue
  fi
  [ -f "$V/$S-k5p2.mp4" ] || { unset HYST_FAST; node "$ROOT/scripts/author/record_ensemble.cjs" "$P" "$A/audio/$S.m4a" "$V/$S-k5p2.mp4.part.mp4" > "$V/work/$S-record.log" 2>&1 && mv "$V/$S-k5p2.mp4.part.mp4" "$V/$S-k5p2.mp4"; }
  [ -f "$V/$S-k5p2.mp4" ] || { echo "$S render failed" >&2; continue; }
  [ -f "$V/$S-k5p2-720p.mp4" ] || mp4_720 "$V/$S-k5p2.mp4" "$V/$S-k5p2-720p.mp4"
  if [ ! -f "$V/work/$S-v47-720p.mp4" ]; then
    page "$HF/$S-arm0.csv" "$V/work/$S-v47.html" "v47 one arm" "$S" || { echo "$S v47 page failed" >&2; continue; }
    unset HYST_FAST; node "$ROOT/scripts/author/record_ensemble.cjs" "$V/work/$S-v47.html" "$A/audio/$S.m4a" "$V/work/$S-v47.mp4" > "$V/work/$S-v47-record.log" 2>&1 || { echo "$S v47 render failed" >&2; continue; }
    mp4_720 "$V/work/$S-v47.mp4" "$V/work/$S-v47-720p.mp4"
  fi
  if [ ! -f "$V/$S-three-panel-720p.mp4" ]; then
    FD=$(dur "$FB/$S-720p.mp4"); VK=$(python3 -I -c "print(int(27*8388.6/$FD-96))")
    while :; do
      ffmpeg -v error -y -i "$V/work/$S-v47-720p.mp4" -i "$FB/$S-720p.mp4" -i "$V/$S-k5p2-720p.mp4" -filter_complex "[0:v][1:v][2:v]hstack=inputs=3[v]" -map "[v]" -map 1:a -c:v libx264 -preset slow -b:v ${VK}k -maxrate $((VK*3/2))k -bufsize $((VK*3))k -pix_fmt yuv420p -c:a aac -b:a 96k -shortest -movflags +faststart "$V/$S-three-panel-720p.mp4"
      [ "$(stat -c %s "$V/$S-three-panel-720p.mp4")" -lt 31457280 ] && break; VK=$((VK*9/10))
    done
  fi
  echo "$S done"
done
