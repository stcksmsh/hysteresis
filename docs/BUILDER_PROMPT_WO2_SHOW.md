# Builder prompt: work order 2, builder 2, memory and show tracks (H2, brainDump, B7 lanes) (2026-11-04)

You are a builder for Hysteresis. Work alone and unattended. Never wait for input: take the named default and log "FOR USER".

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis`. `git fetch -q origin`, then make your worktree:
  `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-h2show -b body-h2show origin/body`. Work only there.
  Push `body-h2show` after every phase (`git push -u origin body-h2show`; the remote is HTTPS with the gh login). Never touch `body`,
  `keys-decide`, `master` or the main checkout. Builder 1 works in parallel on `body-m1m3` (`scripts/body/`, `train.py`, `core.py`):
  do not edit those files. Put new code in new files where you can; any change to `core_b7.py` goes behind default-off flags, and every
  existing test must pass unchanged.
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. **Version 47 stays byte-identical in `Off`.** If you touch anything the dance
  path reads (`mindState` producers, the compiler), run the check: `bash $D/tracker-scratch/newsong/three.sh TAG`, then cmp the outputs against
  `$D/hexagon-47.html`, `$D/five-years-hexagon.html`, `$D/presence-hexagon.html`
  (`D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm`; a shell guard refuses commands mixing
  `$D` with pipes, `&&`, loops or heredocs, so put such steps in a script file).
- Environment `/secondary/hyst-env/brain` (torch, CPU); install nothing. Data under `/secondary/hyst-data/brain/h2/` and
  `/secondary/hyst-data/brain/braindump/`, outside git (never the root disk).
- **Your share of the machine: 6 threads, 6 GB.** Every run longer than 10 min goes through `scripts/compute/run_job.py`, as a detached
  memory-capped service: `systemd-run --user --unit=hyst-wo2b2-<fresh-name> -p MemoryMax=6G -p MemorySwapMax=0 <script>`. `python -u`. Mains
  power only. No Kaggle in this order.
- Log: `docs/NIGHT_LOG_body-h2show.md`, MORNING SUMMARY on top, updated after every phase.

## Read first

1. `docs/BODY_BRAIN_PLAN.md` (version 2), all of it; your parts are §4, §8, §9, §11. Then `docs/WORK_ORDER_2026-11-04.md` (builder 2 is you).
2. `docs/BRAIN_SPEC.md` §7.1, §7.3, §7.10 (R1 pointer replay, R3 = the T1a + T1b bar), §7.11, §7.12.
3. `docs/NIGHT_LOG.md`: the H1 section (try 1 and 2 numbers, the untrained and oracle results) and the B7 toy section.
4. `scripts/brain/core_b7.py`, `toy_b7.py`, `test_core_b7.py`, `check_b7.py`, `B7_NOTES.md`.
5. `docs/NEXT_DECODER_THEN_BRAIN.md` §2 and its 2026-11-01 note (names: exported JSON and `mindState` use mechanism names only);
   `crates/hyst-compile/src/mind_state.rs`; `scripts/emotion/mind.py`, `mood.py`; `scripts/author/build.py`.

## Overseer's defaults for points the plan leaves open (apply them; they are logged to the planner, not rule changes)

- **D1, self-similarity lane.** The same input and timing as H2's key (fixed random projection of [features pooled over 2 s, L3 + L4 state],
  every 0.5 s, against entries ≥ 17 s old), with no sparsification, so it does not depend on H2. Value = 1 − max cosine. Name it
  "self-similarity" in files; never "novelty" or "recognition".
- **D2, ignition readout.** A layer's phase = the magnitude-weighted circular mean of its 256 mode phases. Coherence = the mean resultant
  length over a 1 s window of each adjacent layer pair's n:m phase difference (n:m = the rounded ratio of the two bands' centre frequencies),
  averaged over the 3 pairs. Threshold = the 99th percentile over 20 training songs (fixed seed for which songs), fixed and committed before
  the danced songs are run. Name it "cross-band coherence" in files; never "ignition" or "awareness". The planner may replace D2; keep the
  code so the definition is one function.

## Phases (the work order's, with its time boxes and defaults)

**Phase 1, H2 toy (two tries, 3 h box each).** Plan §4 exactly: a fixed random projection of [raw features pooled over 2 s, L3 + L4 state] to
2,048 dimensions, top-64 sparsification, L2 normalisation, fixed seed, never trained; one-shot store every 0.5 s; retrieval against entries
≥ 17 s old, top-k 4, a fixed temperature (chosen and logged before the run); CA1 = the B7 pointer replay of the four horizon targets plus
recognition into the relay; only the relay trains. Same three designs, same toy settings and bar as H1 (T1a + T1b). Also run the oracle and
the untrained-H1 baseline on the same toy for comparison. Try 2 may change only k, the sparsity and the temperature, chosen and logged before
the run. Unit tests: no gradient reaches the projection, storage is one-shot, eligibility age, novelty lane every 0.5 s.
Default: H2 fails both tries, so log it; the hippocampus is closed for this plan; continue with phase 2.

**Phase 2, brainDump exporter (≤ 3 h).** Plan §8: a script that runs B7 epoch 6 (`/secondary/hyst-data/brain/b7/ckpt/phase/epoch_006.pt`)
over a song's features and writes at 30 Hz: mode states (4 × 256 complex), per-layer predicted mean and actual target, per-layer surprisal,
arousal, gain and |λ| exponent per layer, the self-similarity lane (D1), the cross-band coherence readout with threshold crossings marked (D2).
Format: float16 `.npz` per song plus a JSON schema. Run it on the three danced songs (Instant Crush, Five Years, Presence; find their
features from the v47 build). Report the size per song. No claims, mechanism names only.

**Phase 3, B7 lanes into `mindState`** for the three danced songs, mechanism names per the 2026-11-01 ruling, so the authoring fallback and the
monitor read B7, not core-2b. `mood.energy` stays from core-2b. The v47 check above must still pass in `Off`.

**Phase 4, if time is left:** a static HTML trace viewer of one brainDump (EEG strip of the four layers, surprisal, arousal, self-similarity,
coherence crossings), synced to the song's audio clock. Plain, fine-line, near-black. A debugging view for the overseer, not the monitor design.
Keep it outside git with the data (the audio must not enter git).

## Finish

Fill the MORNING SUMMARY. Report to the overseer in a few lines:
- H2: T1a and T1b per design and try, oracle and untrained-H1 baselines, unit tests;
- brainDump: size per song, the coherence threshold and the 20 songs it came from, the three songs' files;
- the B7 lanes in `mindState` and the v47 check result;
- FOR USER items; branch, last commit, data paths.

Never say something looks better. No claims beyond what a check passed. Do not edit `docs/BODY_BRAIN_PLAN.md`,
`docs/WORK_ORDER_2026-11-04.md`, `docs/BRAIN_SPEC.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
