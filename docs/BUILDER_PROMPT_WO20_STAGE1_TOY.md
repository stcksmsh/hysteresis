# Builder prompt: work order 20, Stage 1 toy: build it and register its rules; do NOT run the experiment yet (2026-11-08)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below.

**This order builds the Stage 1 toy and writes its rules. The experiment itself runs only after the overseer says "run Stage 1".** It
waits on Stage 0 (work order 19, another builder): if Stage 0 shows the diagnosis is wrong, Stage 1 changes.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub
  server error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:** `src/` and `tools/` are read-only. Never drive hardware. Install nothing. Data stays outside git, under
  `/secondary/hyst-data/`.
- **Long runs** (over 10 min): detached and memory-capped with
  `systemd-run --user --unit=hyst-wo20-<fresh-name> -p MemoryMax=8G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`,
  `python -u`, mains power only.
  - During the build: 3 threads (`taskset -c 12-14`). Work order 19 uses cores 6-11.
  - The real run gets 6-8 threads, when the overseer says.
- **Push** within 30 minutes and after every phase. Log: `docs/NIGHT_LOG_body-s1.md` (MORNING SUMMARY on top).
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-s1 origin/body`, then push `body-s1`.
- **Environment:** `/secondary/hyst-env/body` (jax; differentiable rollouts as in the M3 toys).
- **Data:** `/secondary/hyst-data/body/s1/`.
- **Do not change existing scripts.** Import them; write new files only: `scripts/body/s1_*.py`, tests, `docs/STAGE1_RULES.md`.

## Read first

- `docs/BRAIN_SPEC.md` **§7.34** (binding: the hypothesis, the four cumulative arms (i)-(iv), hinge constraints with dual multipliers in
  every arm, and the pass rule). Also §7.33 (the pass2 verdict: one shape repeated at different speeds).
- `docs/RESEARCH_2026-11-08.md`: §1.2-1.3 (why decoding collapses), §3 Ranks 1-4 (contrastive term, Lipschitz observer, DvD
  determinant, hinge constraints) and §5 Stage 1. Background only; §7.34 wins.
- Existing toys, to reuse the style of observer, decoder and rollout:
  - `scripts/body/m3d*.py`, `m3e*.py`, `m3f*.py`;
  - `docs/NIGHT_LOG_body-m3e.md`, `docs/NIGHT_LOG_body-m3f.md`;
  - the (a) gap definition with time-shifted controls in `m3d.py` / `k5_eval.py`.

## Steps

1. **`docs/STAGE1_RULES.md`: write this FIRST, commit and push it, and tell the overseer before building further.** Fix every
   definition so a reader can recompute the verdict:
   - **Arm:** a 2-link planar arm (link lengths, joint limits, dynamics: kinematic or simple torque; keep it cheap).
   - **Synthetic songs:**
     - N songs (default 64 train / 32 held-out);
     - each song = a slow per-song latent (a 2-D vector, constant or slowly drifting within the song) x a fast beat (tempo drawn from
       90-130 BPM, phase), plus noise;
     - the "music features" the policy sees, and the "state" an observer must decode (a fast stream and a slow stream).
   - **Arm (i), the current objective:** decode an 8-D-like target that is causally z-scored over 30 s within the song, with
     time-shifted-control (a) as in M3d/M3e, plus the hinge constraints.
   - **(ii):** + corpus-level normalisation of the slow stream, and a contrastive music<->motion InfoNCE term (batch of B songs; the
     negatives tempo- and RMS-matched; window length).
   - **(iii):** + a 1-Lipschitz observer (spectral normalisation; the input is a posture metric in metres, i.e. hand position).
   - **(iv):** + -lambda log det K over per-song posture embeddings (RBF kernel; the embedding = a soft hand-position histogram; lambda
     from a small grid fixed in the rules).
   - **Hinge constraints in every arm:** hand speed, jerk envelope, joint-limit margin; dual ascent with a slow multiplier rate. State
     the thresholds.
   - **Measures, on held-out songs:**
     - between-song JS of hand-position distributions (a grid scaled to the toy, base 2, median over pairs, with the half-song control);
     - decoding (a);
     - distinct postures;
     - the machine 2AFC as in §7.34's operationalisation.
   - **Seeds:** 2 per arm. **Budget:** the epochs per arm, and a projected total.
   - **Pass rule, verbatim from §7.34:** (iv) between-song JS >= 3x (i) with decoding >= 0.7; report the smallest arm reaching >= 2x
     (i). Say how two seeds combine (default: both seeds must meet the rule).
2. **Build `s1_toy.py` + tests:**
   - each arm's loss term in isolation (InfoNCE: the correct pair scores highest on a constructed batch);
   - the spectral-norm observer's Lipschitz constant <= 1 (measured);
   - log det K rises when the embeddings spread;
   - the hinges are 0 inside the envelope;
   - a 1-epoch smoke run per arm;
   - time per epoch -> a projection for the full grid.
3. **Push and report to the overseer:** the rules file, the tests, the projection. **Then wait** for "run Stage 1" (watch for a message;
   do not start the experiment by yourself).
4. *(Only after "run Stage 1".)* Run all arms x 2 seeds as one detached unit; write `/secondary/hyst-data/body/s1/summary.json` with
   every measure per arm and seed and the verdict; night log; push; report.

## Done when (this order)

Rules file committed and reported, toy and tests built, smoke runs and projection reported. The experiment runs only on the overseer's
word.
