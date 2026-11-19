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

### 7.31 Rulings on work order 15, 2026-11-07, via planner

Binding. They answer `docs/PLANNER_BRIEF_WO15_RESULTS.md`. Set before any further toy or K5-pass2 result.

1. **Q1: diagnose the parked behaviour first.** No training, no new cost, no pass2 until the user has seen the diagnosis. From the saved
   rerun3 rollouts (both seeds; re-simulating them deterministically with extra logging is allowed), every hold stretch >= 2 s at a stop
   (those in the WO15 brief 2.4 plus any others), per stretch:
   1. Clipping: the pre-clip commanded target, generator centre and amplitude for the held joint; the share of hold time where the
      commanded target lies beyond the stop; whether the oscillator keeps swinging there.
   2. Chosen stillness: whether commands sit inside the range with small amplitude (the policy asking to be still).
   3. Contact: any self-contact (ball or links against the base column or other links) or table contact during the hold, with forces;
      whether the arm rests on something.
   4. End stop: end-stop events and velocity zeroing at hold onset and exit; whether the joint is pinned by repeated stop hits.
   5. Brain side: the program chosen during holds vs outside, kappa, and the inner-state targets (arousal, surprisal, L3 order parameter)
      during holds vs outside.
   6. Observer: decoding (a) inside holds vs outside (is the parked pose an easy code?).
   Then stop and report, with a one-line verdict per hypothesis (supported / not supported).
2. **Q2: parking gate, adopted now for the next toy rerun whatever the fix:** per seed, no joint on a stop for more than 10 % of the time
   and no single hold at a stop longer than 5 s, added to the 7.30.3 gate. Report-only: share of time on a stop per joint, longest
   stop-hold, longest hold of ANY pose (hand speed < 2 cm/s).
3. **Q3: (a).** Pass2's own kappa-0 control decides the inner-rhythm wording.
4. **Q4: recorded** as written in the brief, plus: the user's verdict that seed 1, episode 0 "looks alive and smooth, has variety"; the
   user's reading that the slump may be the arm trying to move but being clipped; untested planner note: a hard clip has zero gradient
   beyond the limit, so if commands saturate, the limit-proximity cost alone may be too weak to pull the policy out.
5. **Additions to 7.31.1 (user, 2026-11-07), received after WO16 had run; done as addendum WO16b.**
   1. Step 1 also lists holds >= 2 s within 1 deg of the target-clip boundary (stop - CLIP_MARGIN_DEG), separately from holds on the stop
      itself. In point 1 (clipping), "beyond the stop" means beyond the clip boundary.
   2. **H7, torque saturation / gravity:** per hold, the actuator torque of the held joint and of the shoulder vs the provisional stall
      torque (2.94 N m): share of hold time at saturation, and whether the joint is pushed into the stop by gravity rather than commanded
      there.
   3. **H1b, network saturation:** per hold, whether the motor cortex's centre and amplitude outputs for the held joint sit at their output
      bounds (share of time within 2 % of a bound).
   Verdict lines become H1, H1b, H2-H7.

### 7.32 Rulings on work order 16b, 2026-11-08, via planner

Binding. They answer `docs/PLANNER_BRIEF_WO16B_RESULTS.md`. Set before any further toy or K5-pass2 result.

1. **Q1 (a): smooth centre map.** The centre output becomes a smooth (tanh/sigmoid) function of the unclipped sum, into +-(110 - A_min),
   A_min = 10 deg for the three bend joints; no hard clip on the path. The end stop stays as the physical backstop.
2. **Q2 (b): the same smooth map replaces every clipped u output** (bounds unchanged; A_min applies to centres only), so no output can hide
   behind a zero-gradient clip. A unit test checks the gradient is non-zero at and beyond the old bounds.
3. **Q3:** seed 0's program 2 report-only.
4. **Recorded (Q4):** the WO16/WO16b verdicts (H1 yes, H1b yes, H2 no, H3 no, H4 yes, H5 seed 0 only, H6 no, H7 torque no / gravity yes)
   and the chain: the centre output saturates at its clip, zero gradient, the amplitude cap goes to zero, gravity droop (1.5-1.6 deg)
   carries the joint past the 0.5 deg clip margin onto the stop, where it is pinned. **The user's reading ("trying to do something but
   clipped", 7.31.4) was correct.**
5. **Then:** the two-seed toy rerun (seeds 0 and 1) under the 7.30.3 gate plus the 7.31.2 parking gate. **Both seeds pass: launch pass2
   without asking, and render 60 s clips of both seeds (same episodes as WO15B) for the user in parallel.** Pass2 stays pausable; the user
   may stop it after the clips. **Either seed fails: stop and report, with clips.**
6. **Smooth-map scale (user, 2026-11-08, answering `docs/PLANNER_BRIEF_WO17_MAP_SCALE.md`): (c).** Keep u = 0.5 + 0.5 tanh((s - 0.5)/c)
   with c = 0.5 and the running WO17. Recorded arithmetic: over the reachable sum s in (-0.2, 1.2), u spans 0.057-0.943, so bend centres
   reach +-88.5 deg (not +-100) and about 6 % of each output's range is unreachable at each end; the full joint range is still reachable
   through the amplitude (cap 110 - 88.5 = 21.5 deg). If both seeds pass both gates, pass2 launches with c = 0.5 as ruled. Revisit c = 0.35
   only if the clips or a gate show the arm lacking range.

### 7.33 Rulings on K5-pass2, 2026-11-08, via planner (answering `docs/PLANNER_BRIEF_PASS2_RESULTS.md`)

Results recorded (overseer recomputed): pass2 (best.pkl = round 600 of 977, 17.50 h compute) on the 1,071 check windows / 357 songs, argmax:
external (a) 0.943 [0.911, 0.977], internal 0.958 [0.924, 0.992]; vs untrained +0.922 / +0.926; vs kappa = 0 +0.025 [0.021, 0.030] /
+0.019 [0.014, 0.023]. `hyst check-csv` accepted on Instant Crush, Five Years, Presence; (e'1) 2.13 / 2.14 / 2.11 m/s2 (limits 5.32 / 5.18 /
7.50); (e'2) 0 on all three; contact 0, end stops 0.

1. **(a) + (b).** Pass2 is recorded as passing the pass2 bar (7.23 + 7.25): numeric record. Any public wording waits for the user's verdict
   on the three-panel videos.
2. **(b).** The inner-rhythm wording (7.31.3) is licensed only with the size qualifier, e.g. "a faint pull toward its own inner rhythm (about
   3 % of its readability)". Recorded: trained kappa means 0.005-0.015.
3. **(a).** Recorded: the basal ganglia select a single program 100 % of the time (argmax, check windows and all three songs; (c) MI 0.0).
   They are "present", never described as choosing. A diversity term only if the user's verdict asks for variety.
4. **(a), then (b) conditionally.** Recorded: the peak hand speed is 0.741 m/s in all three songs (identical to 3 decimals), a probable
   ceiling of the movement mapping, cause not checked; hand acceleration p99 ~2.1 vs v47 4.1-6.0. If the user finds the movement too calm
   or capped, a report-only diagnosis of the ceiling (no training) follows.
5. **(a), with (b) required before any future long run.** Recorded: validation peaked at round 600 (ext 0.913, int 0.931) and fell to 0.875
   / 0.869 (round 800) and 0.784 / 0.880 (round 977). Before any future long run, a report-only diagnosis of the late drop (e.g. tau
   schedule, learning-rate tail) is required.
6. **Next:** wait for the user's verdict on the videos. Meanwhile the body-k5p2 code is verified and merged into body.
7. **User verdict on the pass2 three-panel videos (user, 2026-11-08):** "The third video isn't good, it's the same exact shape of movement,
   just repeated at different speeds/accelerations/etc, it's not conveying anything to me." So no public wording for pass2 (point 1).
   Overseer measurement recorded (song CSVs, shoulder / elbow / wrist bend): pass2 visits 214 / 239 / 237 distinct 5-degree postures on
   Instant Crush / Five Years / Presence vs v47 one arm 2,321 / 1,734 / 2,094 and K5 try 1 3,682 / 2,968 / 2,320; shoulder sd 3.0-3.3 deg
   (v47 14-17); the bend-joint sd and range are nearly identical across the three songs (shape is song-independent; only timing and speed
   vary). The readability bar (a) is met by timing and speed modulation of one fixed shape. Next step goes to the planner
   (`docs/PLANNER_BRIEF_PASS2_VERDICT.md`).

### 7.34 New direction after the pass2 verdict, 2026-11-08, via the user + planner

Background: `docs/RESEARCH_2026-11-08.md` (reference only; its claims are untested proposals and some citations are unverified; only the
rulings below bind).

1. **Working hypothesis (untested until Stage 0):** the legibility objective was satisfied by one shape modulated in timing because
   (1) the decoding target was low-dimensional and fast, (2) the 30 s within-song z-scoring removed between-song differences, so
   song-dependence was invisible to the objective, and (3) the costs priced posture variety while nothing rewarded it.
2. **Stage 0 (analysis only; no training).** Policies: pass2 best.pkl (round 600), and v47 one arm as the reference. Measures per song:
   - between-song Jensen-Shannon distance of mirror-ball position distributions (5 cm 3-D grid);
   - distinct postures (cells with >= 0.5 % dwell);
   - shoulder sd;
   - per-song peak hand speed and its distance to the hand-speed bound;
   - program-usage entropy;
   - a machine 2AFC: a classifier picks which of two tempo-matched songs a 30 s motion clip came from (held-out songs).

   Pre-registered expectation: pass2 machine 2AFC <= 60 %, v47 clearly higher. If pass2 is already high (> 60 %), the diagnosis is
   partly wrong: stop and report.
3. **Stage 1 (toy).** A 2-link planar arm; synthetic songs = a slow per-song latent x a fast beat. Four arms, cumulative:
   - (i) the current objective;
   - (ii) + corpus-level normalisation for a slow target stream (slow-layer state, 8 s surprisal integral) and a contrastive music<->motion
     matching term with tempo/RMS-matched negatives;
   - (iii) + a Lipschitz-constrained observer (spectral norm, posture metric in metres);
   - (iv) + a DvD-style -log det song-diversity term.

   In all four arms, costs are hinge constraints with free interiors (dual multipliers). Pass: (iv) between-song JS >= 3x (i) with
   decoding >= 0.7. Report the smallest arm that reaches >= 2x (i). Ship only the ingredients that are needed.
4. **Order and reports:** report after Stage 0, then after Stage 1. The rules of each stage are committed before it runs. The human
   match/mismatch test (real vs swapped music) becomes the headline check for any future pass; its design is ruled before Stage 3.
5. **Not yet:** no 5-DoF run, no memory retry, no motion-capture prior. The basal ganglia stay (scale-human goal). A Switch-style
   load-balancing term per song is the planned fix, tested only after Stage 1.
6. **Hardware note:** 2.9 N m is the 12 V STS3215; the 7.4 V part is ~1.6 N m (16.5 kg cm at 6 V). Record it for the servo choice.

**Overseer operationalisation of Stage 0 (2026-11-08; committed before the run; the planner may amend it before the run starts):**
- **Songs.**
  - Pass2: continuous full-song argmax rollout of all 357 held-out check songs and the three danced songs (WO12 / k5p2_eval "songs"
    recipe), 50 Hz.
  - v47 one arm: arm 0 of the v47 Off hexagon score. The three danced songs come from the existing CSVs. A held-out subset is used if the
    sidecar + score pipeline can run on new songs: target 12 tempo-matched pairs (24 songs) within 6 h compute. If not feasible, v47 is
    measured on the three danced songs only, and its 2AFC is reported as weak (not tempo-matched).
- **Mirror-ball position:** the last point of the rig forward kinematics (`m3f_report.fk_points`; for v47, the same FK on its joint CSV).
  Grid: 5 cm cubes, `floor(p / 0.05)`.
- **JS distance:** base 2, on whole-song cell distributions; median over song pairs. Paired control: the JS between the two halves of each
  song (median over songs). Report both, plus their ratio.
- **Distinct postures:** cells with dwell >= 0.5 % of the song.
- **Peak hand speed:** the maximum of the 50 Hz central-difference hand speed. Report the across-song sd and the distance to the
  hand-speed bound in force in the pass2 loss, read from the code (check-csv's own limit is 1.2 m/s).
- **Program-usage entropy:** bits over the 8 programs, per song.
- **Tempo:** per song, the median beat-phase rate of its B7 lane (`omega`, rad/s -> BPM). Tempo-matched means |dBPM| <= 5. Pairs are
  greedy one-to-one among held-out songs, with different artists; all available pairs.
- **Machine 2AFC, per pair:**
  - clips: non-overlapping 30 s clips;
  - features per clip: a 10 cm ball-cell histogram, plus per-joint mean and sd of angle and of speed;
  - classifier: L2 logistic regression (sklearn, brain env), standardised features, C = 1;
  - train on the clips from the first half of each song, test on the clips from the second half;
  - accuracy = the mean over test clips. Report the mean over pairs with a 10,000-resample bootstrap over pairs, and a label-shuffled
    control (expected ~50 %).
- **"v47 clearly higher":** v47 mean >= pass2 mean + 15 points, and the v47 interval's lower bound > the pass2 mean.

### 7.35 Rulings on the Stage 1 toy, 2026-11-09, via planner (answering `docs/PLANNER_BRIEF_STAGE1_TOY.md`; toy rules `docs/STAGE1_RULES.md` on body-s1)

1. **Q1 (a).** The arm (i) z-score time constant is scaled to 5 s on the 40 s toy songs: the same 1/8 of song length as pass2. Report the
   surviving between-song sd of the slow dims under arm (i)'s target before the run.
   **New arm (0), added before any run:** arm (i)'s target and observer, but with pass2's soft costs in place of the hinges (energy, jerk,
   and hand-speed/jolt penalties as weighted terms, with no free interior). Same two seeds, same epochs. Arm (0) reproduces pass2's full
   setting; arm (i) then isolates the cost change.
2. **Q2 (a), plus MMD as a secondary column.** Collapse precondition, reported before any verdict: arm (0) OR arm (i) reaches a trained
   between-song JS <= 1/3 of the untrained policy's, AND distinct postures <= 1/3 of the untrained policy's. If neither collapses, stop
   and report; there is no verdict on (ii)-(iv). The verdict compares (ii)-(iv) against whichever of (0)/(i) collapses, and states which.
   *Overseer note (not a ruling; the planner may amend): if both collapse, the reference is arm (i), since (ii)-(iv) are cumulative on
   (i); arm (0) is reported alongside.*
3. **Q3.** All three pre-run amendments are recorded: 1000 epochs per run; an epoch = 8 batches, each a random anchor song plus its 7
   tempo- and gain-matched nearest train songs; and the builder's own L2 logistic regression. That regression gets a test against scipy's
   optimiser (or a closed-form check on a separable toy, if scipy is absent).
4. Stage 1 still waits for the Stage 0 report.

### 7.36 Rulings on Stage 0, 2026-11-09, via planner (answering `docs/PLANNER_BRIEF_STAGE0_RESULTS.md`)

1. **Q1 (c). Stage 0 is closed.** The pass2 machine 2AFC is at chance (49.1 % [45.4, 52.7] over 128 tempo-matched held-out pairs;
   overseer recomputed 48.4 %), which confirms the working diagnosis (7.34.1). v47 one arm on the three danced songs is recorded as a weak
   reference only: v47's automatic beat grid failed on held-out songs, 0 of 10.
2. **Q2 (a) + (b), before Stage 1 runs.** "Occupied cells (any dwell)" replaces "distinct postures (>= 0.5 % dwell)" in the Stage 1 collapse
   precondition (7.35.2) and in every later bar. The entropy of the cell distribution (bits) is reported alongside. Occupied cells are
   always compared at equal durations, because cell counts grow with time. Reason: the dwell measure ran backwards (v47 7 vs pass2 60;
   occupied cells v47 1,507 vs pass2 412-458).
3. **Q3 (a), for Stage 3.** The machine 2AFC uses interleaved 30 s clips (odd clips train, even clips test) with a 30 s gap. Stage 1 keeps
   its rules.
4. **Q4: run Stage 1 now** (arms 0 and i-iv, two seeds).
5. **Report-only diagnosis of the 0.741 m/s ceiling on pass2,** before any Stage 3 design: which bound produces it (the generator
   amplitude cap, the smooth-u scale c = 0.5, or the frequency range). It does not block Stage 1. Recorded: the hand-speed hinge bound is
   1.2 m/s (`m3f_jax.py:32`), 0.46 m/s above the ceiling.

### 7.37 Rulings on the Stage 1 results, 2026-11-09, via planner (answering `docs/PLANNER_BRIEF_STAGE1_RESULTS.md`)

Recorded before any run they score.

1. **Q1 (a). Pre-registered now, before the rerun.** All six arms (0, i, ii, iii, iv lambda 0.05, iv lambda 0.5) are rerun on **fresh
   seeds 2 and 3**, 1000 epochs each, rules otherwise as in `docs/STAGE1_RULES.md` and 7.35-7.36.
   - **Collapse precondition:** arm 0 or arm i has a between-song / half-song JS ratio <= 1.5 on **both** seeds 2 and 3. Occupied cells
     (any dwell, equal durations, 7.36.2) and the machine 2AFC are reported alongside; they are not part of the precondition. If neither
     arm 0 nor arm i meets it, there is no verdict: stop and report.
   - **Pass rule otherwise as ruled:** report the smallest arm (in the cumulative order ii, iii, iv) that reaches a between-song JS >= 2x
     arm i's between-song JS with D >= 0.7. Also report whether (iv) reaches >= 3x arm i's with D >= 0.7 (the 7.34 bar).
     *Overseer operationalisation (the planner may amend before the run): arm i's JS = its mean over seeds 2 and 3; an arm reaches a
     factor when its mean over seeds 2 and 3 does and D >= 0.7 holds on each seed; per-seed values are reported too.*
   - Seeds 0 and 1 (WO20) are recorded as informational only.
2. **Q2.** Default going forward: ingredients **ii + iii**. iv only if the rerun shows it is needed and D >= 0.7.
3. **Q3 (a). Report-only probe on the M3f toy.** Hypothesis recorded, **untested**: an acceleration cap that binds about 99.8 % of the
   time imposes one acceleration profile on every movement, so the cap, not the brain, sets the shape.
   - Settings: ACC_SHARE 0.25 -> 0.4 alone; the 0.8 speed share -> 0.95 alone; both together (plus the current setting as baseline).
   - Report per setting: the share of steps on each cap (per joint), occupied cells, between-song JS, decoding, and the hand metrics.
   - Any change must stay within the per-joint acceleration limits of the servo model, stated per joint (`make_arm.py` LIMITS, deg/s and
     deg/s^2: base 120 / 600, shoulder 90 / 300, elbow 150 / 1000, wrist bend 200 / 2000, roll 250 / 3000). The probe reports where each
     setting sits against them (realised joint acceleration and speed, p99 and max, per joint, as a share of the limit).
     *Overseer note: `cpg.py:21` records that ACC_SHARE 0.7 once let the shoulder reach 1.2x its acceleration limit at 50 Hz.*
4. **Q4: recorded.** The toy's arm i is only partly collapsed: its machine 2AFC is 0.70-0.86, against pass2's 0.49 (Stage 0). Song
   identity stays partly readable in the toy without any change.

### 7.38 Rulings on the Stage 1 rerun, 2026-11-09, via planner (answering `docs/PLANNER_BRIEF_STAGE1_RERUN.md`)

1. **Q1 (a). Stage 1 is closed without a verdict.** The four-seed table (seeds 0-3, `/secondary/hyst-data/body/s1/` and `.../s1r/`) is
   recorded as informational: arms ii-iv show between/half JS ratios of 8.8-20.5 against 0.77-4.84 for arms 0/i, and machine 2AFC 0.97-0.99
   against 0.63-0.88. The forward choice is a design decision on this evidence, not a pre-registered pass.
2. **Q2 (a) + (c).** Default forward: **arm ii** (corpus-normalised slow target + matched InfoNCE). The route to arm iii's wider movement:
   ii + iii with **D >= 0.7 enforced as a hinge with a dual multiplier**. One toy check on two fresh seeds (4 and 5), report-only, before
   any long run (work order 24).
3. **Q3: recorded.** Toy collapse is seed-dependent: arm 0 meets the collapse ratio on 3 of 4 seeds, arm i on 2 of 4. Any toy precondition
   needs several seeds.
4. **Recorded: M3f training numbers depend on the thread count with the same code** (WO23 identity control: epoch-0 dec_e 1.9956 at 3
   threads, 1.9924 at 6, 1.9983 at 8; calibration identical). Every run states and fixes its thread count; comparisons only at equal
   thread counts.
5. **Next:** the WO23 cap-probe brief; then the Stage 3 design (5-DoF run; bars incl. the human real-vs-swapped-music test) is ruled with
   both in hand.

### 7.39 Rulings on caps, ingredients and the Stage 3 design, 2026-11-09, via planner (answering `docs/PLANNER_BRIEF_WO23_WO24_RESULTS.md`)

Recorded before any run these rulings score.

1. **Q1 (a). Generator caps stay at the defaults (ACC_SHARE 0.25, speed 0.8).** Recorded: WO23 does not support the 7.37.3 hypothesis.
   Freeing the acceleration cap moves the binding to the speed cap; episode distinctness is unchanged; hand roughness rises 26-37x.
2. **Q2 (a). Stage 3 ingredients: ii + iii + the D hinge, with a multiplier allowed to fall:**
   `mu_D <- max(0, mu_D + eta * (0.7 - D_est))`, eta = 0.16.
   **Toy check first** (work order 25): fresh seeds 6 and 7, about 35 min, 6 threads. Rule fixed now: the falling multiplier is used in
   Stage 3 if held-out D >= 0.7 on **both** seeds **and** its MMD >= the rising version's (WO24 iii+D, `mu_D <- max(0, mu_D + eta g_D)`)
   mean MMD on these same seeds 6 and 7; otherwise the rising version is used.
3. **Q3: limit-check reporting.** Per joint: p99 and max of realised speed and acceleration, by central differences (stated in every
   report). A single-sample max above a limit is a flag, not a failure. Speed overshoot <= 0.6 % is clamped by the servo firmware.
4. **Q4: Stage 3 design (fixed before any Stage 3 result).**
   - **Body:** the pass2 body: v2f, raised plane at 0.053 m, contact tc 0.006, end stops, smooth-u c = 0.5, hard clip; generator caps
     at the defaults (point 1).
   - **Brain:** B7 epoch 6, frozen. Two state streams:
     - fast: beat-band phase (cos/sin), arousal, surprisal; causal 30 s z-score;
     - slow: top 8 PCs of the slow-layer (L4) state, the 8 s surprisal integral, per-layer band power; corpus-level normalisation
       (fit on training songs only).
   - **Objective:**
     - ii: InfoNCE music<->motion over a batch of 8 songs (anchor + 7 tempo/RMS-matched), on 4 s motion windows vs the matched
       brain-state windows;
     - iii: Lipschitz-constrained observers (spectral norm, posture metric in metres), external and internal;
     - decoding of both streams with the D >= 0.7 hinge (rising or falling multiplier per the point 2 toy check);
     - limits as hinge constraints with dual multipliers and free interiors: jerk, energy, hand speed, hand acceleration, floor margin,
       limit proximity (same thresholds as pass2);
     - basal ganglia kept as built (no load balancing; that is a later, separately tested step).
   - **Data and compute:** the K5 splits; 60 s windows; thread count fixed at 6 and stated; resumable; compute box 30 h. One timed round
     first: if it projects past 30 h, ask before running.
   - **Bars**, all on the 357 held-out songs, argmax, all must pass:
     (a) K5: external (a) > 0 and paired vs untrained > 0;
     (b) machine 2AFC on tempo-matched pairs (|dBPM| <= 5, different artists), interleaved clips (odd train, even test, 30 s gap):
         >= 75 % (pass2: 49 %);
     (c) between-song JS / within-song JS (odd vs even clips of the same song) >= 2 (pass2: 0.69);
     (d) occupied cells per song at equal duration: median >= 1.5x pass2's;
     (e) shoulder sd >= 8 deg in >= 70 % of songs (pass2: about 3-4 deg);
     (f) check-csv accepted and (e'1)/(e'2) <= 1.25x v47 on the three danced songs, plus the per-joint limit report (point 3).
     Reported only: decoding per stream; the kappa-0 control (wording rule as before, 7.31.3); program usage; the Burger-style contrasts
     (shoulder amplitude vs pulse clarity, wrist bend vs low-band flux).
   - **Two tries;** round 2 changes only what the failing bar names.
   - **After the machine bars:** the user's eye on the three danced songs (v47 | pass2 | Stage 3). If the user approves: the human test,
     designed and ruled before it runs (target: real vs swapped tempo-matched music, 20 s clips, n >= 30 x 20 trials, >= 65 % with
     binomial p < .01). No public wording before that test passes.
5. **Order:** toy check (WO25) -> timed round -> Stage 3 run -> bars -> user's eye -> human test.
6. **Outcome of the point 2 toy check (WO25, recorded 2026-11-09 ~18:35, overseer-recomputed from `run_*/result.json` in
   `/secondary/hyst-data/body/s1f/`; body-s1f e2f7761; 6 threads, cores 6-11; tests test_s1f/test_s1d/test_s1_toy OK).**
   Held-out D: rising (iii+D) 0.782 [0.720, 0.837] seed 6, 0.651 [0.576, 0.723] seed 7; falling (iii+Df) 0.778 [0.714, 0.834] seed 6,
   0.665 [0.600, 0.726] seed 7. MMD (between): rising 0.214 / 0.267 (mean 0.240); falling 0.226 / 0.364 (mean 0.295).
   Falling D >= 0.7 on both seeds: no (seed 7 0.665). **By the rule, Stage 3 uses the rising multiplier** (mean and per-seed readings
   agree). Recorded facts, not rulings: the rising version also misses held-out D 0.7 on seed 7 (0.651), although its held-in D_est
   ends at 0.78 on both seeds (held-in estimate optimistic by about 0.13 on seed 7). Rising D across seeds 4-7: 0.790, 0.769, 0.782,
   0.651. Other held-out numbers (seeds 6/7): JS ratio rising 12.1/9.9, falling 10.7/11.2; occupied cells 50.8/41.2 vs 49.9/39.0;
   machine 2AFC 0.970-0.980 all four runs.

### 7.40 Rulings on WO25 and the Stage 3 gaps, 2026-11-09, via planner (answering `docs/PLANNER_BRIEF_WO25_STAGE3_GAPS.md`)

Recorded before the Stage 3 timed round and before any Stage 3 result.

1. **7.39.6 confirmed: Stage 3 uses the rising D multiplier.** Also recorded: rising held-out D over toy seeds 4-7 was 0.790, 0.769, 0.782,
   0.651; the held-in estimate can be optimistic by about 0.12. **D >= 0.7 is a training safeguard, not a Stage 3 bar;** held-out D per
   stream is reported.
2. **Q1 (b). Energy and jerk hinge thresholds:** energy threshold = v47's mean block energy replayed on the v2f body; jerk threshold =
   1.25x v47's jerk. Computed in the build and recorded (dated note in the Stage 3 rules) before the timed round. If v47 cannot be
   replayed on v2f: report, then use pass2's realised values (best.pkl r600, mean over its training windows) x 1.5.
3. **Q2 (b).** The program switch cost stays at W_SWITCH 0.01, as part of the basal ganglia as built.
4. **Q3 (a) + (ii). One D hinge per stream** (fast and slow; two multipliers; rising, `mu <- max(0, mu + 0.16 max(0, 0.7 - D_est))`,
   once per round). D_est is computed once per round on a **fixed set of 16 validation windows** (never trained on, never the 357
   held-out songs), with the toy's shifted-gap definition (20 circular shifts >= 8 s, D = 1 - L_matched / L_shifted).
5. **Q4: overseer defaults accepted as written:**
   - L4 PCs: block mean (0.5 s) of the L4 state's real and imaginary parts, PCA fitted on train songs only, top 8, corpus z-scored;
   - the 8 s surprisal integral: causal sum of total surprisal over the last 8 s, from the 10 Hz lane;
   - InfoNCE: temperature 0.1, weight 0.5, symmetric, motion encoder on hand positions, gradient through the motion encoder; negatives =
     the 7 nearest train songs by sqrt((dBPM/10)^2 + (dlogRMS/0.3)^2), tempo by librosa, RMS from the audio;
   - Lipschitz by spectral norm (exact SVD per step) on both observers, units stated (external: metres of hand/joint position; internal:
     its descriptor units);
   - limit-hinge multipliers start at 1, step 0.02 per batch, rising only.
6. **Q5: start the build now** (L4 lane pass, tempo/RMS, code, tests). The timed round runs after these rulings are recorded (they are,
   here); if it projects past 30 h, ask.

### 7.41 Rulings on the Stage 3 launch, 2026-11-09, via planner (answering `docs/PLANNER_BRIEF_STAGE3_LAUNCH.md`)

The Stage 3 run (unit `hyst-wo26b-run-r1`, started 22:16, code body a9fd858, out `/secondary/hyst-data/body/s3/run/`) continues untouched.

1. **Q1: the energy threshold stays 0.375 J/block for this run.** A change is allowed only as a round-2 adjustment if bar (e) fails.
2. **Facts 1-8 of the brief are recorded as written**, including: bar (c) on pass2 is 0.48 on the interleaved definition (0.663 within,
   0.321 between; Stage 0's 0.69 used the half-vs-half split); bar (b) has 54 tempo-matched pairs (songs >= 210 s); Stage 3's energy budget
   is about pass2's (0.363 vs 0.375 J/block); the starting jerk is ~90x its threshold; 2 anchors per round (1,954 anchors); 8 train songs
   with librosa tempo < 40 BPM left as is; **the overseer's correction (fact 7):** the WO25 gaps brief wrongly said pass2's external
   observer reads positions (it read joint-angle descriptors); the build follows 7.39.4 (external observer: causal 1.5 s window of elbow,
   wrist and hand positions in metres, 4-Lipschitz in metres); pass2 Burger contrasts rho -0.03 / 0.07.
3. **Report-only additions, no change to the run:**
   - at each validation: per limit hinge, the share of steps with the constraint active (on or over its threshold) and the current
     multiplier;
   - at the round-400 validation: a 60 s render of best.pkl so far on one danced song (one-arm camera), with that clip's shoulder sd and
     occupied cells, sent to the user. The user may stop the run early on it; otherwise it continues untouched.
4. **No mid-run changes** to the objective, thresholds or multipliers.

### 7.42 Stage 3 closed, 2026-11-12, via the user (Kosta) + planner (answering `docs/PLANNER_BRIEF_STAGE3_VERDICT.md`)

1. **Stage 3 is closed, rejected by Kosta's eye.** Verdict on the round-400 clip (Instant Crush 60-120 s), verbatim: "Again same issue, it's
   the same tight move all the time with variations." The run stopped at round 511 of 977 (10.94 h compute; best.pkl = round 400, validation
   ext a 0.572). It is not resumed and gets no bar evaluation. All checkpoints and logs stay in `/secondary/hyst-data/body/s3/run/` and
   `.../s3/run_report/`.
2. **Recorded numbers (overseer, Instant Crush whole song, 5 cm cells, hand = `m3f_report.fk_points` last point):**

   | | Stage 3 r400 | pass2 r600 | v47 arm 0 |
   |---|---|---|---|
   | hand extent p5-p95 x / y (cm) | 36 / 27 | 59 / 58 | 84 / 83 |
   | cells per 60 s | 78 | 277 | 474 |
   | base sd / shoulder sd (deg) | 12 / 8.8 | 99 / 3.0 | 525 / 16.7 |

3. **Lesson:** three objective-only attempts (K5 try 1, K5-pass2, Stage 3) passed their numeric bars and failed the eye. **No further
   movement training on proxy objectives.**

### 7.43 New direction and the hand-set dial study, 2026-11-12, via Kosta + planner

1. **The piece, Kosta verbatim:** "a machine attempting to show emotion it doesn't understand, nor encode properly, into movement that
   humans understand perfectly as that emotion". Also: "it has a brain, a human like brain in some aspects, and it dances, it conveys
   something, some emotion, to your human brain through it's dance, it's trying to be human, trying to tell you something which it itself
   does not understand".
2. **Consequences (Kosta's decisions):**
   - The target is no longer "pleasant, varied dance". The target: a viewer reads a feeling in the arm, and it matches the feeling they hear
     in the music.
   - Struggle is allowed: laboured, overthinking, overemphasised. Jitter and glitching are not struggle and are not acceptable.
   - One arm, permanently. It does not sense visitors.
   - The mirror ball and the light projection are no longer the primary objective. The end effector may change if another reads better.
   - v47 must not seed anything. It stays byte-identical in Off.
   - The old test songs (Instant Crush, Five Years, Presence) are dropped as test material.
   - Priority order unchanged: looks good and conveys the music > movement truly learned > brain built from brain-like parts. All three
     central.
   - The piece is for exhibitions, not for sale. Note for later: the DEAM music-emotion dataset is licensed non-commercial (CC BY-NC).
3. **Direction accepted as the thing to test (not a build order):** (a) music -> feeling: a small readout on the frozen cortex (surprise,
   uncertainty, slow state -> intensity and dark/bright), trained on human-rated music; (b) movement -> feeling: the arm explores on its own
   in simulation, Kosta labels single clips with words, a model learns how humans read its movements; (c) matching: select movement whose
   predicted human reading matches the music's predicted reading; (d) feeling acts on movement as slow dials, not as a choice of moves.
   *PROPOSAL (planner, undecided):* auditory cortex (exists) / limbic part (new, small) / emotional drive setting movement dials / motor
   babbling + cerebellum (exist) / learning to express by caregiver-style feedback from Kosta's labels / basal ganglia + dopamine keep what
   the labels reinforce. **Do not build (a), (b), (c) or the proposal yet.**
4. **Work order: the hand-set dial study** (WO28; prompts `docs/BUILDER_PROMPT_WO28A_DIAL_CLIPS.md`, `docs/BUILDER_PROMPT_WO28B_DIAL_TOOL.md`).
   Purpose: whether this arm body can carry readable feelings at all when movement qualities are set by hand at extremes. Disposable;
   nothing ships; no learning, no training, no numeric pass bars; Kosta's eye is the only judge.
   - **Body:** the existing simulated arm (v2f: raised plane, self-collision, hard end stops, smooth command map); plain MuJoCo on CPU;
     thread count stated. No clip may show jitter, penetration of the plane or base, or dwelling at end stops: such clips are rejected and
     regenerated before Kosta sees them.
   - **Five dials** (low / neutral / high): 1 vigour (slow and small <-> fast and large); 2 stiffness (loose, overshoots and settles <->
     rigid, stops dead); 3 roundness (straight angular segments <-> curved arcs of the end effector); 4 lead/lag (all joints together <->
     base and shoulder lead, elbow and wrist follow late); 5 posture (drooped, low, folded <-> lifted, tall, open). Underlying movement: one
     fixed, seeded random sequence of feasible poses, moves timed to a beat grid, the SAME for every clip. Implementation per dial is the
     builder's choice, reported in two lines each with the numeric range, plus whether the stiffness range is plausible for a position
     servo like the STS3215 (best estimate, marked unverified).
   - **Clips:** 12 s, fixed three-quarter camera, table/pillar visible, same framing. Set A: 10 single-dial extremes + 1 all-neutral.
     Set B: 5 presets (heavy: low vigour, high stiffness, large lag, drooped, round; angry: high vigour, high stiffness, angular, together,
     lifted; tense: small moves, high stiffness, angular, long holds, lifted; calm: low vigour, low stiffness, round, flowing lag, neutral;
     light: medium-high vigour, low stiffness, round, bouncy, lifted); adjustments only for feasibility, by eye, final values reported.
     Set C: heavy, angry, light with a lamp-like head and a simple hand/gripper (simple geometry, same mass as the ball): 6 clips. A-C
     silent on a fixed 100 BPM grid. Set D only if audio exists in `/secondary/hyst-data/audio/checkset/` (Epitaph = heavy, 21st Century
     Schizoid Man = angry, One of These Days = tense, Breathe = calm, Blue Lagoon = light): 12 s excerpt per song, matching and clearly
     mismatching preset, timing from the cortex beat-band phase; else skipped and said so.
   - **Blind labelling tool:** local, no network; random order, coded names, key in a separate file. A-C: one click from tense / heavy /
     calm / angry / light / nothing, glitching / something, can't name it; optional note; replay. D: the two renders of one excerpt, order
     randomised: "which one fits the music?" plus "neither". Answers to CSV; session under 20 minutes.
   - **Outputs:** videos, key and CSV in `/secondary/hyst-data/body/dialstudy/` (outside git). Report in `docs/`: intended setting vs label
     per clip; which single dials shifted the reading; end-effector comparison; Set D picks; the dial notes. No verdict from builder or
     overseer. Planner's suggested reading, for Kosta only: viable if >= 3 of 5 presets are read as intended and >= 2 single dials visibly
     shift the reading.
   - **Out of scope (ask Kosta first):** learning or training of any kind; DEAM download; limbic readout; exploration archive / pyribs;
     brain monitor work; cortex changes (B7 epoch 6 frozen); hardware; new dials or feelings.
5. **Standing rules unchanged:** branches keys-decide / body only, never master; plain commit messages without attribution lines; frozen
   `src/` and `tools/`; v47 byte-identical in Off; data, models, audio and videos outside git; copyrighted audio never committed or uploaded;
   free compute only; no posting; never drive hardware; on anything unclear or conflicting, stop and ask Kosta.
6. **Overseer notes (not rulings; Kosta may amend):**
   - Audio check 2026-11-12 19:30: `/secondary/hyst-data/audio/` does not exist and no file with these titles was found under `/secondary`,
     `~/Music` or `~/Downloads`. Set D is skipped unless Kosta places the five files there.
   - "Long holds" (tense) and "bouncy" (light) are not among the five dials, and the pose sequence must stay the same. Default taken:
     "long holds" = each move finishes early in its beat interval and the pose is held to the next (a vigour/timing setting inside the
     same sequence); "bouncy" = low stiffness overshoot and settle. Asked of Kosta in the same message.
   - Glitch gates for rejecting clips (not pass bars on the study): defined by the builder in its rules file before rendering, reviewed by
     the overseer.

### 7.44 Dial study closed; motor-network toy test, 2026-11-12, via Kosta + planner (answering `docs/PLANNER_BRIEF_DIALSTUDY_RESULTS.md`)

Marked DEFAULT = planner choice Kosta did not overrule; PROPOSAL = undecided.

1. **Dial study recorded and closed.** Results as reported in `docs/DIALSTUDY_REPORT.md`. No further dial rounds.
   - Planner reading, for the record (Kosta did not dispute it): about three readings came through: slow/low = calm, heavy or sad;
     choppy move-stop = light, tense or energetic; bouncy = light. Light read as intended 3/3. Heavy and calm swapped. The only "angry"
     came with the lamp.
   - Known limits of round 1: silent only (Set D not run); one shared random pose sequence dominated the clips; the roundness dial
     barely changed path shape (hand chord/arc 0.949 angular vs 0.877 round).
   - Brief answers: Q1 add "sad" as a label button (DEFAULT, see 3.6). Q2 no separate re-run; 4 round-1 clips are repeated inside the
     next session instead. Q3 (Kosta): replace the hand-set dial layer with a motor-cortex recurrent network (point 2). Q4 the lamp head
     is the default end effector (DEFAULT); the ball is kept only for comparison.
2. **New direction, Kosta verbatim:** "lean more into the dynamic NN humanlike angle". Basis: Stroud, Hennequin, Porter & Vogels, Nature
   Neuroscience 2018, "Motor primitives in space and time via targeted gain modulation in cortical networks": one fixed recurrent
   motor-cortex network produces different movements when only its neurons' input-output gains change; a few modulatory control units
   steer it, and a simple reward rule can train them (neuromodulators acting on motor cortex).
   *PROPOSAL (planner, not a build order):* auditory cortex (exists, frozen) -> limbic part (new) -> sets gains of a motor-cortex network
   -> spinal oscillators -> muscle-like joints -> arm. The arm babbles on its own; Kosta's labels act as the reward that trains the gain
   controls (dopamine role). Hand-set dials and random pose lists are gone from the design. **Do not build the proposal; only the toy
   test of point 3.**
3. **Work order: motor-network toy test** (WO29; prompts `docs/BUILDER_PROMPT_WO29A_MOTORNET_CLIPS.md`,
   `docs/BUILDER_PROMPT_WO29B_MOTORNET_TOOL.md`). Question: does changing ONLY the gains of one fixed recurrent network give arm movement
   that (1) looks organic, not glitchy or random, and (2) differs in feeling between gain settings, judged blind by Kosta, with and without
   music? Disposable; nothing ships; no reward learning, no training to targets, no hand-tuning of movement by eye; Kosta's eye is the only
   judge; no pass bars beyond the safety gates of 3.4.
   1. **Motor network:** one recurrent rate network, about 200 units, unit time constant 50-100 ms (builder picks one value, states it),
      smooth saturating nonlinearity. Recurrent weights random, seeded, fixed for the whole study; scale near the edge between decaying
      and self-sustained activity at gain 1 (spectral radius stated). Inputs: cos and sin of the frozen cortex's beat-band phase (from the
      song for music clips; a fixed 100 BPM phase for silent clips), plus the cortex arousal signal when music is present; input weights
      random, seeded, fixed. About 4 modulatory control units, each scaling the gains of a random subset of neurons (subsets overlap); a
      gain setting = the values of these units; optional one extra global gain factor. Readout: 5 linear outputs -> joint targets; weights
      random, seeded, fixed. One allowed calibration: a single overall scale and offset per joint so outputs use a sensible part of the
      joint range at gain 1 (stated). No other fitting.
   2. **Body:** joint targets pass through a per-joint spring-damper (muscle-like), stiffness and damping fixed at mid values for the whole
      study (stated), no per-clip changes. Existing v2f simulated arm, plain MuJoCo on CPU, thread count stated. End effector: lamp head
      (DEFAULT), same geometry as round 1 Set C; ball only for the 2 comparison clips.
   3. **Clips** (12 s, same camera and framing as round 1). Gain settings are SAMPLED, not picked: seeded random settings of the control
      units across their full range; discard only those failing 3.4; take the first 10 that pass; plus 2 settings with all control units at
      their low and high extremes. The builder must not choose settings by looking at them.
      - Part 1, silent: the 12 settings, lamp. 12 clips.
      - Part 2, ball comparison: the first two settings by seed, with the ball. 2 clips.
      - Part 3, with music: per check song one 12 s excerpt where the feeling is clear, rendered with two different settings (seeded pick
        from the 12); question per pair "which fits the music?" + "neither"; 5 pairs. Songs (DEFAULT, from round 1): King Crimson "Epitaph",
        King Crimson "21st Century Schizoid Man", Pink Floyd "One of These Days", Pink Floyd "Breathe", Takanaka "Blue Lagoon". Audio must be
        in `/secondary/hyst-data/audio/checkset/`; if missing, STOP and ask Kosta before running; never skip silently.
      - Part 4, consistency: 4 round-1 clips (seeded pick), shown again in the same blind order mix.
   4. **Gates** (as round 1, recomputed by the overseer's own code before Kosta sees anything): floor and base clearance, end-stop dwell 0,
      joint-velocity power above 8 Hz near zero, speed and acceleration within limits; plus the arm must actually move (minimum motion
      stated). A failing setting is discarded and replaced by the next sampled one; the count of discards is reported.
   5. **Measurements per setting** (numbers only): network activity dimensionality (participation ratio); whether activity decays, cycles
      or wanders; dominant movement frequency; mean hand speed; mean hand height; hand path straightness (chord/arc per stroke).
   6. **Blind tool** (reuse round 1): coded names, seeded random order, key not served. Labels for Parts 1, 2 and 4 (DEFAULT): calm / sad /
      tense / energetic / light / nothing, glitching / something, can't name it; optional note. Part 3: the two renders of an excerpt in
      random order, "which fits the music?" + "neither". Session under 25 minutes.
   7. **Outputs:** clips, key, answers, per-setting measurements under `/secondary/hyst-data/body/motornet_toy/` (outside git). Report in
      `docs/`: setting -> label -> note -> measurements; ball vs lamp; Part 3 picks; Part 4 round 1 vs now; network and body parameters
      used. No verdict from builder or overseer. Planner's suggested reading, for Kosta only: worth building on if most silent clips are
      NOT labelled "nothing, glitching", at least 3 different labels appear across Part 1, and Part 3 picks are not random-looking.
   8. **Out of scope (ask Kosta first):** reward or label-driven learning; training of network weights or readout beyond the one
      calibration; limbic part; DEAM download; exploration archive / pyribs; brain monitor work; changes to the frozen cortex (B7 epoch 6);
      hardware; hand-picking or hand-shaping of movements.
4. **Standing rules unchanged** (as 7.43.5).
   - *Correction (planner, 2026-11-13, see 7.45):* 7.44.3.1 did not fix the ratio of input drive to recurrent drive. As first built, the
     input drive (std 0.864) exceeded the recurrent drive (0.553) at gain 1, and every setting followed the beat input. 7.45 fixes the ratio.
5. **Overseer notes (not rulings; Kosta may amend):**
   - Audio check 2026-11-12 23:55: `/secondary/hyst-data/audio/` still does not exist; no file with the five titles under `/secondary`,
     `~/Music`, `~/Downloads`. Part 3 is held, and asked of Kosta (files, and which 12 s excerpt per song). Parts 1, 2 and 4 go ahead.
   - Defaults taken where the order is silent: (a) every clip runs network and sim for 10 s of warm-up before the 12 s shown (no start
     transient); for music, the excerpt's preceding 10 s of the song drive the warm-up; (b) silent clips feed arousal as 0; (c) the
     spring-damper sits before the v2f command path round 1 used (limiter, hard stops), unchanged; (d) if an all-low or all-high extreme
     fails a gate, it is not shown and not replaced, and this is reported; (e) the minimum-motion gate, the gain range of the control units
     and the decays/cycles/wanders definition are set by the builder in its rules file before any clip is rendered, reviewed by the
     overseer.

### 7.45 Motor-network toy test: input scale and re-run rules, 2026-11-13, via Kosta + planner (answering `docs/PLANNER_BRIEF_MOTORNET_INPUT.md`)

1. **Q1 (b): input weight scale.** Fixed by rule before anything is viewed: input drive std = 0.25 x recurrent drive std at gain 1,
   silent. The same scale is used for music clips. Same seeds (sampling 29011, network 29001); redraw and re-render.
2. **Q2 (a), with a pre-registered rule.** After Q1, if base yaw or shoulder loses more than half its target p5-p95 range to the command
   limiter, the spinal spring-damper is set to 1.5 Hz, fixed for the whole study, without asking again. The limiter's share of the
   command per joint is reported either way.
3. **Q3 (b): gate defaults.** Return to the defaults (0.10 m minimum motion, +-60 % calibration) if the gain-1 run reaches 0.10 m at
   +-60 %.
4. **Q4 (a): extremes.** S11 and S12 are re-gated after the changes; they are shown only if they pass, and are not replaced.
5. **New pre-registered stop.** After the changes, if ALL shown settings still have every joint peaking at the input beat frequency AND an
   activity participation ratio below 3, Kosta's session is not started; the numbers are reported and the study holds.
6. **Planner's spec error recorded:** 7.44 did not fix the input/recurrent drive ratio (correction added under 7.44.4).
7. **Part 3** (music) still waits for Kosta's audio files and excerpt start times; it is not run without both. Parts 1, 2 and 4 may run
   once the rules above pass; Kosta is told Part 3 is pending.
8. **Merge:** body-mnet and body-mnettool go into body only after the re-run report.
9. **Standing rules unchanged** (as 7.43.5).
10. **Overseer notes (operational definitions, not rulings; Kosta may amend):**
    - *Drive std:* for each unit, the std over time of `Win u` and of `W r` over the shown 12 s of the gain-1 silent run, averaged over
      units, as in the builder's diagnosis. Win is multiplied by one scalar s; since W r depends on s, s is found by fixed-point iteration
      until the ratio is 0.25 within 2 %. s is stated.
    - *Order of steps:* (i) Q1 scale; (ii) calibrate at +-60 %; (iii) Q2 check at gain 1, silent: target p5-p95 vs command-limiter-output
      p5-p95 for base yaw and shoulder. If either output is below half the target, set spinal 1.5 Hz and recalibrate at +-60 %. (iv) Q3: if
      the gain-1 hand extent at +-60 % is >= 0.10 m on one axis, use +-60 % and the 0.10 m gate; else +-100 % and 0.05 m, as before.
      (v) Redraw S01-S10 with seed 29011, re-gate S11/S12, render. (vi) Check the stop rule (5) before any session.
    - *"Peaks at the input beat frequency":* the joint's position-spectrum peak (Hann, 12 s, DC excluded) lies within one frequency bin
      (1/12 Hz) of 100/60 Hz.
    - The joint-rate and limiter numbers are recomputed by the overseer's own code before anything reaches Kosta.

### 7.46 Motor-network toy test: Parts 1, 2 and 4 recorded; Part 3 ordered, 2026-11-13, via Kosta + planner (answering `docs/PLANNER_BRIEF_MOTORNET_RESULTS.md`)

1. **Results recorded** as in `docs/MOTORNET_REPORT.md` (body 77cc84c) and the brief. Kosta answered all 16 clips ("unsure of all the
   results, imperfect probably").
2. **Planner reading, for the record (Kosta did not dispute it):**
   - first round with no "nothing, glitching" labels; S06 drew Kosta's most positive note so far;
   - labels ordered with mean hand speed (tense < light < energetic), no overlap, 10 clips: observation only;
   - activity PR about 2 in every setting: gains change speed and size of one cycle; known risk: repetitive over a full song; the next
     design question after Part 3;
   - calm and sad were not produced by any setting;
   - repeat consistency 2/4: single-rater labels are noisy; no decision rests on one label.
3. **Q1 (a): Part 3 runs** (music, 5 pairs, the same 12 settings and the same network; S11/S12 were not shown, so the seeded pick 29031
   draws from the shown S01-S10). Then report; (b) vs (c) of the brief is decided after. **Q2 (a):** network unchanged for Part 3.
4. **Excerpt start times (Kosta, 2026-11-13; those marked ? were given as tentative and are used as given):** Blue Lagoon 0:20;
   21st Century Schizoid Man 0:58; Epitaph 5:45?; Breathe 1:17?; One of These Days 3:57?. 12 s each; the 10 s before each start drive
   the warm-up (7.44.5a). Audio in `/secondary/hyst-data/audio/checkset/` (mp3, 48 kHz stereo; outside git, never uploaded).
5. **Part 3 report adds**, per pair: the mean hand speed of both renders and the cortex arousal over the excerpt (mean of `arousal_b7`
   in the shown 12 s, raw and as the standardised network input), so picks can be compared with energy.
6. **Standing rules unchanged.**
7. **Overseer note, 2026-11-13 (applying 7.44.3.4, not a new ruling):** 3 of the 10 Part 3 renders failed the gates with music input
   although the same settings passed silent: Blue Lagoon S04 (contact 13 substeps, acceleration 1.18x limit), Epitaph S02 (contact 339,
   acceleration 7.32x), One of These Days S06 (contact 180, acceleration 1.96x). Per 7.44.3.4 a failing setting is discarded and replaced
   by the next sampled one: the same generator `default_rng(29031)` continues after the original draws; for each failing render, in song
   order, draw one setting at a time from S01-S10, skip the pair's other setting and any setting already failed for that song, and take the
   first that passes. Every failure and replacement goes into the report, so Kosta sees which settings fail with music.

### 7.47 Motor-network toy round 1 closed; toy round 2 and an arousal/energy comparison ordered, 2026-11-13, via Kosta + planner (answering `docs/PLANNER_BRIEF_MOTORNET_PART3.md`)

1. **Q3: recorded.** Part 3 results as in `docs/MOTORNET_REPORT.md` (body 1df9ada): S03 picked for Blue Lagoon, Breathe and Epitaph;
   "neither" for One of These Days and 21st Century Schizoid Man. **Q1 (a): toy round 1 is closed.** Next is toy round 2 (point 4).
2. **Planner reading, for the record (Kosta did not dispute it):**
   - Kosta's notes name the network's limits: one loop, fixed facing direction, small base/shoulder motion, too small on energetic music.
     S03 won 3/3 of its pairs, as the least bad.
   - `arousal_b7` is surprise-driven, not energy. Predictable energetic music (One of These Days, standardised -1.40) shrank the movement.
     Feeding it alone as the movement input was a planner design error.
   - 3 settings that passed silent failed the gates with music: gates must be checked per song.
3. **Q2 (a), extended: report-only comparison.** Compare `arousal_b7` with Kosta's dial recordings (3 songs) and the 5 excerpts, AND compare a
   plain acoustic energy measure against the same: loudness + onset density from the existing 44 ear features
   (`scripts/brain/fast_features.py`: column 41 `rms`, column 40 `onset`). The builder states the exact formula before looking at any
   result. Correlations only. The cortex stays frozen.
4. **Work order: motor-network toy round 2** (proposal items accepted by Kosta unless struck). Same rules as 7.44: no learning, no training
   of weights, no hand-shaping, Kosta the blind judge, gates as before and recomputed by the overseer. Every change below is fixed and
   written down before any clip is viewed.
   1. **Two populations:** slow (tau 300 ms, about 100 units) and fast (tau 75 ms, about 100 units), random coupling within and between.
      Readout: base yaw and shoulder from the slow population only; elbow, wrist bend and wrist roll from the fast population only. Same
      calibration rule as round 1 (+-60 %).
   2. **Inputs:** beat-band phase (cos, sin) to both populations; the slowest cortex layer's state (a fixed random projection of L4,
      0.01-0.5 Hz) to the slow population; acoustic energy (the formula of point 3) and `arousal_b7` to both. Input drive = 0.25 x recurrent
      drive at gain 1, as 7.45.
   3. **Control units:** 4, as round 1, with subsets spanning both populations.
   4. **Spectral radius:** 1.05 for both populations.
   5. **Sampling:** new seed; the first 8 settings that pass the gates on ALL five songs AND silent. Discards reported by gate.
   6. **Session** (blind, seeded order):
      - Part A, silent, lamp, 30 s clips: the 8 settings. Labels as the 7.46 list (7.44.3.6).
      - Part B, music: 30 s excerpts starting at Kosta's same start times (7.46.4; warm-up as before). Per song, one new setting (seeded
        pick) vs round-1 S03. "Which fits the music?" + "neither". 5 pairs.
   7. **Measurements per clip:** as 7.46, plus base yaw and shoulder p5-p95 range, facing-direction (base yaw) drift over the clip, and
      PR per population.
   8. **Stop rule:** if all 8 settings show PR < 3 in both populations AND base yaw range < 20 deg, hold and report before the session.
   9. No verdict from builder or overseer. Kosta decides.
   10. **Out of scope:** limbic part, label-driven learning, cortex changes, hardware, brain monitor.
5. **Standing rules unchanged** (as 7.43.5).
6. **Overseer notes (operational defaults, not rulings; Kosta may amend):**
   - *Ear energy (point 3):* the builder's formula goes into `docs/EAR_ENERGY_RULES.md`, committed and pushed before any correlation is
     computed or any dial value is read; the overseer checks the commit order. The formula uses only columns 40 and 41 of the 44 features,
     with fixed windows stated. The same function feeds the round-2 network.
   - *Dial data:* `/secondary/hyst-data/emotion/dial/dial2.json` (Five Years and Presence pass A; all three songs pass B) and
     `dial-ic-try1.json` (Instant Crush pass A, Kosta's first try on the older pad, used as given and marked so). The 7.43-era rule that the
     builder never opens dial files is lifted for this comparison only.
   - *Comparison method:* both signals and each dial axis (pass A energy; pass B light, heavy) resampled to 2 Hz after a 2 s moving mean;
     Pearson and Spearman per song at every lag from -2 s to +4 s in 0.5 s steps (dial behind music = positive). All lags reported; none
     is picked. Taps and the 5 excerpts get no correlation (too few points): for the excerpts, the mean of each signal over the 12 s
     shown in round 1, ranked, beside Kosta's Part 3 notes.
   - *L4 input:* L4 = the slowest of B7's four layers (horizon 800 frames). Its complex state (real and imaginary parts) is projected by a
     seeded Gaussian matrix to 4 signals, standardised like `arousal_b7` (one mean and sd over the three danced songs, clipped to +-3). No
     extra filtering. Silent clips: L4 inputs, energy and arousal are 0.
   - *Coupling:* the full 200 x 200 matrix is drawn iid; all rows of a population are scaled by one factor so that the population's
     within-population block has spectral radius 1.05. The between-population blocks keep that row factor. The full matrix's radius is
     reported.
   - *Drive ratio:* one input scale per population, found as in 7.45.10, with the gain-1 silent run, input std = 0.25 x recurrent std in
     each population.
   - *Body:* spinal spring-damper, servo, limiter and gates as round 1 (MOTORNET_PARAMS at body-mnet 265fe79); the 7.45.2 limiter rule
     applies again.
   - *Gate windows:* each candidate is simulated on 10 s warm-up + 30 s for silent and for each song at Kosta's start times; it must pass
     all six. Round-1 S03 is re-rendered unchanged (round-1 network and inputs) at 30 s per song; if it fails a gate on a song, that pair
     is not shown and is reported (S03 is not replaced).
   - *Part B pick:* `default_rng(seed)` draws 5 different settings from the 8, one per song, songs in the 7.46.4 order.
   - *Facing drift:* mean base yaw over the clip's last 3 s minus over its first 3 s (deg), plus the range of its 3 s moving mean.
   - *Stop rule:* evaluated on the Part A silent clips (PR per population and base yaw p5-p95).

### 7.48 Motor-network toy round 2 and the arousal/energy comparison recorded, 2026-11-13, via Kosta + planner (answering `docs/PLANNER_BRIEF_MOTORNET2_RESULTS.md` and `docs/PLANNER_BRIEF_AROUSAL_ENERGY.md`)

1. **Toy round 2 recorded** as in `docs/MOTORNET2_REPORT.md` (body 7801dc9) and the brief. Part A (silent, 8 settings): nothing, glitching 4
   (S02, S04, S05, S07), energetic 2 (S06, S08), tense 1 (S03), something, can't name it 1 (S01); Kosta's notes name "micro-movements" in 7 of
   8, glitchy during sweeps and useful as in-place bobbing. Part B (music, 5 pairs): round-1 S03 picked 5/5.
2. **Seed/order confound recorded, no re-show:** with session seed 30061 no pair was swapped, so the new setting was shown first and round-1
   S03 second in all 5 pairs; "first vs second" is confounded with "new vs S03".
3. **Arousal/energy comparison recorded** as in `docs/AROUSAL_ENERGY_REPORT.md` (body-mnettool4 1c59ea3, merged into body) and the brief:
   ear energy (`docs/EAR_ENERGY_RULES.md`) correlates positively with every dial axis at every lag (lag 0 Pearson 0.35-0.80 against energy and
   light); `arousal_b7` correlates negatively with Five Years pass A energy (-0.77) and near zero on Presence (0.09). The arousal brief's Q1
   (drop arousal from round 2) was overtaken: round 2 ran as ordered.
4. **Standing rules unchanged.**

### 7.49 Toy line closed; new direction: the arm learns by watching humans, 2026-11-13, via Kosta + planner

PROPOSAL = planner, not yet ruled.

1. **Toy line closed.** Reason: no human movement source existed anywhere in the system; proxy objectives, hand-set dials and random networks
   cannot be expected to look human. Kosta's notes across all rounds describe properties human dancers acquire by watching others (head-bob
   vs sweep, rise at vocal peak, rotation as a tool, bigger on the drop). These are not to be hand-built.
2. **New direction (Kosta, verbatim): "It should just learn".** Kosta is comfortable with the story that it learned by watching humans.
   Source: a public dataset if possible.
3. **Frozen target architecture** (changes need Kosta's ruling):
   - a) **WATCHING (imitation):** the motor-cortex network is TRAINED to move to music the way humans do, from human dance motion retargeted
     onto the arm's 5 joints, conditioned on the frozen cortex's view of the same music. Brain parallel: observational learning / mirror
     system.
   - b) **FEELING:** music-driven gain modulation of that trained network (Stroud et al. 2018 mechanism, tested in the toy rounds), using ear
     energy, `arousal_b7` and slow cortex state.
   - c) **TEACHER:** Kosta's blind picks refine it afterwards. Kosta's notes are feedback for this step, never hand-built specs.
   - Unchanged: frozen cortex (B7 epoch 6), one arm, v47 seeds nothing, Kosta's eye is the judge, no proxy-objective training of movement.
4. **Work order step 1: licence check (no downloads yet).** Report from primary sources only (official sites, licence files), quoting the
   exact terms:
   - AIST++ (google.github.io/aistplusplus_dataset): motion annotations are stated as CC BY 4.0; confirm from the licence file.
   - AIST Dance Video Database (the source of the videos AND the music): terms of use for (1) the music audio, (2) the videos, (3) derived
     data. Specifically: is local use for training a model allowed; is public exhibition of a model trained on it allowed (non-commercial
     art exhibition, no ticket sales expected); is any registration or agreement required.
   - 2-3 alternative public music-dance datasets with 3D motion AND music (e.g. FineDance, others the builder finds): size, licence of
     motion, licence of music, same questions.
   - Output: one table + exact quotes + links in `docs/`. No verdict; Kosta decides which source is usable. Unclear terms are reported as
     unclear, not guessed.
5. **Work order step 2: retarget look test (only after Kosta rules on step 1).** Purpose: before any training, find out whether human dance
   mapped onto this arm looks like dancing to Kosta. If it does not, imitation cannot work and the line stops here.
   - 10 clips (seeded pick across genres) of motion from the source Kosta approves. Motion data only; audio only if its terms allow local
     use.
   - Two retargeting variants, both fixed and written down before any clip is viewed:
     - V1 "arm as arm": the human's right arm drives the robot (shoulder, elbow, wrist), torso yaw drives base yaw, forearm/hand twist
       drives wrist roll.
     - V2 "arm as whole body" (PROPOSAL, Kosta's "scale human"): hip/torso yaw -> base yaw; torso lean forward/back -> shoulder; upper-body
       bend / neck -> elbow; head nod -> wrist bend; head tilt -> wrist roll.
   - Angles scaled to joint ranges by one fixed rule per variant; passed through the existing limiter/servo/v2f body; per-joint limiter cut
     reported. Same gates as 7.44 (overseer recomputes). Lamp head.
   - Clips 20 s each: 10 clips x 2 variants = 20, plus round-1 S03 on 2 of the same songs if audio is allowed (reference). With music if
     allowed, else silent.
   - Kosta's blind session: per clip "does this look like dancing?" (yes / sort of / no) + optional note; then V1 vs V2 pairs on 5 clips
     "which looks more like a person dancing?". Under 25 min.
   - Report: answers, limiter cuts, per-variant summary. No verdict.
   - Out of scope until ruled: any model training, the gain-modulation module, Kosta-feedback learning, cortex changes, hardware, monitor,
     uploads anywhere.
6. **Standing rules (unchanged):** branches keys-decide / body only, never master; plain commit messages with no co-author or attribution
   lines; frozen `src/` and `tools/` read-only; data, models, audio and video outside git; nothing uploaded; free compute only, no spending,
   no posting/emailing/submitting, no accounts or registrations without Kosta's go-ahead; never drive hardware; if unclear, stop and ask
   Kosta.

### 7.50 Dataset licences ruled; downloads approved; step 2 with FineDance, 2026-11-13, via Kosta + planner (answering `docs/PLANNER_BRIEF_DATASET_LICENCES.md`)

1. **Context (Kosta):** this is research. It will first be an undergraduate final paper; the art piece is the end goal in the sense of making
   it as good as possible. Nothing is commercial. Kosta is a student.
2. **Usable sources:** all five (FineDance, AIOZ-GDANCE, Motorica Dance, AIST++ motion, AIST Dance DB) are usable for local research / thesis
   use under their own terms (`docs/DATASET_LICENCES.md`). The planner checked the AIOZ-GDANCE licence, Motorica terms and the AIST++ site
   directly; the FineDance LICENSE and AIST terms rest on the overseer's verbatim quotes.
3. **Obligations, recorded and followed:** no redistribution or upload of any dataset content; cite each dataset/paper in any publication;
   credit music where clips with music are shown (Motorica requires it); nothing used for surveillance, military or commercial purposes.
4. **Open item for later** (before any public exhibition of a trained model): Motorica and AIST are research-only; ask the owners, or
   exhibit a model trained only on FineDance / AIOZ-GDANCE / AIST++ motion. Kosta's action, not now.
5. **Downloads approved:** FineDance public part, AIOZ-GDANCE, Motorica Dance, AIST++ motion annotations. If any download needs an account,
   login, form or client install, STOP and ask Kosta (this includes Baidu NetDisk and gated Hugging Face pages). The AIST Dance DB
   application form: Kosta fills it in himself if he wants; the overseer and builders do not. Storage:
   `/secondary/hyst-data/datasets/<name>/`, outside git, with the licence text and the download date saved next to each.
6. **Step 2** (retarget look test, 7.49.5) proceeds as ordered, with FineDance. If FineDance cannot be downloaded without an account, use
   Motorica Dance (single dancer, music included) instead and report the switch; do not wait.
7. **Standing rules unchanged.**
8. **Overseer notes (operational defaults for step 2, not rulings; Kosta may amend):**
   - *No SMPL body model:* the SMPL / SMPL-H model files need a registration, so they are not used. Retargeting works from the datasets'
     local joint rotations with canonical T-pose bone directions (arms along +-x, spine, neck and head along +y). If a variant cannot be
     built without the model file, STOP and report.
   - *Body path:* retargeted angles -> the existing command limiter -> servo -> v2f sim, as round 1, without the spinal spring-damper (the
     human motion is the movement source). Commands at 100 Hz from the dataset's frame rate by cubic interpolation.
   - *Scaling rule* (one per variant, written in the rules file before any clip is viewed): each human angle is mapped linearly so that its
     pooled p2-p98 over all sequences of the downloaded set fills a stated share of the robot joint's range around round 1's centre. The
     builder states the share and every axis definition; the overseer reviews them before rendering.
   - *Clip pick:* seeded, across genres (one per genre in seeded genre order, until 10); the 20 s window start seeded inside each sequence
     after its first 5 s. A clip failing a gate in either variant is replaced by the next seeded pick, and the failure is reported.
   - *Pair order (the 7.48 lesson):* in the 5 V1-vs-V2 pairs, V1 plays first in exactly 2 or 3, chosen by seed, so the order is balanced by
     design.
   - *Reference:* round-1 S03 is rendered on 2 of the 10 clips' music (seeded), 20 s, round-1 network and inputs unchanged, cortex lanes
     computed from that audio.

### 7.51 Retarget look test: pillar mount instead of smaller motion, 2026-11-13, via Kosta + planner (answering `docs/PLANNER_BRIEF_RETARGET_FLOOR.md`)

1. **Record (Q2).** The retarget look test was blocked: over the first 200 seeded 20 s windows, V1 passed 2, V2 13, both 1 (10 needed);
   contact 194 (V1) and 161 (V2); the hand minimum sat at the 0.11 m gate floor. Nothing was rendered or viewed.
2. **Planner reading (Kosta did not dispute):** the failure is body geometry, not scaling. Human arm motion uses the space below the
   shoulder; the robot's shoulder sits just above a table. Options (a)-(c) of the brief all remove that half of human movement.
3. **Decision (Kosta): change the mount, not the motion.**
   - A. **Pillar mount** (new body variant "v2p"): replace the raised plane with a vertical column whose top is the base footprint + 2 cm per
     side; the floor is 1.0 m below the column top. Everything else in v2f is unchanged (servos, limits, end stops, self-collision). Contact
     with the column counts as contact for the gates. Rule fixed before any render.
   - B. **Retargeting on v2p:** V1 and V2 as in `docs/RETARGET_RULES.md`, scaling share 80 % as written, centre = round 1's centre. No other
     change.
   - C. **Floor guard (option b) as a BACKSTOP only:** clamp commands so the hand stays >= 0.05 m from the column and links do not enter it.
     Log the fraction of frames where the guard engages, per clip. If it engages in more than 10 % of frames for a clip, that clip fails the
     gate. Never rely on it to pass.
   - D. Gate the seeded stream of 20 s windows on v2p for both variants as before; 10 passing in both are needed; report pass counts and
     discards by gate.
   - E. If fewer than 10 pass in both variants within 200 candidates: hold and report. No fallback to the share ladder without Kosta.
   - F. Then render and run Kosta's blind session exactly as 7.49.5: FineDance music, lamp head, round-1 S03 reference on 2 songs (S03 re-gated
     on v2p too), pair order checked to be mixed. Camera: same framing, column visible, the column top at the old table height in frame.
4. **Datasets:** AIOZ-GDANCE and AIST++ (downloaded) are not used in this test. Motorica stays blocked (login) unless Kosta says otherwise.
5. **Out of scope:** training, gain modulation, feedback learning, cortex changes, hardware, brain monitor, uploads. Standing rules unchanged.
6. **Overseer notes (operational defaults, not rulings; Kosta may amend):**
   - *Clearance gates on v2p:* the old table rule (links >= 0.05 m and hand >= 0.11 m above z = 0) becomes: no link point inside the column
     or within 0.05 m of it, hand >= 0.05 m from the column (C), and all points >= 0.05 m above the floor. Other gates as 7.44.
   - *Column shape* follows the base footprint (a disc gives a cylinder, a square a square column), stated in the rules note; it rises from
     the floor to the old table plane, so the base sits exactly where it sat.
   - *Guard mechanism* is stated in a dated rules note before any render. Default: when the commanded pose's FK breaks the C margins, hold
     the last safe command for that frame. Engagement = the share of 100 Hz command frames held.
   - *Scale:* `docs/RETARGET_SCALE.json` unchanged. The seeded clip stream restarts from candidate 1.

### 7.52 Retarget look test: limiter overshoot first, then a look-test tolerance of 1.25 and a spread pick rule, 2026-11-13, via Kosta + planner (answering `docs/PLANNER_BRIEF_RETARGET_LIMITS.md`)

1. **Record (Q4).** On v2p (7.51), 145 candidates gave 10 passing in both variants, but 7 of the 10 were windows of one Kunqu opera sequence
   (FineDance seq 028) and 12 of 16 genres, every street style included, passed 0 of 9. The session was held by the overseer; nothing was
   shown to Kosta. Failures were almost all shoulder acceleration (V1 132, V2 97); median realised shoulder acceleration / limit 1.24 (V1),
   1.14 (V2); median commanded shoulder acceleration 22x (V1) and 9x (V2) the limit. In 6 % (V1) and 19 % (V2) of candidates the command
   limiter's own shoulder output exceeded the acceleration limit, up to 5.5x, cause unchecked. Pass-both counts at tolerance 1.05 / 1.25 / 1.5:
   10 / 43 / 93 (genres 4 / 15 / 16, sequences 4 / 30 / 63).
2. **Q3 first, before any re-render:** agent 1 finds why the limiter's own shoulder output exceeds the acceleration limit.
   - If it is a bug: fix it and record the fix in a dated rules note. This is not a design choice and needs no ruling.
   - If it is not a bug: report the cause and HOLD (no re-gate, no render) until Kosta rules.
3. **Q1 (a): speed and acceleration tolerance 1.25 x limit, for this look test only** (simulation, no hardware). It is a **look-test
   exception, not a new hardware margin**; every other gate is unchanged (contact, clearance, end stops, guard > 10 %, > 8 Hz share, minimum
   motion).
4. **Q2: pick rule:** at most one window per FineDance sequence and at most two per genre (genres case-insensitive, 16), taken in the same
   seeded stream order (seed 32011, restarted from candidate 1); both variants must pass.
5. **Then:** re-gate (with the Q3 fix) -> re-pick 10 -> render -> Kosta's blind session as 7.49.5 / 7.51 F. **Report per clip:** commanded vs
   realised shoulder acceleration and the limiter's share of the command, so Kosta can see how much of the human motion was cut.
6. **For the record (planner reading, Kosta did not dispute):** human dance commands 9-22x the provisional shoulder servo's acceleration.
   If the look test passes, the real arm likely needs a stronger or higher-geared shoulder actuator than the STS3215. Hardware decision
   deferred; flagged.
7. Standing rules unchanged.
8. **Overseer notes (operational defaults, not rulings; Kosta may amend):**
   - *Limiter overshoot definition:* the shoulder acceleration of the limiter's output, computed exactly as the gate computes realised
     acceleration (same differencing and filtering), over the limit. The report names the code lines and shows the fix on the worst candidate
     (5.5x) before and after.
   - *A fix that changes the limiter's output* re-gates the whole stream from candidate 1; the old gating log is kept, not overwritten.
   - *Per-clip numbers:* commanded / realised shoulder acceleration as p50, p95 and max over the clip, both as multiples of the limit; the
     limiter's share = the share of 100 Hz frames where the limiter changed the shoulder command, plus the RMS of (command - limiter output) on
     the shoulder in degrees. Both variants; in `numbers.json` and the session report.
   - *Reference:* round-1 S03 is re-gated at the same 1.25 tolerance on v2p on the 2 seeded songs; a failing reference is logged, not replaced.
   - *Pair order:* V1 first in exactly 2 or 3 of the 5 pairs (7.50.8), checked before the session.
   - *Fewer than 10 picks within 200 candidates under the pick rule:* HOLD and report counts; no relaxation without Kosta.

### 7.53 Retarget look test results; jitter diagnosis next, 2026-11-13, via Kosta + planner (answering `docs/PLANNER_BRIEF_RETARGET_RESULTS.md`)

1. **Record (Q4).** Look test (7.49.5 / 7.51 / 7.52) at the 1.25 look-test tolerance, 10 clips from 10 FineDance sequences in 9 genres:
   singles V1 yes 4 / sort of 6 / no 0, V2 2 / 8 / 0, round-1 S03 reference 0 / 2 / 0; pairs V1 3, V2 2. **No "no" answer.** C04_V2 is the
   first clip Kosta rated above v47 ("its actually good"). The 7.52.6 shoulder-actuator note stands (human dance commands 9-22x the STS3215
   shoulder acceleration; a stronger or higher-geared shoulder is likely needed; hardware decision deferred). Report:
   `docs/RETARGET_REPORT.md`.
2. **Planner reading (Kosta did not dispute):** imitation of human dance works on this body in principle.
3. **The next problem (Kosta, verbatim):** "micro-movements, too frequent changes of direction, robotic unhuman stuff ... it is a robot
   dancing, but it is dancing for a human audience".
4. **Q2 (a):** keep V1 and V2.
5. **Q3: record only.** Energy/timing-vs-song notes belong to step 3 (music conditioning). C03_V1 "too low" is recorded for later.
6. **Q1 (a): JITTER DIAGNOSIS, report-only, the same 20 clips.**
   - Measure at each stage: (1) raw FineDance motion after retargeting at 30 fps; (2) after 30 -> 100 Hz resampling; (3) after the limiter;
     (4) after the servo/body (realised).
   - Per stage and per joint: acceleration sign changes per second, jerk RMS, share of joint-speed power above 3 Hz and above 6 Hz.
   - Hypotheses, each reported separately (which stage adds what; adopt nothing):
     - **H1, missing muscle-like layer:** the retarget pipeline ran without the spinal spring-damper. Re-run stages 3-4 with the round-1
       spinal layer (3 Hz, zeta 0.7) inserted before the limiter.
     - **H2, limiter saturation chatter:** report the fraction of frames where the limiter output sits at +- the acceleration limit, and how
       often it flips sign.
     - **H3, resampling:** re-run with a smooth interpolant and compare (builder states which).
   - Report each hypothesis separately and combined (H1 + H3). No verdict. **Then STOP;** Kosta rules on a fix.
   - After the ruling: a blind re-look of 4-6 clips (must include C04_V2 and C10_V1), old vs fixed in pairs, pair order checked to be mixed.
7. **Out of scope:** training, music conditioning, gain modulation, hardware, monitor, uploads. Standing rules unchanged.
8. **Overseer notes (operational defaults, not rulings; Kosta may amend):**
   - *H3 premise:* the resampling is already a cubic spline (`scripts/body/retarget.py` `to_100hz`, `CubicSpline`), not linear
     interpolation, so it does not put acceleration impulses every 33 ms. H3 is therefore run as: stage 2 vs stage 1 numbers (what the
     cubic spline adds), plus a linear-interpolation control to show the size of the effect the hypothesis describes. "H1 + H3 combined"
     = H1 with the cubic spline as used. No new interpolant is adopted or tuned.
   - *Like-for-like rates:* every measure is computed at each stage's own rate, and stages 2-4 are also sampled at the 30 fps instants, so
     stage 1 compares like for like. Jerk RMS is in deg/s^3. Power shares are of the joint-speed spectrum (mean removed) over 0.2 Hz.
   - *H1 spinal layer:* `scripts/body/motornet.py` `spinal` unchanged (3 Hz, zeta 0.7, as round 1), applied to the 100 Hz command before the
     fixed limiter of 7.52 (rules note (k)).
   - *H2 "at the limit":* |limiter output acceleration| >= 0.98 x the limit, on the 100 Hz frames and on the gate's 50 Hz measure; sign flips
     per second of the limiter output acceleration.
   - *Control:* the 2 round-1 S03 reference clips are measured at stages 3-4 as they are (they have no stages 1-2).
   - *Gates:* every variant run is also gated as 7.52 (1.25), and the pass/fail is reported, not used to select.

### 7.54 Jitter comes from the retargeting; space retarget V3; Q1 session held, 2026-11-13, via Kosta + planner (answering `docs/PLANNER_BRIEF_JITTER.md`, then superseding its Q1)

1. **Record (Q3).** Jitter diagnosis (`docs/JITTER_DIAGNOSIS.md`, report only), medians over the 20 look-test clips:

   | stage | acceleration sign changes per second, shoulder | wrist bend |
   |---|---|---|
   | stage 1, human command at 30 fps | 7.3 | 11.6 |
   | cubic spline to 100 Hz | 9.1 | 14.6 |
   | limiter | 4.2 | 9.0 |
   | realised | 2.7 | 5.0 |
   | H1 (round-1 spinal layer before the limiter), realised | 2.4 | 3.65 |
   | round-1 S03 reference | about 1 | about 1 |

   The limiter sits at its acceleration limit in 62 % of shoulder frames. The 7.53 H3 premise was false: the resampling was already a cubic
   spline (overseer note 7.53.8). Linear vs cubic interpolation differ little at the realised stage.
2. **Kosta, after watching the viewing video** (`/secondary/hyst-data/body/retarget_look/jitter/viewing/jitter_viewing.mp4`; C05_V1 and
   C04_V2, four panels): the human dancer's hand (V1 source) and spine (V2 source) do not jitter at all; at most a wrist flick, a real human
   gesture. **Therefore the jitter is created by the retargeting, not by the dance or the servo.**
3. **HOLD** the Q1 old-vs-H1 / H1 + low-pass session. **Q2 stands:** report-only check of the C04_V2 steady shoulder offset (about 10 deg).
4. **STEP A, report-only:** for the same 20 clips, direction changes per second and power above 3 Hz for:
   - (0) the human source end point in world space from FineDance forward kinematics: right hand position (V1), head / upper-spine position
     (V2);
   - (1) the retargeted joint angles (stage 1), as already measured.

   **Planner hypothesis:** (0) is smooth and (1) is not, because per-joint angles in the data wobble in ways that cancel in world space;
   copying single angles onto different kinematics removes the cancellation.
5. **STEP B, new variant V3 "space retarget"** (rules fixed in `docs/RETARGET_RULES.md` before any render):
   - V3a: the lamp's position follows the human right-hand path. V3b: the lamp follows the head / upper-spine path.
   - Both are taken relative to the human shoulder (V3a) or pelvis (V3b), scaled uniformly so the human's p2-p98 reach fills 80 % of the
     arm's reach, then offset to the arm's workspace centre.
   - Lamp orientation follows the human hand (V3a) or head (V3b) orientation, only in the two axes the wrist has.
   - Joint angles by damped least-squares inverse kinematics on the v2p arm, warm-started from the previous frame, with a small penalty on
     joint change per frame (weight fixed in the rules, not tuned by eye). Joint limits and column clearance are enforced in the solve.
   - Then the existing pipeline: round-1 spinal layer (H1) before the limiter, limiter, servo, v2p body, gates at 1.25.
   - Report the same jitter measures per stage as the diagnosis.
6. **STEP C, blind look** (only after Kosta sees the Step A/B numbers and says go):
   - the same seeded clips as the look test, where they pass;
   - 6 pairs: V3 vs the look-test version of the same variant (V3a vs V1, V3b vs V2), pair order checked to be mixed;
   - question "which looks more like a person dancing?" with first / second / same, and an optional note.
7. **Out of scope:** training, music conditioning, gain modulation, limiter redesign, hardware, monitor, uploads. Standing rules unchanged.
   Q2 of the brief (keep V1 and V2) already stands from 7.53.
8. **Overseer notes (operational defaults, not rulings; Kosta may amend):**
   - *End points:*
     - "right hand" = FineDance SMPL-H right wrist joint (index 21);
     - "head / upper spine" = the head joint (15);
     - the "pelvis" (0) and the "right shoulder" (17) are the origins.
   - *FK:* FK uses the same canonical T-pose offsets as the viewing video (WO34, stated in the rules note). FineDance ships no body model
     and none is downloaded (7.50.8). Scale cancels in the reach normalisation.
   - *Step A columns:*
     - (0w) end point in world space (root translation included);
     - (0r) end point relative to its origin (shoulder for V1, pelvis for V2), the signal V3 actually follows;
     - (1) stage-1 joint angles;
     - (1e) the robot lamp position by arm FK of the stage-1 angles, which compares end point with end point.

     For a 3D position the measures are per axis (direction changes per second as acceleration sign changes per axis, the jitter_diag
     counting rule; power above 3 Hz and above 6 Hz of the speed vector), reported per axis and as the mean over axes.
   - *Reach and centre:*
     - the human p2-p98 reach = the 98th percentile of the end point's distance from its origin, pooled over the same 4,603 eligible
       windows as `RETARGET_SCALE.json`; one scale per variant, written to `RETARGET_SCALE.json` as new keys (old keys unchanged);
     - "the arm's reach" = the distance from the shoulder joint (p1) to the lamp centre at full extension;
     - the workspace centre = the lamp position at round 1's centre pose (base 0, shoulder -60, elbow 30, wrist bend -15, roll 0);
     - the scaled human end-point offset is added there (direction kept, the human's forward axis mapped to the robot's base-0 forward).
   - *IK:*
     - IK runs at 100 Hz on the end-point path, cubic-spline resampled (as now);
     - DLS damping lambda, the per-frame change penalty, the orientation weight (position first, orientation secondary) and the iteration
       count are fixed as numbers in the rules note, from a rule stated before any render (e.g. the change penalty set so that a stationary
       target gives zero motion and a 1 cm target step moves the joints by at least 90 % of the exact solution); never tuned by eye;
     - joint limits by clamping inside the solve, column clearance by a penalty plus projection, with the guard of 7.51 as backstop;
     - frames where the solver ends with residual error > 2 cm are counted and reported per clip.
   - *Clips:* Step B runs the same 10 seeded windows (V3a and V3b each), gated at 1.25. Pass/fail is reported; nothing is re-picked.
   - *Step C pairs:* from the passing clips, seed 32061, 3 V3a-vs-V1 and 3 V3b-vs-V2, always including C10 (V3a vs V1) and C04 (V3b vs V2)
     when they pass (Kosta's earlier re-look picks); V3 first in exactly 3 of 6.
   - *The C04_V2 offset check (Q2)* is part of the same work order, report-only.
9. **Overseer correction to 7.54.8, 2026-11-13 (before any V3 run; flagged to the planner in the next brief):**
   - **Workspace centre.** Round 1's centre pose puts the lamp 0.673 m from the shoulder joint p1, and the arm reaches 0.69 m. That
     "centre" sits 1.7 cm inside the edge of reach, so most motion around it would be unreachable. The 7.54.8 default "centre = lamp at
     round 1's centre pose" is withdrawn.
   - **Replacement:** the human origin (right shoulder for V3a, pelvis for V3b) maps onto the robot's shoulder joint p1. Lamp target =
     p1 + s x A x rel, with no median shift. With the uniform scale of 7.54.5 (human p98 reach -> 80 % of the arm's reach), 98 % of the
     targets lie within 0.55 m of p1, inside the 0.69 m reach by construction. This is the literal reading of "relative to the human
     shoulder / pelvis, scaled so the reach fills 80 % of the arm's reach": for a reach measured from p1, the workspace centre is p1.
   - **Consequence, stated:** V3b's lamp sits mostly high (head about 0.6 m above the pelvis -> about 0.54 m above p1). V3a's lamp often
     hangs below p1 beside the column (arm at the dancer's side), handled by the column penalty, projection and guard. Both are counted and
     reported, never tuned.
   - **Builder's rules note (m) (body-v3 66e72b4), reviewed:** the heading frame (pelvis yaw removed), the orientation projection, the IK
     numbers from stated rules (damping 3.604e-4 from the 90 % step rule, lam 1 % of reach, mu, w_o 0.05, w_c 1, step cap 0.351 rad,
     N = 3 from the 1 cm and 5 cm probes run before any clip) and the scales (V3a 1.0824, V3b 0.8909) are accepted. The median-centred
     offset at c0 in (m) is replaced by the line above.
   - **Q2 answered (WO35, report only):** the C04_V2 shoulder offset is gravity sag in the servo model: mean +4.8 deg (-4.4 to +12.4) over
     seconds 8-12, +0.1 deg with gravity off, 5.3 deg predicted from gravity torque 1.55 N m / kp 16.86 N m/rad. Not the limiter, guard, end
     stops or column.

### 7.55 V3 closed; joint-space low-pass to the human's own smoothness, then the blind re-look, 2026-11-13, via Kosta + planner (answering `docs/PLANNER_BRIEF_V3.md`)

1. **Record (Q4).**
   - **Step A:** the human end point (right wrist relative to the right shoulder for V1, head relative to the pelvis for V2) carries 3-5x
     less speed power above 3 Hz than the retargeted angles. Median over 20 clips: 0.031 in world space, 0.048 relative to the origin; the
     lamp path under the stage-1 angles 0.150; the angles 0.129. This confirms Kosta's viewing judgement.
   - **Q2:** the C04_V2 shoulder offset is gravity sag in the servo model, about 5 deg on the shoulder. Hardware note: the real shoulder needs
     higher stiffness as well as torque (see 7.52.6).
   - **Step B:** V3 passed 0/20 gates at 1.25. The causes are geometry (V3b shoulder on its -110 deg stop with the arm pointing up; V3a
     folding into the column, elbow and wrist at their stops) and IK noise (IK output 9.5-14.3 direction changes per second). Realised V3 was
     about equal to V1/V2 + H1. The target mapping was a planner spec error.
   - **Step C** did not run.
2. **Q3:** 7.54.9 confirmed (the human origin maps onto the shoulder joint p1).
3. **Q2:** the V3 code and report are merged as a report-only tool. They are not in the look-test path. **No V3 round 2.**
4. **Q1 (a), the fix to test:**
   - A zero-phase low-pass on the stage-1 angles of V1 and V2.
   - **Cutoff by the stated rule:** the cutoff at which the lamp path under the filtered angles has no more power above 3 Hz than the human
     end point it came from (median over the clips), computed per variant and stated in the rules file before any render.
   - H1 kept (the round-1 spinal layer before the limiter). Gate at 1.25. The jitter measures are reported per stage as before.
   - **Blind re-look:**
     - C04_V2 and C10_V1, plus 2-4 more by seeded pick (a clip whose fixed version fails the gate is replaced by the next seeded pick,
       reported);
     - pairs old vs fixed, order checked to be mixed;
     - question "which looks more like a person dancing?" with first / second / same, and an optional note.
5. **After the session: report and stop.** If Kosta judges the fixed version at least as good, this pipeline becomes the training-data
   pipeline and the retargeting work ends; the planner then writes the imitation-training plan (7.49 a). No further retarget variants
   without Kosta's ruling.
6. **Out of scope:** training, music conditioning, gain modulation, limiter redesign, hardware, monitor, uploads. Standing rules unchanged.
7. **Overseer notes (operational defaults, not rulings; Kosta may amend):**
   - **Cutoff wording, corrected.** The brief and the ruling say "the *lowest* cutoff at which the filtered lamp path has no more power above
     3 Hz than the human". A lower cutoff always smooths more, so that wording would select the bottom of any search range. The wording error
     was the overseer's (`PLANNER_BRIEF_V3.md`). The intended rule is **the highest cutoff (the least smoothing) at which the median over the
     variant's clips of the lamp path's power share above 3 Hz is <= the median of the human end point's**.
   - **Human reference:** the end point relative to its origin, column (0r) of Step A (right wrist relative to the right shoulder for V1,
     head relative to the pelvis for V2). This is the signal the retargeting maps from.
   - **Filter:** 2nd-order Butterworth applied forward and backward (`scipy.signal.filtfilt`, zero phase), at 30 fps, on the stage-1 angles
     (base yaw and wrist roll unwrapped). It runs over each whole sequence before windowing, so no window-edge effects.
   - **Cutoff search:** grid 0.5-14.5 Hz in 0.25 Hz steps; measured on the 10 look-test windows of each variant. The chosen value, the curve
     (cutoff vs median power) and the human medians go into the rules note before any render.
   - **Re-look clips:** C04_V2 and C10_V1, plus 4 more by seeded pick (seed 32071) from the other 18 shown clips, so 6 pairs in total. A
     clip whose fixed version fails the 1.25 gate is replaced by the next seeded pick, and the replacement is reported. "Old" = the
     look-test mp4 as shown (stage 4 baseline, no H1). "Fixed" = low-pass + H1, rendered with the same camera, lamp head, column and music.
     The fixed version plays first in exactly 3 of 6 pairs.
   - **Tool:** in look-test mode, pair answers are "first / second / same" (the tool's current "neither" is renamed for look-test pairs
     only; other modes unchanged; a test covers it).

### 7.56 Re-look closed; low-pass + H1 is the training-data pipeline; imitation-training plan (7.49 a), 2026-11-14, via Kosta + planner (answering `docs/PLANNER_BRIEF_LOWPASS_RELOOK.md`)

1. **Record.** Re-look (6 pairs): low-pass + H1 picked 4, old 1, same 1. Four of six answers were noted "close / unsure". The remaining
   jitter is not removed: low-pass + H1 stays 3-4x the round-1 S03 references on acceleration direction changes.
2. **Q4:** the highest-cutoff rule of 7.55.7 is confirmed (the 7.55 wording "lowest" was an error); V2 cutoff 5.75 Hz and V1 2.50 Hz stand
   as recorded.
3. **Q1 (a):** low-pass + H1 meets 7.55.5. It is the training-data pipeline. **Retargeting work ends.**
4. **Q2 (a):** the remaining jitter is a known gap, judged again on the trained model's output.
5. **Q3 (a):** training windows are gated the same way (1.25 look-test tolerance); failures are dropped and counted.
6. **Imitation training plan (planner proposal; items marked DEFAULT are Kosta's to strike).**
   - **Retarget variant:** V2 (DEFAULT; Kosta may choose V1). One model, one variant.
   - **Data:** FineDance public part only (DEFAULT). Split by SEQUENCE and by SONG: no song in both train and test. 15 % of songs held out
     for test, 10 % for validation, seeded. Kosta's check songs are never used for training or tuning.
   - **T0, data pipeline (no training):**
     - run the frozen cortex (B7 epoch 6) on every FineDance song locally: beat-band phase (cos, sin), arousal_b7, ear energy (formula as
       recorded), L4 slow-state projection (fixed random, 4 dims); 100 Hz;
     - retarget all sequences with the low-pass + H1 pipeline, target stage (joint targets before the limiter), aligned to the cortex lanes
       at 100 Hz;
     - gate 20 s windows as Q3; report counts kept / dropped per genre;
     - report total usable hours.
   - **T1, model (fixed in a rules note before training):**
     - motor-cortex recurrent network, 256 rate units (tau 75 ms); inputs = the cortex lanes above + its own previous output
       (autoregressive) + a proprioceptive copy of the previous joint target;
     - 4 gain-control units as in the toy tests, driven by a small learned map from [energy, arousal_b7, L4 slow state]; they scale the
       gains of overlapping neuron subsets. Trained jointly here. Later Kosta-feedback learning trains ONLY this map (core frozen);
     - output: a mixture-density head (e.g. a 5-component Gaussian mixture) over the next joint-target step, sampled at run time (plain
       average-error training is known to collapse dance to a frozen mean pose);
     - training: truncated backprop through time on the laptop CPU (state threads); Kaggle T4 only if CPU is impractical (estimate reported
       first). Early stopping on validation likelihood.
   - **T2, checks before Kosta sees anything (numbers reported; stop rules):**
     - on held-out songs: joint range p5-p95 per joint vs the human data (stop if any joint < 50 % of the data's); jitter measures vs the
       training data (stop if > 1.5x); a beat-alignment score (a standard one from the music-to-dance literature; the builder states which)
       vs the human data on the same songs; between-song difference (stop if the model's outputs on different songs differ less than the
       human data's, by a stated measure); frozen-pose check (stop if hand speed < 0.05 m/s for > 3 s anywhere);
     - gates at 1.25 through limiter, servo, v2p body.
   - **T3, Kosta's blind look (only after Kosta has seen the T2 numbers and says go):** 6 held-out songs, 20 s: model vs retargeted human
     (same song) vs round-1 S03; singles "does this look like dancing?" + pairs model vs human "which looks more like a person dancing?".
     Then the model on Kosta's 5 check songs, singles only.
   - No verdict from builder or overseer. Kosta decides.
7. **Out of scope:** Kosta-feedback learning, limbic module, hardware, monitor, uploads, other datasets. Standing rules unchanged.
8. **Overseer notes (operational defaults for T0, not rulings; Kosta may amend):**
   - **Songs, not sequences.** FineDance has 203 motion sequences but 181 distinct song names (label_json `name`, compared stripped and
     lower-case); 22 songs have two sequences (e.g. killthislove 006/200, gudian1 022/032). The split unit is the song; both sequences of a
     song go to the same split. The builder also hashes the decoded audio (mono 44.1 kHz) and merges any two names whose audio is
     identical, reported. Split: seeded shuffle of songs, seed **33001**; test = round(0.15 x songs), validation = round(0.10 x songs), the
     rest train (181 songs -> 27 / 18 / 136). Genre counts per split are reported. FineDance's own @Genre split is not used (the ruling
     asks for a seeded split).
   - **Check songs:** Epitaph, 21st Century Schizoid Man, One of These Days, Breathe, Blue Lagoon (7.47 round 1); also the three danced
     songs (Instant Crush, Five Years, Presence). None is in FineDance; T0 asserts no name or audio-hash match.
   - **Cortex lanes, same recipe as the toy rounds** (`scripts/body/motornet_part3.py` / `motornet_music.py` / `motornet2_lanes.py`):
     FineDance `music_wav` -> ffmpeg mono 44.1 kHz; beats by `analyze.structure.analyze_mix`; `b2.build_inputs`; B7 epoch 6 =
     `/secondary/hyst-data/brain/b7/ckpt/phase/epoch_006.pt`, state carried across 6000-frame chunks. Before any FineDance run the builder
     reproduces the stored lanes of one check song and one danced song (max abs difference reported).
     - beat-band phase = `l3_cos`, `l3_sin` (cortex lane y columns 2, 3), as in MOTORNET2_RULES;
     - arousal_b7 and the L4 state at frames 9::10 (10 Hz), linearly interpolated to 100 Hz;
     - L4 projection: the toy-2 matrix (seed 30002, 512 x 4);
     - ear energy: `scripts/body/ear_energy.py` as recorded (`EAR_ENERGY_RULES.md`, fixed norm constants), 10 Hz lane interpolated to 100 Hz;
     - standardisation of L4 projection and arousal_b7: one mean and sd per signal pooled over the TRAIN songs only, clipped +-3 (the toy
       rounds pooled the three danced songs; training needs train-split statistics). Constants written once to a JSON file.
   - **Retarget targets:** both V1 (2.50 Hz) and V2 (5.75 Hz) are produced in T0 (cheap; keeps Kosta's variant choice open), each as the
     H1 spinal-layer output at 100 Hz (the stage before the limiter), from the same code as WO36 (`body-lowpass`, merged). Motion frame k
     is at k / 30 s; music time 0 = motion frame 0 (look-test audio offset 0.0 s). Lanes and targets cut to the shorter length.
   - **Windows:** non-overlapping 20 s windows from each sequence start; a tail under 20 s is dropped and counted. Each window gated
     through limiter, servo, v2p body at 1.25 (all parts: limits, end stop, contact, clearance, guard), per variant. Kept windows are the
     training segments; no state is carried across a dropped window.
   - **Report:** per variant, per split and per genre: windows kept / dropped by failed part, usable hours; cortex lane coverage; run time.
   - **Compute:** each long step in its own detached systemd unit with MemoryMax, 8 threads (§0); a time estimate from one song before the
     full run; T0 stops at its report. T1 starts only after the overseer has reviewed T1's rules note and Kosta has seen the T0 numbers.
9. **Kosta's amendments, 2026-11-14 (strikes the DEFAULT "FineDance only"):**
   - **AIOZ-GDANCE is added, checked and pruned first.** Licence wording ("non-commercial artistic projects") matches FineDance's
     (`DATASET_LICENCES.md`). T0 runs a report-only validity check on AIOZ before it enters any training set, with the prune rule stated
     in `T0_RULES.md` before any AIOZ number is looked at (overseer defaults below). AIOZ hours are always reported separately.
   - **V1 and V2 together** (Kosta's question: both variants as one training set, "human dance movement in general"). Not decided; T0 makes
     both, so it is a T1 question for the planner. Overseer note for that brief: the two variants are the same human motion mapped two ways,
     not twice the motion; the same robot joint means different body parts in each (e.g. shoulder = arm shoulder in V1, torso lean in V2).
     Mixed without a label, the model would switch between the two mappings unpredictably; with a variant input (0/1), it can share timing
     to music across both and be run in either. The ruling "one model, one variant" would change.
10. **Overseer defaults for AIOZ in T0 (not rulings; Kosta may amend):**
    - **Safety:** the `.pkl` files are untrusted; open them only with a restricted unpickler that allows numpy arrays and plain containers
      and nothing else (a test proves a crafted pickle is refused).
    - **Format:** `smpl_poses` (persons x frames x 72, SMPL 24 joints axis-angle), `root_trans`. The frame rate is not stated: the builder
      derives it from music length / frame count on every sequence and reports the distribution; a sequence off by > 2 % from the mode is
      dropped and counted. Each person is a separate sequence; the first 22 SMPL joints map onto FineDance's SMPL-H body joints (same
      order) for the existing retarget code, the adapter tested on a FineDance sequence converted to axis-angle and back (max abs angle
      difference reported).
    - **Song unit:** the YouTube id (first name field); all clips and persons of one id go to the same split. AIOZ's own split files are
      not used; one seeded split (seed 33001) over FineDance songs and AIOZ ids together, same 15 / 10 % shares, with the audio-hash check
      against FineDance and the check songs.
    - **Validity check (per person-sequence, before the low-pass), report-only, with FineDance as the reference distribution:**
      (1) human end-point power above 3 Hz (the Step A measure, both end points); (2) share of frames where any body joint's angular speed
      exceeds FineDance's p99.9 for that joint; (3) root jumps: share of frames with root speed above FineDance's p99.9; (4) frozen
      frames: share of frames with all joints still (< 1 deg/s). Also the per-person mean height and its vertical drift.
    - **Prune rule:** drop a person-sequence if (1) is above FineDance's p95 for either end point, or (2) or (3) exceeds 1 % of frames, or
      (4) exceeds 20 %. Counts dropped per reason and per style are reported. The remaining AIOZ data then goes through the same
      low-pass (V1 2.50 Hz, V2 5.75 Hz, the cutoffs are NOT recomputed), H1, windows and 1.25 gates as FineDance; the lamp-path power
      above 3 Hz of AIOZ vs FineDance after the low-pass is reported.
    - The AIOZ check report is a stop point: T0 continues to the full AIOZ run only if at least 30 % of AIOZ person-sequences survive the
      prune; otherwise "HOLD aioz <share>", and FineDance continues alone.
11. **Kosta's ruling, 2026-11-14 (replaces "one model, one variant" in point 6 and settles the open question in 9):** V1 and V2 of every
    clip go into ONE training set as separate examples, with **no variant label**. Kosta: the body and the arm move very differently but
    both are valid; a dance is not one solution, it is freedom; one style at run time, with the mixture head's sampling as its freedom.
    Both versions of a clip are always in the same split (the split unit is the song). Overseer note (report only, not a stop rule): T2 also
    reports, per 20 s output window on held-out songs, the distance to the nearest V1 and the nearest V2 target window of the same song,
    so Kosta can see whether the model uses both, switches, or averages them; the existing T2 stop rules (range < 50 %, frozen pose) cover
    collapse to a mean pose.

### 7.59 Imitation training redesigned: motor vocabulary + sequencer (Bailando family), 2026-11-14, via Kosta + planner

**Supersedes** the training-plan parts of 7.56 (points 6-7 and 11's T2 note: T1-T3, the per-step motor RNN, gain units, mixture head)
and the unrecorded 7.57 (chunk mixture head) and 7.58 (phrase planner); neither was ever recorded here. The 7.56 re-look decisions
(points 1-5) stand. 7.56.9-11 (AIOZ added, V1 + V2 pooled without a label) are carried into this entry. Decisions are Kosta's; items
marked PROPOSAL were accepted by Kosta unless struck.

1. **Why this design.**
   - Kosta's requirements: actual dance that fits humans, with phrase-level planning and repetition across about 10 s, and an architecture
     that can actually be trained here.
   - Rejected: per-step motor RNN with gain units, mixture-density chunk head, jointly learned phrase latents (they stack untested parts;
     next-pose models are known to collapse to frozen or mean poses).
   - Families compared: A learned motion vocabulary + sequencer (Bailando, CVPR 2022, arXiv 2203.13055); B diffusion over the 5-joint
     sequence; C retrieval of human clips matched to music. **A chosen**: the only option strong on looks, learning and brain mapping, with a
     clean slot for Kosta-feedback learning later.
   - Switch rule: if Kosta's S1 rebuild check (point 4.2) fails even with the residual fallback, the next design is B, scaled to 5 joints
     (needs a ruling).
   - Brain mapping, for the record: vocabulary = learned motor chunks (basal ganglia chunking, Graybiel 1998); sequencer = premotor
     planning + action selection; vigour = movement vigour; posture vs gesture = postural vs focal movement control; cortex = frozen
     auditory cortex (B7 epoch 6).
2. **Data (T0).**
   1. Sources: FineDance public part + AIOZ-GDANCE. Licences as recorded in 7.50 (`DATASET_LICENCES.md`).
   2. Retargeting: the low-pass pipeline of 7.55/7.56: stage-1 angles, zero-phase low-pass (V1 2.50 Hz, V2 5.75 Hz), cubic spline to
      100 Hz. **Training targets are joint targets BEFORE the spinal layer (H1) and the limiter.** Spinal layer, limiter, servo and v2p body
      are applied only when rendering or gating.
   3. V1 and V2 pooled with no label: every clip gives two training examples. Plus **mirror augmentation**: left/right mirror of the human
      motion before retargeting (V1 uses the left arm when mirrored; base yaw sign flips). Counted separately.
   4. AIOZ prune rule, fixed before any AIOZ number is seen. Drop a dancer if any of: wrist/head path power above 3 Hz > FineDance p95;
      > 1 % of frames with joint or root speed > FineDance p99.9; > 20 % of frames frozen. If < 30 % of AIOZ dancers survive, AIOZ is
      dropped. FineDance cutoffs reused. Hours always reported per dataset.
   5. Split: one seeded split over both datasets by song (FineDance) / YouTube id (AIOZ): **75 % train, 10 % validation, 15 % test**. No
      song in two splits. Kosta's 5 check songs never used for training or tuning.
   6. Weighting: cap each song's (YouTube id's) total training weight at the weight of its single longest dancer, so multi-dancer group
      songs do not dominate.
   7. Gating: 20 s windows rendered through spinal layer, limiter, servo, v2p body at the 1.25 look-test tolerance. Failing windows
      dropped and counted per dataset and genre.
   8. Music features, from the music only (frozen cortex run locally on every song), per 0.5 s token (pooling fixed in the rules before
      training): pooled 44 ear features; cortex summary (per-layer pooled mode amplitudes in 8 groups x 4 layers, surprisal per layer,
      arousal_b7); ear energy (formula as recorded); beat-band phase cos/sin at token start and middle.
   9. Posture/gesture split of every target sequence: posture(t) = zero-phase low-pass of the joint targets, cutoff 0.5 Hz;
      gesture(t) = target(t) - posture(t).
   Report: usable hours per dataset after pruning and gating, tokens per split.
3. **Model.**
   1. **T1a motor vocabulary (stage 1):** vector-quantised autoencoder over 0.5 s GESTURE chunks (50 steps x 5 joints at 100 Hz). Each
      chunk is normalised by its amplitude; the amplitude is the token's "vigour" scalar; shape and timing (snap vs smooth) stay in the
      code. Codebook size by rule: train 128, 256, 512 and 1024; choose the smallest whose validation reconstruction error is within 5 % of
      the next larger one; report error and code usage for all four. EMA codebook updates with dead-code reset. Decoder: convolutional,
      sees neighbouring tokens so joins are smooth, causal with at most 0.25 s lookahead. Fallback (needs a ruling): 2-stage residual
      quantisation (coarse + correction).
   2. **T1b sequencer (stage 2):** GRU, 256 units, stepped once per token (2 per second). Inputs: the current token's music features;
      embedding of its previous code, its vigour and its posture; single-head attention over its own last 32 tokens (16 s), its memory for
      planning and repetition. Outputs per token: categorical over the codes; log-normal over vigour; Gaussian over the change in posture
      (5 joints) for the next 0.5 s. Training: next-token likelihood with teacher forcing, noise on the fed-back inputs (rule fixed before
      training), dropout, early stopping on validation. Causal: music only up to decision time; the decision for a chunk is made 0.25 s
      before it starts. Run time: movement = posture + vigour x decoded gesture. Sampling: nucleus p = 0.9 for codes, median vigour, mean
      posture change (fixed here, not tuned by eye).
   3. **Retrieval control (C), training split only:** for each 0.5 s token of a held-out song, pick the training chunk (posture + gesture
      + vigour) with the nearest music features (cosine, same per-token features); transition cost = joint-space jump at the boundary,
      weight fixed in the rules; solved by Viterbi over the song. Same body pipeline and gates.
   4. Later, not now: Kosta-feedback learning adjusts only the sequencer (reward on its choices, dopamine role); the vocabulary stays frozen.
4. **Checks** (in order; each stage only after the previous passes).
   1. **T1a numeric (stop rules):** >= 60 % of codes in use on validation; reconstruction on held-out songs: jitter measures <= 1.1x the
      input's, joint ranges within 10 % of the input's; passes gates at 1.25.
   2. **S1, Kosta's blind rebuild check:** 6 held-out clips, original retarget vs vocabulary reconstruction, both through the full body
      pipeline; "which looks more like a person dancing?" + "same"; pair order checked to be mixed. Expected: "same". T1b starts only on
      Kosta's go.
   3. **T2 numeric checks on held-out songs** (STOP = stop rule; others report only): STOP music matters (validation likelihood with the
      true music vs another song's music; stop if no gap); cortex ablation (ear features only vs ear + cortex summary); STOP repetition
      (correlation of music self-similarity with movement self-similarity vs the human data on the same songs; stop if below half the
      human value); beat-alignment score (builder states which) vs human data; vigour vs ear-energy correlation vs human data; posture
      range and posture-change rate vs human data; STOP joint range p5-p95 per joint (stop if any joint < 50 % of the human data's); STOP
      jitter (stop if > 1.5x the training data's); STOP frozen pose (hand speed < 0.05 m/s for > 3 s anywhere); V1/V2 nearest-style share
      and style switches per minute; how often posture + gesture hits joint limits; how often high vigour saturates the limiter; gates at
      1.25 through the full body pipeline.
   4. **T3, Kosta's blind look** (only after Kosta sees T2 and says go): 6 held-out songs, 20 s each. Singles "does this look like
      dancing?" (yes / sort of / no + note) for sequencer, retargeted human (same song), retrieval control, round-1 S03. Pairs "which
      looks more like a person dancing?" + "same": sequencer vs retargeted human; sequencer vs retrieval; order checked to be mixed. Then
      the sequencer on Kosta's 5 check songs, singles only. Planner reading rule, for Kosta's use: if the sequencer does not beat or tie
      retrieval, the learning adds nothing yet.
   No verdict from builder or overseer at any stage. Kosta decides.
5. **Compute.** Laptop CPU first; a short timing run and an estimate for T1a and T1b before full training; threads stated. Kaggle T4 as
   fallback, with Kosta's go-ahead per run. Kaggle uploads: private dataset, DERIVED FEATURES ONLY (cortex/ear token features and
   retargeted joint targets); never raw FineDance/AIOZ files, never audio. Record: the licences' third-party clause makes Kaggle a grey
   zone; Kosta chose derived-features-only.
6. **Out of scope:** Kosta-feedback learning, limbic module, gain modulation, cortex changes (B7 epoch 6 stays frozen), hardware, brain
   monitor, any upload except the Kaggle rule above, emails, registrations.
7. **Standing rules unchanged:** branches keys-decide / body (sub-branches merged into body), never master; plain commit messages with no
   co-author or attribution lines; frozen src/ and tools/ read-only; v47 byte-identical in Off; data, models, audio, video outside git;
   free compute only; no posting, emailing or submitting; never drive hardware; if anything is unclear or conflicts with repo docs, stop
   and ask Kosta.
8. **Overseer notes (operational defaults for T0, not rulings; Kosta may amend).** 7.56.8 and 7.56.10 stay in force where 7.59 does not
   change them: song grouping by stripped lower-case name + audio hash, check-song exclusion, B7 checkpoint
   `/secondary/hyst-data/brain/b7/ckpt/phase/epoch_006.pt` and the toy-round lane recipe (`analyze_mix` beats, `b2.build_inputs`), lane
   reproduction before any run, the restricted unpickler, derived AIOZ frame rate, persons as separate dancers, AIOZ adapter round trip,
   non-overlapping 20 s windows. Changed or added by 7.59:
   - **Split:** seed 33001, shares 75 / 10 / 15 (train / validation / test) over FineDance songs and AIOZ ids together; rounding: test =
     round(0.15 n), validation = round(0.10 n), rest train.
   - **Targets:** the stage after spline and guard, before H1 (`motornet.spinal`). Gating still runs the full chain (H1, limiter, servo,
     v2p). One npz per dancer and variant copy.
   - **Mirror:** reflect across the human's sagittal plane: swap left/right joints, reflect each joint rotation (R' = M R M with M the
     reflection of the lateral axis), negate the root's lateral translation. The builder identifies the lateral axis from the data and
     tests: mirror twice = identity (max abs difference reported); a mirrored frame's left wrist = the original's right wrist reflected.
     Four copies per dancer (V1, V2, V1 mirrored, V2 mirrored), counted separately.
   - **Weighting (2.6):** per song / id, w_song = hours of its longest dancer (human motion, before the 4 copies); each of its dancers
     weighted by w_song / (sum of its dancers' hours) if that sum exceeds w_song, else 1. Applies to FineDance too (22 songs danced twice).
     The 4 copies share their dancer's weight. Weights written per npz.
   - **Token features (2.8):** tokens on a fixed 0.5 s grid from motion frame 0. Ear features = mean over the token of the 44 standardised
     fast features. Mode amplitudes: |h| of each layer's 256 complex modes at the 10 Hz stamps, modes split into 8 contiguous groups of 32
     in index order, mean over group and token. Surprisal: `b2.surprisal_lanes` per layer, mean over the token (NaN stamps excluded; a
     token with none gets 0 and a mask bit). arousal_b7 and ear energy: mean over the token. Beat phase cos/sin: values at the token's
     start and middle frames. All standardised with train-split mean and sd per feature, clipped +-3, constants in one JSON. Features use
     only frames up to the token's end (the sequencer's 0.25 s decision lead is applied in T1b, not here).
   - **Posture/gesture (2.9):** 2nd-order Butterworth filtfilt at 0.5 Hz on the 100 Hz targets (base yaw and wrist roll unwrapped), per
     whole dancer sequence before windowing.
   - **T0 report** adds tokens per split and dataset, and copy counts (V1 / V2 / mirrored).
   - **Kaggle:** nothing is uploaded in T0.

### 7.60 AIOZ prune calibrated; weight cap per clip, 2026-11-14, via Kosta + planner (answering `docs/PLANNER_BRIEF_T0_AIOZ.md`)

1. **Record (Q3).** The original prune thresholds of 7.56.10 / 7.59.2.4 were the overseer's error: rule (2) takes a union over 20 joints,
   so "> 1 % of frames" would drop 58 % of FineDance itself, and AIOZ kept only 168 dancers (2.8 %, 1.52 h).
2. **Q1 (a):** the calibrated prune variant as written in `T0_AIOZ_RULES.md` (fixed before any AIOZ number): the thresholds of rules (2) and
   (3) = max(1 %, FineDance's p95 of the same share) = 5.78 % and 1 %; the dead foot joints (10, 11) are excluded from rule (2); rules (1)
   and (4) unchanged. AIOZ kept: 1,852 dancers, 19.28 h (`t0/aioz_keep_calibrated.json`). Note: 30.8 % is just above the 30 % stop;
   AIOZ is borderline data.
3. **Q2 (a):** weight cap per CLIP: dancers on screen together share weight (per AIOZ clip, w = hours of its longest dancer; FineDance
   unchanged, capped per song). The split stays by YouTube id. Replaces the weighting line of 7.59.2.6 / 7.59.8.
4. **Safeguards (report-only, adopt nothing):**
   - T0: after retargeting and the low-pass, the jitter measures (acceleration direction changes per second, power above 3 Hz, per joint)
     of kept AIOZ dancers vs FineDance.
   - T1a: reconstruction error and jitter reported separately for FineDance-sourced and AIOZ-sourced validation chunks.
   - S1 rebuild check: of the 6 clips, 2 from AIOZ (seeded pick from held-out ids), 4 from FineDance.
5. Everything else in 7.59 stands. T0 continues. Standing rules unchanged.

### 7.61 T1a retrain: data balance check, velocity/acceleration loss, spline decoder, residual run; 2026-11-14, via Kosta + planner (answering `docs/PLANNER_BRIEF_T1A_RESULTS.md`)

1. **Record.** T1a round 1: K = 1024 by the size rule; three sizes were still improving at the 40-epoch cap. Jitter stop rule failed (7-10x
   direction changes, 17-110x power above 3 Hz); usage, ranges, gates passed. Planner reading (Kosta did not dispute): the ripple is the
   smaller problem; 88 % of the error is shape error, and AIOZ (72 % of train chunks, 2.5x lower error) may be teaching small, soft motion.
2. **Step 1, report-only, before any retrain:** variance explained by the K = 1024 reconstruction per joint (1 - error variance / signal
   variance of the gesture), FineDance and AIOZ separately; gesture amplitude (RMS and p5-p95 per joint) of FineDance vs kept AIOZ after the
   same retargeting and filtering; effective training-weight share by dataset after the per-clip cap.
3. **Dataset share rule (fixed now):** if Step 1 shows kept-AIOZ gesture RMS below 70 % of FineDance's on 3 or more joints, AIOZ is capped
   at 50 % of total training weight in both runs. Report which applied.
4. **Step 2, retrain (both runs, same data unless rule 3 applies):**
   - Run A: K = 1024 single codebook, velocity + acceleration loss terms as in Bailando's VQ-VAE (quoted and used as written); the decoder
     outputs 25 Hz control points through a fixed cubic B-spline to 100 Hz (stated in the rules); 80-epoch cap.
   - Run B: as Run A with 2-stage residual quantisation (2 x 1024: coarse + correction).
   - Report for each: variance explained per joint and per dataset, all T1a stop measures, jitter.
5. **Stop rules:** unchanged (usage >= 60 %, jitter <= 1.1x, ranges within 10 %, gates at 1.25), plus **variance explained >= 0.85 on every
   joint on FineDance validation chunks**. S1 runs on the smaller passing model (A before B). If neither passes: report and hold. Report
   and stop before S1.
6. Standing rules unchanged.
7. **Overseer notes (operational defaults, not rulings):**
   - Variance explained per joint j and dataset: 1 - var(recon_j - gesture_j) / var(gesture_j), pooled over all chunks of the split, in
     degrees (unweighted); Step 1 on validation and test; the 0.85 stop rule on FineDance validation.
   - Weight share = sum over kept windows of (npz weight x chunks) per dataset / total. The 50 % cap scales every AIOZ weight by one factor
     so AIOZ's sum equals FineDance's.
   - Bailando's loss: read from the paper (arXiv 2203.13055) and its official repository; quote the terms and weights in the rules note;
     velocity and acceleration are first and second differences of the 100 Hz decoded gesture (joint angles here, positions in Bailando).
   - B-spline: uniform cubic B-spline, control points every 4 rows (40 ms); a row depends on 4 control points, so the extra lookahead is at
     most 80 ms; the decoder's total right reach stays <= 0.25 s (stated and tested).
   - Runs A and B in parallel (cores 6-13 and 14-19, 4 threads each), resumable per epoch; same seeds as round 1 where applicable.

### 7.62 Run B goes to S1; jitter measured at the realised stage; gate share defined, 2026-11-15, via Kosta + planner (answering `docs/PLANNER_BRIEF_T1A2_RESULTS.md`)

1. **Q1 (a):** Run B (2 x 1024 residual) goes to S1.
   - The jitter stop rule is measured at the **realised stage** (after H1, limiter, servo, v2p body). **Recorded honestly: this is a post-hoc
     change of where the rule is measured, made after seeing the numbers.** Justification: the rule protects what the arm does; at the
     realised stage Run B is at or below the original except base-yaw power above 3 Hz (1.29x of a very small value); on the rebuilt
     targets the remaining difference is a sub-degree wiggle (likely from the 40 ms spline knots, unchecked). Kosta's S1 viewing is the
     deciding test.
   - S1 picks only windows whose rebuild passes the gates at 1.25: 6 held-out clips, 4 FineDance + 2 AIOZ by seeded pick, original
     retarget vs Run B rebuild, both through the full body pipeline. Question "which looks more like a person dancing?" + "same",
     optional note. Pair order checked to be mixed.
2. **Q2 (a):** gate rule = >= 0.95 of windows overall, per source reported. **Recorded as a post-hoc definition** (the original rule had
   no share). Run B: 0.983 overall (FineDance 0.948, AIOZ 0.990).
3. **Open, report-only, no action now:** the source of the rebuilt-target wiggle (spline knot spacing). Fix only if Kosta's S1 notes
   mention jitter.
4. Then report S1 and stop. T1b starts only on Kosta's go. Standing rules unchanged.
5. **Overseer notes (operational defaults, not rulings):**
   - Pool: test-split windows whose Run B rebuild passes the gates at 1.25 (the original windows all pass by construction). At most one
     window per song group (FineDance song / AIOZ YouTube id). Picks by `numpy.random.default_rng(35001)` permutation of the pool, sorted by
     (dataset, dancer, copy, window) before permuting; the first 4 FineDance and first 2 AIOZ taken. Any of the 4 copies may be picked; the
     copy is reported (and shown to Kosta only after the session).
   - Rebuild = posture + Run B decoded gesture (vigour x shape) at 100 Hz; original = the stored target. Both through guard, H1, limiter,
     servo, v2p, rendered exactly as the look-test clips (camera, lamp head, column, 20 s, 1280x720 h264 + aac, the window's own music:
     FineDance `music_wav`, AIOZ `musics/`), audio offset 0.
   - Pair order: rebuild first in exactly 3 of 6, set by `default_rng(35011)`.
   - Session: the overseer builds and serves it (look-test mode, first / second / same), key not served.

### 7.63 S1 passes; T1b on FineDance only; categorical heads; 2026-11-15, via Kosta + planner (answering `docs/PLANNER_BRIEF_S1.md`)

1. **Q1 (a):** the vocabulary (Run B, 2 x 1024 residual) passes S1 (same 4, original 2 with "Idk"/"Unsure", rebuild 0). Vocabulary frozen
   from here.
2. **Q2 (a):** no wiggle fix.
3. **Q3 (a):** T1b trains and validates on FineDance only (4 copies: V1, V2, mirrored). AIOZ stays in the vocabulary only. T2 reports
   FineDance held-out songs as the main result; AIOZ held-out reported separately, report-only. Kosta's notes recorded: AIOZ dancing waits,
   does nothing for periods, misses obvious music events (drops), is small.
4. **Q4:** rebuild shrink report-only; covered by T2 joint-range and vigour checks.
5. **T1b additions (fixed in the rules before training):**
   - Data caveat recorded: about 140 training songs; mirrored copies are near-duplicates. Keep the sequencer as specified (GRU 256 +
     attention) or smaller; no size increase without a ruling.
   - Report the train vs validation likelihood gap per epoch; early stopping on validation as specified.
   - Report how many train songs per FineDance genre.
6. **T3 note for later:** Kosta's check songs (prog rock, jazz fusion, city pop) are outside FineDance's genres; their results are a stretch
   test, reported separately from held-out FineDance songs.
7. **Go:** T1b, then T2 numbers. Report and stop before T3.
8. **Amendment (recorded with 7.63).** Kosta: for any music there are many valid dances (V1, V2, mirrored, left/right); the model must not
   learn "one right answer". Use normalised (softmax) outputs instead of bell curves; all sequencer outputs are categorical choices, which
   represent many valid answers without averaging and without shape assumptions.
   - Code head: categorical over the vocabulary.
   - Vigour head: categorical over 32 log-spaced bins spanning the training data's p0.5-p99.5 vigour. Bin edges fixed from training data
     before training.
   - Posture head: a posture-change vocabulary: k-means (or VQ) on the 0.5 s posture-change vectors (all 5 joints together) of the training
     split, 256 entries, fit before T1b training and then frozen; the sequencer outputs a categorical over these. Report the variance of
     posture change explained by the 256 entries (**STOP if < 0.9**).
   - Run time: sample all three heads with nucleus p = 0.9 (fixed).
   - Loss: sum of the three cross-entropies, equal weights (fixed).
   - T2 addition (report-only): diversity across samples: for each held-out song, generate 8 samples; report the share nearest to V1-style,
     V2-style, mirrored or not, and the mean pairwise distance between samples vs between human copies of the same song.
   - Planned, NOT now (T1c, needs Kosta's go after T2): adversarial critic fine-tuning. Superseded in 7.66/7.67 by the preference-based
     teacher stage; the adversarial critic is postponed.

### 7.64 T1b architecture: listener over the full cortex state, planner over tokens; no source separation; 2026-11-15, via Kosta + planner

This 7.64 replaces the planner's earlier 7.64 draft (Demucs stems, per-token pooled features), which was never recorded.

Kosta: no source separation. The model should track the music the way an ear does, from the feel and properties of the sound, without
naming instruments. It needs memory far longer than half a second. The per-token pooled summary threw away most of what the cortex hears.
The planner agrees; the pooled summary was the planner's simplification.

1. **Input:** the frozen cortex (B7 epoch 6) full state at 100 Hz for every song: all 4 layers' mode states (amplitude and phase as
   cos/sin, or real/imag), per-layer surprisal and precision, arousal_b7, plus the 44 ear features. Precomputed and stored per song
   (outside git).
2. **Listener (new, trained):** learned linear input projection to 128 dims, dropout 0.2, then a recurrent network at 50 Hz (cortex state
   downsampled by averaging), 256 units with learned per-unit time constants initialised log-uniform from 0.1 s to 30 s. Runs continuously
   over the whole song.
3. **Planner (the former sequencer):** GRU 256, stepped every 0.5 s, decision made 0.25 s before the chunk starts. Inputs: listener state
   at decision time; embedding of its previous code, vigour bin and posture-change entry; attention over its own last 32 tokens (16 s).
   Outputs: categorical code (vocabulary 2 x 1024 residual; the builder states how the two stages are predicted), vigour (32 bins),
   posture change (256-entry posture vocabulary).
4. **Training:** listener + planner trained jointly by the three cross-entropies; truncated backprop through 60 s windows; teacher
   forcing with input noise (rule fixed before training); early stopping on validation; train/validation gap reported per epoch.
   FineDance only (7.63). Cortex and vocabulary frozen.
5. **Dropped:** Demucs/stems; per-token pooled music features; any instrument labels.
6. **T2 additions:**
   - **STOP, swapped-music test:** likelihood with the true music vs a tempo-matched other song (tempo within 5 %); stop if no gap.
   - Event response (report): around strong onsets, energy jumps and cortex slow-state changes (detected by a fixed rule), movement change
     of model vs human data on the same songs.
   - Ablation (report): listener fed ear features only (no cortex state). If it equals the full model, record that the cortex adds
     nothing.
   - Long memory (report): effect on likelihood of truncating the listener's history to 2 s vs full.
7. **Emotion:** every Kosta viewing from here includes swapped-music pairs and feeling labels as in the planner's previous draft (Kosta
   labels music and movement separately, blind).
8. **Retrieval control (7.59.3.3):** listener-free: cosine on the 0.5 s-averaged cortex state + ear features.
9. Everything else in 7.59-7.63 stands.
10. **Overseer notes (operational defaults, not rulings):**
    - Storage first: the builder reports the per-frame width of the cortex state and the total size (float16 vs float32) before
      precomputing; data under `/secondary/hyst-data/body/t1b/`.
    - Mirror copies share the same (unmirrored) music input.
    - Listener state starts at zero at song start and is carried (detached) across consecutive 60 s windows of the same song; the builder
      states it in the rules note.
    - "Listener state at decision time" = the last 50 Hz listener step at or before chunk start - 0.25 s (causal).
    - Swapped-music pairs: tempo from the offline beat grid; pairs chosen by a seeded rule fixed in the rules note before training; the
      number of songs with no partner within 5 % is reported.

### 7.65 Repertoire checks, affect part of the listener, viewings, teacher stage; GO for T1b; 2026-11-15, via Kosta + planner

Amends 7.64. Then start T1b.

1. **Repertoire (Kosta):** a learned move repertoire is acceptable only if it is vast and varied, with moves different each time (start/end
   location and scale vary). The design meets this through 2 x 1024 residual shapes (about 1M pairs), 32 vigour bins, 256 posture shifts and
   decoder blending with neighbours. T2 checks:
   - **STOP identical-shape repetition:** in each generated 60 s dance on held-out songs, the share of tokens whose (coarse code, residual
     code) pair already occurred earlier in the same dance. Stop if it exceeds the human data's share on the same songs by more than 2x.
   - Report: distinct (shape, vigour bin, posture entry) triples per minute, model vs human data.
2. **Emotion embedding** (Kosta: no named emotions; an abstract high-dimensional embedding is right). Amends 7.64 item 2; the listener is
   split:
   - RHYTHM part: 192 units, time constants initialised log-uniform 0.1-1 s.
   - AFFECT part: 64 units, time constants initialised log-uniform 2-30 s. This is the emotion embedding: unlabeled, learned only from human
     movement to music.
   - Both parts receive the cortex projection and each other's state. The planner reads both.
   - Report-only probe in T2: Kosta labels the feeling he hears in 20 held-out FineDance songs (calm / sad / tense / energetic / light),
     blind to any model output, using the existing labelling tool. Report whether the affect states of those songs separate by his labels:
     cross-validated linear probe vs a shuffled-label control. The labels never train the model.
   - Monitor note for later: the affect space projected to 2D replaces the mockup feeling field (canvas board C3).
3. **Viewings** (defines what 7.64.7 refers to). Every Kosta viewing of generated dance from here includes:
   - swapped-music pairs: the same generated movement shown with its own song vs a tempo-matched other song (tempo within 5 %), "which fits
     the music?" + "neither", order checked to be mixed;
   - feeling labels for the movement (calm / sad / tense / energetic / light / nothing / can't name it), and separately, blind to the
     movement, labels for the music; report agreement.
4. **Teacher stage moves up:** directly after T2/T3 of the first trained version, the model dances to songs outside the dataset and Kosta
   gives input. The form of input (pick the better of two / feeling labels / timeline marks) is Kosta's ruling later.
5. **Go:** T1b training with 7.64 + 7.65. Report T2 and stop before T3. Standing rules unchanged.
6. **Overseer notes (operational defaults, not rulings; the builder writes them into the rules note before training):**
   - T2 is the 7.59.4.3 list as amended: "music matters" = the 7.64 swapped-music STOP; "cortex ablation" = the 7.64 ear-only listener (a
     second trained model, same rules); repetition STOP of 7.59 stays and the 7.65.1 STOP is added; jitter STOP measured at the realised
     stage (7.62); V1/V2 nearest-style report (7.56.11).
   - Held-out songs = FineDance test split; 60 s dances from a fixed start (the song's first full 60 s after 10 s), one per song, seed fixed
     in the rules note. Human comparison = the T0 targets of the same songs and windows, all 4 copies averaged where a measure allows.
   - Vigour bins, posture vocabulary, run-time sampling and loss: as 7.63.8 (log-spaced vigour bins, k-means posture vocabulary, nucleus
     p = 0.9 on all three heads). (Corrected 2026-11-15: an earlier version of this note said equal-count bins and median/mean choices,
     written before the 7.63 text arrived.)
   - Kosta's music-label probe: 20 FineDance test songs (validation songs fill up if test has fewer), seeded pick; one 30 s audio clip per
     song (a still frame), labels calm / sad / tense / energetic / light only, through `scripts/body/dialstudy_session.py` (a label-set
     option is the only allowed change). The overseer serves the session; the builder never sees the answers before the probe is run.
   - Retrieval control (7.64.8) is built and run on the held-out songs in T2 (for T3 later); its numbers reported beside the model's.

### 7.66 Two external architecture reviews: proceed, no pivot; E1 baseline; T2 additions; variants; 2026-11-15, via Kosta + planner (brief `claude/hysteresis-arch-review-brief.md`)

1. Do NOT stop the running T1b. It is the BASELINE (E1). All changes below are tested against it, one at a time, same splits.
   (Overseer: T1b was not yet running when this arrived; E1 = T1b as specified in 7.63-7.65 plus the 7.66.3 T2 additions.)
2. **Facts for the reviewers, report back (no work beyond lookup):** a) exact definition of the 44 ear features (what each is;
   normalisation per song or global); b) how FineDance audio and motion are aligned (original timestamps, offsets, any manual alignment;
   checked how); c) trainable parameter counts: cortex projection, listener, planner, heads; d) FineDance genres and dancers per split.
3. **T2 additions for the baseline and every variant:**
   - Ablations (same architecture otherwise): ear features only; cortex only; ear + cortex; ear + cortex with cortex states time-shuffled
     within the song. (Amended by 7.67.4: time-SHIFTED, not shuffled.)
   - Controls in viewings: retrieval (as 7.59.3.3) AND random human chunks with the same transition cost (no music).
   - Swapped-music test against 3 tempo-matched songs, not 1.
   - Self-similarity correlation at 3 timescales (2 s, 8 s, 30 s windows).
   - Endpoint (lamp) jerk and direction changes, alongside joint measures.
   - Approximate repetition: nearest-neighbour gesture distance within a dance, not only identical code pairs.
   - All aesthetic numbers on REALISED trajectories (after spinal layer, limiter, servo); report commanded vs realised difference.
   - Affect test: passages matched on tempo (within 5 %) and RMS energy (within 10 %) that Kosta labels differently (blind): do affect
     states separate them better than a shuffled-label control?
   - Vocabulary: share of codes used only by AIOZ chunks (report).
4. **Variants after baseline** (each needs Kosta's go, rules fixed before training): E3 timing: planner outputs an onset offset per token,
   categorical over -0.2..+0.2 s in 25 ms bins; decoder shifts the chunk; overlap handled by the existing blending. E4 listener timescales:
   three groups, fast 0.1-0.5 s / medium 1-4 s / slow 8-30 s (replaces rhythm/affect split). E5 V1/V2 style: pending Kosta's ruling (style ID
   sampled per song/phrase vs pooled). Audio pitch-shift augmentation (+-2 semitones, motion unchanged) in all variants after baseline.
   (Amended by 7.67.)
5. **Viewing protocol from now:** 2-3 repeated pairs per session (consistency), confidence mark per answer, tie option, separate sessions for
   "looks like dance" and "fits the music", no re-watching a pair until a preference appears. (Amended by 7.67.)
6. **Teacher stage** (after baseline + variants): blind pairs of the model's own dances on teaching songs ("A better / B better / both
   poor" + optional timeline notes) -> small preference model -> planner fine-tune with a likelihood anchor to human motion; vocabulary
   frozen. Teaching songs and final evaluation songs are separate pools (pending Kosta's confirmation). Adversarial critic postponed.
   (Amended by 7.67.)
7. **Wording in BRAIN_SPEC from now:** cortex = multi-timescale predictive recurrent model inspired by auditory processing (not
   anatomical); vigour = movement amplitude selection (no dopamine claim); affect units = slow modulatory state, "limbic-inspired" only if
   the affect test passes; spinal layer = spinal-inspired compliant control layer.

Rejected, for the record: contrastive grounding of affect units to valence features (needs emotion labels; reverses Kosta's ruling;
contrastive objectives failed before); unspecified "style adapter"; dropping AIOZ without evidence. Standing rules unchanged.

### 7.67 Second review round (ChatGPT, Gemini): order of work, sync check, features, structured listener, ablations, style, timing, teacher stage; 2026-11-15, via Kosta + planner

Amends 7.66 items 4-6.

Order (one change at a time against the E1 baseline, same splits): 1 finish E1 baseline; 2 verify FineDance audio-motion sync; 3 structured
listener input; 4 listener ablations; 5 V1/V2 style per song; 6 offset supervision; 7 timing head; 8 first 40-60 preference comparisons;
9 100-150 comparisons + generalisation check; 10 first constrained fine-tune (150-250 comparisons).

2. **Sync check (blocks 6-7):** document per FineDance sequence: audio and motion start offsets, any trimming, whether alignment holds over
   the whole clip (e.g. beat/onset vs movement-onset cross-correlation drift between first and last minute), and that training and
   evaluation use identical preprocessing.
3. **Features:** report the 44 ear features (7.66 2a). Provide two forms where meaningful: globally normalised (statistics from the training
   split only) and within-song relative (vs a causal recent window). Verify every feature is causal (no centred or future windows); list any
   that are not and fix them.
   3b. **Structured listener** (variant vs the 128-dim baseline): each cortex layer compressed separately to 16 dims (64 total) + auxiliary
   signals (per-layer surprisal, precision, arousal) kept as separate inputs + a separate 32-dim embedding of the ear features; listener
   total 256 units, fast 0.1-0.5 / medium 1-4 / slow 8-30 s.
4. **Ablations:** ear only / cortex only / ear + cortex / ear + cortex TIME-SHIFTED by a fixed offset (state it, e.g. 4 s) instead of
   shuffled. Comparable parameter budgets. Keep the combined listener only if it improves held-out music responsiveness or blind
   preference, not only likelihood.
5. **Style:** explicit V1/V2 ID input to the planner; one style sampled per song at start and held. V1/V2/mirror copies of one performance
   share a performance ID in splits and evaluation.
6-7. **Timing:** offsets supervised by soft targets from local alignment (for each token, reconstruction error of the decoded chunk shifted
   -200..+200 ms in 25 ms steps vs the human trajectory, softmax with a temperature fixed in the rules); 17-way categorical head; offsets as
   corrections to a shared timeline with a penalty on neighbouring-offset differences; monotonic boundaries with at least 0.1 s separation;
   boundary control points blended over 50 ms; report realised timing.
8-10. **Teacher stage:**
   - Pools: teaching songs (split into preference-train and preference-validation songs, whole songs only) and a final evaluation pool never
     taught on (pending Kosta's confirmation).
   - Per song, generate 4 candidates, compare 2 (same music, genuinely different). Mark comparisons as holistic or diagnostic; mostly
     holistic.
   - Answers: A / B / tie / both poor + confidence. Sessions: 20-30 new pairs + 3-5 hidden repeats, spaced; 10-15 teaching songs, 8-15
     comparisons each, V1 and V2 both present.
   - Preference model: linear Bradley-Terry (Davidson extension for ties; "both poor" kept as a separate rejection signal) on a small fixed
     feature set of the REALISED dance in relation to its music (endpoint trajectory, curvature, acceleration, jerk, commanded vs realised,
     motion change around musical events, spatial expansion, code repetition, interactions with listener states). L1 + weight decay. 2-layer
     MLP (32 hidden) only if linear fails.
   - Gates before any fine-tune: held-out pairwise accuracy >= 65 % with calibration reported; not explained by amplitude alone; repeat
     agreement reported; transfer across preference-validation songs.
   - Fine-tune: DPO on planner action sequences (code, vigour, posture, offset heads) vs a frozen reference snapshot, plus the original
     FineDance likelihood as anchor (weight fixed in rules). Trainable: heads first; then heads + small adapter; full GRU only if needed.
     Cortex and vocabulary frozen. Low LR, early stopping. No PPO, no adversarial critic.
   - Every fine-tuned model must beat the pre-feedback baseline in blind viewing on the final evaluation pool. Lower loss is not evidence.

Deferred: Gemini's MMD genre adapter between cortex and listener (only if check songs fail); Gemini's slowness penalty and FiLM-to-
vigour/posture for affect units (optional variant). Standing rules unchanged.

**Overseer notes (operational, not rulings):**
- WO41 (`docs/BUILDER_PROMPT_WO41_T1B.md`) rewritten 2026-11-15 for E1 under 7.63-7.67; the e710b4b version was never sent.
- Item 3, known candidates: T0 recorded per-column lookahead (`token_lookahead_s`): ear features 0.023 s, ear energy 1.0 s
  (verified 2026-11-14). Both must appear in the causality list.
- Item 5: the T0 split already groups V1, V2 and mirror copies by song (FineDance) / YouTube id (AIOZ), 403 groups, none in two splits
  (verified 2026-11-14). Evaluation must group the same way.
- Item 4 default: time shift = 4 s, cortex + ear state delayed (the listener hears the music 4 s late); stated in the rules note.
- Causality before E1: E1 must be causal (7.59.3.2), so the item 3 causality check runs BEFORE E1 trains; any non-causal ear feature or
  cortex input is fixed (shifted to causal) first and listed. The other item 2-3 reports (7.66.2 lookups, sync check, the two feature forms)
  run while E1 trains and change nothing in E1.
- E1 = the ear + cortex model of 7.64/7.65 only. The four ablations are step 4, after E1; the 7.65.6 "ear-only ablation trained beside E1"
  is withdrawn.
- Affect: the 7.65.2 song probe (20 songs) and the 7.66.3 passage test both stand. Kosta labels in one session: one 30 s clip per probe
  song and three 15 s passages per song (seeded starts); the passage test uses passage pairs matched on tempo (5 %) and RMS (10 %) that
  received different labels.

### 7.68 Answers to the pre-E1 brief; compute and seeds; GO for WO41; 2026-11-15, via Kosta + planner (answering `docs/PLANNER_BRIEF_T1B_PRE.md`)

1. **Q1 (a):** causal in the token sense only. The planner sees music only up to decision time; inputs may contain offline whole-song facts
   (beat grid, ear energy 1.0 s lookahead, ear features 0.023 s) as long as they are listed in the rules and the report. No cortex retrain.
   Basis: dance plays from offline sidecars (Kosta, 2026-10-04). 7.67.3's "fix every non-causal feature" is replaced by "list every
   non-causal feature". (c) deliberate lookahead is a possible later variant, needs a ruling.
2. **Q2 (a):** E1 stays pooled V1/V2 with no label (7.56.11). The per-song style ID (7.67.5) is a VARIANT tested against E1; adopting it
   needs Kosta's ruling after seeing the result.
3. **Q3 (a):** two variants: E4 timescale groups first (fast 0.1-0.5 / medium 1-4 / slow 8-30 s); then the structured input (per-layer
   compression, separate auxiliary inputs, separate ear embedding) on the better listener.
4. **Q4 (a):** full 4-way ablation for E1 and for the final candidate only; intermediate variants vs E1 only.
5. **Q5 (a):** per held-out song, true-music log-likelihood minus the mean over 3 swaps; STOP if the bootstrap 95 % interval of the mean
   over songs (resampled by song, fixed seed) includes 0. Swap partners: fill from validation songs, then allow half/double tempo; report
   how many needed it.
6. **Q6 (b):** Kosta labels 40 songs (test + validation), 3 passages each, blind to model output, with the existing labelling tool, before
   T2 is computed. Both affect tests stay report-only; no conclusion below 10 matched passage pairs.
7. **Q7 (a):** offset soft targets computed by decoding the whole local sequence per shift, in the real neighbours' context.
8. **Q8 (a):** one answer set in every viewing: A / B / tie / both poor + confidence (low / medium / high).
9. **Compute** (Kosta: Kaggle gives 30 h GPU + 20 h TPU per week):
   - Use Kaggle GPU for T1b and variants when it is faster than the laptop (timing comparison first). Derived features only (cortex
     states, ear features, joint targets, tokens); never raw FineDance/AIOZ files, never audio. Private datasets. Each Kaggle run still
     needs Kosta's go-ahead.
   - Use the extra compute for SEEDS, not size: E1 and every variant trained with 3 seeds; report mean and spread; a variant counts as
     better only if its gain exceeds the seed spread. Model sizes unchanged without a ruling.
   - TPU not used.
10. **Go:** send WO41 (E1 baseline with these rulings). Standing rules unchanged.
11. **Overseer notes (operational, not rulings):**
    - Test + validation hold 39 FineDance song groups (19 + 20), not 40: all 39 are labelled (one sequence per group, seeded pick), 3
      passages each; the 20-song probe of 7.65.2 uses these labels (song label = majority of its 3 passages, ties reported).
    - Kaggle timing comparison needs an upload, which needs Kosta: the builder times the laptop and prepares a Kaggle package (derived
      features + script, private dataset) without uploading. If 3 laptop seeds in parallel finish in <= 24 h, they run locally;
      otherwise the builder STOPs with the package ready and Kosta decides.
    - 3 E1 seeds in parallel on cores 6-17 (4 threads each); side tasks on cores 18-19.

### 7.69 Data expansion: PhantomDance now, other sources by Kosta; 2026-11-15, via Kosta + planner

Does not change E1 (FineDance only).

1. **PhantomDance** (github.com/libuyu/PhantomDanceDataset): download now (direct Google Drive link, no account; if a login appears, STOP
   and ask Kosta). Save the licence file and README with the data; record date and version (v1.2 expected: 260 pairs, ~9.5 h,
   animator-made, 30 fps, wav 16 kHz). Record the licence as stated (repo MIT) and that music rights are not separately stated. Data
   outside git, derived features only to Kaggle.
2. Run it through T0 exactly as FineDance (retarget V1/V2 + mirror, LP cutoffs reused, posture/gesture split, gates at 1.25, cortex states
   computed locally on its audio). Report hours kept, genres, jitter vs FineDance, gesture amplitude vs FineDance.
3. **Look check before any planner use:** Kosta views 6 retargeted PhantomDance clips (seeded, across genres), single answer each: does the
   dancer follow the music? (yes / partly / no) + note. Planner use only on Kosta's go.
4. **Kosta's own actions** (overseer does none of these): Motorica download via browser login; AIST registration form (for AIST++ music);
   email to FineDance authors asking for the full 14.6 h. When any arrives, same steps 1-3.
5. **After E1:** variant E-data = planner trained on FineDance + approved new sources, same splits by song, 3 seeds, compared to E1. Report
   per-source results on held-out songs.

Not now: InfiniteDance (licence unknown), SoulDance (on hold per its repo), PopDanceSet (licence unknown), Kosta's own recordings.
Standing rules unchanged.

**Overseer notes (operational, not rulings):**
- PhantomDance's audio is 16 kHz. `scripts/brain/fast_features.py` resamples any input to 44.1 kHz itself (soxr), so nothing breaks, but
  PhantomDance has no content above 8 kHz while FineDance does. Report-only: which of the 44 ear columns and which cortex inputs depend on
  content above 8 kHz, and the size of the shift (FineDance features computed from audio low-passed at 8 kHz vs the original, on 5
  songs). (Corrected the same day: an earlier wording of this note asked the builder to resample.)
- Split by song with its own seed (fixed in the rules note); PhantomDance songs that also appear in FineDance (by name) are listed.
- No installs. If the Google Drive download cannot be done with curl / the existing env, STOP and ask.
- **2026-11-15, Kosta downloaded both by browser** to `~/Downloads/`: `PhantomDanceDatav1.2.zip` (2.65 GB; 260 motion json + 260 wav;
  the folder inside is named `PhantomDanceDatav1.1`, and the zip holds no licence or README) and `OneDrive_1_11-15-2026.zip` = Motorica
  (4.02 GB: `LICENSE.txt`, `motorica_dance_dataset.zip`, `motorica_dance_dataset_features.zip`). No Google Drive download is needed; the
  PhantomDance licence and README are fetched from the GitHub repository (7.69.1). Copies go to `/secondary/hyst-data/`; the files in
  Downloads are left in place.
- **Motorica licence (LICENSE.txt, read 2026-11-15):** motion (c) Motorica AB, all rights reserved; research use only, no commercial use
  (explicitly including "training machine-learning algorithms for commercial purposes") without written consent; no redistribution
  of any content; music has its own copyright holders; attribution and two citations required. Operational default until Kosta rules:
  Motorica data and anything derived from it stay on this laptop (no Kaggle, not even a private dataset), and it gets steps 1-3 of 7.69
  like PhantomDance. **Open for Kosta:** whether Hysteresis counts as non-commercial research under these terms.
- **Kosta ruled 2026-11-15:** Hysteresis is non-commercial research (unpaid, not a commission, not a product), so Motorica may be used
  for training under its licence. The no-redistribution term still holds: Motorica and anything derived from it stay on this laptop (no
  Kaggle, not even a private dataset). Attribution and the two citations go into any write-up that uses it.

### 7.70 Posture head = residual 2 x 256; five equal cross-entropies; GO for E1; 2026-11-15, via Kosta + planner (answering `docs/PLANNER_BRIEF_T1B_POSTURE.md`)

1. **Q1 (a):** posture head = residual 2 x 256 (coarse + correction given coarse), built like the gesture vocabulary; 0.967 variance
   explained on validation (0.971 train; the 7.63.8 STOP at 0.9 is met). Reason: joints stay coupled; posture (droop/lift) is part of the
   emotional channel (7.71) and must move as one body.
2. **Q2: confirm.** The two posture stages are predicted the same way as the two gesture stages (stated in `T1B_RULES.md`). Loss = sum of
   five cross-entropies with equal weights (gesture coarse, gesture residual, vigour, posture coarse, posture residual). Report each head's
   training and validation loss separately per epoch.
3. **GO:** resume WO41 (E1 baseline) with 7.68-7.71. Standing rules unchanged.

### 7.71 Music-label session cancelled; emotion carried by readable movement properties; 2026-11-15, via Kosta + planner (answering `docs/PLANNER_BRIEF_LABELS.md`)

1. **Q1: none of (a)-(d). CANCEL the 117-clip music-label session.** Close the page; nothing was answered.
   Kosta: most FineDance songs carry no clear feeling ("modern pop slop"); deep, precise emotional state is not needed; emulating it
   through movement properties people can read (size, speed, droop/lift, smooth vs abrupt) is enough. Basis (planner): Saerbeck &
   Bartneck 2010 (acceleration -> perceived energy, path curvature -> valence); Pollick et al. 2001 (arm movement: energy from
   speed/acceleration, pleasantness from inter-segment timing); Reachy Mini 2026 (viewers read energy, anger and sadness from a low-DoF
   robot; subtle feelings near chance).
2. **Consequences:**
   - The T2 affect probe and the matched-passage test (7.65.2, 7.66.3, 7.68.6) are DROPPED for FineDance. No prefill, no audio-emotion
     encoder labels.
   - The emotional channel in the design is explicit: vigour head (size/speed), posture head (droop/lift), and move shape (smooth vs
     abrupt). T2 reports, report-only, on held-out FineDance songs: correlation of vigour with ear energy and of posture height with ear
     energy, model vs human data.
   - Emotion is judged on music with clear feeling: Kosta's check songs and the teaching pool (Kosta picks teaching songs with clear
     feeling, including his own genres). Every viewing keeps 7.65.3 / 7.68.8: Kosta labels the movement (calm / sad / tense / energetic /
     light / nothing / can't name it) and, separately and blind, the music; report agreement.
   - Teacher stage: preferences on these songs shape how size, speed and posture follow the music's feeling.
   - Optional later variant (needs a ruling): affect units modulate the vigour and posture heads directly (scale/shift), no labels.
3. **Q2:** n/a. 7.70 (posture ruling) still pending. Standing rules unchanged.
4. **Overseer notes (operational, not rulings):** the private page (claude.ai artifact NcL5N9rcfNCRfwgachwCFx, 0 answers) is closed for use; deleting it needs Kosta to confirm on the laptop (not possible over Remote Control); the local
   session folder `t1b/labels_session_2026-11-15` and the clips stay on disk unused. WO41 step 5's label clips and the T2 wait for labels
   are void; T2 no longer waits for labels.

### 7.73 Redesign: control representation first; A = motor grammar conditioned on measured controls, B = listener predicting controls; 2026-11-16, via Kosta + planner (refined after external review)

Recorded as 7.73 because no earlier 7.73 was recorded; this replaces the planner's earlier redesign draft (never received by the
overseer). Planner text, verbatim:

KEPT from 7.73: root cause (E1 asked to predict WHICH move; music determines HOW/WHEN); A = motor grammar trained on all retargeted
motion, conditioned on control signals measured from the motion; B = listener predicting those controls from music; teacher tunes B only;
A frozen after training. Dropped: E1b and V-fam/V-data/V-hd.

NEXT MILESTONE = THE CONTROL REPRESENTATION (before any A or B training).

Step 0a, define (fixed in rules before computing), per 0.5 s token, from REALISED or target trajectories of retargeted human motion:
- vigour: angular speed RMS over joints AND lamp (end-effector) speed RMS, kept separately; combined vigour = first principal component;
  global robust normalisation from training data.
- height: absolute lamp height normalised to the usable workspace (also replaces posture-as-change; posture vocabulary rebuilt on
  absolute posture).
- accent pattern: continuous motion-accent strength (normalised lamp acceleration + jerk, smoothed) aggregated into 8 sub-slots (62.5 ms).
- sharpness: dimensionless, independent of speed: share of high-frequency acceleration energy in total movement energy (builder states
  band edges).
- direction: mean lamp velocity direction (unit 3-D vector, workspace frame).
- continuity: movement-activity measure + pause probability (lamp speed below a stated threshold for > 0.25 s).

Measured only, not yet a control: movement lead (proximal vs distal onset order).
Slow structure (separate, not per-token controls): phrase start/end probability, repetition relation, contrast; see Step 0c.

Step 0b, validate numerically on FineDance + PhantomDance + Motorica (after Kosta's look check) + AIOZ: distributions per dataset,
pairwise correlations between controls (report any |r| > 0.7 as redundant), within-song vs between-song variance.

Step 0b', Kosta's visual validation (~15 min, blind): for each of vigour, height, sharpness, continuity, accent density: 3 pairs of real
retargeted human clips (rendered on the arm) at low vs high values of that control with the others matched where possible; question
"which looks [bigger/faster | higher | sharper | more continuous | more accented]?" + "same". A control that Kosta cannot see is dropped or
redefined.

Step 0c, music side (report-only diagnostics on HUMAN data): relation of each control to acoustic measures (RMS, spectral flux, onset
strength, low/high band energy, spectral centroid, local dynamic range, beat strength): global, within-song (song mean removed), per song,
and over lags -1..+1 s. Musical structure layer: beat (existing grid), onsets, phrase boundaries and repetition from a self-similarity
(novelty) analysis of the cortex/ear features; no source separation, no instrument labels (pending Kosta's OK).

THEN (each reported before the next):
- A: GRU 256 grammar over gesture codes + absolute posture; inputs: previous tokens, controls for the current token and the next 1-2 s
  (small temporal convolution), dataset/domain embedding. Loss: token likelihood + auxiliary control loss (expected controls of the
  predicted code distribution, using per-code control statistics precomputed from the vocabulary, vs requested). Control dropout 15 %
  (whole vector); control corruption sampled from realistic joint control distributions. Analyse residual-code utilisation and
  conditional entropy before keeping the residual stage in A.
- A checks: intervention matrix (same start, vary one control at a time incl. held-out combinations; output controls must move in the
  expected direction, report effect sizes); S-B blind look: human vs A with own oracle controls vs other performance's controls vs
  shuffled vs constant.
- Control substitution: same music, several control sequences into A; does A express the differences.
- B: listener (frozen cortex + ear + structure layer) predicts a categorical over a learned joint CONTROL vocabulary (k-means on control
  vectors, size by the 7.61 rule) per token, plus phrase events at the slow scale. S-A comparisons: true vs tempo-matched swapped vs random
  music, persistence baseline (previous control), ear-only, without cortex. Bootstrap by song.
- S-C: true music -> B -> A vs swapped music vs shuffled B controls vs random plausible controls vs oracle controls; several samples per
  condition; Kosta blind, feeling labels on clear-feeling songs.

Parallel task: chunk joining (decode whole token sequences with overlap) so re-joined human chunks reach human-level high-frequency power;
report before S-B.

Avoid: training B on unpaired data; independent sampling of controls; artist feedback into A; GAN critic.
Kosta to-do: 12-clip look check (PhantomDance/Motorica); later the ~15 min control validation.
Standing rules unchanged.

**Overseer notes (operational, not rulings):**
- 7.72 (the answer to `docs/PLANNER_BRIEF_E1_RESULTS.md`) never reached the overseer and is not recorded. Q1 of that brief is answered by
  this redesign. Q2 (jitter measured against the re-joined-chunk level), Q3 (posture drift report-only), Q4 (no T3) and Q5 (AIOZ held-out
  skipped) have no recorded answer; the verbatim 7.72 text replaces this note when it arrives.
- Work split for the next milestone: WO43 (agent 1) = Steps 0a, 0b, 0c and the clip candidates for 0b' (not served; the overseer serves
  Kosta's session). WO44 (agent 2) = the parallel chunk-joining task. Nothing of A or B is trained under either.
- Step 0b on PhantomDance and Motorica uses the WO42 T0 outputs (`/secondary/hyst-data/body/t0_{phantom,motorica}/`); their numbers are
  computed and reported separately and marked "look check pending" until Kosta has done the 12-clip look check (7.69.3).

### 7.74 Controls fixed (accent pattern, pause), joining closed, whole-song 0c, lookahead selection planned; 7.72 replaced; 2026-11-16, via Kosta + planner (answering `docs/PLANNER_BRIEF_CONTROLS.md`)

Planner text, verbatim:

Q6 / 7.72 (short, replaces the lost reply): record E1 results as reported; all STOP rules fired; posture-as-accumulated-change was a
planner spec error (drift); no Kosta viewing of E1; AIOZ held-out skipped. All other parts of the lost reply are superseded by 7.73.

Q1 (a): accent control = PATTERN only (8 sub-slots divided by their token mean). Vigour carries the level. Accent pairs leave the 0b'
viewing.

Q2 (a): continuity control = pause probability only; activity dropped.

Q3 (a): serve the 12 pairs (vigour, height, sharpness, continuity) to Kosta now; report that vigour pairs also differ in accent level by
1.5-1.6 sd, so a "seen" vigour counts as vigour + accent level.

Q4 (a): chunk-joining task closed (target met by A1 and B). Use decoder A1; re-joined human A1 is the jitter reference in S-B. Before A,
report-only: contribution of posture knots vs gesture codes to lamp power above 3 Hz and to the frozen share (decoded retrieval with human
posture knots, and vice versa). Record the finding: the model's excess is in token sequences that do not form one human movement, not in
the joins.

Q5 (c): proceed to A; in parallel on separate cores, Step 0c on whole songs (not 20 s windows), including phrase-scale boundary alignment.
B's S-A results are reported against these human values, not an absolute bar. Record: within-song control-music relations in human data
are weak (|rho| <= 0.19 at token scale), so the datasets can teach B little; the teacher stage is expected to carry more of the musical
shaping.

PLANNED STAGE, recorded, not a build order (Kosta's proposal): LOOKAHEAD SELECTION between B and A (receding-horizon planning). Each 0.5 s:
sample N futures (e.g. 32) of 2-4 s from A given B's control distribution; score each by A log-likelihood (human-likeness) + match to B's
controls over the horizon (later horizon steps down-weighted) + kinematic feasibility (limits, clearance) + later the teacher preference
model; sample the next token from the top-k futures (not argmax, to keep variety); execute one token; compare realised vs predicted state;
replan. Brain mapping (simplified): basal ganglia selection/gating among cortically simulated candidates; cerebellum forward model for
predicted vs realised state. Built only after S-B shows A follows controls; evaluated against plain sampling.

Kosta to-do: 12-clip PhantomDance/Motorica look check; the 12-pair control viewing.
Standing rules unchanged.

**Overseer notes (operational, not rulings):**
- The 7.73 overseer note on the missing 7.72 is closed by Q6 above.
- Controls as of 7.74 (definitions in `docs/CONTROLS_RULES.md` with addenda 1-2): vigour (combined, level), height (v2p bounds
  [-0.569, 0.770] m), accent pattern (8 sub-slots / token mean), sharpness, direction, pause probability. Activity and accent level are not
  controls.
- A trains on retargeted motion. PhantomDance and Motorica enter only after Kosta's 12-clip look check (7.69.3); until then FineDance +
  AIOZ.

### 7.76 Third external review (ChatGPT, Gemini): beat-relative coupling first; A additions; control refinements; B, lookahead, teacher refined; 2026-11-16, via Kosta + planner

Planner text, verbatim:

Record as BRAIN_SPEC 7.76: third external review (ChatGPT, Gemini) of the redesign + lookahead idea. Both: redesign sound; measure
beat-relative coupling first.

1. NEXT EXPERIMENT (decides B's targets; report-only):
 Beat-phase / metrical analysis of HUMAN motion, all paired datasets, whole songs (not 20 s windows), realised lamp trajectory and each
 joint/axis separately.
 - Motion events by several definitions (stated in rules before computing): lamp-speed local minima, lamp-acceleration peaks, joint
   angular-velocity peaks, direction reversals, movement onsets (threshold + minimum separation).
 - Phase of each event relative to beat, half-beat (double-time), half-time and bar; circular phase concentration (mean resultant length)
   and preferred phase per level; lead/lag scan +-250 ms, reported (not silently maximised).
 - Controls: same events vs time-shuffled beats and vs other songs' beat grids (tempo-matched).
 - Tempo/density: motion-event rate vs tempo and onset density; pause occupancy/duration vs rhythmic density and pulse clarity.
 - Uncertainty by song (bootstrap by song).
 - Whole-song structure: change points in control distributions and movement motifs vs music novelty and repetition, delays -2..+2 s;
   spot-check 10 songs' section boundaries by ear.
2. A (motor grammar) proceeds in parallel (needs no music), with additions:
 - persistent STYLE / MOVEMENT-MODE embedding at sequence level (dataset + V1/V2 + genre where labelled), sampled per song at generation;
 - persistent MOTIF state (latent, updated every 2 s, not every token) for 2-4 s coherence;
 - accent input stays token-relative for A; beat-relative accent timing will be B's output, converted at run time.
 A checks as 7.73/7.74 (intervention matrix, S-B), plus coherence over 2-4 s.
3. Control refinements, report-only before adoption: vigour split into amplitude (lamp path extent per token) and speed; sharpness 3 Hz
   threshold checked against filtered human vs realised robot motion and against noise; pause as occupancy/duration at 2-8 s scale.
4. B (after step 1): predicts a joint temporal distribution over controls at matched timescales (accent timing beat-relative;
   vigour/sharpness short; height/pause longer; repetition/change phrase-level). Compare cortex against simple baselines
   (beat/onset/density/standard audio features); keep the cortex only if it adds measurable value.
5. Lookahead selection (later, after A passes): feasibility = hard constraint; grammar likelihood = minimum-plausibility threshold, not
   main score; main score = fit of the DECODED, REALISED controls to B's joint distribution; variety by clustering the good pool on movement
   path, gesture family, posture and timing, then sampling among clusters; persistent intention state; horizon 2 s vs 4 s, N 16/32/64.
   Compared against plain sampling on control adherence, diversity, smoothness and Kosta's preference.
6. Teacher stage: small regularised logistic preference model over control trajectories x music features; active, controlled comparisons
   (one control varied), uncertainty-targeted, ties allowed, repeats, and a held-out set of comparisons.
7. Music-fit critic: DEFERRED (selection can still be gamed by beat-hitting with dull movement). If ever built: harder negatives (same song
   wrong segment, shifted alignment, similar beat different structure) and a shortcut test.

Open framing for Kosta (no decision now): if step 1 shows coupling mostly in timing, the music-character to movement-character mapping
comes from the teacher (artist-authored), described as such.
Standing rules unchanged.

**Overseer notes (operational, not rulings):**
- Numbering: no 7.75 is recorded. `docs/PLANNER_BRIEF_VIEWINGS.md` (V2 sharpness, energy = vigour + sharpness, excerpt choice, two
  unexplained notes, data go) is still unanswered and keeps the number 7.75. Point 2 (style embedding includes V1/V2) partly covers its Q1.
- Beat grids: FineDance has stored offline grids (`t1b/cortex/beats/`); AIOZ, PhantomDance and Motorica have none. Step 1 uses the
  repository's existing offline beat tracker on their audio (no installs), checked first against FineDance's stored grids.
- The 10-song by-ear spot check is Kosta's; the builder prepares the songs and boundary times, the overseer serves them.
- Work split: WO46 (agent 2) = the 7.74 Q4 posture-vs-gesture diagnostic, then step 1 (replacing the 7.74 Q5 whole-song 0c plan, whose
  control-vs-acoustics part is folded into step 1). WO45 (agent 1) = A with point 2, plus point 3 report-only before training.

### 7.75 Viewings: controls validated by eye; PhantomDance + Motorica enter A; V1/V2 as style; energy = vigour + sharpness; excerpt choice; GO for A; 2026-11-16, via Kosta + planner (answering `docs/PLANNER_BRIEF_VIEWINGS.md` and `docs/PLANNER_BRIEF_DIAG.md` Q1)

Planner text, verbatim:

Controls validated by eye: 11/12 correct, 0 wrong (vigour 3/3, height 3/3, sharpness 3/3, continuity 2/3 + 1 same). Look check:
PhantomDance 6/6 yes, Motorica 5 yes + 1 partly ("tiny"). Kosta confirms: PhantomDance + Motorica enter A.

Q1 (a, modified): keep V1, V2 and mirrors in A; copy (V1/V2) part of A's domain/style embedding. NO V1 default: style chosen per song at
generation (sampled), sharpness from the controls (B, later the teacher). S-B reports sharpness-matched V1 vs V2; if V2 still looks flicky
at matched low sharpness, re-filter V2 (needs a ruling). Record: V1/V2 sharpness difference comes from the T0 low-pass cutoffs (2.50 vs
5.75 Hz), not arm proportions.

Q2 (a): sharpness stays its own control; perceived energy = vigour + sharpness. Viewings ask "more abrupt / flicky?".

Q3 (a): viewing excerpts where song RMS >= its own median, not in the first/last 10 s, same excerpt across conditions; S-C music-fit
viewings add 1-2 deliberately quiet excerpts per session, flagged.

Q4 (a): finding 5 open; A's intervention matrix also reports direction-change rate and base-rotation speed.

Diagnostic brief Q1: GO for A's training (3 seeds) as 7.73/7.74/7.76 point 2.

### 7.77 Beat coupling not accepted as a finding yet: verification V1-V4; B's first targets; cortex only as a variant; 2026-11-16, via Kosta + planner (answering `docs/PLANNER_BRIEF_METRIC.md`)

Planner text, verbatim:

Planner reading: no beat-phase locking in professional dance data contradicts published ground-truth beat-alignment results and is
consistent with a MEASUREMENT cause: a grid tempo error of up to 4 % drifts about 2 beats per minute, which erases whole-song phase locking
while keeping power at the beat period (observed). Not accepted as a finding yet.

Verification (report-only, before B's accent design):
- V1 local phase locking: per song, sliding windows of 8 beats with local tempo/phase re-estimated per window (from the grid AND from
  librosa), event phase concentration vs shuffled within-window controls; median over windows and songs, bootstrap by song.
- V2 published anchor: compute the standard beat-alignment score (BAS, as defined in the FineDance / Bailando evaluation code; state the
  source) on RAW FineDance ground truth and on our retargeted realised motion; compare with the value FineDance reports for ground truth. If
  our raw-data value is far from the published one, the pipeline is suspect; find why before anything else.
- V3 per-file sync: per FineDance file, cross-correlation of motion energy with the onset envelope over shifts -1..+1 s; report the offset
  distribution and any drift between first and last minute.
- V4 Kosta's grid click check (Q2 a), 10 songs, "are the clicks on the beat?".

Q1 (c, modified): B's first version predicts tempo (event rate per beat), slow controls (vigour, height, sharpness, pause over 2-8 s) and
phrase-level change probability. Beat-relative accent timing is NOT decided: after V1-V4, either learned (if locking appears) or an
authored rule tuned by the teacher, stated as authored in every write-up. AIST++ check when Kosta's registration arrives.
Q2 (a). Q3 (a): B's first version uses ear features + beat grid + onset/density features; the cortex enters only as a variant that must
beat it. Record for Kosta: if the cortex adds nothing to B either, it does not drive the dance and must not be shown on the monitor as
driving it.
Q4 (a): yaw lock report-only.
Standing rules unchanged.

**Overseer notes (operational, not rulings):**
- Fact for V1's interpretation: the grids are per-beat lists from the tracker (local inter-beat intervals), not one constant tempo, so a
  global tempo error does not accumulate along the song. The overseer's check with librosa beats in 20 s windows (25 FineDance songs,
  realised lamp-speed minima) gave R 0.177 against 0.159 / 0.165 with shifted beats; raw FineDance mocap gave whole-song R 0.079 against
  0.060. V1-V3 are still run as ruled; these numbers go next to them.
- V2 needs the published BAS code: no download is allowed for builders. The builder reimplements BAS from the paper's definition (FineDance /
  Bailando, stated with its formula and sigma) and the overseer checks it against the published formula; the published ground-truth value
  is quoted from the paper with its citation. If the code itself is needed, that is a download for Kosta to approve.
- V4 material (clicks on the grid) is prepared by the builder and served by the overseer, together with the 10-song section spot check.

### 7.78 Timing by entrainment (internal pulse, motor clock, coupling); B's first version; A retrain; 2026-11-17, via Kosta + planner (answering `docs/PLANNER_BRIEF_A_BEATV.md`)

Recorded as received (no earlier 7.78 draft reached the overseer). Planner text, verbatim:

== 1. FINDINGS RECORDED ==
1.1 Beat timing in human data:
 - BAS on raw FineDance (0.22) matches the published ground truth (0.212, Lodge CVPR 2024 Table 1), but equals its own shifted-beat
   chance level (+0.003 [-0.003, 0.009]). Published ground-truth BAS is at chance.
 - Dancers carry TEMPO (movement period power at the beat period, periodic base rotation), not beat-phase accent timing.
 - Caveat: evaluation-code variant not confirmed; AIST++ cross-check when Kosta's registration arrives. Possible thesis finding; verify
   before any claim.
1.2 Beat trackers fail in human-obvious ways (Kosta's V4 flash check):
 - project grid: dropouts, local irregularity (79 ms median residual);
 - librosa: wrong metrical level on slow songs, chases the fastest element (hats).
 Neither is used as a timing source from here.
1.3 A works:
 - human-level smoothness;
 - frozen share ~0;
 - follows vigour, height and sharpness;
 - 2-4 s coherence via the motif state.
 Pause is not followed; the accent pattern is only weakly followed; all seeds hit the epoch cap while still improving.
1.4 Perception (PLOS One 2019, audiovisual synchrony of human motion to music): temporal integration window ~300-450 ms total width;
observers judge from movement landings (lowest points, reach ends) and predict them. Exact on-beat placement is not needed; tempo matters
more than precise phase. Consistent with 1.1.

== 2. TIMING REDESIGN (Kosta: rethink, no patch stack) ==
Timing comes from ENTRAINMENT, not from an external beat grid or an authored accent rule.
2.1 INTERNAL PULSE:
 - A bank of nonlinear oscillators (resonance model of beat perception, after Large et al.; builder cites the exact model, equations and
   parameters used), log-spaced over 0.5-4 Hz, ~50-100 oscillators, driven by the onset envelope from the ear features with low-band
   (kick/rim) weighting.
 - Pulse = the oscillator with the highest amplitude x a preferred-tempo prior (centred ~2 Hz, stated), restricted to rates the arm can
   physically move at (servo basis stated: shoulder/base acceleration limits).
 - Required properties, to be verified: persists through dropouts and quiet sections; picks a sensible metrical level; stable within a
   section; follows genuine tempo changes.
 - All parameters fixed in the rules before any result; no per-song tuning.
 - Check (report): pulse vs librosa vs project grid on the 10 V4 songs (tempo, level, gaps, local regularity). Then Kosta's flash check
   of the pulse on the same 10 songs: blind, same protocol, questions "on the beat?" and "right speed?".
2.2 MOTOR CLOCK:
 - A's tokens are time-scaled so each token spans one pulse period, or two periods when one period is shorter than the arm's comfortable
   token duration (rule and threshold stated).
 - Token starts are aligned to pulse phase through the coupling in 2.3.
 - The decoder resamples its 25 Hz control points to the token duration.
 - Vigour and sharpness are measured AFTER scaling; A's control requests are compensated for the time-scaling (builder states the method).
 - Gates at 1.25 apply after scaling.
2.3 COUPLING:
 - One parameter for how tightly token phase follows the pulse: 0 = free-running at the pulse period, 1 = fully phase-locked. Default
   0.7, fixed in the rules. The teacher tunes it later.
 - Phase target: movement landings (lamp-speed minima / reach ends) within +-150 ms of the pulse. Precision beyond that is not a goal.
 - Report: landing-to-pulse phase distribution, share within +-150 ms, jitter and smoothness vs re-joined human level.
2.4 Dropped as timing mechanisms: librosa and the project grid as timing sources for B and for generation; the half-time selection rule;
the rate-cap rule; the time-warp layer; the accent pattern as a timing lever (it stays a measured A control).
2.5 Framing for every write-up: "it learned to move from dancers; it keeps time the way humans do, by entraining to the music; how tightly,
its teacher shaped." The entrainment mechanism is designed (a model of a human mechanism, like the cortex), not choreography.

== 3. B (first version) ==
 - Tempo comes from the internal pulse.
 - B predicts slow controls (vigour, height, sharpness, pause over 2-8 s) and phrase-change probability, from ear features + pulse state +
   onset/density features.
 - Cortex only as a variant that must beat this.
 - Later variant: the cortex's beat band driven by the internal pulse instead of the project grid (its beat input currently comes from the
   flawed grid; this may be why it adds nothing). Evaluated against B without the cortex.

== 4. A RETRAIN AND OTHER QUESTIONS ==
Q3 (a): retrain A to convergence (cap 100, early stopping as ruled), 3 seeds; rerun all checks.
Q4 (a): up-weight windows containing pauses (factor stated in the rules); the pause request gets the same corruption and dropout treatment
as the other controls; report the pause intervention again.
Q5 (a): cross-talk report-only; judge by eye in S-B.
Q6 (a): keep the residual gesture stage.
Q7 (a): S-B viewing after the retrain, on the new A, with the prepared conditions (human; A with own / other / shuffled / constant
controls; V1 vs V2 matched on realised sharpness). Add per excerpt: A with motor clock (coupling 0.7) vs A at fixed 0.5 s tokens, with
music. Excerpts per 7.75 Q3. Answers A / B / tie / both poor + confidence.

== 5. ORDER ==
1 internal pulse + numeric check; 2 Kosta's pulse flash check; 3 A retrain (may run in parallel with 1-2); 4 motor clock on the new A;
5 S-B viewing; 6 B first version.

Standing rules unchanged.

**Overseer notes (operational, not rulings):**
- Work split: WO48 (agent 2) = 2.1 internal pulse + numeric check + flash-check material (served by the overseer). WO49 (agent 1) = 4 A
  retrain (Q3, Q4) + all checks rerun. The motor clock (2.2/2.3) and the S-B viewing follow as later work orders.
- The pulse bank's citation and equations are reconstructed by the builder from the published papers (no downloads); the overseer checks
  them against the papers before results are read.

### 7.79 "Fits the music" = four levels scored in lookahead selection; motor clock paused; factorial viewing; cortex as event detector; pulse Q1-Q4; 2026-11-17, via Kosta + planner (answering `docs/PLANNER_BRIEF_PULSE_AIST.md` + addendum)

Recorded as received. It supersedes the planner's earlier 7.79 draft (landing-opportunity mechanism); that draft never reached the overseer.
Planner text, verbatim:

TO: overseer. FROM: Kosta via planner. Re: PLANNER_BRIEF_PULSE_AIST + addendum (2026-11-17). Record as BRAIN_SPEC 7.79. Supersedes the planner's earlier 7.79 draft (landing-opportunity mechanism) if received.

Kosta's statement (verbatim): "the purpose isnt to find the beat, but possible end locations to match music, so it isnt just flashing on beat, but flashing at oportune moments e.g. beat/dropout/accent whatever right?"

DESIGN READING (planner, after re-deriving from all of Kosta's viewing notes): "fits the music" has four levels:
 1 TEMPO/groove (movement period matches the music's; supported by human data);
 2 EVENTS (response to salient moments: drops, dropouts, accents, entries; the response may be a landing, hold, burst, rise or change, chosen freely);
 3 CHARACTER (size/energy/level match the music's feel; B + teacher);
 4 STRUCTURE (change when the music changes, return when it returns).
Beat-phase placement is NOT a goal (human data, perception study, Kosta never asked for it). These four are not separate timing modules: they become the scoring terms of the planned LOOKAHEAD SELECTION (7.74/7.76): A proposes futures at the pulse tempo; futures are scored on alignment of their landings, holds, changes and controls with the music at each level; feasibility hard; the weights between levels are what the teacher tunes.
HOLD: no motor clock or landing-opportunity implementation yet (7.78 2.2-2.3 and the previous draft are paused).

STEP 1, FACTORIAL VIEWING (test tooling only, not architecture): what matters to Kosta's eye.
 - Material: current A outputs (or the retrain's when ready) on 6 excerpts (7.75 Q3 rules, at least 2 with a drop or dropout), 10 s each, with music, lamp head.
 - Factors, applied by test-only time-scaling/warping of the same movement:
   T tempo: movement period matched to the pulse vs 15 % off;
   P phase: landings pulled to pulse events (+-150 ms) vs random phase;
   E events: at drops/dropouts/strong accents (detected causally from ear features, rules stated) the movement lands or holds vs ignores them.
 - 2 x 2 x 2 = 8 versions per excerpt, 48 clips, blind random order. Kosta rates each 1-5 "fits the music" + optional note. Repeat 4 clips for consistency.
 - Report: mean effect of T, P, E and interactions, with song-level bootstrap.
STEP 2, report-only: cortex surprisal as an EVENT detector: alignment of surprisal peaks (per layer) with drops, dropout onsets/ends and section changes (ear-based detections and the 10 V4 songs checked by ear) vs ear-feature event detectors. If the cortex detects events better, it becomes the planner's event source.
Pulse questions:
 Q1 (d): second flash check on the 3:2 / 2:3 songs + the two failures; (b) harmonic-support readout only if they fail.
 Q2 (b): arm cap from A's measured shoulder amplitude at high vigour.
 Q3 (a): amend 7.78 1.1: beat-phase locking is dataset-dependent (FineDance at chance; AIST++ small but above chance, +0.016 to +0.067); tempo carrying holds.
 Q4: clips under 12 s excluded from pulse-driven use and summaries; report-only.
Please send the A retrain (A2) brief to the planner if it has open questions.
Standing rules unchanged.

**Overseer notes (operational, not rulings):**
- "Current A" = A2, seed 49102 (lowest validation total; `docs/A2_REPORT.md`). The A2 brief (`docs/PLANNER_BRIEF_A2.md`, 3 open questions)
  was given to Kosta for the planner on 2026-11-17. Its Q2 (S-B after the motor clock) and Q3 (motor-clock work order) are affected by the
  HOLD above.
- Defaults the overseer set for Step 1 (not ruled; the work order names them):
  - T "15 % off": 3 excerpts slower, 3 faster, fixed per excerpt before rendering;
  - the 4 repeated clips: one per T x E cell, drawn with a fixed seed; they are not scored as separate items;
  - rating options 1-5, with an optional note;
  - the speed cap still holds in every version (Q2 is not yet built, so 7.78's current cap is used).
- Work split: Step 1 to the builder (agent 1). Step 2 and Q1's second flash check to overseer subagents, because they are small and
  independent.

### 7.80 Pulse = tempo source only; pulse v2 (harmonic readout, stability, confidence) with a fixed decision rule; event selectivity requirement; 2026-11-17, via Kosta + planner (answering `docs/PLANNER_BRIEF_PULSE_FLASH2.md`)

Recorded as received. Planner text, verbatim:

TO: overseer. FROM: Kosta via planner. Re: PLANNER_BRIEF_PULSE_FLASH2 (2026-11-17). Record as BRAIN_SPEC 7.80.

Role clarified (7.79): the pulse is the TEMPO source only (period, phase, confidence), not a landing clock. "On the beat?" is no longer a criterion for the pulse; criteria are right speed and stability.
Q1: pulse v2, one work order, rules fixed before results:
 (b) harmonic-support readout (candidate amplitude + amplitudes at 2f and f/2, after Large's metrical readout).
 (s) stability: a level change needs sustained evidence (hold and margin stated, longer/higher than 2 s / 20 %), preferably at a large novelty or phrase boundary (detector stated).
 (c) CONFIDENCE output instead of the (g) gate: the pulse always runs; it outputs period, phase and confidence (oscillator amplitude relative to the bank, normalised; stated). Low-band periodic drive absent -> confidence falls; state keeps running so the beat resumes in phase. Holds in breaks are a movement choice made by the planner (event level), not a pulse output.
 Numeric check as before plus: level switches per minute, confidence during silence/beatless/dropout passages vs beat passages.
 Viewing: same 40 items (both checks), pulse v2 vs librosa, blind; questions "right speed?" (right / too fast / too slow) and "steady?" (yes / switches); flashes shown with brightness = confidence. Scored per item against Kosta's earlier answers.
 DECISION RULE (fixed now): pulse v2 must match or beat librosa on "right speed" and on stability across the 40 items. If not, stop tuning the oscillator bank and report for a Kosta ruling on the tempo source.
Q2 (a): the pulse stays the tempo source; events come from the event detector. Kosta's note "catch the distinct stuff" = event selectivity relative to context; record it as the requirement for the event detector (surprise-like: distinct relative to recent context, sparse). Event-only flash check once the event source is ruled. Send the CORTEX_EVENTS brief to the planner if it has open questions.
7.79 STEP 1 (factorial viewing T x P x E) proceeds with whichever pulse is current; it does not wait for pulse v2.
Standing rules unchanged.

**Overseer notes (operational, not rulings):**
- **"Same 40 items":** the 20 song-excerpts of the two flash checks (10 each). Each is shown once with pulse v2 and once with librosa, so
  there are 40 items in the session. The librosa items are re-rendered with the new question set, so both sources get the same questions.
- **Decision rule as the overseer will score it:**
  - right speed = count of "right" over the 20 excerpts, pulse v2 vs librosa;
  - stability = count of "yes" to "steady?";
  - "match or beat" means pulse v2 ≥ librosa on both counts.
- **Who builds:** pulse v2 (WO51) goes to an overseer subagent, because the one builder (agent 1) takes WO50. WO50 uses pulse v1, as 7.80
  allows.
- **The CORTEX_EVENTS brief** (3 open questions) was given to Kosta for the planner on 2026-11-17.

### 7.81 Timing is learned, not hand-built: rhythm and event-response controls for A; trackers become B senses; timing mechanisms dropped; 2026-11-18, via Kosta + planner (answering `docs/PLANNER_BRIEF_TEMPO_SOURCE.md`)

Recorded as received. It supersedes the planner's earlier 7.81 draft (librosa + confidence decision); that draft never reached the
overseer. Planner text, verbatim:

TO: overseer. FROM: Kosta via planner. Re: PLANNER_BRIEF_TEMPO_SOURCE (2026-11-18). Record as BRAIN_SPEC 7.81. Supersedes the planner's earlier 7.81 draft (librosa + confidence decision) if received.

RETHINK (Kosta): since 7.78 timing was built as a hand-made layer on top of A (pulse -> motor clock -> coupling -> landing opportunities -> tracker choice), each round adding a rule. Stopped. Timing is LEARNED like the other controls:
1. New A controls, measured from human motion (definitions fixed in rules before computing):
 - MOVEMENT RHYTHM: per 2-4 s window, dominant period of lamp/joint velocity (autocorrelation), expressed as a ratio to the librosa beat period, binned {1/2, 1, 2, other/none}, plus a rhythm-strength value.
 - EVENT RESPONSES: hold (pause onset), change (gesture-family or posture change), burst (vigour jump) per token, already partly measurable; stated.
2. Trackers and oscillators become SENSES (B inputs only): librosa beat phase/period, pulse v2 phase/period/confidence, onset/density features, ear features, cortex surprise. No tracker drives the movement directly. B learns which help; ablations report each sense's contribution.
3. Dropped as mechanisms: motor clock time-scaling, coupling parameter, landing-opportunity rules, tracker selection, anti-doubling rules. The pulse comparison closes with no winner declared: the viewing difference is within Kosta's between-session variability.
4. FIRST (report-only): in the human data, distribution of movement-rhythm ratio to beat (does it cluster at 1/2, 1, 2?), per dataset, using librosa AND pulse v2 periods; and relation of hold/change/burst to music events (onset, dropout, novelty, cortex surprise), with lags +-1 s, bootstrap by song. Outcome decides whether rhythm is learned by B (clusters present) or shaped by the teacher (absent).
5. A retrain (A2): add the rhythm and event-response controls if step 4 is ready before A2 starts; otherwise in the next A training. Intervention matrix includes rhythm (1/2 vs 1 vs 2) and hold requests.
6. Lookahead planner (later): no timing rules; scores futures against B's predicted controls including rhythm and event responses.
7. 7.79 STEP 1 factorial viewing: still run as information on what Kosta's eye weighs; nothing waits on it.
Send the A2 brief to the planner if it has open questions.
Standing rules unchanged.

**Overseer notes (operational, not rulings):**
- **A2 is already trained** (WO49, merged 2026-11-17, `docs/A2_REPORT.md`), so under item 5 the rhythm and event-response controls go into
  the next A training (A3). The A2 brief (`docs/PLANNER_BRIEF_A2.md`) still has open questions: Q1 pause/stillness, now also covered by the
  "hold" event response; Q2/Q3 were overtaken by 7.79-7.81. Kosta has it to forward again.
- **Pulse v2 stays** in the repo as a sense (merged, fb3eacd). 7.78 2.2-2.3 and 7.80's decision rule are closed.
- **Step 4** goes to an overseer subagent as WO52 (`docs/BUILDER_PROMPT_WO52_RHYTHM_EVENTS.md`).
- **WO50** (the factorial viewing, item 7) still waits for Kosta's "send" to agent 1. Its warps are viewing tooling only and do not
  conflict with item 3.

### 7.84 Mismatch test before WO50 and B; paired forced-choice viewing protocol; raw-joint rhythm rerun; one combined A3/B ruling later; 2026-11-18, via Kosta + planner (answering `docs/PLANNER_BRIEF_OVERSEER_QUESTIONS.md`)

Recorded as received, before any result it scores. Planner text, verbatim:

TO: overseer. FROM: Kosta via planner. Re: PLANNER_BRIEF_OVERSEER_QUESTIONS (2026-11-18). Record as BRAIN_SPEC 7.84.

1. MISMATCH TEST: adopted, runs before WO50 and before any B work. A3 training may run in parallel (its controls serve as teacher knobs regardless).
 - Material: retargeted human clips (FineDance + PhantomDance + Motorica, mix of V1/V2, realised stage, lamp head), 10 s, excerpts per 7.75 Q3.
 - Pairs: same movement with its own music vs (a) the same song shifted by a random 2-6 s, or (b) a different song within 5 % tempo. Half of each kind. About 20 pairs + 5 repeats (>= 20 %); order and side randomised and checked.
 - Question: "which fits the music better?" (first / second / same) + confidence.
 - Decision rule stated in advance: Kosta picks the real pairing in >= 70 % of non-tie answers AND above his repeat-flip rate -> data carry visible fit; otherwise timing/fit is treated as teacher- and planner-shaped, and data-learned timing is deprioritised.
 - Report separately for shifted vs different-song pairs.
2. VIEWING PROTOCOL from now: paired forced choice wherever versions are compared; >= 20 % hidden repeats per session; minimum effect size stated in advance and larger than the measured test-retest flip rate. WO50 restructured as proposed: main effects T, P, E as paired comparisons (factor on vs off, others fixed), 6 excerpts x 3 x 2 orders = 36 pairs + 8 repeats; runs after the mismatch test.
3. RAW-JOINT RHYTHM: adopted, report-only, with the mismatch test: rerun the rhythm part of WO52 on raw human joints (wrists, feet, pelvis, head) before retargeting; compare period distributions and beat-ratio clustering with the retargeted lamp. If raw joints cluster at 1/2, 1, 2 and the arm does not, record the arm/retarget as the bottleneck.
4. CONSOLIDATION: one combined ruling "A3 controls and B senses" after the planner sees the A2 and CORTEX_EVENTS briefs (send both). Principles already fixed: hold/pause is an A control (7.82 Q2); all trackers, the pulse and the cortex are B senses (7.81); 7.83's free-dance positive control and data check stand.
Order: mismatch test + raw-joint rhythm (and the 7.83 data check) -> WO50 -> B design. A3 in parallel.
Standing rules unchanged.

**Overseer notes (operational, not rulings):**
- **Numbering gap:** 7.82 and 7.83 are cited above but are not recorded in this file; their texts never reached the overseer. They keep
  their numbers and are recorded when Kosta pastes them. Until then "hold/pause is an A control" (7.82 Q2) is taken as stated here, and
  the 7.83 data check cannot be specified.
- **WO50** (`docs/BUILDER_PROMPT_WO50_FACTORIAL.md`, 48 rated items + 4 repeats) is superseded in its viewing design by item 2 (36 paired
  items + 8 repeats) and must be rewritten before it is sent. It waits for the mismatch test's result.
- **Repeat-flip rate** for the item 1 rule is measured within the mismatch session itself (the 5 hidden repeats), not taken from the
  pulse2 test-retest.

### 7.85 Raw-joint rhythm: item 3 "not shown"; retarget removes fast movement (report only); one combined A3/B ruling after four inputs; 2026-11-19, via Kosta + planner (answering `docs/PLANNER_BRIEF_RAWRHYTHM.md`)

Recorded as received, before any result it scores. Planner text, verbatim:

TO: overseer. FROM: Kosta via planner. Re: PLANNER_BRIEF_RAWRHYTHM (2026-11-18). Record as BRAIN_SPEC 7.85.

Q1 (a): chance 1 (similar-tempo song) decides. Raw-joint beat-ratio clustering beyond tempo class is <= ~1 percentage point and mixed in sign; item 3 recorded as "not shown": the arm/retarget is not the bottleneck for beat-ratio clustering. Chance-2 results reported alongside, labelled as tempo-class effects.
Q2 (a): report-only. Record: the retarget removes fast movement (1/2-beat share 0.090 -> 0.020; median period 1.07 -> 1.24 s). A3's intervention matrix reports whether the arm produces 1/2-beat rhythm on request.
Q3 (a): one combined ruling "A3 controls and B senses" after: the mismatch test (7.84 item 1), the 7.83 data check / free-dance positive control, and the A2 and CORTEX_EVENTS briefs (send both to the planner).
Standing rules unchanged.

**Overseer notes (operational, not rulings):**
- Numbers behind Q1/Q2 are in `docs/RAWRHYTHM_REPORT.md` (merged body 5dd8d9f); the overseer recomputed all 20 point estimates.
- The combined ruling waits on four inputs: the mismatch test result (WO53 part A, not yet built), the 7.83 data check (7.83 text has
  not reached the overseer), and the planner seeing `PLANNER_BRIEF_A2.md` and `PLANNER_BRIEF_CORTEX_EVENTS.md` (Kosta to forward).
- A3's work order stays unwritten until that ruling.

### 7.86 Shifted-foil preference is systematic; coupling conclusions 7.74-7.85 on hold; end-to-end sync audit first; 2026-11-19, via Kosta + planner (answering `docs/PLANNER_BRIEF_MISMATCH.md`)

Recorded as received, before any result it scores. Planner text, verbatim:

TO: overseer. FROM: Kosta via planner. Re: PLANNER_BRIEF_MISMATCH (2026-11-19). Record as BRAIN_SPEC 7.86.

Q1: neither (a) nor (c). Rule outcome NOT applied yet. The shifted-foil preference (8/8 non-tie, p ~0.008) is a systematic effect, not noise, and the most likely cause is a time offset between movement and music somewhere in the pipeline. Such an offset would also produce the weak-coupling results of 7.74-7.85 (beat phase at chance, V3 offsets spread +-1 s, weak events/structure). All coupling conclusions 7.74-7.85 are ON HOLD pending a sync audit.
Q2 (extended): END-TO-END SYNC AUDIT, report-only, before anything else that uses music timing:
 A1 synthetic probe: synthetic audio (clicks at known times) + synthetic human motion (sharp joint impulses at the same times, in the FineDance input format); run through the full pipeline exactly as used for the mismatch clips and for WO47/52/53 measures: loading, retarget, low-pass, spline, warm-up, spinal layer, limiter, servo, v2p body, CSV export, rendering, audio muxing. Report the offset between clicks and motion impulses at every stage's output, including the final video (audio track vs frames) and the arrays the measures read.
 A2 known-aligned reference: AIST++ sequences (registration done) through the same pipeline; beat-alignment and onset-motion cross-correlation on raw keypoints vs after each stage.
 A3 the overseer's per-song lag diagnostic (lamp speed and raw joints vs onset/energy envelope, lag distribution per dataset, bootstrap by song, vs shifted-song chance).
 A4 code review of every place where time origins are set: dataset loaders (motion vs audio start, trimming, fps), the 10 s warm-up, window extraction, clip excerpt start times, muxing. List each with its offset handling.
Outcome rules: if any stage introduces an offset > 50 ms or a dataset loader misaligns motion and audio, fix it, record which earlier results it touched, rerun WO47 (beat phase), WO52/53 (rhythm, events) and round 2 of the mismatch test on the fixed pipeline. If no offset is found anywhere, record the foil preference as an unexplained finding and apply the 7.84 rule outcome.
Q3: round 2 of the mismatch test only after the audit; with the instruction page explaining shifted pairs, offsets 4-6 s, different-song foils from a different dataset when tempo allows, fresh excerpts, 5 repeats.
7.83 (Jyväskylä data check / positive control) proceeds in parallel; it uses a fresh loader and is an independent check of the measures.
Standing rules unchanged.

**Overseer notes (operational, not rulings):**
- The audit is report-only, but its outcome rule allows FIXES when a stage adds an offset above 50 ms or a loader misaligns motion and
  audio. A fix needs the overseer's go-ahead first (the builder reports the finding; the overseer verifies and orders the fix and the
  reruns). Fixes never touch the frozen `src/` or `tools/`.
- The 7.83 text has still not reached the overseer, so the Jyväskylä check cannot be specified; it is not part of WO54.
- Sync audit work order: `docs/BUILDER_PROMPT_WO54_SYNC_AUDIT.md`.
