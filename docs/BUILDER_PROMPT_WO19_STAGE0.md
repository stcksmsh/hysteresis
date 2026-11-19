# Builder prompt: work order 19, Stage 0, measure the one-shape collapse (analysis only) (2026-11-08)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below. **No training in this order.** You measure the pass2 policy and the v47
one-arm reference against pre-registered rules, and report.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub
  server error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:** `src/` and `tools/` are read-only. Never drive hardware. Install nothing. Data stays outside git, under
  `/secondary/hyst-data/`.
- **Long runs** (over 10 min): detached and memory-capped with
  `systemd-run --user --unit=hyst-wo19-<fresh-name> -p MemoryMax=12G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`,
  `python -u`, mains power only (wait on `/sys/class/power_supply/ADP1/online` = 1). Use 6 threads (`taskset -c 6-11`,
  `OMP_NUM_THREADS=6`). Kabl jobs share this machine.
- **Push** within 30 minutes and after every phase. Log: `docs/NIGHT_LOG_body-s0.md` (MORNING SUMMARY on top).
- **Never go idle while a job you depend on runs:** watch it (a Monitor or a background wait loop) so you see it finish.
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-s0 origin/body`, then push `body-s0`.
- **Environments:**
  - `/secondary/hyst-env/body` (jax, MuJoCo) for rollouts;
  - `/secondary/hyst-env/brain` (sklearn, scipy, librosa) for the analysis.
- **Output data:** `/secondary/hyst-data/body/s0/`.
- **Do not change existing scripts.** Import them; write new files only: `scripts/body/s0_*.py` and tests.

## Read first

- `docs/BRAIN_SPEC.md` **§7.34** (binding: the diagnosis, the Stage 0 measures, the pre-registered expectation, and the overseer
  operationalisation at its end, which fixes every definition: grid, JS, dwell, tempo, pairs, classifier, "clearly higher"). Also §7.33
  (pass2 rulings + user verdict 7.33.7).
- `docs/RESEARCH_2026-11-08.md` §5 Stage 0. Background only; §7.34 wins.
- `docs/NIGHT_LOG_body-k5p2.md` (WO18) and `scripts/body/k5p2_eval.py`. Its `songs` step does a continuous full-song argmax rollout and
  writes a 50 Hz joint CSV + npz. Reuse it for every held-out song.
- `scripts/body/m3f_report.py` (`fk_points`, `hand_metrics`), `scripts/body/hf_share.py` (`read_csv`).
- `/secondary/hyst-data/body/k5/splits.json` + `windows.json` (357 check songs), and the B7 lanes in `/secondary/hyst-data/body/k5/lanes/`
  (`omega` = beat-phase rate, rad/s).
- Audio: `/secondary/hyst-data/brain/corpus/audio/<id>.mp3`.
- **v47:**
  - one-arm CSVs for the three danced songs: `/secondary/hyst-data/body/hf/v47/<song>-arm0.csv`;
  - how they were made: `docs/NIGHT_LOG_body-hf.md` (WO13A), `scripts/body/hf_v47.sh`;
  - the v47 export needs a `*.notes.sidecar.json` per song (see `docs/DANCE_HANDOFF.md`, last entries, for the sidecar pipeline).

## Steps

1. **Pass2 on all 357 held-out songs.** Continuous full-song argmax rollout of `/secondary/hyst-data/body/k5p2/run/best.pkl` (round 600).
   Use the same body, options and recipe as k5p2_eval `songs`. Save per song: 50 Hz joint angles, program per block, hand position.
   Resume-safe (skip finished songs). Time 3 songs first and log the projection. Expected about 2 h.
2. **v47 on held-out songs: feasibility first (bounded to 1 h of your effort).**
   - Find out whether the v47 sidecar + score + `hyst score-csv --mode off --agent 0` pipeline runs headless on a new song from its mp3.
   - Measure the time per song.
   - If it is feasible within 6 h of compute: pick 12 tempo-matched pairs (24 held-out songs, rules in §7.34) and export the v47 arm-0
     CSVs.
   - If it is not feasible: log why, use the three danced songs only, and flag the v47 2AFC as weak.
   - **The v47 Rust regression must stay byte-identical** if you build anything (`git diff --stat` on `crates/` must be empty; you should
     not need to touch Rust).
3. **`s0_measure.py` (brain env).** Compute every §7.34 measure per song, for pass2 and v47:
   - JS distance (median over pairs) + the half-song control;
   - distinct postures (>= 0.5 % dwell);
   - shoulder sd;
   - peak hand speed, its across-song sd, and its distance to the hand-speed bound in force in the pass2 loss (find that bound in the code
     and cite the line);
   - program entropy (pass2 only);
   - tempo per song (from `omega`). Sanity check first, on 20 held-out songs: compare the omega-BPM with `librosa.beat.beat_track` on
     the mp3. If they disagree by more than 5 % (after allowing a factor of 2 or 1/2) on more than 4 of the 20, use the librosa tempo for
     all songs, and log it as a deviation;
   - the tempo-matched pairs;
   - the machine 2AFC exactly as operationalised (logistic regression, train on first halves, test on second halves, mean over pairs,
     bootstrap over pairs, label-shuffled control).

   Also report the same 2AFC for pass2 restricted to the v47 subset's pairs, so the two are compared on the same songs.

   Tests: a synthetic case where two "songs" differ only in speed of one fixed shape, and one where they differ in posture; JS and 2AFC
   behave as expected; the shuffled control is ~50 %.
4. **Verdict against the pre-registration:**
   - pass2 2AFC <= 60 %? If **> 60 %**: stop, do not continue, and report: the diagnosis is partly wrong.
   - v47 "clearly higher" (mean >= pass2 + 15 points, and the v47 interval's lower bound > the pass2 mean)?

   Write `/secondary/hyst-data/body/s0/summary.json` and a short table in the night log. Push.
5. **Report to the overseer:**
   - every measure for pass2 and v47, with intervals;
   - the 2AFC verdict;
   - the hand-speed bound and where it is set;
   - v47 feasibility and the number of songs;
   - paths.

## Done when

Rollouts done, measures computed and tested, summary + night log pushed, report sent. Nothing trained.
