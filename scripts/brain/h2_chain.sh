#!/bin/bash
# try 2 of H2, then the frozen-H1 and oracle baselines, all three designs each (two at a time, 3 threads each)
cd "$(dirname "$0")"
bash h2_try.sh try2 h2 --k 16 --tau 0.02
bash h2_try.sh base frozen
bash h2_try.sh base oracle
