# Second pulse flash check: rules (BRAIN_SPEC 7.79 pulse Q1 (d)), written before any material

Material only; nothing is served. Builder script: `scripts/body/pulse_flash2.py` (reuses `beatv_clicks_visual.render`, the same rendering and the
same two questions as `pulse_flash.py`).

## Songs

- Pool: every song in `pulse/songs/<key>.json` whose whole-song `whole.level_vs_lib.nearest` is "2/3" or "3/2".
- Excluded: songs under 12 s (Q4); the 10 songs of the first flash check (`pulse/flash/key.json`); songs shorter than 50 s (a 30 s excerpt
  with 10 s margin at both ends needs 50 s; this removes only short aioz clips, and is a consequence of the excerpt rule below); songs with no
  librosa beats file or no decodable wav.
- Stratified: 4 songs at 2/3 and 4 at 3/2, one per dataset (finedance, aioz, phantom, motorica) in each level. Motorica is allowed (Kosta views
  locally; the items are marked `local_only`). Within a dataset and level the song is the first of the pool (sorted by key) after a shuffle with
  `random.Random(49301)`, drawn level 2/3 first, then 3/2, datasets in the order finedance, aioz, phantom, motorica.
- Plus the 2 songs that failed in the first check: aioz_8JQ0zHmZBIg_05_0_1950 and aioz_SZhU9XTCUiM_13_0_1950. Total 10 songs, 20 items
  (each song: one item with flashes at the pulse events, one at librosa's beats).

Amendment (found at the first run): a drawn song with no admissible excerpt under the rules below (ph_187, 55 s, its only window below the
song's median RMS) is skipped and the next song of the same shuffled pool is drawn; skips are printed in the log.

## Excerpts (30 s)

Candidate starts on a 1 s grid, from 10 s up to duration - 40 s (so the excerpt is not in the first or last 10 s). A candidate is kept when:
1. the window RMS (median of `rms` in the `.npz`, 100 Hz) is at least the median RMS of the whole song;
2. the window holds at least 8 pulse events and 8 librosa beats;
3. the window's nearest simple ratio (`pulse_run.level`, tempo from `series_stats` of events in the window against librosa's) equals the song's
   whole-song nearest level.
The chosen start is the kept candidate whose window ratio is closest to the whole-song ratio (absolute log ratio of the two), the earliest on a tie.
If no candidate passes rule 3, rule 3 is dropped and the closest ratio still decides (reported in the material note).
For the 2 failures the start must also differ from the first check's start (24 s for aioz_8JQ0, 10 s for aioz_SZhU) by at least 10 s. Amendment (found at the
second run): both songs are 65 s long, so with the 10 s margins the only admissible starts are 10-25 s; a 30 s non-overlap with the first excerpt is
impossible, and the new excerpt overlaps the first by 16-20 s. Reported in the material note.

## Rendering and order

As the first check: white disc, intensity 1 at the first frame at or after the event, 120 ms fade, music without clicks, 640x360, 60 fps, 30 s,
audio included. Two questions per item ("Is the flash on the beat?" yes / partly / no; "Is it the right speed?" right / too fast / too slow).
Item ids Q00..Q19 in a seeded random order (seed 49302); `key.json` keeps which item is which. Session built with seed 49303.
