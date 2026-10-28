"""Representational similarity for check 3 (docs/NEXT_DECODER_THEN_BRAIN.md, "check 3 made operational").

A rank matrix holds, for every pair of segments, the rank (average ranks for ties, scaled to (0, 1]) of
their Euclidean distance among all pairs; the diagonal is 0 and never used. The Spearman correlation of
two distance matrices is the Pearson correlation of their rank matrices over the pairs i != j.

  rho(A, B)                    Spearman of two distance sets
  permutation_rhos(A, B, ...)  the same with the pairing of segments shuffled (B's rows and columns permuted
                               together; the set of pair ranks is unchanged, so no re-ranking is needed)
  weighted_rhos(A, B, W)       the same with segment weights w_i * w_j on pair (i, j), one column of W per
                               bootstrap resample (a song drawn twice weighs its segments twice); ranks stay
                               those of the full held-out fold
"""
from __future__ import annotations

import numpy as np
from scipy.spatial.distance import pdist, squareform
from scipy.stats import rankdata


def rank_matrix(x):
    """(n, d) standardised rows -> (n, n) float64 rank matrix of their pair distances."""
    n = len(x)
    if n < 3:
        raise ValueError("need at least 3 segments")
    d = pdist(np.asarray(x, dtype=np.float64))
    return squareform(rankdata(d) / len(d))


def _off_diagonal_moments(a, b):
    n = len(a)
    pairs = n * (n - 1)
    sa, sb = a.sum(), b.sum()
    return pairs, sa / pairs, sb / pairs, (a * a).sum() / pairs, (b * b).sum() / pairs


def _corr(sab, pairs, ma, mb, saa, sbb):
    den = np.sqrt((saa - ma * ma) * (sbb - mb * mb))
    return (sab / pairs - ma * mb) / den if den > 0 else float("nan")


def rho(a, b):
    """Spearman correlation of the two distance sets whose rank matrices are a and b."""
    pairs, ma, mb, saa, sbb = _off_diagonal_moments(a, b)
    return float(_corr((a * b).sum(), pairs, ma, mb, saa, sbb))


def permutation_rhos(a, b, n_perm, seed):
    """rho(a, b[p][:, p]) for n_perm random permutations p of the segment pairing."""
    rng = np.random.default_rng(seed)
    pairs, ma, mb, saa, sbb = _off_diagonal_moments(a, b)
    out = np.empty(n_perm)
    for i in range(n_perm):
        p = rng.permutation(len(a))
        out[i] = _corr((a * b[np.ix_(p, p)]).sum(), pairs, ma, mb, saa, sbb)
    return out


def weighted_rhos(a, b, weights):
    """Weighted Spearman, one value per column of `weights` (n, R): pair (i, j), i != j, weighs w_i w_j."""
    w = np.asarray(weights, dtype=np.float64)

    def quad(m):
        return (w * (m @ w)).sum(axis=0)

    s0 = w.sum(axis=0) ** 2 - (w * w).sum(axis=0)
    sa, sb, saa, sbb, sab = quad(a), quad(b), quad(a * a), quad(b * b), quad(a * b)
    ma, mb = sa / s0, sb / s0
    den = np.sqrt((saa / s0 - ma * ma) * (sbb / s0 - mb * mb))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, (sab / s0 - ma * mb) / den, np.nan)
