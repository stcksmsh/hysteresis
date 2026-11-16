# T1b facts for the reviewers (WO41 step 5; BRAIN_SPEC 7.66.2 a-d, 7.67.2, 7.67.3)

Lookups and checks only; nothing here changes E1. Code `scripts/body/t1b_facts.py`; raw numbers `/secondary/hyst-data/body/t1b/facts_{genres,sync,forms}.json`.

## a) The 44 ear features (`scripts/brain/fast_features.py`)

One STFT of the mono mix at 44.1 kHz: Hann window 2048 (46.4 ms), hop 441 (100 Hz), centred (reflect padding); P = |X|^2; dB(x) = 10 log10(x + 1e-8).
- cols 0-31 log-mel: 32 Slaney mel bands (30-16000 Hz) of P, in dB.
- cols 32-39 flux: for each of 8 frequency groups (edges 30, 200, 400, 800, 1600, 3200, 6400, 12800, 16000 Hz), the mean over the group's bins of the half-wave rectified one-frame rise of dB(P) (col 32 = the 30-200 Hz kick proxy).
- col 40 onset strength: mean over the 32 log-mel bands of the half-wave rectified one-frame rise (librosa definition, lag 1, no smoothing).
- col 41 RMS of the 2048-sample frame (linear amplitude). col 42 spectral centroid of |X| in units of Nyquist. col 43 spectral flatness of P (geometric / arithmetic mean).
- First frame: every rise is 0.
- Normalisation: **global, not per song**: `braindump.stats()` mean and sd from the B3 training corpus, then clip (cortex input clip 10). FineDance statistics are not used. All lookahead 23.2 ms (`T1B_CAUSAL.md`).

## b) FineDance audio and motion alignment

- How T0 aligned them: audio offset 0, music time 0 = motion frame 0, motion 30 fps; no trimming, no manual alignment, no per-song offset (T0_RULES section 4). FineDance ships `music_wav` and `motion` with no timestamps or offsets beyond that (`label_json` has name, style1, style2, frames).
- Checked here (203 sequences):
  - **Duration**: audio length minus motion length (frames / 30). Median 0.0 s. Audio shorter than motion by more than 0.5 s: 5 sequences (fd_036 -0.5, fd_043 **-20.0 s (validation)**, fd_041 -1.9, fd_050 -0.5, fd_059 **-18.0 s (train)**); longer by more than 0.5 s: 5. In the two big cases the last 18-20 s of motion have no audio.
    **E1 rule from this: tokens whose chunk starts after the audio's end are dropped from training and validation** (`Song.n` in `t1b_train.py`; rules note).
  - **Onset vs movement cross-correlation** (ear col 40 vs standardised V1 joint speed, both smoothed 0.1 s, 100 Hz, lag window +-0.25 s, first 60 s vs last 60 s of each sequence; sequences of 60-120 s use first and second half; 172 sequences long enough):
    median lag first part -0.02 s, last part -0.04 s (sd 0.17 s each; positive = movement after the music); median drift (last minus first) 0.00 s; |drift| > 0.1 s in 120 of 172 sequences, but the per-sequence peak correlation is only about 0.05, so a single sequence's lag is not resolved to better than about +-0.2 s.
    Reading: no systematic offset and no systematic drift between the first and last minute; per-sequence alignment better than 0.1 s is NOT confirmed by this check (the signal is too weak). A stronger check needs beat-synchronous statistics or a manual look; not done.
  - Training and evaluation use identical preprocessing (the same T0 npz and the same cortex files for every split).

## c) Trainable parameter counts (E1, `Model.counts()`)

| part | single 256-entry posture head | residual 2 x 256 posture (if ruled) |
|---|---|---|
| cortex projection (Linear 2105 -> 128) | 269,568 | 269,568 |
| listener input U (128 -> 256) | 33,024 | 33,024 |
| listener recurrent W (256 x 256) + 256 time constants | 65,792 | 65,792 |
| planner embeddings (code 1, code 2, vigour, posture) | 74,240 | 82,432 |
| planner GRU 256 | 480,768 | 505,344 |
| attention (q, k, v, o) + LayerNorm | 263,680 | 263,680 |
| head code 1 (1024) | 263,168 | 263,168 |
| head code 2 given code 1 (1024) | 295,936 | 295,936 |
| head vigour (32) | 8,224 | 8,224 |
| head posture (256, [+ stage 2 given stage 1]) | 65,792 | 139,776 |
| **total** | **1,820,192** | **1,926,944** |

Listener 368,384 (0.37 M) with the projection, planner 1.45 M / 1.56 M. The frozen cortex (B7) and vocabulary (run B) are not counted.

## d) FineDance genres and dancers per split

- Sequences (T0 split, grouped by song): train 154, validation 26, test 23 (203). Groups: train 133, validation 20, test 19 (172 groups; 31 groups have two sequences = a song danced twice).
- Dancer identity is NOT recorded (`label_json` has no dancer field); one sequence is one performance.
- style1 (genre) by split: train Street 60, Mix 36, Classic 36, Folk 22; validation Street 8, Classic 7, Mix 5, Folk 4, "jiewu" 2; test Street 12, Classic 5, Mix 4, Folk 2. Train sequences per genre are the numbers 7.63.5 asks for.
- style2 (sub-style) train: ShenYun 28, Korean 26, Popping 16, Jazz 14, Hiphop 14, Breaking 10, Dai 9, Miao 7, HanTang 6, Wei 6, Choreography 6, Chinese 4, Urban 4, Locking 2, DunHuang 2; validation and test in `facts_genres.json`. Note: "jazz" (lower case, 2 validation) and "jiewu" appear only in validation.

## 7.67.3 The two feature forms (report)

- Global form (what E1 uses): corpus mean and sd, same for every song.
- Within-song relative form: z-score against a causal trailing 30 s window (mean and sd over the last 30 s of that song).
- Between-song variance share (train sequences, share of each feature's variance that is song-to-song, carried by the global form and removed by the relative form): log-mel 0.34 on average (0.16 in the lowest bands up to 0.71 in the highest), flux 0.02, onset 0.02, **RMS 0.42, centroid 0.35**, flatness 0.02.
- Correlation of the two forms inside songs (mean over every 4th train song, after the first 30 s): log-mel 0.93, flux 0.99, onset 0.99, RMS 0.92, centroid 0.94, flatness 0.88.
- Reading: flux, onset and flatness are already song-relative; loudness (RMS), brightness (centroid) and the upper log-mel bands carry large between-song differences, so the two forms differ mostly in those. The relative form would be a variant, not E1.
