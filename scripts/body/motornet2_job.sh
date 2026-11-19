#!/bin/bash
# motornet2_job.sh ENV SCRIPT [ARGS]   WO30B: run a script pinned to cores 6-11 (6 threads), waiting for mains. ENV = body | brain.
while [ "$(cat /sys/class/power_supply/ADP1/online)" != 1 ]; do sleep 30; done
cd "$(dirname "$0")"
env=$1; shift
export PATH=/secondary/hyst-env/$env/bin:$PATH
if [ "$env" = body ]; then export OMP_NUM_THREADS=1; else export OMP_NUM_THREADS=6; fi
exec taskset -c 6-11 python -u "$@"
