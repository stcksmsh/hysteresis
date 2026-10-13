#!/bin/bash
# render.sh R5DIR: record the 72 clips of clips.tsv (16 s, silent, study camera, each at
# its stored stretch) and stack each triplet of triplets.tsv as A | B | C into
# R5DIR/test/tNN.mp4. Before stacking, every clip must pass check 2a (frame rule
# included, `body_study html`) and its stored stretch must be its ladder value
# (`body_study ladder`); otherwise the failures are listed and nothing is stacked.
# Needs the release `body_study` example and R5DIR/silence.m4a (16 s of silence).
set -euo pipefail
R=$1
D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
BS=$(cd "$(dirname "$0")/../.." && pwd)/target/release/examples/body_study
mkdir -p "$R/clips" "$R/test"
: > "$R/clips/failed.txt"
one() {
  local name=$1 b=$2 seed=$3 s=$4
  if ! "$BS" ladder "$b" "$seed" "$s" > "$R/clips/$name.ladder.txt" 2>&1; then
    echo "$name ladder: $(cat "$R/clips/$name.ladder.txt")" >> "$R/clips/failed.txt"; return
  fi
  if ! "$BS" html "$R/clips/$name.html" silence.m4a "$b" "$seed" "$s" > "$R/clips/$name.txt" 2>&1; then
    echo "$name 2a: $(tail -1 "$R/clips/$name.txt")" >> "$R/clips/failed.txt"; return
  fi
  [ -s "$R/clips/$name.mp4" ] && return
  node "$D/record-ensemble.cjs" "$R/clips/$name.html" "$R/silence.m4a" "$R/clips/$name.mp4" 0 16 > /dev/null
}
export -f one; export R D BS
cut -f1-4 "$R/clips.tsv" | xargs -P 6 -L 1 bash -c 'one "$@"' _
if [ -s "$R/clips/failed.txt" ]; then
  echo "clips failing their checks (nothing stacked):"; cat "$R/clips/failed.txt"; exit 1
fi
while IFS=$'\t' read -r t a b c; do
  ffmpeg -nostdin -y -v error -i "$R/clips/$a.mp4" -i "$R/clips/$b.mp4" -i "$R/clips/$c.mp4" \
    -filter_complex "[0:v][1:v][2:v]hstack=inputs=3[v]" -map "[v]" -an -map_metadata -1 \
    -c:v libx264 -crf 20 -pix_fmt yuv420p -movflags +faststart "$R/test/$t.mp4"
done < "$R/triplets.tsv"
echo "24 triplets in $R/test"
