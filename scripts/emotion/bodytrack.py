#!/usr/bin/env python3
"""Add an additive `bodyTrack` field to a sidecar (docs/NEXT_DECODER_THEN_BRAIN.md, D3).

Usage: python bodytrack.py NOTES_SIDECAR MINDSTATE_SIDECAR MAP.npz OUTPUT_SIDECAR

NOTES_SIDECAR is the sidecar the planner reads (its `musicalMemory.phrases` are the phrases).
MINDSTATE_SIDECAR holds `mindState` (mindstate.py). MAP is a decoder map saved by `save_map`:
body = sigmoid(W lanes + b), lanes being the mean of the mood lanes (energy, power, rest...) over the
phrase, as the maps were fitted on the mean lanes of 8 s segments (decoder.Map.forward).
The output is NOTES_SIDECAR plus `bodyTrack`: per phrase the 15-value body vector in body.rs PARAMS
order. `authored` is written empty. The input is never modified; OUTPUT must be a different file.
The Rust reader is crates/hyst-compile/src/body_track.rs; the planner uses it only in
`BodyMode::Layered`.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

import common
from decoder import DIMS

VERSION = 1


def save_map(path, fitted, map_id):
    """Save a fitted decoder.Map as W (15, width), b (15) and a name for the sidecar."""
    np.savez_compressed(path, W=fitted.weights.detach().numpy().astype(np.float64),
                        b=fitted.b.detach().numpy().astype(np.float64), id=map_id)


def load_map(path):
    with np.load(path) as z:
        return np.asarray(z["W"], dtype=np.float64), np.asarray(z["b"], dtype=np.float64), str(z["id"])


def lane_matrix(mind):
    """(T, 2 + k) lanes in 0..1 of a mindState field: energy, power, rest..."""
    mood = mind["mood"]
    energy, power = np.asarray(mood["energy"], dtype=np.float64), np.asarray(mood["power"], dtype=np.float64)
    rest = np.asarray(mood["rest"], dtype=np.float64).reshape(len(energy), -1)
    return np.column_stack([energy, power, rest])


def bodies_of(lanes, w, b):
    """The map: sigmoid(W lanes + b) for each row of lanes."""
    return 1.0 / (1.0 + np.exp(-(np.asarray(lanes) @ w.T + b)))


def phrase_lanes(lanes, hop, phrases):
    """Mean lanes over the steps whose centre lies in each phrase [start, end); a phrase with no step
    centre in it (the pickup before the first beat) takes the step nearest its middle."""
    centres = np.arange(len(lanes)) * hop
    out = []
    for start, end in phrases:
        inside = (centres >= start) & (centres < end)
        if inside.any():
            out.append(lanes[inside].mean(axis=0))
        else:
            out.append(lanes[int(np.argmin(np.abs(centres - 0.5 * (start + end))))])
    return np.array(out)


def body_track(mind, w, b, map_id, phrases):
    """The `bodyTrack` object: phrases are (start, end) seconds in order."""
    lanes = lane_matrix(mind)
    if w.shape != (len(DIMS), lanes.shape[1]) or b.shape != (len(DIMS),):
        raise ValueError(f"map is {w.shape} but the mood has {lanes.shape[1]} lanes")
    if abs(mind["hopSeconds"] - common.HOP_SECONDS) > 1e-9:
        raise ValueError("mindState hop is not the 0.5 s grid")
    bodies = bodies_of(phrase_lanes(lanes, mind["hopSeconds"], phrases), w, b)
    return {
        "version": VERSION, "source": mind["source"], "map": map_id, "dims": list(DIMS),
        "phrases": [{"start": float(s), "end": float(e), "body": np.round(body, 6).tolist()}
                    for (s, e), body in zip(phrases, bodies)],
        "authored": [],
    }


def write(notes_path, mind_path, map_path, output_path):
    notes_path, output_path = pathlib.Path(notes_path).resolve(), pathlib.Path(output_path).resolve()
    if output_path in (notes_path, pathlib.Path(mind_path).resolve()):
        raise ValueError("output must be a different file from the inputs")
    sidecar = json.loads(notes_path.read_text())
    if "bodyTrack" in sidecar:
        raise ValueError("input sidecar already has bodyTrack")
    mind = json.loads(pathlib.Path(mind_path).read_text()).get("mindState")
    if mind is None:
        raise ValueError("mind sidecar has no mindState")
    phrases = [(p["start"], p["end"]) for p in sidecar["musicalMemory"]["phrases"]]
    w, b, map_id = load_map(map_path)
    field = body_track(mind, w, b, map_id, phrases)
    output_path.write_text(json.dumps(dict(sidecar, bodyTrack=field), separators=(",", ":")))
    return field


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sidecar")
    parser.add_argument("mindstate")
    parser.add_argument("map")
    parser.add_argument("output")
    args = parser.parse_args(argv)
    field = write(args.sidecar, args.mindstate, args.map, args.output)
    print(f"wrote {args.output}: {len(field['phrases'])} phrases, source {field['source']}, map {field['map']}")


if __name__ == "__main__":
    main(sys.argv[1:])
