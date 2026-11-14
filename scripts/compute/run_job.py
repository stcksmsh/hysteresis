"""Run one job file anywhere (laptop CPU, Kaggle, Modal, a rented GPU) with the same behaviour.

    python run_job.py JOB.json --repo DIR --out DIR --ckpt DIR [--data DIR] [--prev DIR]

A job file is JSON:
    {
      "id": "bench-b7-001",                 required, [A-Za-z0-9._-]
      "cmd": ["python", "-u", "scripts/brain/bench_b7.py", "--out", "{OUT}"],   required
      "cwd": "{REPO}",                      optional, default {REPO}
      "env": {"OMP_NUM_THREADS": "4"},      optional
      "wall_limit_s": 3600,                 required: hard stop
      "idle_limit_s": 1200,                 optional, default 1200: stop if no output and no progress-file change for this long
      "progress_file": "{OUT}/progress.json",  optional: a file the job touches when it makes progress
      "grace_s": 60                         optional: seconds between SIGTERM and SIGKILL (jobs checkpoint on SIGTERM)
    }
Placeholders in cmd, cwd, env values and progress_file: {REPO} {OUT} {CKPT} {DATA} {PREV} {JOB_ID}.

What the runner guarantees:
- OUT/status.json: state (running | done | failed | killed_wall | killed_idle), times, exit code, host, GPU name.
- OUT/heartbeat.json rewritten every 30 s while running (elapsed, seconds since last activity).
- OUT/log.txt: the job's stdout and stderr, interleaved, line-buffered.
- If --prev is given and contains files, they are copied into CKPT before the job starts (resume across sessions).
  A job resumes by looking for its own checkpoint in CKPT; the runner never interprets checkpoints.
- On wall or idle limit: SIGTERM, wait grace_s, then SIGKILL. Exit code of the runner: 0 done, 1 failed, 2 killed.
No third-party dependencies.
"""
import argparse
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

HEARTBEAT_S = 30
ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def gpu_name():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or None if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def substitute(value, mapping):
    if isinstance(value, str):
        for k, v in mapping.items():
            value = value.replace("{" + k + "}", v)
        return value
    if isinstance(value, list):
        return [substitute(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: substitute(v, mapping) for k, v in value.items()}
    return value


def load_job(path):
    job = json.loads(Path(path).read_text())
    for key in ("id", "cmd", "wall_limit_s"):
        if key not in job:
            raise ValueError(f"job file lacks '{key}'")
    if not ID_RE.match(job["id"]):
        raise ValueError(f"bad job id {job['id']!r}")
    if not isinstance(job["cmd"], list) or not job["cmd"]:
        raise ValueError("cmd must be a non-empty list")
    return job


def write_json(path, obj):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2))
    os.replace(tmp, path)


def copy_prev(prev, ckpt):
    prev = Path(prev)
    if not prev.is_dir():
        return 0
    n = 0
    for src in prev.rglob("*"):
        if src.is_file():
            dst = Path(ckpt) / src.relative_to(prev)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(src, dst)
                n += 1
    return n


def run(job, repo, out, ckpt, data="", prev=""):
    out, ckpt = Path(out), Path(ckpt)
    out.mkdir(parents=True, exist_ok=True)
    ckpt.mkdir(parents=True, exist_ok=True)
    mapping = {"REPO": str(repo), "OUT": str(out), "CKPT": str(ckpt), "DATA": str(data or ""),
               "PREV": str(prev or ""), "JOB_ID": job["id"]}
    cmd = substitute(job["cmd"], mapping)
    cwd = substitute(job.get("cwd", "{REPO}"), mapping)
    env = dict(os.environ)
    env.update({k: str(v) for k, v in substitute(job.get("env", {}), mapping).items()})
    env.update({"HYST_OUT": str(out), "HYST_CKPT": str(ckpt), "HYST_DATA": str(data or ""), "HYST_JOB_ID": job["id"],
                "PYTHONUNBUFFERED": "1"})
    progress = substitute(job.get("progress_file", ""), mapping)
    wall = float(job["wall_limit_s"])
    idle = float(job.get("idle_limit_s", 1200))
    grace = float(job.get("grace_s", 60))

    copied = copy_prev(prev, ckpt) if prev else 0
    status = {"id": job["id"], "state": "running", "start": time.time(), "host": socket.gethostname(),
              "gpu": gpu_name(), "cmd": cmd, "copied_from_prev": copied, "commit": job.get("commit")}
    write_json(out / "status.json", status)

    last_activity = [time.time()]
    log = open(out / "log.txt", "a", buffering=1)
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1, start_new_session=True)

    def pump():
        for line in proc.stdout:
            log.write(line)
            last_activity[0] = time.time()

    t = threading.Thread(target=pump, daemon=True)
    t.start()

    killed = None
    last_hb = 0.0
    while proc.poll() is None:
        now = time.time()
        if progress and os.path.exists(progress):
            last_activity[0] = max(last_activity[0], os.path.getmtime(progress))
        elapsed = now - status["start"]
        quiet = now - last_activity[0]
        if now - last_hb >= HEARTBEAT_S:
            write_json(out / "heartbeat.json", {"time": now, "elapsed_s": round(elapsed, 1), "quiet_s": round(quiet, 1)})
            last_hb = now
        if elapsed > wall:
            killed = "killed_wall"
        elif quiet > idle:
            killed = "killed_idle"
        if killed:
            log.write(f"[run_job] {killed}: elapsed {elapsed:.0f} s, quiet {quiet:.0f} s; SIGTERM\n")
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                log.write("[run_job] grace over; SIGKILL\n")
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            break
        time.sleep(0.5)
    proc.wait()
    t.join(timeout=5)
    proc.stdout.close()
    log.close()
    status.update({"end": time.time(), "exit_code": proc.returncode,
                   "state": killed or ("done" if proc.returncode == 0 else "failed")})
    status["wall_s"] = round(status["end"] - status["start"], 1)
    write_json(out / "status.json", status)
    return 0 if status["state"] == "done" else (2 if killed else 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--data", default="")
    ap.add_argument("--prev", default="")
    a = ap.parse_args(argv)
    return run(load_job(a.job), a.repo, a.out, a.ckpt, a.data, a.prev)


if __name__ == "__main__":
    sys.exit(main())
