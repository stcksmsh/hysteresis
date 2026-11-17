"""WO48: a single may ask several questions (manifest field `questions`, list of {q, labels}); the answer is one label per question, stored joined by "|".
python3 -I -m unittest discover -s scripts/body -p test_dialstudy_wo48.py"""
import csv, json, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dialstudy_session as ses

QS = [dict(q="Is the flash on the beat?", labels=["yes", "partly", "no"]), dict(q="Is it the right speed?", labels=["right", "too fast", "too slow"])]


class TwoQuestions(unittest.TestCase):
    def test_two_questions_per_item(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for f in ("a.mp4", "b.mp4"):
                (root / f).write_bytes(f.encode() * 50)
            man = dict(labels=["yes", "partly", "no"], clips=[dict(id="a", kind="single", file="a.mp4", questions=QS, grid="pulse"), dict(id="b", kind="single", file="b.mp4", question="Is the flash on the beat?")])
            (root / "m.json").write_text(json.dumps(man))
            ses.build(root / "m.json", root / "s", seed=1)
            items = json.loads((root / "s" / "order.json").read_text())
            key = json.loads((root / "s" / "key" / "key.json").read_text())["key"]
            a = next(i for i in items if key[i["code"]]["id"] == "a")
            b = next(i for i in items if key[i["code"]]["id"] == "b")
            self.assertEqual(a["qs"], QS)
            self.assertNotIn("qs", b)
            s = ses.Session(root / "s")
            self.assertEqual(s.answer(dict(code=a["code"], answer="yes")), 400)                    # one label is not enough
            self.assertEqual(s.answer(dict(code=a["code"], answer=["yes", "right", "no"])), 400)   # wrong count
            self.assertEqual(s.answer(dict(code=a["code"], answer=["right", "yes"])), 400)         # wrong order
            self.assertEqual(s.answer(dict(code=a["code"], answer=["partly", "too fast"])), 200)
            self.assertEqual(s.answer(dict(code=a["code"], answer=["yes", "right"])), 409)
            self.assertEqual(s.answer(dict(code=b["code"], answer="no")), 200)                     # single-question items unchanged
            rows = {r[0]: r[1] for r in csv.reader(open(root / "s" / "answers.csv")) if r}
            self.assertEqual(rows[a["code"]], "partly|too fast")
            self.assertEqual(rows[b["code"]], "no")
            self.assertIn("it.qs", ses.PAGE)


if __name__ == "__main__":
    unittest.main()
