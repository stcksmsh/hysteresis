# Builder prompt: work order 48, internal pulse (oscillator bank) + numeric check + flash-check material (7.78 2.1) (2026-11-17)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BRAIN_SPEC.md` **§7.78** (sections 1, 2.1, 2.4, 2.5, 5 and its overseer notes), then 7.77. No motor clock, no
coupling, no A or B change in this work order. No verdict. One arm. Another builder (WO49, A retrain) works on cores 6-13: stay on cores
14-19.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-pulse origin/body`; absolute paths; no new
worktrees. Detached units `hyst-wo48-<fresh>`, `MemoryMax=8G`, `MemorySwapMax=0`, cores 14-19, `python -u`; read logs 1 min after start;
catch errors per item and log names; scan inputs first. Run on battery. Commit and push before every run. Plain commit messages, no
co-author or attribution lines. No installs, downloads, uploads. Env `/secondary/hyst-env/brain`. In (read-only): `/secondary/hyst-data/body/
{t0,t0_phantom,t0_motorica,metric,beatv,controls}/`, the four datasets' audio. Out: `/secondary/hyst-data/body/pulse/`. Motorica stays on
this laptop. Night log `docs/NIGHT_LOG_body-pulse.md`. Keep messages short.

## Read first

`docs/BRAIN_SPEC.md` 7.76-7.78; `docs/BEATV_RULES.md`, `docs/BEATV_REPORT.md`, `docs/BEATV_V4_RESULT.md` (Kosta's flash check and notes);
the ear features (44 columns, onset strength col 40, band-flux 32..39, log-mel bands; `scripts/brain/fast_features.py`, `t1b_cortex.py`);
the arm's joint limits (`make_arm.LIMITS`, `make_arm_v2p.py`); `scripts/body/beatv_clicks_visual.py`.

## The work

1. **Rules note `docs/PULSE_RULES.md`, pushed before any result.** Everything fixed in it:
   - the model: a bank of nonlinear oscillators after Large et al. (gradient-frequency neural network / canonical oscillator model; cite
     the exact paper(s) and equations from the published text, no downloads; if something cannot be reconstructed, say so and state the
     replacement), parameters (alpha, beta1, beta2, epsilon, coupling of the input, time step), 50-100 oscillators log-spaced over 0.5-4 Hz,
     integration method;
   - the drive: onset envelope from the ear features with low-band (kick/rim) weighting (state the weights and bands), causal (no look
     ahead), its normalisation;
   - pulse selection: highest amplitude x a preferred-tempo prior (log-Gaussian, centre ~2 Hz, width stated), restricted to rates the arm can
     move at: derive the maximum pulse rate from the shoulder and base acceleration / speed limits for a stated reference movement (e.g. a
     ±A degree swing per period; state A and the formula); hysteresis / smoothing of the selection (state it) so the pulse is stable
     within a section; pulse phase from the selected oscillator's phase;
   - outputs per song at 100 Hz: pulse rate, phase, amplitude (confidence), selected index; pulse event times (phase zero crossings);
   - the numeric check on the 10 V4 songs (`metric/spotcheck/manifest.json`): pulse vs librosa vs project grid — tempo, metrical level
     (ratio to Kosta's judged level where his notes say it: fd_018 half of librosa), gaps (longest interval without a pulse event),
     local regularity (8-event line residual, as BEATV), persistence through quiet / dropout passages (state how found), tempo following;
     the same summary over all songs of the four datasets (tempo distribution, share below 80 / above 150 BPM-equivalent, longest gap);
   - no per-song tuning; tests: a click train at 120 BPM is tracked at 2 Hz with phase on the clicks; a train with a 4 s silence keeps
     the pulse through it; a 60 BPM kick train with 240 BPM hats picks a level within the arm limit and nearer the prior; a tempo ramp
     100 -> 120 BPM is followed.
2. **Run** on all songs (causal, whole songs), save per-song outputs. `docs/PULSE_REPORT.md`, night log "PULSE READY <commit>".
3. **Flash-check material (prepare, do not serve):** the same 10 songs and the same 30 s excerpts as `beatv/clicks_visual` (same
   rendering: white disc at each pulse event, fade 120 ms, music without clicks), one item per song, plus the librosa versions again as
   blind comparison items (random order, key keeps which). Two questions per item: "Is the flash on the beat?" (yes / partly / no) and "Is
   it the right speed?" (right / too fast / too slow). If `dialstudy_session.py` cannot ask two questions per item, add the smallest
   option that does, with a test. Folder `pulse/flash/`, manifest, night log "PULSE FLASH READY". Then STOP; all tests pass.
