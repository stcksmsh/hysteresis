#!/usr/bin/env python3
"""Plain HTML report for the stage-1 encoder (docs/EMOTION.md, "Report for the user").

Usage: python report.py OUT.html --components NAME ... --table TABLE.md [--table T2.md]
                        --song TITLE=ENCODED_SIDECAR [--song ...]

For every 10 s of each encoded song: the predicted GEMS profile (ridge fitted on
all Emotify clips) and the nearest labelled clips in the same encoding space
(cosine on library-standardised vectors): 3 from Emotify with their top GEMS
feelings, 3 from DEAM with their mean valence and arousal. Diagnostic only.
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib

import numpy as np

import check1
import common

SEGMENT = 10.0


def library(components):
    durations = check1.clip_durations()
    data = check1.build_index(durations)
    comp = {c: check1.load_component(c, data["deam_index"], data["emotify_index"]) for c in components}
    x_rows = np.concatenate([comp[c][0] for c in components], axis=-1)
    x_emo = np.concatenate([comp[c][1] for c in components], axis=-1)
    songs = np.unique(data["song"])
    x_deam = np.stack([x_rows[data["song"] == s].mean(axis=0) for s in songs])
    deam_label = np.stack([data["y"][data["song"] == s].mean(axis=0) for s in songs])
    return {"x_deam": x_deam, "deam_ids": songs, "deam_label": deam_label,
            "x_emo": x_emo, "emo_ids": data["tids"], "profile": data["profile"], "genre": data["genre"]}


def unit(v):
    v = v - 0.0
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


def top_feelings(profile, n=3):
    order = np.argsort(-profile)[:n]
    return ", ".join(f"{common.GEMS[i]} {profile[i]:.2f}" for i in order)


def analyse(lib, encoding):
    """Per 10 s segment: predicted profile and nearest library clips."""
    all_x = np.concatenate([lib["x_deam"], lib["x_emo"]])
    std = common.Standardizer().fit(all_x)
    deam, emo = std(lib["x_deam"]), std(lib["x_emo"])
    centre = np.concatenate([deam, emo]).mean(axis=0)
    deam_u, emo_u = unit(deam - centre), unit(emo - centre)
    alpha = common.choose_alpha(emo, lib["profile"], np.array(lib["emo_ids"]))
    model = common.ridge_fit(emo, lib["profile"], alpha)
    steps = np.asarray(encoding["steps"], dtype=np.float32)
    centres = np.arange(len(steps)) * encoding["hopSeconds"] + encoding.get("stepCentre0", 0.0)
    rows = []
    for t0 in np.arange(0.0, centres[-1], SEGMENT):
        sel = (centres >= t0) & (centres < t0 + SEGMENT)
        if not sel.any():
            continue
        q = std(steps[sel].mean(axis=0, keepdims=True))
        predicted = np.clip(common.ridge_predict(model, q)[0], 0, None)
        qu = unit(q - centre)[0]
        e_near = np.argsort(-(emo_u @ qu))[:3]
        d_near = np.argsort(-(deam_u @ qu))[:3]
        rows.append({
            "t": float(t0),
            "predicted": predicted,
            "emotify": [(lib["emo_ids"][i], lib["genre"][lib["emo_ids"][i]], lib["profile"][i]) for i in e_near],
            "deam": [(int(lib["deam_ids"][i]), lib["deam_label"][i]) for i in d_near],
        })
    return rows


def mmss(t):
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def render(songs, tables, components):
    out = ["<!doctype html><meta charset=utf-8><title>Emotion encoder, stage 1</title>",
           "<style>body{font:14px/1.4 sans-serif;max-width:1200px;margin:2em auto;padding:0 1em}"
           "table{border-collapse:collapse;margin:1em 0}td,th{border:1px solid #bbb;padding:3px 8px;vertical-align:top;text-align:left}"
           "pre{background:#f4f4f4;padding:.6em;overflow:auto}</style>",
           "<h1>Emotion encoder, stage 1</h1>",
           f"<p>Encoding: {html.escape(' + '.join(components))}. Windows 4 s, step 0.5 s. Each row below is the mean "
           "of the encoding over 10 s of the song, compared with labelled public clips (Emotify: felt GEMS fractions, "
           "DEAM: mean valence and arousal, -1 to 1). Predicted profile = ridge fitted on all 400 Emotify clips. "
           "Library clips are 45-60 s means, so a 10 s query is noisier than they are. Diagnostic only, not a pass or fail: "
           "tell me where it is wrong.</p>"]
    for title, table in tables:
        out.append(f"<h2>Check 1: {html.escape(title)}</h2><pre>{html.escape(table)}</pre>")
    for title, rows in songs:
        out.append(f"<h2>{html.escape(title)}</h2><table><tr><th>time<th>predicted GEMS (top 3)"
                   "<th>nearest Emotify (id, genre, top feelings)<th>nearest DEAM (id, valence / arousal)")
        for r in rows:
            emo = "<br>".join(f"#{i} {html.escape(g)}: {html.escape(top_feelings(p))}" for i, g, p in r["emotify"])
            deam = "<br>".join(f"#{i}: {v[0]:+.2f} / {v[1]:+.2f}" for i, v in r["deam"])
            out.append(f"<tr><td>{mmss(r['t'])}<td>{html.escape(top_feelings(r['predicted']))}<td>{emo}<td>{deam}")
        out.append("</table>")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out")
    parser.add_argument("--components", nargs="+", required=True)
    parser.add_argument("--table", action="append", default=[], help="LABEL=PATH of a check-1 table (markdown)")
    parser.add_argument("--song", action="append", required=True, help="TITLE=ENCODED_SIDECAR")
    args = parser.parse_args()
    lib = library(args.components)
    songs = []
    for spec in args.song:
        title, path = spec.split("=", 1)
        encoding = json.loads(pathlib.Path(path).read_text())["emotionEncoding"]
        if [c["name"] for c in encoding["components"]] != args.components:
            raise SystemExit(f"{path}: components differ from --components")
        songs.append((title, analyse(lib, encoding)))
    tables = []
    for spec in args.table:
        label, path = spec.split("=", 1)
        tables.append((label, pathlib.Path(path).read_text()))
    pathlib.Path(args.out).write_text(render(songs, tables, args.components))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
