#!/bin/bash
# Stand-in for `python -m demucs -n htdemucs -o OUT WAV`: copies existing stems so the TS and
# Python analyzers are fed identical stem WAVs. STEM_SRC = dir holding vocals/drums/bass/other.wav.
# Used as `python3` on PATH for the TS run and as $HYST_DEMUCS_PYTHON for the Python run.
out=$6; wav=$7
slug=$(basename "$wav" .wav)
mkdir -p "$out/htdemucs/$slug"
cp "$STEM_SRC"/{vocals,drums,bass,other}.wav "$out/htdemucs/$slug/"
