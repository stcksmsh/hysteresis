# GrFNN (Hopf bank) parameters for B1, with sources

Fixed before any check (BRAIN_SPEC section 8). Nothing here was tuned on a test set.
Code: `grfnn.py`. Spec: `docs/BRAIN_SPEC.md` section 2.1.

## Sources actually read

| Short name | Reference | Where it was read |
|---|---|---|
| **Large 2015** | Large EW, Herrera JA, Velasco MJ (2015). Neural networks for beat perception in musical rhythm. Front. Syst. Neurosci. 9:159. doi 10.3389/fnsys.2015.00159 | Full text via Europe PMC (PMC4658578), saved at `/secondary/hyst-data/brain/papers/large2015.xml`. Equations (2), (3), (4) are in section 3 ("Oscillatory network interactions could give rise to musical pulse perception"); Figure 4 caption. The article has e-page 159 only; there are no printed page numbers. |
| **Velasco & Large 2011** | Velasco MJ, Large EW (2011). Pulse detection in syncopated rhythms using neural oscillators. Proc. ISMIR 2011, poster session 2. | `https://ismir2011.ismir.net/papers/PS2-3.pdf`, saved at `.../papers/velasco2011.pdf`. Section 2.1 "Model" (PDF p. 3) and section 3.2 (PDF p. 4). |
| **Lambert 2014** | Lambert AJ, Weyde T, Armstrong N (2014). Beyond the beat: towards metre, rhythm and melody modelling with hybrid oscillator networks. Proc. ICMC/SMC 2014. | `http://www.icmc14-smc14.net/images/proceedings/PS3-B03-BeyondtheBeat.pdf`, section 3.1 "GFNN" (PDF p. 2-3). Used only to cross-check the equation form. |
| **Large 2010** | Large EW, Almonte FV, Velasco MJ (2010). A canonical model for gradient frequency neural networks. Physica D 239:905-911. | **Not read.** The only open copy found (`musicdynamicslab.uconn.edu/.../LargeAlmonteVelasco2010PubsAHEdits.pdf`) refused the connection (ECONNREFUSED) on 2026-10-29; Europe PMC has no record of it. Its equations are quoted in Large 2015 (Eq. 3, 4) and Lambert 2014 (Eq. 1), which is what the code follows. |

**Neither Large 2015 nor (unread) Large 2010 gives the simulation parameter values the spec asked for.** Large 2015
states the model and the critical point (alpha = 0) and gives no oscillator count, frequency range, density, beta
or epsilon value (checked in the whole text, all figure captions, no tables). The nearest published source with
numbers for the same canonical model, same group, used for pulse detection, is **Velasco & Large 2011**. The values
below are taken from it. This substitution is listed for the overseer's ruling.

## Model

dz/dt = z (alpha + i w + beta1 |z|^2 + eps beta2 |z|^4 / (1 - eps |z|^2)) + c P(eps, x) A(eps, conj z),
P = x / (1 - sqrt(eps) x), A = 1 / (1 - sqrt(eps) conj z), w = 2 pi f.

| Item | Form used | Source |
|---|---|---|
| Intrinsic terms | alpha + i w + beta1 abs(z)^2 + eps beta2 abs(z)^4 / (1 - eps abs(z)^2) | Large 2015 Eq. (2) (series form "alpha + i2pi + beta1 abs(z)^2 + eps beta2 abs(z)^4 + ..."); the closed form of the higher-order terms is Lambert 2014 Eq. (1); Velasco & Large 2011 section 1.2 Eq. (3) names beta1, beta2, c, delta1, delta2, eps |
| Passive coupling P(eps, x) = x / (1 - sqrt(eps) x) | closed forms of the series | Large 2015 Eq. (3); Lambert 2014 Eq. (1) |
| Active coupling A(eps, conj z) = 1 / (1 - sqrt(eps) conj z) | closed form of the series | Large 2015 Eq. (4); Lambert 2014 Eq. (1) |
| Time scale | unscaled time, w = 2 pi f (radians per second) | Velasco & Large 2011 section 1.2 and Lambert 2014 Eq. (1). Large 2015 Eq. (2) writes tau_i dz/dt with tau_i = 1/f_i, which scales alpha and beta by f_i; the unscaled form is used because the beta1 and beta2 values below are given for it |
| Detuning delta1, delta2 | 0 (absent) | Large 2015 Eq. (2) has no delta terms. Velasco & Large 2011 names them and gives no values |

## Values

| Parameter | Value | Source | Status |
|---|---|---|---|
| alpha | 0 (critical, "poised between damped and spontaneous oscillation") | Velasco & Large 2011 section 2.1; Large 2015 section 3 and Figure 4A caption (alpha = 0 is the critical point) | from the paper |
| beta1 | -1 | Velasco & Large 2011 section 2.1 | from the paper |
| beta2 | -0.25 | Velasco & Large 2011 section 2.1 | from the paper |
| eps | 1 | Velasco & Large 2011 section 2.1 | from the paper |
| Number of oscillators | 289 over 0.25-16 Hz | Velasco & Large 2011 section 2.1 ("289 oscillators ... logarithmically spaced from 0.25 Hz to 16 Hz") | from the paper |
| Density | 48 per octave (289 oscillators over 6 octaves = 48.08 per octave; 48 steps per octave gives 289 over 0.25-16 Hz) | derived from the line above; the paper does not state a per-octave figure | derived |
| Range used | 0.25-8 Hz, log spaced, 5 octaves x 48 + 1 = 241 oscillators | the spec's range (BRAIN_SPEC 2.1) at the density above | spec + derived |
| Frequency spacing | logarithmic | Velasco & Large 2011 section 2.1; Lambert 2014 section 3.1 (128 oscillators, 0.25-16 Hz, logarithmic - a different count) | from the paper |
| Coupling c | 1 (the gain is applied in the input scaling below) | not in the papers: Velasco & Large 2011 names c "strength of coupling to the external stimulus" and gives no value | **not published here; chosen** |
| Input gain C_IN | 0.05 per unit of summed z-score | not in the papers | **chosen from synthetic signals** (see below) |
| Input cap X_MAX | 0.5, so that x < 1 / sqrt(eps) = 1 and P stays finite | follows from the form of P with eps = 1; the value 0.5 is not published | **chosen from the bound** (see below) |
| Input half-wave rectification | negative sums are set to 0 | not in the papers | **chosen** (see below) |
| Input standardisation | running z-score, exponential mean and variance, time constant 10 s, prior mean 0 and variance 1, causal | spec says "each standardised, summed with equal weight" (BRAIN_SPEC 2.1 planner review); the form is not specified | **chosen** (see below) |
| Integration | RK4, 5 ms sub-step (two per 10 ms frame), input held over each frame | not in the papers (Velasco & Large 2011 section 2.3 only says Matlab 7.4) | **chosen** |
| Initial state | z = 0.001 (real), same for every oscillator | not in the papers | **chosen** |
| Safety clip | abs(z) is clipped to 0.95 after each step, so A stays finite when eps = 1 | not in the papers | **chosen** |
| Stimulus shape | onset strength and low-band flux at 100 Hz from the full mix (the paper renders events as "continuous time onset bumps", section 2.2) | Velasco & Large 2011 section 2.2 | spec |

Also in the papers, not used here (listed so they are not lost): a critical bank in Lambert 2014 uses alpha = -0.1,
beta = -0.1, eps = 0.5 with 128 oscillators over 0.25-16 Hz; the double-limit-cycle motor network of Velasco & Large
2011 section 3.2 uses alpha = 0.3, beta1 = 1, beta2 = -1, eps = 1. B1 has the sensory (critical) network only.

## Readout (spec, BRAIN_SPEC 2.1)

Beats are the upward phase-zero crossings of the strongest oscillator (by amplitude abs(z)) with natural frequency
in 0.5-4 Hz. The readout switches to another oscillator only when some oscillator's amplitude exceeds the current
one's by more than 20 % on 2 s of consecutive frames (`SWITCH_RATIO = 1.2`, `SWITCH_SECONDS = 2.0`). Crossing times
are linearly interpolated inside a frame.

## What the synthetic tests show (not a check result)

A click train drives the bank at the click frequency when each click is a bump about 30 ms wide (the width
the 46 ms STFT gives real onset strength). A one-frame impulse train has equal amplitude at every harmonic, and the
strongest oscillator in 0.5-4 Hz is then the one at the band edge (4 Hz for 2 Hz clicks, 3 Hz for 1.5 Hz clicks):
the readout rule picks a harmonic. The tests use the bump; this is reported to the overseer as a property of the
rule, not changed.

## How the four input choices were made (synthetic signals only; no Ballroom, GTZAN or SMC audio was used)

- **X_MAX = 0.5.** P(eps, x) = x / (1 - sqrt(eps) x) is singular at x = 1 when eps = 1, so x must stay below 1. Half the bound
  was taken as a margin. Fixed from the equation, not from any signal.
- **Half-wave rectification.** The input channels are non-negative series with a mean taken out by standardisation. A
  negative forcing would act as an anti-pulse between events; the stimulus the papers describe is a train of positive
  "onset bumps" (Velasco & Large 2011 section 2.2). Fixed from that description, not from any signal.
- **Standardisation, 10 s.** Chosen a priori: long against a beat (0.25-2 s) and about four bars at 120 bpm, short
  against a clip (30 s), causal so that the live system can use it. Not swept.
- **C_IN = 0.05.** The only value chosen by looking at signals. Candidates 0.05, 0.1, 0.2, fixed in advance. Criterion
  fixed in advance: the largest ratio of the readout amplitude on a 2 Hz click train to the readout amplitude on
  half-wave-rectified Gaussian noise alone. Results (40 s synthetic inputs, bump width 30 ms, height 4, mean over the
  last 15 s; the noise is 4000 frames from a seeded generator):

  | C_IN | 2 Hz clicks: readout Hz, amplitude | 1.5 Hz clicks: readout Hz, amplitude | noise only: readout amplitude | ratio (2 Hz clicks / noise) |
  |---|---|---|---|---|
  | 0.05 | 2.00, 0.41 | 1.50, 0.41 | 0.068 | 6.0 |
  | 0.1 | 2.03, 0.56 | 1.50, 0.57 | 0.166 | 3.4 |
  | 0.2 | 2.03, 0.62 | 1.52, 0.61 | 0.201 | 3.1 |

  The bank entrains to the click frequency at all three; the criterion picks 0.05. (The first draft of `grfnn.py` had 0.1,
  written before this sweep; the change is recorded here.) Script: `scripts/brain/synthetic_input_sweep.py`.

## SD floor of the running z-score (BRAIN_SPEC 2.2 correction, 2026-10-29)

The running SD never falls below 1e-3 of a reference SD, per channel: `SD_REF_FLUX = 4.4373` (30-200 Hz flux) and
`SD_REF_ONSET = 1.4513` (onset strength). B1 has no training corpus, so these are fixed now from a synthetic,
training-free source: 5 seeds x 30 s of the test-suite pulse-and-bed generator (`sd_reference.py` prints them). A constant,
not a corpus value, so that the floor is the same for every clip and B1 does not depend on the B3 corpus. The floor matters
only where the running SD collapses (digital silence); tested: a silent gap gives finite input (`test_gaps.py`).
