# Authoring page: machine state to the arm's body

The pivot (docs/NEXT_DECODER_THEN_BRAIN.md, section 2): the user authors, by eye, how the machine's state becomes the 15 body
dimensions. No pre-registered rules, no claims. Mapping: `body_d(t) = clamp(base_d + sum_i w_di * input_i(t), 0, 1)`, then a one-pole
smoother with a per-dimension tau (seconds; 0 = none). Lanes are at 10 Hz; bin k is stamped 0.1 (k + 1) s.

Inputs (10, in this order, all 0..1): `arousal`, `tension`, `familiarity`, `surprisal` (B2's lanes, each normalised per song by its
5th and 95th percentiles), `spike` (normalised surprisal above a threshold, rescaled to 0..1, peak-held and decaying with tau; the
threshold and tau are sliders), `band1..band4` (B2's band power L1..L4, normalised the same way), `energy` (core-2b `mood.energy`,
0.5 s steps held; already 0..1, not renormalised).

## Files

| File | What |
|---|---|
| `author_core.cjs` | the maths (normalise, spike lane, mapping, span means, bodyTrack object, mapping validation); used by the page and by node |
| `author_template.html` | the page; `build.py` inlines the maths and the data |
| `build.py` | builds `/secondary/hyst-data/brain/author/index.html` (+ `data.json`, audio symlinks). Data stays outside git |
| `serve.py` | local static server with Range support, port 8765 |
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

## Per-beat bodyTrack

`body_track.rs` accepts any ordered list of spans, and the planner reads the track only through `BodyTrack::at(t, beat)`. A per-beat
export (spans = beat intervals) therefore parses and compiles with no change in hyst-compile (checked on `presence`). What it
does not do is make every knob follow the beat: knobs that `figures.rs` reads once per figure or moment (`body_at(t)` at a figure's
start) take only the beat value at that time. A knob that follows the state inside a figure would need hyst-compile to sample
`body_at` along the figure. Not verified by eye.

## Tests

```sh
node --test scripts/author/test_author.cjs
python3 -m unittest discover -s scripts/author -p "test_attach.py"
cargo test -p hyst-compile body_track          # includes the exported fixture, crates/hyst-compile/tests/fixtures/bodytrack_author.json
```
