#!/usr/bin/env python3
"""Add an additive `emotionEncoding` field to a sidecar (docs/EMOTION.md, stage 1).

Usage: python encode.py INPUT_SIDECAR AUDIO OUTPUT_SIDECAR --components NAME [NAME ...]
                        [--stems-dir DIR]

Components (those named by check 1's pick): baseline_mix, baseline_stems
(needs --stems-dir with vocals/drums/bass/other.wav), mert_avg, clap,
essentia_effnet, essentia_mood. Vectors are the raw concatenation of the
components, one per 0.5 s step (4 s window centred on the step), plus the mean
per beat. The input sidecar is never modified; OUTPUT must be a different file.
The planner reads nothing from this field yet.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

import common
import extract
import features

VERSION = 1
DURATION_TOLERANCE = 0.1
CHUNK_SECONDS = 30.0
CONTEXT_SECONDS = 5.0


def step_centres(duration):
    return common.step_centres(duration)


def baseline_mix(audio_path, duration, centres, **_):
    audio = extract.load_audio(audio_path, 44100)
    return features.window_matrix(features.mix_frames(audio, 44100), None, centres)


def baseline_stems(audio_path, duration, centres, stems_dir=None, **_):
    if stems_dir is None:
        raise ValueError("baseline_stems needs --stems-dir")
    import soundfile as sf
    mix = features.mix_frames(extract.load_audio(audio_path, 44100), 44100)
    stems = {}
    for name in features.SOURCES:
        audio, rate = sf.read(str(pathlib.Path(stems_dir) / f"{name}.wav"), dtype="float32", always_2d=True)
        if rate != 44100:
            raise ValueError(f"{name}.wav is {rate} Hz, expected 44100")
        stems[name] = audio
    frames = features.stem_frames(stems, 44100)
    n = min(len(mix), len(frames))
    return features.window_matrix(mix[:n], frames[:n], centres)


def _mert_hidden(audio_path):
    """MERT hidden states (13, T, 768) at 75 Hz, run in 30 s chunks with 5 s context."""
    import torch
    from transformers import AutoModel, Wav2Vec2FeatureExtractor
    model = AutoModel.from_pretrained(extract.MERT_NAME, trust_remote_code=True).eval()
    proc = Wav2Vec2FeatureExtractor.from_pretrained(extract.MERT_NAME, trust_remote_code=True)
    sr = proc.sampling_rate
    audio = extract.load_audio(audio_path, sr)
    chunk, ctx = int(CHUNK_SECONDS * sr), int(CONTEXT_SECONDS * sr)
    parts = []
    for start in range(0, len(audio), chunk):
        lo, hi = max(0, start - ctx), min(len(audio), start + chunk + ctx)
        inputs = proc(audio[lo:hi], sampling_rate=sr, return_tensors="pt")
        with torch.no_grad():
            hidden = torch.stack(model(**inputs, output_hidden_states=True).hidden_states)[:, 0].numpy()
        first = int(round((start - lo) / sr * extract.MERT_RATE))
        count = int(round(min(chunk, len(audio) - start) / sr * extract.MERT_RATE))
        parts.append(hidden[:, first:first + count])
    return np.concatenate(parts, axis=1)


def mert_avg(audio_path, duration, centres, **_):
    windows = extract.mert_windows(_mert_hidden(audio_path))   # (steps, 13, 768)
    return windows.mean(axis=1)[:len(centres)]


def clap(audio_path, duration, centres, **_):
    from transformers import ClapModel, ClapProcessor
    import torch
    model = ClapModel.from_pretrained(extract.CLAP_NAME).eval()
    proc = ClapProcessor.from_pretrained(extract.CLAP_NAME)
    audio = extract.load_audio(audio_path, 48000)
    return extract.clap_embed(model, proc, audio, 48000, centres)


def _essentia(audio_path, centres):
    embed, mood = extract.essentia_models()
    audio = extract.load_audio(audio_path, 16000)
    patches = np.asarray(embed(audio))
    return patches, np.asarray(mood(patches))


def essentia_effnet(audio_path, duration, centres, **_):
    return extract.essentia_windows(_essentia(audio_path, centres)[0], centres)


def essentia_mood(audio_path, duration, centres, **_):
    return extract.essentia_windows(_essentia(audio_path, centres)[1], centres)


COMPONENTS = {
    "baseline_mix": (baseline_mix, "sidecar-style features, mix only", "1"),
    "baseline_stems": (baseline_stems, "sidecar-style features with Demucs stems", "1"),
    "mert_avg": (mert_avg, extract.MERT_NAME + " (mean of 13 layers)", "transformers 4.47.1"),
    "clap": (clap, extract.CLAP_NAME, "transformers 4.47.1"),
    "essentia_effnet": (essentia_effnet, "Discogs-EffNet (discogs-effnet-bs64-1)", "essentia-tensorflow 2.1b6.dev1389"),
    "essentia_mood": (essentia_mood, "mtg_jamendo_moodtheme-discogs-effnet-1", "essentia-tensorflow 2.1b6.dev1389"),
}


def pool_per_beat(steps, centres, beats, duration):
    """Mean of the step vectors in [beat_i, beat_i+1); the nearest step if none fall inside."""
    centres = np.asarray(centres)
    edges = list(beats) + [duration]
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = np.where((centres >= lo) & (centres < hi))[0]
        if len(sel) == 0:
            sel = [int(np.argmin(np.abs(centres - (lo + hi) / 2)))]
        out.append(steps[sel].mean(axis=0))
    return np.stack(out) if out else np.zeros((0, steps.shape[1]), steps.dtype)


def build_encoding(sidecar, audio_path, components, stems_dir=None, window=common.WINDOW_SECONDS):
    duration = float(sidecar["duration"])
    centres = step_centres(duration)
    parts, info = [], []
    for name in components:
        fn, model, version = COMPONENTS[name]
        matrix = np.asarray(fn(audio_path, duration, centres, stems_dir=stems_dir), dtype=np.float32)
        if len(matrix) != len(centres):
            raise ValueError(f"{name}: {len(matrix)} steps for {len(centres)} centres")
        parts.append(matrix)
        info.append({"name": name, "model": model, "version": version, "dims": int(matrix.shape[1])})
    steps = np.concatenate(parts, axis=1)
    per_beat = pool_per_beat(steps, centres, sidecar.get("beats", []), duration)
    return {
        "version": VERSION,
        "model": "+".join(components),
        "components": info,
        "dims": int(steps.shape[1]),
        "hopSeconds": common.HOP_SECONDS,
        "windowSeconds": window,
        "stepCentre0": 0.0,
        "steps": np.round(steps, 4).tolist(),
        "perBeat": np.round(per_beat, 4).tolist(),
        "provenance": {
            "scale": "raw concatenation, not standardised; labelled-library statistics are applied by the report",
            "limits": "learned from public induced/perceived emotion labels; not a statement about this song's feeling",
            "audio": str(audio_path),
        },
    }


def encode_file(input_path, audio_path, output_path, components, stems_dir=None):
    input_path, output_path = pathlib.Path(input_path).resolve(), pathlib.Path(output_path).resolve()
    if input_path == output_path:
        raise ValueError("output must be a different file from the input sidecar")
    unknown = [c for c in components if c not in COMPONENTS]
    if unknown:
        raise ValueError(f"unknown components: {unknown}")
    sidecar = json.loads(input_path.read_text())
    if "emotionEncoding" in sidecar:
        raise ValueError("input sidecar already has emotionEncoding")
    import soundfile as sf
    info = sf.info(str(audio_path))
    if abs(info.frames / info.samplerate - float(sidecar["duration"])) > DURATION_TOLERANCE:
        raise ValueError("audio and sidecar duration differ by more than 100 ms")
    encoding = build_encoding(sidecar, audio_path, components, stems_dir)
    output_path.write_text(json.dumps(dict(sidecar, emotionEncoding=encoding), separators=(",", ":")))
    return encoding


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sidecar")
    parser.add_argument("audio")
    parser.add_argument("output")
    parser.add_argument("--components", nargs="+", required=True)
    parser.add_argument("--stems-dir")
    args = parser.parse_args(argv)
    encoding = encode_file(args.sidecar, args.audio, args.output, args.components, args.stems_dir)
    print(f"wrote {args.output}: {len(encoding['steps'])} steps x {encoding['dims']} dims, {len(encoding['perBeat'])} beats")


if __name__ == "__main__":
    main(sys.argv[1:])
