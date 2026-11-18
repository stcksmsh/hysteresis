# Builder prompt: work order 52, movement rhythm vs beat and event responses in human data (7.81 item 4, report only) (2026-11-18)

You are a builder for Hysteresis. Work alone and unattended. Where a choice is open, take the named default and log "FOR USER".

**Binding:** `docs/BRAIN_SPEC.md` **§7.81** (items 1 and 4 and its overseer notes), then 7.73-7.80 and `docs/A_RULES.md` (control
definitions). This is report only: do not change A or B, and train nothing. Give no verdict. One arm. Another builder may use cores 6-13,
so stay on cores 14-19.

**Header rules:**
- Setup: in your current worktree run `git fetch origin && git checkout -b body-rhythm origin/body`. Use absolute paths. Create no new
  worktrees.
- Units:
  - detached `hyst-wo52-<fresh>` units, `MemoryMax=10G`, `MemorySwapMax=0`, `--working-directory=<worktree>`;
  - `taskset -c 14-19` on the worker, `python -u`;
  - make sure the log directory exists before start; read logs 1 min after start; wait with the Monitor tool;
  - catch errors per item and log names; scan inputs first.
- Commit and push before every run.
- Commits: plain messages, with no co-author or attribution lines.
- No installs, downloads or uploads. Environment: `/secondary/hyst-env/brain`.
- Data:
  - In (read-only): `/secondary/hyst-data/body/{t0,t0_phantom,t0_motorica,grammar,controls,pulse,pulse2,metric,beatv,cortexev}/`;
  - Out: `/secondary/hyst-data/body/rhythm/`.
- Night log `docs/NIGHT_LOG_body-rhythm.md`.
- When done, stop every Monitor and background task you started, and send your final report exactly ONCE.

## Read first

- `docs/BRAIN_SPEC.md` 7.73-7.81.
- `docs/A_RULES.md`, which has the per-token controls (vigour, height, sharpness, direction, pause; tokens, windows).
- `docs/BEATV_REPORT.md`, which has the librosa grids and the lamp/joint motion used for BAS.
- `docs/METRIC_*` (beat-phase analysis), `docs/PULSE2_REPORT.md` (pulse v2 outputs per song), `docs/CORTEX_EVENTS_RULES.md` and
  `_REPORT.md` (event detectors, surprisal lanes).
- Code: `scripts/body/grammar_data.py` (human windows, tokens, controls), `controls_stats.py`, `cortexev.py`, `pulse2_lib.py`, the
  beatv scripts.

## The work

1. **Rules note `docs/RHYTHM_EVENTS_RULES.md`, pushed before any result.** It fixes the definitions with numbers.
   - **Movement rhythm:**
     - per window of W s (default 3 s, hop 1 s) of human motion as retargeted to the arm;
     - the dominant period of lamp speed: autocorrelation peak within 0.2-2.5 s; state the detrending and the peak rule. Also joint-velocity
       variants, report only;
     - rhythm strength = the autocorrelation peak height;
     - ratio r = period / beat period, using two beat sources: librosa's local beat period and pulse v2's period;
     - bins: 1/2 when r is in [0.4, 0.6], 1 in [0.8, 1.25], 2 in [1.6, 2.5]; otherwise "other"; "none" when strength < 0.2. State the edges
       and a sensitivity variant.
   - **Event responses per token,** using the existing token grid:
     - hold = pause onset (the pause control crossing up);
     - change = a gesture-family (code 1 family) change, or a posture-knot change beyond a stated distance;
     - burst = a vigour jump > a stated sd within one token.
   - **Music events:**
     - onset peaks (ear col 40, p95 rule);
     - dropout onset and end (low band only, as amended in the WO50 prompt);
     - novelty boundaries (pulse v2's causal novelty detector);
     - cortex surprisal peaks (L2 and total, as in `cortexev.py`).
   - **Analyses:**
     - (A) The distribution of the rhythm ratio per dataset and per beat source: a histogram on a log2 axis plus the bin shares.
       - Chance: the same windows against a beat period from another song with a similar tempo (± 10 %), and against beat periods shuffled
         within the dataset.
       - Clustering measure: the share in {1/2, 1, 2} minus chance; also the circular concentration of log2(r) modulo 1.
       - Bootstrap by song (2,000, seed 52101).
     - (B) The relation of each response (hold, change, burst) to each music event: the event-locked rate at lags −1..+1 s (0.1 s bins)
       against the circularly shifted rate (≥ 100 shifts per song, seed 52102). Peak excess with an interval, bootstrap by song.
   - **Songs:** all human windows used by A (the four datasets), songs under 12 s excluded. Motorica stays local.
2. **Run** and write `docs/RHYTHM_EVENTS_REPORT.md`:
   - tables per dataset and beat source;
   - the event-lock tables;
   - all per-window and per-song values saved under `rhythm/`.

   In the report, state plainly which outcome item 4's rule points to (clusters present or absent), as a number against chance. No verdict
   beyond that.
3. **Tests** on synthetic motion: a sinusoid at the beat period gives r = 1, at twice the period gives 2, noise gives "none", and the event
   lock of a planted response gives the right lag.

Report to the overseer:
- commits;
- paths;
- the headline tables (bin shares vs chance per dataset and source; the top event-lock excesses with lags);
- anything that failed or was skipped;
- every FOR USER item.
