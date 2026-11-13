#!/bin/bash
# motornet_part3_job.sh ENV STEP   WO29C: run motornet_part3.py STEP pinned to cores 6-11 (6 threads), waiting for mains. ENV = body | brain.
while [ "$(cat /sys/class/power_supply/ADP1/online)" != 1 ]; do sleep 30; done
cd "$(dirname "$0")"
export PATH=/secondary/hyst-env/$1/bin:$PATH
if [ "$1" = body ]; then export OMP_NUM_THREADS=1; else export OMP_NUM_THREADS=6; fi
exec taskset -c 6-11 python -u motornet_part3.py "$2"
