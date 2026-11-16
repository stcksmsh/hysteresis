# Builder prompt: work order 47, beat-coupling verification V1-V4 (7.77) (2026-11-16)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BRAIN_SPEC.md` **§7.77** (verification V1-V4 and its overseer notes), then 7.76 point 1. Report only: no training. No
verdict. One arm. Another builder (WO45, grammar A training) works on cores 6-13: stay on cores 14-19.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-beatv origin/body`; absolute paths; no new
worktrees. Detached units `hyst-wo47-<fresh>`, `MemoryMax=8G`, `MemorySwapMax=0`, cores 14-19, `python -u`; read logs 1 min after start.
Catch errors per file and log names (as WO46 finally did); scan inputs before any long run. Run on battery. Commit and push before every
run. Plain commit messages, no co-author or attribution lines. **No installs, downloads, uploads** (librosa 0.11+ is in
`/secondary/hyst-env/brain`). In (read-only): `/secondary/hyst-data/body/{t0,metric,controls}/`, FineDance raw data
`/secondary/hyst-data/datasets/finedance/data/finedance/{motion,music_wav}/` (motion: 30 fps, 315 columns = root position 3 + 52 joints x
6D rotation). Out: `/secondary/hyst-data/body/beatv/`. Motorica stays on this laptop. Night log `docs/NIGHT_LOG_body-beatv.md`. Keep
messages short.

## Read first

`docs/BRAIN_SPEC.md` 7.76, 7.77 (with overseer notes); `docs/METRIC_RULES.md`, `docs/METRIC_REPORT.md`, `scripts/body/metric_*.py`;
the overseer's checks `scripts/body/overseer/{gridcheck2,motionbeat,rawbeat}.py` (librosa beats; raw-mocap angular speed from 6D).

## The work

1. **Rules note `docs/BEATV_RULES.md`, pushed before any result.** Everything fixed in it:
   - **V1 local phase locking:** per song, sliding windows of 8 beats (state the hop). In each window the local tempo and phase are
     re-estimated (state how: e.g. a least-squares line through the window's beat times) from (a) the project grid and (b) librosa beats
     (`librosa.beat.beat_track` on the song's audio, parameters stated). Event phase concentration (R) of the WO46 events E1-E5 and E3 yaw
     against the window's fitted beat line, versus shuffled within-window controls (state them). Median over windows and songs; bootstrap
     by song. Material: realised V1 and V2 (`metric/q50`) for all four datasets, plus raw FineDance (step 3's motion energy and minima).
   - **V2 published anchor:** reimplement the beat-alignment score (BAS) from its published definition: Bailando (Siyao et al., CVPR
     2022), as used in the FineDance evaluation (Li et al., ICCV 2023). State the formula, sigma, and how kinematic beats (local minima of
     joint-velocity magnitude) and music beats are obtained, citing the paper section. No code download: if the exact published code is
     needed to match, log "FOR USER: BAS code download needed". Compute BAS on RAW FineDance ground truth (positions from the 6D rotations
     need forward kinematics: if no SMPL-X skeleton offsets are available locally, state that and use the angular-speed proxy, marked as a
     deviation) and on our realised motion (lamp and per joint). Quote the paper's ground-truth BAS for FineDance with its table reference.
     If the raw-data value is far from the published one (state "far" before computing, e.g. outside ±25 %), STOP the other steps and find
     why.
   - **V3 per-file sync (FineDance):** per file, cross-correlation of raw motion energy (whole-body angular speed) with the onset envelope
     over shifts -1..+1 s (state the step). Report the distribution of the best offset and its strength against circularly shifted controls;
     drift = best offset in the first minute vs the last minute.
   - Tests: synthetic motion locked to a known phase gives R near 1 in V1 and the right phase; a known offset is recovered by V3; BAS of
     motion whose minima sit on the beats is near its maximum.
2. **Run V2 and V3 first** (they can invalidate the rest), then V1. Save per-song values. `docs/BEATV_REPORT.md`, night log "BEATV READY
   <commit>".
3. **V4 material (prepare, do not serve):** for the 10 songs of `metric/spotcheck/manifest.json`, a 30 s excerpt each (RMS at or above the
   song's own median, not in the first or last 10 s, per 7.75 Q3) with short clicks mixed at the grid's beat times. Also one version with
   clicks at librosa's beats, presented as separate items in random order (the key keeps which). One manifest of singles for
   `dialstudy_session.py`, question "Are the clicks on the beat?", answers yes / partly / no. Folder `beatv/clicks/`. Night log "CLICKS
   READY". Then STOP; all tests pass.
