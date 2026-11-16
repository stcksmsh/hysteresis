#!/bin/bash
# t1b_run.sh IDX   start E1 seed IDX (1..3) as a detached unit on its 4 cores; resumable (rerun after a stop). Seeds 41101..41103, cores 6-9 / 10-13 / 14-17.
set -e
i=$1; seed=$((41100 + i)); a=$((2 + 4 * i)); b=$((a + 3))
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
mkdir -p /secondary/hyst-data/body/t1b/logs
systemd-run --user --unit=hyst-wo41-${UNIT_TAG:-e1b}-s$i -p MemoryMax=8G -p MemorySwapMax=0 -p AllowedCPUs=$a-$b --working-directory=$ROOT -- bash -c \
  "T1B_POST=2 /secondary/hyst-env/brain/bin/python -u scripts/body/t1b_train.py train $seed 4 >> /secondary/hyst-data/body/t1b/logs/e1_seed$seed.log 2>&1"
