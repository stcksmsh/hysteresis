#!/bin/bash
# usage: [DESIGNS="A B C"] [THREADS=3] h2_try.sh TRY MODE [extra toy_h2 args]; two designs at a time (one run peaks near 2.4 GB, the cap is 6 GB for the unit).
# logs in /secondary/hyst-data/brain/h2/
try=$1; mode=$2; shift 2
cd "$(dirname "$0")"
mkdir -p /secondary/hyst-data/brain/h2
go() { /secondary/hyst-env/brain/bin/python -u toy_h2.py $mode --design $1 --threads ${THREADS:-3} "${@:2}" > /secondary/hyst-data/brain/h2/${try}_${mode}_$1.log 2>&1; }
n=0
for d in ${DESIGNS:-A B C}; do
  go $d "$@" &
  n=$((n + 1))
  [ $((n % 2)) -eq 0 ] && wait
done
wait
exit 0
