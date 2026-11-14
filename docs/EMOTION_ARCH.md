# Emotion encoder: the current architecture (stage 1, as built)

State on 2026-10-13, branch `keys-decide`, code in `scripts/emotion/`. This file
describes what exists, not what is planned. The spec is `docs/EMOTION.md`; the
numbers are in the "Emotion stage 1: encoder" entry of `docs/DANCE_HANDOFF.md`.

## In one picture

```
audio ─┬─ mix features (20 Hz) ──────────┐
       ├─ Demucs stems ─ stem features ──┤ summarised per 4 s window → baseline (49)
       ├─ MERT-v1-95M (75 Hz, 13 layers) ─ mean of layers, mean over 4 s → 768
       ├─ CLAP music (one 4 s clip each) ─────────────────────────────── → 512
       └─ Essentia EffNet (2 s patches, 0.5 s hop) ─ mean over 4 s ─────── → 1,280 + 56 mood
                                                                           │
                            concatenate, raw, no reduction ────────────────┘
                                           │
                           one vector of 2,665 numbers every 0.5 s
                                           │
                    ┌──────────────────────┼──────────────────────────┐
              mean per beat          check 1 (ridge readouts)    report (ridge + nearest clips)
           (sidecar `perBeat`)      DEAM V/A, Emotify GEMS        per 10 s of each song
```

Nothing downstream of the sidecar reads it yet. The planner and version 47 are
unchanged.

## The parts

### 1. The step

The unit is a **4 s window, one every 0.5 s**. Each window gets one vector.
Window `k` is centred at `k × 0.5 s`. For a 5:40 song that is 680 vectors.

### 2. The five components, and how much of the song each one sees

| Component | Dims | What it is | Time it sees per vector |
|---|---|---|---|
| `baseline_stems` | 49 | the sidecar's own signals, from audio: loudness, five bands, centroid, flatness, flux (mean, std, max over the window), onset density, periodicity (29); per stem (vocals, drums, bass, other): level mean and std, flux, power share, which stem leads (20) | the 4 s window only |
| `mert_avg` | 768 | MERT-v1-95M, a self-supervised music transformer; hidden states at 75 Hz, mean of all 13 layers, then mean over the window | the window, but each hidden state has attended to the whole input it was run on (see below) |
| `clap` | 512 | LAION CLAP, music checkpoint; the window is fed as its own clip (padded to CLAP's 10 s input) | the 4 s window only |
| `essentia_effnet` | 1,280 | Discogs-EffNet embedding, trained to tag genre/style; 2 s patches every 0.5 s, mean of the patches inside the window | about 4 s |
| `essentia_mood` | 56 | the mtg_jamendo mood/theme head on those patches (56 tag probabilities: "sad", "dark", "energetic", ...) | about 4 s |

MERT's context differs between the library and the songs:
- Library clips (DEAM, Emotify) were run whole, so each hidden state saw the
  whole 45–60 s clip.
- The danced songs were run in 30 s chunks with 5 s of context each side, so
  each hidden state saw at most 40 s.

### 3. Combining

The five blocks are concatenated as raw numbers: 2,665 per step. Nothing is
learned, weighted or reduced. Standardising happens only inside the readouts.

### 4. Pooling to beats

`perBeat` is the plain mean of the step vectors whose centres fall inside each
beat. It is stored next to `steps` in the sidecar.

### 5. Readouts: used only to check and to report

These are not part of the encoding. They only test what the encoding holds.

- **DEAM, valence and arousal at 2 Hz.** 1,744 clips of 45 s. A linear ridge
  maps one vector to a valence and arousal value.
- **Emotify, nine GEMS feelings.** 400 clips of 1 min, with the share of raters
  who felt each feeling. The vectors are averaged over the clip, then a ridge
  maps the average to the nine shares.
- **Nearest clips** (report only): cosine distance between a 10 s mean of the
  song and each library clip's mean.

Every readout is linear and memoryless: one vector in, one answer out.

### 6. Outputs

- `*.emotion.sidecar.json`: the input sidecar plus `emotionEncoding` (`steps`,
  `perBeat`, components, provenance). 62–77 MB per song.
- `emotion-report.html`: the predicted GEMS profile and the nearest Emotify and
  DEAM clips for every 10 s of each song.

## Timescales in the system today

| Scale | Where it appears |
|---|---|
| 50 ms | baseline frames (20 Hz); MERT runs at 13 ms (75 Hz) |
| 2 s | Essentia patches; the check-1 grid |
| 4 s | the window: **the only scale the encoding itself carries** |
| beat (about 0.5 s) | `perBeat` mean |
| 10 s | report rows |
| 45–60 s | library labels as used by Emotify (clip mean) and by DEAM (between-clip variation) |
| phrase, section, song, repeated listening | **nothing** |

## What it does not do

- **Nothing is recurrent.** No step knows the steps before it. Each vector is
  computed from its own window, apart from MERT's attention context above.
  Swapping two windows in time would change nothing except MERT's inputs and
  the onset-density threshold, which is one value per song (75th percentile of
  its flux).
- **No memory across the song.** There is no state that builds, decays or
  compares the present with what came earlier. B's expectation signals were not
  computed.
- **No slow levels.** Phrase, section and song vectors exist only by averaging
  after the fact, as the report does over 10 s.
- **No structure learned for this purpose.** Every model is frozen. Only the
  linear readouts are fitted, and only for checking.

## What check 1 does and does not show

- It shows the vector holds **a clip's overall mood**. The pick beats the
  baseline when predicting DEAM between clips (R² 0.62 against 0.45) and
  Emotify feeling profiles (rank correlation 0.62 against 0.52; nearest-neighbour
  agreement 0.32 against 0.22).
- It barely tests **change inside a song**. In DEAM only about 2.5 % of the
  label variance lies inside a clip: within-clip spread is 0.04, between-clip
  spread is 0.24–0.28.
- A readout trained on within-clip change finds a little arousal: correlation
  0.25 for the pick, 0.23 for the baseline. Valence gets 0.11.

## The user's reading of the report (2026-10-13)

- **Presence 2:00–3:15: right.** The report's "sadness" at 2:00–3:10 matches
  the user's long-held feeling of that part as sad and reminiscing, until about
  3:15. The 3:10 edge is the 10 s rows, not a real boundary.
- **Five Years opening: wrong.** The opening is much less sad than what
  follows, and not high energy. The report reads 0:00 as the most aroused
  moment of the song (0.61, against 0.41–0.45 at the climax). Lone drums seem
  to read as excitement.
