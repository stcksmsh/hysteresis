# AIST++ BAS cross-check rules (BRAIN_SPEC 7.78 section 1.1) — written before any result

Report only, no verdict, no comparison with a published number (the overseer fetches it). Code `scripts/body/aist_bas.py` (reuses `beatv_lib.py` of WO47 V2 unchanged), loader `scripts/body/aist_load.py`.

## Data
- Motion: AIST++ `keypoints3d` (COCO 17 joints, 60 fps), `/secondary/hyst-data/datasets/aist/data/keypoints3d/*.pkl`, 1,408 sequences. Each pkl holds `keypoints3d` and `keypoints3d_optim`.
  **Main: `keypoints3d_optim`** (the smoothed ground-truth keypoints; the AIST++/FACT ground-truth side). Variant: raw `keypoints3d`.
- Music: AIST Dance DB audio extracted from the c01 video of one sequence per music ID (60 IDs), mono 22,050 Hz (the sample rate of the V2 librosa beats). One file per music ID, music starting at motion t = 0, valid only if the 5-pair alignment check gives every lag under 10 ms (see `docs/AIST_BAS_REPORT.md`).
- Ignore list: `ignore_list.txt` of the AIST++ v1.0 release (46 poorly reconstructed sequences, small file from the release assets) is applied: those sequences are dropped.
- Sequence sets: (a) **full** = all sequences not on the ignore list; (b) **test** = the AIST++ `crossmodal_test` split (19 sequences, the music-to-dance test set used by Bailando/EDGE-style evaluation), ignore list applied; also reported: `pose_test` (469 sequences). Split files from the release asset `splits.zip` (small).
- `.pkl` files are untrusted: restricted `Unpickler` allowing only numpy array reconstruction globals; anything else raises.

## Procedure (identical to WO47 V2, `docs/BEATV_RULES.md` section 1)
- Kinematic speed = mean over the 17 joints of the 3-D position speed (distance between consecutive frames x fps), Gaussian smoothing (sigma 5 frames at 30 fps, scaled to time: 10 frames at 60 fps), kinematic beats = local minima (`scipy.signal.argrelextrema(np.less)`), as `beatv_lib.kin_beats`.
- Music beats: `librosa.beat.beat_track` on onset strength (sr 22,050, hop 441, defaults), as `beatv_raw.librosa_beats`. Computed once per music ID.
- BAS: `beatv_lib.bas`, sigma 0.1 s, **music-beat sum is the main variant**, kinematic-beat sum next to it. Duration = motion length / 60 (music beats after it are dropped).
- Chance level: `beatv_lib.bas_chance`: the same BAS with the music beats shifted by a uniform offset in [0.25, 1] x the median beat interval (wrapping inside the duration), 20 draws per sequence, seed 47102 + sequence index.
- Paired interval: per-sequence difference BAS - chance; set value = mean over sequences; 95 % percentile bootstrap, 2,000 resamples, seed 47101 (`beatv_report.boot`). Because many sequences share one music ID, the bootstrap is also run **by music ID** (sequences of one music ID resampled together); both are reported, the by-music-ID interval is the more conservative.
- Variant (evaluation-code frame constants): smoothing sigma 5 frames and BAS sigma 3 frames at 60 fps (0.05 s), the literal frame constants, in case the Bailando/FACT code applies them at 60 fps. Reported next to the main.

## Outputs
Per-sequence values `/secondary/hyst-data/datasets/aist/bas/per_sequence.csv` (not redistributed; derived values only); report `docs/AIST_BAS_REPORT.md`.
