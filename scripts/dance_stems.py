#!/usr/bin/env python3
"""Add estimated-stem activity evidence to an existing sidecar.

Usage: python3 scripts/dance_stems.py INPUT_SIDECAR STEM_DIR OUTPUT_SIDECAR EVIDENCE

STEM_DIR must contain vocals.wav, drums.wav, bass.wav, and other.wav. These are
source-separation estimates, not ground-truth isolated recordings.
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

import numpy as np
import soundfile as sf
from scipy.ndimage import median_filter, uniform_filter1d

SOURCES = ("vocals", "drums", "bass", "other")
FFT_LIMIT = 2048
SEPARATION_METADATA = (
    "model", "demucsVersion", "torchVersion", "torchaudioVersion", "device",
    "shifts", "clipMode", "outputFormat", "inputSource", "inputFile",
    "inputSha256", "weightsSha256",
)


def _validate_paths(sidecar_path, stem_dir, output_path, evidence_path):
    sidecar_path, output_path, evidence_path = map(
        lambda path: pathlib.Path(path).resolve(), (sidecar_path, output_path, evidence_path)
    )
    stem_dir = pathlib.Path(stem_dir).resolve()
    if output_path in (sidecar_path, evidence_path) or evidence_path == sidecar_path:
        raise ValueError("input sidecar, output sidecar, and evidence paths must be distinct")
    for path in (output_path, evidence_path):
        if path.parent == stem_dir or stem_dir in path.parents:
            raise ValueError("outputs must not overwrite or be placed inside stem directory")


def analyze(sidecar, stem_dir):
    """Return additive `stemInterpretation` and compact audit evidence."""
    try:
        duration = float(sidecar["duration"])
        rate = float(sidecar["envelopeRate"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("sidecar requires numeric duration and envelopeRate") from error
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("sidecar duration must be finite and positive")
    if not math.isfinite(rate) or not 0 < rate <= 1000:
        raise ValueError("sidecar envelopeRate must be finite, >0 and <=1000")

    stem_dir = pathlib.Path(stem_dir)
    separation = _read_separation_manifest(stem_dir)
    paths = {name: stem_dir / f"{name}.wav" for name in SOURCES}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise ValueError("missing estimated stem WAV(s): " + ", ".join(missing))

    infos = {name: sf.info(path) for name, path in paths.items()}
    sample_rates = {info.samplerate for info in infos.values()}
    frame_counts = {info.frames for info in infos.values()}
    if len(sample_rates) != 1:
        raise ValueError("stem WAV sample rates must match")
    if len(frame_counts) != 1:
        raise ValueError("stem WAV frame counts must match")
    sample_rate = next(iter(sample_rates))
    frame_count = next(iter(frame_counts))
    if sample_rate <= 0 or frame_count <= 0:
        raise ValueError("stem WAVs must contain audio frames")
    audio_duration = frame_count / sample_rate
    if abs(audio_duration - duration) > 0.1:
        raise ValueError("stem WAV and sidecar duration mismatch (>100 ms)")

    frame_total = int(math.ceil(duration * rate))
    nfft = 2 ** int(math.floor(math.log2(min(FFT_LIMIT, sample_rate))))
    if nfft < 128:
        raise ValueError("stem WAV sample rate is too low for spectral analysis")
    window = np.hanning(nfft).astype(np.float32)
    result = {}
    source_evidence = {}
    for name, path in paths.items():
        audio, actual_rate = sf.read(path, dtype="float32", always_2d=True)
        if actual_rate != sample_rate or len(audio) != frame_count:
            raise ValueError(f"{name} stem changed while being read")
        if not np.isfinite(audio).all():
            raise ValueError(f"{name} stem contains non-finite samples")

        rms = np.empty(frame_total, dtype=np.float32)
        clipped_fraction = float(np.mean(np.abs(audio) >= 0.99))
        peak_absolute = float(np.max(np.abs(audio)))
        flux = np.zeros(frame_total, dtype=np.float32)
        previous = None
        for index in range(frame_total):
            left = min(frame_count, round(index * sample_rate / rate))
            right = min(frame_count, round((index + 1) * sample_rate / rate))
            block = audio[left:right]
            rms[index] = np.sqrt(np.mean(np.square(block, dtype=np.float32))) if len(block) else 0.0

            center = round((index + 0.5) * sample_rate / rate)
            first = center - nfft // 2
            lo, hi = max(0, first), min(frame_count, first + nfft)
            frame = np.zeros((nfft, audio.shape[1]), dtype=np.float32)
            if hi > lo:
                frame[lo - first : hi - first] = audio[lo:hi]
            spectrum = np.fft.rfft(frame * window[:, None], axis=0)
            magnitude = np.log1p(np.sqrt(np.mean(np.abs(spectrum) ** 2, axis=1)))
            if previous is not None:
                flux[index] = np.maximum(0.0, magnitude - previous).sum(dtype=np.float64)
            previous = magnitude

        rms_scale = float(np.percentile(rms, 95)) if len(rms) else 0.0
        activity = np.clip(rms / max(rms_scale, 1e-12), 0.0, 1.0).astype(np.float32)
        flux_scale = float(np.percentile(flux, 95)) if np.any(flux) else 0.0
        flux_norm = np.clip(flux / max(flux_scale, 1e-12), 0.0, 1.0).astype(np.float32)
        positive_flux = flux[flux > 0]
        flux_peak = float(np.percentile(positive_flux, 90)) if len(positive_flux) else 0.0
        impulses = (flux >= flux_peak).astype(np.float32) if flux_peak > 0 else np.zeros_like(flux)
        density = uniform_filter1d(impulses, size=max(1, round(rate)), mode="nearest").astype(np.float32)
        candidates = _activity_candidates(name, activity, flux_norm, rate)
        result[name] = {
            "absoluteRms": rms.tolist(),
            "wholeTrackActivity": activity.tolist(),
            "spectralFlux": flux_norm.tolist(),
            "transientDensity": density.tolist(),
            "sampleDiagnostics": {
                "peakAbsolute": peak_absolute,
                "sampleFractionAtOrAbove0_99FullScale": clipped_fraction,
            },
        }
        source_evidence[name] = {
            "rmsP95FullScale": rms_scale,
            "spectralFluxP95": flux_scale,
            "peakAbsolute": peak_absolute,
            "sampleFractionAtOrAbove0_99FullScale": clipped_fraction,
            "candidateCount": len(candidates),
        }
        result[name]["candidates"] = candidates

    interpretation = {
        "version": 1,
        "method": "estimated_stem_rms_spectral_flux_v1",
        "duration": audio_duration,
        "envelopeRate": rate,
        "provenance": {
            "kind": "source_separation_estimates",
            "producer": "unspecified" if separation is None else separation.get("model", "unspecified"),
            "groundTruth": False,
            "separationRun": separation,
            "confidenceMeaning": "heuristic local-activity evidence strength, not probability or source identity certainty",
            "activityCalibration": "per-source whole-track RMS p95; no adaptive per-frame silence normalization",
            "candidateScope": "local activity entries, exits, and changes; no phrase or song-section labels",
            "clippingNote": "samples at or above 0.99 full scale are counted; clamp-mode separation may flatten peaks, and absolute RMS cannot recover pre-clamp peaks",
        },
        "sources": result,
    }
    evidence = {
        "duration": audio_duration,
        "sampleRate": sample_rate,
        "frameRate": rate,
        "frameCount": frame_total,
        "provenance": interpretation["provenance"],
        "sources": source_evidence,
    }
    return interpretation, evidence


def _activity_candidates(source, activity, flux, rate):
    """Find local estimated-source activity transitions and substantial changes."""
    smooth = median_filter(activity, size=3, mode="nearest")
    candidates = []
    active = False
    for index, value in enumerate(smooth):
        if not active and value >= 0.18:
            active = True
            kind = "activity_entry"
        elif active and value <= 0.10:
            active = False
            kind = "activity_exit"
        else:
            continue
        previous = float(smooth[max(0, index - 1)])
        following = float(value)
        change = abs(following - previous)
        candidates.append({
            "source": source,
            "kind": kind,
            "scope": "local_activity_only",
            "time": index / rate,
            "confidence": float(np.clip(0.35 + 0.4 * max(previous, following) + 0.5 * change + 0.15 * flux[index], 0, 1)),
            "evidence": {"activityBefore": previous, "activityAfter": following, "spectralFlux": float(flux[index])},
        })

    # Large local changes are evidence only; they are not assigned musical labels.
    if len(smooth) >= 3:
        delta = np.abs(np.diff(smooth, prepend=smooth[0]))
        minimum_gap = max(1, round(0.5 * rate))
        last_change = -minimum_gap
        for index in range(1, len(delta) - 1):
            if delta[index] < 0.28 or delta[index] < delta[index - 1] or delta[index] < delta[index + 1]:
                continue
            if index - last_change < minimum_gap:
                continue
            before, after = float(smooth[index - 1]), float(smooth[index])
            candidates.append({
                "source": source,
                "kind": "activity_change",
                "scope": "local_activity_only",
                "time": index / rate,
                "confidence": float(np.clip(0.3 + delta[index] * 0.7 + flux[index] * 0.2, 0, 1)),
                "evidence": {"activityBefore": before, "activityAfter": after, "spectralFlux": float(flux[index])},
            })
            last_change = index
    candidates.sort(key=lambda candidate: candidate["time"])
    return candidates


def _read_separation_manifest(stem_dir):
    path = pathlib.Path(stem_dir) / "separation.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid separation manifest {path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("separation manifest must contain a JSON object")
    # Keep only explicit producer metadata. Separation stems alone do not prove
    # model/version/device/clip settings for arbitrary input directories.
    return {key: data[key] for key in SEPARATION_METADATA if key in data}


def enrich(sidecar, stem_dir):
    interpretation, _ = analyze(sidecar, stem_dir)
    # Preserve published fields, including any existing stemPresence estimates.
    return dict(sidecar, stemInterpretation=interpretation)


def main(argv):
    if len(argv) != 5:
        raise SystemExit(__doc__)
    sidecar_path, stem_dir, output_path, evidence_path = map(pathlib.Path, argv[1:])
    _validate_paths(sidecar_path, stem_dir, output_path, evidence_path)
    sidecar = json.loads(sidecar_path.read_text())
    interpretation, evidence = analyze(sidecar, stem_dir)
    enriched = dict(sidecar, stemInterpretation=interpretation)
    output_path.write_text(json.dumps(enriched, separators=(",", ":")))
    evidence_path.write_text(json.dumps(evidence, indent=2))
    print(f"Added estimated-source activity for {len(SOURCES)} stems → {output_path}")


if __name__ == "__main__":
    main(sys.argv)
