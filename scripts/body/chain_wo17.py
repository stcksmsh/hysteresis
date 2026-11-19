"""WO17 chain, one detached unit: the WO15A toy try 1 recipe (body v2f, hard stop, floor/acc hinges, contact tc 0.006, raised plane, jerk 0.03, switch 0.01, held-out) plus --smooth-u (BRAIN_SPEC 7.32),
seed 0 and then seed 1 (BOTH always run: the clips are wanted whatever the gate says). Per seed: the run, the WO7 controls, the end-stop analysis, the summary, the gate (m3f_gate17.py: 7.30.3 + parking
7.31.2 + report-only lines). Output /secondary/hyst-data/body/m3f/rerun4/seed{0,1}/, verdict.json. Waits for mains power before each step; skips finished steps; resumes from ckpt.pkl. Launch: chain_wo17.sh.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

D = Path("/secondary/hyst-data/body/m3f/rerun4")
PY = "/secondary/hyst-env/body/bin/python"
OPTS = ["--eval", "held", "--body", "v2f", "--lam", "0.03", "--lr", "1e-3", "--epochs", "40", "--w-jerk", "0.03", "--w-switch", "0.01", "--floor-acc-hinges", "--hard-clip",
        "--contact-tc", "0.006", "--raised-plane", "--w-floor", "1.0", "--smooth-u"]


def mains():
    while Path("/sys/class/power_supply/ADP1/online").read_text().strip() != "1":
        time.sleep(30)


def sh(*cmd, tries=3):
    for _ in range(tries):
        mains()
        if subprocess.run(["taskset", "-c", "0-7", "env", "OMP_NUM_THREADS=8", PY, "-u", *cmd]).returncode == 0:
            return True
    return False


def seed(n):
    d = D / f"seed{n}"
    if not (d / "try1" / "result.json").exists():
        sh("run_m3f.py", "--out", str(d / "try1"), "--seed", str(n), *OPTS)
    if not (d / "try1" / "controls" / "summary.json").exists():
        sh("m3f_controls.py", "--try", str(d / "try1"))
    sh("m3f_endstop.py", str(d / "try1"), str(d / "try1" / "controls"))
    sh("m3f_gate17.py", str(d))
    return json.loads((d / "gate17.json").read_text())


def main():
    g = {n: seed(n) for n in (0, 1)}
    v = {f"seed{n}": g[n]["pass"] for n in g}
    (D / "verdict.json").write_text(json.dumps({**v, "pass": bool(all(v.values())), "parts": {f"seed{n}": g[n]["parts"] for n in g}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
