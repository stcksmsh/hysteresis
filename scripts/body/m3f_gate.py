"""WO15A gate (BRAIN_SPEC 7.30.3 / 7.29.3), per seed: PASS = every toy-bar component (external and internal (a), (b), (c), argmax) AND (e'1) mean <= 6.001 AND (e'2) mean <= 0.01101 AND
floor-margin breaches (check-csv rule from z = 0) in <= 2 of 16 episodes. Reads RUNDIR/try1/result.json; writes RUNDIR/gate.json and prints the verdict.
    m3f_gate.py RUNDIR [RUNDIR ...]
"""
import json
import sys
from pathlib import Path

E1_MAX, E2_MAX, FLOOR_EPS_MAX = 6.001, 0.01101, 2


def gate(rundir):
    r = json.loads((Path(rundir) / "try1" / "result.json").read_text())["result"]["argmax"]
    parts = {"ext_a": bool(r["ext"]["a_pass"]), "int_a": bool(r["int"]["a_pass"]), "b": bool(r["b_pass"]), "c": bool(r["c_pass"]),
             "eprime1": bool(r["eprime"]["acc_p99_mean"] <= E1_MAX), "eprime2": bool(r["eprime"]["fast_mean"] <= E2_MAX), "floor_breach_episodes": bool(r["breaches"]["floor_m"]["episodes_with_breach"] <= FLOOR_EPS_MAX)}
    out = {"pass": all(parts.values()), "parts": parts, "eprime1": r["eprime"]["acc_p99_mean"], "eprime2": r["eprime"]["fast_mean"], "floor_breach_episodes": r["breaches"]["floor_m"]["episodes_with_breach"],
           "floor_breach_row_share": r["breaches"]["floor_m"]["row_share_mean"], "floor_breach_worst_m": r["breaches"]["floor_m"]["worst_excess"]}
    (Path(rundir) / "gate.json").write_text(json.dumps(out, indent=1))
    return out


def main():
    for d in sys.argv[1:]:
        g = gate(d)
        print(d, "PASS" if g["pass"] else "FAIL", {k: v for k, v in g["parts"].items() if not v} or "all components pass", "e'1 %.3f e'2 %.5f floor-breach episodes %d" % (g["eprime1"], g["eprime2"], g["floor_breach_episodes"]))


if __name__ == "__main__":
    main()
