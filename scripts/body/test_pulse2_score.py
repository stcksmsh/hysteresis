"""WO51 scorer test on synthetic answers.   /secondary/hyst-env/brain/bin/python -m unittest discover -s scripts/body -p test_pulse2_score.py"""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pulse2_score as S  # noqa: E402


def session(d, items, answers):
    """items: id -> meta; answers: id -> (answer, note). Writes key/key.json (code -> {id}) and answers.csv"""
    (d / "key").mkdir(parents=True)
    codes = {mid: f"c{i:04x}" for i, mid in enumerate(items)}
    (d / "key/key.json").write_text(json.dumps(dict(seed=1, key={c: dict(id=mid) for mid, c in codes.items()})))
    with open(d / "answers.csv", "w", newline="") as f:
        w = csv.writer(f)
        for mid, (a, n) in answers.items():
            w.writerow([codes[mid], a, n, "t", 0])


class Score(unittest.TestCase):
    def test_decision_rule_counts_and_earlier_answers(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            songs = [(("flash" if i < 10 else "flash2"), f"song{i:02d}") for i in range(20)]
            items, ans = {}, {}
            for i, (chk, s) in enumerate(songs):
                for src in ("pulse2", "lib"):
                    mid = f"Q{len(items):02d}"
                    items[mid] = dict(song=s, source=src, check=chk, start_s=10.0)
                    # pulse2: 14 right, 15 steady; lib: 13 right, 15 steady -> rule met
                    if src == "pulse2":
                        ans[mid] = ("right" if i < 14 else "too slow") + "|" + ("yes" if i < 15 else "switches"), "n"
                    else:
                        ans[mid] = ("right" if i < 13 else "too fast") + "|" + ("yes" if i >= 5 else "switches"), ""
            view = t / "view"; view.mkdir()
            (view / "key.json").write_text(json.dumps(dict(items=items)))
            sess = t / "sess"
            session(sess, items, ans)
            # earlier checks: one per flash key, one item per song and source (pulse = v1)
            em = {}
            for chk in ("flash", "flash2"):
                its = {}
                for chk2, s in songs:
                    if chk2 == chk:
                        for src in ("pulse", "lib"):
                            its[f"Q{len(its):02d}"] = dict(song=s, source=src)
                (t / chk).mkdir()
                (t / chk / "key.json").write_text(json.dumps(dict(items=its)))
                session(t / chk / "s", its, {m: (f"yes|right-{v['source']}", "old note") for m, v in its.items()})
                em[chk] = (t / chk / "s", t / chk / "key.json")
            res, md = S.score(sess, view, em)
            self.assertEqual(res["counts"]["pulse2"]["right"], 14)
            self.assertEqual(res["counts"]["lib"]["right"], 13)
            self.assertEqual(res["counts"]["pulse2"]["steady_yes"], 15)
            self.assertEqual(res["counts"]["lib"]["steady_yes"], 15)
            self.assertEqual(res["counts"]["pulse2"]["too_slow"], 6)
            self.assertTrue(res["complete"] and res["passes"])
            r = next(x for x in res["rows"] if x["song"] == "song03" and x["source"] == "pulse2")
            self.assertEqual(r["earlier_answer"], "yes|right-pulse")
            r = next(x for x in res["rows"] if x["song"] == "song12" and x["source"] == "lib")
            self.assertEqual(r["earlier_answer"], "yes|right-lib")
            self.assertTrue((sess / "score.md").exists())
            # one fewer "right" for pulse v2 than librosa -> not met
            ans2 = dict(ans)
            for mid in ("Q00", "Q02"):
                ans2[mid] = ("too slow|yes", "")
            sess2 = t / "sess2"
            session(sess2, items, ans2)
            res2, _ = S.score(sess2, view, em)
            self.assertEqual(res2["counts"]["pulse2"]["right"], 12)
            self.assertFalse(res2["speed_ok"])
            self.assertFalse(res2["passes"])


if __name__ == "__main__":
    unittest.main()
