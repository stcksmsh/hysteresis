#!/usr/bin/env python3
"""Build provisional beat-phrase memory from an audio WAV.

Usage: python3 scripts/dance_memory.py WAV INPUT_SIDECAR OUTPUT_SIDECAR EVIDENCE
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

import numpy as np
import soundfile as sf
from scipy.optimize import minimize_scalar
from scipy.signal import find_peaks

PHRASE_BEATS = 16
RHYTHM_BINS = 32
FFT_SIZE = 4096
FRAME_RATE = 50


def _finite_list(values):
    return np.asarray(values, dtype=np.float64)


def regularize_beats(beats, duration):
    beats = _finite_list(beats)
    beats = beats[np.isfinite(beats) & (beats >= 0) & (beats < duration)]
    beats = np.unique(beats)
    intervals = np.diff(beats)
    plausible = intervals[(intervals >= 0.35) & (intervals <= 1.5)]
    if len(plausible) < 4:
        raise ValueError("need at least five supplied beats with 0.35–0.9s intervals")
    initial = float(np.median(plausible))

    def phase_for(period):
        angle = beats * (2 * np.pi / period)
        z = np.mean(np.exp(1j * angle))
        return float((np.angle(z) % (2 * np.pi)) * period / (2 * np.pi))

    def residual_cost(period):
        phase = phase_for(period)
        residual = (beats - phase + period / 2) % period - period / 2
        return float(np.median(np.abs(residual)))

    lower, upper = initial * 0.96, initial * 1.04
    # Wrapped phase has many local minima over a long track. Scan finer than
    # one quarter of the period error that would accumulate a full phase cycle.
    step = initial * initial / max(4 * duration, 1e-9)
    count = max(3, int(math.ceil((upper - lower) / step)) + 1)
    grid = np.linspace(lower, upper, count)
    best_index = int(np.argmin([residual_cost(float(p)) for p in grid]))
    left = float(grid[max(0, best_index - 1)])
    right = float(grid[min(len(grid) - 1, best_index + 1)])
    fit = minimize_scalar(
        residual_cost,
        bounds=(left, right),
        method="bounded",
        options={"xatol": 1e-10},
    )
    period = float(fit.x)
    phase = phase_for(period)
    residual = (beats - phase + period / 2) % period - period / 2
    abs_residual = np.abs(residual)
    within80 = float(np.mean(abs_residual <= 0.08))
    return period, phase, {
        "suppliedBeatCount": int(len(beats)),
        "periodSeconds": period,
        "tempoBpm": 60.0 / period,
        "beatZeroSeconds": phase,
        "residualMsP50": float(np.percentile(abs_residual, 50) * 1000),
        "residualMsP90": float(np.percentile(abs_residual, 90) * 1000),
        "residualMsMax": float(np.max(abs_residual) * 1000),
        "within80msFraction": within80,
        "fitReliable": bool(within80 >= 0.9 and np.percentile(abs_residual, 90) <= 0.08),
        "provisional": True,
    }


def _audio_features(wav_path):
    audio, sample_rate = sf.read(wav_path, dtype="float32", always_2d=True)
    if not len(audio) or sample_rate <= 0:
        raise ValueError("WAV has no audio frames")
    duration = len(audio) / sample_rate
    hop = max(1, round(sample_rate / FRAME_RATE))
    nfft = 2 ** int(math.floor(math.log2(min(FFT_SIZE, max(256, sample_rate // 8)))))
    window = np.hanning(nfft).astype(np.float32)
    frame_count = max(1, 1 + max(0, len(audio) - nfft) // hop)
    centers = (np.arange(frame_count) * hop + nfft / 2) / sample_rate
    rms = np.empty(frame_count, dtype=np.float32)
    total_power = np.empty(frame_count, dtype=np.float32)
    low_power = np.empty(frame_count, dtype=np.float32)
    high_power = np.empty(frame_count, dtype=np.float32)
    chroma_power = np.zeros((frame_count, 12), dtype=np.float32)
    flux = np.zeros(frame_count, dtype=np.float32)
    low_flux = np.zeros(frame_count, dtype=np.float32)
    high_flux = np.zeros(frame_count, dtype=np.float32)
    freqs = np.fft.rfftfreq(nfft, 1 / sample_rate)
    low_mask = freqs < 250
    high_mask = freqs >= 2000
    pitch_bins = freqs > 55
    midi = np.zeros_like(freqs)
    midi[pitch_bins] = np.rint(69 + 12 * np.log2(freqs[pitch_bins] / 440)).astype(int)
    pitch_classes = midi.astype(int) % 12
    prev = None
    # Batch framing bounds temporary memory for long tracks.
    channels = audio.shape[1]
    per_channel_batch = max(1, 64 * 1024 * 1024 // (nfft * 4 * channels))
    for first in range(0, frame_count, per_channel_batch):
        last = min(frame_count, first + per_channel_batch)
        starts = np.arange(first, last) * hop
        frames = np.zeros((last - first, channels, nfft), dtype=np.float32)
        valid = np.minimum(nfft, np.maximum(0, len(audio) - starts))
        for row, (start, count) in enumerate(zip(starts, valid)):
            if count:
                frames[row, :, :count] = audio[start : start + count].T
        rms[first:last] = np.sqrt(np.mean(frames * frames, axis=(1, 2)))
        spec = np.abs(np.fft.rfft(frames * window, axis=2)).astype(np.float32)
        power = np.mean(spec * spec, axis=1)
        total_power[first:last] = np.sum(power, axis=1)
        low_power[first:last] = np.sum(power[:, low_mask], axis=1)
        high_power[first:last] = np.sum(power[:, high_mask], axis=1)
        for pitch_class in range(12):
            chroma_power[first:last, pitch_class] = np.sum(power[:, pitch_bins & (pitch_classes == pitch_class)], axis=1)
        mag = np.sqrt(power)
        log_spec = np.log1p(mag)
        if prev is not None:
            log_spec = np.vstack((prev, log_spec))
            diff = np.maximum(0, np.diff(log_spec, axis=0))
        else:
            diff = np.zeros_like(log_spec)
            diff[1:] = np.maximum(0, np.diff(log_spec, axis=0))
        flux[first:last] = np.sum(diff, axis=1)
        low_flux[first:last] = np.sum(diff[:, low_mask], axis=1)
        high_flux[first:last] = np.sum(diff[:, high_mask], axis=1)
        prev = np.log1p(mag[-1])
    return {
        "duration": duration,
        "times": centers.astype(np.float64),
        "rms": rms,
        "total": total_power,
        "low": low_power,
        "high": high_power,
        "chroma": chroma_power,
        "flux": flux,
        "lowFlux": low_flux,
        "highFlux": high_flux,
        "frameRate": sample_rate / hop,
        "sampleRate": int(sample_rate),
    }


def _profile(values):
    if not len(values):
        return [0.0] * RHYTHM_BINS
    scale = float(np.percentile(values, 95))
    if not math.isfinite(scale) or scale <= 1e-12:
        return [0.0] * RHYTHM_BINS
    return np.clip(values / scale, 0, 1).astype(float).tolist()


def _correlation(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if np.std(a) < 0.04 or np.std(b) < 0.04:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _phrase_similarity(a, b):
    channels = {key: _correlation(a[key], b[key]) for key in ("rhythm", "lowRhythm", "highRhythm")}
    rhythm = 0.5 * channels["rhythm"] + 0.25 * channels["lowRhythm"] + 0.25 * channels["highRhythm"]
    chroma = _correlation(a["chromaRhythm"], b["chromaRhythm"])
    timbre = 1 - (abs(a["lowRatio"] - b["lowRatio"]) + abs(a["brightness"] - b["brightness"])) / 2
    score = float(np.clip(0.55 * rhythm + 0.30 * chroma + 0.15 * timbre, 0, 1))
    return {**channels, "rhythm": float(rhythm), "chroma": float(chroma), "timbre": float(timbre), "score": score}


def _build_phrases(features, period, beat_zero):
    duration = features["duration"]
    times = features["times"]
    flux_floor = float(np.percentile(features["rms"], 95)) * 0.01
    active = features["rms"] >= max(1e-7, flux_floor)
    flux = features["flux"].copy()
    low_flux = features["lowFlux"].copy()
    high_flux = features["highFlux"].copy()
    flux[~active] = low_flux[~active] = high_flux[~active] = 0
    boundary = beat_zero
    phrases = []
    spans = []
    if boundary > 1 / features["frameRate"]:
        spans.append((0.0, min(boundary, duration), False, boundary / period))
    start = boundary
    while start < duration - 1e-8:
        end = min(duration, start + PHRASE_BEATS * period)
        complete = end - start >= PHRASE_BEATS * period * 0.999
        spans.append((start, end, complete, min(PHRASE_BEATS, (end - start) / period)))
        start += PHRASE_BEATS * period

    for start, end, complete, beat_count in spans:
        mask = (times >= start) & (times < end)
        idx = np.flatnonzero(mask)
        bins = np.zeros(RHYTHM_BINS, dtype=int)
        if len(idx):
            rel = (times[idx] - start) / period
            bins = np.clip(np.floor(rel * 2).astype(int), 0, RHYTHM_BINS - 1)
        def rhythm(source):
            vals = np.zeros(RHYTHM_BINS, dtype=np.float32)
            for bin_index in range(RHYTHM_BINS):
                selected = source[idx[bins == bin_index]] if len(idx) else []
                vals[bin_index] = np.percentile(selected, 90) if len(selected) else 0
            return _profile(vals)
        chroma_profile = np.zeros((RHYTHM_BINS, 12), dtype=np.float32)
        for bin_index in range(RHYTHM_BINS):
            selected = idx[bins == bin_index] if len(idx) else []
            if len(selected):
                energy = np.mean(features["chroma"][selected], axis=0)
                if np.sum(energy) > 1e-12:
                    chroma_profile[bin_index] = energy / np.sum(energy)
        def mean(source):
            return float(np.mean(source[idx])) if len(idx) else 0.0
        avg_rms = mean(features["rms"])
        total = mean(features["total"])
        low = mean(features["low"])
        high = mean(features["high"])
        phrases.append({
            "start": float(start), "end": float(end), "complete": bool(complete), "beatCount": float(beat_count),
            "level": 0.0, "lowRatio": float(np.clip(low / total, 0, 1)) if total > 1e-12 else 0.0,
            "brightness": float(np.clip(high / total, 0, 1)) if total > 1e-12 else 0.0,
            "rhythm": rhythm(flux), "lowRhythm": rhythm(low_flux), "highRhythm": rhythm(high_flux),
            "chromaRhythm": chroma_profile.reshape(-1).astype(float).tolist(),
            "repeatOf": None, "similarity": 0.0,
            "_rms": avg_rms,
        })
    loud_scale = max(float(np.percentile(features["rms"], 95)), 1e-8)
    for phrase in phrases:
        phrase["level"] = float(np.clip(phrase.pop("_rms") / loud_scale, 0, 1))
    return phrases


def _link_repeats(phrases):
    # ponytail: exhaustive phrase-pair scan; suitable for this short offline track, index if catalog-scale.
    candidates = []
    for j, target in enumerate(phrases):
        if not target["complete"] or target["level"] < 0.03 or not any(target["rhythm"]):
            continue
        qualifying = None
        for i in range(j - 2, -1, -1):
            source = phrases[i]
            if not source["complete"] or source["level"] < 0.03 or not any(source["rhythm"]):
                continue
            components = _phrase_similarity(source, target)
            passed = min(components[k] for k in ("rhythm", "lowRhythm", "highRhythm")) >= 0.90 and components["chroma"] >= 0.85 and components["timbre"] >= 0.82 and components["score"] >= 0.90
            candidates.append({"sourcePhrase": i, "targetPhrase": j, **components, "accepted": passed})
            if passed and qualifying is None:
                qualifying = (i, components["score"])
        if qualifying:
            source_index, score = qualifying
            target["repeatOf"] = source_index
            target["similarity"] = float(score)
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:20]


def _events(features, phrases):
    flux = features["flux"]
    rate = features["frameRate"]
    # Detect actual waveform-derived flux peaks, then retain sparse prominent events.
    threshold = max(float(np.percentile(flux, 98.5)), 1e-7)
    peaks, props = find_peaks(flux, height=threshold, distance=max(1, int(1.25 * rate)), prominence=threshold * 0.35)
    if not len(peaks):
        return []
    scale = max(float(np.max(flux)), threshold * 1.01, 1e-9)
    ranked = sorted(peaks, key=lambda i: flux[i], reverse=True)[:24]
    ranked.sort()
    return [{"time": float(features["times"][i]), "kind": "mix_onset", "source": "wav_spectral_flux_onset",
             "strength": float(np.clip(np.log1p(flux[i] / threshold) / np.log1p(scale / threshold), 0, 1))} for i in ranked]


def _flux_grid_support(features, period, beat_zero):
    flux = features["flux"]
    rate = features["frameRate"]
    threshold = max(float(np.percentile(flux, 98.5)), 1e-7)
    peaks, _ = find_peaks(flux, height=threshold, distance=max(1, int(0.12 * rate)), prominence=threshold * 0.35)
    residuals = np.abs((features["times"][peaks] - beat_zero + period / 2) % period - period / 2)
    return {
        "source": "wav_spectral_flux_onsets_independent_of_supplied_beats",
        "peakCount": int(len(peaks)),
        "timeResolutionMs": float(1000 / rate),
        "nearestGridResidualMsP50": float(np.percentile(residuals, 50) * 1000) if len(residuals) else None,
        "nearestGridResidualMsP90": float(np.percentile(residuals, 90) * 1000) if len(residuals) else None,
        "within60msFraction": float(np.mean(residuals <= 0.06)) if len(residuals) else None,
        "provisionalSupportOnly": True,
    }


def analyze(wav_path, sidecar):
    features = _audio_features(wav_path)
    duration = float(sidecar.get("duration", features["duration"]))
    if abs(duration - features["duration"]) > 0.1:
        raise ValueError("WAV and sidecar duration differ by more than 100ms")
    period, beat_zero, grid = regularize_beats(sidecar.get("beats", []), duration)
    phrases = _build_phrases(features, period, beat_zero)
    partial_coverage = [{"start": p["start"], "end": p["end"], "complete": p["complete"], "beatCount": p["beatCount"]} for p in phrases if not p["complete"]]
    complete_count = sum(1 for p in phrases if p["complete"])
    repeat_candidates = _link_repeats(phrases)
    events = _events(features, phrases)
    flux_support = _flux_grid_support(features, period, beat_zero)
    memory = {"version": 1, "method": "wav_stft_flux_phrase16_v1", "beatPeriod": period, "beatZero": beat_zero,
              "phrases": phrases, "events": events}
    evidence = {
        "duration": duration, "audio": {"sampleRate": features["sampleRate"], "frameRate": features["frameRate"], "channels": "channel-power average"},
        "gridFit": grid,
        "measuredFluxGridSupport": flux_support,
        "warnings": [] if grid["fitReliable"] else [f"provisional beat grid: {grid['within80msFraction']:.1%} of supplied beats fall within 80ms"],
        "phraseCount": len(phrases), "completePhraseCount": complete_count,
        "partialCoverage": partial_coverage,
        "repeatLinks": [{"phrase": i, "repeatOf": p["repeatOf"], "similarity": p["similarity"]} for i, p in enumerate(phrases) if p["repeatOf"] is not None],
        "repeatCandidates": repeat_candidates,
        "events": events,
        "contrasts": _contrast_windows(features, phrases, duration),
        "limits": ["Mix-only spectral features; no instrument/source labels.", "Beat fit provisional; supplied beat timestamps retained in input JSON.", "Flux onsets use frame-center estimates at 50Hz; timing is quantized, not sample-accurate.", "Flux events are measured spectral onsets, not downbeats, drops, or section labels."],
    }
    return memory, evidence


def _contrast_windows(features, phrases, duration):
    spans = [(0, min(2.554, duration)), (88, 96), (96, 104), (128, 136), (264, 280), (320, 328), (328, min(336, duration)), (336, duration)]
    out = []
    for start, end in spans:
        if end <= start or start >= duration:
            continue
        end = min(end, duration)
        mask = (features["times"] >= start) & (features["times"] < end)
        idx = np.flatnonzero(mask)
        if not len(idx):
            continue
        total = float(np.mean(features["total"][idx]))
        low = float(np.mean(features["low"][idx]))
        high = float(np.mean(features["high"][idx]))
        out.append({"start": start, "end": end, "rms": float(np.mean(features["rms"][idx])),
                    "lowRatio": low / total if total > 1e-12 else 0.0,
                    "brightness": high / total if total > 1e-12 else 0.0,
                    "spectralFluxMean": float(np.mean(features["flux"][idx]))})
    return out


def main(argv):
    if len(argv) != 5:
        raise SystemExit(__doc__)
    wav_path, input_path, output_path, evidence_path = map(pathlib.Path, argv[1:])
    _validate_output_paths(wav_path, input_path, output_path, evidence_path)
    original = json.loads(input_path.read_text())
    memory, evidence = analyze(wav_path, original)
    output = with_musical_memory(original, memory)
    output_path.write_text(json.dumps(output, separators=(",", ":")))
    evidence_path.write_text(json.dumps(evidence, indent=2))
    print(f"wrote {output_path} + {evidence_path}: {len(memory['phrases'])} phrases, {len(memory['events'])} measured mix onsets")


def _validate_output_paths(wav_path, input_path, output_path, evidence_path):
    wav_path, input_path, output_path, evidence_path = map(lambda p: p.resolve(), (wav_path, input_path, output_path, evidence_path))
    if output_path in (wav_path, input_path) or evidence_path in (wav_path, input_path) or output_path == evidence_path:
        raise ValueError("WAV/input must stay immutable; output and evidence paths must be distinct")


def with_musical_memory(sidecar, memory):
    return dict(sidecar, musicalMemory=memory)


if __name__ == "__main__":
    main(sys.argv)
