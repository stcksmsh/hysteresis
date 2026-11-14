"""Port of scripts/structure.ts (analyzeMix, analyzeMixDetailed, computeStemPresence)."""
import math
from dataclasses import dataclass

import numpy as np

from .brain import BarTracker, BeatTracker, BreakDetector, BuildDetector, DropDetector
from .dsp import (BAND_NAMES, FFT_SIZE, HOP_SIZE, AdaptiveNormalizer, EnvelopeFollower, compute_band_ranges,
                  band_energies, dominant_band_tone, js_round, seqsum, spectral_centroid_hz, spectral_flatness,
                  spectral_flux)
from .fftjs import WindowedFFT
from .wav import DecodedWav

SIDECAR_SCHEMA_VERSION = 3
ONSET_EVENT_THRESHOLD = 0.4
CENTROID_CEILING_HZ = 8000
NORMALIZER_DECAY_MS = 6000
DROP_NORMALIZER_DECAY_MS = 45000
BUILD_WINDOW_BARS = 8
ENVELOPE_RATE_HZ = 20
MIN_INTRO_OUTRO_SEC = 2
LOW_PRESENCE_THRESHOLD = 0.3
FFT_CHUNK_HOPS = 1024  # batch size for the vectorized FFT/feature pass; does not change results


def synthetic_pan(t: float) -> float:
    return math.sin(t * 37.13) * 0.6


def clamp01(v: float) -> float:
    return max(0, min(1, v))


def downsample(raw, hops_per_sample: int, envelope_length: int):
    """raw: float32 ndarray (per-hop). Sequential mean per bucket, clamped to 0..1."""
    r = raw.astype(np.float64).tolist()
    out = []
    for i in range(envelope_length):
        s = i * hops_per_sample
        e = min(len(r), s + hops_per_sample)
        total = 0.0
        n = 0
        for h in range(s, e):
            total += r[h]
            n += 1
        out.append(clamp01(total / n) if n > 0 else 0)
    return out


def build_windows_from_drops(drop_times, tempo_bpm, duration):
    bar_sec = (4 * 60) / max(1, tempo_bpm)
    window_sec = BUILD_WINDOW_BARS * bar_sec
    srt = sorted(drop_times)
    windows = []
    for i, drop in enumerate(srt):
        prev_drop = srt[i - 1] if i > 0 else -math.inf
        start = max(drop - window_sec, prev_drop, 0)
        if drop <= start:
            continue
        windows.append({'start': start, 'end': drop, 'kind': 'build'})
    return windows


def break_sections_from_events(events):
    sections = []
    for i in range(len(events) - 1):
        if events[i]['type'] == 'breakStart' and events[i + 1]['type'] == 'breakEnd':
            sections.append({'start': events[i]['t'], 'end': events[i + 1]['t'], 'kind': 'break'})
    return sections


def average_stem_presence(sp, envelope_rate, start, end):
    i0 = max(0, math.floor(start * envelope_rate))
    i1 = min(len(sp['vocals']), math.ceil(end * envelope_rate))
    if i1 <= i0:
        return 0
    total = 0.0
    n = 0
    for i in range(i0, i1):
        total += (sp['vocals'][i] if i < len(sp['vocals']) else 0) + (sp['drums'][i] if i < len(sp['drums']) else 0) \
            + (sp['bass'][i] if i < len(sp['bass']) else 0) + (sp['other'][i] if i < len(sp['other']) else 0)
        n += 4
    return total / n if n > 0 else 0


def label_sections(sections, events, duration, envelope_rate, stem_presence=None):
    labeled = []
    for s in sections:
        d = dict(s)
        d['label'] = 'build' if s['kind'] == 'build' else 'breakdown' if s['kind'] == 'break' else s.get('label')
        if d['label'] is None:
            del d['label']  # JSON.stringify drops undefined
        labeled.append(d)

    boundary_times = [duration] + [s['start'] for s in sections] + [e['t'] for e in events]
    earliest = min(boundary_times)
    if earliest >= MIN_INTRO_OUTRO_SEC:
        ok = stem_presence is None or average_stem_presence(stem_presence, envelope_rate, 0, earliest) < LOW_PRESENCE_THRESHOLD
        if ok:
            labeled.append({'start': 0, 'end': earliest, 'kind': 'other', 'label': 'intro'})

    latest = max([0] + [s['end'] for s in sections] + [e['t'] for e in events])
    if duration - latest >= MIN_INTRO_OUTRO_SEC:
        ok = stem_presence is None or average_stem_presence(stem_presence, envelope_rate, latest, duration) < LOW_PRESENCE_THRESHOLD
        if ok:
            labeled.append({'start': latest, 'end': duration, 'kind': 'other', 'label': 'outro'})

    return sorted(labeled, key=lambda s: s['start'])


@dataclass
class AnalyzeMixDetailed:
    sidecar: dict
    band_raw: dict
    centroid_raw: np.ndarray
    flatness_raw: np.ndarray
    hop_sec: float
    drop_times: list


def mix_down_mono(channels) -> np.ndarray:
    frame_count = len(channels[0]) if channels else 0
    total = np.zeros(frame_count, dtype=np.float64)
    for c in channels:
        total = total + c.astype(np.float64)
    return (total / len(channels)).astype(np.float32) if channels else np.zeros(0, dtype=np.float32)


def _hop_frames(mono: np.ndarray, first: int, count: int) -> np.ndarray:
    """(count, FFT_SIZE) float32 frames starting at hop `first`; zero-padded past the end."""
    out = np.zeros((count, FFT_SIZE), dtype=np.float32)
    for j in range(count):
        start = (first + j) * HOP_SIZE
        seg = mono[start:start + FFT_SIZE]
        out[j, :len(seg)] = seg
    return out


def analyze_mix(wav: DecodedWav) -> dict:
    return analyze_mix_detailed(wav).sidecar


def analyze_mix_detailed(wav: DecodedWav) -> AnalyzeMixDetailed:
    sample_rate = wav.sample_rate
    channels = wav.channels
    frame_count = len(channels[0]) if channels else 0
    duration = frame_count / sample_rate
    mono = mix_down_mono(channels)

    fft = WindowedFFT(FFT_SIZE)
    hop_sec = HOP_SIZE / sample_rate
    hop_ms = hop_sec * 1000
    band_ranges = compute_band_ranges(FFT_SIZE, sample_rate)

    attack_release = {'sub': (10, 300), 'low': (10, 250), 'mid': (8, 200), 'presence': (6, 150), 'air': (5, 120)}
    band_env = [EnvelopeFollower(*attack_release[n], hop_ms) for n in BAND_NAMES]
    band_norm = [AdaptiveNormalizer(NORMALIZER_DECAY_MS, hop_ms) for _ in BAND_NAMES]
    flux_norm = AdaptiveNormalizer(NORMALIZER_DECAY_MS, hop_ms)
    drop_env = EnvelopeFollower(30, 220, hop_ms)
    drop_norm = AdaptiveNormalizer(DROP_NORMALIZER_DECAY_MS, hop_ms)

    beat_tracker = BeatTracker(hop_sec)
    bar_tracker = BarTracker()
    build_detector = BuildDetector(hop_ms)
    drop_detector = DropDetector(hop_ms)
    break_detector = BreakDetector(hop_ms)

    total_hops = max(0, math.floor((frame_count - FFT_SIZE) / HOP_SIZE) + 1)
    energy_raw = np.zeros(total_hops, dtype=np.float32)
    band_raw = {n: np.zeros(total_hops, dtype=np.float32) for n in BAND_NAMES}
    centroid_raw = np.zeros(total_hops, dtype=np.float32)
    flatness_raw = np.zeros(total_hops, dtype=np.float32)

    beats, events, onsets, drop_times = [], [], [], []
    last_beat_phase = 0.0
    last_bar_phase = 0.0
    was_above = False
    final_tempo = 120.0
    tempo_sum = 0.0
    tempo_samples = 0
    prev_mags = np.zeros(fft.bins)

    for c0 in range(0, total_hops, FFT_CHUNK_HOPS):
        n = min(FFT_CHUNK_HOPS, total_hops - c0)
        mags = fft.transform(_hop_frames(mono, c0, n))
        bands_all = band_energies(mags, band_ranges)
        centroid_hz = spectral_centroid_hz(mags, sample_rate, FFT_SIZE)
        flat_f32 = spectral_flatness(mags).astype(np.float32)
        flux_all, prev_mags = spectral_flux(mags, prev_mags)
        flat_list = flat_f32.astype(np.float64).tolist()
        bands_list = bands_all.tolist()
        centroid_list = centroid_hz.tolist()
        flux_list = flux_all.tolist()
        flatness_raw[c0:c0 + n] = flat_f32

        for j in range(n):
            h = c0 + j
            start = h * HOP_SIZE
            br = bands_list[j]
            raw_low = (br[0] + br[1]) / 2
            b = [band_norm[k].normalize(band_env[k].update(br[k])) for k in range(5)]
            low_energy = (b[0] + b[1]) / 2
            energy_raw[h] = (b[0] + b[1] + b[2] + b[3] + b[4]) / 5
            for k, name in enumerate(BAND_NAMES):
                band_raw[name][h] = b[k]

            centroid = min(1, centroid_list[j] / CENTROID_CEILING_HZ)
            centroid_raw[h] = centroid
            flatness = flat_list[j]
            novelty = flux_norm.normalize(flux_list[j])

            t_now = start / sample_rate
            tempo_bpm, _conf, beat_phase = beat_tracker.update(novelty, t_now)
            bar_phase = bar_tracker.update(beat_phase, novelty)

            if beat_phase < last_beat_phase - 0.5:
                beats.append(t_now)
            last_beat_phase = beat_phase

            if novelty > ONSET_EVENT_THRESHOLD and not was_above:
                onsets.append({'t': t_now, 'strength': novelty, 'tone': dominant_band_tone(b), 'pan': synthetic_pan(t_now)})
            was_above = novelty > ONSET_EVENT_THRESHOLD

            if bar_phase < last_bar_phase - 0.5:
                events.append({'type': 'downbeat', 't': t_now, 'strength': 1})
            last_bar_phase = bar_phase

            if t_now > duration * 0.5:
                tempo_sum += tempo_bpm
                tempo_samples += 1
            final_tempo = tempo_sum / tempo_samples if tempo_samples > 0 else tempo_bpm

            _tension, bev = break_detector.update(low_energy, novelty, t_now)
            if bev is not None:
                events.append({'type': bev[0], 't': bev[2], 'strength': bev[1]})

            drop_signal = drop_norm.normalize(drop_env.update(raw_low))
            vec = [b[0], b[1], b[2], b[3], b[4], centroid, flatness]
            dev = drop_detector.update(drop_signal, novelty, vec, beat_phase, tempo_bpm, t_now)
            if dev is not None:
                events.append({'type': 'drop', 't': dev[1], 'strength': dev[0]})
                drop_times.append(dev[1])
                build_detector.reset()

            build_detector.update(centroid, b[0])

    build_sections = build_windows_from_drops(drop_times, final_tempo, duration)
    break_sections = break_sections_from_events([e for e in events if e['type'] in ('breakStart', 'breakEnd')])
    unlabeled = sorted(build_sections + break_sections, key=lambda s: s['start'])
    sections = label_sections(unlabeled, events, duration, ENVELOPE_RATE_HZ)

    hops_per = max(1, js_round(1 / ENVELOPE_RATE_HZ / hop_sec))
    env_len = max(1, math.ceil(total_hops / hops_per))
    sidecar = {
        'schema': SIDECAR_SCHEMA_VERSION,
        'duration': duration,
        'tempo': final_tempo,
        'beats': beats,
        'sections': sections,
        'events': sorted(events, key=lambda e: e['t']),
        'onsets': sorted(onsets, key=lambda o: o['t']),
        'energyEnvelope': downsample(energy_raw, hops_per, env_len),
        'bandEnvelope': {n: downsample(band_raw[n], hops_per, env_len) for n in BAND_NAMES},
        'centroidEnvelope': downsample(centroid_raw, hops_per, env_len),
        'flatnessEnvelope': downsample(flatness_raw, hops_per, env_len),
        'envelopeRate': ENVELOPE_RATE_HZ,
    }
    return AnalyzeMixDetailed(sidecar, band_raw, centroid_raw, flatness_raw, hop_sec, drop_times)


def _presence_envelope(raw: np.ndarray, hop_sec: float):
    hops_per = max(1, js_round(1 / ENVELOPE_RATE_HZ / hop_sec))
    env_len = max(1, math.ceil(len(raw) / hops_per))
    return downsample(raw, hops_per, env_len)


def compute_presence_envelope(mono: np.ndarray, sample_rate: float):
    hop_sec = HOP_SIZE / sample_rate
    hop_ms = hop_sec * 1000
    total_hops = max(0, math.floor(len(mono) / HOP_SIZE))
    envelope = EnvelopeFollower(15, 200, hop_ms)
    normalizer = AdaptiveNormalizer(NORMALIZER_DECAY_MS, hop_ms)
    m = mono[:total_hops * HOP_SIZE].astype(np.float64).reshape(total_hops, HOP_SIZE)
    rms = np.sqrt(seqsum(m * m) / HOP_SIZE).tolist()
    raw = np.zeros(total_hops, dtype=np.float32)
    for h in range(total_hops):
        raw[h] = normalizer.normalize(envelope.update(rms[h]))
    return _presence_envelope(raw, hop_sec)


def compute_lead_presence_envelope(mono: np.ndarray, sample_rate: float):
    hop_sec = HOP_SIZE / sample_rate
    hop_ms = hop_sec * 1000
    total_hops = max(0, math.floor((len(mono) - FFT_SIZE) / HOP_SIZE) + 1)
    fft = WindowedFFT(FFT_SIZE)
    envelope = EnvelopeFollower(30, 400, hop_ms)
    normalizer = AdaptiveNormalizer(NORMALIZER_DECAY_MS, hop_ms)
    raw = np.zeros(total_hops, dtype=np.float32)
    for c0 in range(0, total_hops, FFT_CHUNK_HOPS):
        n = min(FFT_CHUNK_HOPS, total_hops - c0)
        mags = fft.transform(_hop_frames(mono, c0, n))
        peaks = mags[:, 1:].astype(np.float64).max(axis=1).tolist()
        for j in range(n):
            raw[c0 + j] = normalizer.normalize(envelope.update(max(0, peaks[j])))
    return _presence_envelope(raw, hop_sec)


def compute_stem_presence(vocals: DecodedWav, drums: DecodedWav, bass: DecodedWav, other: DecodedWav) -> dict:
    other_mono = mix_down_mono(other.channels)
    return {
        'vocals': compute_presence_envelope(mix_down_mono(vocals.channels), vocals.sample_rate),
        'drums': compute_presence_envelope(mix_down_mono(drums.channels), drums.sample_rate),
        'bass': compute_presence_envelope(mix_down_mono(bass.channels), bass.sample_rate),
        'other': compute_presence_envelope(other_mono, other.sample_rate),
        'leadPresence': compute_lead_presence_envelope(other_mono, other.sample_rate),
    }
