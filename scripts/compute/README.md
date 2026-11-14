# scripts/compute: run any job on the laptop, Kaggle, or (with the user's go-ahead) a rented GPU

Plan and rules: `docs/BODY_BRAIN_PLAN.md` §4 (step Z). Stdlib + numpy only. Tests: `cd scripts/compute && python -m unittest -v test_compute`.

| File | What |
|---|---|
| `run_job.py` | Runs one job file: placeholders, wall and idle limits (SIGTERM, grace, SIGKILL), heartbeat, `status.json`, `log.txt`, copies a previous session's checkpoints into `{CKPT}` |
| `manifest.py` | `build` / `verify` SHA-256 manifests for anything that moves between machines |
| `pack_features.py` | Corpus features → a portable folder (float16, relative paths, hashed): the private dataset `hyst-features` |
| `code_snapshot.py` | `git archive` of one commit → the private dataset `hyst-code` (every run is reproducible from a hash) |
| `kaggle/make_kernel.py` | Job file → a Kaggle kernel folder (`kernel-metadata.json` + `run.py`) for `kaggle kernels push` |
| `jobs/*.json` | Job files. `bench_b7.json`, `bench_mjx.json` are the first two (their scripts are written by the builder, plan §4 Z5) |

## A job's contract

- Reads data only from `{DATA}`; writes results only to `{OUT}`; keeps checkpoints only in `{CKPT}`.
- Checkpoints at least every 30 min **and** on SIGTERM, and resumes from `{CKPT}` if a checkpoint is there.
- Touches `progress_file` (or prints) at least once per `idle_limit_s`.
- Writes a small `{OUT}/results.json` that is safe to commit.

## The Kaggle cycle (from the laptop)

```bash
# once: Kaggle account (phone-verified, so kernels may use internet), API token in ~/.kaggle/kaggle.json, `pip install kaggle`
python scripts/compute/pack_features.py --manifest $C/manifest.json --stats $C/feature_stats.npz --out $P/features --slug USER/hyst-features
python scripts/compute/manifest.py verify $P/features
kaggle datasets create -p $P/features            # private by default; later: kaggle datasets version -p $P/features -m "msg"

# per commit you want to run
python scripts/compute/code_snapshot.py --commit HEAD --out $P/code --slug USER/hyst-code
kaggle datasets version -p $P/code -m "$(git rev-parse HEAD)"      # first time: kaggle datasets create -p $P/code

# per job
python scripts/compute/kaggle/make_kernel.py --job scripts/compute/jobs/bench_b7.json --user USER \
    --data-slug USER/hyst-features --out /tmp/kern-bench-b7
kaggle kernels push -p /tmp/kern-bench-b7
kaggle kernels status USER/hyst-job-bench-b7-001
kaggle kernels output USER/hyst-job-bench-b7-001 -p /secondary/hyst-data/runs/bench-b7-001   # status.json, log.txt, results

# a long job across sessions: same job id with a new suffix, attaching the previous kernel's output
python scripts/compute/kaggle/make_kernel.py --job jobs/train_x_002.json --user USER --data-slug USER/hyst-features \
    --prev-kernel USER/hyst-job-train-x-001 --out /tmp/kern-train-x-002
```

To check on first use (not verifiable from outside Kaggle): metadata field names against `kaggle kernels init`; which accelerator `enable_gpu` gives; dataset and saved-output size limits; whether the newest dataset version is attached at push time.
