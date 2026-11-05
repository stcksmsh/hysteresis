"""M3e chain (docs/NIGHT_LOG_body-m3e.md items 6-7), one detached unit: lambda grid on the tune episodes (rule stated in the log) -> try 1 (held-out) -> its controls ->
try 2 (ONLY the policy learning rate 1e-3 -> 3e-3) and its controls if try 1 fails the bar -> unit tests. Pass = external (a), (b), (c) in the ARGMAX mode.
Every step waits for mains power (/sys/class/power_supply/ADP1/online = 1) and is skipped when its result file exists; an interrupted run resumes from its ckpt.pkl.
Writes /secondary/hyst-data/body/m3e/chain.json after every step. Launch: chain_m3e.sh.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

D = Path("/secondary/hyst-data/body/m3e")
PY = "/secondary/hyst-env/body/bin/python"
LAMS = [0.03, 0.3, 3]
SUMMARY = {}


def mains():
    while Path("/sys/class/power_supply/ADP1/online").read_text().strip() != "1":
        time.sleep(30)


def sh(*cmd, tries=3):
    for _ in range(tries):
        mains()
        if subprocess.run(["taskset", "-c", "0-7", "env", "OMP_NUM_THREADS=8", PY, "-u", *cmd]).returncode == 0:
            return True
    return False


def run(out, lam, epochs, ev, lr):
    if not (D / out / "result.json").exists():
        sh("run_m3e.py", "--out", str(D / out), "--lam", str(lam), "--epochs", str(epochs), "--eval", ev, "--lr", str(lr))
    p = D / out / "result.json"
    return json.loads(p.read_text())["result"] if p.exists() else None


def controls(out):
    if not (D / out / "controls" / "summary.json").exists():
        sh("m3e_controls.py", "--try", str(D / out))


def passes(r):
    a = r["argmax"]
    return bool(r and a["ext"]["a_pass"] and a["b_pass"] and a["c_pass"])


def save():
    (D / "chain.json").write_text(json.dumps(SUMMARY, indent=1))


def main():
    for L in LAMS:
        run(f"grid_{L}", L, 12, "tune", 1e-3)
    cells = {L: r for L in LAMS if (r := run(f"grid_{L}", L, 12, "tune", 1e-3))}
    ok = {L: r for L, r in cells.items() if r["argmax"]["b_pass"]}
    lam = max(ok, key=lambda L: ok[L]["argmax"]["ext"]["a_gap_mean"]) if ok else max(cells, key=lambda L: cells[L]["argmax"]["b_rms_nonroll"])
    SUMMARY["grid"] = {str(L): {"ext_a": r["argmax"]["ext"]["a_gap_mean"], "int_a": r["argmax"]["int"]["a_gap_mean"], "b": r["argmax"]["b_rms_nonroll"], "c_p": r["argmax"]["c_p"]} for L, r in cells.items()}
    SUMMARY["lambda"] = lam
    save()
    for name, lr in (("try1", 1e-3), ("try2", 3e-3)):
        r = run(name, lam, 40, "held", lr)
        SUMMARY[name] = r
        controls(name)
        SUMMARY[name + "_pass"] = passes(r)
        save()
        if passes(r):
            break
    SUMMARY["verdict"] = "pass" if any(SUMMARY.get(t + "_pass") for t in ("try1", "try2")) else "fail"
    save()
    mains()
    t = subprocess.run(["taskset", "-c", "0-7", PY, "-m", "unittest", "-v", "test_m3e"], capture_output=True, text=True)
    (D / "unittest.log").write_text(t.stdout + t.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
