#!/usr/bin/env python3
"""Add an additive `mindState` field to a sidecar (docs/NEXT_DECODER_THEN_BRAIN.md, D1).

Usage: python mindstate.py INPUT_SIDECAR MODEL.npz OUTPUT_SIDECAR

INPUT_SIDECAR holds `emotionEncoding` (encode.py). MODEL is a mood model fitted by mood.py (the final
model that check3.py saves). The input sidecar is never modified; OUTPUT must be a different file.
events, authored, bands, pulse, surprise and neuromod are written empty; the Rust reader
(crates/hyst-compile/src/mind_state.rs) rejects anything else in version 1. The planner reads nothing
from this field yet.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

import common
import mood

VERSION = 1


def mind_state_field(model, steps):
    """The `mindState` object for one song's encoding steps (T, d)."""
    lanes = model.lanes(np.asarray(steps, dtype=np.float32))
    scale = model.lane_scale[:2 + model.k]
    return {
        "version": VERSION,
        "source": model.source,
        "hopSeconds": common.HOP_SECONDS,
        "smoothing": {"tauSeconds": mood.TAU_SECONDS, "lagSeconds": mood.LAG_SECONDS},
        "scale": {"energy": scale[0].tolist(), "power": scale[1].tolist(), "rest": scale[2:].tolist()},
        "mood": {"energy": np.round(lanes[:, 0], 5).tolist(), "power": np.round(lanes[:, 1], 5).tolist(),
                 "rest": np.round(lanes[:, 2:], 5).tolist()},
        "events": [], "authored": [],
        "bands": [], "pulse": [], "surprise": [], "neuromod": [],
    }


def write(input_path, model_path, output_path):
    input_path, output_path = pathlib.Path(input_path).resolve(), pathlib.Path(output_path).resolve()
    if input_path == output_path:
        raise ValueError("output must be a different file from the input sidecar")
    sidecar = json.loads(input_path.read_text())
    if "mindState" in sidecar:
        raise ValueError("input sidecar already has mindState")
    if "emotionEncoding" not in sidecar:
        raise ValueError("input sidecar has no emotionEncoding")
    field = mind_state_field(mood.MoodModel.load(model_path), sidecar["emotionEncoding"]["steps"])
    output_path.write_text(json.dumps(dict(sidecar, mindState=field), separators=(",", ":")))
    return field


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sidecar")
    parser.add_argument("model")
    parser.add_argument("output")
    args = parser.parse_args(argv)
    field = write(args.sidecar, args.model, args.output)
    print(f"wrote {args.output}: {len(field['mood']['energy'])} steps, {len(field['scale']['rest'])} rest lanes, source {field['source']}")


if __name__ == "__main__":
    main(sys.argv[1:])
