"""WO11 chain, one detached unit: try 1 and A1-A3 retrained with Trainer seed 1 (everything else as WO8/WO9), then m3e_ablate2.py, then the unit tests.
Skips finished runs (result.json); an interrupted run resumes from its ckpt.pkl. Launch: chain_wo11.sh."""
import subprocess
import sys
import time
from pathlib import Path

D = Path("/secondary/hyst-data/body/m3e/seed2")
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
    for n in ("try1", "a1_closed_loop", "a2_gating", "a3_internal"):
        if not (D / n / "result.json").exists():
            sh("run_m3e.py", "--out", str(D / n), "--lam", "0.03", "--epochs", "40", "--eval", "held", "--lr", "1e-3", "--seed", "1", *(["--ablate", n] if n != "try1" else []))
    sh("m3e_ablate2.py")
    mains()
    t = subprocess.run(["taskset", "-c", "0-7", PY, "-m", "unittest", "-v", "test_m3e"], capture_output=True, text=True)
    (D / "unittest.log").write_text(t.stdout + t.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
