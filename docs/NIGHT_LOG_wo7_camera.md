# Night log: work order 7, camera framing for one-arm renders (2026-11-05)

## MORNING SUMMARY

Branch `body-tuning`. One arm only. No claims beyond the checks below.

- **Change.** `ensemble_preview` swaps the one-arm camera in the page text (only when the score has exactly one arm; `crates/hyst-previz/src/ensemble.html`
  is untouched, so the hexagon export is byte-identical). New camera: target 0.35 reach above the shoulder, same yaw and pitch, distance found at
  page load as the smallest at which the whole reach envelope (sphere round the shoulder of radius sum of links + implement radius + 5 cm, clipped
  at the floor) projects inside the 1280x720 frame with a 40 px margin.
- **Check.** `scripts/author/camera_check.cjs PAGE.html` projects every arm point and the hand disc every 0.1 s with the page's own camera code.
  `example-sketch.json`: Instant Crush 3399 samples, outside share 0, min margin 144.5 px; Five Years 2838, 0, 141.8 px; Presence 2708, 0, 134.0 px.
  Same check on the old camera (presence page with distance 2.1): outside share 0.0713, min margin -194.4 px, so the check can fail.
- **Presence 110 s frame:** `/secondary/hyst-data/brain/author/tuning/frames/presence-110s.png` (hand and disc inside the frame).
- **v47 Off:** cmp of the three hexagon exports against `hexagon-47.html`, `five-years-hexagon.html`, `presence-hexagon.html`: identical.
- **Tests:** cargo test, clippy -D warnings, fmt --check on hyst-compile, hyst-output, hyst-previz, hyst-cli: pass.
- **Not done:** the three whole-song 720p renders. Mains power was off (`ADP1/online` = 0) for the whole session, so I did not start them.
  To run: on mains, `OUT=/secondary/hyst-data/brain/author/tuning scripts/author/retune.sh SONG scripts/author/mappings/example-sketch.json`
  per song (1080p), then downscale to 720p under 30 MiB as `tuning_check.sh` does. `retune.sh` gained `HTML_ONLY=1` (print the page path, no render).
