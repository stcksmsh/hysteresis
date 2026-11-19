#!/bin/bash
# motornet_job.sh CMD...   run CMD pinned to cores 6-11, waiting for mains (WO29A). Use via systemd-run, see docs/MOTORNET_PARAMS.md.
while [ "$(cat /sys/class/power_supply/ADP1/online)" != 1 ]; do sleep 30; done
cd "$(dirname "$0")"
export OMP_NUM_THREADS=1 PATH=/secondary/hyst-env/body/bin:$PATH
exec taskset -c 6-11 "$@"
