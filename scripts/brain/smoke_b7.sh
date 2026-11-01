#!/usr/bin/env bash
# One smoke setting inside a memory-capped scope, with the scope's MemoryPeak read before the scope ends.
#   bash smoke_b7.sh NAME identity
#   bash smoke_b7.sh NAME steps --model b7 --batch 8 [--grad-checkpoint]
set -uo pipefail
NAME=$1; shift
cd "$(dirname "$0")"
OUT=/secondary/hyst-data/brain/b7/smoke
mkdir -p "$OUT"
systemd-run --user --scope -p MemoryMax=20G -p MemorySwapMax=0 --unit="hyst-b7-smoke-$NAME" bash -c '
  /secondary/hyst-env/brain/bin/python -u smoke_b7.py '"$*"'
  echo "{\"memory_peak_bytes\": $(systemctl --user show hyst-b7-smoke-'"$NAME"'.scope -p MemoryPeak --value)}"
  ' 2>&1 | tee "$OUT/$NAME.log"
