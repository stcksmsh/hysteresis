"""triplets.py REGIONS.json OUTDIR: the 32 scored and 4 practice triplets of
docs/BODY_STUDY.md, addendum 8, from `body_study regions` (round 2).

Scored triplet i (0..31): pair from region p = i mod 8, odd one from region
(p + k) mod 8, k = 1, 3, 5, 7 for i in 0-7, 8-15, 16-23, 24-31. Each region gives
its 12 clips in stored order (centre first): clips 0-7 go to its 4 pairs (in
triplet order), clips 8-11 to its 4 odd appearances. With random.Random(20261017):
the triplet order is shuffled, then a list of odd positions (A 11, B 11, C 10
times) is shuffled and assigned in shown order.

Practice triplet q (0..3): pair from practice body 2q (its 2 clips), odd one from
practice body 2q + 1 (its first clip); odd position drawn from the same generator
after the scored ones (randrange(3)).

Writes OUTDIR/key.json (never read by answer.html), OUTDIR/clips.tsv (clip name, b,
seed, stretch), OUTDIR/triplets.tsv (shown name, clip names A B C) and
OUTDIR/test/practice.js (the practice odd positions only, for the page's
feedback; a script, so the page also works from file://).
"""
import json, random, sys
from pathlib import Path

rg = json.load(open(sys.argv[1]))
out = Path(sys.argv[2])
assert rg["holds"], "separation rule broken: no triplets"
regions, practice = rg["regions"], rg["practice"]
assert len(regions) == 8 and all(len(r["clips"]) == 12 for r in regions)
assert len(practice) == 8 and all(len(p["clips"]) == 2 for p in practice)

pair_next, odd_next = [0] * 8, [8] * 8
trip = []
for i in range(32):
    p, k = i % 8, (1, 3, 5, 7)[i // 8]
    q = (p + k) % 8
    a = pair_next[p]
    pair_next[p] += 2
    trip.append({"index": i, "pairRegion": p, "oddRegion": q, "k": k,
                 "pair": [(p, a), (p, a + 1)], "odd": (q, odd_next[q])})
    odd_next[q] += 1
assert pair_next == [8] * 8 and odd_next == [12] * 8

rng = random.Random(20261017)
rng.shuffle(trip)
pos = list("A" * 11 + "B" * 11 + "C" * 10)
rng.shuffle(pos)
for t, o in zip(trip, pos):
    t["oddPosition"] = o
prac = [{"pairBody": 2 * q, "oddBody": 2 * q + 1, "oddPosition": "ABC"[rng.randrange(3)]}
        for q in range(4)]


def clip(src, name):
    return {"name": name, "sweep": src.get("sweep"), "b": src["b"], "seed": src["seed"],
            "stretch": src["s"]}


key, lines, clips = [], [], {}
for n, t in enumerate(trip, 1):
    slots = list(t["pair"])
    slots.insert("ABC".index(t["oddPosition"]), t["odd"])
    abc = []
    for r, c in slots:
        cl = clip(regions[r]["clips"][c], f"r{r}c{c:02d}")
        cl.update(region=r, centre=regions[r]["centre"])
        abc.append(cl)
        clips[cl["name"]] = cl
    shown = f"t{n:02d}"
    key.append({"shown": shown, "odd": t["oddPosition"], "pairRegion": t["pairRegion"],
                "oddRegion": t["oddRegion"], "k": t["k"], "abc": abc})
    lines.append("\t".join([shown] + [c["name"] for c in abc]))
pkey = []
for q, t in enumerate(prac, 1):
    pb, ob = practice[t["pairBody"]], practice[t["oddBody"]]
    slots = [clip(pb["clips"][0] | {"sweep": pb["sweep"]}, f"q{t['pairBody']}c0"),
             clip(pb["clips"][1] | {"sweep": pb["sweep"]}, f"q{t['pairBody']}c1")]
    slots.insert("ABC".index(t["oddPosition"]), clip(ob["clips"][0] | {"sweep": ob["sweep"]}, f"q{t['oddBody']}c0"))
    for c in slots:
        clips[c["name"]] = c
    pkey.append({"shown": f"p{q}", "odd": t["oddPosition"], "pairBody": t["pairBody"],
                 "oddBody": t["oddBody"], "abc": slots})
    lines.append("\t".join([f"p{q}"] + [c["name"] for c in slots]))

assert len(clips) == 96 + 12 and len({(c["seed"], tuple(c["b"])) for c in clips.values()}) == 108
assert sorted(t["odd"] for t in key) == sorted(pos)
for r in range(8):
    assert sum(t["oddRegion"] == r for t in key) == 4 and sum(t["pairRegion"] == r for t in key) == 4

# mean joint speed (deg/s) of each region: mean over its 12 clips of the mean over the
# five joints of each joint's mean speed (descriptor 6 j)
speed = [sum(sum(c["desc"][6 * j] for j in range(5)) / 5 for c in r["clips"]) / 12 for r in regions]
json.dump({"triplets": key, "practice": pkey, "m": rg["m"], "w": rg["w"], "speed": speed, "centres": rg["centres"],
           "shuffleSeed": 20261017}, open(out / "key.json", "w"), indent=1)
(out / "triplets.tsv").write_text("\n".join(lines) + "\n")
(out / "clips.tsv").write_text("".join(
    f"{c['name']}\t{','.join(repr(x) for x in c['b'])}\t{c['seed']}\t{c['stretch']!r}\n"
    for c in clips.values()))
(out / "test").mkdir(exist_ok=True)
(out / "test" / "practice.js").write_text(
    "window.PRACTICE = " + json.dumps({"odd": [t["odd"] for t in pkey]}) + ";\n")
print("32 scored + 4 practice triplets; key in", out / "key.json")
