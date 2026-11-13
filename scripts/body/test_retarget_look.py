"""Tests for the retarget look-test session and report (WO32A).  python test_retarget_look.py"""
import csv, json, tempfile, threading, unittest, urllib.error, urllib.request
from pathlib import Path

import dialstudy_session as ses
import retarget_report as rep

V1_FIRST = {0, 2, 4}  # pair clip indices where V1 plays first (balanced by the manifest builder: 3 of 5)


def fake(root):
    items = []
    for c in range(1, 11):
        for v in ("V1", "V2"):
            f = f"C{c:02d}_{v}.mp4"; (root / f).write_bytes(f.encode() * 20)
            items.append(dict(id=f"C{c:02d}_{v}", kind="single", file=f, variant=v, clip=f"C{c:02d}", genre=f"g{c}", source_seq=f"{c:03d}",
                              window_start_s=5.0, csv=f"C{c:02d}_{v}.csv", music_credit="x"))
    for c in (3, 8):
        f = f"C{c:02d}_R1S03.mp4"; (root / f).write_bytes(b"r" * 50)
        items.append(dict(id=f"C{c:02d}_R1S03", kind="single", file=f, variant="R1_S03", clip=f"C{c:02d}", genre=f"g{c}"))
    for i, c in enumerate((1, 3, 5, 7, 9)):
        order = ("V1", "V2") if i in V1_FIRST else ("V2", "V1")
        items.append(dict(id=f"PAIR_C{c:02d}", kind="pair", files=[f"C{c:02d}_{v}.mp4" for v in order], variants=list(order), clip=f"C{c:02d}", genre=f"g{c}"))
    (root / "manifest.json").write_text(json.dumps({"clips": items}))
    return root / "manifest.json"


class Look(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name); self.manifest = fake(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_labels_questions_and_fixed_pair_order(self):
        for seed in range(12):  # the pair order must never be reshuffled, whatever the seed
            out = self.root / f"s{seed}"; ses.build(self.manifest, out, seed=seed)
            key = json.loads((out / "key/key.json").read_text())["key"]
            order = json.loads((out / "order.json").read_text())
            self.assertEqual(json.loads((out / "labels.json").read_text()), ["yes", "sort of", "no"])
            self.assertEqual(len(order), 20 + 2 + 5)
            pairs = [i for i in order if i["kind"] == "pair"]
            self.assertEqual(len(pairs), 5)
            self.assertEqual(sum(1 for p in pairs if key[p["code"]]["variants"][0] == "V1"), 3)
            for p in pairs:
                k = key[p["code"]]
                self.assertEqual(k["first"], k["files"][0] if "files" in k else k["first"])
                self.assertTrue(k["first"].endswith(f"_{k['variants'][0]}.mp4"), k)
                self.assertEqual(p["q"], "Which looks more like a person dancing?")
            self.assertTrue(all(i["q"] == "Does this look like dancing?" for i in order if i["kind"] == "single"))
        # same seed, same order
        a = self.root / "a"; ses.build(self.manifest, a, seed=7)
        self.assertEqual((a / "order.json").read_text(), (self.root / "s7" / "order.json").read_text())

    def test_serve_answers_and_hidden_key(self):
        out = self.root / "s"; ses.build(self.manifest, out, seed=1)
        srv = ses.make_server(out, 0)
        threading.Thread(target=srv.serve_forever, daemon=True).start(); self.addCleanup(srv.shutdown)
        self.assertEqual(srv.server_address[0], "127.0.0.1")
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        for path in ("/key/key.json", "/order.json", "/answers.csv"):
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(base + path)
            self.assertEqual(e.exception.code, 404)
        st = json.loads(urllib.request.urlopen(base + "/api/state").read())
        self.assertEqual(st["labels"], ["yes", "sort of", "no"])
        self.assertNotIn("V1", json.dumps(st))  # coded names only
        it = st["item"]

        def post(code, ans):
            req = urllib.request.Request(base + "/api/answer", json.dumps({"code": code, "answer": ans, "note": "n"}).encode(), {"Content-Type": "application/json"})
            try:
                return urllib.request.urlopen(req).status
            except urllib.error.HTTPError as e:
                return e.code
        bad = "first" if it["kind"] == "single" else "yes"
        self.assertEqual(post(it["code"], bad), 400)
        self.assertEqual(post(it["code"], "yes" if it["kind"] == "single" else "first"), 200)
        self.assertEqual(post(it["code"], "no" if it["kind"] == "single" else "second"), 409)

    def test_report_on_synthetic_session(self):
        out = self.root / "s"; ses.build(self.manifest, out, seed=3)
        key = json.loads((out / "key/key.json").read_text())["key"]
        with open(out / "answers.csv", "w", newline="") as f:
            w = csv.writer(f)
            for c, k in key.items():
                if k["id"] == "C01_V1": w.writerow([c, "yes", "nice|flow", "t", 0])
                if k["id"] == "C02_V2": w.writerow([c, "no", "", "t", 0])
                if k["id"] == "PAIR_C03": w.writerow([c, "second", "arm", "t", 0])
        numbers = {"C01": {"V1": {"limiter_share": {"base": 0.1, "elbow": 0.25}, "gates": {"hf_share": 0.003, "contact_substeps": 0}}, "V2": {"limiter_share": {"base": 0.0}}}}
        nf = self.root / "numbers.json"; nf.write_text(json.dumps(numbers))
        text = rep.build(out, nf)
        for h in ("## Singles: clip, variant, answer, note", "## Singles: counts per variant", "## Pairs (order as shown)", "## Per-joint limiter cuts", "## Gate values"):
            self.assertEqual(text.count(h), 1, h)
        self.assertIn("| C01 | V1 | g1 | C01_V1 | yes | nice/flow |", text)
        self.assertIn("| V1 | 1 | 0 | 0 | 9 |", text)  # V1: one yes, nine unanswered
        self.assertIn("| R1_S03 | 0 | 0 | 0 | 2 |", text)
        pair = next(c for c, k in key.items() if k["id"] == "PAIR_C03")
        v = key[pair]["variants"]  # clip 3 is pair index 1: V2 shown first
        self.assertEqual(v, ["V2", "V1"])
        self.assertIn("| C03 | PAIR_C03 | V2 | V1 | second | V1 | arm |", text)
        self.assertIn("Variant shown first, pairs: V1 3, V2 2.", text)
        self.assertIn(": V1 1; unanswered 4.", text)
        self.assertIn("| C01 | V1 | limiter_share.elbow | 0.25 |", text)
        self.assertIn("| C01 | V1 | gates.hf_share | 0.003 |", text)
        for w in ("worth building", "viable", "correct", "pass ", "winner"):
            self.assertNotIn(w, text)
        # the report also builds without numbers
        self.assertNotIn("## Gate values", rep.build(out))


if __name__ == "__main__":
    unittest.main()
