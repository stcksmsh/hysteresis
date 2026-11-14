"""Port of fft.js `realTransform` (radix-4, in-place) plus WindowedFFT.

fft.js runs in float64; this applies the same butterflies, in the same operation
order, to a whole batch of frames at once (numpy elementwise float64 ops are
IEEE-identical to the scalar JS ones; no FMA). Within one stage no iteration reads
a slot another writes, so gather-then-scatter equals the sequential in-place loop.
"""
import math

import numpy as np


class FFT:
    def __init__(self, size: int):
        if size <= 1 or size & (size - 1):
            raise ValueError('FFT size must be a power of two and bigger than 1')
        self.size = size
        self._csize = size << 1
        table = [0.0] * (size * 2)
        for i in range(0, len(table), 2):
            angle = math.pi * i / size
            table[i] = math.cos(angle)
            table[i + 1] = -math.sin(angle)
        self.table = np.array(table, dtype=np.float64)
        power = 0
        t = 1
        while size > t:
            power += 1
            t <<= 1
        self._width = power - 1 if power % 2 == 0 else power
        bitrev = []
        for j in range(1 << self._width):
            v = 0
            for shift in range(0, self._width, 2):
                # JS shift counts wrap mod 32 (width 11 gives -1 at the last step) and `|=` is int32
                v |= ((j >> shift) & 3) << ((self._width - shift - 2) & 31)
            v &= 0xFFFFFFFF
            bitrev.append(v - (1 << 32) if v >= 1 << 31 else v)
        self._bitrev = bitrev
        self._plan_stages()

    def _plan_stages(self):
        size = self._csize
        step = 1 << self._width
        ln = (size // step) << 1
        self._len0 = ln
        # initial permute+transform: per output block t, source offset bitrev[t]>>1
        t = np.arange(size // ln)
        self._init_out = t * ln
        self._init_off = np.array(self._bitrev, dtype=np.int64)[: len(t)] >> 1
        self._init_step = step >> 1
        self._stages = []
        step >>= 2
        while step >= 2:
            ln = (size // step) << 1
            half = ln >> 1
            quarter = half >> 1
            hq = quarter >> 1
            outs = np.arange(0, size, ln)
            ii = np.arange(0, hq + 1, 2)
            kk = (ii // 2) * step
            O, I = np.meshgrid(outs, ii, indexing='ij')
            K = np.broadcast_to(kk, O.shape)
            O, I, K = O.ravel(), I.ravel(), K.ravel()
            A = O + I
            B = A + quarter
            C = B + quarter
            D = C + quarter
            first = I == 0
            last = I == hq
            mid = ~first & ~last
            tab = self.table
            self._stages.append({
                'A': A, 'B': B, 'C': C, 'D': D,
                'tBr': tab[K], 'tBi': tab[K + 1],
                'tCr': tab[2 * K], 'tCi': tab[2 * K + 1],
                'tDr': tab[3 * K], 'tDi': tab[3 * K + 1],
                'first': first, 'mid': mid,
                'SA': (O + quarter - I)[mid], 'SB': (O + half - I)[mid],
            })
            step >>= 2

    def real_transform(self, data: np.ndarray) -> np.ndarray:
        """data: (B, size) float64 -> (B, 2*size) interleaved complex, like fft.js `out`."""
        nb = data.shape[0]
        out = np.zeros((nb, self._csize), dtype=np.float64)
        o = self._init_out
        off = self._init_off
        step = self._init_step
        if self._len0 == 4:
            even = data[:, off]
            odd = data[:, off + step]
            out[:, o] = even + odd
            out[:, o + 2] = even - odd
        else:
            Ar, Br, Cr, Dr = (data[:, off + j * step] for j in range(4))
            T0r = Ar + Cr
            T1r = Ar - Cr
            T2r = Br + Dr
            T3r = 1 * (Br - Dr)
            out[:, o] = T0r + T2r
            out[:, o + 2] = T1r
            out[:, o + 3] = -T3r
            out[:, o + 4] = T0r - T2r
            out[:, o + 6] = T1r
            out[:, o + 7] = T3r
        for s in self._stages:
            A, B, C, D = s['A'], s['B'], s['C'], s['D']
            Ar, Ai = out[:, A], out[:, A + 1]
            Br, Bi = out[:, B], out[:, B + 1]
            Cr, Ci = out[:, C], out[:, C + 1]
            Dr, Di = out[:, D], out[:, D + 1]
            tBr, tBi = s['tBr'], 1 * s['tBi']
            MBr = Br * tBr - Bi * tBi
            MBi = Br * tBi + Bi * tBr
            tCr, tCi = s['tCr'], 1 * s['tCi']
            MCr = Cr * tCr - Ci * tCi
            MCi = Cr * tCi + Ci * tCr
            tDr, tDi = s['tDr'], 1 * s['tDi']
            MDr = Dr * tDr - Di * tDi
            MDi = Dr * tDi + Di * tDr
            T0r = Ar + MCr
            T0i = Ai + MCi
            T1r = Ar - MCr
            T1i = Ai - MCi
            T2r = MBr + MDr
            T2i = MBi + MDi
            T3r = 1 * (MBr - MDr)
            T3i = 1 * (MBi - MDi)
            FAr = T0r + T2r
            FAi = T0i + T2i
            FBr = T1r + T3i
            FBi = T1i - T3r
            out[:, A] = FAr
            out[:, A + 1] = FAi
            out[:, B] = FBr
            out[:, B + 1] = FBi
            first = s['first']
            Cf = C[first]
            out[:, Cf] = (T0r - T2r)[:, first]
            out[:, Cf + 1] = (T0i - T2i)[:, first]
            m = s['mid']
            ST0r = T1r[:, m]
            ST0i = -T1i[:, m]
            ST1r = T0r[:, m]
            ST1i = -T0i[:, m]
            ST2r = -1 * T3i[:, m]
            ST2i = -1 * T3r[:, m]
            ST3r = -1 * T2i[:, m]
            ST3i = -1 * T2r[:, m]
            SA, SB = s['SA'], s['SB']
            out[:, SA] = ST0r + ST2r
            out[:, SA + 1] = ST0i + ST2i
            out[:, SB] = ST1r + ST3i
            out[:, SB + 1] = ST1i - ST3r
        return out


class WindowedFFT:
    """Hann-windowed magnitude spectrum, float32 window/windowed/magnitudes like the TS."""

    def __init__(self, size: int):
        self.size = size
        self.bins = size // 2 + 1
        self.fft = FFT(size)
        w = np.empty(size, dtype=np.float32)
        for i in range(size):
            w[i] = 0.5 - 0.5 * math.cos((2 * math.pi * i) / (size - 1))
        self.window = w

    def transform(self, samples: np.ndarray) -> np.ndarray:
        """samples: (B, size) float32 -> (B, bins) float32 magnitudes."""
        windowed = (samples * self.window).astype(np.float32).astype(np.float64)
        c = self.fft.real_transform(windowed)
        re = c[:, 0 : 2 * self.bins : 2]
        im = c[:, 1 : 2 * self.bins : 2]
        return np.sqrt(re * re + im * im).astype(np.float32)
