# The brain, B1–B3: spec with checks fixed in advance

Status: **draft, 2026-10-29, awaiting the user's yes. Nothing is built before it.**
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
- ★ B1: after the checks are committed; after results.
- **If B1 fails twice:** the pulse comes from the offline analysis grid, labelled
  "beat grid" on the monitor, and the B1 claims are dropped.

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
  | L3 | 0.5–4 Hz | +2 s | beat, meter |
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
  - "An oscillator bank entrains to the beat of music it has not heard."
  - "It keeps the pulse through short silences."
  - "Its oscillators resonate at the bar, telling triple from duple time."
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

## 7. Out of this spec

Ignition (cross-band coherence events), B4 dreaming, B5 monitor, B6 staging.

## 8. Fixed before any result (committed with each check)

- Test sets and their hashes.
- The exclusion list.
- Seeds.
- The artist split.
- The licence filter.
- The compute cap.
- The feature code.
- The GrFNN parameters with their sources.

## 9. Open points

None in the design. U1 (corpus access), U2 (the overseer's fills) and U3 (the two changed
numbers) are ruled above. The spec waits for the user's yes.
