#!/bin/bash
# Launch the WO18 chain detached, 14 GB cap, mains only (the python steps wait for mains). Usage: k5p2_chain_launch.sh UNIT_SUFFIX. Same command (fresh suffix) resumes after a stop.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LOG=/secondary/hyst-data/body/k5p2/chain.log
systemd-run --user --unit=hyst-wo18-"$1" -p MemoryMax=14G -p MemorySwapMax=0 -p WorkingDirectory="$HERE" \
  -p StandardOutput=append:"$LOG" -p StandardError=append:"$LOG" -E PATH="$PATH" "$HERE/k5p2_chain.sh"
