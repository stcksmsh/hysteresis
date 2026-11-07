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

### 7.11 B7 close-out: user ruling 2026-11-03, via planner (after B7 round 1)

Binding. Recorded from `docs/BODY_BRAIN_PLAN.md` §2, which is the work order from here on.

1. Round 2 is not taken. **B7 epoch 6 is the cortex of record** and the source of every brain lane in `mindState`. C4 and C5 round-2
   rights are recorded as "not taken", not as failed twice.
2. C5 is unchanged (round 1: MSE ratio 1.041 against ridge AR, needs <= 0.95; fail). For the record, the warm start restarted the learning
   rate at about 9x B3's final rate. **Rule for every future warm start:** constant learning rate at the source run's final rate, or a
   warm-up of <= 200 steps to it.
3. C4(b): "one common direction across all four layers" is the correct reading and stays (fail). The per-layer directions are reported as
   data (L1 +36 %, L2 -29 %, L3 -8 %, L4 -12 %; 99.4 % same sign) and may appear on the monitor as numbers.
4. The hippocampus is not in B7. It continues as toy step H1 (`BODY_BRAIN_PLAN.md` §5).
5. Backlog: the unexplained step-2 memory growth; long runs on mains power only.
6. Truth table for B7: `BODY_BRAIN_PLAN.md` §10.

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

### 7.12 Rulings of 2026-11-04, via planner (after step Z, M0, M2 and H1)

Binding. Recorded from `docs/BODY_BRAIN_PLAN.md` version 2, §2, which replaces version 1 in full.

- Implement for M0 and later: the mirror ball. Continuous joints (base yaw, wrist roll): amplitude cap ±180°.
- The B7 lane export comes with the monitor work (plan §8). Checks stay on CPU.
- Servo values stay provisional (Feetech STS3215 12 V; kp, rotor inertia, damping 1.5, acceleration share 0.25), and every body result states them.
- A Kaggle job verifies the whole `hyst-features` upload.
- K4 is fixed as in plan §6 (paired runs per song, 8 s windows, d_diff − d_same).
- The self-similarity data lane (plan §8) is allowed with no claim.
- H1 is confirmed off. M4 (H1-based) is dropped. The hippocampus continues only as H2 (plan §4).

### 7.13 Rulings on the plan v2 check, 2026-11-04, via planner

Binding. They answer `docs/PLANNER_BRIEF_PLAN_V2_CHECK.md`.

1. Accepted: the cerebellum's command is the servo target (joint angles at 100 Hz) in every set; efference copy = the last 10 targets
   (100 ms). In M3 the policy's commands pass through the generators, and the cerebellum still sees targets.
2. Changed: all 18 v47 trajectories (6 arms x 3 songs) are used, split into 60 s segments. Bootstrap at two levels: arms within song, then
   segments within arm, with the 3 songs held fixed (not resampled); 10,000 resamples. The report states that the interval is conditional on
   these three songs, and that arms in unison or mirrored formations are near-duplicates.
3. Accepted: 120 independent 60 s held-out babbling trajectories, bootstrap over trajectories, 10,000 resamples.
4. Accepted: builder 1 runs the Kaggle verify job first.
5. Changed, ignition readout (a data lane, no claim):
   - per layer, the magnitude-weighted Kuramoto order parameter of its 256 mode phases, computed at 100 Hz and averaged over 1 s windows
     (stepped every 0.1 s);
   - per layer, a threshold = its 99th percentile over 20 training songs, fixed before the danced songs run;
   - a crossing = at least 3 of the 4 layers above their own threshold in the same window.
   No n:m cross-band phase comparisons. Export the four order parameters and the crossing marks.
6. Accepted: the self-similarity lane uses H2's input and timing with no sparsification, so it does not depend on H2 passing.
7. Accepted: the M3 benchmark reports the largest environment count that fits the cap.
8. Accepted: `docs/NIGHT_LOG_<branch>.md` per builder; `BODY_BRAIN_PLAN.md` §11 reads accordingly.

### 7.14 Rulings on work order 2, 2026-11-04, via planner

Binding. They answer `docs/PLANNER_BRIEF_WO2_RESULTS.md`.

1. **Self-surprisal lane:** exported from the K1 round-2 bundle as a mechanism-named data lane ("cerebellum: prediction error of its own
   arm"). No claim. Record for K1: the v47 out-of-distribution set contained targets the M0 servos cannot follow (up to 10° RMS of limiter
   change). That is a flaw in the check's design (the planner's), not a reason to rerun. K1 stays failed and its claim forbidden. The cerebellum
   stays usable as a mechanism (babbling passes).
2. **M3 is closed by the rule. A new plan item, M3b, is opened.** The diagnosis names three design flaws:
   - (a) was hackable: S_still came from relay weights trained only on moving input, so stillness was out of distribution (the control: about
     85 % of (a) did not depend on timing);
   - the wrist roll moves no point of the chain, so it was the cheapest way to "move";
   - selection collapsed (2 programs, entropy 0.034 nats).

   M3b changes, fixed now:
   - Reward: r = (S_shifted − S_moving) + β·LP − λ·E, where S_shifted = the cortex fed the same episode's proprioception shifted by a random
     2–8 s (fixed seeds). Only timing-relevant movement pays. No S_still anywhere.
   - The roll is excluded from (b), from the dominant joint in (c) and K3, and from the proprioception into the cortex relay. It still costs
     energy, and the cerebellum still sees it.
   - Selection: an entropy bonus on the program choice (weight from the toy grid), plus a report of programs used. The pass adds (d): at least
     4 programs, each chosen in ≥ 5 % of decisions.
   - Toy bar = T-M3 (a)–(c), with (a) on the new reward, plus (d). Two tries, 4 h box each. The grid (β, λ, c_sw, entropy weight) runs on the
     toy only.
   - The 2 s block staleness is parked until a real run.

   If M3b fails twice, the self-driven body is closed for this plan and the fallback drives the arm.
3. Parked with M3b (above).
4. **Ignition lane:** show the four per-layer synchrony traces (magnitude-weighted order parameters) as continuous data; drop the crossing
   marks. Finding recorded: no 3-of-4 co-synchronisation above the per-layer 99th percentile on 20 training songs or on the 3 danced songs.
   No thresholds are tuned to make events appear.
5. **`mindState` version 2:** yes, with the monitor build. v47 byte-identical in `Off`.
6. **Next work order, two builders.** Builder 1: the M3b toy, unattended template. Builder 2: the fallback, minimal (the authoring tool on B7
   lanes for the three danced songs, plus the self-surprisal export, so a watchable arm exists whatever M3b does); then `mindState` v2;
   `manifest.py` skips `dataset-metadata.json`. The monitor build waits for the user's choice of mockup.

### 7.15 Change of direction, user, 2026-11-04 (via planner)

Binding. It replaces M3b (§7.14 point 2) and adds H3. Builder 2's fallback order (§7.14 point 6) stands, plus previz videos for the user, so a
watchable arm exists either way.

**Principle.** Stop literal brain mimicry where it blocks learning. Build mechanisms in; train only small, well-defined parts.

**H3 (memory), new plan item, toy only first.**
- Keep H2's fixed sparse random code and one-shot store (untrained H2 passes T1a on all three designs).
- The hippocampus makes its own prediction: the replayed horizon targets from the top-k sources (the oracle path, which passes T1b).
- Final prediction per layer = a blend of cortex and hippocampus: w = sigmoid(a·(recognition − b)); mean = (1 − w)·cortex + w·replay; the
  variance blended likewise. Only a and b are trained, per layer. The cortex is unchanged. After kNN-LM (Khandelwal et al. 2020); verify the
  citation before any public use.
- Toy bar: T1a + T1b as before (§7.10 R3); two tries, 3 h box each.
- If it passes: C1–C3 round 1 on held-out songs with B7 epoch 6 + H3 (no cortex retrain).

**M3c (learning to move), replaces M3b.**
- Reward: r = legibility − λ·E. Legibility = −loss of an observer network that decodes the brain's inner state (arousal, total surprisal, L3
  phase as cos/sin, per-layer band power, smoothed to 0.5 s) from the arm's movement alone, through the 37 body-study descriptors over a
  sliding 2 s window, excluding the wrist roll. The observer trains alongside (as in GAIL-style setups), on training songs only.
- Kept: basal ganglia selection among 8 programs with the entropy bonus and (d); dopamine δ; the cerebellum's LP as an optional term (the grid
  includes β = 0); spinal generators with a phase coupling to L3 (κ set by the motor cortex; κ = 0 recovers the old generators).
- Toy (two tries, 4 h box each), synthetic features. Pass: (a) observer decoding on held-out toy episodes beats a song-shuffled control,
  interval above 0; (b) RMS joint speed ≥ 10 °/s excluding the roll; (c) at least 4 programs, each chosen in ≥ 5 % of decisions.
- Real-run claims, checks fixed before results:
  - **K5** "Its inner state can be read from its movement": held-out-song decoding above a shuffled control, per-song bootstrap interval above 0.
  - **K4** as ruled (§7.12 / plan §6).
  - **K3** "Its movement locks to the beat": reported, not required.
- Wall wording: "It was rewarded for movement that shows what is inside it. Nobody designed how it moves."
- **Retired:** the M3 and M3b reward designs. Their premise (prediction gain) fails because the cortex does not need a body to predict.

### 7.16 Rulings on work order 4, 2026-11-04, via planner

Binding. They answer `docs/PLANNER_BRIEF_WO4_RESULTS.md`.

1. **Re-evaluation with sampled selection** is allowed as a measurement fix: no retraining, nothing tuned; both versions reported; both rounds
   stand; no pass is claimed from it. Every M3-family policy also reports the mutual information between the chosen program and the brain state
   (binned arousal and L3 phase), with a shuffle control. Near-uniform choice is not selection. **Recorded evaluation bug:** `tm3.py`
   `evaluate()` used argmax over near-flat logits (`deterministic=True`), so the reported program counts, (d) and "selection collapse" described
   the argmax, not the trained, sampled policy.
2. **M3c is closed as defined (two tries).** New, final item for the self-driven body, **M3d**:
   - Training by gradient, not RL: brain state → motor cortex → program mixture (Gumbel-softmax, temperature annealed) + modulation →
     generators (with the L3 phase coupling) → MJX physics → descriptors (ported to JAX; parity test with Rust) → observer.
   - Loss = observer decoding loss − λ·energy, with the inner-state targets z-scored within each episode (decode moment-to-moment changes, not
     song identity).
   - The observer is cross-fitted: trained on other episodes, frozen while it scores, refreshed each epoch.
   - Toy: synthetic features with within-song state swings (cuts every 12 s; arousal and surprisal varying on a 1–4 s scale), so there is
     something to read.
   - Pass: (a) held-out-episode decoding beats a time-shuffled control, interval above 0; (b) RMS joint speed ≥ 10 °/s excluding the roll;
     (c) program choice carries information about the state: MI above shuffle, p < 0.01.
   - Two tries, 4 h box each. If M3d fails, the self-driven body is closed for this plan and the fallback mapping drives the arm for good.
3. **H3 is closed.** New, final memory item, **H4**: uncertainty-based arbitration (after Daw, Niv & Dayan 2005; verify the citation).
   - Per layer, each system (cortex, hippocampal replay) keeps a running mean squared prediction error over the last 1 s (fixed; try 2 may
     change only this window, to 2 s).
   - w = (1/e_hippo) / (1/e_hippo + 1/e_cortex); mean and variance blended as in H3.
   - Nothing trained. H2's fixed sparse code and one-shot store; top-k pointer replay as before.
   - Toy bar unchanged (T1a + T1b). If H4 fails, memory is closed for this plan.
4. **Priority tonight:** the fallback order (authoring on B7 lanes + previz videos of the three songs) has priority on the machine; the M3d and H4
   toys run after it, or in parallel within the thread caps.

### 7.17 Rulings on work order 5, 2026-11-05, via planner

Binding. They answer `docs/PLANNER_BRIEF_WO5_RESULTS.md`.

1. **H4: one diagnostic, no new try.**
   - Check the retrieval top-k actually used against the spec: top-k = 4 sources. "k 64" is the sparse-code k, not the number of replayed
     sources.
   - Report, inside the repeat, the replay's own prediction error against the oracle replay's error, on the same frames.
   - Explain the 1.000 cortex-only control (repeat and first errors identical on every design suggests a runner bug; H3's cortex-only control on
     the same cortex files gave 0.881 | 0.656 | 0.566).
   - If an implementation deviates from the spec, fix it and rerun; that rerun counts as the same try (bugs are not tries). If nothing deviates,
     memory is closed for this plan, with the discrepancy recorded.
2. **M3d:** a run killed for memory before any result is not a try. Relaunch with 3 runs × 6 GB; the 4 h box counts compute actually spent.
3. **Sampled re-evaluation:** nothing reopens; both evaluation modes are recorded (table in the WO5 brief §1).
4. **Fallback, next step (corrected by the user, 2026-11-05; supersedes the planner's first wording, which asked for six-arm hexagon wiring):**
   the installation is ONE arm. No hexagon, no six-arm wiring; the ensemble is out of scope for good. The user judges the one-arm videos and
   tunes the mapping by eye in the authoring tool; the builder supports that loop with a fast re-render of a whole song or of a 20 s window
   from the current mapping. Version 47 `Off` stays byte-identical. Ensemble items are removed from the plan's later lists
   (`docs/BODY_BRAIN_PLAN.md` §10).
5. **Self-surprisal** is offered in the authoring tool as a mechanism-named lane ("cerebellum: prediction error of its own arm"), no claim.
6. **mindState v2 grouping** (bands / surprise / neuromod) is accepted.

### 7.18 Rulings on work order 6, 2026-11-05, via planner

Binding. They answer `docs/PLANNER_BRIEF_WO6_RESULTS.md`.

1. **M3d controls, report only** (same 16 held-out episodes, same observer procedure, no retraining, not a try):
   (i) untrained motor cortex (initial weights, kappa as initialised); (ii) trained motor cortex with kappa forced to 0; (iii) untrained motor
   cortex with kappa fixed at the trained per-joint means (isolates the phase coupling). Report (a), (b), (c) for each, plus
   (a)_trained − (a)_control with a paired interval. The toy pass stands as written.
   **Recorded design flaw (planner's):** the M3d toy bar could be met by any state-driven mapping.
2. **The real M3d run (K5), fixed now, before it starts; it starts after the controls of point 1:**
   - State: B7 epoch 6 lanes on training-artist songs; held-out songs for the check; the three danced songs for the user's eye.
   - **K5 passes only if** held-out decoding beats BOTH the time-shifted control AND the untrained-policy control (paired per-song bootstrap
     intervals above 0).
   - The claim "it learned to move so that its inner state can be read from its body" needs both. If it beats only the shifted control, the
     allowed wording is "its movement is driven by its inner state", with no "learned".
   - Before training: an MJX one-iteration vs full-MuJoCo parity check on 60 s trajectories (report the joint differences).
   - The fallback mapping's videos are kept as the comparison for the user's eye.
3. **Memory is closed for this plan;** nothing from H1–H4 joins the arm. Corrected baselines: the true cortex-only control is 1.000 for H3 and
   H4 (H3's reported 0.881 | 0.656 | 0.566 was a 50 % blend, mislabelled). The H4 diagnostic shows retrieval replaying wrong sources, so the
   partial ratio drops are mostly averaging two noisy predictors, not recall.
4. **Design fix:** camera framing. In Presence at 110 s the hand leaves the top edge of the view; widen or re-aim the camera for all renders.

### 7.19 Rulings and next order, 2026-11-05 (user + planner)

Binding. They answer `docs/PLANNER_BRIEF_WO7_RESULTS.md`. Build in the order given.

**Goal (user):** a scale human, one arm. The brain's own encodings drive it (no emotion decoding). It learns to move so that its inner state
can be read from its body. Every mechanism shown or claimed must be in the loop that moves the arm, or be a labelled data lane.

**A. Rulings on the WO7 brief**
1. K5 bar as in 7.18 point 2 (beat both the time-shifted and the untrained-policy control). Wording rule: any "moves in time with its inner
   rhythm" / phase-locking wording only if the trained policy also beats the kappa = 0 version, paired interval above 0, in the mode that runs.
2. Mode, chosen by the user before any K5 result: **ARGMAX** (steady, state-driven selection). Every claim applies to argmax; sampled is
   reported only. Reason: in the toy, argmax choice carries about 10× more information about the inner state (MI 0.536 vs 0.055 nats);
   near-random switching reads as noise.
3. K5 size: training on all training-artist songs except the validation artists (no held-out artist in training or tuning); 60 s windows; B7
   epoch-6 lanes as the state. Check on all 357 held-out songs, three 60 s windows per song (starting at 25 %, 50 %, 75 %), per-song paired
   bootstrap, 10,000 resamples. Two tries, 8 h box each, laptop; Kaggle via run_job if the projection exceeds 8 h.
4. Every K5 number (trained and controls) uses the WO7 controls' observer procedure (fresh observer per scored policy, hard rollouts of the
   fixed policy). Try 1's warm-started (a) = 0.480 is superseded.

**B. Changes before the real run** (they change training, so first ONE toy rerun under the same toy bar, two tries, with the WO7 controls
reported again)
1. Closed loop: the motor cortex also receives proprioception (quantised, delayed 10 ms, roll included) and the cerebellum's predicted pose and
   prediction error (K1 round-2 bundle, frozen). Zero-initialised input weights.
2. Dopamine made real: a critic predicts the next 2 s of legibility from the motor cortex's input; δ = realised − predicted. |δ| scales the
   learning rate of the basal-ganglia selection parameters: base rate × (0.5 + clip(|δ|/σ_δ, 0, 2)), σ_δ a running SD. Export δ as the
   dopamine lane. If this cannot be built cleanly, dopamine is removed from the monitor and the story.
3. Causal normalisation: all inner-state inputs and targets z-scored with running statistics over the past 30 s. No whole-episode statistics
   anywhere in the arm's loop.
4. Self-observer: a second observer inside the brain decodes the same inner-state targets from proprioception alone (quantised, delayed, roll
   included), cross-fitted like the external one (which sees the 31 visible descriptors, no roll). Loss = external decoding loss + internal
   decoding loss − λ·energy, equal weights, fixed now. Report both decodings and the WO7 controls for each.

**C. Real run (after the toy rerun passes)**
- As in A.3. The three danced songs rendered with the new camera, next to the fallback videos, for the user's eye.
- Claims:
  - external and internal both pass K5: "It learned to move so that both it and you can read its inner state from its body."
  - only the external passes: "It learned to move so that its inner state can be read from its body."
  - beats only the shifted control: "Its movement is driven by its inner state" (no "learned").
- If the toy rerun or the real run fails twice: the authoring fallback drives the arm for good.

**D. Standing**
- Dropped and closed: hippocampus (H1–H4), B1 pulse, M3/M3b (prediction-gain reward), emotion decoding as driver, ignition events, the ensemble.
- Data lanes only (labelled, no claim): self-similarity, self-surprisal, per-layer synchrony.
- The monitor shows only mechanisms in the loop plus labelled data lanes.
- Provisional servo model stated in every body result. No spending. No attribution lines.

### 7.20 Rulings on work order 8, 2026-11-05, via planner

Binding. They answer `docs/PLANNER_BRIEF_WO8_RESULTS.md`. Set before any K5 result.

1. **K5 compute:** no deliberately reduced try. One try = one full pass over the 15,624 training windows (early stopping on validation
   allowed); compute box 24 h, counted as compute actually spent, resumable across sessions. This replaces the 8 h box of §7.19 A3.
   Path: first a short Kaggle check (JAX GPU + MJX import, steps per second on a K5 window batch). If Kaggle projects faster than the laptop,
   run there via run_job (free tier only); otherwise the laptop over several nights with checkpoint resume, on mains power.
2. **Report-only toy ablations:** small copies retrained with one mechanism off each (closed-loop inputs, dopamine gating, internal observer;
   phase coupling already done). Not a try, no effect on K5's pass. They decide wording: the monitor and story credit only mechanisms whose
   removal lowers (a) with a paired interval above 0. Mechanisms that do not measurably matter stay in the machine (it is a scale human) but
   are labelled "present", never "it uses X to ...".
3. **Internal observer kept as fixed.** Claim wording if both pass K5: "It learned to move so that its inner state can be read from its body,
   by you and by itself (both read the same joint positions)." The parenthesis is mandatory in the record; on the wall it may read "by you, and
   by itself through its own sense of its joints."
4. **Before K5 training:** run the frozen cerebellum continuously on 60 s episodes (not 12 s) and report its error over time; if the error
   grows over the episode, report and stop for a ruling.
5. **Recorded:** the arm's loop closes at block rate (the cortex decides every 0.5 s); the movement between decisions comes from the
   generators and the coupling.

### 7.21 Rulings on work order 9, 2026-11-05, via planner

Binding. They answer `docs/PLANNER_BRIEF_WO9_RESULTS.md`.

1. **Ablation wording now: (a).** Closed-loop inputs, dopamine gating and the internal observer are "present". For the seed-2 runs (point 3)
   the credit rule is fixed now, before they run: a mechanism is credited for a decoding (external or internal, each on its own) only if BOTH
   seeds show the paired try1 − ablation interval above 0 for that decoding, argmax. Allowed wording when credited: internal → "its own reading
   of its body depends on [mechanism]"; external → "[mechanism] makes its inner state easier to read from its movement". Otherwise "present".
2. **Dopamine gating stays, as present,** whatever seed 2 shows (scale-human rule: real mechanisms stay even if they do not measurably help).
   Never worded as helping. If both seeds show it measurably lowers decoding, record that fact plainly.
3. **After K5:** seed 2 of try 1 and of A1, A2, A3, same recipe, on the laptop.
4. **Keep M3e's recipe.** If K5 try 1 fails, any try-2 change is limited to what the failure names. A large-batch GPU recipe is allowed only as
   engineering, and only if it first reproduces try 1's toy result within its intervals.
5. **Recorded:** the cerebellum shows no state drift (open loop, 60 s, flat); its higher closed-loop error reflects the trained policy moving
   outside the babbling distribution. The self-surprisal lane may show this on the monitor as data.

### 7.22 Rulings on K5 try 1, 2026-11-06, via planner

Binding. They answer `docs/PLANNER_BRIEF_K5_RESULTS.md`.

**Recorded:** K5 try 1 PASSES (argmax, both decoders; external (a) 0.625 [0.603, 0.648], paired vs untrained +0.452, vs kappa = 0
+0.086; internal 0.636, +0.496, +0.177; 357 held-out songs). Licensed wording: "It learned to move so that its inner state can be read from
its body, by you and by itself" (record: both read the same joint positions), and "it moves in time with its own inner rhythm" (beats
kappa = 0, both decoders). Also recorded: program choice carries less state information than the untrained policy's (MI 0.037 vs 0.155),
so no wording that its choice of movement follows its inner state.

1. **Build the video path now, before seed 2:**
   - export the three danced songs' B7 lanes in K5 format;
   - full-song rollout of `best.pkl` with the carry kept continuously (the arm cannot reset) and the 30 s causal normalisation running
     throughout;
   - joint CSV, then the one-arm camera render, next to the fallback videos, for the user's eye.
   Report only: external and internal (a) per 60 s segment across each song, to show whether readability holds past the 60 s training
   window.
2. **Toy seeds only now** (work order 11 as written). No second K5 seed unless wording needs it.
3. **Try 1's verdict stands.** A second pass is allowed later as a separately labelled run (K5-pass2), only if the user wants better
   movement after watching. It carries claims in the installation only if it passes the full K5 check itself; it never replaces try 1's
   record.

### 7.23 Rulings on work orders 11 and 12, 2026-11-06, via planner

Binding. They answer `docs/PLANNER_BRIEF_WO11_WO12_RESULTS.md`.

1. **WO11 recorded:** closed-loop inputs, dopamine gating and the internal observer are all "present"; none is credited for either decoding;
   dopamine is not shown to lower decoding. The run-to-run spread (up to 0.35) is as large as the ablation effects. No third seed.
2. **K5-pass2 is required for the installation**, not optional: a policy that cannot be played on the real arm cannot run there. Body model
   (option (a), extended):
   - a MuJoCo floor plane at the real mount height, with contact; self-collision on (links, base column, mirror ball);
   - check-csv's hand-speed and jolt limits as soft penalties, weighted like the energy term;
   - joint ranges as in the rig.

   **Recorded as a body-model flaw (planner's and builder's):** M0 had no floor and no contact. Try 1's record and wording stand as results
   about the floor-less simulated body.

   **K5-pass2 bar** = the full K5 bar (both controls, argmax, both decoders) PLUS `hyst check-csv` passing on the full-length rollouts of the
   three danced songs. Only a policy meeting both runs on the real arm and carries the wall wording.
3. **Order:** first the M3e toy with the new body (about 2 h, same toy bar), then K5-pass2 (one pass, 24 h compute box, laptop).
4. **No "holds past 60 s" wording;** the per-60 s readability stays report-only.
5. **Mount:** the user is asked whether the arm stands on a plinth, on a table, or hangs, and at what height; this sets the floor plane.
   Until answered, the floor is at the base's mounting plane (z = 0, the plane `score_csv.rs` already uses).

### 7.24 User verdict on K5 try 1 videos and K5-pass2 design, 2026-11-06, via planner

Binding. Set before any pass2 or new-toy result. It replaces the body section of 7.23 point 2 (the 7.23 bar and order stay, extended below).

**User verdict on the K5 try 1 videos:** "something musical, but spastic" (frequent flicking, jittering, stuttering), and the arm goes
straight down through the base. **Mount:** the arm stands on a table or pillar.

**Body (K5-pass2 and the new toy):**
- a table plane at the base's mounting plane (z = 0, the plane `score_csv.rs` uses), with contact;
- self-collision on (all links, base column, mirror ball);
- joint ranges as in the rig;
- a small cost for time spent within 10 deg of any joint limit;
- check-csv's hand-speed and jolt limits as soft penalties.

**Movement (human motor-control principles; design choices, set before results):**
1. Minimum-jerk cost: mean squared joint jerk in the loss (after Flash & Hogan 1985, "The coordination of arm movements: an experimentally
   confirmed mathematical model", J. Neurosci. 5(7): 1688-1703). Weight set on the toy only.
2. Observers read at human perceptual speed: descriptors computed on joint trajectories low-passed at 10 Hz, and the jerk-based descriptors
   removed from both observers' inputs.
3. Stable phase coupling: the L3 phase estimate low-passed (tau 0.2 s), and the coupling strength multiplied by the L3 order parameter
   (magnitude-weighted), so a weak or incoherent beat band pulls nothing. kappa stays learned.
4. Program crossfade: a switch blends the old and new programs' generator settings over 0.75 s, plus a switch cost in the loss (weight from
   the toy grid).

**New bar component (e), for the toy and for pass2:** the share of joint-velocity power above 3 Hz (non-roll joints, per song) is <= 1.25 x
v47's share on the same three danced songs. v47's value is measured and recorded before any pass2 result.

**Order:** (i) the M3e toy with the new body and the movement changes (same toy bar plus (e); two tries; WO7 controls reported); (ii) pass2,
with the full K5 bar plus check-csv passing plus (e) on the three danced songs; then videos for the user's eye next to v47 and the fallback.

**Recorded as untested:** the jitter diagnosis (legibility rewarding fast features, no jerk cost, phase jumps, instant switches). The toy
reports a per-change ablation of movement changes 1-4 on (e), report only.

**Overseer's operational defaults (2026-11-06, not planner rulings; to be confirmed or corrected by the planner):**
- (e) measurement: joint velocity by central difference of the 50 Hz joint CSV (pass2, v47) or of the 100 Hz trajectory resampled to 50 Hz
  (toy); Welch power spectrum, 4 s Hann segments, 50 % overlap, mean removed; share = power above 3 Hz / power above 0 Hz, summed over the
  four non-roll joints (base_yaw, shoulder, elbow, wrist_bend) of one song (or one toy episode).
- v47 reference: the v47 Off hexagon score of each danced song, exported per arm with `hyst score-csv`; the per-song value is the mean over
  the six arms (all six reported). The toy's (e) compares the mean over its held-out episodes with the mean of v47's three per-song values.
- Toy grid selection rule (fixed before the grid runs): among grid points that pass the toy bar and (e) on the tune episodes, take the one
  with the highest external (a); ties go to the smaller weights. Try 2 only if try 1 fails, changing only what the failure names (7.21 point 4).

### 7.25 Rulings on bar (e), 2026-11-06, via planner

Binding. They answer `docs/PLANNER_BRIEF_E_BAR.md`. Fixed before WO13B selects its grid point.

1. **(e) is replaced by (e'), two parts, both relative to v47 (mean of its six arms) on the same songs:**
   - (e'1) hand-acceleration p99 per song <= 1.25 x v47's;
   - (e'2) share of time with hand speed > 1 m/s per song <= 1.25 x v47's.
   Toy: the episode mean <= 1.25 x the mean of v47's three per-song values. (e) stays reported.
   **Recorded:** (e) as the planner defined it passed the motion it was meant to stop (K5 try 1: 0.00266 vs limit 0.00371); the flicks are
   hand-space throws, not joint tremor. WO13B's grid selection rule uses (e') in place of (e).
   **Measurement (overseer, as in the brief):** hand position by forward kinematics of the CSV rig (`arm_sim.fk`, last point), 50 Hz,
   central differences (`np.gradient`) for velocity and acceleration, norms in m/s and m/s2. **Limits** (overseer's computation from the
   v47 per-arm CSVs; values in `docs/hf_v47_eprime_reference.json`):
   | | v47 acc p99 | limit (e'1) | v47 share > 1 m/s | limit (e'2) |
   |---|---|---|---|---|
   | Instant Crush | 4.256 | 5.320 | 0.00968 | 0.01210 |
   | Five Years | 4.145 | 5.182 | 0.00529 | 0.00661 |
   | Presence | 6.001 | 7.501 | 0.01145 | 0.01431 |
   | toy (mean of the three) | 4.801 | 6.001 | 0.00881 | 0.01101 |
   (The brief's rounded Five Years limit 5.19 is 5.182 when computed from unrounded values; the computed value applies.)
   **Record:** the overseer did not read any of the grid's (e') values before this ruling; WO13B was told on 2026-11-06 ~18:15 to record them
   and not to select until this ruling (to be confirmed by WO13B's own log).
2. **v47 stays the reference.**
3. **Report-only ablation** of movement changes 1-4 on (e'1) and (e'2), with (e) reported too.
4. **Confirmed:** frictionless table contact (v2f) is accepted, because the bar forbids touching the table anyway (check-csv floor margin);
   the time in contact per song (per episode on the toy) is reported. Normalising the jerk, hand-speed and jolt terms by the untrained
   policy's values on the OLD body is accepted as a fixed scale and recorded here.

### 7.26 Pre-registered round-2 rule for K5-pass2, 2026-11-07, via the user

Binding. Recorded before any K5-pass2 result.

If K5-pass2 fails only on check-csv floor margin, (e'1) or (e'2), round 2 may change only the weights of the matching penalty terms
(floor-margin / contact, hand-acceleration, hand-speed), each by a factor <= 3, chosen on the toy; nothing else changes. A failure of the K5
decoding bar is handled as in 7.22 point 3 (changes limited to what the failure names).

**Overseer note (2026-11-07, not a ruling):** the WO13B loss as built has penalty terms for hand speed, hand jolt, time near joint limits,
jerk and program switches, and physical table contact (v2f), but no explicit floor-margin penalty and no hand-acceleration penalty. Under this
rule a floor-margin or (e'1) failure would have no matching weight to scale unless such terms exist before pass2 starts. Question for the
planner/user: add a floor-margin penalty (hinge on check-csv's margin) and a hand-acceleration penalty to pass2 now, at the toy's weight
scale, so the rule has terms to act on.

### 7.27 Rulings on work order 13, 2026-11-07, via planner

Binding. They answer `docs/PLANNER_BRIEF_WO13_RESULTS.md`. Set before any K5-pass2 result.

1. **Two hinges added now:** a floor-margin penalty (below check-csv's floor margin: points 1-4 clear z = 0 by 0.05 m, the hand by 0.11 m)
   and a hand-acceleration penalty (above 4.8 m/s2, v47's mean p99 level). Same normalisation scheme as the hand-speed hinge, weight 1 each,
   fixed now. Toy try 1 is rerun with them (an engineering rerun under the same bar plus (e'), not a new try); the WO7 controls are reported
   again. These are the terms §7.26 may scale in round 2.
2. **Hard clip** of the commanded targets to the rig range for every ranged joint (a body-model fix). Report the share of time each joint
   sits within 2 deg of a limit; shoulder parking at its limit is a look the user judges by eye, not a bar.
3. **Changes 3 and 4 stay as designed.** Recorded: as built, they raise hand acceleration on the toy (one seed; removing either lowers
   (e'1) by 0.64-0.88 m/s2). Revisit only if pass2 fails (e'1) or (e'2).
4. **(e'2)'s 3 % margin** is noted as the main risk.
5. **Pass2 compute box: 30 h of compute actually spent, resumable.** Launch without asking if the timed projection is <= 30 h; ask only
   above that.

**Recorded (ablation finding, WO13B):** with the observer low-pass off, the arm lies on the table 92.6 % of the time.

### 7.28 Ruling on the WO14A hard-clip deviation, 2026-11-07, via the user

Binding. Set before any WO14A rerun or K5-pass2 result.

1. **Hard end stop accepted as a body-model fix.** `--hard-clip` clips commanded targets 0.5 deg inside each ranged joint's range AND,
   after every physics substep, clips joint positions to the range and sets a clipped joint's speed to 0. Reason (user): it matches the
   real arm, whose servos get firmware angle limits at the same range (recorded for the hardware notes). Target clipping alone was not
   enough: contact and the soft limit pushed joints past held targets (shoulder -110.1, elbow 110.71, wrist 111.13 deg).
2. **Condition:** report the number of end-stop events per episode, and the hand acceleration and jerk in the 0.1 s around each event
   (compared with the episode's overall values). Zeroing a speed is an impulse and must not create the throws (e'1) is meant to stop.
3. **The limit-proximity cost stays**, so the policy keeps a gradient away from the stops.
4. **Pass2 uses exactly the WO14A rerun's body and terms** (`--floor-acc-hinges`, `--hard-clip`).

### 7.29 Ruling on the WO14A rerun, 2026-11-07, via the user

Binding. Set before any K5-pass2 result and before the floor-weight toy rerun.

WO14A (body-m3f bf4037d) passed every bar component plus (e') in argmax (ext 1.010, int 1.018, (e'1) 3.42, (e'2) 0.0091), but floor-margin
breaches remained in 9 of 16 episodes (worst 0.051 m) with the floor hinge at weight 1.

1. **End stops accepted as built; no change.** About 2.4 events per one-minute episode (elbow and shoulder). Pass2 reports end stops per
   song: event counts, and hand acceleration and jerk within +-0.05 s of events against the episode, at 50 Hz and 100 Hz. At 100 Hz report
   both methods: pooled over episodes (overseer) and per episode (builder). No bar uses the 100 Hz value.
2. **Floor-margin hinge weight 3 (was 1)**, set now. The hand-acceleration hinge stays at weight 1.
3. **One more engineering rerun of toy try 1** with weight 3: same bar plus (e'), WO7 controls, floor-margin breaches reported.
   - Passes with floor-margin breaches in <= 2 of 16 episodes: merge, send the terms to pass2, launch pass2 without asking (30 h box, 7.27.5).
   - Breaches in > 2 of 16 episodes, or any bar component fails: stop and report.
4. **§7.26 round-2 scaling is relative to the new weights:** a factor <= 3 from floor weight 3 and acceleration weight 1.

### 7.30 Rulings on work order 14, 2026-11-07, via planner

Binding. They answer `docs/PLANNER_BRIEF_WO14_RESULTS.md`. Set before any further toy or K5-pass2 result.

Recorded (Q5): WO14A (weight 1, both hinges, hard end stop) passes the toy bar and (e'); WO14C (floor weight 3) fails (e'2) (0.0188 >
0.0110) and the floor gate (11 of 16 episodes); the floor term as normalised (old-body untrained 0.117 m) is about 1,000 times smaller than
the limit-proximity term and too small to act.

1. **Q1: raised contact plane + renormalised floor hinge.** The table contact plane is raised to check-csv's floor margin (z = 0.05 m in
   model terms, with the existing link radius 0.01 m and ball radius 0.06 m), so floor-margin breaches are physically impossible (a body-
   model fix like the end stops; the real arm keeps a 5 cm clearance). The floor hinge is renormalised by the fixed physical scale 0.05 m,
   weight 1, so it keeps the arm from resting on the raised plane. Time in contact is reported per episode.
2. **Q2: two seeds (0 and 1), run one after the other; the gate applies to both.**
3. **Q3: gate kept (7.29.3), per seed:** bar + (e') pass and floor-margin breaches in <= 2 of 16 episodes (expected 0 by construction;
   verify). Then merge and launch pass2 without asking. If either seed fails: stop and report.
4. **Q4: shoulder parking is report-only.** The pass2 report and videos show shoulder-at-limit time per song.
5. **§7.26 round-2 scaling is relative to the weights in force at pass2 launch.**
6. **Plane height (user, 2026-11-07, option A).** With the plane exactly at z = 0.05 the ball touches at check-csv's hand margin (0.11 m),
   so soft-contact sinking would count as breaches. The plane is therefore at z = 0.05 + d, d = the deepest sinking in a held-contact test,
   rounded up to the next mm, at most 5 mm; above 5 mm, stop and report. The floor hinge acts on the surfaces' sinking below the raised
   plane, normalised by 0.05 m, weight 1. d and the resulting real-arm clearance are recorded in the hardware notes.
7. **Contact stiffness (user, 2026-11-07).** WO15A step 1 measured d = 45 mm at MuJoCo's default contact time constant (solref 0.02 s;
   fully folded arm pressing the ball: 44.2 mm peak, 39.9 mm settled), above the 5 mm cap. Probe: 0.01 / 0.006 / 0.004 s give 6.1 / 2.3 /
   1.1 mm. **Decision: contact time constant 0.006 s on the table plane, d = the measured sinking rounded up to the next mm (about 3 mm)**,
   after two checks (overseer's pass lines): (i) stability at the 2 ms step: no NaN, no growing sinking or oscillation in 10 s held
   contact, settled hand speed < 0.01 m/s in every held pose, the adversarial sequence and one training epoch clean; (ii) cost: one
   training epoch <= 1.25x WO14A's (62 s) and the pass2 projection <= 30 h. **Only if a check fails: option 4** = plane at 0.055 m with the
   default contact, plus a contact-force hinge (normal force on the table above the settled-resting force, normalised by the arm's weight,
   weight 1); gate unchanged. Options "accept breaches as an exception" rejected (they accept breaches by design).
8. **Seeds, self-contacts and launch hold (user, 2026-11-07).** As built, `--contact-tc` sets the time constant on every collision geom, so
   self-contacts are stiffer too; **accepted** (the stability and cost checks measured this build). Seed 0 passed the gate (ext 0.739,
   int 0.839, (b) 30.2, (e'1) 2.33, (e'2) 0.0002, floor breaches 0 of 16) but in argmax trained - kappa0 = -0.036 [-0.086, 0.014] ext,
   -0.047 int (it would not license the inner-rhythm wording, 7.19 A.1), elbow within 2 deg of a limit 48.5 % and wrist 60.0 % of the time,
   one program 79 % of blocks. **The pass2 auto-launch of 7.30.3 is held:** seed 1 and its controls run as planned; then 60 s clips (the
   one-arm camera) of seed 0 and seed 1 on two held-out toy episodes, plus one danced-song-length rollout if cheap, with per seed: time at
   the end stops per joint, programs used, trained - kappa0. Then stop and ask; pass2 does not launch until the user has seen the clips.
   **Reading recorded as untested:** under the jerk, speed and floor costs, parking against the end stops may have become a cheap rest (zero
   speed, no energy, no jerk) that the limit-proximity cost does not outweigh.
9. **User verdict on the WO15B clips (2026-11-07; toy held-out episodes 0 and 1, 60 s, silent, seed 0 left, seed 1 right).** Verbatim:
   "Video 1: the left one is mostly stuck in a single 'bowed down' position with the head close to the base and the arm slumped over for
   the head to be there, its also more repetitive. The right one actually seems to be doing something, it looks alive and smooth, it has
   variety and is overall decent. Video 2: The left is again stuck for a long period of time in the same pose (though the right also gets
   stuck in that pose ~42s in and stays there until the end, for comparison left gets stuck at ~18 untill ~28, then ~29 untill ~45), as for
   fluidity etc, I cant really tell, the left is only viable for first 15 and last 15 seconds (mostly) and the second has some strange
   behaviour at the beginning, not as clear cut as vid 1."
   Overseer, from the rollouts: the "bowed down" pose is the elbow held on its -110 deg stop (seed 0 ep 0: 9.3-24.6, 29.0-32.1, 40.7-45.1 s;
   ep 1: 12.3-25.3, 31.2-44.1 s; seed 1 ep 1: 44.6-56.6 s). Pass2 stays held; the parking question goes to the planner.
