"""B3 corpus step 7: Chromaprint exclusion by bit-error rate.

usage: corpus_fingerprint.py refs            build reference fingerprints (audio files only) -> refs.npz
       corpus_fingerprint.py scan [DIR]      fingerprint DIR (default corpus audio) and match against refs
Writes fingerprints.npz (cache, one array per corpus file) and fp_matches.csv (one row per corpus file with BER < THRESH).

Match rule (BRAIN_SPEC 1.4, fixed): bit-error rate < 0.35 on the best alignment of a reference clip inside a
corpus track (at least MIN_OVERLAP frames, 0.124 s each). Candidate alignments come from a 16-bit key index (three
views of each 32-bit hash); the five best-voted (reference, offset) pairs per corpus file are scored by BER over
offsets +-2 and the lowest BER counts. Raw Chromaprint default algorithm (enum 1, TEST2, as fpcalc -algorithm 2) at 11025 Hz mono; measure/scripts/m5_fp.py used enum 2 (TEST3, 2.3 items per s) by mistake.
"""
import ctypes
import glob
import os
import subprocess
import sys
from collections import Counter
from multiprocessing import Pool

import numpy as np

C = "/secondary/hyst-data/brain/corpus/"
E = "/secondary/hyst-data/emotion/"
T = "/secondary/hyst-data/brain/testsets/"
SONGS = "/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm/"
THRESH = 0.35
MIN_OVERLAP = 40
SR = 11025
EXT = (".wav", ".mp3", ".au", ".m4a", ".ogg", ".flac")

lib = ctypes.CDLL("libchromaprint.so.1")
lib.chromaprint_new.restype = ctypes.c_void_p
lib.chromaprint_new.argtypes = [ctypes.c_int]
lib.chromaprint_start.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
lib.chromaprint_feed.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
lib.chromaprint_finish.argtypes = [ctypes.c_void_p]
lib.chromaprint_get_raw_fingerprint.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(ctypes.c_uint32)), ctypes.POINTER(ctypes.c_int)]
lib.chromaprint_free.argtypes = [ctypes.c_void_p]
lib.chromaprint_dealloc.argtypes = [ctypes.c_void_p]


def fp_file(path):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    ctx = lib.chromaprint_new(1)
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


def ber_at(q, r, off):
    """BER of q[i] against r[i + off] over the overlap; 1.0 when the overlap is too short."""
    i0, j0 = max(0, -off), max(0, off)
    n = min(len(q) - i0, len(r) - j0)
    if n < MIN_OVERLAP:
        return 1.0
    return float(popcount(q[i0:i0 + n] ^ r[j0:j0 + n]).sum() / (32.0 * n))


def ref_files():
    out = []
    out += sorted(glob.glob(E + "deam/audio/MEMD_audio/*.mp3"))
    out += sorted(glob.glob(E + "merp/audio/*.wav"))
    out += sorted(glob.glob(E + "emotify/audio/*/*.mp3"))
    for d in ("ballroom", "gtzan"):
        for root, _, fs in os.walk(T + d + "/audio"):
            out += sorted(os.path.join(root, f) for f in fs if f.lower().endswith(EXT) and not f.startswith("._"))
    out += [SONGS + n + ".m4a" for n in ("instant-crush", "five-years", "presence")]
    return out


def work(path):
    try:
        return path, fp_file(path)
    except Exception as e:
        return path, str(e)[:100]


def fingerprint_all(files, cache):
    have = dict(np.load(cache, allow_pickle=False)) if os.path.exists(cache) else {}
    todo = [f for f in files if f not in have]
    bad = {}
    with Pool(16) as p:
        for k, (f, r) in enumerate(p.imap_unordered(work, todo, chunksize=2)):
            if isinstance(r, str):
                bad[f] = r
            else:
                have[f] = r
            if k % 200 == 199:
                print(f"fingerprinted {k + 1}/{len(todo)}", flush=True)
                np.savez(cache, **have)
    np.savez(cache, **have)
    return have, bad


KEYS = (lambda v: v >> 16, lambda v: v & 0xFFFF, lambda v: (v >> 8) & 0xFFFF)


def build_index(refs):
    names = list(refs)
    allf = np.concatenate([refs[n] for n in names])
    rid = np.concatenate([np.full(len(refs[n]), i, dtype=np.int32) for i, n in enumerate(names)])
    pos = np.concatenate([np.arange(len(refs[n]), dtype=np.int32) for n in names])
    idx = []
    for kf in KEYS:
        kv = kf(allf)
        o = np.argsort(kv, kind="stable")
        idx.append((kv[o], rid[o], pos[o]))
    return names, idx


def match(q, refs, names, idx):
    """Best (ber, ref name, offset) of corpus fingerprint q against all references, or None."""
    votes = Counter()
    for kf, (kv, rid, pos) in zip(KEYS, idx):
        k = kf(q)
        lo, hi = np.searchsorted(kv, k, "left"), np.searchsorted(kv, k, "right")
        for qi in np.flatnonzero((hi - lo > 0) & (hi - lo <= 12)):
            for j in range(lo[qi], hi[qi]):
                votes[(int(rid[j]), int(qi) - int(pos[j]))] += 1   # offset: q index = r index + off
    best = None
    for (r, off), _ in votes.most_common(5):
        for d in range(-2, 3):
            b = ber_at(refs[names[r]], q, off + d)   # reference slid inside the corpus track
            if best is None or b < best[0]:
                best = (b, names[r], off + d)
    return best


def scan(audio_dir):
    refs = dict(np.load(C + "refs.npz"))
    names, idx = build_index(refs)
    files = sorted(glob.glob(audio_dir + "*.mp3"))
    fps, bad = fingerprint_all(files, C + "fingerprints.npz")
    rows = []
    for f in files:
        if f not in fps:
            continue
        m = match(fps[f], refs, names, idx)
        if m and m[0] < THRESH:
            rows.append((os.path.basename(f), round(m[0], 4), m[1], m[2]))
    with open(C + "fp_matches.csv", "w") as o:
        o.write("file,ber,reference,offset\n")
        for r in rows:
            o.write(",".join(str(x) for x in r) + "\n")
    print(f"scanned {len(fps)} files, unreadable {len(bad)} {sorted(bad)[:5]}, matches {len(rows)}")
    return 0


def main():
    if sys.argv[1] == "refs":
        files = ref_files()
        print(len(files), "reference files")
        refs, bad = fingerprint_all(files, C + "refs_cache.npz")
        np.savez(C + "refs.npz", **refs)
        print(f"refs {len(refs)} unreadable {len(bad)} {sorted(bad.items())[:3]}")
        return 0
    return scan(sys.argv[2] if len(sys.argv) > 2 else C + "audio/")


if __name__ == "__main__":
    sys.exit(main())
