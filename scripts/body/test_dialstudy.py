"""Tests for dialstudy_session.py and dialstudy_report.py on a fake 5-clip manifest.  python3 -I -m unittest test_dialstudy"""
import csv, json, sys, tempfile, threading, unittest, urllib.error, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dialstudy_report as rep
import dialstudy_session as ses

CLIPS = [
    dict(id="A_vigour_low", set="A", file="a1.mp4", effector="ball", intent=dict(kind="dial", dial="vigour", level="low"), dials={}),
    dict(id="A_vigour_high", set="A", file="a2.mp4", effector="ball", intent=dict(kind="dial", dial="vigour", level="high"), dials={}),
    dict(id="A_neutral", set="A", file="a3.mp4", effector="ball", intent=dict(kind="neutral"), dials={}),
    dict(id="B_heavy", set="B", file="b1.mp4", effector="ball", intent=dict(kind="preset", preset="heavy"), dials={}),
    dict(id="C_heavy_lamp", set="C", file="c1.mp4", effector="lamp", intent=dict(kind="preset", preset="heavy"), dials={}),
]


def fake(root, with_d=False):
    clips = list(CLIPS)
    for c in clips:
        (root / c["file"]).write_bytes(c["id"].encode() * 50)
    if with_d:
        (root / "d1.mp4").write_bytes(b"d1" * 50); (root / "d2.mp4").write_bytes(b"d2" * 50)
        clips.append(dict(id="D_epitaph", set="D", files=["d1.mp4", "d2.mp4"], intent=dict(kind="preset", preset="heavy"), dials={}))
    (root / "manifest.json").write_text(json.dumps({"clips": clips}))
    return root / "manifest.json"


def get(url, headers=None):
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}))


def post(url, body):
    return urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"}))


class Tool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.manifest = fake(self.root, with_d=True)

    def tearDown(self):
        self.tmp.cleanup()

    def serve(self, out):
        srv = ses.make_server(out, 0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}"

    def test_order_seeded_and_stable(self):
        a, b, c = self.root / "a", self.root / "b", self.root / "c"
        ses.build(self.manifest, a, seed=7); ses.build(self.manifest, b, seed=7); ses.build(self.manifest, c, seed=8)
        ka = json.loads((a / "key/key.json").read_text()); kb = json.loads((b / "key/key.json").read_text())
        self.assertEqual(ka, kb)
        self.assertEqual(ka["seed"], 7)
        self.assertEqual((a / "order.json").read_text(), (b / "order.json").read_text())
        self.assertNotEqual((a / "order.json").read_text(), (c / "order.json").read_text())

    def test_key_never_served_and_page_is_offline(self):
        out = self.root / "s"; ses.build(self.manifest, out, seed=1)
        base = self.serve(out)
        for path in ("/key/key.json", "/key", "/order.json", "/answers.csv", "/clips/../key/key.json", "/clips/key.json"):
            with self.assertRaises(urllib.error.HTTPError, msg=path) as e:
                get(base + path)
            self.assertEqual(e.exception.code, 404, path)
        page = get(base + "/").read().decode()
        self.assertNotIn("http", page)
        state = get(base + "/api/state").read().decode()
        for name in ("A_vigour", "B_heavy", "lamp", "intent", "dials", "preset"):
            self.assertNotIn(name, state + page)

    def test_answers_written_and_resumed(self):
        out = self.root / "s"; ses.build(self.manifest, out, seed=1)
        base = self.serve(out)
        st = json.loads(get(base + "/api/state").read())
        self.assertEqual((st["total"], st["done"]), (6, 0))
        first = st["item"]
        self.assertEqual(post(base + "/api/answer", {"code": first["code"], "answer": "calm", "note": "x, y", "replays": 2}).status, 200)
        with self.assertRaises(urllib.error.HTTPError) as e:
            post(base + "/api/answer", {"code": first["code"], "answer": "calm"})
        self.assertEqual(e.exception.code, 409)
        with self.assertRaises(urllib.error.HTTPError) as e:
            post(base + "/api/answer", {"code": st["item"]["code"], "answer": "not a label"})
        self.assertEqual(e.exception.code, 400)
        rows = list(csv.reader(open(out / "answers.csv")))
        self.assertEqual(rows[0][:3] + [rows[0][4]], [first["code"], "calm", "x, y", "2"])
        # A fresh server on the same folder resumes at the first unanswered item.
        base2 = self.serve(out)
        st2 = json.loads(get(base2 + "/api/state").read())
        self.assertEqual(st2["done"], 1)
        self.assertNotEqual(st2["item"]["code"], first["code"])

    def test_pair_item_and_clip_ranges(self):
        out = self.root / "s"; ses.build(self.manifest, out, seed=3)
        base = self.serve(out)
        order = json.loads((out / "order.json").read_text())
        pair = next(i for i in order if i["kind"] == "pair")
        self.assertEqual(len(pair["clips"]), 2)
        self.assertEqual(post(base + "/api/answer", {"code": pair["code"], "answer": "neither"}).status, 200)
        with self.assertRaises(urllib.error.HTTPError):
            post(base + "/api/answer", {"code": next(i for i in order if i["kind"] == "single")["code"], "answer": "first"})
        r = get(f"{base}/clips/{pair['clips'][0]}.mp4", {"Range": "bytes=2-5"})
        self.assertEqual((r.status, len(r.read())), (206, 4))

    def test_report_has_tables_and_no_verdict(self):
        out = self.root / "s"; ses.build(self.manifest, out, seed=1)
        key = json.loads((out / "key/key.json").read_text())["key"]
        code = {k["id"]: c for c, k in key.items()}
        with open(out / "answers.csv", "w", newline="") as f:
            w = csv.writer(f)
            for cid, lab in [("A_vigour_low", "calm"), ("A_vigour_high", "angry"), ("A_neutral", "nothing, glitching"), ("B_heavy", "heavy"), ("C_heavy_lamp", "tense")]:
                w.writerow([code[cid], lab, "n|ote", "t", 0])
            w.writerow([code["D_epitaph"], "second", "", "t", 1])
        text = rep.report(out)
        self.assertIn("| A_vigour_low | A | vigour low | ball | calm |", text)
        self.assertRegex(text, r"\| vigour \| calm \| nothing, glitching \| angry \|")
        self.assertRegex(text, r"\| heavy \| heavy \| tense \| \(none\) \|")
        self.assertIn("Set D", text)
        self.assertIn("DIALSTUDY_DIALS.md", text)
        self.assertIn("n/ote", text)
        for word in ("viable", "%", "score", "correct"):
            self.assertNotIn(word, text.replace("No verdict and no score", ""))


if __name__ == "__main__":
    unittest.main()
