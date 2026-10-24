"""End-to-end test of check1b.py on a tiny synthetic world and fake dial files (never real data).
Run: cd scripts/emotion && /secondary/hyst-env/emotion/bin/python -m unittest
"""
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import numpy as np

import check1b
import common
import lifts
import mind
from mind import Clip

CFG = check1b.Config(units=24, ear_k=6, state_k=8, rehearsal_k=3, sr_grid=(0.8, 0.95), n_boot=60, n_draws=60)
DIM = 10


def latent(steps, rng, sections=4):
    knots = rng.uniform(-0.8, 0.8, sections + 1)
    return np.interp(np.arange(steps), np.linspace(0, steps - 1, sections + 1), knots)


def synth_clip(key, ds, steps, rng, rows):
    a = latent(steps, rng)
    x = rng.normal(0, 0.4, (steps, DIM)).astype(np.float32)
    x[:, :3] += a[:, None]
    x[:, 3] += np.cumsum(a) / 10
    y = np.stack([-0.5 * a + rng.normal(0, 0.05, steps), a + rng.normal(0, 0.05, steps)], axis=1) if ds in ("deam", "merp") else None
    clip = Clip(key, ds, x, np.arange(0.1, steps * 0.5, 0.5), y, np.array(rows, dtype=int))
    clip.extra["latent"] = a
    return clip


def synthetic_world(seed=0):
    rng = np.random.default_rng(seed)
    deam = [synth_clip(f"deam_{i}", "deam", 50, rng, range(30, 50, 4)) for i in range(1, 16)]
    emotify = []
    for i in range(1, 11):
        c = synth_clip(f"emotify_{i}", "emotify", 40, rng, range(4, 40, 4))
        c.profile = rng.dirichlet(np.ones(9))
        emotify.append(c)
    merp = []
    for i in range(10):
        c = synth_clip(f"merp_s{i}", "merp", 140, rng, range(4, 140, 4))
        curve = np.interp(np.arange(700) / 10.0, [0, 15, 21, 40, 46, 70], [-0.6, -0.6, 0.0, 0.0, 0.6, 0.6])
        c.extra.update(duration=70.0, arousal10=curve, trials=3)
        merp.append(c)
    songs = []
    for key, *_ in check1b.SONGS:
        c = synth_clip(key, "song", 561, rng, [])
        c.extra.update(duration=280.0, title=key)
        songs.append(c)
    folds = common.assign_folds([c.key for c in deam])
    folds.update(common.assign_folds([c.key for c in emotify]))
    folds.update(common.assign_folds([c.key for c in merp]))
    return check1b.World(deam, emotify, merp, songs, folds, {"labelVariant": ["none", "before"]})


def write_dial(directory):
    directory = pathlib.Path(directory)
    curve = lambda: [[k / 10, float(v)] for k, v in enumerate(np.interp(np.arange(2800) / 10.0, [0, 30, 36, 90, 96, 280], [0.1, 0.1, 0.6, 0.6, 0.9, 0.9]))]
    takes = []
    for song in ("song1.m4a", "song2.m4a", "song3.m4a"):
        takes.append({"pass": "A", "song": song, "status": "done", "samples": curve(), "taps": [], "events": []})
        takes.append({"pass": "B", "song": song, "status": "done", "taps": [], "events": [],
                      "samples": [[k / 10, 0.5 + 0.3 * np.sin(k / 37), 0.4 + 0.2 * np.cos(k / 53)] for k in range(2800)]})
    takes.append({"pass": "A", "song": "song2.m4a", "status": "discarded", "samples": [[0.0, 0.99]], "taps": [], "events": []})
    (directory / "dial2.json").write_text(json.dumps({"format": "hyst-emotion-dial", "version": 2, "rate": 10, "takes": takes}))
    arousal = np.interp(np.arange(3290) / 10.0, [0, 40, 50, 329], [-0.8, -0.8, 0.4, 0.4])
    (directory / "dial-ic-try1.json").write_text(json.dumps({"format": "hyst-emotion-dial", "version": 1, "songs": [
        {"file": "song1.m4a", "title": "Instant Crush", "samples": [[k / 10, 0.0, float(a)] for k, a in enumerate(arousal)]},
        {"file": "song2.m4a", "title": "Five Years", "samples": []}]}))


class DialTests(unittest.TestCase):
    def test_reads_the_two_formats(self):
        with tempfile.TemporaryDirectory() as d:
            write_dial(d)
            dial = check1b.load_dial(pathlib.Path(d) / "dial2.json", pathlib.Path(d) / "dial-ic-try1.json")
        self.assertAlmostEqual(dial["five-years"]["energy10"][0], 0.1)
        self.assertEqual(len(dial["five-years"]["energy10"]), 2800)       # the discarded take is not read
        self.assertEqual(dial["presence"]["masks"], [])
        ic = dial["instant-crush"]
        self.assertAlmostEqual(ic["energy10"][0], (-0.8 + 1) / 2)          # try 1, not dial2's pass A
        self.assertEqual(len(ic["energy10"]), 3290)
        self.assertEqual(ic["masks"], [(135.0, 171.0), (329.0, 1e9)])
        self.assertIn("light10", dial["presence"])

    def test_steps_touching_a_mask_or_past_the_end_are_left_out(self):
        steps = check1b._dial_steps(np.full(200, 0.5), 60, [(5.0, 7.0)])
        self.assertTrue(np.isnan(steps[10]) and np.isnan(steps[14]))       # 4.75-5.25 and 6.75-7.25 touch
        self.assertTrue(np.isnan(steps[9]) == False)                       # 4.25-4.75 does not
        self.assertEqual(steps[20], 0.5)
        self.assertTrue(np.isnan(steps[45]))                               # recording ends at 20 s


class LibraryTests(unittest.TestCase):
    def test_library_vectors_have_the_stage_one_layout(self):
        with tempfile.TemporaryDirectory() as d:
            emb = pathlib.Path(d) / "emb"
            for name, shape in (("baseline_stems", (9, 49)), ("mert", (9, 13, 768)), ("essentia_effnet", (9, 1280)), ("essentia_mood", (9, 56))):
                (emb / name).mkdir(parents=True)
                np.save(emb / name / "k.npy", np.ones(shape, np.float16))
            (emb / "clap").mkdir()
            np.save(emb / "clap" / "k.npy", np.array([np.full(512, 1.0), np.full(512, 3.0)], np.float16))
            (emb / "clap" / "manifest.json").write_text(json.dumps({"centre0": 2.0, "hopSeconds": 2.0}))
            with mock.patch.object(common, "CACHE", pathlib.Path(d)):
                x = check1b.library_vectors("k")
        self.assertEqual(x.shape, (9, 2665))
        clap = x[:, 49 + 768:49 + 768 + 512]
        np.testing.assert_allclose(clap[:, 0], [1, 1, 1, 1, 1, 1.5, 2, 2.5, 3])   # held, then linear between 2 s and 4 s


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = synthetic_world()
        cls.dir = tempfile.TemporaryDirectory()
        write_dial(cls.dir.name)
        dial_args = (pathlib.Path(cls.dir.name) / "dial2.json", pathlib.Path(cls.dir.name) / "dial-ic-try1.json")
        cls.dial = check1b.load_dial(*dial_args)
        cls.out = pathlib.Path(cls.dir.name) / "out"
        cls.lines = []
        cls.results = check1b.run(cls.world, cls.dial, CFG, cls.out, log=cls.lines.append)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_every_gate_is_computed_and_reported(self):
        r = self.results
        for gate in ("gate1", "gate2", "gate3", "gate4", "gate5"):
            self.assertIsInstance(r[gate]["pass"], bool)
        self.assertIsInstance(r["pass"], bool)
        self.assertEqual(r["pass"], all(r[g]["pass"] for g in ("gate1", "gate2", "gate3", "gate4", "gate5")))
        self.assertEqual(r["gate1"]["deam"]["songs"], 15)
        self.assertEqual(r["gate1"]["merp"]["songs"], 10)
        lo, hi = r["gate1"]["merp"]["core"][1]
        self.assertTrue(lo <= r["gate1"]["merp"]["core"][0] <= hi)
        self.assertEqual(set(r["gate5"]["songs"]), {"instant-crush", "five-years", "presence"})
        self.assertIn("passB", r["gate5"]["songs"]["presence"])
        self.assertEqual(r["gate5"]["songs"]["instant-crush"]["source"], "dial-ic-try1.json arousal, (a + 1) / 2")
        self.assertEqual(set(r["radii"]), {"0", "1", "2", "3", "4", "all"})
        for f in range(5):
            self.assertIn(r["radii"][str(f)]["chosen"], CFG.sr_grid)

    def test_gate_2_uses_its_own_deam_only_readout(self):
        world = synthetic_world()
        train = [c for c in world.deam + world.emotify + world.merp if world.folds[c.key] != 0]
        model, readouts, _, _ = check1b.fit_model(train, CFG)
        test = [c for c in world.deam if world.folds[c.key] == 0]
        out = check1b.evaluate(model, readouts, test)
        deam_train = [c for c in train if c.ds == "deam"]
        x, y, g = check1b.pooled_rows(deam_train, None, None)
        expected = check1b.Ridge(x, y, g)(test[0].x[test[0].rows])
        np.testing.assert_allclose(out[test[0].key]["ref_deam"], expected)           # fitted on DEAM rows only
        self.assertFalse(np.allclose(out[test[0].key]["ref_deam"], out[test[0].key]["ref"]))   # not the pooled fit
        self.assertFalse(np.allclose(out[test[0].key]["core_deam"], out[test[0].key]["core"]))

    def test_the_core_tracks_the_synthetic_signal(self):
        # the signal is a function of the input: the reference must read it, and the core must not be at chance
        self.assertGreater(self.results["gate1"]["deam"]["reference"][0], 0.5)
        self.assertGreater(self.results["gate1"]["deam"]["core"][0], 0.2)

    def test_lifts_come_from_the_curves_and_the_p_value_is_a_permutation_p(self):
        g4 = self.results["gate4"]
        self.assertEqual(sum(g4["merp"]["lifts"].values()), 20)             # two clean rises per MERP curve
        self.assertEqual(g4["merp"]["windows"], 20)
        self.assertGreaterEqual(g4["merp"]["p"], 1 / (CFG.n_draws + 1))
        self.assertLessEqual(g4["merp"]["p"], 1.0)
        self.assertEqual(g4["songs"]["lifts"]["instant-crush"], 1)          # try 1 rise at 40-50 s -> lift near 38.5 s
        lifts_found = json.loads((self.out / "lifts.json").read_text())
        self.assertAlmostEqual(lifts_found["instant-crush"][0], 40 - 1.5 - 0.5, delta=1.5)
        self.assertEqual(len(lifts_found["five-years"]), 2)                 # rises at 30-36 s and 90-96 s

    def test_the_run_is_deterministic_and_writes_its_files(self):
        again = check1b.run(self.world, self.dial, CFG, None, log=lambda s: None)
        strip = lambda r: {k: v for k, v in r.items() if k != "seconds"}
        self.assertEqual(json.dumps(strip(self.results), sort_keys=True), json.dumps(strip(again), sort_keys=True))
        for name in ("results.json", "folds.json", "lifts.json"):
            self.assertTrue((self.out / name).exists())

    def test_report_prints_pass_or_fail_per_gate_and_overall(self):
        lines = []
        check1b.report(self.results, lines.append)
        text = "\n".join(lines)
        for tag in ("GATE 1:", "GATE 2:", "GATE 3:", "GATE 4:", "GATE 5:", "OVERALL:"):
            self.assertIn(tag, text)

    def test_the_test_fold_never_reaches_the_fit(self):
        # wreck the labels of the held-out fold 0: its radius and inner scores must not move
        world = synthetic_world()
        for c in world.deam + world.merp:
            if world.folds[c.key] == 0:
                c.y[:] = np.random.default_rng(9).normal(size=c.y.shape)
        wrecked = check1b.run(world, self.dial, CFG, None, log=lambda s: None)
        self.assertEqual(wrecked["radii"]["0"], self.results["radii"]["0"])
        self.assertNotEqual(wrecked["radii"]["1"]["innerScores"], self.results["radii"]["1"]["innerScores"])
        self.assertNotEqual(wrecked["gate1"]["deam"]["core"], self.results["gate1"]["deam"]["core"])

def pred_with_r(y, r):
    """A vector whose Pearson r with y is r (y centred, plus an orthogonal part)."""
    y = y - y.mean()
    u = np.cos(np.arange(len(y)) * 1.7)
    u = u - u.mean()
    u = u - (u @ y) / (y @ y) * y
    return r * y / np.linalg.norm(y) + np.sqrt(1 - r * r) * u / np.linalg.norm(u)


def gate_world(n=12, steps=40):
    rng = np.random.default_rng(5)
    def clips(ds):
        out = []
        for i in range(n):
            y = np.zeros((steps, 2))
            y[:, 1] = np.linspace(0, 1, steps) ** 2 + rng.normal(0, 0.01, steps)
            y[:, 0] = np.linspace(0, 1, steps) ** 3 + rng.normal(0, 0.01, steps)
            out.append(Clip(f"{ds}_{i}", ds, np.zeros((steps, 3), np.float32), np.arange(0, 100, 0.5), y, np.arange(4, steps, 2)))
        return out
    return check1b.World(clips("deam"), [], clips("merp"), [], {}), 


class GateTests(unittest.TestCase):
    cfg = check1b.Config(n_boot=300, n_draws=100)

    def collected(self, world, core_r, ref_r, core0_r=None):
        out = {}
        for k, c in enumerate(world.deam + world.merp):
            truth = c.y[c.rows, 1]
            mk = lambda r: np.stack([truth * 0, pred_with_r(truth, r[k % len(r)])], axis=1)
            out[c.key] = {"core": mk(core_r), "ref": mk(ref_r), "core0": mk(core0_r or core_r)}
        return out

    def test_gate1_needs_non_overlapping_intervals_not_just_a_better_mean(self):
        world = gate_world()[0]
        clear = check1b.gate1(self.collected(world, [0.9], [0.1]), world, self.cfg)
        self.assertTrue(clear["pass"])
        wide = check1b.gate1(self.collected(world, [1.0, -0.2], [0.2]), world, self.cfg)   # mean 0.4 against 0.2, intervals touch
        self.assertGreater(wide["deam"]["core"][0], wide["deam"]["reference"][1][1])
        self.assertFalse(wide["deam"]["pass"])
        self.assertFalse(check1b.gate1(self.collected(world, [0.1], [0.9]), world, self.cfg)["pass"])

    def test_gate3_wants_the_arousal_r_at_least_halved(self):
        world = gate_world()[0]
        shuffled = lambda r: {k: v["core"] for k, v in self.collected(world, [r], [0.1]).items()}
        collected = self.collected(world, [0.8], [0.1])
        self.assertTrue(check1b.gate3(collected, shuffled(0.3), world, self.cfg)["pass"])
        self.assertFalse(check1b.gate3(collected, shuffled(0.5), world, self.cfg)["pass"])
        self.assertFalse(check1b.gate3(self.collected(world, [-0.2], [0.1]), shuffled(-0.4), world, self.cfg)["pass"])

    def test_gate4_p_is_one_plus_count_over_one_plus_draws(self):
        beats = np.arange(0, 100, 0.5)
        dist = np.zeros(200)
        lift_times = [30.0, 70.0]
        for t in lift_times:
            dist[int((t - 4) / 0.5):int(t / 0.5)] = 5.0          # 8 beats of 0.5 s before each lift
        result = check1b.gate4([("s", dist, beats, lift_times)], self.cfg)
        self.assertEqual(result["windows"], 2)
        self.assertEqual(result["p"], 1 / (self.cfg.n_draws + 1))   # nothing in the null reaches 5
        self.assertTrue(result["pass"])
        flat = check1b.gate4([("s", np.ones(200), beats, lift_times)], self.cfg)
        self.assertEqual(flat["p"], 1.0)                             # every draw ties the statistic
        self.assertFalse(flat["pass"])
        self.assertFalse(check1b.gate4([("s", dist, beats, [])], self.cfg)["pass"])

    def test_gate4_null_windows_never_overlap_a_lift_window(self):
        beats = np.arange(0, 100, 0.5)
        dist = np.zeros(200)
        dist[int(26 / 0.5):int(34 / 0.5)] = 9.0                      # a big block: the lift window is [26, 30), the next 4 s are free
        result = check1b.gate4([("s", dist, beats, [30.0])], self.cfg)
        self.assertLess(result["nullInterval"][1], 9.0)               # no null window picked the lift window itself

    def test_gate5_presence_needs_sadness_in_the_top_three_and_above_the_rest(self):
        world = check1b.World([], [], [], [Clip(k, "song", np.zeros((561, 3), np.float32), np.arange(0, 280, 0.5)) for k, *_ in check1b.SONGS], {})
        names = list(common.GEMS)
        def song_out(sadness_rank_value, rest=0.1):
            gems = np.full((561, 9), 0.3)
            gems[:, names.index("sadness")] = rest
            gems[240:380, names.index("sadness")] = sadness_rank_value
            return {k: {"va_core": np.zeros((561, 2)), "va_ref": np.zeros((561, 2)), "gems_core": gems} for k, *_ in check1b.SONGS}
        dial = {k: {"masks": [], "source": {}} for k, *_ in check1b.SONGS}
        self.assertTrue(check1b.gate5(song_out(0.9), dial, world)["presence"]["pass"])     # highest of nine
        self.assertFalse(check1b.gate5(song_out(0.2), dial, world)["presence"]["pass"])    # last of nine
        three = song_out(0.35)                                                             # second-highest except 8 others at 0.3: rank 1
        self.assertEqual(check1b.gate5(three, dial, world)["presence"]["sadnessRank"], 1)
        fourth = song_out(0.3)
        for k in fourth:
            fourth[k]["gems_core"][:, [0, 1, 2]] = 0.5
        self.assertFalse(check1b.gate5(fourth, dial, world)["presence"]["pass"])           # rank 4 of nine

    def test_gate4_threshold_is_five_percent(self):
        beats = np.arange(0, 100, 0.5)
        dist = np.arange(200, dtype=float)                           # a ramp: later windows are higher
        result = check1b.gate4([("s", dist, beats, [75.0])], self.cfg)
        self.assertGreater(result["p"], 0.1)                         # about a quarter of the free windows are higher
        self.assertLess(result["p"], 0.4)
        self.assertFalse(result["pass"])

    def test_gate2_compares_the_point_value_with_stage_ones_lower_bound(self):
        rng = np.random.default_rng(2)
        deam = []
        for i in range(10):
            y = np.stack([np.sin(np.arange(40) / 3 + i), np.cos(np.arange(40) / 4 + i)], axis=1)
            deam.append(Clip(f"deam_{i}", "deam", np.zeros((40, 2), np.float32), np.arange(0, 100, 0.5), y, np.arange(0, 40, 2)))
        emotify = []
        for i in range(10):
            profile = rng.dirichlet(np.ones(9))
            emotify.append(Clip(f"emotify_{i}", "emotify", np.zeros((40, 2), np.float32), np.arange(0, 100, 0.5), None, np.arange(4, 40, 4), profile))
        world = check1b.World(deam, emotify, [], [], {})
        def collected(r2, good):
            shrink = 1 - np.sqrt(1 - r2)
            out = {c.key: {"core_deam": shrink * c.y[c.rows], "ref_deam": shrink * c.y[c.rows],
                           "core": 0 * c.y[c.rows], "ref": 0 * c.y[c.rows]} for c in deam}   # pooled-readout predictions are useless
            out.update({c.key: {"core": c.profile if good else -c.profile, "ref": c.profile} for c in emotify})
            return out
        cfg = check1b.Config(n_boot=50)
        inside = check1b.gate2(collected(0.60, True), world, cfg)       # below stage 1's point value, above its lower bound
        self.assertAlmostEqual(inside["timing"]["value"], 0.60, delta=0.02)
        self.assertTrue(inside["timing"]["pass"] and inside["rho"]["pass"] and inside["pass"])
        self.assertFalse(check1b.gate2(collected(0.57, True), world, cfg)["timing"]["pass"])
        self.assertFalse(check1b.gate2(collected(0.60, False), world, cfg)["rho"]["pass"])
        # gate 2 reads the DEAM-only predictions, not the pooled ones: with the pooled ones useless it still passes
        self.assertTrue(inside["pass"])
        swapped = collected(0.60, True)
        for c in deam:
            swapped[c.key]["core_deam"], swapped[c.key]["core"] = swapped[c.key]["core"], swapped[c.key]["core_deam"]
        self.assertFalse(check1b.gate2(swapped, world, cfg)["timing"]["pass"])

    def test_gate5_dial_and_five_years_rules(self):
        names = [k for k, *_ in check1b.SONGS]
        world = check1b.World([], [], [], [Clip(k, "song", np.zeros((561, 3), np.float32), np.arange(0, 280, 0.5)) for k in names], {})
        rng = np.random.default_rng(4)
        curve = np.interp(np.arange(2800) / 10.0, [0, 60, 120, 200, 280], [0.1, 0.8, 0.2, 0.9, 0.3])
        dial = {k: {"masks": [], "source": {}, "energy10": curve} for k in names}
        follow = check1b._dial_steps(curve, 561, [])
        def song_out(winners, ramp=None):
            out = {}
            for k in names:
                core = follow if k in winners else rng.normal(size=561)
                ref = rng.normal(size=561) if k in winners else follow
                out[k] = {"va_core": np.stack([core * 0, core], axis=1), "va_ref": np.stack([ref, ref], axis=1),
                          "gems_core": np.full((561, 9), 0.1)}
            if ramp is not None:
                out["five-years"]["va_core"][:, 1] = ramp
            return out
        two = check1b.gate5(song_out(["instant-crush", "presence"]), dial, world)
        self.assertEqual(two["dial"]["wins"], 2)
        self.assertTrue(two["dial"]["pass"])
        one = check1b.gate5(song_out(["instant-crush"]), dial, world)
        self.assertEqual(one["dial"]["wins"], 1)
        self.assertFalse(one["dial"]["pass"])
        rising = np.linspace(-1, 1, 561)
        self.assertTrue(check1b.gate5(song_out([], rising), dial, world)["fiveYears"]["pass"])      # opening below the climax
        self.assertFalse(check1b.gate5(song_out([], -rising), dial, world)["fiveYears"]["pass"])

    def test_rule_constants_are_those_of_the_notes(self):
        self.assertEqual((check1b.FIVE_YEARS_OPENING, check1b.FIVE_YEARS_CLIMAX), ((0.0, 30.0), (156.0, 258.0)))
        self.assertEqual(check1b.PRESENCE_SPAN, (120.0, 190.0))
        self.assertEqual(check1b.INSTANT_CRUSH_MASKS, [(135.0, 171.0), (329.0, 1e9)])
        self.assertEqual((check1b.N_DRAWS, check1b.LIFT_WINDOW_BEATS), (1000, 8))
        self.assertEqual(check1b.STAGE1_PICK, {"timing": (0.617, 0.596, 0.635), "rho": (0.616, 0.588, 0.643)})
        self.assertEqual((common.N_FOLDS, common.N_BOOT), (5, 2000))


if __name__ == "__main__":
    unittest.main()
