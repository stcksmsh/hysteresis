# Mismatch test: rules (WO53 part A, BRAIN_SPEC 7.84 item 1, 7.85) — written and pushed before any clip is made

Report and test tooling only. No change to A or B, nothing trained, no verdict from the builder. One arm. Defaults are marked
**(default)** and listed under FOR USER at the end. Builder code `scripts/body/mismatch_build.py` (+ tests); scorer
`scripts/body/mismatch_score.py` (written by agent 2 against sections 7 and 8 here). Out: `/secondary/hyst-data/body/mismatch/`.
Seed for everything the builder draws: **53101** **(default)**, one `random.Random(53101)` consumed in the order the sections below
name (excerpts, versions, kinds, foils, offsets, orders, repeats). Re-running with the same inputs gives the same key.

## 1. Movement

- Retargeted human clips at the realised stage, lamp head (`--implement lamp`, the `retarget_render.sh` path: `ensemble_preview
  --joint-csv`, label text blanked, `record_ensemble.cjs`), 10 s each. Source of motion: `controls/q50/<ds>/<key>.npz` (realised joints
  `q50`, 50 Hz) of the kept 20 s windows.
- Datasets: FineDance, PhantomDance, Motorica (not AIOZ). Version mix V1/V2 half each: 10 excerpts V1 and 10 V2, assigned by seed,
  balanced within each dataset as far as its count allows (7/7/6 gives V1 counts 4/3/3 or 3/4/3, drawn by seed).
- **Excerpt rule (7.75 Q3):** song RMS (the music of the excerpt, mono, 10 s) at or above that song's own median RMS over its
  10 s-hop windows, and the excerpt lies inside [10 s, song_length - 10 s]. The excerpt is a 10 s sub-window of one kept 20 s window
  (start offset 0-10 s inside it, drawn uniformly on a 0.5 s grid among the offsets that satisfy the rule).
- **20 distinct movement excerpts**, at most one per song, spread **7 FineDance / 7 PhantomDance / 6 Motorica** **(default)**. Mirror
  copies (V1m, V2m) are not used. Candidate pool is every (dataset, song, window, version) that passes the rule and the retarget gates
  (`gates.passed` of the realised clip: no joint limit or speed breach). The 20 are drawn by seed, one song per draw, no repeats of a song.
- Motorica stays local: only aggregates leave the laptop; the session folder stays on the laptop.

## 2. Pairs

Each pair is the same movement shown twice, once with its own music (**real**) and once with a **foil** music. Movement is identical
frame for frame in both halves.

- **(a) shifted:** the foil is the same song, the music excerpt shifted by a random offset of 2-6 s: |offset| uniform in [2, 6] s on a
  0.1 s grid, sign random (seed), so the foil music is the song at [t0 + offset, t0 + offset + 10). It must lie inside the song and, where
  possible, inside the Q3 window ([10 s, len - 10 s]); if the drawn sign does not fit it is flipped; if neither fits inside the Q3 window
  but one fits inside the song, that one is used and the pair is flagged `foil_outside_q3` in the key; if neither fits the song, the
  excerpt is redrawn.
- **(b) different song:** a different song whose librosa tempo is within 5 % of the real song's (`|T_foil / T_real - 1| <= 0.05`; tempo
  = 60 / median inter-beat interval of `beatv/librosa/<song>.json` over the whole song, bpm). Any dataset is allowed; **default: same
  dataset first**, other datasets only when the same dataset has no candidate. Its excerpt is chosen by the same Q3 rule (10 s sub-window
  with RMS at or above that song's median, not in the first or last 10 s), start drawn by seed. A foil song is used by at most one pair.
  If no song is within 5 % the movement excerpt is redrawn.
- **10 pairs of each kind**, kind assigned by seed, balanced to 10 / 10 overall and, **(default)**, 3-4 of each kind per dataset.

## 3. Presentation

`dialstudy_session.py` shows one clip per item, so each pair is ONE clip, 21.5 s exactly **(default, FOR USER)**:

| time (s) | content |
|---|---|
| 0.0 - 10.0 | version 1: movement + its music |
| 10.0 - 11.5 | 1.5 s black frames, digital silence |
| 11.5 - 21.5 | version 2: the same movement + the other music |

- Video 30 fps **(default, as the recorder produces)**; duration 21.5 s means 645 frames; audio 44,100 Hz mono/stereo as the source
  music, 948,150 samples; each half's audio starts at sample 0 and sample 507,150 (= 11.5 s x 44,100) of the clip.
- **Order:** real first or second randomised per pair and balanced 10 first / 10 second overall, 5 / 5 within each kind (seed), with
  the unbalanced remainder none (20 is even in both kinds). Repeats are not counted in the balance of the 20; the 5 repeats are
  balanced 2-3 / 3-2 by their own draw (their order is the reverse of their original, so they are 5 items with the opposite side).
- **Levels:** RMS match of the music: both halves are scaled so that their music RMS over the 10 s equals the mean of the two raw RMS
  values (a pure gain, no limiter; peaks must stay below 0.99 full scale or the gain is lowered for both halves of that pair).
  The achieved RMS ratio between halves must be 1.00 +- 0.01 (checked, section 6).
- Questions per item (`questions` option of the manifest): **"Which fits the music better?"** with labels `first`, `second`, `same`;
  **"Confidence?"** with labels `low`, `medium`, `high`. Both answered together before sending.

## 4. Repeats

5 hidden repeats of pairs (25 % of 20): a repeated pair is the same two halves with the **order reversed** (the real half now plays
where the foil played). Drawn by seed, **at least 2 shifted and at least 2 different-song**, no pair repeated twice. Marked in the key
only (never in the clip, file or item order metadata). Repeat items are placed anywhere in the shuffled order by the session tool.

## 5. Decision rule (copied verbatim from 7.84 item 1) and how it is computed

> Decision rule stated in advance: Kosta picks the real pairing in >= 70 % of non-tie answers AND above his repeat-flip rate -> data carry
> visible fit; otherwise timing/fit is treated as teacher- and planner-shaped, and data-learned timing is deprioritised.
> Report separately for shifted vs different-song pairs.

Computation (the scorer implements exactly this):
- **Presented choice** per item: `real` if the first answer part equals the key's `real_side`; `foil` if it is the other side; `tie`
  if it is `same`.
- **First presentations** = the 20 non-repeat items. **Real-pick share** `p = real / (real + foil)` over first presentations (ties
  dropped from numerator and denominator; the tie count is reported).
- **Repeat-flip rate** `f` = share of the 5 repeat pairs whose presented choice (real / foil / tie) differs between the original item
  and its repeat. The repeat is not used in `p`.
- **Rule met** if both hold:
  1. `p >= 0.70`;
  2. the one-sided 95 % binomial lower bound of `p` (Clopper-Pearson, n = non-tie first presentations) is `> 0.5 + f / 2`.
  The second form is also reported: `p > 0.5 + f / 2` (point estimate). The stated outcome is the conjunction of 1 and 2 (the lower-bound
  form); the point-estimate form is shown beside it, not used.
- Reported for all pairs and separately for shifted and different-song pairs (shares with Clopper-Pearson two-sided 95 % intervals, plus
  the same rule check per kind marked "exploratory", n is about 10), and split by confidence (low / medium / high: n and real-pick share
  per level). No verdict beyond "rule met / not met".

## 6. Checks on the built material

Clip checks, by numbers, every one of the 25 clips:
- duration exactly 21.5 s (645 frames, 948,150 audio samples, container duration within 1 frame);
- the 1.5 s gap is black and digital silence (max abs sample 0 in samples [441,000, 507,150), frame mean luminance below 2/255);
- each half's audio starts at the stated sample; the real half's music equals the movement's own music for the excerpt **sample for
  sample**: compared on the pre-encode WAV the builder muxes (gain divided out, max abs difference below 1/32768); the muxed AAC is
  checked by cross-correlation of each half against the source excerpt: peak at lag 0 samples, correlation above 0.99;
- the movement is identical in both halves (frame hashes of the video of half 1 and half 2 equal at 30 fps for the stage pixels;
  the music-dependent pillar page may differ: it is recorded with the same page for both halves, so the frames are expected equal, and
  any difference is reported by count);
- no limit is breached: the realised `gates.passed` of the movement and the rig limits of the `--joint-csv` run (joint, speed,
  acceleration as `ensemble_preview` reports them).
- 3 clips spot-checked by eye from extracted frames and audio waveforms (frames at 0, 5, 10, 11.5, 12, 21 s; waveforms of both halves).

Order checks (written to `order_checks.json`, all must hold or be reported as failing):
- real side balanced 10 / 10 in the 20 first presentations, 5 / 5 per kind; repeats' sides as stated in section 3;
- real side not predictable from item position: the session order is the seeded shuffle of the session tool; report the correlation of
  `real_side == first` with position index (Spearman, |rho| below 0.4) and the run lengths of the sides;
- not predictable from file name: clip files are `c<4 hex>.mp4` code names, the code is unrelated to the side (chi-square or sign test
  of code parity vs side reported); the manifest file names use only the pair id, not the side or kind;
- sizes: for every pair the encoded size of half 1 and half 2 (encoded separately with the same settings, as the builder does before
  concatenation) differ by at most 2 %; the whole-clip sizes are reported next to the kind and side;
- no clip name, container tag or metadata (`ffprobe` format and stream tags) contains the side, the kind, the foil or the song; the
  builder strips metadata (`-map_metadata -1`) and this is verified.

## 7. Files and exact schemas (agent 2 codes the scorer against these)

All under `/secondary/hyst-data/body/mismatch/`. The session folder is `session_<date>/` (date of the build, `YYYY-MM-DD`).

### 7.1 Manifest (input to `dialstudy_session.py --clips`)

`mismatch/manifest.json`: `{"clips": [ item, ... ]}`, 25 items, each
`{"id": "P07", "file": "clips_src/P07.mp4", "kind": "single", "questions": [{"q": "Which fits the music better?", "labels": ["first","second","same"]}, {"q": "Confidence?", "labels": ["low","medium","high"]}]}`.
`id` is the pair id (`P01`..`P20`) or the repeat id (`R01`..`R05`). Nothing else in the manifest.

### 7.2 Session (built by `dialstudy_session.py`, unchanged tool except the use of `questions`)

- `session_<date>/key/key.json` = `{"seed": 53101, "key": {"<code>": {"id": "P07", ...}}}` (the tool's own key; only `id` is used by
  the scorer). `<code>` = `c` + 4 hex characters, the name of the clip file in `clips/`.
- `session_<date>/order.json`: items in presentation order (the tool's own file, no key information).
- `session_<date>/answers.csv`, **no header**, one row per answer: `code,answer,note,timestamp,replays`.
  - `answer` is the two answers joined by `|`: `"<which>|<confidence>"`, `<which>` in `first`, `second`, `same`; `<confidence>` in `low`,
    `medium`, `high`. Examples: `first|high`, `same|low`.
  - `note` free text (may contain commas, quoted by the csv writer), `timestamp` `YYYY-MM-DDTHH:MM:SS`, `replays` an integer.
  - A code answered twice cannot happen (the server refuses); if it did, the last row wins.
- Both halves are in one clip, so "first" is the half at 0-10 s and "second" the half at 11.5-21.5 s.

### 7.3 Material key `mismatch/material_key.json` (also copied to `session_<date>/key/material_key.json`)

```
{
  "version": 1,
  "seed": 53101,
  "rule": {"threshold": 0.70, "flip_form": "lower95 > 0.5 + f/2"},
  "items": {
    "P07": {
      "id": "P07",                         // pair id; equals the manifest id and key.json "id"
      "repeat": false,                     // true for R01..R05
      "repeat_of": null,                   // "P07" for a repeat item, else null
      "kind": "shifted" | "different_song",
      "real_side": "first" | "second",     // which half of the clip carries the real music
      "dataset": "finedance" | "phantomdance" | "motorica",
      "version": "V1" | "V2",
      "song": "<music key of the movement's song>",
      "window": <int>,                     // 20 s window index in the dataset file
      "excerpt_start_s": <float>,          // movement excerpt start in the song, seconds
      "excerpt_end_s": <float>,            // = start + 10
      "foil": {
        "song": "<music key>",
        "dataset": "...",
        "offset_s": <signed float> | null, // shifted: music start minus real start; different_song: null
        "excerpt_start_s": <float>,
        "tempo_bpm_real": <float>, "tempo_bpm_foil": <float>,  // different_song only, else null
        "tempo_ratio": <float> | null      // foil / real, within [0.95, 1.05]
      },
      "foil_outside_q3": false,
      "rms_real": <float>, "rms_foil": <float>, "gain_real": <float>, "gain_foil": <float>
    },
    "R03": { ... same fields, "repeat": true, "repeat_of": "P12", "real_side" the opposite of P12's, rest equal to P12's ... }
  }
}
```

JSON has no comments; the `//` lines above are explanations only. Every item has every field. The scorer joins
`answers.csv` (code) -> `key/key.json` (`id`) -> `key/material_key.json` (`items[id]`).

### 7.4 Other build outputs

`clips_src/<id>.mp4` (21.5 s clips, 25), `clip_checks.json` (per clip, per check, pass/fail with numbers), `order_checks.json`,
`mismatch_build_report.md` (short). `mismatch_result.json` and `mismatch_result.md` are written later by the scorer.

## 8. Scorer output `mismatch_result.json` (for agent 2; the session folder is the argument)

`scripts/body/mismatch_score.py SESSION_DIR` reads `SESSION_DIR/answers.csv`, `SESSION_DIR/key/key.json`,
`SESSION_DIR/key/material_key.json`, and writes `SESSION_DIR/mismatch_result.json` and a short table (stdout and
`mismatch_result.md`). Required keys of the JSON: `rule_met` (bool), `real_pick_share`, `n_non_tie`, `ci95`, `lower95_one_sided`,
`flip_rate`, `ties`, `by_kind` (`shifted`, `different_song`, each with the same share fields), `by_confidence` (`low`, `medium`,
`high`), `answered` (how many of the 25 items had an answer). A session with unanswered items scores what is answered and says
`complete: false`.

## FOR USER (defaults taken)

1. One clip per pair, 21.5 s (10 s, 1.5 s black and silent gap, 10 s), because the session tool shows one clip per item.
2. Excerpt split 7 / 7 / 6 over FineDance / PhantomDance / Motorica; V1 / V2 half each, balanced per dataset.
3. Foil of "different song": same dataset first, any dataset when none exists; tempo = librosa median interval over the whole song.
4. Level match = RMS match of the two music halves to their mean, pure gain, peak below 0.99.
5. Rule met = share >= 0.70 AND the one-sided 95 % Clopper-Pearson lower bound > 0.5 + f / 2 (point-estimate form reported beside it).
6. Repeats: 5 pairs (25 %), at least 2 of each kind, order reversed, in the same session.
7. Video 30 fps; seed 53101.
