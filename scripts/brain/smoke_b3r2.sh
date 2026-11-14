#!/usr/bin/env bash
# One smoke setting inside a memory-capped scope, with the scope's MemoryPeak read before the scope ends.
#   bash smoke_b3r2.sh NAME BATCH [--grad-checkpoint]      e.g.  bash smoke_b3r2.sh a 8
set -uo pipefail
NAME=$1; BATCH=$2; shift 2
cd "$(dirname "$0")"
OUT=/secondary/hyst-data/brain/b3r2/smoke
mkdir -p "$OUT"
systemd-run --user --scope -p MemoryMax=20G -p MemorySwapMax=0 --unit="hyst-b3-r2smoke-$NAME" bash -c '
  /secondary/hyst-env/brain/bin/python -u smoke_b3r2.py --batch '"$BATCH"' '"$*"'
  echo "{\"memory_peak_bytes\": $(systemctl --user show hyst-b3-r2smoke-'"$NAME"'.scope -p MemoryPeak --value)}"
  ' 2>&1 | tee "$OUT/$NAME.log"
