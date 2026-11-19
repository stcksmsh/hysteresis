#!/bin/bash
# k5_render.sh [SONG ...]   (default: the three danced songs)  WO12 step 3: the K5 joint CSV drawn with the one-arm camera of the fallback videos.
#   page   = ensemble_preview --joint-csv (same page, camera, rig geometry, implement as `--body layered --clock music`), audio url as retune.sh
#   1080p  = scripts/author/record_ensemble.cjs, whole song, original audio stream copied     -> $V/<song>-k5.mp4
#   720p   = size loop of wo7_renders.sh (< 30 MiB)                                            -> $V/<song>-k5-720p.mp4
#   side   = fallback 720p (left) | K5 720p (right), 2560x720, audio of the fallback, < 30 MiB -> $V/<song>-side-by-side-720p.mp4
# Resume-safe: a finished file is kept. Waits while the machine is on battery. Run detached (see docs/NIGHT_LOG_body-k5video.md). K5_TEST="START DUR" renders only that window of the 1080p
# step into $V/test/ (HYST_FAST=1, nothing else is made).
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
K=/secondary/hyst-data/body/k5/danced; V=$K/video; A=/secondary/hyst-data/brain/author
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
(cd "$ROOT" && cargo build -q --release -p hyst-previz --example ensemble_preview) || exit 2
for S in "${SONGS[@]}"; do
  while [ "$(cat /sys/class/power_supply/ADP1/online)" != 1 ]; do sleep 30; done
  P=$V/work/$S-k5.html
  "$CARGO_TARGET_DIR/release/examples/ensemble_preview" "$P" "../audio/$S.m4a" --joint-csv "$K/$S.k5.csv" > "$V/work/$S-k5.log" 2>&1 || { echo "$S page failed" >&2; continue; }
  if [ -n "${K5_TEST:-}" ]; then
    HYST_FAST=1 node "$ROOT/scripts/author/record_ensemble.cjs" "$P" "$A/audio/$S.m4a" "$V/test/$S-k5-test.mp4" $K5_TEST > "$V/work/$S-test.log" 2>&1; echo "$V/test/$S-k5-test.mp4"; continue
  fi
  [ -f "$V/$S-k5.mp4" ] || { unset HYST_FAST; node "$ROOT/scripts/author/record_ensemble.cjs" "$P" "$A/audio/$S.m4a" "$V/$S-k5.mp4.part.mp4" > "$V/work/$S-record.log" 2>&1 && mv "$V/$S-k5.mp4.part.mp4" "$V/$S-k5.mp4"; }
  [ -f "$V/$S-k5.mp4" ] || { echo "$S render failed" >&2; continue; }
  [ -f "$V/$S-k5-720p.mp4" ] || mp4_720 "$V/$S-k5.mp4" "$V/$S-k5-720p.mp4"
  if [ ! -f "$V/$S-side-by-side-720p.mp4" ]; then
    FD=$(dur "$FB/$S-720p.mp4"); VK=$(python3 -I -c "print(int(27*8388.6/$FD-96))")
    while :; do
      ffmpeg -v error -y -i "$FB/$S-720p.mp4" -i "$V/$S-k5-720p.mp4" -filter_complex "[0:v][1:v]hstack=inputs=2[v]" -map "[v]" -map 0:a -c:v libx264 -preset slow -b:v ${VK}k -maxrate $((VK*3/2))k -bufsize $((VK*3))k -pix_fmt yuv420p -c:a aac -b:a 96k -shortest -movflags +faststart "$V/$S-side-by-side-720p.mp4"
      [ "$(stat -c %s "$V/$S-side-by-side-720p.mp4")" -lt 31457280 ] && break; VK=$((VK*9/10))
    done
  fi
  echo "$S done"
done
