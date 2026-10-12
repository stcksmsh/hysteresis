#!/usr/bin/env python3
"""Compute and cache per-clip features / embeddings for the emotion check.

  extract.py mix        20 Hz mix features of every clip        (cache/frames_mix)
  extract.py stems      Demucs + 20 Hz stem features             (cache/frames_stems)
  extract.py baseline   4 s window vectors of the above          (cache/emb/baseline_*)
  extract.py mert|clap|essentia   model embeddings               (cache/emb/<name>)

Every command is resumable (skips clips already cached) and writes a manifest.
Embedding files are (steps, dim) float16 (MERT: (steps, 13, 768)); step k is the
4 s window centred at centre0 + k * hop (see manifest.json).
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np

import common
from common import CACHE, HOP_SECONDS, WINDOW_SECONDS

MODELS_DIR = "/secondary/hyst-env/essentia-models"


def load_audio(path, sr, mono=True):
    import soundfile as sf
    import soxr
    audio, native = sf.read(str(path), dtype="float32", always_2d=True)
    if mono:
        audio = audio.mean(axis=1, keepdims=True)
    elif audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    if native != sr:
        audio = soxr.resample(audio, native, sr, quality="HQ")
    return audio[:, 0] if mono else audio


def emb_dir(name):
    path = CACHE / "emb" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_manifest(name, info, clips):
    common.write_json(emb_dir(name) / "manifest.json", dict(info, name=name, clips=clips))


def todo(directory, clips):
    return [(k, p) for k, p in clips if not (directory / f"{k}.npy").exists()]


# ------------------------------------------------------------------ mix

def _mix_one(item):
    import features
    key, path = item
    audio = load_audio(path, 44100)
    np.save(CACHE / "frames_mix" / f"{key}.npy", features.mix_frames(audio, 44100))
    return key


def cmd_mix(args):
    from multiprocessing import Pool
    (CACHE / "frames_mix").mkdir(parents=True, exist_ok=True)
    work = todo(CACHE / "frames_mix", common.all_clips())
    print(f"mix: {len(work)} clips to do", flush=True)
    with Pool(args.workers) as pool:
        for i, key in enumerate(pool.imap_unordered(_mix_one, work), 1):
            if i % 100 == 0:
                print(i, key, flush=True)


# ---------------------------------------------------------------- stems

def cmd_stems(args):
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    import features
    torch.set_num_threads(args.threads)
    model = get_model("htdemucs").eval()
    (CACHE / "frames_stems").mkdir(parents=True, exist_ok=True)
    work = todo(CACHE / "frames_stems", common.all_clips())
    print(f"stems: {len(work)} clips to do", flush=True)
    start = time.time()
    for i, (key, path) in enumerate(work, 1):
        wav = torch.from_numpy(load_audio(path, model.samplerate, mono=False).T.copy())
        ref = wav.mean(0)
        wav = (wav - ref.mean()) / max(float(ref.std()), 1e-8)
        with torch.no_grad():
            out = apply_model(model, wav[None], device="cpu", shifts=0, split=True, overlap=0.25, progress=False)[0]
        out = out * ref.std() + ref.mean()
        stems = {name: out[j].T.numpy() for j, name in enumerate(model.sources)}
        np.save(CACHE / "frames_stems" / f"{key}.npy", features.stem_frames(stems, model.samplerate))
        if i % 20 == 0:
            rate = (time.time() - start) / i
            print(f"{i}/{len(work)} {key} {rate:.1f}s/clip eta {rate * (len(work) - i) / 3600:.2f}h", flush=True)


# ------------------------------------------------------------- baseline

def cmd_baseline(args):
    import features
    for name, with_stems in (("baseline_mix", False), ("baseline_stems", True)):
        directory = emb_dir(name)
        clips, dim = [], None
        for key, _ in common.all_clips():
            mix_path = CACHE / "frames_mix" / f"{key}.npy"
            stem_path = CACHE / "frames_stems" / f"{key}.npy"
            if not mix_path.exists() or (with_stems and not stem_path.exists()):
                continue
            mix = np.load(mix_path)
            stems = np.load(stem_path) if with_stems else None
            duration = len(mix) / features.RATE
            centres = common.step_centres(duration)
            vectors = features.window_matrix(mix, stems, centres)
            np.save(directory / f"{key}.npy", vectors.astype(np.float16))
            clips.append({"key": key, "steps": len(vectors)})
            dim = vectors.shape[1]
        write_manifest(name, {"model": "sidecar-style features", "version": "1", "dim": dim,
                              "windowSeconds": WINDOW_SECONDS, "hopSeconds": HOP_SECONDS, "centre0": 0.0,
                              "stems": with_stems}, clips)
        print(name, len(clips), "clips, dim", dim)


# ----------------------------------------------------------------- MERT

MERT_NAME = "m-a-p/MERT-v1-95M"
MERT_RATE = 75.0


def mert_windows(hidden, hop=HOP_SECONDS, window=WINDOW_SECONDS):
    """hidden (layers, T, D) at 75 Hz -> (steps, layers, D): mean over 4 s windows, hop 0.5 s."""
    layers, total, dim = hidden.shape
    n_bins = int(np.ceil(total / (MERT_RATE * hop)))
    edges = np.minimum(np.round(np.arange(n_bins + 1) * MERT_RATE * hop).astype(int), total)
    edges = np.unique(edges)
    sums = np.add.reduceat(hidden, edges[:-1], axis=1)
    counts = np.diff(np.append(edges[:-1], total)).astype(np.float32)[None, :, None]
    sums = np.concatenate([np.zeros((layers, 1, dim), np.float32), np.cumsum(sums, axis=1)], axis=1)
    cum_n = np.concatenate([[0.0], np.cumsum(counts[0, :, 0])])
    half = int(round(window / 2 / hop))
    steps = n_bins
    out = np.empty((steps, layers, dim), np.float32)
    for k in range(steps):
        lo, hi = max(0, k - half), min(n_bins, k + half)
        hi = max(hi, lo + 1)
        out[k] = (sums[:, hi] - sums[:, lo]) / (cum_n[hi] - cum_n[lo])
    return out


def cmd_mert(args):
    import torch
    from transformers import AutoModel, Wav2Vec2FeatureExtractor
    torch.set_num_threads(args.threads)
    model = AutoModel.from_pretrained(MERT_NAME, trust_remote_code=True).eval()
    proc = Wav2Vec2FeatureExtractor.from_pretrained(MERT_NAME, trust_remote_code=True)
    directory = emb_dir("mert")
    work = todo(directory, common.all_clips())
    print(f"mert: {len(work)} clips to do", flush=True)
    start = time.time()
    for i, (key, path) in enumerate(work, 1):
        audio = load_audio(path, proc.sampling_rate)
        inputs = proc(audio, sampling_rate=proc.sampling_rate, return_tensors="pt")
        with torch.no_grad():
            hidden = torch.stack(model(**inputs, output_hidden_states=True).hidden_states)[:, 0].numpy()
        np.save(directory / f"{key}.npy", mert_windows(hidden).astype(np.float16))
        if i % 50 == 0:
            rate = (time.time() - start) / i
            print(f"{i}/{len(work)} {key} {rate:.1f}s/clip eta {rate * (len(work) - i) / 3600:.2f}h", flush=True)
    finish_manifest("mert", {"model": MERT_NAME, "version": "transformers 4.47.1, 13 hidden states",
                             "dim": 768, "layers": 13, "centre0": 0.0, "hopSeconds": HOP_SECONDS})


# ----------------------------------------------------------------- CLAP

CLAP_NAME = "laion/larger_clap_music"
CLAP_HOP = common.EVAL_STEP


def clap_centres(duration, hop=CLAP_HOP):
    c, out = hop, []
    while c + WINDOW_SECONDS / 2 <= duration + 1e-6:
        out.append(round(c, 6))
        c += hop
    return out


def clap_embed(model, proc, audio, sr, centres, batch=32):
    import torch
    half = int(WINDOW_SECONDS / 2 * sr)
    wins = [audio[max(0, int(c * sr) - half):int(c * sr) + half] for c in centres]
    out = []
    for i in range(0, len(wins), batch):
        inputs = proc(audios=wins[i:i + batch], sampling_rate=sr, return_tensors="pt")
        with torch.no_grad():
            out.append(model.get_audio_features(**inputs).numpy())
    return np.concatenate(out) if out else np.zeros((0, 512), np.float32)


def cmd_clap(args):
    import torch
    from transformers import ClapModel, ClapProcessor
    torch.set_num_threads(args.threads)
    model = ClapModel.from_pretrained(CLAP_NAME).eval()
    proc = ClapProcessor.from_pretrained(CLAP_NAME)
    directory = emb_dir("clap")
    work = todo(directory, common.all_clips())
    print(f"clap: {len(work)} clips to do", flush=True)
    start = time.time()
    for i, (key, path) in enumerate(work, 1):
        audio = load_audio(path, 48000)
        centres = clap_centres(len(audio) / 48000)
        np.save(directory / f"{key}.npy", clap_embed(model, proc, audio, 48000, centres).astype(np.float16))
        if i % 25 == 0:
            rate = (time.time() - start) / i
            print(f"{i}/{len(work)} {key} {rate:.1f}s/clip eta {rate * (len(work) - i) / 3600:.2f}h", flush=True)
    finish_manifest("clap", {"model": CLAP_NAME, "version": "transformers 4.47.1", "dim": 512,
                             "centre0": CLAP_HOP, "hopSeconds": CLAP_HOP})


# ------------------------------------------------------------- Essentia

EFFNET_PATCH_SECONDS = 128 * 256 / 16000
EFFNET_HOP_FRAMES = 31


def essentia_models():
    import essentia.standard as es
    embed = es.TensorflowPredictEffnetDiscogs(
        graphFilename=f"{MODELS_DIR}/discogs-effnet-bs64-1.pb", output="PartitionedCall:1",
        patchHopSize=EFFNET_HOP_FRAMES)
    mood = es.TensorflowPredict2D(
        graphFilename=f"{MODELS_DIR}/mtg_jamendo_moodtheme-discogs-effnet-1.pb",
        input="model/Placeholder", output="model/Sigmoid")
    return embed, mood


def essentia_windows(patches, centres, window=WINDOW_SECONDS):
    """Mean of patch vectors that lie inside each 4 s window (nearest patch if none)."""
    hop = EFFNET_HOP_FRAMES * 256 / 16000
    starts = np.arange(len(patches)) * hop
    out = np.empty((len(centres), patches.shape[1]), np.float32)
    for i, c in enumerate(centres):
        sel = np.where((starts >= c - window / 2 - 1e-6) & (starts + EFFNET_PATCH_SECONDS <= c + window / 2 + 1e-6))[0]
        if len(sel) == 0:
            sel = [int(np.argmin(np.abs(starts + EFFNET_PATCH_SECONDS / 2 - c)))]
        out[i] = patches[sel].mean(axis=0)
    return out


def cmd_essentia(args):
    embed, mood = essentia_models()
    d_embed, d_mood = emb_dir("essentia_effnet"), emb_dir("essentia_mood")
    work = todo(d_embed, common.all_clips())
    print(f"essentia: {len(work)} clips to do", flush=True)
    start = time.time()
    for i, (key, path) in enumerate(work, 1):
        audio = load_audio(path, 16000)
        patches = np.asarray(embed(audio))
        moods = np.asarray(mood(patches))
        centres = common.step_centres(len(audio) / 16000)
        np.save(d_mood / f"{key}.npy", essentia_windows(moods, centres).astype(np.float16))
        np.save(d_embed / f"{key}.npy", essentia_windows(patches, centres).astype(np.float16))
        if i % 100 == 0:
            rate = (time.time() - start) / i
            print(f"{i}/{len(work)} {key} {rate:.2f}s/clip", flush=True)
    finish_manifest("essentia_effnet", {"model": "Discogs-EffNet (discogs-effnet-bs64-1)", "version": "essentia-tensorflow 2.1b6.dev1389",
                                        "dim": 1280, "centre0": 0.0, "hopSeconds": HOP_SECONDS})
    finish_manifest("essentia_mood", {"model": "mtg_jamendo_moodtheme-discogs-effnet-1", "version": "essentia-tensorflow 2.1b6.dev1389",
                                      "dim": 56, "centre0": 0.0, "hopSeconds": HOP_SECONDS})


def finish_manifest(name, info):
    directory = emb_dir(name)
    clips = [p.stem for p in sorted(directory.glob("*.npy"))]
    common.write_json(directory / "manifest.json", dict(info, name=name, windowSeconds=WINDOW_SECONDS, clips=clips))


COMMANDS = {"mix": cmd_mix, "stems": cmd_stems, "baseline": cmd_baseline,
            "mert": cmd_mert, "clap": cmd_clap, "essentia": cmd_essentia}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    COMMANDS[args.command](args)
