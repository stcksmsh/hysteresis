# Authoring page: machine state to the arm's body

The pivot (docs/NEXT_DECODER_THEN_BRAIN.md, section 2): the user authors, by eye, how the machine's state becomes the 15 body
dimensions. No pre-registered rules, no claims. Mapping: `body_d(t) = clamp(base_d + sum_i w_di * input_i(t), 0, 1)`, then a one-pole
smoother with a per-dimension tau (seconds; 0 = none). Lanes are at 10 Hz; bin k is stamped 0.1 (k + 1) s.

Inputs (11, in this order, all 0..1): `arousal`, `tension`, `familiarity`, `surprisal` (B2's lanes, each normalised per song by its
5th and 95th percentiles), `spike` (normalised surprisal above a threshold, rescaled to 0..1, peak-held and decaying with tau; the
threshold and tau are sliders), `band1..band4` (B2's band power L1..L4, normalised the same way), `energy` (core-2b `mood.energy`,
0.5 s steps held; already 0..1, not renormalised), `self_prediction_error` ("cerebellum: prediction error of its own arm", `scripts/body/selfsurprisal.py`: the mean over the six replayed v47 arms and the three horizons, because no single replayed arm is the arm the fallback drives; 30 Hz averaged to 0.1 s; normalised like the others; mechanism name only, no claim). Mappings saved with the first ten inputs still load (the 11th weights are 0).

## Files

| File | What |
|---|---|
| `author_core.cjs` | the maths (normalise, spike lane, mapping, span means, bodyTrack object, mapping validation); used by the page and by node |
| `author_template.html` | the page; `build.py` inlines the maths and the data |
| `build.py` | builds `/secondary/hyst-data/brain/author/index.html` (+ `data.json`, audio symlinks). Data stays outside git |
| `serve.py` | local static server with Range support, port 8765 |
| `retune.sh`, `record_ensemble.cjs` | the tuning loop (below): mapping to an mp4 of the arm with the song's audio |
| `tuning_check.sh` | work order 6 phase 3 check: a window per song, 720p copies |
| `export_cli.cjs` | the page's Export without the page |
| `attach.py` | puts an exported bodyTrack into an interpreted sidecar; `--preview` compiles the arm preview |
| `mappings/neutral.json`, `mappings/example-sketch.json` | neutral start; a sketch to edit (not a claim) |
| `make_mappings.cjs` | writes the two mapping files with the page's own maths |
| `test_author.cjs`, `test_attach.py` | tests (below) |

## Use

```sh
python3 scripts/author/build.py                 # needs B2's lanes in /secondary/hyst-data/brain/b2/
python3 scripts/author/serve.py                 # then open http://127.0.0.1:8765/index.html
```

Sliders: one per input and dimension (weight, -1..1), plus base (0..1) and tau (0..30 s) per dimension; double-click resets one.
The mapping autosaves to the browser's localStorage. Save JSON / Load JSON write and read the mapping file (schema: `author_core.cjs`
`neutralMapping`). Click the plot to seek.

## Arm preview: Export, then compile (the page itself has no live arm)

`ensemble_preview` compiles a whole score from the sidecar, so it cannot follow slider changes live. Instead:

1. In the page press Export bodyTrack. It downloads `SONG.bodytrack.phrase.json` (D3 format: one mean vector per planner phrase,
   the default) or `.beat.json` (one per beat, experimental).
2. Attach it and compile (from the repo root; the sidecars are the `*.interpreted.sidecar.json` files):

```sh
python3 scripts/author/attach.py SONG.interpreted.sidecar.json SONG.bodytrack.phrase.json OUT/SONG.sidecar.json \
  --preview OUT/SONG.html ../audio/SONG.m4a
```

   which runs `cargo run --release -p hyst-previz --example ensemble_preview -- OUT/SONG.html AUDIO_URL OUT/SONG.sidecar.json --body layered --clock music`.
   `AUDIO_URL` is relative to `OUT/SONG.html`; serve `OUT` with `serve.py OUT`.

## The tuning loop: change the mapping, see the arm again in seconds

The installation is one arm. Judge the videos, tune the mapping by eye, re-render.

1. `python3 scripts/author/build.py` once (and again if the lanes change), then `python3 scripts/author/serve.py` and open
   `http://127.0.0.1:8765/index.html`.
2. Edit the sliders. Put the playhead where you want to look and press **Render 20 s at playhead**: the page posts the current mapping to
   `serve.py`, which runs `retune.sh` and plays the clip under the header (about 20 s of waiting, one arm, 720p).
3. Or from a shell, with a mapping file the page saved (Save JSON) or any file in `mappings/`:

```sh
scripts/author/retune.sh SONG MAPPING.json 60 20     # a 20 s window starting at 60 s, 1280x720, audio re-encoded
FULL=1 scripts/author/retune.sh SONG MAPPING.json 60 20   # the same window at 1920x1080
scripts/author/retune.sh SONG MAPPING.json                # the whole song, 1920x1080, original audio copied (full quality, minutes)
```

   SONG is `instant-crush`, `five-years` (its tempo map is applied) or `presence`. Output: `/secondary/hyst-data/brain/author/tuning/`
   (`SONG-MAPPING[-STARTs-DURs].mp4`; intermediate files in `work/`). `retune.sh` prints the seconds each step took.
4. Steps inside: `export_cli.cjs` (mapping to bodyTrack), `attach.py` (into the interpreted sidecar), `cargo build --release` of `ensemble_preview`
   (a no-op when current; it uses its own target dir, `CARGO_TARGET_DIR`), the preview page, then `record_ensemble.cjs` draws it frame by frame.
   Where the time goes in a 20 s window: compile about 5 s, frame capture and encoding about 16 s. Window renders use `HYST_FAST=1` (the page's own
   1280x720 canvas, x264 veryfast, no upscale); the whole-song render keeps the full-quality settings.

## Per-beat bodyTrack

`body_track.rs` accepts any ordered list of spans, and the planner reads the track only through `BodyTrack::at(t, beat)`. A per-beat
export (spans = beat intervals) therefore parses and compiles with no change in hyst-compile (checked on `presence`). What it
does not do is make every knob follow the beat: knobs that `figures.rs` reads once per figure or moment (`body_at(t)` at a figure's
start) take only the beat value at that time. A knob that follows the state inside a figure would need hyst-compile to sample
`body_at` along the figure. Not verified by eye.

## Tests

```sh
node --test scripts/author/test_author.cjs
python3 -m unittest discover -s scripts/author -p "test_*.py"     # attach, build (self-prediction lane), serve (/retune with a stub)
cargo test -p hyst-compile body_track          # includes the exported fixture, crates/hyst-compile/tests/fixtures/bodytrack_author.json
```
