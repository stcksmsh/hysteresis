"""Tests for the round-2 session, measurement and report (WO30A).  python test_motornet2.py"""
import csv, json, subprocess, sys, tempfile, threading, unittest, urllib.error, urllib.request
from pathlib import Path

import numpy as np

import dialstudy_session as ses
import motornet_measure as mm
import motornet_report as rep

SONGS = ["blue-lagoon", "schizoid-man", "epitaph", "breathe", "one-of-these-days"]
HZ, T = 50, 1501


def clip_files(root, name, yaw_slope=0.0):
    t = np.arange(T) / HZ
    q = np.zeros((T, 5)); q[:, 0] = 10 * np.sin(2 * t) + yaw_slope * t; q[:, 1] = -60 + 5 * np.cos(t)
    (root / f"{name}.csv").write_text("# c\ntime_s,a,b,c,d,e\n" + "\n".join(f"{x:.2f}," + ",".join(f"{v:.3f}" for v in r) for x, r in zip(t, q)) + "\n")
    rr = np.random.default_rng(len(name)).standard_normal((T, 200)).astype(np.float32)
    rr[:, :100] = rr[:, :1] + 0.1 * rr[:, :100]  # slow population: nearly one component
    np.save(root / f"{name}.activity.npy", rr)
    (root / f"{name}.mp4").write_bytes(name.encode() * 40)


def fake(root):
    items = []
    for i in range(1, 9):
        n = f"A_S{i:02d}"; clip_files(root, n)
        items.append(dict(id=n, part="A", file=f"{n}.mp4", csv=f"{n}.csv", activity=f"{n}.activity.npy", setting=f"S{i:02d}", population=[0] * 100 + [1] * 100))
    for i, s in enumerate(SONGS):
        for x in "ab":
            clip_files(root, f"B_{i}{x}", yaw_slope=3.0 * (x == "b"))
        items.append(dict(id=f"B_{s}", part="B", files=[f"B_{i}a.mp4", f"B_{i}b.mp4"], csv=[f"B_{i}a.csv", f"B_{i}b.csv"],
                          activity=[f"B_{i}a.activity.npy", f"B_{i}b.activity.npy"], setting=[f"S0{i + 1}", "R1S03"], song=s, excerpt_start_s=10.0 * i,
                          ear_energy=0.5 + i, arousal_raw=0.1 * i, arousal_std=-1.0 + i))
    (root / "manifest.json").write_text(json.dumps({"clips": items}))
    return root / "manifest.json"


class Tool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.manifest = fake(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_session_parts_pairs_key_404_loopback(self):
        out = self.root / "s"; ses.build(self.manifest, out, seed=5)
        order = json.loads((out / "order.json").read_text())
        self.assertEqual(sorted(i["kind"] for i in order).count("pair"), 5); self.assertEqual(len(order), 13)
        self.assertEqual(json.loads((out / "labels.json").read_text()), ses.LABELS2)
        srv = ses.make_server(out, 0)
        threading.Thread(target=srv.serve_forever, daemon=True).start(); self.addCleanup(srv.shutdown)
        self.assertEqual(srv.server_address[0], "127.0.0.1")
        for path in ("/key/key.json", "/order.json"):
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}{path}")
            self.assertEqual(e.exception.code, 404)
        out2 = self.root / "s2"; ses.build(self.manifest, out2, seed=5)
        self.assertEqual((out / "order.json").read_text(), (out2 / "order.json").read_text())
        pa = self.root / "pa"; ses.build(self.manifest, pa, seed=5, parts={"A"})
        self.assertEqual(len(json.loads((pa / "order.json").read_text())), 8)

    def test_measure2(self):
        r = np.random.default_rng(1).standard_normal((T, 200))
        q = np.zeros((T, 5)); q[:, 0] = np.linspace(0, 30, T); q[:, 1] = np.where(np.arange(T) % 2, 4, -4)
        m = mm.measure2(r, np.cumsum(np.ones((T, 3)) * 0.001, 0), q, [0] * 100 + [1] * 100)
        self.assertAlmostEqual(m["yaw_range"], 27.0, delta=0.1)   # p5-p95 of a ramp over 30 deg
        self.assertAlmostEqual(m["shoulder_range"], 8.0, delta=0.01)
        self.assertAlmostEqual(m["drift"], 30 * (1 - 3 / 30) - 0, delta=0.5 + 3)  # last 3 s minus first 3 s of the ramp
        self.assertGreater(m["drift_range"], 20)
        self.assertGreater(m["pr_slow"], 50); self.assertGreater(m["pr_fast"], 50)
        # one-component population -> PR near 1
        r2 = r.copy(); r2[:, :100] = r2[:, :1]
        self.assertLess(mm.measure2(r2, np.zeros((T, 3)) + np.arange(T)[:, None] * 1e-3, q, [0] * 100 + [1] * 100)["pr_slow"], 1.5)

    def test_cli_and_report_synthetic(self):
        meas = self.root / "meas.json"
        subprocess.run([sys.executable, str(Path(mm.__file__)), "--manifest", str(self.manifest), "--out", str(meas), "--round2"], check=True, capture_output=True)
        m = json.loads(meas.read_text())
        self.assertEqual(len(m), 8 + 10); self.assertIn("pr_slow", m["A_S01"]); self.assertGreater(m["B_0b"]["drift"], m["B_0a"]["drift"])
        out = self.root / "s"; ses.build(self.manifest, out, seed=2)
        key = json.loads((out / "key/key.json").read_text())["key"]
        code = {(k["part"], k["id"]): c for c, k in key.items()}
        with open(out / "answers.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([code[("A", "A_S01")], "tense", "slow|ish", "t", 0]); w.writerow([code[("B", "B_epitaph")], "second", "n", "t", 0])
        (self.root / "settings.json").write_text(json.dumps({"settings": [dict(id="S01", values=[1.0, 2.0])],
                                                            "discards": [dict(draw=3, song="breathe", gates=["contact"]), dict(draw=5, song="silent", gates=["limits"])]}))
        text = rep.report2(out, meas, self.root / "settings.json")
        for h in ("## Part A: silent, 30 s", "## Part B: which render fits the music", "## Discards by gate", "## Network and body parameters"):
            self.assertEqual(text.count(h), 1, h)
        self.assertIn("| S01 | tense | slow/ish |", text)
        self.assertIn("(not answered)", text)
        k = key[code[("B", "B_epitaph")]]
        self.assertIn(f"| epitaph | first {k['first_setting']}, second {k['second_setting']} | second | {k['second_setting']} | n |", text)
        self.assertIn("2.5 | 0.2 | 1", text)  # ear energy, arousal raw, std of the epitaph pair (i = 2)
        self.assertIn("breathe", text); self.assertIn("contact", text); self.assertIn("MOTORNET2_RULES.md", text)
        for w in ("worth building", "viable", "correct", "pass"):
            self.assertNotIn(w, text)


if __name__ == "__main__":
    unittest.main()
