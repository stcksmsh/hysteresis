#!/bin/bash
# test_answer.sh: run answer.html (addendum 7) headless at 1366 x 768 on gray 3 s
# dummy clips for triplets 1-3 and 24 (lossless 4:4:4 H.264, as the real crops).
set -euo pipefail
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/test" "$T/dl"
ffmpeg -nostdin -v error -f lavfi -i color=c=gray:s=1280x720:d=3:r=30 -c:v libx264 -qp 0 -pix_fmt yuv420p "$T/x.mp4"
for n in 01 02 03 24; do for k in a b c; do cp "$T/x.mp4" "$T/test/t$n-$k.mp4"; done; done
cp "$(dirname "$0")/answer.html" "$T/"
node "$(dirname "$0")/test_answer.cjs" "$T"
# again over serve.cjs (byte ranges, whitelist); key.json must answer 404
echo '{}' > "$T/key.json"; rm -f "$T/dl/"*
node "$(dirname "$0")/serve.cjs" "$T" 8791 > /dev/null & S=$!
trap 'kill $S; rm -rf "$T"' EXIT
until curl -s -o /dev/null http://127.0.0.1:8791/answer.html; do sleep 0.2; done
[ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8791/key.json)" = 404 ] && echo "ok serve.cjs refuses key.json"
[ "$(curl -s -o /dev/null -w '%{http_code}' -r 100-199 http://127.0.0.1:8791/test/t01-a.mp4)" = 206 ] && echo "ok serve.cjs serves byte ranges"
node "$(dirname "$0")/test_answer.cjs" "$T" http://127.0.0.1:8791/answer.html
