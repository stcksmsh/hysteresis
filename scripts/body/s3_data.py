"""Stage 3 data (docs/STAGE3_RULES_TRAIN.md sections 1-4): windows with a fast target (causal 30 s z-score, floored sd), a slow target (26A's corpus-normalised lanes), the previous block's
slow columns as extra policy input, and the tempo/RMS-matched batches of the InfoNCE. Existing modules are imported, never edited."""
import json
from pathlib import Path

import numpy as np
import jax
import jax.numpy as jnp

import k5_train as T
import k5p2_train as P2
import m3d
import m3e

S3 = Path("/secondary/hyst-data/body/s3")
N_FAST, N_SLOW = 4, 13
N_TGT = N_FAST + N_SLOW
SLOW_CLIP = 8.0
NB = T.NB
_SLOW = {}


def slow_lanes(s3, split, sid):
    key = (str(s3), split, sid)
    if key not in _SLOW:
        _SLOW[key] = np.load(Path(s3) / "slow" / split / f"{sid}.npz")["slow"].astype(float)
    return _SLOW[key]


def corpus_sd(k5, windows):
    """sd of the 4 fast columns over all blocks of `windows` [(sid, start)] of the train split, after m3d.transform_state (rules section 1)."""
    ys = np.concatenate([T.lanes(k5, "train", sid)[0][b:b + NB] for sid, b in windows])
    return m3d.transform_state(ys)[:, :N_FAST].std(0)


def fast_z(y4, floor_sd, win=m3e.ZWIN, minn=m3e.ZMIN, clip=m3e.CLIP_Z):
    """y4 (E, T, 4) -> causal z over the past `win` blocks (30 s), 0 where fewer than `minn` blocks, sd floored at floor_sd (4,), clipped. m3e.running_z with the floor."""
    z = np.zeros_like(y4, dtype=float)
    for b in range(minn - 1, y4.shape[1]):
        w = y4[:, max(0, b - win + 1):b + 1]
        z[:, b] = (y4[:, b] - w.mean(1)) / np.maximum(w.std(1), floor_sd)
    return np.clip(z, -clip, clip)


class Toy3(P2.WindowToyF):
    """WindowToyF plus: slow (E, 120, 13), tgt (E, 120, 17) = [fast z | slow], and the previous block's slow columns appended to the policy input x."""

    def inputs(self, idx, key):
        d = super().inputs(idx, key)
        sl = np.clip(self.slow[idx], -SLOW_CLIP, SLOW_CLIP)
        prev = np.concatenate([np.zeros_like(sl[:, :1]), sl[:, :-1]], 1)
        d["x"] = jnp.concatenate([d["x"], jnp.asarray(prev)], -1)
        return d


def build_toy3(k5, s3, split, wins, floor_sd):
    """wins [(song id, start block)] -> Toy3."""
    t = P2.build_toy(k5, split, wins)
    t.__class__ = Toy3
    t.slow = np.stack([slow_lanes(s3, split, sid)[b:b + NB] for sid, b in wins])
    assert t.slow.shape == (len(wins), NB, N_SLOW), t.slow.shape
    t.tgt = np.concatenate([fast_z(t.y[..., :N_FAST], floor_sd), np.clip(t.slow, -SLOW_CLIP, SLOW_CLIP)], -1).astype(np.float32)
    t.wins = [tuple(w) for w in wins]
    return t


def combine3(a, b):
    """Observer-training windows a followed by evaluation windows b (as k5p2_train.combine)."""
    t = P2.combine(a, b)
    t.__class__ = Toy3
    t.slow, t.tgt, t.wins = np.concatenate([a.slow, b.slow]), np.concatenate([a.tgt, b.tgt]), a.wins + b.wins
    return t


# ---------------------------------------------------------------------------------------------------------------- matched batches
class Matched:
    """Nearest train songs by sqrt(((dBPM)/10)^2 + (dlogRMS/0.3)^2), and the batch of a round (rules section 2, point 2)."""

    def __init__(self, tempo_rms, windows, batch=8):
        self.batch = batch
        by_song = {}
        for sid, b in windows:
            by_song.setdefault(sid, []).append((sid, int(b)))
        self.songs = sorted(s for s in by_song if s in tempo_rms)
        self.by_song = {s: by_song[s] for s in self.songs}
        bpm = np.array([tempo_rms[s]["bpm"] for s in self.songs], float)
        lr = np.array([tempo_rms[s]["log_rms"] for s in self.songs], float)
        self.d = np.sqrt(((bpm[:, None] - bpm[None]) / 10.0) ** 2 + ((lr[:, None] - lr[None]) / 0.3) ** 2)
        self.pos = {s: i for i, s in enumerate(self.songs)}

    def nearest(self, sid, k):
        """The k nearest other songs, ties broken by position in the sorted id list."""
        i = self.pos[sid]
        order = np.lexsort((np.arange(len(self.songs)), self.d[i]))
        return [self.songs[j] for j in order if j != i][:k]

    def batch_of(self, anchor, round_, group):
        """anchor window (sid, start) -> [anchor window] + one window of each of the nearest (batch - 1) songs, drawn with default_rng([SEED, round, group, rank])."""
        out = [tuple(anchor)]
        for rank, s in enumerate(self.nearest(anchor[0], self.batch - 1)):
            ws = self.by_song[s]
            out.append(ws[int(np.random.default_rng([T.SEED, round_, group, rank]).integers(0, len(ws)))])
        return out

    def round_windows(self, order, r):
        """The 2 x batch windows of round r: group A (anchor order[2r' ] ...). Anchors are order[round_windows * r] and order[round_windows * r + 1]."""
        a = order[2 * self.batch * r], order[2 * self.batch * r + 1]
        return self.batch_of(a[0], r, 0) + self.batch_of(a[1], r, 1)


def load_inputs(s3=S3):
    s3 = Path(s3)
    tr = json.loads((s3 / "tempo_rms.json").read_text())
    th = json.loads((s3 / "thresholds.json").read_text())
    return tr, th
