# Night log: body-hf (work order 13A)

Provisional servo model (Feetech STS3215 12 V assumed). One arm. Branch `body-hf` from `origin/body` 90607c5, worked in the existing worktree `.claude/worktrees/body-k5video` (overseer's correction: no new worktree). Data outside git: `/secondary/hyst-data/body/hf/`.

## MORNING SUMMARY

All three steps done.

**Step 1.** `scripts/body/hf_share.py` (`hf_share(q_deg, hz)`, `hf_share_csv(path)`) and `scripts/body/test_hf_share.py`, pushed first. Definition as 7.24's operational defaults: velocity = `np.gradient` (central difference, one-sided at the two edge rows) x hz; `scipy.signal.welch`, Hann, 4 s segments, 50 % overlap, `detrend="constant"`; power added over base_yaw, shoulder, elbow, wrist_bend; share = power at f > 3 Hz / power at f > 0 Hz (DC bin excluded). Tests (7, all pass): 1 Hz sine < 0.01; 6 Hz sine > 0.97; 1 Hz + 6 Hz with equal velocity power within 0.05 of 0.5; the roll joint is ignored; mean offset and scale do not change the share; a trajectory under 4 s is refused; CSV round trip.

**Step 2, v47 reference** (`/secondary/hyst-data/body/hf/v47_reference.json`, copy `docs/hf_v47_reference.json`). The v47 Off hexagon scores were compiled with the three commands of `v47_regression.sh` plus `--score`, in a fresh `CARGO_TARGET_DIR=/secondary/hyst-data/cargo-target-wo13`. **The three v47 html files are byte-identical (`cmp`) to `hexagon-47.html`, `five-years-hexagon.html`, `presence-hexagon.html`.** Each of the six arms was exported with `hyst score-csv --mode off --agent N --hz 50`.

| song | six arms (e) | song mean | limit 1.25x |
|---|---|---|---|
| instant-crush | 0.00238, 0.00248, 0.00243, 0.00248, 0.00242, 0.00233 | 0.002419 | 0.003024 |
| five-years | 0.00284, 0.00283, 0.00281, 0.00283, 0.00280, 0.00286 | 0.002828 | 0.003535 |
| presence | 0.00362, 0.00378, 0.00374, 0.00350, 0.00357, 0.00375 | 0.003662 | 0.004577 |

Reference (the toy's) = mean of the three song means = **0.002970**; limit 1.25 x = **0.003712**. (Values are shares, i.e. 0.30 % and 0.37 %.)

**Step 3, report only** (`/secondary/hyst-data/body/hf/report.json`), same measure:
| | instant-crush | five-years | presence | mean |
|---|---|---|---|---|
| K5 try 1 (`danced/<song>.k5.csv`) | 0.002447 | 0.003150 | 0.002383 | 0.002660 |
| fallback (authoring tool, example-sketch, `--body layered --clock music`, `hyst score-csv --mode layered`, one arm) | 0.001812 | 0.001156 | 0.002471 | 0.001813 |
The fallback CSVs were made from the sidecars `retune.sh` built (`tuning/work/<song>-example-sketch.sidecar.json`). Against the v47 limit 0.003712: K5 try 1's three values and its mean, and the fallback's, are all below it (a comparison of numbers, not a claim about movement).

**Scripts**: `hf_v47.sh` (compile, cmp, per-arm export), `hf_fallback.sh`, `hf_reference.py` (`v47 --docs`, `report`). Logs under `/secondary/hyst-data/body/hf/`.

**Deviations**: none from the order except the worktree (overseer's correction). **FOR USER**: none.
