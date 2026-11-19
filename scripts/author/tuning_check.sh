#!/bin/bash
# tuning_check.sh: work order 6 phase 3. One 20 s window per song from example-sketch.json with retune.sh (default window start 100 s),
# the middle frame of each, duration and audio checks against the audio window, and a 720p copy under 30 MiB of each whole-song fallback video.
# Writes $OUT/check.json and $OUT/frames/*.png. Safe to run detached: systemd-run --user -p MemoryMax=6G -p MemorySwapMax=0 scripts/author/tuning_check.sh
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
A=/secondary/hyst-data/brain/author; OUT=${OUT:-$A/tuning}; F=$A/fallback; START=${START:-100}
export PATH=/secondary/hyst-env/brain/bin:$PATH
mkdir -p "$OUT/frames" "$OUT/720p"
dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }
RES=$OUT/check.json; echo '{' > "$RES"; first=1
for S in instant-crush five-years presence; do
  MP4=$("$HERE/retune.sh" "$S" "$HERE/mappings/example-sketch.json" "$START" 20 2>"$OUT/work/check-$S.err")
  VD=$(dur "$MP4")
  ffmpeg -v error -y -ss 10 -i "$MP4" -frames:v 1 "$OUT/frames/$S-window-mid.png"
  # the audio of the window vs the song's audio for the same window: same decoded samples (the window is re-encoded, so compare RMS of both, not bytes)
  R1=$(ffmpeg -v error -i "$MP4" -map 0:a -f wav - | python3 -I -c "import sys,io,wave,array,math;w=wave.open(io.BytesIO(sys.stdin.buffer.read()));a=array.array('h',w.readframes(w.getnframes()));print(round(math.sqrt(sum(x*x for x in a)/len(a)),1))")
  R2=$(ffmpeg -v error -ss $START -t 20 -i "$A/audio/$S.m4a" -f wav - | python3 -I -c "import sys,io,wave,array,math;w=wave.open(io.BytesIO(sys.stdin.buffer.read()));a=array.array('h',w.readframes(w.getnframes()));print(round(math.sqrt(sum(x*x for x in a)/len(a)),1))")
  # 720p copy of the whole-song fallback video, total size target 27 MiB
  FD=$(dur "$F/$S-fallback.mp4"); VK=$(python3 -I -c "print(int(27*8388.6/$FD-96))")
  C=$OUT/720p/$S-fallback-720p.mp4
  while :; do
    ffmpeg -v error -y -i "$F/$S-fallback.mp4" -vf scale=1280:720 -c:v libx264 -preset slow -b:v ${VK}k -maxrate $((VK*3/2))k -bufsize $((VK*3))k -pix_fmt yuv420p -c:a aac -b:a 96k -movflags +faststart "$C"
    SZ=$(stat -c %s "$C"); [ "$SZ" -lt 31457280 ] && break; VK=$((VK*9/10))
  done
  ffmpeg -v error -y -ss $(python3 -I -c "print($FD/2)") -i "$C" -frames:v 1 "$OUT/frames/$S-720p-mid.png"
  [ $first = 1 ] || echo ',' >> "$RES"; first=0
  printf '"%s": {"window_mp4": "%s", "window_s": %s, "audio_start": %s, "audio_window_rms": %s, "audio_source_rms": %s, "copy720": "%s", "copy720_bytes": %s, "copy720_s": %s, "whole_s": %s}\n' \
    "$S" "$MP4" "$VD" "$START" "$R1" "$R2" "$C" "$SZ" "$(dur "$C")" "$FD" >> "$RES"
done
echo '}' >> "$RES"
