#!/bin/bash
# retarget_render.sh [ID ...]   WO32C: render the gated singles of work/ (CNN_V1, CNN_V2, CNN_R1S03) to clips/<id>.mp4 (1280x720, 20 s, the clip's FineDance music, v2p pillar page).
#   Round 1's recorder path (motornet_part3_render.sh): ensemble_preview --joint-csv, label text blanked, scripts/author/record_ensemble.cjs (HYST_FAST=1). Waits on battery. Resume-safe.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
O=/secondary/hyst-data/body/retarget_look; W=$O/work; C=$O/clips
export CARGO_TARGET_DIR=/secondary/hyst-data/cargo-target-dial
mkdir -p "$W/pages" "$C"
IDS=("$@"); [ ${#IDS[@]} -gt 0 ] || IDS=($(cd "$W" && ls C??_V?.json C??_R1S03.json | sed 's/\.json$//'))
one() {
  local id=$1 clip=${1%%_*}
  while [ "$(cat /sys/class/power_supply/ADP1/online)" != 1 ]; do sleep 30; done
  [ -f "$C/$id.mp4" ] && return 0
  python3 -I -c "import json,sys; sys.exit(0 if json.load(open('$W/$id.json'))['gates']['passed'] else 1)" || { echo "$id: gates failed, not rendered" >&2; return 1; }
  "$CARGO_TARGET_DIR/release/examples/ensemble_preview" "$W/pages/$id.raw.html" "$W/$clip.m4a" --implement lamp --joint-csv "$W/$id.csv" > "$W/pages/$id.log" 2>&1 || { echo "$id page failed" >&2; return 1; }
  sed -i 's/K5 policy//g; s/joint CSV//g' "$W/pages/$id.raw.html"
  (cd "$HERE" && /secondary/hyst-env/body/bin/python -I retarget_page.py "$W/pages/$id.raw.html" "$W/pages/$id.html") || { echo "$id page patch failed" >&2; return 1; }
  HYST_FAST=1 node "$ROOT/scripts/author/record_ensemble.cjs" "$W/pages/$id.html" "$W/$clip.m4a" "$C/$id.mp4.part.mp4" > "$W/pages/$id.rec.log" 2>&1 && mv "$C/$id.mp4.part.mp4" "$C/$id.mp4" && echo "$id done"
}
export -f one; export W C ROOT HERE CARGO_TARGET_DIR
printf '%s\n' "${IDS[@]}" | xargs -P 3 -I{} bash -c 'one {}'
