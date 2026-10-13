"""triplets.py REGIONS.json OUTDIR: the 24 triplets of docs/BODY_STUDY.md from the
addendum-4 regions (`body_study regions`), fixed by addendum 5 to the last set of
commit 90cbec8 (factor 0.6: its smallest ratio is 0.618).

Triplet i (0..23): pair from region p = i mod 8, odd one from region (p + k) mod 8,
k = 1, 3, 5 for i in 0-7, 8-15, 16-23. Each region gives its 9 clips in its own
order (centre first): clips 0-5 go to its 3 pairs (in triplet order), clips 6-8 to
its 3 odd appearances. Triplet order and the odd one's position are shuffled with
Python's random.Random(20261014).

Writes OUTDIR/key.json (never read by answer.html) and OUTDIR/clips.tsv (one line
per clip: clip file name, b, seed, stretch) for render.sh, and OUTDIR/triplets.tsv
(test file name, the three clip names A B C).
"""
import json, random, sys
from pathlib import Path

rg = json.load(open(sys.argv[1]))
out = Path(sys.argv[2])
assert rg["centres"] == [1706, 1966, 529, 786, 1582, 365, 1919, 183], "not addendum 5's set"
assert rg["smallestRatio"] >= 0.6, "addendum 5 factor 0.6 broken"
regions = rg["regions"]
assert len(regions) == 8 and all(len(r["clips"]) == 9 for r in regions)

pair_next = [0] * 8  # next clip index for a pair, per region
odd_next = [6] * 8
trip = []
for i in range(24):
    p, k = i % 8, (1, 3, 5)[i // 8]
    q = (p + k) % 8
    a, b = pair_next[p], pair_next[p] + 1
    pair_next[p] += 2
    o = odd_next[q]
    odd_next[q] += 1
    trip.append({"index": i, "pairRegion": p, "oddRegion": q, "k": k,
                 "pair": [[p, a], [p, b]], "odd": [q, o]})
assert pair_next == [6] * 8 and odd_next == [9] * 8

rng = random.Random(20261014)
rng.shuffle(trip)
for t in trip:
    t["oddPosition"] = "ABC"[rng.randrange(3)]

def name(rc):
    return f"r{rc[0]}c{rc[1]}"

key, lines = [], []
for n, t in enumerate(trip, 1):
    slots = list(t["pair"])
    slots.insert("ABC".index(t["oddPosition"]), t["odd"])
    test = f"t{n:02d}"
    clips = []
    for r, c in slots:
        clip = regions[r]["clips"][c]
        clips.append({"name": name((r, c)), "region": r, "centre": regions[r]["centre"],
                      "sweep": clip["sweep"], "b": clip["b"], "seed": clip["seed"],
                      "stretch": clip["s"]})
    key.append({"test": test, "odd": t["oddPosition"], "pairRegion": t["pairRegion"],
                "oddRegion": t["oddRegion"], "k": t["k"], "abc": clips})
    lines.append("\t".join([test] + [c["name"] for c in clips]))

json.dump({"triplets": key, "m": rg["m"], "w": rg["w"], "centres": rg["centres"],
           "shuffleSeed": 20261014}, open(out / "key.json", "w"), indent=1)
(out / "triplets.tsv").write_text("\n".join(lines) + "\n")
(out / "clips.tsv").write_text("".join(
    f"{name((r, c))}\t{','.join(repr(x) for x in cl['b'])}\t{cl['seed']}\t{cl['s']!r}\n"
    for r, reg in enumerate(regions) for c, cl in enumerate(reg["clips"])))
print("24 triplets; key in", out / "key.json")
