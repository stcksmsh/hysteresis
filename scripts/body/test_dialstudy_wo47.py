"""WO47: a look single may carry its own question (manifest field `question`), custom labels via the manifest object. python3 -I -m unittest discover -s scripts/body -p test_dialstudy_wo47.py"""
import json, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dialstudy_session as ses


class SingleQuestion(unittest.TestCase):
    def test_per_item_question_and_labels(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for f in ("a.mp4", "b.mp4"):
                (root / f).write_bytes(f.encode() * 50)
            man = dict(labels=["yes", "partly", "no"], clips=[dict(id="a", kind="single", file="a.mp4", question="Are the clicks on the beat?", grid="proj"), dict(id="b", kind="single", file="b.mp4")])
            (root / "m.json").write_text(json.dumps(man))
            ses.build(root / "m.json", root / "s", seed=1)
            items = json.loads((root / "s" / "order.json").read_text())
            key = json.loads((root / "s" / "key" / "key.json").read_text())["key"]
            qs = {key[i["code"]]["id"]: i["q"] for i in items}
            self.assertEqual(qs["a"], "Are the clicks on the beat?")
            self.assertEqual(qs["b"], ses.LOOK_Q["single"])
            self.assertEqual(next(v for v in key.values() if v["id"] == "a")["grid"], "proj")
            self.assertEqual(json.loads((root / "s" / "labels.json").read_text()), ["yes", "partly", "no"])


if __name__ == "__main__":
    unittest.main()
