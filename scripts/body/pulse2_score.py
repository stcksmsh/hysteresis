"""WO51 scorer: BRAIN_SPEC 7.80 DECISION RULE as the overseer note states it.   pulse2_score.py SESSION_DIR [--view DIR] [--earlier S1 S2]
right speed = count of "right" over the 20 excerpts per source; stability = count of "yes" to "Is it steady?" per source;
pass = pulse v2 >= librosa on both counts. Per-item table next to Kosta's earlier answers for the same excerpt (first and second pulse flash
checks: librosa item vs librosa item, pulse v2 item vs the v1 pulse item). -> SESSION_DIR/score.json, SESSION_DIR/score.md, printed."""
import argparse
import csv
import json
from pathlib import Path

B = Path("/secondary/hyst-data/body")
VIEW = B / "pulse2" / "view"
EARLIER = {"flash": (B / "pulse/flash/session_2026-11-17", B / "pulse/flash/key.json"),
           "flash2": (B / "pulse/flash2/session_2026-11-17", B / "pulse/flash2/key.json")}


def answers(session):
    """code -> (answer, note); the last row for a code wins"""
    out = {}
    with open(Path(session) / "answers.csv", newline="") as f:
        for row in csv.reader(f):
            if row:
                out[row[0]] = (row[1], row[2] if len(row) > 2 else "")
    return out


def by_item(session, item_key):
    """manifest id -> (answer, note) for a built session and its manifest key"""
    skey = json.loads((Path(session) / "key/key.json").read_text())["key"]
    items = json.loads(Path(item_key).read_text())["items"]
    out = {}
    for code, (a, n) in answers(session).items():
        mid = skey[code]["id"]
        out[mid] = dict(items[mid], answer=a, note=n)
    return out


def earlier(earlier_map=EARLIER):
    """(check, song, source) -> earlier answer; source 'pulse' (v1) or 'lib'"""
    out = {}
    for chk, (s, k) in earlier_map.items():
        if not (Path(s) / "answers.csv").exists():
            continue
        for v in by_item(s, k).values():
            out[(chk, v["song"], v["source"])] = (v["answer"], v["note"])
    return out


def score(session, view=VIEW, earlier_map=EARLIER):
    cur = by_item(session, Path(view) / "key.json")
    old = earlier(earlier_map)
    counts = {s: dict(items=0, right=0, too_fast=0, too_slow=0, steady_yes=0, switches=0) for s in ("pulse2", "lib")}
    rows = []
    for mid, v in sorted(cur.items(), key=lambda kv: (kv[1]["check"], kv[1]["song"], kv[1]["source"])):
        parts = v["answer"].split("|")
        speed, steady = (parts + ["", ""])[:2]
        c = counts[v["source"]]
        c["items"] += 1
        c["right"] += speed == "right"
        c["too_fast"] += speed == "too fast"
        c["too_slow"] += speed == "too slow"
        c["steady_yes"] += steady == "yes"
        c["switches"] += steady == "switches"
        prev = old.get((v["check"], v["song"], "pulse" if v["source"] == "pulse2" else "lib"))
        rows.append(dict(id=mid, check=v["check"], song=v["song"], source=v["source"], speed=speed, steady=steady, note=v["note"],
                         earlier_source="pulse v1" if v["source"] == "pulse2" else "lib", earlier_answer=prev[0] if prev else None, earlier_note=prev[1] if prev else None))
    p, l = counts["pulse2"], counts["lib"]
    complete = p["items"] == 20 and l["items"] == 20
    res = dict(counts=counts, complete=complete, rule="pulse v2 >= librosa on count of 'right' and on count of 'yes' (steady), over the 20 excerpts",
               speed_ok=p["right"] >= l["right"], steady_ok=p["steady_yes"] >= l["steady_yes"], rows=rows)
    res["passes"] = bool(complete and res["speed_ok"] and res["steady_ok"])   # not decided until all 40 items are answered
    L = ["# Pulse v2 viewing score (BRAIN_SPEC 7.80 decision rule)", "", f"Session `{session}`; answered items {p['items'] + l['items']} of 40" + ("" if complete else " (INCOMPLETE)") + ".", "",
         "| source | right | too fast | too slow | steady yes | switches |", "|---|---|---|---|---|---|"]
    for s in ("pulse2", "lib"):
        c = counts[s]
        L.append(f"| {s} | {c['right']} | {c['too_fast']} | {c['too_slow']} | {c['steady_yes']} | {c['switches']} |")
    L += ["", f"Right speed: pulse v2 {p['right']} vs librosa {l['right']} -> {'pulse v2 >= librosa' if res['speed_ok'] else 'pulse v2 < librosa'}.",
          f"Steady: pulse v2 {p['steady_yes']} vs librosa {l['steady_yes']} -> {'pulse v2 >= librosa' if res['steady_ok'] else 'pulse v2 < librosa'}.",
          f"Decision rule: {('MET' if res['passes'] else 'NOT MET') if complete else 'NOT DECIDED (session incomplete)'}.", "",
          "| id | check | song | source | speed | steady | note | earlier (source) | earlier answer (on beat / speed) | earlier note |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['id']} | {r['check']} | {r['song'][:26]} | {r['source']} | {r['speed']} | {r['steady']} | {r['note']} | {r['earlier_source']} | {r['earlier_answer']} | {r['earlier_note']} |")
    (Path(session) / "score.json").write_text(json.dumps(res, indent=1))
    (Path(session) / "score.md").write_text("\n".join(L) + "\n")
    return res, "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--view", default=str(VIEW))
    a = ap.parse_args()
    print(score(a.session, a.view)[1])


if __name__ == "__main__":
    main()
