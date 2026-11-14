#!/bin/bash
# v47_regression.sh [TAG]: the hexagon pages from THIS tree (the three commands of newsong/three.sh, without its measuring) must be byte-identical to the stored v47 exports.
# Needs CARGO_TARGET_DIR (fresh, under /secondary/hyst-data/). Prints "identical" or "DIFFERENT" per song; exit 1 if any differs.
set -uo pipefail
TAG=${1:-wo12}
D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
: "${CARGO_TARGET_DIR:?set CARGO_TARGET_DIR}"
OUT=${V47_OUT:-/secondary/hyst-data/body/k5/danced/v47}; mkdir -p "$OUT"
(cd "$ROOT" && cargo build -q --release -p hyst-previz --example ensemble_preview) || exit 2
X=$CARGO_TARGET_DIR/release/examples/ensemble_preview
$X "$OUT/$TAG-ic.html" instant-crush.m4a "$D/instant-crush.notes.sidecar.json" --ring 6,0.8 > /dev/null
$X "$OUT/$TAG-fy.html" five-years.m4a "$D/five-years-steady.notes.sidecar.json" --ring 6,0.8 > /dev/null
$X "$OUT/$TAG-pr.html" presence.m4a "$D/presence.notes.sidecar.json" --ring 6,0.8 > /dev/null
bad=0
for pair in ic:hexagon-47 fy:five-years-hexagon pr:presence-hexagon; do
  s=${pair%%:*}; ref=$D/${pair#*:}.html
  if cmp -s "$OUT/$TAG-$s.html" "$ref"; then echo "$s identical"; else echo "$s DIFFERENT"; bad=1; fi
done
exit $bad
