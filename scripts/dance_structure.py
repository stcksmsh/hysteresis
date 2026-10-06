#!/usr/bin/env python3
"""Add confidence-ranked mixed-audio structure evidence to a sidecar.

Usage: dance_structure.py WAV INPUT_SIDECAR OUTPUT_SIDECAR EVIDENCE [REFERENCE]
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

import numpy as np
from scipy.signal import find_peaks

from dance_memory import _audio_features, _validate_output_paths, regularize_beats

SCALES = (4, 8, 16, 32)
REPEAT_SCALES = (32, 48, 64)
GROUPS = ((0, 1), (1, 3), (3, 15), (15, 18))
GROUP_NAMES = ('level', 'bandBalance', 'chroma', 'flux')
SOURCE_NAMES = ('vocals', 'drums', 'bass', 'other')


def _validated_stem_interpretation(value, duration):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError('stemInterpretation must be a JSON object')
    provenance = value.get('provenance', {})
    try:
        rate, source_duration = float(value['envelopeRate']), float(value['duration'])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('stemInterpretation v1 needs numeric envelopeRate and duration') from error
    if (value.get('version') != 1 or value.get('method') != 'estimated_stem_rms_spectral_flux_v1'
            or not isinstance(provenance, dict) or provenance.get('kind') != 'source_separation_estimates'
            or provenance.get('groundTruth') is not False):
        raise ValueError('stemInterpretation must be v1 source_separation_estimates, groundTruth=false')
    if not math.isfinite(rate) or not 0 < rate <= 1000 or not math.isfinite(source_duration) or source_duration <= 0:
        raise ValueError('stemInterpretation rate and duration must be finite and positive')
    if abs(source_duration-duration) > 0.1:
        raise ValueError('stemInterpretation and WAV duration differ by more than 100ms')
    expected = math.ceil(source_duration * rate)
    sources = value.get('sources', {})
    if not isinstance(sources, dict):
        raise ValueError('stemInterpretation sources must be a JSON object')
    result = {}
    for name in SOURCE_NAMES:
        try:
            envelope = np.asarray(sources[name]['absoluteRms'], dtype=float)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f'stemInterpretation missing {name}.absoluteRms') from error
        if envelope.ndim != 1 or len(envelope) != expected or not np.isfinite(envelope).all() or np.any(envelope < 0):
            raise ValueError(f'stemInterpretation {name}.absoluteRms must have {expected} finite nonnegative samples')
        result[name] = envelope
    return {'rate': rate, 'duration': source_duration, 'rms': result, 'provenance': provenance,
            'method': value.get('method')}


def _descriptors(features, period, zero, stems=None):
    cell = period / 4
    count = max(0, math.ceil((features['duration'] - zero) / cell))
    times = features['times']
    total = features['total']
    chroma = features['chroma'] / np.maximum(features['chroma'].sum(axis=1, keepdims=True), 1e-12)
    low = features['low'] / np.maximum(total, 1e-12)
    high = features['high'] / np.maximum(total, 1e-12)
    rows = np.zeros((count, 18 + (4 if stems else 0)), dtype=float)
    for i in range(count):
        a, b = zero + i * cell, zero + (i + 1) * cell
        selected = (times >= a) & (times < b)
        if selected.any():
            rows[i, :18] = [np.log1p(float(np.mean(features['rms'][selected])) * 1000),
                       float(np.mean(low[selected])), float(np.mean(high[selected])),
                       *np.mean(chroma[selected], axis=0),
                       np.log1p(float(np.mean(features['flux'][selected]))),
                       np.log1p(float(np.mean(features['lowFlux'][selected]))),
                       np.log1p(float(np.mean(features['highFlux'][selected])))]
    if stems:
        source_times = (np.arange(math.ceil(stems['duration'] * stems['rate'])) + 0.5) / stems['rate']
        centers = zero + (np.arange(count) + 0.5) * cell
        for offset, name in enumerate(SOURCE_NAMES, 18):
            aligned = np.interp(centers, source_times, stems['rms'][name], left=0.0,
                               right=float(stems['rms'][name][-1]))
            rows[:, offset] = np.log1p(aligned * 1000)
    scale = rows.std(axis=0)
    scale[scale < 1e-8] = 1
    return (rows - rows.mean(axis=0)) / scale


def novelty_candidates(descriptors, period, zero, top_per_scale=10):
    """Contrast adjacent beat windows; score percentiles are empirical, not probabilities."""
    cell = period / 4
    results = []
    groups = GROUPS + (((18, 22),) if descriptors.shape[1] >= 22 else ())
    for beats in SCALES:
        width = beats * 4
        if len(descriptors) < 2 * width + 3:
            continue
        score = np.full(len(descriptors), np.nan)
        parts = np.zeros((len(descriptors), len(groups)))
        for center in range(width, len(descriptors) - width):
            for g, (a, b) in enumerate(groups):
                delta = descriptors[center-width:center, a:b].mean(axis=0) - descriptors[center:center+width, a:b].mean(axis=0)
                parts[center, g] = np.linalg.norm(delta) / math.sqrt(b-a)
            score[center] = np.sqrt(np.mean(parts[center] ** 2))
        peaks, _ = find_peaks(np.nan_to_num(score, nan=-1.0), distance=max(1, round(2 / cell)))
        peaks = [i for i in peaks if math.isfinite(score[i]) and score[i] > 1e-10]
        peaks.sort(key=lambda i: score[i], reverse=True)
        valid = score[np.isfinite(score)]
        for rank, i in enumerate(peaks[:top_per_scale], 1):
            percentile = float(np.mean(valid <= score[i]))
            results.append({'time': float(zero + i * cell), 'scaleBeats': beats,
                            'score': float(score[i]), 'rank': rank,
                            'scorePercentile': percentile,
                            'components': dict(zip(GROUP_NAMES + (('sourceParticipation',) if len(groups) == 5 else ()),
                                                   map(float, parts[i])))})
    results.sort(key=lambda item: item['scorePercentile'], reverse=True)
    return results


def repeat_links(descriptors, period, zero, minimum_similarity=0.72, limit=12):
    """Search 8–16 bar windows; ponytail: stride 4 beats, denser search only if recall needs it."""
    beat_features = descriptors[:len(descriptors)//4*4].reshape(-1, 4, descriptors.shape[1]).mean(axis=1)
    links = []
    for length in REPEAT_SCALES:
        if len(beat_features) < 2 * length:
            continue
        starts = np.arange(0, len(beat_features) - length + 1, 4)
        positions = np.linspace(0, length - 1, 24)
        windows = np.array([[np.interp(positions, np.arange(length), beat_features[s:s+length, k])
                             for k in range(beat_features.shape[1])] for s in starts])
        windows -= windows.mean(axis=2, keepdims=True)
        flat = windows.reshape(len(starts), -1)
        norms = np.linalg.norm(flat, axis=1)
        unit = flat / np.maximum(norms[:, None], 1e-12)
        similarity = unit @ unit.T
        for i, start in enumerate(starts):
            later = np.flatnonzero((starts >= start + length) & (similarity[i] >= minimum_similarity))
            for j in later:
                links.append({'start': float(zero + start * period), 'end': float(zero + (start + length) * period),
                              'repeatStart': float(zero + starts[j] * period),
                              'repeatEnd': float(zero + (starts[j] + length) * period),
                              'scaleBeats': int(length), 'similarity': float(similarity[i, j])})
    links.sort(key=lambda link: link['similarity'], reverse=True)
    chosen = []
    for link in links:
        if any(abs(link['start']-old['start']) < 4*period and
               abs(link['repeatStart']-old['repeatStart']) < 4*period for old in chosen):
            continue
        chosen.append(link)
        if len(chosen) == limit:
            break
    return chosen


def analyze(wav, sidecar):
    features = _audio_features(str(wav))
    duration = float(sidecar.get('duration', features['duration']))
    if abs(duration - features['duration']) > 0.1:
        raise ValueError('WAV and sidecar duration differ by more than 100ms')
    period, zero, fit = regularize_beats(sidecar.get('beats', []), duration)
    stems = _validated_stem_interpretation(sidecar.get('stemInterpretation'), features['duration'])
    descriptors = _descriptors(features, period, zero, stems)
    candidates = novelty_candidates(descriptors, period, zero)
    repeats = repeat_links(descriptors, period, zero)
    structure = {'version': 1, 'method': 'beat-synchronous novelty and repeated-material search',
                 'featureRateHz': float(features['frameRate']),
                 'featureSource': 'provided WAV mix' + (' plus validated estimated stem RMS' if stems else ''),
                 'beatGrid': {'periodSeconds': period, 'beatZeroSeconds': zero, **fit},
                 'noveltyCandidates': candidates, 'repeatedMaterial': repeats,
                 'limits': ['WAV spectral descriptors are mix-only; low/high bands are not isolated sources.',
                            'Novelty candidates are not downbeats, drops, or semantic section labels.',
                            'Beat fit is provisional; similarity and percentiles are uncalibrated evidence.']}
    if stems:
        provenance = stems['provenance']
        structure['sourceParticipation'] = {'kind': provenance['kind'], 'method': stems['method'],
                                            'producer': provenance.get('producer'),
                                            'model': (provenance.get('separationRun') or {}).get('model'),
                                            'groundTruth': False,
                                            'confidenceMeaning': provenance.get('confidenceMeaning'),
                                            'clippingNote': provenance.get('clippingNote'),
                                            'features': 'log absolute RMS; aligned from shared stem envelope timestamps'}
        structure['featureGroups'] = list(GROUP_NAMES) + ['sourceParticipation']
        structure['limits'].extend(['Stem envelopes are source-separation estimates, not isolated-source ground truth.',
                                    'Source participation contrast uses only aligned absolute RMS; identity and activity confidence remain uncertain.'])
    evidence = {'audio': {'inputWav': str(pathlib.Path(wav).resolve()),
                          'durationSeconds': features['duration'], 'sampleRate': features['sampleRate'],
                          'featureRateHz': features['frameRate'], 'descriptorCount': len(descriptors)},
                'beatGrid': fit, 'noveltyCandidateCount': len(candidates),
                'repeatLinkCount': len(repeats), 'methodNotes': ['Novelty compares adjacent 4/8/16/32-beat descriptors.',
                                                                  'Repetition scan compares 32/48/64-beat descriptors at 4-beat stride.',
                                                                  'Feature sources: RMS, low/high power ratios, 12-bin chroma, spectral flux and band flux.'],
                'warnings': [] if fit['fitReliable'] else ['Beat fit provisional; retain boundary uncertainty.']}
    if stems:
        evidence['sourceFeatureProvenance'] = structure['sourceParticipation']
        evidence['audio']['descriptorCount'] = len(descriptors)
    return structure, evidence


def validate_reference(structure, reference):
    """Compare externally supplied labels after inference; labels never reach analyzers."""
    candidates = structure['noveltyCandidates']
    regions = []
    for region in reference.get('regions', []):
        row = {'label': region['label'], 'start': region['start'], 'end': region['end']}
        for edge in ('start', 'end'):
            nearest = min(candidates, key=lambda c: abs(c['time']-region[edge])) if candidates else None
            close = nearest if nearest and abs(nearest['time']-region[edge]) <= 4 else None
            row[edge + 'Candidate'] = (None if close is None else
                {'time': close['time'], 'deltaSeconds': close['time']-region[edge],
                 'scaleBeats': close['scaleBeats'], 'scorePercentile': close['scorePercentile']})
            row[edge + 'NearestAnyCandidate'] = (None if nearest is None else
                {'time': nearest['time'], 'deltaSeconds': nearest['time']-region[edge],
                 'scaleBeats': nearest['scaleBeats'], 'scorePercentile': nearest['scorePercentile']})
        regions.append(row)
    return {'source': reference.get('source'), 'purpose': 'validation only; excluded from inference; candidate match radius 4s',
            'regions': regions}


def main(argv):
    if len(argv) not in (5, 6):
        raise SystemExit(__doc__)
    wav, input_path, output_path, evidence_path = map(pathlib.Path, argv[1:5])
    _validate_output_paths(wav, input_path, output_path, evidence_path)
    sidecar = json.loads(input_path.read_text())
    structure, evidence = analyze(wav, sidecar)
    if len(argv) == 6:
        reference_path = pathlib.Path(argv[5])
        if reference_path.resolve() in {p.resolve() for p in (wav, input_path, output_path, evidence_path)}:
            raise ValueError('reference path must stay separate from WAV, sidecar, and outputs')
        reference = json.loads(reference_path.read_text())
        evidence['referenceValidation'] = validate_reference(structure, reference)
    output = dict(sidecar)
    output['musicalStructure'] = structure
    output_path.write_text(json.dumps(output, indent=2))
    evidence_path.write_text(json.dumps(evidence, indent=2))
    print(json.dumps({'noveltyCandidates': len(structure['noveltyCandidates']),
                      'repeatedMaterial': len(structure['repeatedMaterial']),
                      'beatGridReliable': structure['beatGrid']['fitReliable']}, indent=2))


if __name__ == '__main__':
    main(sys.argv)
