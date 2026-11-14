#!/bin/bash
# dialstudy_render.sh [ID ...]   WO28A: render the gated clips of $W (work dir) to $C/<id>.mp4 (1280x720, 12 s, silent audio track).
#   $W/<id>.csv + $W/<id>.json come from `dialstudy.py gen`; a clip is rendered only if its json says gates.passed. Resume-safe. Waits on battery.
#   One-arm page: ensemble_preview --joint-csv; label text of the page blanked; recorder = scripts/author/record_ensemble.cjs (HYST_FAST=1: 1280x720).
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
D=/secondary/hyst-data/body/dialstudy; W=${DIAL_W:-$D/work}; C=${DIAL_C:-$D/clips}
export CARGO_TARGET_DIR=${CARGO_TARGET_DIR:-/secondary/hyst-data/cargo-target-dial}
mkdir -p "$C" "$W/pages"
IDS=("$@"); [ ${#IDS[@]} -gt 0 ] || IDS=($(cd "$W" && ls *.csv | sed 's/\.csv$//'))
one() {
  local id=$1
  while [ "$(cat /sys/class/power_supply/ADP1/online)" != 1 ]; do sleep 30; done
  [ -f "$C/$id.mp4" ] && return 0
  python3 -I -c "import json,sys; sys.exit(0 if json.load(open('$W/$id.json'))['gates']['passed'] else 1)" || { echo "$id: gates failed, not rendered" >&2; return 1; }
  local eff; eff=$(python3 -I -c "import json; print(json.load(open('$W/$id.json')).get('effector','ball'))")
  "$CARGO_TARGET_DIR/release/examples/ensemble_preview" "$W/pages/$id.html" "$W/silence12.m4a" --implement "$eff" --joint-csv "$W/$id.csv" > "$W/pages/$id.log" 2>&1 || { echo "$id page failed" >&2; return 1; }
  sed -i 's/K5 policy//g; s/joint CSV//g' "$W/pages/$id.html"
  HYST_FAST=1 node "$ROOT/scripts/author/record_ensemble.cjs" "$W/pages/$id.html" "$W/silence12.m4a" "$C/$id.mp4.part.mp4" > "$W/pages/$id.rec.log" 2>&1 && mv "$C/$id.mp4.part.mp4" "$C/$id.mp4" && echo "$id done"
}
export -f one; export W C ROOT CARGO_TARGET_DIR
printf '%s\n' "${IDS[@]}" | xargs -P 3 -I{} bash -c 'one {}'
