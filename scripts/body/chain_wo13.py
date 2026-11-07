"""WO13B chain, one detached unit. Stage "grid": the six grid points (jerk weight {0.01, 0.03, 0.1} x switch cost {0.01, 0.05}) on the tune episodes, body v2f, movement switches 2-4
on, lambda 0.03, lr 1e-3, 40 epochs, Trainer seed 0. Stage "main" (run after the selected point is stated in the log): try 1 on the held-out episodes, its WO7 controls, then the four
ablations of movement changes 1-4 (each alone off, selected weights otherwise), then the tests. Waits for mains power before each step; skips finished runs (result.json);
an interrupted run resumes from its ckpt.pkl. Launch: chain_wo13.sh grid | chain_wo13.sh main JERK SWITCH.
"""
import subprocess
import sys
import time
from pathlib import Path

D = Path("/secondary/hyst-data/body/m3f")
PY = "/secondary/hyst-env/body/bin/python"
GRID = [(j, s) for j in (0.01, 0.03, 0.1) for s in (0.01, 0.05)]
COMMON = ["--body", "v2f", "--lam", "0.03", "--lr", "1e-3", "--epochs", "40", "--seed", "0"]


def mains():
    while Path("/sys/class/power_supply/ADP1/online").read_text().strip() != "1":
        time.sleep(30)


def sh(*cmd, tries=3):
    for _ in range(tries):
        mains()
        if subprocess.run(["taskset", "-c", "0-7", "env", "OMP_NUM_THREADS=8", PY, "-u", *cmd]).returncode == 0:
            return True
    return False


def run(name, evalset, jerk, sw, *extra):
    out = D / name
    if not (out / "result.json").exists():
        sh("run_m3f.py", "--out", str(out), "--eval", evalset, "--w-jerk", str(jerk), "--w-switch", str(sw), *COMMON, *extra)


def main():
    stage = sys.argv[1]
    if stage == "grid":
        for j, s in GRID:
            run(f"grid/j{j}_s{s}", "tune", j, s)
        return 0
    j, s = float(sys.argv[2]), float(sys.argv[3])
    run("try1", "held", j, s)
    if not (D / "try1" / "controls" / "summary.json").exists():
        sh("m3f_controls.py", "--try", str(D / "try1"))
    # ablations (report only): each movement change alone off, selected weights otherwise. Movement 1 off = jerk weight 0; 4 off = no crossfade and no switch cost.
    run("abl/m1_no_jerk", "held", 0.0, s)
    run("abl/m2_no_obs_lp", "held", j, s, "--no-obs-lp")
    run("abl/m3_no_phase_lp", "held", j, s, "--no-phase-lp")
    run("abl/m4_no_xfade", "held", j, 0.0, "--no-xfade")
    sh("m3f_summary.py")
    mains()
    t = subprocess.run(["taskset", "-c", "0-7", PY, "-m", "unittest", "-v", "test_m3f"], capture_output=True, text=True)
    (D / "unittest.log").write_text(t.stdout + t.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
