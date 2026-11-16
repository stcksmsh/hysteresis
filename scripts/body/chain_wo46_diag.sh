#!/bin/bash
# WO46 part 1: posture/gesture diagnostic as a detached capped unit (8 GB, cores 14-19). Resumable: re-run to continue.
D=/secondary/hyst-data/body/diag
W=$(cd "$(dirname "$0")" && pwd)
mkdir -p $D
systemd-run --user --unit=hyst-wo46-diag-$(date +%H%M%S) -p MemoryMax=8G -p MemorySwapMax=0 \
  -p StandardOutput=append:$D/log.txt -p StandardError=append:$D/err.txt --working-directory=$W \
  -E T1B_POST=2 taskset -c 14-19 /secondary/hyst-env/brain/bin/python -u diag_run.py 6
