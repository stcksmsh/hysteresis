"""WO9 chain, one detached unit: Part 1 (m3e_cb60.py) -> stop if the cerebellum error grows (verdict.json) -> Part 2: three ablation runs (run_m3e.py --ablate) -> m3e_ablate.py
-> unit tests. Waits for mains power before each step; skips finished steps (result files); an interrupted run resumes from its ckpt.pkl. Launch: chain_wo9.sh."""
import json
import subprocess
import sys
import time
from pathlib import Path

D = Path("/secondary/hyst-data/body/m3e")
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
    if not (D / "cb60" / "verdict.json").exists():
        sh("m3e_cb60.py")
    if json.loads((D / "cb60" / "verdict.json").read_text())["grows"]:
        print("cerebellum error grows over 60 s: Part 2 not run, waiting for a ruling", flush=True)
        return 0
    for n in ("a1_closed_loop", "a2_gating", "a3_internal"):
        if not (D / "ablations" / n / "result.json").exists():
            sh("run_m3e.py", "--out", str(D / "ablations" / n), "--lam", "0.03", "--epochs", "40", "--eval", "held", "--lr", "1e-3", "--ablate", n)
    sh("m3e_ablate.py")
    mains()
    t = subprocess.run(["taskset", "-c", "0-7", PY, "-m", "unittest", "-v", "test_m3e"], capture_output=True, text=True)
    (D / "ablations" / "unittest.log").write_text(t.stdout + t.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
