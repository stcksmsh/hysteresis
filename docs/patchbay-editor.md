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

## Debug drawer

The 🐞 **Debug** button opens diagnostics that are useful while tuning but
not part of the graph itself: live bus values, musical-state readouts, the
drop detector's internal qualifying conditions (useful if `dropImpulse`
isn't firing on a real track — it shows exactly which condition is
failing), and a log of recent drop events.

## Saving a graph

**Save to file** writes the current graph + fixture set to
`src/render/conductor/patchbay/editor/saved/patch-graph.ts` — a real,
committable TypeScript file, not a copy-paste-from-a-textarea workaround.
This only works against a local `npm run patchbay` dev server (it's a
dev-only Vite middleware, restricted to that one directory).
