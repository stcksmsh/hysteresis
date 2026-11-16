#!/bin/bash
# WO46 generic detached launcher (8 GB cap, cores 14-19). Usage: chain_wo47.sh NAME ENV SCRIPT [ARGS...]  (ENV = brain|body). Log: /secondary/hyst-data/body/beatv/NAME.log
NAME=$1; ENVN=$2; shift 2
D=/secondary/hyst-data/body/beatv
W=$(cd "$(dirname "$0")" && pwd)
mkdir -p $D
systemd-run --user --unit=hyst-wo47-$NAME-$(date +%H%M%S) -p MemoryMax=8G -p MemorySwapMax=0 \
  -p StandardOutput=append:$D/$NAME.log -p StandardError=append:$D/$NAME.err --working-directory=$W \
  -E T1B_POST=2 taskset -c 14-19 /secondary/hyst-env/$ENVN/bin/python -u "$@"
