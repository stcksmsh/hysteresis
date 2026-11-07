"""WO15A chain, one detached unit: toy try 1 with the raised plane (make_arm_v2.RAISED_PLANE_Z = 0.053 m), contact time constant 0.006 s, the floor hinge on the surfaces' clearance above the plane
(divided by 0.05 m, weight 1), the other terms as WO14A (hand-acceleration hinge, hand-speed/jolt/limit penalties, jerk 0.03, switch 0.01, hard stop), body v2f, held-out episodes, seed 0 and then
seed 1. Per seed: the run, the WO7 controls, the end-stop analysis, the summary, the gate (m3f_gate.py). Seed 1 runs only if seed 0 passes the gate (BRAIN_SPEC 7.30.3: either fails -> stop and
report). Then the tests. Output /secondary/hyst-data/body/m3f/rerun3/seed{0,1}/. Waits for mains power before each step; skips finished steps; resumes from ckpt.pkl. Launch: chain_wo15.sh.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

D = Path("/secondary/hyst-data/body/m3f/rerun3")
PY = "/secondary/hyst-env/body/bin/python"
OPTS = ["--eval", "held", "--body", "v2f", "--lam", "0.03", "--lr", "1e-3", "--epochs", "40", "--w-jerk", "0.03", "--w-switch", "0.01", "--floor-acc-hinges", "--hard-clip",
        "--contact-tc", "0.006", "--raised-plane", "--w-floor", "1.0"]


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
    sh("m3f_summary.py", str(d))
    sh("m3f_gate.py", str(d))
    return json.loads((d / "gate.json").read_text())["pass"]


def main():
    ok0 = seed(0)
    ok1 = seed(1) if ok0 else None
    (D / "verdict.json").write_text(json.dumps({"seed0": ok0, "seed1": ok1, "pass": bool(ok0 and ok1)}, indent=1))
    mains()
    t = subprocess.run(["taskset", "-c", "0-7", PY, "-m", "unittest", "-v", "test_m3f"], capture_output=True, text=True)
    (D / "unittest.log").write_text(t.stdout + t.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
