"""Tests of check2b.py on a synthetic world and fake dial files (never real data).
Run: cd scripts/emotion && /secondary/hyst-env/emotion/bin/python -m unittest
"""
import json
import pathlib
import tempfile
import unittest

import numpy as np

import check1b
import check2b
import common
import mind
import smoothing
from mind import Clip
from test_check1b import CFG as CFG1, gate_world, pred_with_r, synthetic_world, write_dial

CFG = check2b.Config2b(units=24, ear_k=6, state_k=8, rehearsal_k=3, sr_grid=(0.8, 0.95), n_boot=60, n_draws=60,
                       taus=(0.0, 2.0, 4.0), lags=(0.0, 1.0, 2.0))


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.world = synthetic_world()
        self.clips = self.world.deam[:6]
        ear = mind.fit_projector([c.x for c in self.clips], 6)
        self.model = mind.MindModel(ear, 0.9, mind.SEED_CORE, 24, state_k=8, rehearsal_k=3).fit_state(self.clips)

    def test_the_core_has_no_rehearsal_input(self):
        self.assertIsNone(self.model.rehearsal)                    # no rehearsal projector exists
        plain = self.model.run_plain(self.clips)
        for c in self.clips:                                       # beats play no part: the rehearsal index uses them
            c.beats = np.arange(0.3, 300, 1.7)
        again = self.model.run_plain(self.clips)
        for c in self.clips:
            np.testing.assert_array_equal(plain[c.key]["state"], again[c.key]["state"])
        # the state is the round-1 core's rho = 0 state: pass 1, nothing else
        ear = mind.fit_projector([c.x for c in self.clips], 6)
        full = mind.MindModel(ear, 0.9, mind.SEED_CORE, 24, state_k=8, rehearsal_k=3).fit_projectors(self.clips)
        zero = full.run(self.clips[:2], 0.0)
        plain2 = full.run_plain(self.clips[:2])
        for c in self.clips[:2]:
            np.testing.assert_array_equal(plain2[c.key]["state"], zero[c.key]["mind"])

    def test_readouts_receive_the_state_and_the_ear(self):
        out = self.model.run_plain(self.clips[:1])
        c = self.clips[0]
        feats = check2b.core_features(out, c)
        self.assertEqual(feats.shape, (len(c.x), 8 + 6))
        np.testing.assert_array_equal(feats[:, :8], out[c.key]["state"])
        np.testing.assert_array_equal(feats[:, 8:], self.model.ear(c.x))
        fit = check2b.fit_2b(self.world.deam + self.world.emotify + self.world.merp, CFG)
        self.assertEqual(fit["readouts"]["va_core"].model[0].shape[0], CFG.state_k + CFG.ear_k)
        self.assertEqual(fit["readouts"]["va_ref"].model[0].shape[0], check1b.DIM if hasattr(check1b, "DIM") else 10)

    def test_predictions_apply_each_sides_chosen_smoothing(self):
        fit = check2b.fit_2b(self.world.deam + self.world.emotify + self.world.merp, CFG)
        fit["smoothing"] = {"core": {"tau": 4.0, "lag": 1.0}, "ref": {"tau": 2.0, "lag": 0.5}}
        out = check2b.predict(fit, self.world.songs[:1])[self.world.songs[0].key]
        np.testing.assert_allclose(out["core_s"], smoothing.smooth_delay(out["core"], 4.0, 1.0))
        np.testing.assert_allclose(out["ref_s"], smoothing.smooth_delay(out["ref"], 2.0, 0.5))
        self.assertFalse(np.allclose(out["core_s"], out["core"]))

    def test_the_shuffle_keeps_the_step_ear_and_scrambles_the_history(self):
        order = np.random.default_rng(1).permutation(len(self.clips[0].x))
        c = self.clips[0]
        a = self.model.run_plain([c])[c.key]
        b = self.model.run_plain([c], {c.key: order})[c.key]
        np.testing.assert_array_equal(b["ear"], a["ear"][order])
        self.assertFalse(np.allclose(b["state"], a["state"][order]))


class ChoiceTests(unittest.TestCase):
    def test_choose_smoothing_recovers_the_tau_and_lag_that_made_the_labels(self):
        rng = np.random.default_rng(3)
        clips, pred = [], {}
        for i in range(8):
            latent = rng.normal(size=120)
            y = np.zeros((120, 2))
            y[:, 1] = smoothing.smooth_delay(latent, 4.0, 1.0)
            clips.append(Clip(f"deam_{i}", "deam" if i % 2 else "merp", np.zeros((120, 1)), np.arange(0, 100, 0.5), y, np.arange(10, 110, 2)))
            pred[f"deam_{i}"] = np.stack([latent, latent], axis=1)
        tau, lag, score = check2b.choose_smoothing(clips, pred, CFG)
        self.assertEqual((tau, lag), (4.0, 1.0))
        self.assertGreater(score, 0.99)

    def test_the_test_fold_never_reaches_a_choice(self):
        world = synthetic_world()
        dial_dir = tempfile.mkdtemp()
        write_dial(dial_dir)
        dial = check1b.load_dial(pathlib.Path(dial_dir) / "dial2.json", pathlib.Path(dial_dir) / "dial-ic-try1.json")
        base = check2b.run(world, dial, CFG, None, log=lambda s: None)
        wrecked_world = synthetic_world()
        for c in wrecked_world.deam + wrecked_world.merp:
            if wrecked_world.folds[c.key] == 0:
                c.y[:] = np.random.default_rng(9).normal(size=c.y.shape)
        wrecked = check2b.run(wrecked_world, dial, CFG, None, log=lambda s: None)
        self.assertEqual(wrecked["chosen"]["0"], base["chosen"]["0"])           # radius, tau, L and the scores behind them
        self.assertNotEqual(wrecked["chosen"]["1"]["smoothing"], base["chosen"]["1"]["smoothing"])


class GateTests(unittest.TestCase):
    cfg = CFG

    def collected(self, world, core_s, ref_s, core=None, ref=None):
        out = {}
        for k, c in enumerate(world.deam + world.merp):
            truth = c.y[:, 1]
            def series(r):
                vals = pred_with_r(truth[c.rows], r[k % len(r)])
                full = np.zeros((len(truth), 2))
                full[c.rows, 1] = vals
                full[c.rows, 0] = vals
                return full
            out[c.key] = {"core_s": series(core_s), "ref_s": series(ref_s),
                          "core": series(core or core_s), "ref": series(ref or ref_s)}
        return out

    def test_a1_needs_the_core_clearly_above_the_smoothed_reference(self):
        world = gate_world()[0]
        self.assertTrue(check2b.gate_a1(self.collected(world, [0.9], [0.1]), world, self.cfg)["pass"])
        self.assertFalse(check2b.gate_a1(self.collected(world, [0.1], [0.9]), world, self.cfg)["pass"])
        wide = check2b.gate_a1(self.collected(world, [1.0, -0.2], [0.2]), world, self.cfg)
        self.assertGreater(wide["deam"]["arousal"]["core_smoothed"][0], wide["deam"]["arousal"]["reference_smoothed"][1][1])
        self.assertFalse(wide["deam"]["pass"])                       # mean above the upper bound, lower bound not
        # it compares the smoothed series, not the raw ones
        mixed = check2b.gate_a1(self.collected(world, [0.9], [0.1], core=[0.1], ref=[0.9]), world, self.cfg)
        self.assertTrue(mixed["pass"])
        self.assertAlmostEqual(mixed["deam"]["arousal"]["core"][0], 0.1, places=2)

    def test_a1_needs_both_datasets(self):
        world = gate_world()[0]
        collected = self.collected(world, [0.9], [0.1])
        for c in world.merp:
            collected[c.key]["core_s"] = collected[c.key]["ref_s"]
        result = check2b.gate_a1(collected, world, self.cfg)
        self.assertTrue(result["deam"]["pass"] and not result["merp"]["pass"] and not result["pass"])

    def test_b_is_the_smoothed_core_against_the_smoothed_reference_on_two_of_three(self):
        names = [k for k, *_ in check1b.SONGS]
        world = check1b.World([], [], [], [Clip(k, "song", np.zeros((561, 3), np.float32), np.arange(0, 280, 0.5)) for k in names], {})
        rng = np.random.default_rng(4)
        curve = np.interp(np.arange(2800) / 10.0, [0, 60, 120, 200, 280], [0.1, 0.8, 0.2, 0.9, 0.3])
        dial = {k: {"masks": [], "source": {}, "energy10": curve} for k in names}
        follow = check1b._dial_steps(curve, 561, [])
        def preds(winners):
            out = {}
            for k in names:
                good, bad = np.stack([follow] * 2, axis=1), rng.normal(size=(561, 2))
                core_s, ref_s = (good, bad) if k in winners else (bad, good)
                out[k] = {"core_s": core_s, "ref_s": ref_s, "core": ref_s, "ref": core_s, "gems_core": np.full((561, 9), 0.1)}
            return out
        two = check2b.gate_b(preds(names[:2]), dial, world, None)
        self.assertEqual((two["dial"]["wins"], two["dial"]["pass"]), (2, True))
        one = check2b.gate_b(preds(names[:1]), dial, world, None)
        self.assertEqual((one["dial"]["wins"], one["dial"]["pass"]), (1, False))
        entry = two["songs"][names[0]]
        self.assertGreater(entry["core"], entry["coreUnsmoothed"])   # smoothed core listed first, raw beside it
        self.assertGreater(entry["referencePlain"], entry["reference"])
        round1 = {"gate5": {"songs": {k: {"core": 0.25, "reference": 0.5} for k in names}}}
        self.assertEqual(check2b.gate_b(preds(names[:2]), dial, world, round1)["songs"][names[0]]["round1Core"], 0.25)

    def test_the_outcome_logic(self):
        self.assertIn("encoding for stage 3", check2b.outcome(True, True))
        self.assertIn("A1 and B pass", check2b.outcome(True, True))
        self.assertIn("A1 fails", check2b.outcome(False, True))
        self.assertIn("A1 fails", check2b.outcome(False, False))
        self.assertIn("the user decides", check2b.outcome(True, False))

    def test_a2_reads_the_deam_only_core_and_round_ones_bounds(self):
        rng = np.random.default_rng(2)
        deam = [Clip(f"deam_{i}", "deam", np.zeros((40, 2), np.float32), np.arange(0, 100, 0.5),
                     np.stack([np.sin(np.arange(40) / 3 + i), np.cos(np.arange(40) / 4 + i)], axis=1), np.arange(0, 40, 2)) for i in range(10)]
        emotify = [Clip(f"emotify_{i}", "emotify", np.zeros((40, 2), np.float32), np.arange(0, 100, 0.5), None, np.arange(4, 40, 4),
                        rng.dirichlet(np.ones(9))) for i in range(10)]
        world = check1b.World(deam, emotify, [], [], {})
        def collected(good_r2, other_r2):
            def pred(c, r2):
                return (1 - np.sqrt(1 - r2)) * c.y
            out = {c.key: {"core_deam": pred(c, good_r2), "ref_deam": pred(c, good_r2), "core": pred(c, other_r2)} for c in deam}
            out.update({c.key: {"gems_core": c.profile, "gems_ref": c.profile} for c in emotify})
            return out
        cfg = check2b.Config2b(n_boot=50)
        self.assertTrue(check2b.gate_a2(collected(0.60, 0.0), world, cfg)["pass"])       # only the DEAM-only predictions count
        self.assertFalse(check2b.gate_a2(collected(0.57, 0.9), world, cfg)["timing"]["pass"])
        self.assertAlmostEqual(check2b.gate_a2(collected(0.60, 0.0), world, cfg)["timing"]["value"], 0.60, delta=0.02)
        mixed = collected(0.60, 0.0)
        for c in deam:
            mixed[c.key]["ref_deam"] = (1 - np.sqrt(1 - 0.30)) * c.y
        self.assertAlmostEqual(check2b.gate_a2(mixed, world, cfg)["reference"]["timing"], 0.30, delta=0.02)   # the reference's own readout

    def test_a2_and_a3_are_round_ones_gates_on_the_core(self):
        world = synthetic_world()
        gw = gate_world()[0]
        def at_rows(c, r):
            out = np.zeros((len(c.y), 2))
            out[c.rows, 1] = pred_with_r(c.y[c.rows, 1], r)
            return out
        coll = {c.key: {"core": at_rows(c, 0.8)} for c in gw.deam + gw.merp}
        shuffled = lambda r: {c.key: at_rows(c, r)[c.rows] for c in gw.deam + gw.merp}
        self.assertTrue(check2b.gate_a3(coll, shuffled(0.3), gw, self.cfg)["pass"])
        self.assertFalse(check2b.gate_a3(coll, shuffled(0.5), gw, self.cfg)["pass"])


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = synthetic_world()
        cls.dir = tempfile.TemporaryDirectory()
        write_dial(cls.dir.name)
        cls.dial = check1b.load_dial(pathlib.Path(cls.dir.name) / "dial2.json", pathlib.Path(cls.dir.name) / "dial-ic-try1.json")
        cls.out = pathlib.Path(cls.dir.name) / "out"
        cls.out.mkdir()
        round1 = {"gate5": {"songs": {k: {"core": 0.1, "reference": 0.2} for k, *_ in check1b.SONGS}}}
        cls.results = check2b.run(cls.world, cls.dial, CFG, cls.out, round1, log=lambda s: None)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_everything_is_computed_and_reported(self):
        r = self.results
        for gate in ("A1", "A2", "A3"):
            self.assertIsInstance(r[gate]["pass"], bool)
        self.assertIsInstance(r["B"]["dial"]["pass"], bool)
        self.assertEqual(r["pass"], {"A1": r["A1"]["pass"], "B": r["B"]["dial"]["pass"]})
        self.assertEqual(r["outcome"], check2b.outcome(r["A1"]["pass"], r["B"]["dial"]["pass"]))
        self.assertEqual(set(r["chosen"]), {"0", "1", "2", "3", "4", "all"})
        for f, c in r["chosen"].items():
            self.assertIn(c["radius"], CFG.sr_grid)
            for side in ("core", "ref"):
                self.assertIn(c["smoothing"][side]["tau"], CFG.taus)
                self.assertIn(c["smoothing"][side]["lag"], CFG.lags)
        self.assertEqual(r["B"]["songs"]["instant-crush"]["round1Core"], 0.1)
        lines = []
        check2b.report(r, lines.append)
        text = "\n".join(lines)
        for tag in ("A1:", "A2:", "A3:", "B:", "OUTCOME:"):
            self.assertIn(tag, text)

    def test_the_saved_predictions_recompute_gate_a1(self):
        held = np.load(self.out / "predictions_heldout.npz")
        r = []
        for c in self.world.deam:
            r.append(check1b.within_r(held[f"{c.key}/core_s"][held[f"{c.key}/rows"], 1], held[f"{c.key}/y"][held[f"{c.key}/rows"], 1]))
        mean = float(np.mean(r))
        self.assertAlmostEqual(mean, self.results["A1"]["deam"]["arousal"]["core_smoothed"][0], places=5)   # stored as float32
        songs = np.load(self.out / "predictions_songs.npz")
        for key, *_ in check1b.SONGS:
            for name in ("core", "core_s", "ref", "ref_s", "dial_steps"):
                self.assertIn(f"{key}/{name}", songs.files)
        dial_r = check1b.dial_correlation(songs["presence/core_s"][:, 1], songs["presence/dial_steps"])[0]
        self.assertAlmostEqual(dial_r, self.results["B"]["songs"]["presence"]["core"], places=4)
        for ds in self.world.merp[:1]:
            self.assertIn(f"{ds.key}/ref_s", held.files)

    def test_the_run_is_deterministic(self):
        again = check2b.run(self.world, self.dial, CFG, None, None, log=lambda s: None)
        strip = lambda r: json.dumps({k: v for k, v in r.items() if k not in ("seconds",)}, sort_keys=True, default=str)
        a = {k: v for k, v in self.results.items()}
        for side in (a, again):
            for key in ("round1",):
                side["B"].pop(key, None)
            for e in side["B"]["songs"].values():
                e.pop("round1Core", None), e.pop("round1Reference", None)
        self.assertEqual(strip(a), strip(again))


if __name__ == "__main__":
    unittest.main()
