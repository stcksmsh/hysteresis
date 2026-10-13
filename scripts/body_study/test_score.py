"""Check score.py on a synthetic key and synthetic answers (never the real key)."""
import json, random, subprocess, sys, tempfile
from pathlib import Path

here = Path(__file__).parent
rng = random.Random(1)
tr = []
for n in range(24):
    p, k = n % 8, (1, 3, 5)[n // 8]
    tr.append({"test": f"t{n + 1:02d}", "odd": "ABC"[n % 3], "pairRegion": p,
               "oddRegion": (p + k) % 8, "k": k})
key = {"triplets": tr, "m": [[rng.random() for _ in range(37)] for _ in range(8)],
       "w": [1.0] * 8, "centres": list(range(8))}


def run(right):
    """`right` of 24 answered correctly (the first ones), the rest wrong."""
    ans = [{"shown": n + 1, "choice": t["odd"] if n < right else "ABC"[(n + 1) % 3],
            "text": "odd one jerky" if n == 0 else "", "time": "2026-10-13T00:00:00Z"}
           for n, t in enumerate(tr)]
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "a.json").write_text(json.dumps({"answers": ans}))
        (Path(d) / "k.json").write_text(json.dumps(key))
        return subprocess.run([sys.executable, here / "score.py", Path(d) / "a.json", Path(d) / "k.json"],
                              capture_output=True, text=True, check=True).stdout


out = run(16)
assert "16 of 24 correct -> PASS" in out, out
# triplets t01..t16 correct: regions 0..7 odd-found counts from n % 8 pattern
assert "t01 (found, odd region 1): odd one jerky" in out, out
assert "found minus missed" in out, out
assert "15 of 24 correct -> FAIL" in run(15)
assert "all found or all missed" in run(24)
print("score.py checks pass")
