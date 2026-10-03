import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from dance_structure import _descriptors, _validated_stem_interpretation, novelty_candidates, repeat_links


def frames(duration, changed=False):
    times = np.arange(0, duration, 0.02)
    count = len(times)
    rms = np.zeros(count) if not changed else np.where(times < duration/2, .1, .3)
    total = np.zeros(count) if not changed else np.ones(count)
    low = np.zeros(count) if not changed else np.where(times < duration/2, .7, .3)
    high = np.zeros(count) if not changed else np.where(times < duration/2, .1, .4)
    chroma = np.zeros((count, 12))
    if changed:
        chroma[times < duration/2, 0] = 1
        chroma[times >= duration/2, 4] = 1
    return {'duration': duration, 'times': times, 'rms': rms, 'total': total,
            'low': low, 'high': high, 'chroma': chroma,
            'flux': rms, 'lowFlux': low, 'highFlux': high}


def stem_estimates(duration, changed=False):
    count = int(np.ceil(duration * 20))
    sources = {name: {'absoluteRms': np.full(count, .02).tolist()}
               for name in ('vocals', 'drums', 'bass', 'other')}
    if changed:
        sources['vocals']['absoluteRms'] = np.where(np.arange(count) < count/2, .01, .2).tolist()
    return {'version': 1, 'method': 'estimated_stem_rms_spectral_flux_v1', 'duration': duration,
            'envelopeRate': 20, 'sources': sources,
            'provenance': {'kind': 'source_separation_estimates', 'groundTruth': False}}


class DanceStructureTests(unittest.TestCase):
    def test_silence_and_constant_features_have_no_confident_candidates_or_repeats(self):
        descriptors = _descriptors(frames(100), 0.5, 0)
        self.assertEqual(novelty_candidates(descriptors, 0.5, 0), [])
        self.assertEqual(repeat_links(descriptors, 0.5, 0), [])

    def test_planted_feature_change_ranks_near_its_boundary(self):
        descriptors = _descriptors(frames(80, changed=True), 0.5, 0)
        candidates = novelty_candidates(descriptors, 0.5, 0)
        self.assertTrue(candidates)
        best = max(candidates, key=lambda item: item['score'])
        self.assertLess(abs(best['time'] - 40), 0.5)
        self.assertGreater(best['components']['bandBalance'], 0)

    def test_repeated_descriptor_sequence_beats_shuffled_copy(self):
        rng = np.random.default_rng(4)
        motif = rng.normal(size=(32, 18))
        background = rng.normal(scale=.05, size=(160, 18))

        def score(target):
            beats = background.copy()
            beats[:32] = motif
            beats[80:112] = target
            subbeats = np.repeat(beats, 4, axis=0)
            return repeat_links(subbeats, .5, 0)

        repeated = score(motif)
        shuffled = score(motif[rng.permutation(len(motif))])
        self.assertTrue(repeated)
        self.assertEqual(repeated[0]['start'], 0)
        self.assertEqual(repeated[0]['repeatStart'], 40)
        self.assertGreater(repeated[0]['similarity'], shuffled[0]['similarity'] if shuffled else 0)

    def test_source_activity_can_change_structure_when_mix_is_identical(self):
        mix = frames(100)
        stable = _validated_stem_interpretation(stem_estimates(100), 100)
        changed = _validated_stem_interpretation(stem_estimates(100, changed=True), 100)
        no_change = novelty_candidates(_descriptors(mix, .5, 0, stable), .5, 0)
        source_change = novelty_candidates(_descriptors(mix, .5, 0, changed), .5, 0)
        self.assertEqual(no_change, [])
        best = max(source_change, key=lambda item: item['score'])
        self.assertLess(abs(best['time'] - 50), .5)
        self.assertGreater(best['components']['sourceParticipation'], 0)
        self.assertEqual(best['components']['level'], 0)
        self.assertEqual(best['components']['bandBalance'], 0)

    def test_source_envelope_requires_complete_finite_nonnegative_vector(self):
        bad = stem_estimates(10)
        bad['sources']['bass']['absoluteRms'] = [float('nan')]
        with self.assertRaises(ValueError):
            _validated_stem_interpretation(bad, 10)


if __name__ == '__main__':
    unittest.main()
