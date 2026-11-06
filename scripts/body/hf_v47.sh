#!/bin/bash
# hf_v47.sh: WO13A step 2. The v47 Off hexagon score of each danced song (the three commands of v47_regression.sh plus --score), the html cmp-ed with the stored export,
# each of the six arms exported with `hyst score-csv --mode off --agent N` to $O/v47/<song>-arm<N>.csv. Needs a fresh CARGO_TARGET_DIR under /secondary/hyst-data/.
# Then hf_reference.py computes (e). Resume-safe (rebuilds the small files, cheap).
set -uo pipefail
D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
: "${CARGO_TARGET_DIR:?set CARGO_TARGET_DIR}"
O=/secondary/hyst-data/body/hf; mkdir -p "$O/v47"
(cd "$ROOT" && cargo build -q --release -j 4 -p hyst-cli && cargo build -q --release -j 4 -p hyst-previz --example ensemble_preview) || exit 2
X=$CARGO_TARGET_DIR/release/examples/ensemble_preview; H=$CARGO_TARGET_DIR/release/hyst
run() {  # tag audio sidecar ref
  $X "$O/v47/$1.html" "$2" "$3" --ring 6,0.8 --score "$O/v47/$1.score.json" > /dev/null || return 1
  if cmp -s "$O/v47/$1.html" "$4"; then echo "$1 html identical"; else echo "$1 html DIFFERENT"; fi
  for n in 0 1 2 3 4 5; do $H score-csv "$O/v47/$1.score.json" "$O/v47/$1-arm$n.csv" --hz 50 --mode off --agent $n || return 1; done
}
run instant-crush instant-crush.m4a "$D/instant-crush.notes.sidecar.json" "$D/hexagon-47.html"
run five-years five-years.m4a "$D/five-years-steady.notes.sidecar.json" "$D/five-years-hexagon.html"
run presence presence.m4a "$D/presence.notes.sidecar.json" "$D/presence-hexagon.html"
