"""The spread fix of docs/NEXT_DECODER_THEN_BRAIN.md, rule note 2026-10-29, A2.

A QuantileMap sends each body dimension's pre-sigmoid value to its rank among the training corpus's
values for that dimension: the empirical CDF, linear between ranks, equal values sharing their mean
rank. The ranks are then stretched linearly so that the `p_low` quantile lands on `out_low` and the
`p_high` quantile on `out_high`, and clipped to [0, 1]. With the note's anchors (0.05, 0.95 -> 0.05,
0.95) the result is the rank itself. Order is kept. Training values only are ever passed to `fit`.
"""
from __future__ import annotations

import numpy as np

P_LOW, P_HIGH = 0.05, 0.95
OUT_LOW, OUT_HIGH = 0.05, 0.95


def _ranks(sorted_unique, rank_of_unique, x):
    return np.interp(x, sorted_unique, rank_of_unique)


class QuantileMap:
    """Per-column empirical CDF of `values` (n, d) with the two anchors; call it on (m, d) values."""

    def __init__(self, values, p_low=P_LOW, p_high=P_HIGH, out_low=OUT_LOW, out_high=OUT_HIGH):
        values = np.asarray(values, dtype=np.float64)
        if values.ndim != 2 or len(values) < 2:
            raise ValueError("need (n >= 2, d) training values")
        if not 0.0 <= p_low < p_high <= 1.0:
            raise ValueError("need 0 <= p_low < p_high <= 1")
        self.anchors = (float(p_low), float(p_high), float(out_low), float(out_high))
        self.knots, self.ranks = [], []
        n = len(values)
        for col in values.T:
            unique, count = np.unique(col, return_counts=True)
            start = np.cumsum(count) - count
            self.knots.append(unique)
            self.ranks.append((start + (count - 1) / 2.0) / (n - 1))

    def __call__(self, z):
        z = np.asarray(z, dtype=np.float64)
        p_low, p_high, out_low, out_high = self.anchors
        p = np.column_stack([_ranks(k, r, z[:, j]) for j, (k, r) in enumerate(zip(self.knots, self.ranks))])
        return np.clip(out_low + (p - p_low) * (out_high - out_low) / (p_high - p_low), 0.0, 1.0)

    def with_anchors(self, p_low, p_high, out_low, out_high):
        """The same training values with other anchors (the one allowed adjustment, moved symmetrically)."""
        other = object.__new__(QuantileMap)
        other.knots, other.ranks = self.knots, self.ranks
        other.anchors = (float(p_low), float(p_high), float(out_low), float(out_high))
        return other

    def save(self, path):
        np.savez_compressed(path, anchors=np.array(self.anchors),
                            **{f"knots{j}": k for j, k in enumerate(self.knots)},
                            **{f"ranks{j}": r for j, r in enumerate(self.ranks)})

    @classmethod
    def load(cls, path):
        with np.load(path) as z:
            q = object.__new__(cls)
            q.anchors = tuple(float(a) for a in z["anchors"])
            d = len([k for k in z.files if k.startswith("knots")])
            q.knots = [z[f"knots{j}"] for j in range(d)]
            q.ranks = [z[f"ranks{j}"] for j in range(d)]
        return q
