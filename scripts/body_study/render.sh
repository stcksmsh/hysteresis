#!/bin/bash
# render.sh R6DIR: record the 108 clips of clips.tsv (8 s, silent, study camera, each
# at its stored stretch) into R6DIR/clips/, then copy each triplet's three clips of
# triplets.tsv to R6DIR/test/{tNN,pN}-{a,b,c}.mp4 (video stream copied, no audio, no
# metadata). Before any copy, every clip must pass check 2a (frame rule included,
# `body_study html`) and its stored stretch must be its ladder value (`body_study
# ladder`); otherwise the failures are listed and nothing is copied.
# Needs the release `body_study` example and R6DIR/silence.m4a (8 s of silence).
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
  node "$D/record-ensemble.cjs" "$R/clips/$name.html" "$R/silence.m4a" "$R/clips/$name.mp4" 0 8 > /dev/null
}
export -f one; export R D BS
cut -f1-4 "$R/clips.tsv" | xargs -P 6 -L 1 bash -c 'one "$@"' _
if [ -s "$R/clips/failed.txt" ]; then
  echo "clips failing their checks (nothing copied):"; cat "$R/clips/failed.txt"; exit 1
fi
while IFS=$'\t' read -r t a b c; do
  for k in a b c; do
    case $k in a) n=$a ;; b) n=$b ;; c) n=$c ;; esac
    ffmpeg -nostdin -y -v error -i "$R/clips/$n.mp4" -map 0:v -c:v copy -an -map_metadata -1 \
      -movflags +faststart "$R/test/$t-$k.mp4"
  done
done < "$R/triplets.tsv"
echo "$(ls "$R"/test/*-?.mp4 | wc -l) clips in $R/test"
