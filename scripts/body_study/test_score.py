"""Check score.py on a synthetic key and synthetic answers (never the real key)."""
import json, random, subprocess, sys, tempfile
from pathlib import Path

here = Path(__file__).parent
rng = random.Random(1)
tr = []
for n in range(32):
    p, k = n % 8, (1, 3, 5, 7)[n // 8]
    tr.append({"shown": f"t{n + 1:02d}", "odd": "ABC"[n % 3], "pairRegion": p,
               "oddRegion": (p + k) % 8, "k": k})
key = {"triplets": tr, "m": [[rng.random() for _ in range(37)] for _ in range(8)],
       "w": [1.0] * 8, "speed": [10.0 * r for r in range(8)], "centres": list(range(8))}


def run(right):
    """`right` of 32 answered correctly (the first ones), the rest wrong."""
    # second answer: always the true odd one (must never count)
    ans = [{"shown": n + 1, "counted": t["odd"] if n < right else "ABC"[(n + 1) % 3],
            "second": t["odd"], "text": "odd one jerky" if n == 0 else "",
            "timeToCountedS": 30.0 + n, "totalS": 60.0 + n, "pausesFirstPass": n % 2,
            "replaysBeforeCounted": {"A": int(n < 4), "B": int(n < 2), "C": 0},
            "replays": {"A": n % 3, "B": 0, "C": 1}}
           for n, t in enumerate(tr)]
    # practice answers are all wrong: they must never count
    prac = [{"shown": f"p{q}", "counted": "A", "correct": False} for q in range(1, 5)]
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "a.json").write_text(json.dumps({"practice": prac, "answers": ans}))
        (Path(d) / "k.json").write_text(json.dumps(key))
        return subprocess.run([sys.executable, here / "score.py", Path(d) / "a.json", Path(d) / "k.json"],
                              capture_output=True, text=True, check=True).stdout


out = run(20)
assert "20 of 32 correct -> PASS" in out, out
assert "P(>= 20 | guessing) = 0.0007" in out, out
assert "t01 (found, odd region 1): odd one jerky" in out, out
assert "found minus missed" in out, out
assert "second answers given 32 of 32: correct 32, changed from the counted answer 12" in out, out
assert "timeToCountedS: median 45.5" in out, out
assert "first half (shown 1-16): 16/16; second half: 4/16" in out, out
assert "practice: 0 of 4 right" in out, out
assert "replays before the counted answer per triplet: 0: 28, 1: 2, 2: 2; found with any 4 of 4, without 16 of 28" in out, out
# odd position table: odd A is t01, t04, ... (11 triplets); the first 20 are right,
# a wrong answer to odd A is B
assert "odd A   7   4   0   7/11" in out, out
# speed gap of triplet n: 10 x |((p + k) mod 8) - p|; the 16 largest, by hand
gaps = [10 * abs((t["pairRegion"] + t["k"]) % 8 - t["pairRegion"]) for t in tr]
far = sorted(range(32), key=lambda i: -gaps[i])[:16]
want = sum(i < 20 for i in far)
assert f"{want}/16; other 16" in out and f") {20 - want}/16" in out, out
assert "19 of 32 correct -> FAIL" in run(19)
assert "0 of 32 correct -> FAIL" in run(0)
assert "all found or all missed" in run(32)
print("score.py checks pass")
