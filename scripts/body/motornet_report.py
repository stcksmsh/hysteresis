#!/usr/bin/env python3
"""Join a motor-network session's answers with its key and the measurements into docs/MOTORNET_REPORT.md (WO29B).

  motornet_report.py --session SESSION_DIR --measurements measurements.json [--round1 ROUND1_SESSION_DIR] [--out docs/MOTORNET_REPORT.md]

Tables only. No verdict, no score, no counts of correct answers. The setting values are read from settings.json next to the
clips folder (SESSION_DIR/../settings.json) when it exists.
"""
import argparse, csv, json
from pathlib import Path

ROUND1 = "/secondary/hyst-data/body/dialstudy/session_2026-11-12"
MEAS = ["pr", "regime", "freq_hz", "hand_speed", "hand_height", "straightness"]


def cell(s):
    if isinstance(s, float):
        s = f"{s:.3g}"
    return str(s if s not in (None, "") else "-").replace("|", "/").replace("\n", " ")


def table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows])


def answers(session):
    with open(Path(session) / "answers.csv", newline="") as f:
        return {r[0]: r for r in csv.reader(f) if r}


def values_text(v):
    if v is None:
        return "-"
    if isinstance(v, dict):
        return ", ".join(f"{k} {x:.3g}" if isinstance(x, (int, float)) else f"{k} {x}" for k, x in v.items())
    return ", ".join(f"{x:.3g}" for x in v) if isinstance(v, (list, tuple)) else str(v)


def report(session, measurements, round1=ROUND1):
    session = Path(session)
    key = json.loads((session / "key" / "key.json").read_text())["key"]
    ans = answers(session)
    label = lambda c: ans[c][1] if c in ans else "(not answered)"
    note = lambda c: ans[c][2] if c in ans else ""
    meas = json.loads(Path(measurements).read_text())
    sf = session.parent / "settings.json"
    settings = {}
    if sf.is_file():
        s = json.loads(sf.read_text())
        s = s.get("settings", s) if isinstance(s, dict) else s
        settings = {(e.get("id") or e.get("setting")): e.get("values", e) for e in s} if isinstance(s, list) else s
    singles = {c: k for c, k in key.items() if k.get("part") in (1, 2, 4)}
    pairs = {c: k for c, k in key.items() if k.get("part") == 3}
    p1 = {k["setting"]: c for c, k in singles.items() if k.get("part") == 1}
    out = ["# Motor-network toy test report", "",
           "Kosta's labels next to the gain setting and the measured numbers. No verdict and no score here: what it means is Kosta's call.",
           "Network and body parameters used: see `docs/MOTORNET_PARAMS.md`.", ""]

    rows = []
    for s in sorted(p1):
        m = meas.get(s, {})
        rows.append([s, values_text(settings.get(s)), label(p1[s]), note(p1[s])] + [m.get(x) for x in MEAS])
    out += ["## Part 1: silent, every setting (lamp)", "", table(["setting", "values", "label", "note"] + MEAS, rows), ""]

    ball = {k["setting"]: c for c, k in singles.items() if k.get("part") == 2}
    out += ["## Part 2: ball vs lamp", "", table(["setting", "lamp label", "lamp note", "ball label", "ball note"],
            [[s, label(p1[s]) if s in p1 else "(none)", note(p1[s]) if s in p1 else "", label(c), note(c)] for s, c in sorted(ball.items())]), ""]

    if pairs:
        rows = []
        for c, k in sorted(pairs.items(), key=lambda kv: str(kv[1].get("song"))):
            a = ans.get(c)
            sett = [k.get("first_setting"), k.get("second_setting")]
            chosen = "(not answered)" if not a else {"first": sett[0], "second": sett[1]}.get(a[1], "neither")
            rows.append([k.get("song"), ", ".join(map(str, sorted(map(str, sett)))), a[1] if a else "(not answered)", chosen, note(c)])
        out += ["## Part 3: which render fits the music", "", table(["song", "settings", "pick", "chosen setting", "note"], rows), ""]
    else:
        out += ["## Part 3", "", "Not run (no pairs in this session).", ""]

    r1key = {}
    r1ans = {}
    try:
        r1key = json.loads((Path(round1) / "key" / "key.json").read_text())["key"]
        r1ans = answers(round1)
    except OSError:
        pass
    byid = {k["id"]: c for c, k in r1key.items()}
    rows = []
    for c, k in sorted(((c, k) for c, k in singles.items() if k.get("part") == 4), key=lambda kv: str(kv[1].get("round1_id"))):
        rc = byid.get(k.get("round1_id"))
        rows.append([k.get("round1_id"), r1ans[rc][1] if rc in r1ans else "(no round-1 answer)", label(c), note(c)])
    out += ["## Part 4: round 1 vs now", "", table(["round-1 clip", "round-1 label", "label now", "note now"], rows) if rows else "No repeated clips in this session.", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", required=True); ap.add_argument("--measurements", required=True); ap.add_argument("--round1", default=ROUND1)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "docs" / "MOTORNET_REPORT.md"))
    a = ap.parse_args()
    Path(a.out).write_text(report(a.session, a.measurements, a.round1) + "\n")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
