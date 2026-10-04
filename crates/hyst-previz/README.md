# Figure-planner arm preview

`ensemble_preview` compiles an interpreted sidecar with the figure planner
(`hyst_compile::director::figures::compile_figures`), samples the resolved score at
60 fps and exports one standalone HTML preview (`src/ensemble.html`). Audio
playback position owns time; pause and seek reconstruct the arm from the same
score. The browser canvas is disposable previz, not a native renderer.

Human dance acceptance is still open. Figure shapes and motif tables are prototype
assumptions. Rig geometry is illustrative; no hardware-safety claim.

## Input sidecar

The sidecar must carry `musicalMemory`, `stemInterpretation` and `musicalStructure`:

```sh
media=/path/to/media
python3 scripts/dance_memory.py "$media/track.wav" "$media/track.sidecar.json" "$media/track.memory.sidecar.json" "$media/track.memory.evidence.json"
python3 scripts/dance_stems.py "$media/track.memory.sidecar.json" "$media/stems" "$media/track.stems.sidecar.json" "$media/track.stems.evidence.json"
python3 scripts/dance_structure.py "$media/track.wav" "$media/track.stems.sidecar.json" "$media/track.interpreted.sidecar.json" "$media/track.interpreted.evidence.json"
```

`scripts/instant_crush.acceptance.json` holds the user's listening references. It is
validation-only (optional last argument of `dance_structure.py`) and must never
drive inference or choreography.

## Preview

```sh
cargo run --release -p hyst-previz --example ensemble_preview -- OUTPUT.html AUDIO_URL SIDECAR.json [options]
```

`AUDIO_URL` resolves relative to `OUTPUT.html`; serve both with a range-capable
local server for reliable seeking. Audio starts only after Play.

- `--score PATH` writes the resolved score JSON for audit.
- `--rig PATH` uses JSON rig geometry and local axes (default: illustrative five-axis).
- `--zone x0,y0,z0,x1,y1,z1` adds a red zone no link may enter, metres, repeatable.
- `--groove-only` disables hit accents.
- `--no-reuse` disables recalled musical material.
- `--figures` is accepted and ignored; the figure planner is the only mode.

## Critique panel

The preview has a Critique panel for review notes: time ranges, tags and text.
Notes persist in browser `localStorage` and export as JSON together with planner
context (the cues and hand positions under each marked range).

## Verification

```sh
cargo test -p hyst-compile -p hyst-previz
cargo clippy -p hyst-compile -p hyst-previz --all-targets -- -D warnings
node crates/hyst-previz/tests/ensemble.cjs
python3 -m unittest discover -s scripts -p 'test_dance_*.py'
```
