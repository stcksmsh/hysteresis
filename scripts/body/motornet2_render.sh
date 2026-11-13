#!/bin/bash
# motornet2_render.sh   WO30B: render the gated clips of motornet_toy2/work to clips/<id>.mp4 (round 1's recorder and camera, lamp, 30 s; Part B with the song's excerpt muxed).
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
W=/secondary/hyst-data/body/motornet_toy2/work; C=/secondary/hyst-data/body/motornet_toy2/clips
export CARGO_TARGET_DIR=/secondary/hyst-data/cargo-target-dial
mkdir -p "$W/pages" "$C"
one() {
  local id=$1
  while [ "$(cat /sys/class/power_supply/ADP1/online)" != 1 ]; do sleep 30; done
  [ -f "$C/$id.mp4" ] && return 0
  local aud; aud=$(python3 -I -c "import json,sys; j=json.load(open('$W/$id.json')); sys.exit(1) if not j['gates']['passed'] else print(j.get('song') or 'silence30')") || { echo "$id gates failed" >&2; return 1; }
  "$CARGO_TARGET_DIR/release/examples/ensemble_preview" "$W/pages/$id.html" "$W/$aud.m4a" --implement lamp --joint-csv "$W/$id.csv" > "$W/pages/$id.log" 2>&1 || { echo "$id page failed" >&2; return 1; }
  sed -i 's/K5 policy//g; s/joint CSV//g' "$W/pages/$id.html"
  HYST_FAST=1 node "$ROOT/scripts/author/record_ensemble.cjs" "$W/pages/$id.html" "$W/$aud.m4a" "$C/$id.mp4.part.mp4" > "$W/pages/$id.rec.log" 2>&1 && mv "$C/$id.mp4.part.mp4" "$C/$id.mp4" && echo "$id done"
}
export -f one; export W C ROOT CARGO_TARGET_DIR
{ printf 'A_S%02d\n' 1 2 3 4 5 6 7 8; for n in 1 2 3 4 5; do echo B${n}_new; echo B${n}_s03; done; } | xargs -P 3 -I{} bash -c 'one {}'
