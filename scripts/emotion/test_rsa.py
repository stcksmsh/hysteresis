"""Tests of the representational similarity maths (rsa.py). Synthetic data only."""
import unittest

import numpy as np
from scipy.spatial.distance import pdist
from scipy.stats import rankdata, spearmanr

import rsa


def upper(m):
    return m[np.triu_indices(len(m), 1)]


class RsaTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1)
        self.x = rng.normal(size=(14, 3))
        self.y = self.x @ rng.normal(size=(3, 5)) + 0.5 * rng.normal(size=(14, 5))

    def test_rank_matrix_is_the_scaled_rank_of_the_distances(self):
        m = rsa.rank_matrix(self.x)
        np.testing.assert_allclose(upper(m), rankdata(pdist(self.x)) / len(pdist(self.x)))
        np.testing.assert_array_equal(m, m.T)
        np.testing.assert_array_equal(np.diag(m), 0)

    def test_rho_is_spearman_of_the_pair_distances(self):
        a, b = rsa.rank_matrix(self.x), rsa.rank_matrix(self.y)
        self.assertAlmostEqual(rsa.rho(a, b), spearmanr(pdist(self.x), pdist(self.y))[0], places=12)

    def test_rho_is_one_for_equal_and_minus_one_for_reversed_ranks(self):
        a = rsa.rank_matrix(self.x)
        self.assertAlmostEqual(rsa.rho(a, a), 1.0, places=12)
        reversed_ = (1.0 - a) * (1 - np.eye(len(a)))
        self.assertAlmostEqual(rsa.rho(a, reversed_), -1.0, places=12)

    def test_ties_get_average_ranks(self):
        x = np.array([[0.0], [1.0], [2.0], [3.0]])        # distances 1,2,3,1,2,1: three ties of 1
        np.testing.assert_allclose(sorted(upper(rsa.rank_matrix(x)) * 6), [2, 2, 2, 4.5, 4.5, 6])

    def test_too_few_segments(self):
        with self.assertRaises(ValueError):
            rsa.rank_matrix(self.x[:2])

    def test_permutation_equals_recomputing_with_the_descriptors_shuffled(self):
        a, b = rsa.rank_matrix(self.x), rsa.rank_matrix(self.y)
        got = rsa.permutation_rhos(a, b, 5, seed=3)
        rng = np.random.default_rng(3)
        for value in got:
            p = rng.permutation(len(self.x))
            self.assertAlmostEqual(value, spearmanr(pdist(self.x), pdist(self.y[p]))[0], places=12)

    def test_permutation_is_seeded_and_centred_on_zero(self):
        rng = np.random.default_rng(5)
        a, b = rsa.rank_matrix(rng.normal(size=(60, 4))), rsa.rank_matrix(rng.normal(size=(60, 4)))
        one, two = rsa.permutation_rhos(a, b, 200, 11), rsa.permutation_rhos(a, b, 200, 11)
        np.testing.assert_array_equal(one, two)
        self.assertFalse(np.array_equal(one, rsa.permutation_rhos(a, b, 200, 12)))
        self.assertLess(abs(one.mean()), 0.02)

    def test_a_real_relation_beats_every_permutation(self):
        rng = np.random.default_rng(6)
        x = rng.normal(size=(60, 4))
        a, b = rsa.rank_matrix(x), rsa.rank_matrix(x @ rng.normal(size=(4, 6)))
        self.assertGreater(rsa.rho(a, b), rsa.permutation_rhos(a, b, 300, 1).max())

    def test_unit_weights_give_rho(self):
        a, b = rsa.rank_matrix(self.x), rsa.rank_matrix(self.y)
        w = rsa.weighted_rhos(a, b, np.ones((len(a), 3)))
        np.testing.assert_allclose(w, rsa.rho(a, b), atol=1e-12)

    def test_integer_weights_equal_the_expanded_pair_list(self):
        a, b = rsa.rank_matrix(self.x), rsa.rank_matrix(self.y)
        w = np.array([2, 0, 1, 3, 1, 1, 0, 2, 1, 1, 1, 2, 1, 1], dtype=float)
        xs, ys = [], []
        for i in range(len(w)):
            for j in range(len(w)):
                if i != j:
                    xs += [a[i, j]] * int(w[i] * w[j])
                    ys += [b[i, j]] * int(w[i] * w[j])
        self.assertAlmostEqual(rsa.weighted_rhos(a, b, w[:, None])[0], np.corrcoef(xs, ys)[0, 1], places=12)

    def test_dropping_a_segment_with_weight_zero_matches_dropping_its_pairs(self):
        a, b = rsa.rank_matrix(self.x), rsa.rank_matrix(self.y)
        w = np.ones(len(a))
        w[4] = 0
        keep = np.arange(len(a)) != 4
        want = rsa.rho(a[np.ix_(keep, keep)], b[np.ix_(keep, keep)])
        self.assertAlmostEqual(rsa.weighted_rhos(a, b, w[:, None])[0], want, places=12)


if __name__ == "__main__":
    unittest.main()
