#!/bin/bash
# WO26B smoke test (Run test of test_s3_train): cores 12-17, one process. Launch detached and memory-capped:
#   systemd-run --user --unit=hyst-wo26b-smoke -p MemoryMax=14G -p MemorySwapMax=0 --working-directory=<this dir> <this script>
cd /secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f/scripts/body || exit 1
mkdir -p /secondary/hyst-data/body/s3/train_tests
exec taskset -c 12-17 /secondary/hyst-env/body/bin/python -u -m unittest -v test_s3_train.Run > /secondary/hyst-data/body/s3/train_tests/smoke.log 2>&1
