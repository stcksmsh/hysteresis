"""WO14A chain, one detached unit: toy try 1 rerun with the floor-margin and hand-acceleration hinges (weight 1 each) and the hard joint clip (BRAIN_SPEC 7.27), at WO13B's selected point
(jerk 0.03, switch 0.01), seed 0, body v2f, held-out episodes; then the WO7 controls (untrained, kappa = 0), the summary and the tests. Output /secondary/hyst-data/body/m3f/rerun1/.
Waits for mains power before each step; skips finished steps; an interrupted run resumes from its ckpt.pkl. Launch: chain_wo14.sh.
"""
import subprocess
import sys
import time
from pathlib import Path

D = Path("/secondary/hyst-data/body/m3f/rerun1")
PY = "/secondary/hyst-env/body/bin/python"


def mains():
    while Path("/sys/class/power_supply/ADP1/online").read_text().strip() != "1":
        time.sleep(30)


def sh(*cmd, tries=3):
    for _ in range(tries):
        mains()
        if subprocess.run(["taskset", "-c", "0-7", "env", "OMP_NUM_THREADS=8", PY, "-u", *cmd]).returncode == 0:
            return True
    return False


def main():
    if not (D / "try1" / "result.json").exists():
        sh("run_m3f.py", "--out", str(D / "try1"), "--eval", "held", "--body", "v2f", "--lam", "0.03", "--lr", "1e-3", "--epochs", "40", "--seed", "0", "--w-jerk", "0.03", "--w-switch", "0.01",
           "--floor-acc-hinges", "--hard-clip")
    if not (D / "try1" / "controls" / "summary.json").exists():
        sh("m3f_controls.py", "--try", str(D / "try1"))
    sh("m3f_summary.py", str(D))
    mains()
    t = subprocess.run(["taskset", "-c", "0-7", PY, "-m", "unittest", "-v", "test_m3f"], capture_output=True, text=True)
    (D / "unittest.log").write_text(t.stdout + t.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
