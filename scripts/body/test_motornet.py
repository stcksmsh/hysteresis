"""Tests for the WO29B tool: session (round-2 manifest), measurement and report.  One module per process: python3 -I -m unittest test_motornet
(the measurement tests need numpy+scipy: /secondary/hyst-env/body/bin/python -I -m unittest test_motornet)."""
import csv, json, sys, tempfile, threading, unittest, urllib.error, urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dialstudy_session as ses
import motornet_measure as mm
import motornet_report as rep

SONGS = ["Epitaph", "Schizoid", "Days", "Breathe", "Lagoon"]


def fake(root, r1dir, with_pairs=True):
    clips = []
    for i in range(1, 13):
        f = f"S{i:02d}.mp4"; (root / f).write_bytes(b"x%d" % i * 40)
        clips.append(dict(id=f"P1_S{i:02d}", part=1, file=f, setting=f"S{i:02d}", effector="lamp", setting_values=[0.5] * 4))
    for i in (1, 2):
        f = f"B{i}.mp4"; (root / f).write_bytes(b"b%d" % i * 40)
        clips.append(dict(id=f"P2_S{i:02d}", part=2, file=f, setting=f"S{i:02d}", effector="ball"))
    for i in range(4):
        f = r1dir / f"old{i}.mp4"; f.write_bytes(b"o%d" % i * 40)
        clips.append(dict(id=f"P4_{i}", part=4, file=str(f), round1_id=f"A_old{i}", effector="ball"))
    if with_pairs:
        for i, s in enumerate(SONGS):
            for n in "ab":
                (root / f"m{i}{n}.mp4").write_bytes(b"m%d%s" % (i, n.encode()) * 40)
            clips.append(dict(id=f"P3_{s}", part=3, files=[f"m{i}a.mp4", f"m{i}b.mp4"], setting=[f"S0{i + 1}", f"S1{i}"], song=s))
    (root / "manifest.json").write_text(json.dumps({"clips": clips}))
    return root / "manifest.json"


def get(url, headers=None):
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}))


def post(url, body):
    return urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"}))


class Session(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        (self.root / "r1").mkdir()
        self.manifest = fake(self.root, self.root / "r1")

    def tearDown(self):
        self.tmp.cleanup()

    def serve(self, out):
        srv = ses.make_server(out, 0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}"

    def test_seeded_order_and_key(self):
        a, b, c = self.root / "a", self.root / "b", self.root / "c"
        for o, sd in ((a, 5), (b, 5), (c, 6)):
            ses.build(self.manifest, o, seed=sd)
        self.assertEqual((a / "order.json").read_text(), (b / "order.json").read_text())
        self.assertNotEqual((a / "order.json").read_text(), (c / "order.json").read_text())
        k = json.loads((a / "key/key.json").read_text())
        self.assertEqual(k["seed"], 5)
        self.assertEqual(len(json.loads((a / "order.json").read_text())), 12 + 2 + 4 + 5)
        parts = sorted(v["part"] for v in k["key"].values())
        self.assertEqual((parts.count(1), parts.count(2), parts.count(3), parts.count(4)), (12, 2, 5, 4))
        one = next(v for v in k["key"].values() if v["part"] == 4)
        self.assertTrue(one["round1_id"].startswith("A_old"))
        pair = next(v for v in k["key"].values() if v["part"] == 3)
        self.assertEqual(sorted([pair["first_setting"], pair["second_setting"]]), sorted(pair["setting"]))

    def test_key_and_answers_404_page_offline(self):
        out = self.root / "s"; ses.build(self.manifest, out, seed=1)
        base = self.serve(out)
        for path in ("/key/key.json", "/answers.csv", "/order.json", "/labels.json", "/manifest.json"):
            with self.assertRaises(urllib.error.HTTPError, msg=path) as e:
                get(base + path)
            self.assertEqual(e.exception.code, 404)
        page = get(base + "/").read().decode()
        self.assertNotIn("http", page)

    def test_labels_new_for_round2_old_for_round1(self):
        out = self.root / "s"; ses.build(self.manifest, out, seed=1)
        st = json.loads(get(self.serve(out) + "/api/state").read())
        self.assertEqual(st["labels"], ses.LABELS2)
        self.assertIn("sad", st["labels"]); self.assertNotIn("angry", st["labels"])
        old = self.root / "old"; (old / "x").mkdir(parents=True)
        (old / "x/a.mp4").write_bytes(b"a" * 40)
        (old / "m.json").write_text(json.dumps({"clips": [dict(id="A1", set="A", file="x/a.mp4")]}))
        o = self.root / "so"; ses.build(old / "m.json", o, seed=1)
        self.assertEqual(json.loads(get(self.serve(o) + "/api/state").read())["labels"], ses.LABELS)

    def test_part4_codes_fresh_and_nothing_old_in_page_or_state(self):
        out = self.root / "s"; ses.build(self.manifest, out, seed=2)
        names = {p.name for p in (out / "clips").iterdir()}
        self.assertEqual(len(names), 12 + 2 + 4 + 10)
        for n in names:
            self.assertRegex(n, r"^c[0-9a-f]{4}\.mp4$")
        base = self.serve(out)
        txt = get(base + "/api/state").read().decode() + get(base + "/").read().decode() + (out / "order.json").read_text()
        for w in ("A_old", "round1", "round 1", "r1/", "lamp", "ball", "S01"):
            self.assertNotIn(w, txt)

    def test_answers_resume_and_pair_labels(self):
        out = self.root / "s"; ses.build(self.manifest, out, seed=1)
        base = self.serve(out)
        order = json.loads((out / "order.json").read_text())
        single = next(i for i in order if i["kind"] == "single"); pair = next(i for i in order if i["kind"] == "pair")
        self.assertEqual(post(base + "/api/answer", {"code": single["code"], "answer": "sad", "note": "n"}).status, 200)
        for bad in ({"code": single["code"], "answer": "first"}, {"code": pair["code"], "answer": "sad"}):
            with self.assertRaises(urllib.error.HTTPError):
                post(base + "/api/answer", bad)
        self.assertEqual(post(base + "/api/answer", {"code": pair["code"], "answer": "first"}).status, 200)
        st = json.loads(get(self.serve(out) + "/api/state").read())
        self.assertEqual((st["total"], st["done"]), (len(order), 2))


class Measure(unittest.TestCase):
    T = np.arange(600) / 50.0

    def test_pr_k_equal_components(self):
        rng = np.random.default_rng(0)
        for k in (1, 3, 8):
            x = np.zeros((20000, 20)); x[:, :k] = rng.standard_normal((20000, k))
            self.assertAlmostEqual(mm.participation_ratio(x), k, delta=0.15 * k)

    def test_regimes(self):
        w = np.random.default_rng(1).standard_normal(5)
        u = np.outer(np.sin(2 * np.pi * 1.0 * self.T), w)
        self.assertEqual(mm.regime(u), "cycles")
        d = np.outer(np.exp(-self.T / 0.8) * np.sin(2 * np.pi * 1.0 * self.T), w)
        self.assertEqual(mm.regime(d), "decays")
        walk = np.cumsum(np.random.default_rng(2).standard_normal((600, 5)), 0)
        self.assertEqual(mm.regime(walk), "wanders")

    def test_frequency_straightness_speed_height(self):
        f = 1.5
        h = np.stack([0.2 * np.sin(2 * np.pi * f * self.T), 0 * self.T, 0.3 + 0 * self.T], 1)
        self.assertAlmostEqual(mm.dominant_freq(h), f, delta=0.1)
        h8 = np.stack([0.1 * np.sin(2 * np.pi * 0.8 * self.T), 0 * self.T, 0 * self.T], 1)
        self.assertAlmostEqual(mm.dominant_freq(h8), 0.8, delta=0.1)
        self.assertAlmostEqual(mm.hand_speed(h).mean(), 0.2 * 2 * np.pi * f * 2 / np.pi, delta=0.02)
        self.assertAlmostEqual(mm.straightness(h)[0], 1.0, places=3)
        self.assertAlmostEqual(float(h[:, 2].mean()), 0.3)
        th = np.pi * (0.5 - 0.5 * np.cos(2 * np.pi * 0.5 * self.T))  # back and forth along a semicircle: chord/arc = 2/pi
        c = 0.2 * np.stack([np.cos(th), np.sin(th), 0 * th], 1)
        self.assertAlmostEqual(mm.straightness(c)[0], 2 / np.pi, delta=0.05)

    def test_cli_on_fake_manifest(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            q = np.tile([0.0, 20, 30, 0, 0], (600, 1)) + np.outer(np.sin(self.T * 6), [10, 10, 10, 0, 0])
            hdr = "# c\n" * 7 + "time_s,a,b,c,d,e\n"
            (d / "S01.csv").write_text(hdr + "".join(f"{i / 50:.4f}," + ",".join(map(str, row)) + "\n" for i, row in enumerate(q)))
            np.save(d / "S01.npy", np.random.default_rng(0).standard_normal((600, 30)).astype("float32"))
            (d / "m.json").write_text(json.dumps({"clips": [dict(part=1, setting="S01", csv="S01.csv", activity="S01.npy"), dict(part=2, setting="S01")]}))
            r = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve().parent / "motornet_measure.py"), "--manifest", str(d / "m.json"), "--out", str(d / "o.json")],
                               capture_output=True, text=True, env={"PYTHONPATH": str(Path(__file__).resolve().parent)})
            self.assertEqual(r.returncode, 0, r.stderr)
            m = json.loads((d / "o.json").read_text())["S01"]
            self.assertEqual(sorted(m), sorted(["pr", "regime", "freq_hz", "hand_speed", "hand_height", "straightness", "straightness_min"]))


class Report(unittest.TestCase):
    def test_fake_session(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); (d / "r1").mkdir()
            man = fake(d, d / "r1")
            out = d / "session"; ses.build(man, out, seed=4)
            key = json.loads((out / "key/key.json").read_text())["key"]
            code = {}
            for c, k in key.items():
                code[(k["part"], k["id"])] = c
            r1 = d / "round1"; (r1 / "key").mkdir(parents=True)
            (r1 / "key/key.json").write_text(json.dumps({"key": {"cz": {"id": "A_old0"}}}))
            (r1 / "answers.csv").write_text("cz,heavy,,t,0\n")
            with open(out / "answers.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow([code[(1, "P1_S01")], "calm", "slow|ish", "t", 0]); w.writerow([code[(2, "P2_S01")], "tense", "", "t", 0])
                w.writerow([code[(4, "P4_0")], "sad", "", "t", 0])
                pk = key[code[(3, "P3_Epitaph")]]
                w.writerow([code[(3, "P3_Epitaph")], "second", "", "t", 1])
            meas = d / "m.json"
            meas.write_text(json.dumps({"S01": dict(pr=3.14159, regime="cycles", freq_hz=1.5, hand_speed=0.2, hand_height=0.3, straightness=0.9)}))
            text = rep.report(out, meas, r1)
            self.assertIn("| S01 | ", text)
            self.assertIn("calm", text); self.assertIn("cycles", text); self.assertIn("3.14", text); self.assertIn("slow/ish", text)
            self.assertIn("| S01 | calm |", text); self.assertIn("tense", text)
            self.assertIn(f"| Epitaph | ", text)
            self.assertIn(pk["second_setting"], text)
            self.assertIn("| A_old0 | heavy | sad |", text)
            self.assertIn("MOTORNET_PARAMS.md", text)
            self.assertIn("(not answered)", text)
            for w in ("worth building", "viable", "score ", "correct", "pass"):
                self.assertNotIn(w, text.replace("No verdict and no score", ""))


if __name__ == "__main__":
    unittest.main()
