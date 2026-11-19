import csv, json, random, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import mismatch_score as ms


def make_session(tmp, picker, seed=1):
    """20 pairs (10 shifted, 10 different_song), 5 repeats; picker(item, rng) -> (real|foil|tie, confidence)."""
    rng = random.Random(seed)
    items, key, rows = {}, {}, []
    ids = [f"P{i:02d}" for i in range(1, 21)]
    for n, i in enumerate(ids):
        items[i] = dict(id=i, repeat=False, repeat_of=None, kind="shifted" if n % 2 == 0 else "different_song",
                        real_side="first" if (n // 2) % 2 == 0 else "second")
    for n in range(5):
        o = items[ids[n]]
        items[f"R{n+1:02d}"] = dict(o, id=f"R{n+1:02d}", repeat=True, repeat_of=ids[n],
                                    real_side="second" if o["real_side"] == "first" else "first")
    for n, (i, it) in enumerate(items.items()):
        code = f"c{n:04x}"
        key[code] = {"id": i}
        choice, conf = picker(it, rng)
        if choice == "tie":
            w = "same"
        else:
            rs = it["real_side"]
            other = "second" if rs == "first" else "first"
            w = rs if choice == "real" else other
        rows.append([code, f"{w}|{conf}", "a, note", "2026-11-20T10:00:00", "0"])
    (tmp / "key").mkdir()
    json.dump({"seed": 1, "key": key}, open(tmp / "key/key.json", "w"))
    json.dump({"version": 1, "items": items}, open(tmp / "key/material_key.json", "w"))
    with open(tmp / "answers.csv", "w", newline="") as f:
        csv.writer(f).writerows(rows)
    return tmp


def test_all_real_met(tmp_path):
    r, _ = ms.score(make_session(tmp_path, lambda it, g: ("real", "high")))
    assert r["rule_met"] is True and r["real_pick_share"] == 1.0 and r["flip_rate"] == 0.0
    assert r["complete"] and r["answered"] == 25
    assert r["by_kind"]["shifted"]["n_non_tie"] == 10


def test_random_not_met(tmp_path):
    r, _ = ms.score(make_session(tmp_path, lambda it, g: (g.choice(["real", "foil"]), "low"), seed=3))
    assert r["rule_met"] is False


def test_all_foil_not_met(tmp_path):
    r, _ = ms.score(make_session(tmp_path, lambda it, g: ("foil", "low")))
    assert r["rule_met"] is False and r["real_pick_share"] == 0.0


def test_flip_rate_blocks_rule(tmp_path):
    # real on all first presentations, every repeat flips to foil -> f=1 -> bound 1.0 -> not met
    r, _ = ms.score(make_session(tmp_path, lambda it, g: ("foil" if it["repeat"] else "real", "medium")))
    assert r["flip_rate"] == 1.0 and r["rule_met"] is False and r["p_ge_0.70"] is True


def test_ties_dropped_and_confidence_split(tmp_path):
    def p(it, g):
        return ("tie", "low") if it["id"] in ("P01", "P02") else ("real", "high")
    r, _ = ms.score(make_session(tmp_path, p))
    assert r["ties"] == 2 and r["n_non_tie"] == 18 and r["real_pick_share"] == 1.0
    assert r["by_confidence"]["low"]["n_non_tie"] == 0 and r["by_confidence"]["low"]["real_pick_share"] is None
    assert r["by_confidence"]["high"]["n_non_tie"] == 18


def test_incomplete_session(tmp_path):
    make_session(tmp_path, lambda it, g: ("real", "high"))
    lines = open(tmp_path / "answers.csv").read().splitlines()[:10]
    open(tmp_path / "answers.csv", "w").write("\n".join(lines) + "\n")
    r, _ = ms.score(tmp_path)
    assert r["complete"] is False and r["answered"] == 10


def test_clopper_pearson_known():
    lo, hi = ms.cp(7, 10, 0.05, True)
    assert abs(lo - 0.3475) < 1e-3 and abs(hi - 0.9333) < 1e-3
    assert ms.cp(0, 0, 0.05, True) == (None, None)


def test_cli_writes_files(tmp_path):
    make_session(tmp_path, lambda it, g: ("real", "high"))
    out = subprocess.run([sys.executable, ms.__file__, str(tmp_path)], capture_output=True, text=True, check=True).stdout
    assert "rule met: True" in out
    assert (tmp_path / "mismatch_result.json").exists() and (tmp_path / "mismatch_result.md").exists()
