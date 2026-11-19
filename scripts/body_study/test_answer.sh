#!/bin/bash
# test_answer.sh: run answer.html (addendum 8) headless at 1366 x 768 on gray 3 s
# dummy clips for practice 1-4 and triplets 1-3 and 32.
set -euo pipefail
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/test" "$T/dl"
ffmpeg -nostdin -v error -f lavfi -i color=c=gray:s=1280x720:d=3:r=30 -c:v libx264 -pix_fmt yuv420p "$T/x.mp4"
for n in p1 p2 p3 p4 t01 t02 t03 t32; do for k in a b c; do cp "$T/x.mp4" "$T/test/$n-$k.mp4"; done; done
echo 'window.PRACTICE = {"odd": ["A", "B", "C", "A"]};' > "$T/test/practice.js"
cp "$(dirname "$0")/answer.html" "$T/"
node "$(dirname "$0")/test_answer.cjs" "$T"
# again over serve.cjs (byte ranges, whitelist); key.json must answer 404
echo '{}' > "$T/key.json"; rm -f "$T/dl/"*
node "$(dirname "$0")/serve.cjs" "$T" 8791 > /dev/null & S=$!
trap 'kill $S; rm -rf "$T"' EXIT
until curl -s -o /dev/null http://127.0.0.1:8791/answer.html; do sleep 0.2; done
[ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8791/key.json)" = 404 ] && echo "ok serve.cjs refuses key.json"
[ "$(curl -s -o /dev/null -w '%{http_code}' -r 100-199 http://127.0.0.1:8791/test/t01-a.mp4)" = 206 ] && echo "ok serve.cjs serves byte ranges"
[ "$(curl -s -o /dev/null -w '%{http_code}' -r 100-199 http://127.0.0.1:8791/test/p1-a.mp4)" = 206 ] && echo "ok serve.cjs serves practice clips"
[ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8791/test/practice.js)" = 200 ] && echo "ok serve.cjs serves practice.js"
node "$(dirname "$0")/test_answer.cjs" "$T" http://127.0.0.1:8791/answer.html
