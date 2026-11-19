#!/bin/bash
# hf_fallback.sh: WO13A step 3, the fallback (authoring tool, example-sketch mapping) as a one-arm joint CSV. The sidecars are those retune.sh built
# (tuning/work/<song>-example-sketch.sidecar.json); compile as retune.sh does (--body layered --clock music) plus --score, then hyst score-csv --mode layered. Needs CARGO_TARGET_DIR (built by hf_v47.sh).
set -uo pipefail
: "${CARGO_TARGET_DIR:?set CARGO_TARGET_DIR}"
W=/secondary/hyst-data/brain/author/tuning/work; O=/secondary/hyst-data/body/hf/fallback; mkdir -p "$O"
X=$CARGO_TARGET_DIR/release/examples/ensemble_preview; H=$CARGO_TARGET_DIR/release/hyst
for S in instant-crush five-years presence; do
  $X "$O/$S.html" "../audio/$S.m4a" "$W/$S-example-sketch.sidecar.json" --body layered --clock music --score "$O/$S.score.json" > "$O/$S.log" 2>&1 || { echo "$S compile failed"; continue; }
  $H score-csv "$O/$S.score.json" "$O/$S.csv" --hz 50 --mode layered --agent 0 || echo "$S score-csv failed"
  echo "$S ok"
done
