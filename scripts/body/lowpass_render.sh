#!/bin/bash
# lowpass_render.sh ID ...   WO36: render the gated low-passed clips of lowpass/work (CNN_Vn.csv + .json) to lowpass/clips/<id>_LP.mp4, as the look-test clips were rendered
#   (retarget_render.sh path: ensemble_preview --joint-csv, lamp, retarget_page v2p patch, record_ensemble.cjs HYST_FAST=1: 1280x720, 20 s, the clip's FineDance music). Battery is fine (WO36).
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
O=/secondary/hyst-data/body/retarget_look; LP=$O/lowpass; W=$LP/work; C=$LP/clips
export CARGO_TARGET_DIR=/secondary/hyst-data/cargo-target-dial
mkdir -p "$W/pages" "$C"
one() {
  local id=$1 clip=${1%%_*}
  [ -f "$C/${id}_LP.mp4" ] && return 0
  python3 -I -c "import json,sys; sys.exit(0 if json.load(open('$W/$id.json'))['gates']['passed'] else 1)" || { echo "$id: gates failed, not rendered" >&2; return 1; }
  "$CARGO_TARGET_DIR/release/examples/ensemble_preview" "$W/pages/$id.raw.html" "$O/work/$clip.m4a" --implement lamp --joint-csv "$W/$id.csv" > "$W/pages/$id.log" 2>&1 || { echo "$id page failed" >&2; return 1; }
  sed -i 's/K5 policy//g; s/joint CSV//g' "$W/pages/$id.raw.html"
  (cd "$HERE" && /secondary/hyst-env/body/bin/python -I retarget_page.py "$W/pages/$id.raw.html" "$W/pages/$id.html") || { echo "$id page patch failed" >&2; return 1; }
  HYST_FAST=1 node "$ROOT/scripts/author/record_ensemble.cjs" "$W/pages/$id.html" "$O/work/$clip.m4a" "$C/${id}_LP.mp4.part.mp4" > "$W/pages/$id.rec.log" 2>&1 && mv "$C/${id}_LP.mp4.part.mp4" "$C/${id}_LP.mp4" && echo "$id done"
}
export -f one; export W C O ROOT HERE CARGO_TARGET_DIR
printf '%s\n' "$@" | xargs -P 3 -I{} bash -c 'one {}'
