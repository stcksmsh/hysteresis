#!/bin/bash
# crops.sh R5DIR: cut A, B and C out of each R5DIR/test/tNN.mp4 into tNN-a/-b/-c.mp4
# (1280 x 720, x264 lossless qp 0, so the decoded pixels equal the stack's), then check
# every crop's decoded frames (framemd5) against its third of the stack.
set -euo pipefail
R=$1
bad=0
for s in "$R"/test/t[0-9][0-9].mp4; do
  for k in 0 1 2; do
    l=$(echo abc | cut -c$((k + 1)))
    c=${s%.mp4}-$l.mp4
    ffmpeg -nostdin -y -v error -i "$s" -vf "crop=1280:720:$((k * 1280)):0" -an -map_metadata -1 \
      -c:v libx264 -qp 0 -pix_fmt yuv420p -movflags +faststart "$c"
    a=$(ffmpeg -nostdin -v error -i "$s" -vf "crop=1280:720:$((k * 1280)):0" -f framemd5 - | grep -v '^#' | md5sum)
    b=$(ffmpeg -nostdin -v error -i "$c" -f framemd5 - | grep -v '^#' | md5sum)
    if [ "$a" != "$b" ]; then echo "MISMATCH $(basename "$c")"; bad=$((bad + 1)); fi
  done
done
echo "crops checked: $(ls "$R"/test/t*-?.mp4 | wc -l), mismatches: $bad"
[ $bad -eq 0 ]
