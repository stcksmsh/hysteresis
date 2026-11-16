"""WO43: a look pair may carry its own question (manifest field `question`); without one the old question stays. python3 -I -m unittest discover -s scripts/body -p test_dialstudy_wo43.py"""
import json, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dialstudy_session as ses


class LookPairQuestion(unittest.TestCase):
    def test_per_item_question(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for f in ("p1.mp4", "p2.mp4", "p3.mp4", "p4.mp4"):
                (root / f).write_bytes(f.encode() * 50)
            man = [dict(id="a", kind="pair", files=["p1.mp4", "p2.mp4"], question="Which looks higher?", control="height", high_first=True),
                   dict(id="b", kind="pair", files=["p3.mp4", "p4.mp4"])]
            (root / "m.json").write_text(json.dumps(man))
            ses.build(root / "m.json", root / "s", seed=1)
            items = json.loads((root / "s" / "order.json").read_text())
            key = json.loads((root / "s" / "key" / "key.json").read_text())["key"]
            qs = {key[i["code"]]["id"]: i["q"] for i in items}
            self.assertEqual(qs["a"], "Which looks higher?")
            self.assertEqual(qs["b"], ses.LOOK_Q["pair"])
            ka = next(v for v in key.values() if v["id"] == "a")
            self.assertEqual((ka["control"], ka["high_first"]), ("height", True))
            self.assertEqual(json.loads((root / "s" / "pair_labels.json").read_text()), ["first", "second", "same"])


if __name__ == "__main__":
    unittest.main()
