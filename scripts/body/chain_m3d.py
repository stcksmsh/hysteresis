"""M3d chain: grid (resume-safe) -> lambda by the rule stated in the night log -> try 1 (held-out) -> try 2 only if try 1 fails -> unit tests. Resume-safe: a step with
its result.json is skipped, an interrupted run resumes from its ckpt.pkl. Try 2 changes ONE engineering setting, named now: the policy learning rate 1e-3 -> 3e-3.
Pass = (a), (b), (c) all pass in the argmax mode (the sampled mode is reported alongside). Writes /secondary/hyst-data/body/m3d/chain.json.
Launched as one detached unit: see chain_m3d.sh."""
import json
import subprocess
import sys
import time
from pathlib import Path

D = Path("/secondary/hyst-data/body/m3d")
LAMS = [0.03, 0.3, 3]


def run(out, lam, epochs, ev, lr):
    if (D / out / "result.json").exists():
        return
    subprocess.run(["taskset", "-c", "0-7", "env", "OMP_NUM_THREADS=8", "/secondary/hyst-env/body/bin/python", "-u", "run_m3d.py", "--out", str(D / out), "--lam", str(lam),
                    "--epochs", str(epochs), "--eval", ev, "--lr", str(lr)], check=False)


def res(out):
    p = D / out / "result.json"
    return json.loads(p.read_text())["result"] if p.exists() else None


def passes(r):
    return bool(r and r["argmax"]["a_pass"] and r["argmax"]["b_pass"] and r["argmax"]["c_pass"])


def main():
    while subprocess.run(["systemctl", "--user", "is-active", "--quiet", "hyst-wo5-m3d-grid"]).returncode == 0:
        time.sleep(30)
    for L in LAMS:
        run(f"grid_{L}", L, 12, "tune", 1e-3)
    cells = {L: res(f"grid_{L}") for L in LAMS if res(f"grid_{L}")}
    ok = {L: r for L, r in cells.items() if r["argmax"]["b_pass"]}
    lam = max(ok, key=lambda L: ok[L]["argmax"]["a_gap_mean"]) if ok else max(cells, key=lambda L: cells[L]["argmax"]["b_rms_nonroll"])
    summary = {"grid": {str(L): {k: r["argmax"][k] for k in ("a_gap_mean", "a_ci", "b_rms_nonroll", "c_p")} for L, r in cells.items()}, "lambda": lam}
    run("try1", lam, 40, "held", 1e-3)
    summary["try1"] = res("try1")
    if not passes(summary["try1"]):
        run("try2", lam, 40, "held", 3e-3)
        summary["try2"] = res("try2")
    summary["verdict"] = "pass" if any(passes(summary.get(t)) for t in ("try1", "try2")) else "fail"
    (D / "chain.json").write_text(json.dumps(summary, indent=1))
    t = subprocess.run(["taskset", "-c", "0-7", "/secondary/hyst-env/body/bin/python", "-m", "unittest", "-v", "test_m3d"], capture_output=True, text=True)
    (D / "unittest.log").write_text(t.stdout + t.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
