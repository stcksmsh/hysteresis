#!/bin/bash
# Work order 27: the Stage 3 side-car watcher. Cores 12-17 only (6-11 are the run's). Launch detached and memory-capped:
#   systemd-run --user --unit=hyst-wo27-watch-<fresh> -p MemoryMax=6G -p MemorySwapMax=0 --working-directory=<this dir> <this script>
cd "$(dirname "$0")" || exit 1
exec taskset -c 12-17 /secondary/hyst-env/body/bin/python -u s3_sidecar.py watch --run /secondary/hyst-data/body/s3/run --out /secondary/hyst-data/body/s3/run_report >> /secondary/hyst-data/body/s3/run_report/watch.log 2>&1
