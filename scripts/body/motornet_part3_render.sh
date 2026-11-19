#!/bin/bash
# motornet_part3_render.sh   WO29C: render the 10 gated Part 3 sims of work3/ to clips/<id>.mp4 (round 1's recorder and camera, lamp, the song's 12 s excerpt muxed).
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
W=/secondary/hyst-data/body/motornet_toy/work3; C=/secondary/hyst-data/body/motornet_toy/clips
export CARGO_TARGET_DIR=/secondary/hyst-data/cargo-target-dial
mkdir -p "$W/pages"
one() {
  local id=$1
  while [ "$(cat /sys/class/power_supply/ADP1/online)" != 1 ]; do sleep 30; done
  [ -f "$C/$id.mp4" ] && return 0
  local slug; slug=$(python3 -I -c "import json,sys; j=json.load(open('$W/$id.json')); sys.exit(1) if not j['gates']['passed'] else print(j['song'])") || { echo "$id gates failed" >&2; return 1; }
  "$CARGO_TARGET_DIR/release/examples/ensemble_preview" "$W/pages/$id.html" "$W/$slug.m4a" --implement lamp --joint-csv "$W/$id.csv" > "$W/pages/$id.log" 2>&1 || { echo "$id page failed" >&2; return 1; }
  sed -i 's/K5 policy//g; s/joint CSV//g' "$W/pages/$id.html"
  HYST_FAST=1 node "$ROOT/scripts/author/record_ensemble.cjs" "$W/pages/$id.html" "$W/$slug.m4a" "$C/$id.mp4.part.mp4" > "$W/pages/$id.rec.log" 2>&1 && mv "$C/$id.mp4.part.mp4" "$C/$id.mp4" && echo "$id done"
}
export -f one; export W C ROOT CARGO_TARGET_DIR
printf 'P3_%s\n' 1a 1b 2a 2b 3a 3b 4a 4b 5a 5b | xargs -P 3 -I{} bash -c 'one {}'
