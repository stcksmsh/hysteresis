"""Port of scripts/wav.ts: minimal RIFF/WAVE reader. Samples are float32, like the TS Float32Array."""
import struct
from dataclasses import dataclass

import numpy as np


@dataclass
class DecodedWav:
    sample_rate: int
    channels: list  # list of float32 ndarrays
    duration: float


def decode_wav_file(path: str) -> DecodedWav:
    with open(path, 'rb') as f:
        buf = f.read()
    if buf[0:4] != b'RIFF' or buf[8:12] != b'WAVE':
        raise ValueError(f'{path}: not a RIFF/WAVE file')

    fmt = 1
    channel_count = 0
    sample_rate = 0
    bits = 0
    data_offset = -1
    data_length = 0

    offset = 12
    while offset + 8 <= len(buf):
        cid = buf[offset:offset + 4]
        size = struct.unpack_from('<I', buf, offset + 4)[0]
        body = offset + 8
        if cid == b'fmt ':
            fmt, channel_count, sample_rate = struct.unpack_from('<HHI', buf, body)
            bits = struct.unpack_from('<H', buf, body + 14)[0]
            if fmt == 0xFFFE and size >= 26:
                fmt = struct.unpack_from('<H', buf, body + 24)[0]
        elif cid == b'data':
            data_offset = body
            data_length = size
        offset = body + size + (size % 2)

    if data_offset < 0 or channel_count == 0:
        raise ValueError(f'{path}: missing fmt/data chunk')

    bps = bits // 8
    frame_count = data_length // (bps * channel_count)
    total = frame_count * channel_count
    raw = buf[data_offset:data_offset + total * bps]
    if len(raw) < total * bps:
        raise ValueError(f'{path}: data chunk runs past end of file')  # JS: RangeError

    if fmt == 3:
        a = np.frombuffer(raw, dtype='<f8' if bits == 64 else '<f4')
    elif bits == 16:
        a = np.frombuffer(raw, dtype='<i2') / 32768
    elif bits == 24:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2].astype(np.int8).astype(np.int32) << 16)
        a = v / 8388608
    elif bits == 32:
        a = np.frombuffer(raw, dtype='<i4') / 2147483648
    elif bits == 8:
        a = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128) / 128
    else:
        raise ValueError(f'{path}: unsupported bit depth {bits}')
    a = a.reshape(frame_count, channel_count).astype(np.float32)
    channels = [np.ascontiguousarray(a[:, c]) for c in range(channel_count)]
    return DecodedWav(sample_rate, channels, frame_count / sample_rate)
