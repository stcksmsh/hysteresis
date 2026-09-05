# Patchbay editor

A dev-only visual tool for authoring the patch graph that drives Hysteresis's
screen visual (and, eventually, physical fixtures — DMX/LED/servo/laser).
It runs a **real** instance of the same render worker the shipped package
uses, so what you see is the actual visual, not a mock of it.

## Running it

```sh
npm run patchbay
```

Opens a local dev server. Use the **⤢** button (or the file picker in the
transport bar) to load a music file and hear/see the visual react; **✕
Edit** returns to the authoring layout.

## Screens

The canvas preview + transport bar are always visible (top-right in edit
mode, full-viewport in demo mode). Below them, four screens, switched via
the nav bar in the header:

- **Patch Graph** — the node canvas (see below), full width.
- **Shaders** — author/load a `.hyst`/ISF shader (see below).
- **Output** — Fixtures, Fixture Visuals, and DMX/OSC/MIDI I/O configuration,
  all in one place.
- **Diagnostics** — live bus/musical-state readouts, the drop detector's
  internal qualifying conditions, and a log of recent drop events. Read-only;
  nothing here shapes the graph.

## The mental model

- **Signal bus** — every frame, Hysteresis computes a flat set of named,
  typed signals from the audio (loudness bands, spectral centroid, beat/bar
  phase, build/drop/break structure, and more). These are read-only inputs
  to a patch graph; you never write to them directly.
- **Patch graph** — a node graph you build in the canvas: `signal` nodes
  read the bus, operator nodes (`threshold`, `envelope`, `logic`,
  `combine`, `curve`, `map`) reshape/gate/combine values, and `target`
  nodes write the result somewhere. One graph can drive both the screen
  and physical fixtures at once — that's the point of the unified engine.
- **Targets** — the "somewhere" a `target` node writes to. Built-in screen
  targets (`screen.*`) are always available; adding a fixture (see below)
  or loading an ISF shader (see [ISF shaders](./isf-shaders.md)) adds more
  targets to the same dropdown, live, with no code change.
- **Fixtures** — simulated physical devices (dimmer / RGB / servo / mover)
  you add in the right-hand rail. Each instance's channels become real
  routable targets immediately, and `Fixture visuals` shows a live simulated
  readout (glow / swatch / needle / crosshair) so you can sanity-check a
  patch without real hardware attached yet.

## Working with the graph canvas

- Drag a node's header to reposition it.
- Drag from a node's output circle to another node's input circle to wire
  them. Click a filled input circle to disconnect (and immediately pick the
  wire back up for rewiring).
- Click a node to select it and edit its typed fields in the side inspector.
- Double-click a node's header to rename it — useful once a graph has more
  than a couple of nodes; the "find a node" box in the toolbar autocompletes
  by name.
- Delete/Backspace removes the selected node (only when no form field has
  focus, so editing a number field's digits doesn't also delete the node).
- Mouse wheel zooms toward the cursor; drag empty background to pan; **⊡
  Fit** frames the whole graph.

## Live-controlling an envelope's attack/release with a knob

A `midiCc`/`oscIn` node can already drive any target's *value* directly
(wire it straight to a `target` node, or into `combine`/`curve`/`map` like
any signal). `envelope` nodes go one step further: their **attack/release
time constants themselves** can be live-controlled too, not just the value
being smoothed. This is what makes something like "a physical fader that
controls how loose/tight a servo's motion feels, live" possible — the fader
isn't driving the servo's position, it's driving *how the servo eases into*
whatever position the signal chain gives it.

An `envelope` node has 3 input slots in the graph canvas (hover a slot to
see which is which):

1. **value** — the signal to smooth (required, same as always).
2. **attack override** (optional) — when wired, this input's live value
   replaces the node's own `attackSec` field every frame. Leave unwired to
   use the static field, exactly like before this existed.
3. **release override** (optional) — same, for `releaseSec`.

A `midiCc`/`oscIn` node's value is always 0..1, so route it through a `map`
node first to rescale into a real seconds range before feeding an override
slot — e.g. `midiCc → map(0..1 → 0.01..2.0) → envelope's attack override`.
This is the same "remap a knob into a target's real range" pattern any
other knob-to-target route already uses; nothing envelope-specific about
the remap itself.

## Authoring a shader (the Shaders screen)

Load, author, or edit a `.hyst`/ISF shader entirely inside the tool — no
external editor round-trip required. A shader is edited as three tabs:

- **Header** — the JSON header (`INPUTS`, `PASSES`, `CATEGORIES`, etc.), raw
  text with real syntax highlighting.
- **GLSL** — the fullscreen pass body.
- **Script** — the `HYSTERESIS_SCRIPT` companion (see
  [ISF shaders](./isf-shaders.md)), edited as plain, unescaped JavaScript —
  not the hand-escaped JSON-string text the raw file format actually uses.
  Click **+ Add HYSTERESIS_SCRIPT** to start one on a shader that doesn't
  have one yet.

Parse feedback (a structured summary of the shader's declared inputs/passes,
or a real `parseIsf()` error message) updates live as you type, debounced.
**Apply** (or ⌘/Ctrl+Enter) sends the current draft to the live render
worker — the canvas preview becomes that shader immediately on success.
**Save** writes it to a real file under `examples/isf/`. The two bundled
example shaders (`julia.hyst`, `julia-autopilot.hyst` — the full Julia
autopilot, ported onto `HYSTERESIS_SCRIPT`) are one click away as starting
templates.

## Saving a graph

**Save to file** writes the current graph + fixture set to
`src/render/conductor/patchbay/editor/saved/patch-graph.ts` — a real,
committable TypeScript file, not a copy-paste-from-a-textarea workaround.
This only works against a local `npm run patchbay` dev server (it's a
dev-only Vite middleware, restricted to that one directory).
