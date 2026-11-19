# Mismatch test round 2: rules (WO55 part B, BRAIN_SPEC 7.84 item 1, 7.86 Q3, 7.87) — written and pushed before any clip is made

Round 2 is the second and last round of this check. It repeats `docs/MISMATCH_RULES.md` (round 1) in full, with the same decision rule,
pair counts, presentation, level match, order balance, checks and key schema (so `scripts/body/mismatch_score.py` runs unchanged), and
changes only the items listed in section 0. Round 1's session `/secondary/hyst-data/body/mismatch/session_2026-11-19` and material stay
as they are.

Report and test tooling only. No change to A or B, nothing trained, no verdict from the builder. One arm. Defaults are marked
**(default)** and listed under FOR USER at the end. Builder code `scripts/body/mismatch2_build.py` (+ `test_mismatch2.py`); it reuses the
round-1 functions of `mismatch_build.py` and `mismatch_order.py` unchanged. Scorer `scripts/body/mismatch_score.py`, unchanged.
Out (material): `/secondary/hyst-data/body/retime/b/`. Session: `/secondary/hyst-data/body/mismatch2/session_<date>/`, built with
`dialstudy_session.py --clips <manifest> --out ... --seed 53201`. The session is not served by the builder.
Seed for everything the builder draws: **53201** **(default)**, one `random.Random(53201)` consumed in the order the sections below name.

## 0. What changes against round 1 (and nothing else)

1. **Re-timed movement (7.87 Q1).** L(V1) = 0.35 s, L(V2) = 0.28 s, one constant per variant (the shared helper
   `scripts/body/retime.py`, part A). Sign: positive L = the realised movement (`controls/q50`) is later than its music, so it is read
   L later. The joint CSV of every clip is cut from `window_offset + L(variant)` instead of `window_offset`: CSV row k (time k / 50 s)
   = q50 of the kept window at window time `window_offset + L + k / 50`, k = 0..500. q50 is 50 Hz, so L(V2) = 14 rows exactly; L(V1) =
   17.5 rows, and the CSV value is the linear interpolation of q50 between the two neighbouring rows **(default)** (the renderer
   interpolates the CSV linearly in time anyway). The music excerpt is unchanged: it starts at the movement's *unshifted* excerpt start
   `20 w + window_offset` in the song, so the movement now precedes its old position by L. Key field `retime_L_s` (and
   `movement_csv_start_s` = `window_offset + L`, window time).
2. **Excerpt inside the kept window including L.** The excerpt and its extra L must lie inside the kept 20 s window: `window_offset + L +
   10 <= 20`. On the 0.5 s offset grid of round 1 this removes offset 10.0 s; the drawn offset is restricted to 0.0-9.5 s **(default)**
   (no continuation into a neighbouring window, nothing padded).
3. **Arm only (7.87 Q3).** The hand-path look-ahead hint (1.5 s ahead, `ensemble.html` "A faint hint of the hand path") and the trail
   (4 s ribbon, "Hand path: a ribbon of light") are removed at render time by patching the page copy (`scripts/body/armonly_page.py`:
   the round-1 pillar patch of `retarget_page.py`, then both drawing loops set to zero iterations; every replacement must match exactly
   once). `crates/` is not edited. `retarget_render.sh` takes the page patch script from `RETARGET_PAGE` (default unchanged:
   `retarget_page.py`). Proof: one frame rendered with and without the patch, the canvas stroke calls of hint and trail counted (must be
   0 in the arm-only page, > 0 in the round-1 page) and the pixel difference recorded.
4. **Shifted pairs:** |offset| uniform in [4, 6] s on a 0.1 s grid (was 2-6), sign random, then the same fitting rule as round 1
   (inside the song and, where possible, inside the Q3 window; flag `foil_outside_q3`).
5. **Different-song foils from a different dataset (7.86 Q3):** a song within 5 % tempo is searched first among all songs of the
   *other* datasets (FineDance, PhantomDance, Motorica, AIOZ minus the movement's own; one seeded-shuffled pool) **(default)**; the same
   dataset only when no song of another dataset qualifies (key flag `foil_same_dataset: true`, listed in the report). Tempo, excerpt rule
   and "a foil song is used by at most one pair" as round 1.
6. **Fresh excerpts:** no song used in round 1 (`mismatch/material_key.json`, movement songs and foil songs alike) is used in round 2,
   neither as movement nor as foil **(default: stricter than the order, which names movement only)**. Expected overlap 0 songs; it is
   checked and reported per dataset.
7. **Instruction page:** the session opens with a plain-words instruction (manifest field `intro`, a new, smallest option of
   `dialstudy_session.py`: shown once before item 1 with a "start" button; absent `intro` = the tool behaves as before). The text,
   verbatim:

   > Each clip shows the SAME arm movement twice, with a short black pause between the two halves. Only the music differs. In some
   > clips the other music is the same song at a different moment, so both halves can sound alike; in others it is a different song.
   > Question: in which half does the music fit the movement better? "same" is a valid answer. Please answer after the first pass of
   > the clip, then give your confidence.

   It does not say which side is real or how many pairs of each kind there are.
8. **Repeats:** 5, as round 1 (at least 2 of each kind, order reversed).
9. **Seeds and paths:** builder 53201, session 53201; out folders as above.

## 1. Movement

- Retargeted human clips at the realised stage, lamp head (`--implement lamp`, the `retarget_render.sh` path: `ensemble_preview
  --joint-csv`, label text blanked, `record_ensemble.cjs`), 10 s each, **re-timed and arm-only (section 0 items 1-3)**. Source of motion:
  `controls/q50/<ds>/<key>.npz` (realised joints `q50`, 50 Hz) of the kept 20 s windows.
- Datasets: FineDance, PhantomDance, Motorica (not AIOZ). Version mix V1/V2 half each: 10 excerpts V1 and 10 V2, assigned by seed,
  balanced within each dataset as far as its count allows.
- **Excerpt rule (7.75 Q3):** song RMS (the music of the excerpt, mono, 10 s) at or above that song's own median RMS over its
  10 s-hop windows, and the excerpt lies inside [10 s, song_length - 10 s]. The music excerpt is a 10 s sub-window of one kept 20 s
  window (start offset 0-9.5 s inside it, drawn uniformly on a 0.5 s grid among the offsets that satisfy the rule).
- **20 distinct movement excerpts**, at most one per song, spread **7 FineDance / 7 PhantomDance / 6 Motorica**, none from a round-1
  song. Mirror copies (V1m, V2m) are not used. Candidate pool is every (dataset, song, window, version) that passes the rule and the
  retarget gates (`gate_again` of the stored realised window).
- Motorica stays local: only aggregates leave the laptop; the session folder stays on the laptop.

## 2. Pairs

Each pair is the same movement shown twice, once with its own music (**real**) and once with a **foil** music. Movement is identical
frame for frame in both halves.

- **(a) shifted:** the foil is the same song, the music excerpt shifted by |offset| uniform in [4, 6] s on a 0.1 s grid, sign random;
  fitting rule as round 1 (section 0 item 4).
- **(b) different song:** a different song whose librosa tempo is within 5 % of the real song's (`|T_foil / T_real - 1| <= 0.05`; tempo
  = 60 / median inter-beat interval of `beatv/librosa/<song>.json`, bpm); another dataset first (section 0 item 5). Its excerpt is
  chosen by the Q3 rule, start drawn by seed. A foil song is used by at most one pair. If no song is within 5 % the movement excerpt is
  redrawn.
- **10 pairs of each kind**, balanced 10 / 10 overall and 3-4 of each kind per dataset.

## 3. Presentation

One clip per pair, 21.5 s exactly: 0.0-10.0 s version 1 (movement + its music), 10.0-11.5 s black and digital silence, 11.5-21.5 s
version 2 (the same movement + the other music). 30 fps, 645 frames; audio 44,100 Hz, 948,150 samples, halves at sample 0 and 507,150.
Real side balanced 10 / 10 overall and 5 / 5 per kind. RMS match of the two music halves to their mean, pure gain, peak below 0.99,
achieved ratio 1.00 +- 0.01. Questions: **"Which fits the music better?"** (`first`, `second`, `same`) and **"Confidence?"** (`low`,
`medium`, `high`), answered together. The instruction text of section 0 item 7 opens the session.

## 4. Repeats

5 hidden repeats (25 % of 20), order reversed, at least 2 shifted and at least 2 different-song, no pair repeated twice, marked in the
key only.

## 5. Decision rule (copied verbatim from 7.84 item 1) and how it is computed

> Decision rule stated in advance: Kosta picks the real pairing in >= 70 % of non-tie answers AND above his repeat-flip rate -> data carry
> visible fit; otherwise timing/fit is treated as teacher- and planner-shaped, and data-learned timing is deprioritised.
> Report separately for shifted vs different-song pairs.

Computed exactly as `docs/MISMATCH_RULES.md` section 5 (the scorer is unchanged): real-pick share `p` over the 20 first presentations
(ties dropped), repeat-flip rate `f` over the 5 repeats; rule met if `p >= 0.70` AND the one-sided 95 % Clopper-Pearson lower bound of
`p` is `> 0.5 + f / 2`; per kind and per confidence reported, no verdict beyond "rule met / not met".

## 6. Checks on the built material

All clip and order checks of `docs/MISMATCH_RULES.md` section 6 (duration, gap black and silent, real half sample-exact and AAC lag 0,
RMS ratio, peak, frame-identical halves, limits, balance, position, code parity, sizes within 2 %, no metadata leaks), plus:
- **retime check**, every clip: from the key and the clip's joint CSV, CSV row 0 equals q50 at window time `window_offset + L` (linear
  interpolation for a half row), and every CSV row k equals q50 at `window_offset + L + k / 50`, max error 1e-3 deg; `retime_L_s` equals
  L(variant);
- **arm-only check**: every rendered page has the hint and trail loops disabled (string check on each page) and the one-frame
  draw-call / pixel proof of section 0 item 3;
- **overlap with round 1**: songs shared with round 1 (movement and foil), per dataset, must be 0;
- 3 clips spot-checked by eye from frames and waveforms.

## 7. Files and exact schemas

As `docs/MISMATCH_RULES.md` section 7 with `mismatch/` replaced by `retime/b/` for the material and `mismatch2/session_<date>/` for the
session. The manifest object adds one top-level field `intro` (the text of section 0 item 7). The material key's `seed` is 53201 and each
item adds `retime_L_s`, `movement_csv_start_s`, `window_offset_s`, `q_index`, `foil_same_dataset`; every round-1 field is kept with the
same meaning, so `mismatch_score.py` runs unchanged.

## 8. Scorer

`scripts/body/mismatch_score.py SESSION_DIR`, unchanged. Tested on synthetic answers for this session's key in a temporary copy of the
key folder (all real -> "met", random -> "not met"); the session's own `answers.csv` is never opened.

## FOR USER (defaults taken)

1. L(V1) = 0.35 s is 17.5 q50 rows: the CSV is the linear interpolation of q50 at the half row (V2's 0.28 s is 14 rows, exact).
2. Window offsets restricted to 0.0-9.5 s so that offset + L + 10 s fits the kept window; no continuation into a neighbouring window.
3. Different-song foils: one shuffled pool of all other datasets (FineDance, PhantomDance, Motorica, AIOZ) first, same dataset only
   when none qualifies.
4. Fresh songs: round-1 movement and foil songs are both excluded, for movement and for foils.
5. Instruction: new manifest field `intro` in `dialstudy_session.py`, shown once before item 1 (text above).
6. Builder seed 53201 (the same number as the session seed the order gives).
