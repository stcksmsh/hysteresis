#!/bin/bash
# usage: h2_try.sh TRY MODE [extra toy_h2 args]; designs A+B in parallel, then C (3 threads each; one run peaks near 2.4 GB, the cap is 6 GB for the unit).
# logs in /secondary/hyst-data/brain/h2/
try=$1; mode=$2; shift 2
cd "$(dirname "$0")"
mkdir -p /secondary/hyst-data/brain/h2
go() { /secondary/hyst-env/brain/bin/python -u toy_h2.py $mode --design $1 --threads 3 "${@:2}" > /secondary/hyst-data/brain/h2/${try}_${mode}_$1.log 2>&1; }
go A "$@" &
go B "$@" &
wait
go C "$@"
