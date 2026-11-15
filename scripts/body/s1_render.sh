#!/bin/bash
# s1_render.sh: WO40 render s1/work/S??_{orig,rebuild}.csv to s1/clips/*.mp4 exactly as lowpass_render.sh (lamp, v2p page patch, record_ensemble.cjs HYST_FAST=1, 1280x720, 20 s, window's music).
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
O=/secondary/hyst-data/body/s1; W=$O/work; C=$O/clips
export CARGO_TARGET_DIR=/secondary/hyst-data/cargo-target-dial
mkdir -p "$W/pages" "$C"
one() {
  local id=$1 clip=${1%%_*}
  [ -f "$C/$id.mp4" ] && return 0
  "$CARGO_TARGET_DIR/release/examples/ensemble_preview" "$W/pages/$id.raw.html" "$W/$clip.m4a" --implement lamp --joint-csv "$W/$id.csv" > "$W/pages/$id.log" 2>&1 || { echo "$id page failed" >&2; return 1; }
  sed -i 's/K5 policy//g; s/joint CSV//g' "$W/pages/$id.raw.html"
  (cd "$HERE" && /secondary/hyst-env/body/bin/python -I retarget_page.py "$W/pages/$id.raw.html" "$W/pages/$id.html") || { echo "$id page patch failed" >&2; return 1; }
  HYST_FAST=1 node "$ROOT/scripts/author/record_ensemble.cjs" "$W/pages/$id.html" "$W/$clip.m4a" "$C/$id.mp4.part.mp4" > "$W/pages/$id.rec.log" 2>&1 && mv "$C/$id.mp4.part.mp4" "$C/$id.mp4" && echo "$id done"
}
export -f one; export W C O ROOT HERE CARGO_TARGET_DIR
ls "$W"/S??_orig.csv "$W"/S??_rebuild.csv | xargs -n1 basename | sed 's/\.csv$//' | xargs -P 3 -I{} bash -c 'one {}'
