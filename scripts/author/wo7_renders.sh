#!/bin/bash
# wo7_renders.sh: wait for mains power, then render the three whole songs (1080p, example-sketch.json) with retune.sh and make a 720p copy
# under 30 MiB of each. Writes $OUT/wo7-renders.json when done. Run detached:
#   systemd-run --user --unit=hyst-wo7-cam-renders -p MemoryMax=6G -p MemorySwapMax=0 -p CPUQuota=600% scripts/author/wo7_renders.sh
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${OUT:-/secondary/hyst-data/brain/author/tuning}; export OUT
export PATH=/secondary/hyst-env/brain/bin:$PATH
export CARGO_TARGET_DIR=/secondary/hyst-data/cargo-target-wo7
mkdir -p "$OUT/720p-cam"
dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }
while [ "$(cat /sys/class/power_supply/ADP1/online)" != 1 ]; do sleep 30; done
RES=$OUT/wo7-renders.json; echo '{' > "$RES"; first=1
for S in instant-crush five-years presence; do
  MP4=$("$HERE/retune.sh" "$S" "$HERE/mappings/example-sketch.json" 2>"$OUT/work/wo7-$S.err") || { echo "$S failed" >&2; continue; }
  FD=$(dur "$MP4"); VK=$(python3 -I -c "print(int(27*8388.6/$FD-96))")
  C=$OUT/720p-cam/$S-720p.mp4
  while :; do
    ffmpeg -v error -y -i "$MP4" -vf scale=1280:720 -c:v libx264 -preset slow -b:v ${VK}k -maxrate $((VK*3/2))k -bufsize $((VK*3))k -pix_fmt yuv420p -c:a aac -b:a 96k -movflags +faststart "$C"
    SZ=$(stat -c %s "$C"); [ "$SZ" -lt 31457280 ] && break; VK=$((VK*9/10))
  done
  [ $first = 1 ] || echo ',' >> "$RES"; first=0
  printf '"%s": {"full": "%s", "full_bytes": %s, "full_s": %s, "p720": "%s", "p720_bytes": %s, "p720_s": %s}\n' \
    "$S" "$MP4" "$(stat -c %s "$MP4")" "$FD" "$C" "$SZ" "$(dur "$C")" >> "$RES"
done
echo '}' >> "$RES"
