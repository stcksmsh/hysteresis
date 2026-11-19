# Ear energy: one acoustic-energy scalar from the ear features (WO30A, BRAIN_SPEC 7.47.3 and 7.47.6)

Fixed before any dial value is read or any correlation is computed. Code: `scripts/body/ear_energy.py`. Not to be changed afterwards.

**Input:** the 44-feature array of `scripts/brain/fast_features.py`, shape (frames, 44), 100 Hz, frame t centred on t / 100 s. Only column 40
(`onset`) and column 41 (`rms`) are used.

**1. Loudness term** (per 100 Hz frame): `L = 20 log10(max(rms, 1e-4))` (floor -80 dB), then a 1 s moving mean (101 frames, centred,
edges padded with the nearest value).

**2. Onset-density term** (per 100 Hz frame):
- a peak is a frame whose `onset` is the maximum of the +-5 frames around it (first one on ties) and is >= 1.0;
- `D` = number of peaks inside the 2 s window centred on the frame (201 frames, window clipped at the song ends) divided by 2 s, in peaks/s.
  The window is a plain sum of peak indicators, no weighting; the divisor is always 2 s.

**3. Combination:** `E100 = (z(L) + z(D)) / 2`, where `z(x) = (x - mean) / sd` with one mean and one sd per term, pooled over the 100 Hz
frames of the three danced songs (Instant Crush, Five Years, Presence). The six constants are in `scripts/body/ear_energy_norm.json`
(written once by `ear_energy.py norm`, never refitted).

**4. Output lane:** 10 Hz. Block i is the mean of `E100` over frames 10i .. 10i+9, stamped (i + 0.5) * 0.1 s, i < floor(frames / 10)
(the stamps `arousal_b7` uses in `motornet_music.music_input`). This is "ear energy" in every table.

**5. Network input:** `clip((E10 - mu) / sd, -3, 3)`, with `mu` and `sd` the mean and sd of the 10 Hz lane pooled over the three danced
songs (same constants file), as `arousal_b7` is standardised. Silent clips: 0.

**Silence:** rms = 0 gives L = -80 dB, no peaks, D = 0, so the raw lane sits at the floor, far below any song.
No tuning, no per-song fitting, no learning. Features come from the full mix.
