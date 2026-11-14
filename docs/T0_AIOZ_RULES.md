# T0 AIOZ validity check: rules and FineDance reference (WO37 Builder B, 2026-11-14)

Binding: BRAIN_SPEC 7.56.10 and 7.59.2.4. Written and pushed BEFORE any AIOZ measure is computed. Code: `scripts/body/t0_aioz.py`, tests `scripts/body/test_t0_aioz.py`.
Reference file: `/secondary/hyst-data/body/t0/aioz_ref.json` (203 FineDance sequences, 30 fps, whole sequence each).

## Method
- AIOZ `.pkl`: restricted unpickler only (numpy ndarray/dtype/_reconstruct; anything else raises). Opcode scan of one file (no execution) showed only those globals.
- Adapter: first 22 of 24 SMPL axis-angle joints -> rotation matrices -> the retarget code's (T, 315) array (6D = first two rows). FK uses the same canonical skeleton as `v3_lib.fk`.
- Frame rate per sequence = frames / wav seconds; mode = most common value rounded to 0.1; a sequence more than 2 % off the mode is dropped ("fps"). Each person is a sequence.
- Measures per person, before any low-pass: (1) power share above 3 Hz (`v3_lib.pos_measures` p_gt3, Step A) of right wrist relative to right shoulder and of head relative to pelvis;
  (2) share of frames where any live joint's angular speed (angle of R_t^T R_t+1 x fps) exceeds FineDance's p99.9 for that joint; (3) share of frames with root speed above FineDance's p99.9;
  (4) share of frames with every joint below 1 deg/s. Also mean head height and its vertical drift (report only).
- Prune (spec): drop if (1) exceeds FineDance p95 for either end point, or (2) or (3) exceeds 1 %, or (4) exceeds 20 %.

## FineDance reference
| quantity | value |
|---|---|
| p95 of end-point power above 3 Hz, wrist | 0.1489 (median 0.0553) |
| p95 of end-point power above 3 Hz, head | 0.1800 (median 0.0609) |
| root speed p99.9 | 1.772 m/s |
| per-joint angular speed p99.9 (deg/s), 22 joints | in `aioz_ref.json` (`joint_ang_p999`) |
| FineDance frozen share (4): median / max | 0.035 % / 7.3 % |

## Two deviations from the literal spec, FOR USER (both fixed before any AIOZ number was seen)
1. **Dead joints.** The feet (joints 10, 11) have p99.9 = 0 deg/s in FineDance (identity rotations); any AIOZ motion there would exceed a zero threshold. Measure (2) uses the 20 live joints
   (p99.9 >= 1 deg/s); joints 10 and 11 are excluded.
2. **The literal 1 % threshold of (2) is mis-calibrated.** Taking the union over 20 joints each at its own p99.9, the median FineDance sequence already has 1.36 % of frames over; the literal rule
   would prune **58 %** of FineDance itself (60 % under all four rules; rule (1) alone prunes about 5-10 % by construction). So the binding result `aioz_keep.json` applies the literal rule (spec),
   and the check also writes a **calibrated variant** `aioz_keep_calibrated.json` where (2) and (3) use max(1 %, FineDance p95 of the same share): (2) 5.78 %, (3) 0.43 % -> threshold 5.78 % and 1 %.
   The 30 % stop rule is reported for both. Which rule the overseer wants for the full AIOZ run is a decision for the overseer / Kosta; this builder does not choose.
