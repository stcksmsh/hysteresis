"""Tests of check 3 (check3.py). Synthetic data only; the body generator is the real one, nothing of ours is mocked."""
import json
import pathlib
import tempfile
import unittest

import numpy as np

import check3
import common
import decoder
import mood
from mind import Clip
from test_decoder import small_surrogate

D = 14


def corpus(seed=0):
    """Synthetic clips: encoding = fixed mix of three slow latent factors (arousal, power, other) plus noise."""
    rng = np.random.default_rng(seed)
    mix = np.random.default_rng(99).normal(size=(3, D))

    def encoding(steps):
        latent = np.cumsum(rng.normal(scale=0.25, size=(steps, 3)), axis=0) + rng.normal(size=3)
        return (latent @ mix + rng.normal(scale=0.1, size=(steps, D))).astype(np.float32), latent

    clips = []
    for i in range(30):
        x, lat = encoding(50)
        y = np.stack([np.zeros(50), lat[:, 0]], axis=1)
        clips.append(Clip(f"deam_{i}", "deam", x, np.arange(0, 25, 0.5), y, np.arange(30, 50, 4)))
    for i in range(20):
        x, lat = encoding(60)
        profile = np.zeros(9)
        profile[common.GEMS.index("power")] = lat[:, 1].mean()
        clips.append(Clip(f"emotify_{i}", "emotify", x, np.arange(0, 30, 0.5), None, np.arange(4, 60, 4), profile))
    for i in range(6):
        x, lat = encoding(100)
        y = np.stack([np.zeros(100), lat[:, 0]], axis=1)
        clips.append(Clip(f"merp_{i}", "merp", x, np.arange(0, 50, 0.5), y, np.arange(4, 100, 4)))
    for i in range(3):
        x, _ = encoding(100)
        clips.append(Clip(f"song_{i}", "song", x, np.arange(0, 50, 0.5), extra={"duration": 50.0}))
    real = [c for c in clips if c.ds != "song"]
    folds = common.assign_folds([c.key for c in real])
    folds.update({c.key: check3.SIXTH for c in clips if c.ds == "song"})
    return clips, folds


def config(**kw):
    base = dict(core=False, n_perm=30, n_boot=40, std_segments=60, fit={"steps": 25}, k_grid=(2, 4), baseline_columns=6)
    base.update(kw)
    return check3.Config(**base)


def fold_data(z, desc_z, songs=None):
    songs = songs or [f"s{i}" for i in range(len(z))]
    return {"z": z, "desc_z": desc_z, "songs": songs, "total": len(z), "failed": 0}


class SegmentTests(unittest.TestCase):
    def test_whole_windows_only_and_non_overlapping(self):
        clips, _ = corpus()
        table = check3.segment_table(clips)
        self.assertEqual(len(table), 30 * 3 + 20 * 3 + 6 * 6 + 3 * 6)
        self.assertEqual(table[:4], [(0, 0), (0, 16), (0, 32), (1, 0)])
        short = [Clip("x", "deam", np.zeros((31, 2)), np.zeros(1))]
        self.assertEqual(check3.segment_table(short), [(0, 0)])

    def test_segment_mood_is_the_mean_of_its_16_steps(self):
        clips, _ = corpus()
        model = mood.fit([c.x for c in clips if c.ds != "song"], check3.arousal_rows([c for c in clips if c.ds != "song"], {c.key: c.x for c in clips}),
                         check3.power_rows([c for c in clips if c.ds != "song"], {c.key: c.x for c in clips}), k=3)
        feats = {c.key: c.x for c in clips}
        lanes, keys = check3.segment_lanes(model, feats, clips[:2])
        full = model.lanes(clips[0].x)
        np.testing.assert_allclose(lanes[1], full[16:32].mean(axis=0))
        self.assertEqual(keys, ["deam_0"] * 3 + ["deam_1"] * 3)


class SplitTests(unittest.TestCase):
    def test_folds_never_mix_and_the_users_songs_are_never_trained_on(self):
        clips, folds = corpus()
        seen = set()
        for f in range(common.N_FOLDS):
            train, test = check3.split(clips, folds, f)
            keys_tr, keys_te = {c.key for c in train}, {c.key for c in test}
            self.assertFalse(keys_tr & keys_te)
            self.assertTrue(all(folds[k] == f for k in keys_te))
            self.assertTrue(all(folds[k] != f for k in keys_tr))
            self.assertFalse(any(c.ds == "song" for c in train + test))
            self.assertFalse(seen & keys_te)
            seen |= keys_te
        train, test = check3.split(clips, folds, check3.SIXTH)
        self.assertEqual({c.ds for c in test}, {"song"})
        self.assertEqual(len(train), 56)
        self.assertEqual(seen, {c.key for c in train})


class ScoringTests(unittest.TestCase):
    def folds(self, aligned, n=5, size=40, seed=0):
        rng = np.random.default_rng(seed)
        out = []
        for _ in range(n):
            z = rng.normal(size=(size, 4))
            out.append(fold_data(z, z @ rng.normal(size=(4, 9)) if aligned else rng.normal(size=(size, 9))))
        return out

    def test_shuffle_threshold_is_exactly_99_percent(self):
        self.assertTrue(check3.shuffle_passes(990, 1000))
        self.assertFalse(check3.shuffle_passes(989, 1000))
        self.assertTrue(check3.shuffle_passes(100, 100))
        self.assertFalse(check3.shuffle_passes(98, 100))

    def test_alike_in_mood_alike_in_motion_passes_and_unrelated_fails(self):
        good = check3.score_map(self.folds(True), 100)
        bad = check3.score_map(self.folds(False), 100)
        self.assertGreater(good["rho"], 0.6)
        self.assertEqual(good["beaten"], 100)
        self.assertTrue(good["pass"])
        self.assertLess(abs(bad["rho"]), 0.1)
        self.assertFalse(bad["pass"])
        self.assertLess(bad["beaten"], 99)

    def test_the_gate_uses_the_mean_over_the_folds(self):
        folds = self.folds(True)
        result = check3.score_map(folds, 20)
        self.assertAlmostEqual(result["rho"], float(np.mean(result["rhoPerFold"])), places=12)
        self.assertEqual(len(result["rhoPerFold"]), 5)

    def test_failed_segments_are_counted_not_hidden(self):
        folds = self.folds(True)
        folds[2] = dict(folds[2], total=45, failed=5)
        result = check3.score_map(folds, 10)
        self.assertEqual(result["failed"], [0, 0, 5, 0, 0])
        self.assertEqual(result["total"], [40, 40, 45, 40, 40])

    def test_seeded(self):
        a, b = check3.score_map(self.folds(False), 40), check3.score_map(self.folds(False), 40)
        self.assertEqual(a, b)

    def bootstrap(self, dec_aligned, base_aligned):
        songs = [[f"f{f}s{i // 2}" for i in range(40)] for f in range(5)]
        dec, base = self.folds(dec_aligned, seed=1), self.folds(base_aligned, seed=2)
        for f in range(5):
            dec[f]["songs"], base[f]["songs"] = songs[f], songs[f]
        _, dm = check3.score_map(dec, 1, keep=True)
        _, bm = check3.score_map(base, 1, keep=True)
        return check3.bootstrap_difference(dec, dm, base, bm, 200)

    def test_bootstrap_difference_direction(self):
        better, worse, same = self.bootstrap(True, False), self.bootstrap(False, True), self.bootstrap(False, False)
        self.assertGreater(better["difference"][0], 0)
        self.assertTrue(better["pass"])
        self.assertLess(worse["difference"][1], 0)
        self.assertFalse(worse["pass"])
        self.assertLess(same["difference"][0], 0 + 1e-9)
        self.assertFalse(same["pass"])
        self.assertEqual(better["songs"], 100)

    def test_bootstrap_is_seeded(self):
        self.assertEqual(self.bootstrap(True, False), self.bootstrap(True, False))


class DialTests(unittest.TestCase):
    def setup(self, sign_energy=(1, 1, 1), sign_power=(1, 1, 1)):
        rng = np.random.default_rng(3)
        lanes, dial = {}, {}
        for i, key in enumerate(("a", "b", "c")):
            t = np.cumsum(rng.normal(size=120))
            steps = 120
            lanes[key] = np.column_stack([sign_energy[i] * t + rng.normal(scale=0.1, size=steps),
                                          sign_power[i] * t + rng.normal(scale=0.1, size=steps)])
            series = np.repeat(t, 5)[:600]
            dial[key] = {"energy10": series, "masks": [], "heavy10": series, "light10": -series}
        return lanes, dial

    def test_energy_sign_must_be_positive_on_every_song(self):
        lanes, dial = self.setup()
        self.assertTrue(check3.dial_checks(lanes, dial, list(lanes))["energyPass"])
        lanes, dial = self.setup(sign_energy=(1, -1, 1))
        result = check3.dial_checks(lanes, dial, list(lanes))
        self.assertFalse(result["energyPass"])
        self.assertEqual([v["positive"] for v in result["energy"].values()], [True, False, True])

    def test_power_anchor_is_dropped_when_two_of_three_disagree(self):
        for signs, dropped, disagree in (((1, 1, 1), False, 0), ((1, 1, -1), False, 1), ((1, -1, -1), True, 2), ((-1, -1, -1), True, 3)):
            lanes, dial = self.setup(sign_power=signs)
            result = check3.dial_checks(lanes, dial, list(lanes))
            self.assertEqual((result["powerAnchorDropped"], result["powerDisagree"]), (dropped, disagree))

    def test_masked_steps_are_left_out(self):
        lanes, dial = self.setup()
        dial["a"]["masks"] = [(0.0, 30.0)]
        result = check3.dial_checks(lanes, dial, list(lanes))
        self.assertLess(result["energy"]["a"]["steps"], result["energy"]["b"]["steps"])


class RunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.surrogate = small_surrogate()
        cls.clips, cls.folds = corpus()

    def run_once(self, out=None, dial=None):
        return check3.run(self.clips, self.folds, self.surrogate, config(), dial, out, log=lambda s: None)

    def test_end_to_end_is_deterministic_and_folds_are_disjoint(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            a = self.run_once(d)
            b = self.run_once()
            a.pop("seconds"), b.pop("seconds")
            self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
            held = []
            for tag in range(6):
                z = np.load(d / f"segments_{tag}.npz")
                for name in ("decoder", "baseline49", "library"):
                    n = len(z[f"{name}/keys"])
                    self.assertEqual((z[f"{name}/bodies"].shape, z[f"{name}/desc"].shape, z[f"{name}/lanes"].shape[0]), ((n, 15), (n, 37), n))
                    self.assertTrue(np.isfinite(z[f"{name}/bodies"]).all())
                keys = set(z["decoder/keys"].tolist())
                held.append(keys)
                if tag == check3.SIXTH:
                    self.assertTrue(all(k.startswith("song_") for k in keys))
                else:
                    self.assertTrue(all(self.folds[k] == tag for k in keys))
            for i in range(6):
                for j in range(i):
                    self.assertFalse(held[i] & held[j])
            self.assertEqual(len(set().union(*held)), len(self.clips))
            self.assertTrue((d / "results.json").exists())
        self.assertEqual(set(a["maps"]), {"decoder", "baseline49", "library"})
        self.assertEqual(a["pass"]["energySign"], None)
        self.assertEqual(a["maps"]["decoder"]["of"], 30)
        for m in a["maps"].values():
            self.assertEqual(len(m["rhoPerFold"]), 5)
            self.assertEqual(m["sixth"]["of"], 30)

    def test_a_decoder_that_sees_a_structured_world_scores_above_zero(self):
        result = self.run_once()
        self.assertGreater(result["maps"]["decoder"]["rho"], 0.05)

    def test_energy_sign_gate_reads_the_final_model_on_the_songs(self):
        songs = [c for c in self.clips if c.ds == "song"]
        dial = {}
        for c in songs:
            rng = np.random.default_rng(len(c.key))
            dial[c.key] = {"energy10": rng.random(600), "masks": []}
        result = self.run_once(dial=dial)
        self.assertEqual(sorted(result["dial"]["energy"]), sorted(c.key for c in songs))
        self.assertEqual(result["pass"]["energySign"], result["dial"]["energyPass"])
        self.assertEqual(result["check3"], bool(all(v is True for v in result["pass"].values())))


if __name__ == "__main__":
    unittest.main()
