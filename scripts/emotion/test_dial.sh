#!/bin/bash
# test_dial.sh: headless check of dial.html (format 2) over dial_serve.cjs on three synthetic 4 s songs.
# Never run on the real songs or on the user's dial.json.
set -euo pipefail
H=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/dl"
for i in 1 2 3; do
  ffmpeg -nostdin -v error -f lavfi -i "sine=frequency=$((220 * i)):duration=4:sample_rate=44100" -c:a aac -b:a 64k "$T/song$i.m4a"
done
cp "$H/dial.html" "$T/"
for f in dial.json dial2.json dial-ic-try1.json HOWTO.txt; do echo "{}" > "$T/$f"; done; echo x > "$T/other.m4a"
node "$H/dial_serve.cjs" "$T" 8792 > /dev/null & S=$!
trap 'kill $S; rm -rf "$T"' EXIT
until curl -s -o /dev/null http://127.0.0.1:8792/dial.html; do sleep 0.2; done
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
chk() { if [ "$1" = "$2" ]; then echo "ok serve: $3"; else echo "FAIL serve: $3 ($1)"; exit 1; fi; }
chk "$(code http://127.0.0.1:8792/)" 200 "/ gives the page"
chk "$(code -r 100-199 http://127.0.0.1:8792/song2.m4a)" 206 "byte ranges on songs"
chk "$(curl -s -r 100-199 http://127.0.0.1:8792/song2.m4a | cmp - <(tail -c +101 "$T/song2.m4a" | head -c 100) && echo same)" same "range bytes match the file"
for bad in dial.json dial2.json dial-ic-try1.json HOWTO.txt other.m4a song4.m4a dial_serve.cjs %2e%2e/dial.json song1.m4a/x; do
  chk "$(code "http://127.0.0.1:8792/$bad")" 404 "$bad refused"
done
chk "$(code -X POST http://127.0.0.1:8792/dial.html)" 404 "POST refused"
chk "$(ss -ltn | grep -c ':8792 ' )" 1 "one listener"
chk "$(ss -ltn | grep ':8792 ' | awk '{print $4}')" 127.0.0.1:8792 "loopback only"
node "$H/test_dial.cjs" "$T" http://127.0.0.1:8792/dial.html
