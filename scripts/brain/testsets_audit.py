"""Audit of the B1 test sets (not part of the checks): every audio file decodes, exact duplicates (sha256 of the
decoded samples), near duplicates (Chromaprint, bit-error rate < 0.35 on the best alignment, 3-view exact-key
voting as in the M5 measurement), annotation sanity. Writes /secondary/hyst-data/brain/testsets/AUDIT.md.
Uses libchromaprint through ctypes and ffmpeg for decoding (both already on the machine)."""
import ctypes
import hashlib
import os
import subprocess
import sys
from collections import defaultdict
from multiprocessing import Pool

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testsets  # noqa: E402

lib = ctypes.CDLL("libchromaprint.so.1")
lib.chromaprint_new.restype = ctypes.c_void_p
lib.chromaprint_new.argtypes = [ctypes.c_int]
lib.chromaprint_start.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
lib.chromaprint_feed.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
lib.chromaprint_finish.argtypes = [ctypes.c_void_p]
lib.chromaprint_get_raw_fingerprint.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(ctypes.c_uint32)), ctypes.POINTER(ctypes.c_int)]
lib.chromaprint_free.argtypes = [ctypes.c_void_p]
lib.chromaprint_dealloc.argtypes = [ctypes.c_void_p]
SR = 11025
VIEWS = [lambda v: v >> 16, lambda v: v & 0xFFFF, lambda v: (v >> 8) & 0xFFFF]


def fingerprint(path):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    ctx = lib.chromaprint_new(2)
    lib.chromaprint_start(ctx, SR, 1)
    lib.chromaprint_feed(ctx, pcm, len(pcm) // 2)
    lib.chromaprint_finish(ctx)
    p, n = ctypes.POINTER(ctypes.c_uint32)(), ctypes.c_int()
    lib.chromaprint_get_raw_fingerprint(ctx, ctypes.byref(p), ctypes.byref(n))
    fp = np.ctypeslib.as_array(p, shape=(n.value,)).copy()
    lib.chromaprint_dealloc(p)
    lib.chromaprint_free(ctx)
    return fp


def popcount(a):
    a = a.astype(np.uint64)
    a = a - ((a >> 1) & 0x5555555555555555)
    a = (a & 0x3333333333333333) + ((a >> 2) & 0x3333333333333333)
    return (((a + (a >> 4)) & 0x0F0F0F0F0F0F0F0F) * 0x0101010101010101 & 0xFFFFFFFFFFFFFFFF) >> 56


def probe(clip):
    """decode check, sample hash, fingerprint."""
    path = clip["audio"]
    try:
        y, sr = sf.read(path, dtype="int16", always_2d=True)
        return clip["id"], {"ok": True, "seconds": len(y) / sr, "sr": sr, "pcm_sha": hashlib.sha256(y.tobytes()).hexdigest(), "fp": fingerprint(path)}
    except Exception as e:  # corrupted file
        return clip["id"], {"ok": False, "error": str(e)[:100]}


def near_duplicates(fps):
    ids = [i for i in fps if fps[i] is not None and len(fps[i]) > 40]
    flat = np.concatenate([fps[i] for i in ids])
    owner = np.concatenate([[k] * len(fps[i]) for k, i in enumerate(ids)])
    pos = np.concatenate([np.arange(len(fps[i])) for i in ids])
    index = []
    for v in VIEWS:
        key = v(flat)
        o = np.argsort(key, kind="stable")
        index.append((key[o], owner[o], pos[o]))
    pairs = {}
    for qi, i in enumerate(ids):
        fp = fps[i]
        votes = defaultdict(int)
        for v, (key, own, ps) in zip(VIEWS, index):
            k = v(fp)
            lo, hi = np.searchsorted(key, k, "left"), np.searchsorted(key, k, "right")
            for q, (a, b) in enumerate(zip(lo, hi)):
                if b - a > 12:
                    continue
                for j in range(a, b):
                    if own[j] > qi:
                        votes[(int(own[j]), int(ps[j]) - q)] += 1
        for (o, off), n in sorted(votes.items(), key=lambda kv: -kv[1])[:3]:
            if n < 6:
                continue
            f = fps[ids[o]]
            i0, j0 = max(0, -off), max(0, off)
            m = min(len(fp) - i0, len(f) - j0)
            if m < 40:
                continue
            ber = popcount(fp[i0:i0 + m] ^ f[j0:j0 + m]).sum() / (32.0 * m)
            if ber < 0.35 and (i, ids[o]) not in pairs:
                pairs[(i, ids[o])] = (round(float(ber), 3), n, m)
    return pairs


def main():
    clips = testsets.ballroom_clips() + testsets.gtzan_clips()
    with Pool(8) as p:
        res = dict(p.map(probe, clips, chunksize=8))
    lines = ["# Test-set audit (scripts/brain/testsets_audit.py)", ""]
    bad = [i for i, r in res.items() if not r["ok"]]
    lines.append(f"Files decoded: {len(res) - len(bad)} of {len(res)}. Not decodable: {bad or 'none'} {[res[i]['error'] for i in bad]}")
    for name in ("ballroom", "gtzan"):
        sel = [c for c in clips if c["set"] == name]
        secs = np.array([res[c["id"]]["seconds"] for c in sel if res[c["id"]]["ok"]])
        lines.append(f"- {name}: {len(sel)} clips, duration min {secs.min():.1f} s, median {np.median(secs):.1f} s, max {secs.max():.1f} s, total {secs.sum() / 3600:.2f} h; "
                     f"fewer than 20 annotated beats: {[c['id'] for c in sel if len(c['beats']) < 20]}")
    by_sha = defaultdict(list)
    for i, r in res.items():
        if r["ok"]:
            by_sha[r["pcm_sha"]].append(i)
    exact = [v for v in by_sha.values() if len(v) > 1]
    lines.append(f"Exact duplicates (identical decoded samples): {exact or 'none'}")
    pairs = near_duplicates({i: res[i].get("fp") for i in res if res[i]["ok"]})
    lines.append(f"Near duplicates (Chromaprint, BER < 0.35 and at least 6 voting frames): {len(pairs)} pairs")
    for (a, b), (ber, n, m) in sorted(pairs.items()):
        lines.append(f"  - {a} ~ {b}  BER {ber}, votes {n}, overlap {m} frames")
    path = "/secondary/hyst-data/brain/testsets/AUDIT.md"
    open(path, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
