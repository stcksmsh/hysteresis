#!/usr/bin/env python3
"""Ear features of the MERP songs for the mind spike (docs/NEXT_BODY_THEN_MIND.md, step 2).

For every MERP song longer than 50 s this writes the stage-1 pick's vector
(`baseline+all`, 2,665 per 0.5 s step) to CACHE/mind/merp/<song_id>.npy as float16
(steps, 2665), using the same component functions as `encode.py` run on the three
danced songs: whole-song Demucs stems for the baseline, MERT in 30 s chunks with 5 s
context each side, CLAP and Essentia on the whole song. The stems are written to a
scratch directory and deleted once the song's features are written.

This is model input, not a result. Resumable: songs with an existing .npy are skipped.

  python merp_features.py [--threads N] [--only SONG_ID ...]
"""
from __future__ import annotations

import argparse
import functools
import json
import shutil
import sys
import tempfile
import time

import numpy as np

import common
import encode
import extract

COMPONENTS = ("baseline_stems", "mert_avg", "clap", "essentia_effnet", "essentia_mood")
DIMS = (49, 768, 512, 1280, 56)
MIN_SECONDS = 50.0
MERP = common.DATA / "merp"
OUT = common.CACHE / "mind" / "merp"


def merp_songs(min_seconds=MIN_SECONDS):
    """[(song_id, seconds)] of the MERP songs longer than `min_seconds`, from the fetch manifest."""
    rows = [line.rstrip("\n").split("\t") for line in (MERP / "meta" / "audio_manifest.tsv").read_text().splitlines()[1:]]
    return sorted((r[0], float(r[5])) for r in rows if float(r[5]) > min_seconds)


def _cache_model_loaders():
    """encode.py reloads each model on every call; load each once per process instead."""
    import transformers
    for cls in (transformers.AutoModel, transformers.Wav2Vec2FeatureExtractor,
                transformers.ClapModel, transformers.ClapProcessor):
        cls.from_pretrained = functools.lru_cache(maxsize=None)(cls.from_pretrained)
    extract.essentia_models = functools.lru_cache(maxsize=None)(extract.essentia_models)


def write_stems(audio_path, directory, model):
    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    wav = torch.from_numpy(extract.load_audio(audio_path, model.samplerate, mono=False).T.copy())
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / max(float(ref.std()), 1e-8)
    with torch.no_grad():
        out = apply_model(model, wav[None], device="cpu", shifts=0, split=True, overlap=0.25, progress=False)[0]
    out = out * ref.std() + ref.mean()
    for j, name in enumerate(model.sources):
        sf.write(str(directory / f"{name}.wav"), out[j].T.numpy(), model.samplerate, subtype="FLOAT")


def song_vectors(audio_path, duration, stems_dir):
    centres = common.step_centres(duration)
    parts = []
    for name in COMPONENTS:
        fn = encode.COMPONENTS[name][0]
        matrix = np.asarray(fn(audio_path, duration, centres, stems_dir=stems_dir), dtype=np.float32)
        if len(matrix) != len(centres):
            raise ValueError(f"{name}: {len(matrix)} steps for {len(centres)} centres")
        parts.append(matrix)
    return np.concatenate(parts, axis=1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args(argv)
    import torch
    from demucs.pretrained import get_model
    import soundfile as sf
    torch.set_num_threads(args.threads)
    _cache_model_loaders()
    demucs = get_model("htdemucs").eval()
    OUT.mkdir(parents=True, exist_ok=True)
    songs = [s for s in merp_songs() if not args.only or s[0] in args.only]
    log = []
    start = time.time()
    for i, (song, _) in enumerate(songs, 1):
        target = OUT / f"{song}.npy"
        if target.exists():
            continue
        audio_path = MERP / "audio" / f"{song}.wav"
        duration = sf.info(str(audio_path)).frames / sf.info(str(audio_path)).samplerate
        t0 = time.time()
        scratch = tempfile.mkdtemp(prefix=f"merp_stems_{song}_", dir=str(common.CACHE))
        try:
            write_stems(audio_path, __import__("pathlib").Path(scratch), demucs)
            vectors = song_vectors(audio_path, duration, scratch)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        np.save(target, vectors.astype(np.float16))
        log.append({"song": song, "seconds": round(duration, 2), "steps": len(vectors), "runSeconds": round(time.time() - t0, 1)})
        print(f"{i}/{len(songs)} {song} {duration:.0f}s -> {vectors.shape} in {time.time() - t0:.0f}s", flush=True)
    done = sorted(p.stem for p in OUT.glob("*.npy"))
    common.write_json(OUT / "manifest.json", {
        "components": list(COMPONENTS), "dims": list(DIMS), "hopSeconds": common.HOP_SECONDS, "centre0": 0.0,
        "mode": "baseline_stems from whole-song Demucs htdemucs stems; MERT 30 s chunks with 5 s context; as encode.py",
        "songs": done, "totalRunSeconds": round(time.time() - start, 1), "log": log})


if __name__ == "__main__":
    main()
