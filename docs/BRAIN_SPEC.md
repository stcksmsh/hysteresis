# The brain, B1–B3: spec with checks fixed in advance

Status: **accepted by the user, 2026-10-29** (the user's yes after the corpus ruling, commit 045144b).
Source: the planning agent's answers to the overseer's brief (2026-10-29). The overseer
filled the numbers they left open (marked *overseer*); the planning agent then ruled on
every fill (marked *planner review*, same day), and on the corpus measurements
(marked *corpus ruling*, same day). All of it is proposal, not the user's
ruling, until the user says yes. Where
this file and `NEXT_DECODER_THEN_BRAIN.md` §6 differ, this file wins once accepted.
Rules of `EMOTION.md` and `NEXT_DECODER_THEN_BRAIN.md` §3 hold: every pass/fail rule
is committed before any result it scores; two rounds at most per check; stop at
every ★.

## 0. Shape

- B1 (pulse), B2 (untrained core) and B3 (trained core) are specced together. They
  are built and checked in order B1 → B2 → B3, with a ★ after each.
- The B1 pulse runs outside the core and feeds it. B3 gets pulse phase (cos, sin) and
  amplitude of the readout oscillator as inputs. B3 is reported with and without them
  (ablation, not a gate).
- Code: Python under `scripts/brain/`, with tests beside it. The environment is
  `/secondary/hyst-env/brain` (torch CPU). Data goes under `/secondary/hyst-data/brain/`.
  Nothing lands on the root disk.
- Machine: i7-13700H, 14 cores, 20 threads. Training runs at 8 threads, on training
  nights with the machine otherwise idle (*corpus ruling*). Every rule is in wall time;
  none depends on the thread count.
- Compute cap: B3 training gets 3 nights in total. Past that: stop and report. Do not
  scale the model up.
- *Planner review, a general rule:* wherever a z-score or an SD margin appears, the
  yardstick is the same statistic's own variation at the same scale (not frame noise).

## 1. Shared parts

### 1.1 Fast features (about 44 per frame, 100 Hz, hop 10 ms, full mix only)

- 32 log-mel band energies.
- Half-wave rectified spectral flux on 8 grouped bands.
- Onset strength, RMS, spectral centroid, spectral flatness.
- No chroma, no stems.
- Standardised with statistics from the B3 training corpus, stored with the model.
- *Overseer:* the STFT, the mel range, the 8 band groups and the onset-strength
  formula are fixed in code with tests before any check runs. They are written into
  the B1 entry of `DANCE_HANDOFF.md`.

### 1.2 Slow input

- **Decided by the measurement (2026-10-29): B3 is fast only.** CLAP took 1,452 s per
  audio hour at best (under load). For 200 h that is about 80 h, or about 40 h even at
  half that on an idle machine, against the 20 h limit. No re-measurement. A 2.0 s CLAP
  hop would change the input design and is not taken now.
- Finding, nothing changed: the stage-1 cache grid is 0.5 s, but its CLAP part is
  computed every 2.0 s (`common.EVAL_STEP`, `extract.CLAP_HOP`) and interpolated to the
  0.5 s grid (`check1b.py`). Check 1 was evaluated on a 2 s grid. MERT, Essentia and
  the baseline are at 0.5 s.
- **c-lite** = CLAP (music checkpoint, Apache 2.0) plus the mix-only part of the
  49-dim baseline. No stems, no MERT, no Essentia. No non-commercial model goes inside
  the trained brain.
- **Rule fixed before the measurement:** if CLAP extraction over the chosen corpus
  fits in ≤ 2 nights (*overseer:* 2 × 10 h of wall time on the user's machine), B3 is
  trained with fast + c-lite. Otherwise B3 is fast only, and the report says so.

### 1.3 Test sets (evaluation only; never training, never shipped)

- **B1 gates:** Ballroom, and GTZAN with Marchand's beat annotations.
- **B1 report:** SMC.
- **B3 held-out:** 10 % of the corpus's artists (artist-level split). DEAM and MERP
  are used for the readout pre-check only.
- Every file is hashed. The hash lists are committed before the first check.

### 1.4 Corpus (B3)

- **Source:** FMA (`fma_full`, whole tracks), filtered to CC BY, CC BY-SA, CC0 and
  public domain. Licence strings with NC or ND are out, and so are Free Music Philosophy,
  Art Libre, Sampling Plus, CopyrightPlus, EFF Open Audio, missing licences and the
  other unclear strings (317 tracks). The per-track licence list goes into
  `/secondary/hyst-data/brain/SOURCES.md`.
- **CC BY-SA (corpus ruling, fixed before the split is looked at):** report hours by
  licence within the genre rule. If CC BY + CC0 + PD alone reach 200 h with E/P/R
  ≥ 100 h, CC BY-SA is excluded: whether share-alike reaches trained weights is legally
  unsettled. Otherwise it is included and noted for the exhibition licence check.
- **Access (U1, ruled):** single members are read out of the remote `fma_full` zip by
  HTTP ranges (measured: 206 served, about 125 MB per audio hour, about 0.95 MB/s).
  Fallback if that breaks: another whole-track CC source, with licences read per item
  (Internet Archive netlabels, ccMixter).
- **Not MTG-Jamendo**, because its dataset terms are non-commercial research only.
- **Size: N = 200 h (corpus ruling).** Measured training at 48–66 s per audio hour
  gives an epoch of 2.7–3.7 h; the 3-night cap gives about 8–10 epochs. Download about
  25 GB, about 7 h. If the first real epoch exceeds 4 h on an idle machine, N shrinks by
  the one-epoch rule. Never change the model to fit.
- **Exclusions:**
  - the 138 open FMA IDs that match DEAM by artist and title;
  - then Chromaprint on every fetched file, with a fixed bit-error rate < 0.35 (not the
    vote rule), against all DEAM, MERP and Emotify audio, Ballroom, GTZAN, SMC and the 3
    danced songs.

  Excluding too much is cheap, so the permissive threshold stands. The number excluded
  is reported. The list is committed before training.
- **Size and balance amended (user, 2026-10-30, after the training-side count and
  before download):** electronic, pop and rock (recorded `genre_top`, 60–600 s, training
  side, DEAM IDs out) come to only 89.1 h, so 100 of 200 h cannot be met. N becomes
  2 × the E/P/R training hours that remain after both exclusions (about 178 h), with
  "other" filling the second half. Both "half E/P/R" and the epoch rule then hold. CC
  BY-SA is included by the BY-SA rule (BY + CC0 + PD give 66.1 h of E/P/R). Held-out
  cap 20 h.
- **Balance:** electronic, pop and rock (recorded `genre_top` only) make up at least
  100 of the 200 h. The open pool has 120.2 h of them. Tracks whose genre is only
  inferred from `genres_all` may be used, but count as "other". Pop is thin (6.4 h);
  that is accepted.
- **Split:** 10 % of artists held out.

## 2. B1: pulse

### 2.1 Mechanism

- A Hopf oscillator bank: the GrFNN canonical model of Large, Almonte & Velasco 2010
  (Physica D) and Large et al. 2015 (Front. Syst. Neurosci. 9:159).
- Every parameter value is recorded with its source page. Nothing is tuned on test
  sets.
- Range 0.25–8 Hz, log-spaced. *Overseer:* the density is taken from the source and
  recorded.
- Input: onset strength at 100 Hz from the full mix, plus a low-band flux channel
  below 200 Hz as a kick proxy. *Overseer:* how the two channels combine into the
  bank's input is fixed in code before results. *Planner review:* the bank's input is
  the sum of the two channels, each standardised, with equal weight.
- Baseline: the `hyst-audio` PLL (`BeatTracker`), run through a small Rust example on
  the same audio. It is not re-implemented.
- **Beat readout:** beats are the phase-zero crossings of the strongest oscillator in
  0.5–4 Hz. *Overseer, the hysteresis rule:* the readout switches to another oscillator
  only when its amplitude exceeds the current one's by 20 % for 2 s in a row.

### 2.2 Checks (mir_eval)

Metrics: F-measure at ±70 ms, CMLt, AMLt, tempo error, median phase error in ms.
Intervals are 95 % bootstrap over clips, 2,000 resamples.

- **Gate 1, tracking (non-inferiority; planner review).** The claim "entrains to the
  beat" needs good-enough tracking, not superiority over a dedicated tracker. On
  F-measure and on AMLt, on Ballroom and on GTZAN separately, the lower bound of the
  95 % interval of (B1 − PLL) is ≥ −0.05. All four must hold. Superiority is reported,
  not gated. The offline analysis grid is reported as an upper reference, not a target.
- **Gate 2, holding through gaps.** Synthetic gaps are cut into clips after at least
  10 s of music. They are 2, 4 and 8 s long, of two kinds: silence, and an onset-free
  filler (*planner review:* noise shaped to the average spectrum of the 2 s before the
  gap, with 50 ms crossfades; a low-pass would keep the kick). The gap's onset strength
  must be below 5 % of the clip's median. The gap replaces audio; the beat annotations
  continue through it. Measured at the end of a
  4 s gap, both kinds:
  1. median phase error ≤ 70 ms;
  2. not worse than the PLL coasting: *overseer:* the upper bound of the interval of
     (B1 error − PLL error) ≤ +10 ms;
  3. pulse amplitude ≥ 50 % of its value just before the gap (median over clips).

  The 2 s and 8 s gaps are reported, not gated.

  **Correction (planning agent, passed on by the user, 2026-10-29, before any B1
  result).** A dB-domain onset measure reads any stationary noise at about 0.49,
  whatever its level, so the 5 % onset rule could never pass for the noise kind. It is
  dropped. One verification rule now covers both gap kinds:
  - Signal: the bank's actual input over the gap (summed standardised onset and
    low-band flux).
  - Statistic: the maximum of the mean-removed normalised autocorrelation over lags
    0.25 s to min(2 s, gap length / 2).
  - Null: 1,000 random permutations of the gap's frames, with a fixed seed per clip.
  - A gap is valid if its statistic is at or below the 95th percentile of the permuted
    statistics. A zero-variance gap (silence) is valid by definition.
  - The exclusion rate is reported per kind. A rate well above 5 % means the filler
    carries rhythm, and is reported as such.

  The running z-score has an SD floor (1e-3 of the corpus SD). Both kinds are kept and
  gated as written: silence tests free decay, noise tests phase stability under random
  forcing.

  Measurement definitions:
  - Pulse amplitude (criterion 3): the amplitude of the oscillator that was the readout
    just before the gap, measured at the gap's end.
  - Phase error (criteria 1–2): from the system's beat readout at the gap's end,
    hysteresis rule included.
  - Reported: how often the readout switched oscillator during the gap, per kind.
  - The report states that with α = 0 (critical) the amplitude decays without input;
    with α > 0 the bank would sustain itself and criterion 3 would pass trivially. The
    amplitude result therefore reflects the published α. α is not changed.

  Further fills accepted by the planning agent:
  - The PLL baseline is the better of raw and centred, per gate.
  - The `dance_memory` grid is reported beside `analyze.py`'s.
  - GTZAN exact duplicates are removed (first copy kept), the undecodable file is
    skipped, and near-duplicates and short clips are listed.
  - SMC is recorded as not obtained.
  - GrFNN values come from Velasco & Large 2011, input gain 0.05 from the synthetic
    sweep, cap 0.5 from the singularity bound, all with sources in `GRFNN_PARAMS.md`.
- **Gate 3, meter.** Ballroom style labels give the meter: Waltz and VienneseWaltz are
  triple, the rest duple. Per clip, take the ratio of the mean oscillator amplitude at
  beat/3 to the mean amplitude at beat/2.
  - *Overseer:* beat = B1's own tempo, i.e. the readout oscillator's median frequency.
    The amplitude at a frequency is taken from the nearest oscillator. The ratio with
    the annotated tempo is reported beside it, and so is how often B1's tempo is half
    or double the annotated one.
  - Pass: the ratio separates triple from duple with AUC ≥ 0.75, permutation p < 0.01
    (10,000 label permutations).
- **Reported only:** the missing-pulse stimulus of Large 2015.
- **B1 round 2 (planning agent's rulings, passed on by the user, 2026-10-29, after round
  1: gates 1 and 2 passed, gate 3 failed, AUC 0.720 against 0.75; B1's tempo was
  double the annotated one on 30 % of clips).** It is chosen after results and judged
  on the same sets.
  - Readout score per oscillator in 0.5–4 Hz: S(f) = A(f) · P(f), with
    P(f) = exp(−2·(log2(f / 2 Hz))²). This is Parncutt 1994's pulse-salience curve as
    adapted by Frieler 2004 (t_s = 500 ms); van Noorden & Moelants 1999 give the same
    ~2 Hz resonance. Sources are recorded with page or equation.
  - The readout = argmax S. The hysteresis rule applies to S (switch only when another
    oscillator's S exceeds the current one's by 20 % for 2 s).
  - Gate 3's beat = the new readout's median frequency.
  - Bank, input, gain and cap are unchanged.
  - Gates 1, 2 and 3 all rerun under the new readout with the same rules. Round-1
    passes are not carried over. There is no round 3.
  - Reported: the missing-pulse readout per level; half/double tempo shares per
    Ballroom style; 8 s noise exclusions recomputed after linear detrending of the gap
    signal.
  - Gate 2 on noise: criterion 2 (against the PLL) is reported as not informative,
    because the PLL stops emitting beats in noise. The claim rests on criteria 1 and 3
    there.
- ★ B1: after the checks are committed; after results.
- **If B1 fails twice:** the pulse comes from the offline analysis grid, labelled
  "beat grid" on the monitor, and the B1 claims are dropped.

- **After the two failures (planning agent, accepted by the user, 2026-10-29).**
  - No new pulse step now. The body's pulse stays the offline grid, and the B1 claims
    are dropped.
  - Lessons: octave ambiguity is the core difficulty; the round-2 prior was a planning
    error; α = 0 means decay without input.
  - The round-1 bank may drive the monitor, labelled "an oscillator bank driven by the
    music", with no entrainment claim.
  - A learned pulse inside B3 is reported only, never claimed.
  - B3's pulse input is the grid's phase as cos/sin. It has no amplitude, since the grid
    has none. The ablation is "with / without grid phase".
  - The habituation and splice tests cut at fixed times.

- **Go for B3 training (user, 2026-10-30, 00:2x):** real B3 training may start overnight
  without the user, if all of these hold:
  1. the corpus is complete, with the exclusion lists, hashes and training-side
     standardisation statistics committed;
  2. B3's training and check code (§4.3–§4.6) is committed before any real result and
     verified by the overseer;
  3. the smoke test passes;
  4. the measured epoch time for the corpus is ≤ 4 h.

  Training runs at 8 threads under the 3 × 10 h cap. The checks run on the final
  checkpoint only after training ends.

## 3. B2: untrained oscillatory core

- The B3 architecture (§4.1) with its initialisation and no training. Only readouts
  are fitted (ridge on the same targets as B3's heads).
- It makes no claim. It is the control for B3 (§4.3, §4.4).
- ★ B2: architecture count, parameter number, a smoke run on 3 held-out songs, band
  traces exported. Not gated.

## 4. B3: trained predictive core

### 4.1 Architecture

- Four LRU layers (Orvieto et al. 2023), one per band, with the slow layers on top:

  | Layer | Band | Horizon | Role |
  |---|---|---|---|
  | L1 | 8–20 Hz | +100 ms | fast, "fast" in every text, never "gamma" |
  | L2 | 4–8 Hz | +0.5 s | theta-like |
  | L3 | 0.5–4 Hz | +2 s | "the beat band" in every text; never "meter" |
  | L4 | 0.01–0.5 Hz | +8 s | phrase, section |

- Each layer: a gated MLP, a residual and a layer norm.
- **Init per mode:** λ = exp(−dt/τ + i·2π·f·dt), dt = 0.01 s, f log-uniform within
  the layer's band, τ = Q/(π·f), Q log-uniform in 2–8.
- During training each mode's frequency is clamped to its band. The modulus is free
  below 1.
- Width 128, 256 complex modes per layer, about 1–1.5 M parameters. Counted and
  reported.
- The hierarchy is an objective, not literal error-unit predictive coding. Each
  layer's prediction error is computed and written out.
- **Precision is learned.** Each head predicts a variance; precision = 1/σ².
  *Planner review, the coupling defined:* at step t, layer i receives as an extra input
  layer (i−1)'s prediction error from step t−1, multiplied by the precision layer i
  predicts for it. It is causal, and it is the slow-to-fast gain.
- **Sequences (planner review).** Training uses 60 s chunks with the recurrent state
  carried across chunks (gradients truncated at chunk edges). Evaluation runs whole
  songs with the state carried throughout.
- Seeds are fixed and committed.

### 4.2 Objective

- Each layer's target: the fast (+ slow) features averaged over a window as long as
  its horizon, starting at the horizon's end. *Overseer:* the window is
  [t + h, t + 2h).
- Loss: Gaussian negative log-likelihood on standardised features, summed over the 4
  layers with equal weight.
- **Surprisal** = that negative log-likelihood in nats, per layer and in total.
- **Neuromod lanes** (time constants fixed now):
  - arousal = total surprisal smoothed with rise τ 1 s and decay τ 8 s;
  - tension = L4 predicted variance, τ 8 s;
  - familiarity = minus the least-squares slope of total surprisal over the past 30 s,
    with no further smoothing (*planner review*).

### 4.3 Gate: it learned to predict music

- Held-out artists. B3 is compared with three baselines on the same features and
  horizons:
  - a) persistence;
  - b) linear autoregressive (*planner review:* ridge on the last 1 s at full rate plus
    the last 16 s pooled to 0.5 s steps, one model per horizon);
  - c) B2.
- Each baseline gets a predicted variance fitted on training data, so NLL is
  comparable.
- Pass, both conditions:
  1. per baseline, the 95 % per-song bootstrap interval of (baseline NLL − B3 NLL)
     lies above 0;
  2. B3's mean squared error of the predicted mean is ≥ 5 % below the best baseline's.

  *Overseer, kept by the planner review:* the 5 % margin is on MSE, because a Gaussian
  NLL can be negative, so a percentage of it is undefined. Bits per feature-frame are
  reported, not gated.
- The smoothing control is reported on the mood readouts here and gated in D5.

### 4.4 Check: habituation (a synthetic repeat test; corpus ruling)

It does not depend on `musicalStructure` (mix-only repeats were 0 on the one FMA track
tried).
- Per held-out song, with fixed seeds: a 16 s passage S, and a different 16 s passage
  S' from the same song.
- Version H: … S, then ≥ 30 s of other material from the song, then S …
- Version N: the same, with the first S replaced by S'.
- The second S, the 30 s before it and every cut point are identical in H and N. Only
  whether S was heard earlier differs.
- Cuts fall on B1 beats if B1 passed, otherwise at fixed times. 50 ms crossfades at
  every cut, in both versions.
- Pass, both conditions:
  1. surprisal on the second S is lower in H than in N, with the paired 95 % bootstrap
     interval over songs above 0;
  2. the median drop is ≥ 0.25 × the SD of 8 s window means of total surprisal over the
     song.
- Real repeats from mix-only `musicalStructure`: reported only, with their yield on the
  held-out songs.
- B2 is reported on the same test, as the control for "any memory at all". B2 failing
  it does not affect B3's pass. If B2 passes too, the claim stands, with B2's numbers
  beside it. If B3 beats B2 on the paired drop (interval above 0), that is reported, not
  gated.

### 4.5 Check: surprisal at abrupt change (a splice test)

- Cuts on a B1 beat (*corpus ruling*: not the analysis-chain grid, whose fit was flagged
  unreliable on FMA; fixed times if B1 failed) to a different held-out song, and, as a
  control, cuts within the same song at a matched beat phase. 4 cuts per held-out song, fixed seeds, on a beat, each
  ≥ 35 s from the start and ≥ 10 s from the end (*planner review*).
- z = (mean total surprisal in the 1 s after the cut − mean in the 5 s before) / SD of
  the 1 s window means of total surprisal over the 30 s before the cut (*planner
  review*).
- Pass, both conditions:
  1. z ≥ 3 on ≥ 80 % of the cross-song cuts;
  2. cross-song z exceeds within-song z, with a paired bootstrap interval above 0.
- Reported, not gated: correlation with the analysis chain's novelty peaks, and with
  MERP rating-change size.

### 4.6 Reported only

- Within-song arousal r of the brain-state readouts on DEAM and MERP, against core-2b
  and the matched smoothing control. This is a pre-check; the real body check is D5.
- Phase-amplitude coupling: Tort modulation index, L3/L4 phase against L1/L2
  amplitude, against time-shifted surrogates. It is claimed only if measured above
  the surrogates.
- B3 with and without pulse input.
- ★ B3: after the checks are committed; after results.
- **If B3 fails twice:** core-2b stays the body's source. The brain may drive the
  monitor, labelled "an untrained oscillatory network driven by the music", with no
  B3 claims.

### 4.7 B3 round 2 (planning agent, passed on by the user, 2026-10-31, after round 1)

Round 1 (`DANCE_HANDOFF.md`, "★ B3, after results … (round 1 of 2)") failed 4.3 on the
MSE condition, 4.4 on both conditions and 4.5 on condition 1. Briefs:
`PLANNER_BRIEF_B3_ROUND1.md`, `PLANNER_BRIEF_B3_ROUND2.md`. Fixed before any round-2
code runs.

**One retrain, three changes, each tied to a named cause.** Every gated check is rerun
on it with its committed rule unchanged. A check that fails in round 2 drops its claim;
there is no round 3.
1. **Loss (4.3, mean accuracy).** The Gaussian NLL in training is replaced by β-NLL,
   β = 0.5 (Seitzer et al., ICLR 2022, "On the Pitfalls of Heteroscedastic Uncertainty
   Estimation"). The builder verifies the recommended β in the full text and records the
   page. Cause: plain NLL lets the learned variance absorb error instead of improving
   the mean. Surprisal stays the plain Gaussian NLL of 4.2; β only weights training.
2. **Chunks (4.4, habituation).** 180 s instead of 60 s, state carried, gradient through
   the whole chunk. Cause: 60 s chunks never span the 30–90 s gaps of real repeats. Peak
   RAM is reported. The 1,600-frame target lookahead stays.
3. **Length.** Up to 12 epochs, with early stopping on a validation split of 10 % of the
   training artists (never the held-out ones), patience 2. Seed of the split fixed and
   committed.

Nothing else changes: architecture, heads, precision source, features and checks stay
as committed. The 4.5 bar stays 80 % at z ≥ 3.

**Memory and time, decided by one smoke run before training.**
- Measure peak RAM and time per epoch at 8 streams × 180 s.
- If the peak is ≤ 18 GB and 12 epochs project to ≤ 17 h: run as is.
- Else (a), gradient checkpointing (maths unchanged): if it fits memory and projects to
  ≤ 17 h, run with (a).
- Else (b), 3 streams × 180 s (540 s of audio per step against round 1's 480 s). Add (a)
  on top only if (b) alone exceeds 18 GB. The batch change is recorded as an
  engineering change, not a rule change.
- The 12-epoch cap is never lowered. Hard stop at 20 h of wall time: the best checkpoint
  so far is checked, and the report says the run was cut.

**Early stopping.**
- The checked checkpoint is the best validation epoch; on a tie, the earlier one.
- The selecting score is validation β-NLL summed over the 4 layers (the training loss).
  Nothing gated selects the model. Validation NLL and MSE are logged per epoch and
  reported, never used.

**Same data for every model.** The baselines of 4.3 (persistence and AR variances, AR
weights, B2's readouts) are refit on the same 90 % of training artists as B3. The
standardisation statistics stay as committed (full training side): they are
preprocessing, and the validation artists are not the test set.

**Reported, not gated:** per-layer MSE; per-layer habituation drop; per-layer splice z;
how fast the predicted σ rises after a cut.

**Compute.** Round 2 exceeds the 3-night cap (about 30 h used). Raising it by one run
is the user's decision; the planner recommends yes. *User, 2026-10-31, 19:3x:* the cap is
raised by one run, bounded by the 20 h hard stop above. *User, 2026-11-01, 01:4x, after
the first round-2 epoch (validation only, no gated result), because other CPU-heavy work
shares the machine:* the hard stop is 24 h instead of 20 h. The run resumes from the
epoch-1 checkpoint with `--cap-hours 24`; nothing else changes.

**Ablation.** The no-phase run on the round-1 model is the reported ablation, labelled
"round-1 model". There is no round-2 twin. No claim depends on it.

**PAC control (before any coupling claim).**
- L3 only. The input has no phase in L4's band, and L4 coupling was at chance, so no L4
  claim is possible.
- Input envelopes: each of the 44 input features, band-passed to 8–20 Hz and to 4–8 Hz
  (the network bands' filters), Hilbert envelope. Per song, input MI = the maximum over
  the 44 features of the Tort MI against grid phase. The maximum is deliberately
  conservative.
- Coupling is claimed only if network MI (L3 phase against L1 or L2 amplitude, as in
  round 1) minus input max MI, paired over songs, has a 95 % bootstrap interval above
  0. Same bins, lengths and windows on both sides. Each side's own surrogate result is
  also reported.
- Run now on the round-1 model; it decides the round-1 truth-table line. Round 2's
  result supersedes it.

**Sources of `mindState` lanes under the pivot (pre-check, 4.6).** `mood.energy` stays
from core-2b (MERP r 0.644 against the brain's 0.399). From the brain: surprisal
spikes, neuromod tension and familiarity, band power. The source of each lane is
recorded in `mindState`. Arousal regression from the brain is not used.

**Truth table as of round 1** (supersedes §6 for B3 until round 2 reports).
- Allowed:
  - "Its activity is organised in bands modelled on EEG rhythms." (by construction:
    clamped frequencies);
  - "Its surprisal rises more when the music cuts to a different song than when it cuts
    within the same song (median z 4.8 vs 0.6)." (4.5 condition 2, committed in
    advance);
  - "Trained on 175 hours of Creative Commons music, it assigns higher probability to
    unheard music than a linear model, simple persistence, or an untrained copy of
    itself." (4.3 NLL condition). A partial result; it never becomes "learned to
    predict music" unless 4.3 passes in full;
  - beat-band coupling, only after the PAC control passes.
- Forbidden: learned to predict music; habituates; surprisal rises at abrupt changes
  (the full 4.5 claim); tracks arousal or feeling; entrains, keeps a pulse, meter;
  surprised, expects, remembers, anticipates, feels, conscious.

## 5. `mindState` from the brain (after B3 passes)

- `mood.energy` and `mood.power`: ridge readouts from the brain state (mode magnitudes
  pooled to 2 Hz) to DEAM/MERP arousal and Emotify power. The D2 map is refit (a
  rerun).
- `bands`: power per layer, 10 Hz.
- `pulse`: phase (cos, sin) and amplitude, 100 Hz.
- `surprise`: surprisal per layer and in total, 10 Hz. The field name is kept; the
  meaning is surprisal.
- `neuromod`: arousal, tension, familiarity.
- **The body may read**, each only after its claim has passed: the mood lanes,
  neuromod, pulse amplitude, and surprisal spikes over a threshold fixed before
  results (startle).
- **Monitor only (СИНТЕЗА):** bands, raw surprisal traces, pulse phase. Beat timing for
  the body stays v47's offline grid.

## 6. Truth table claims

- **B1:**
  - "An oscillator bank entrains to the beat of music it has not heard." (absolute F and AMLt printed
    beside it; "tracks the beat accurately" and any claim of published-tracker accuracy
    are forbidden; the body's beat timing comes from v47's grid, not from B1)
  - "It keeps the pulse through 4-second gaps of silence or beatless noise." (absolute
    phase error and amplitude ratio per kind printed beside it)
  - "Its oscillators resonate at the bar, telling triple from duple time."
  - *(All three B1 claims are dropped: B1 failed twice, 2026-10-29.)*
- **B2:** no capacity claim. Allowed wording: "an untrained network of the same shape".
- **B3:**
  - "It learned to predict music from N hours of Creative Commons music."
  - "Its surprisal rises at abrupt changes."
  - "It habituates: its surprisal on a passage drops when it has heard that passage
    earlier in the same song."
  - "Its activity is organised in bands modelled on EEG rhythms."
- **Allowed words:** entrains, surprisal, prediction error, habituates.
- **Forbidden words:** hears, feels the beat, knows the beat, surprised, bored,
  expects, anticipates, remembers, dreams, conscious, feels. "Knows" is reserved for
  "it knows the score" (D4).

## 7. B7: memory, relay, modulation

Decided by the user, 2026-11-01, after B3 round 2. Committed before any B7 code runs.
B3's final rulings and truth table (2026-11-01) stay closed. B7 is a new system with new
checks. Old claims may be re-earned only through B7's own checks. Proprioception is
specced later (§7.8).

### 7.0 Why, per weak spot

- **Habituation was zero.** The core's memory is fading waves, with nothing that stores
  and looks up an episode. → Hippocampus (7.1a).
- **Cut spikes reached z ≥ 3 on only 60 % of cross-song cuts.** No mechanism compares now
  against stored experience. → Hippocampal mismatch, i.e. novelty (7.1a).
- **Short-horizon MSE lost to ridge AR.** Raw input reaches the upper layers and the heads
  only through the layers below. → Thalamic relay (7.1b).
- **The neuromod lanes act on nothing.** → Acting neuromodulation (7.1c).
- **Not addressed, on purpose:**
  - arousal regression and emotion decoding (not the brain's job since the pivot);
  - PAC (a test problem, not an architecture one).

### 7.1 Additions (all causal at runtime)

**7.1a Hippocampus (episodic store, per song).**
- The store resets at song start and carries across chunks within a song.
- **Write**, every 0.5 s. The entry for time t is (key_t, value_t), written at t + 2 s,
  when the value is known.
  - key_t = a learned linear projection (dim 64, then L2-normalised) of the concatenated
    L3 + L4 states (real and imaginary parts, layer-normed).
  - value_t = the 44 fast features averaged over [t, t + 2 s).
- **Read**, every frame.
  - query = a learned projection of the current L3 + L4 state (dim 64, normalised).
  - Cosine similarity against entries at least 8 s old, so there is no trivial copying of
    the recent past.
  - top-k = 4, then a softmax with a learned temperature.
- **Outputs per frame:**
  - retrieved value (similarity-weighted, 44 dims);
  - recognition = the maximum similarity;
  - novelty = 1 − recognition;
  - recall source time = the timestamp of the top-1 entry (for the monitor).
- The retrieved value and recognition feed every layer's input through the relay (7.1b).
- **Gradients:** keys and values within the current chunk get gradients. Entries from
  earlier chunks are detached.

**7.1b Thalamic relay.**
- Every layer's input = the layer below's output + a learned linear projection of [the raw
  44 fast features, grid phase, the hippocampal outputs].
- Every head also gets a linear skip from the current raw features.

**7.1c Acting neuromodulation.**
- arousal_t = the existing lane (rise τ 1 s, decay τ 8 s), computed causally: only from L1
  and L2 surprisal of predictions whose target windows have ended by t. Stop-gradient on
  arousal (it acts as an external modulator).
- It acts per layer, in blocks of 0.5 s, using the arousal value known at the block's
  start:
  - input gain g = 1 + w_g · (arousal − running mean);
  - modulus |λ| → |λ|^(1 + w_τ · (arousal − running mean)), clamped below 1;
  - mode frequencies are unchanged (the band clamps hold).
- w_g and w_τ are learned per layer, zero-initialised.
- Block-sequential, parallel within a block. The slowdown is measured in the smoke run.

### 7.2 Training

- **Warm start** from B3 round 2, epoch 12. All new projections and weights are
  zero-initialised, so B7 at step 0 equals B3 exactly. Verified on 10 held-out songs before
  training: maximum absolute difference < 1e-5.
- **As B3 round 2:** same corpus, splits and validation artists; β-NLL with β = 0.5; 180 s
  chunks; 8 streams; the memory ladder rules of 4.7.
- **Length:** up to 8 epochs. Early stopping on validation β-NLL, patience 2. The best
  validation epoch is checked.
- **Budget:** hard stop at 24 h of wall time (approved by the user).
- **No control run of "B3 trained longer".** The attribution comes from evaluation-time
  ablations (7.4). No B7 claim says "the additions improved prediction over B3".

### 7.3 Toy tests (engineering go/no-go before the long run)

These are not claim gates and not rounds. The code is fixed until they pass.
- **T1, recall.** Synthetic feature sequences with an exact 16 s repeat after a 30 s gap. A
  small model is trained briefly on such data. Pass:
  - prediction error on the repeat ≥ 50 % below that on the first occurrence;
  - recognition during the repeat above the 95th percentile of non-repeat frames.
- **T2, relay.** On a synthetic AR(4) process, the model with relay reaches MSE within 5 %
  of a fitted ridge AR at +100 ms.
- **T3, modulation (unit tests).**
  - With w = 0, outputs are identical to no modulation.
  - With a synthetic arousal step, gain and |λ| change by the designed amounts, and mode
    frequencies stay fixed.
- **Smoke run:** peak RAM and time per epoch, reported before training.

### 7.4 Checks

All fixed now. Held-out: 357 songs, 73 artists. Two rounds at most per check. Ablations
switch modules off at evaluation time, on the same B7 weights.

- **C1, recognition.** The synthetic H = S F S against N = S′ F S construction of 4.4.
  - (a) Mean recognition over the second S is higher in H than in N: paired per-song 95 %
    bootstrap interval above 0.
  - (b) In H, ≥ 50 % of top-1 retrievals during the second S point into the first S.
  - Claim if both pass: "It stores what it hears and recognises a passage when it returns."
- **C2, habituation (new mechanism, B7 only).** The committed rule of 4.4, applied to B7:
  - the drop is ≥ 0.25 × the SD of 8 s window means, with the interval above 0;
  - and with retrieval off, the drop shrinks: the interval of (drop with retrieval − drop
    without) lies above 0.
  - Claim if pass: "It habituates: its surprisal on a passage drops when it has heard that
    passage earlier in the same song."
- **C3, novelty.** The cut construction and z definition of 4.5, applied to the novelty
  signal, not surprisal.
  - Pass: z ≥ 3 on ≥ 80 % of cross-song cuts, and cross − within with a paired interval
    above 0.
  - Claim if pass: "Its novelty signal rises when the music cuts to something it has not
    heard."
  - 4.5 on total surprisal is rerun and reported.
- **C4, modulation acts.**
  - (a) With arousal frozen at its song mean, held-out NLL is worse: interval above 0.
  - (b) The effective time constant of each layer differs between the top and bottom
    arousal quartiles by ≥ 10 % (median over songs), in a consistent direction on ≥ 70 %
    of songs.
  - Claim if pass, stating the measured direction: "Its arousal changes how its network
    runs: when arousal is high, its layers [shorten/lengthen] their memory."
- **C5, prediction.** 4.3 rerun as committed, on B7:
  - the NLL condition against all three baselines;
  - and MSE ≥ 5 % below ridge AR.
  - Claim if pass: "It learned to predict music from 175 hours of Creative Commons music."
  - Each reported: relay off, hippocampus off, modulation frozen.
- **Reported, not gated:**
  - every B3 allowed claim, re-measured on B7;
  - DEAM/MERP arousal r;
  - PAC (still no claim).

### 7.5 Truth words

- **Newly allowed, each only if its check passes:** recognises, stores, habituates, novelty
  signal, arousal changes its dynamics, learned to predict.
- **Still forbidden:** remembers, surprised, expects, anticipates, familiar, dreams, feels,
  conscious, entrains, pulse, meter, coupling.

### 7.6 `mindState` and monitor (after the checks; mechanism names only)

- **New lanes:**
  - `hippo.recognition` and `hippo.novelty` (10 Hz);
  - `hippo.recall_source`, the top-1 entry's time (2 Hz);
  - `neuromod.arousal`, now acting.
- **Monitor idea for B5, no claim needed:** draw an arc from "now" back to the moment it
  recalled from.
- **Authoring:** the authoring tool may use any lane. Lanes whose claim failed keep their
  mechanism name and lose their interpretive one.

### 7.7 Parallel work

- The second builder builds the authoring tool now, per the 2026-11-01 ruling, on B3's
  lanes. The ruling is recorded in `NEXT_DECODER_THEN_BRAIN.md` §2 ("The authoring tool on
  B3's lanes").
- When B7 lands, its lanes are swapped in through `mindState` (same shape).
- There is no dependency in either direction.

### 7.8 Parked, specced later

- **B8, proprioception and efference copy.**
  - Input: the commanded joint angles and velocities, at 100 Hz.
  - A head predicting the next pose; on real servos, also the measured position. This
    gives a self-prediction error lane.
  - It needs the arm in a runtime loop, so it waits for the authoring tool.
- **B4 dreaming:** replay from the hippocampal store in silence. It becomes possible with
  7.1a.
- **Lifetime learning and nightly consolidation.**

### 7.9 Order

1. Toy tests.
2. Smoke run: RAM, speed, and the B7 = B3 identity check.
3. Commit C1–C5.
4. Train.
5. Checks.
6. Report with numbers.

### 7.10 User ruling 2026-11-02, via planner (after the B7 smoke run and toy tests of 2026-11-01)

Binding. It changes how 7.1a, 7.1c, 7.2 and 7.3 are built; the checks C1 to C5 (7.4), the truth words and everything in the B3 record are unchanged.

- **R1. Hippocampus = pointer replay with centred keys.** Per song: a raw buffer of the 44 fast features at 100 Hz, plus keys every 0.5 s.
  Key = a learned projection (dim 64) of [the raw features pooled over the last 2 s, the L3 + L4 state], minus the per-song running mean of keys,
  then L2-normalised. The query is built the same way with its own projection, centred by the same mean. Key and query projections start equal
  and random. Read once per block (2 s), from the previous block's final state: cosine against keys at least 17 s old, top-k 4, learned
  temperature. Value = replay: for each source s_j and each frame t in the block (block start b), per horizon h in {0.1, 0.5, 2, 8 s}, the raw
  features averaged over [s_j + (t - b) + h, s_j + (t - b) + 2h), mixed by the softmax weights. Relay input = the 4 x 44 replayed targets +
  recognition (max similarity) + grid phase + features. Relay, skip, w_g and w_tau are zero at init, so step 0 equals B3.
- **R2. Modulation blocks are 2 s** (was 0.5 s). Arousal as built.
- **R3. T1 is split, both parts required.** T1a, retrieval finds the source: during the repeat at least 50 % of top-1 sources point into the first S
  and recognition is above the 95th percentile of non-repeat frames. T1b, the network uses it: error ratio (repeat / first) <= 0.5 on the
  iid-noise design and <= 0.5 on at least one of the two other designs.
- **R4. T2:** 2,000 steps. If still > 1.05 x ridge AR: add a 10-frame tapped delay of raw features to each head's skip, rerun once. If it still
  fails, keep the relay anyway and log the numbers.
- **R5. Identity:** the float64 maximum difference <= 1e-9 is the criterion; the float32 difference is logged.
- **R6. Training budget:** hard stop 24 h wall time, never more; up to 8 epochs, early stopping on validation beta-NLL with patience 2, best epoch
  kept. If 8 epochs project past 24 h, run anyway.
- **R7.** Per-cut z values are saved in results.json for every check.
- **Fallback (overnight order):** if the toy tests cannot be passed with the hippocampus within their budget, the hippocampus is dropped from B7
  (relay + modulation stay), and C1 to C3 and the "recognises, stores, habituates, novelty signal" words are not claimed.

## 8. Out of this spec

Ignition (cross-band coherence events), B4 dreaming, B5 monitor, B6 staging, B8
proprioception (parked in 7.8).

## 9. Fixed before any result (committed with each check)

- Test sets and their hashes.
- The exclusion list.
- Seeds.
- The artist split.
- The licence filter.
- The compute cap.
- The feature code.
- The GrFNN parameters with their sources.

## 10. Open points

None in the design. U1 (corpus access), U2 (the overseer's fills) and U3 (the two changed
numbers) are ruled above. The user said yes on 2026-10-29.
