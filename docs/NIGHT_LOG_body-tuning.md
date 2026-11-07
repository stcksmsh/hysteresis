# Night log: body-tuning (work order 6, one-arm tuning loop + self-surprisal lane), 2026-11-05

## MORNING SUMMARY

Branch `body-tuning` (from `origin/body`). One arm only; no ensemble work. No claims; mechanism names only.

- **Phase 1, the loop.** `scripts/author/retune.sh SONG MAPPING.json [START_S DURATION_S]`: mapping -> bodyTrack -> attach -> one-arm preview -> mp4
  with the song's audio. Window renders at 1280x720 (`HYST_FAST`), whole song at 1080p with the original audio copied. A **Render 20 s at playhead**
  button in the authoring page posts the mapping to `serve.py` (`POST /retune`). README section "The tuning loop" has the steps.
  Measured wall times (this machine, 6 threads): 20 s window **20.7 s** (presence, steady state; bodytrack 0.2, build 0.1, compile 4.7, render 15.8;
  the first run adds a 9 s cargo build); through `serve.py` for Five Years 100-120 s **22.5 s**. Whole song at full quality (presence, 270.7 s, 1080p, audio copied):
  **6 min 47 s** (render 401 s; the run was inside a 600 % CPU cap). Window under 60 s on the first try, so nothing needed cutting; what I
  changed from the fallback's recorder anyway: window and fast options (native canvas 720p, veryfast, jpeg 0.8).
- **Phase 2, self-surprisal lane.** New input `self_prediction_error` ("cerebellum: prediction error of its own arm", no claim), the 11th input.
  **Which arm:** the mean over the six replayed v47 arms and the three horizons. No single replayed arm is the arm the fallback drives (the fallback is a
  separate one-arm score, not replayed in physics), so no single arm matches. 30 Hz averaged to the 0.1 s bins, NaN left out, normalised by the
  5th/95th percentiles like the other lanes. Mappings saved with ten inputs still load (zero 11th column). `mappings/*.json` regenerated with 11 inputs.
- **Phase 3, check.** Detached service `hyst-wo6-b2-check` runs `scripts/author/tuning_check.sh`: a 20 s window per song from `example-sketch.json`, the middle frame,
  duration and audio checks, and the 720p copies (< 30 MiB) of the whole-song fallback videos. Results: `/secondary/hyst-data/brain/author/tuning/check.json`,
  frames in `tuning/frames/`. Finished; results below.
- **v47 Off:** no Rust or `crates/` change on this branch (scripts only), so the v47 bytes cannot have changed. Not re-run on this branch; the
  `body-fallback` cmp (3/3 identical) is the last one.
- **Tests:** node author 11 pass; Python `test_attach` 5, `test_build` 1, `test_serve` 2 pass (`python3 -m unittest discover -s scripts/author -p "test_*.py"`).
  Not tested in a browser: the page's Render button (page JS passes `node --check`; the endpoint is tested with a stub and end to end by a real POST).

## Results of the phase 3 check

All paths under `/secondary/hyst-data/brain/author/tuning/` (`check.json` has the numbers). Window start 100 s, example-sketch.json, 1280x720.

| song | window mp4 | window s (audio window 20 s) | audio RMS window / source (aac re-encode) | 720p copy | bytes | s (whole song) |
|---|---|---|---|---|---|---|
| instant-crush | `instant-crush-example-sketch-100s-20s.mp4` | 20.000 | 8861.3 / 8921.1 | `720p/instant-crush-fallback-720p.mp4` | 28,288,112 (27.0 MiB) | 339.833 (339.833) |
| five-years | `five-years-example-sketch-100s-20s.mp4` | 20.000 | 2753.8 / 2773.9 | `720p/five-years-fallback-720p.mp4` | 28,551,237 (27.2 MiB) | 283.771 (283.767) |
| presence | `presence-example-sketch-100s-20s.mp4` | 20.000 | 5416.8 / 5469.8 | `720p/presence-fallback-720p.mp4` | 28,582,033 (27.3 MiB) | 270.744 (270.733) |

Audio RMS differs by about 1 % (the window audio is re-encoded to aac, so bytes are not compared). Middle frames in `frames/*-window-mid.png` (looked at):
arm, disc, floor and shadow drawn, no part below the floor in any of the three; in the Presence frame (110 s) the hand is partly above the top edge of the
view (camera crop, not a floor issue). Whole-song 1080p presence render from the timing run: `tuning/presence-example-sketch.mp4`.

## FOR USER

1. The loop renders windows at 720p for speed; press nothing special for the whole-song 1080p render (run `retune.sh SONG MAPPING.json` with no window).
2. The self-prediction lane is the mean of six v47 arms, not the fallback arm's own motion.
