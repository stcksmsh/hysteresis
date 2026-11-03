#!/usr/bin/env bash
# Overseer watcher for one Hysteresis job (use with Monitor, timeout 30 min, re-arm on expiry).
#   watch_unit.sh UNIT LOG...   e.g. watch_unit.sh hyst-b7-train.service /secondary/hyst-data/brain/b7/train.log
# Emits: each new epoch line (val_score) in a short form; each new non-heartbeat line of non-JSON logs;
# unit end; stale logs (> 25 min); anon memory > 18 GB; OOM kills in the unit.
U=$1; shift; LOGS=("$@")
declare -A n0; for f in "${LOGS[@]}"; do n0[$f]=$(wc -l < "$f" 2>/dev/null || echo 0); done
ws=0; wm=0
while true; do
  for f in "${LOGS[@]}"; do
    n=$(wc -l < "$f" 2>/dev/null || echo 0)
    if [ "$n" -gt "${n0[$f]}" ]; then
      sed -n "$((n0[$f]+1)),${n}p" "$f" | grep -v '"heartbeat"' | python3 -c '
import sys,json
for l in sys.stdin:
    l=l.strip()
    try: d=json.loads(l)
    except Exception: print(l[:200]); continue
    if "val_score" in d: print("epoch",d["epoch"],"wall_s",round(d["wall_s"]),"val_score",round(d["val_score"],4),"best",d["best"],"val_nll",[round(v,3) for v in d["val_nll"]],"val_mse",[round(v,3) for v in d["val_mse"]])
    else: print(l[:200])'
      n0[$f]=$n
    fi
  done
  if ! systemctl --user is-active -q "$U"; then echo "UNIT ENDED: $U"; exit 0; fi
  newest=$(stat -c %Y "${LOGS[@]}" 2>/dev/null | sort -n | tail -1); age=$(( $(date +%s) - ${newest:-0} ))
  if [ $age -gt 1500 ] && [ $ws = 0 ]; then echo "STALE: logs unchanged ${age}s (check CPU before calling it a stall)"; ws=1; fi
  [ $age -le 1500 ] && ws=0
  d=$(find /sys/fs/cgroup -path "*$U" -type d 2>/dev/null | head -1)
  if [ -n "$d" ]; then
    a=$(grep '^anon ' "$d/memory.stat" | cut -d' ' -f2); o=$(grep '^oom_kill ' "$d/memory.events" | cut -d' ' -f2)
    [ "${o:-0}" != 0 ] && [ $wm -lt 2 ] && { echo "OOM KILL in $U"; wm=2; }
    [ "${a:-0}" -gt 19327352832 ] && [ $wm = 0 ] && { echo "ANON MEMORY HIGH: $a"; wm=1; }
  fi
  sleep 60
done
