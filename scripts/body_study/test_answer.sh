#!/bin/bash
# test_answer.sh: run answer.html headless at 1366 x 768 on 24 gray 1 s dummy videos.
# Checks: no horizontal scroll, A/B/C locked until the video ends, no replay,
# progress n / 24, the saved JSON, and no request outside test/.
set -euo pipefail
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/test" "$T/dl"
ffmpeg -v error -f lavfi -i color=c=gray:s=3840x720:d=1:r=30 -c:v libx264 -pix_fmt yuv420p "$T/x.mp4"
for n in $(seq -w 1 24); do cp "$T/x.mp4" "$T/test/t$n.mp4"; done
cp "$(dirname "$0")/answer.html" "$T/"
node "$(dirname "$0")/test_answer.cjs" "$T"
