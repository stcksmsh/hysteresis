"""Synthetic-only unit tests. Run: /secondary/hyst-env/analyze-py/bin/python -m pytest scripts/analyze -q"""
import math
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analyze.brain import BeatTracker  # noqa: E402
from analyze.dsp import AdaptiveNormalizer, EnvelopeFollower, js_round  # noqa: E402
from analyze.fftjs import FFT, WindowedFFT  # noqa: E402
from analyze.jsjson import dumps, js_number  # noqa: E402
from analyze.structure import (analyze_mix, build_windows_from_drops, downsample, label_sections,  # noqa: E402
                               mix_down_mono)
from analyze.wav import decode_wav_file  # noqa: E402

SR = 44100


def write_wav(path, data, bits=16, fmt=1):
    ch = data.shape[1]
    raw = data.astype('<f4').tobytes() if fmt == 3 else np.round(data * 32767).astype('<i2').tobytes()
    block = ch * bits // 8
    hdr = b'RIFF' + struct.pack('<I', 36 + len(raw)) + b'WAVE'
    hdr += b'fmt ' + struct.pack('<IHHIIHH', 16, fmt, ch, SR, SR * block, block, bits) + b'data' + struct.pack('<I', len(raw))
    Path(path).write_bytes(hdr + raw)


def test_fft_matches_numpy_rfft():
    rng = np.random.RandomState(0)
    x = rng.standard_normal((3, 2048))
    c = FFT(2048).real_transform(x)
    ref = np.fft.rfft(x, axis=1)
    got = c[:, 0:2050:2] + 1j * c[:, 1:2051:2]
    assert np.max(np.abs(got - ref)) < 1e-9


def test_windowed_fft_peak_bin_and_hann_edges():
    w = WindowedFFT(2048)
    assert w.window[0] == 0 and w.window[-1] == np.float32(0.5 - 0.5 * math.cos(2 * math.pi))
    n = np.arange(2048)
    x = np.sin(2 * np.pi * 43 * n / 2048).astype(np.float32)[None, :]
    m = w.transform(x)[0]
    assert m.dtype == np.float32 and int(np.argmax(m)) == 43


def test_envelope_follower_seeds_from_first_input_then_attacks():
    e = EnvelopeFollower(10, 100, 10)
    assert e.update(0.5) == 0.5
    a = math.exp(-1)
    assert e.update(1.0) == pytest.approx(a * 0.5 + (1 - a) * 1.0, abs=1e-15)


def test_adaptive_normalizer_peak_is_one_then_scales():
    n = AdaptiveNormalizer(6000, 11.6)
    assert n.normalize(2.0) == 1
    assert n.normalize(1.0) == pytest.approx(1.0 / (2.0 * math.exp(-11.6 / 6000)), abs=1e-15)


def test_js_round_ties_up():
    assert [js_round(x) for x in (0.5, 1.5, 2.5, -0.5, 689.06)] == [1, 2, 3, 0, 689]


def test_js_number_formatting():
    cases = {1.0: '1', 0.5: '0.5', 1e-7: '1e-7', 1.5e-6: '0.0000015', 1e21: '1e+21', 123456789012345680000.0: '123456789012345680000',
             -2.5e-9: '-2.5e-9', 0.1 + 0.2: '0.30000000000000004', 100.0: '100'}
    for v, s in cases.items():
        assert js_number(v) == s
    assert js_number(float('nan')) == 'null'
    assert dumps({'a': [1, 2.0, 'x'], 'b': None}) == '{"a":[1,2,"x"],"b":null}'


def test_decode_wav_int16_and_float32(tmp_path):
    d = np.array([[0.0, 0.5], [-0.5, 0.25]])
    write_wav(tmp_path / 'a.wav', d)
    w = decode_wav_file(str(tmp_path / 'a.wav'))
    assert w.sample_rate == SR and len(w.channels) == 2 and w.channels[0].dtype == np.float32
    assert w.channels[0].tolist() == [0.0, -16384 / 32768] and w.channels[1].tolist() == [16384 / 32768, 8192 / 32768]
    write_wav(tmp_path / 'b.wav', d, 32, 3)
    assert decode_wav_file(str(tmp_path / 'b.wav')).channels[1].tolist() == [0.5, 0.25]
    (tmp_path / 'c.wav').write_bytes(b'nope')
    with pytest.raises(ValueError):
        decode_wav_file(str(tmp_path / 'c.wav'))


def test_mix_down_mono_is_float32_channel_mean():
    m = mix_down_mono([np.array([1, 0], np.float32), np.array([0, 1], np.float32)])
    assert m.dtype == np.float32 and m.tolist() == [0.5, 0.5]


def test_beat_tracker_locks_to_120_bpm_click_train():
    hop = 512 / SR
    bt = BeatTracker(hop)
    tempo = 0
    for h in range(int(20 / hop)):
        t = h * hop
        nov = 1.0 if (t % 0.5) < hop else 0.0
        tempo, _c, _p = bt.update(nov, t)
    assert tempo == pytest.approx(120, abs=4)


def test_build_windows_from_drops_hand_values():
    # 120 bpm: bar 2 s, window 16 s
    w = build_windows_from_drops([20.0, 30.0, 5.0], 120, 60)
    assert w == [{'start': 0, 'end': 5.0, 'kind': 'build'}, {'start': 5.0, 'end': 20.0, 'kind': 'build'},
                 {'start': 20.0, 'end': 30.0, 'kind': 'build'}]


def test_label_sections_adds_intro_and_outro_and_names_kinds():
    secs = [{'start': 10.0, 'end': 12.0, 'kind': 'break'}, {'start': 3.0, 'end': 5.0, 'kind': 'build'}]
    events = [{'type': 'drop', 't': 5.0, 'strength': 1}]
    out = label_sections(sorted(secs, key=lambda s: s['start']), events, 30.0, 20)
    assert [(s['start'], s['end'], s['label']) for s in out] == [(0, 3.0, 'intro'), (3.0, 5.0, 'build'),
                                                                 (10.0, 12.0, 'breakdown'), (12.0, 30.0, 'outro')]
    assert list(out[0].keys()) == ['start', 'end', 'kind', 'label']
    assert label_sections([], [], 1.0, 20) == []  # under 2 s: no intro/outro


def test_downsample_means_and_clamps():
    raw = np.array([0.5, 1.5, 0.25, 0.25, 0.1], np.float32)
    assert downsample(raw, 2, 3) == [1, 0.25, pytest.approx(0.1)]


def test_analyze_mix_shape_on_click_train(tmp_path):
    n = SR * 8
    x = np.zeros(n)
    for i in range(0, n - 800, SR // 2):
        x[i:i + 800] = np.random.RandomState(i).standard_normal(800) * np.exp(-np.arange(800) / 150)
    write_wav(tmp_path / 'c.wav', (x * 0.5).reshape(-1, 1))
    sc = analyze_mix(decode_wav_file(str(tmp_path / 'c.wav')))
    assert list(sc.keys()) == ['schema', 'duration', 'tempo', 'beats', 'sections', 'events', 'onsets', 'energyEnvelope',
                               'bandEnvelope', 'centroidEnvelope', 'flatnessEnvelope', 'envelopeRate']
    assert sc['schema'] == 3 and sc['duration'] == 8.0 and sc['envelopeRate'] == 20
    assert len(sc['energyEnvelope']) == math.ceil(((n - 2048) // 512 + 1) / 4)
    assert list(sc['bandEnvelope']) == ['sub', 'low', 'mid', 'presence', 'air']
    assert len(sc['onsets']) >= 10 and all(0 <= o['tone'] <= 1 for o in sc['onsets'])


def test_analyze_mix_tiny_and_silent_inputs(tmp_path):
    write_wav(tmp_path / 't.wav', np.zeros((1000, 1)))
    sc = analyze_mix(decode_wav_file(str(tmp_path / 't.wav')))
    assert sc['beats'] == [] and sc['tempo'] == 120 and sc['sections'] == [] and len(sc['energyEnvelope']) == 1
