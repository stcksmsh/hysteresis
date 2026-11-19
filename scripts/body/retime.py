"""Read-time re-timing of the realised arm (docs/BRAIN_SPEC.md 7.87, docs/RETIME_RULES.md).

Sign: L is positive when the movement is LATER than its music. The realised arm (controls/q50 and every array cut
from it) trails the music by L, so a lamp-derived array is read L later: sample i of the re-timed array is sample
i + round(L * rate) of the original, i.e. the array is shifted EARLIER by L. The last L seconds of a window have no
movement after them and are dropped, never padded.
"""
L = {"V1": 0.35, "V2": 0.28}


def retime(x, rate_hz, variant):
    """lamp-derived array x (time on axis 0) at rate_hz -> (x shifted earlier by L[variant], new valid length)"""
    k = int(round(L[variant] * rate_hz))
    y = x[k:]
    return y, len(y)


def retime_rows_start(window_offset_s, variant):
    """start time (s, window-relative) at which to cut a joint CSV so its first row matches the music at window_offset_s"""
    return window_offset_s + L[variant]
