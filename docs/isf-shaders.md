# ISF shaders

[ISF](https://isf.video/) (Interactive Shader Format) is a GLSL fragment
shader plus a JSON header declaring typed, host-exposed inputs — the format
behind a large existing library of free VJ-style generators and effects
(plasma fields, kaleidoscopes, noise fields, feedback effects, and more).
The patchbay editor can load a real `.fs` file from that ecosystem as the
screen's active scene, and every input the shader declares shows up as a
real target you can route any signal into — the same way `screen.*` targets
or a fixture's channels do.

## Loading a shader

In the patchbay editor's right-hand rail, under **ISF shader**: click
**Load .fs shader…** (or drag a `.fs` file onto the panel). If it parses and
compiles, the screen immediately switches to it, and its declared inputs
appear in the panel and in the graph canvas's target dropdown, prefixed
`isf.` (e.g. an input named `speed` becomes target `isf.speed`). **Revert to
Julia** switches back to the built-in scene at any time.

## Using it from a real host, not just the editor

`loadIsfShader`/`clearIsfShader` are real, public methods on the object
`init()` returns (`VizInstance`) — not editor-only debug hooks:

```ts
const instance = init(canvas, opts)
const source = await fetch('my-shader.fs').then((r) => r.text())
instance.loadIsfShader(source, (result) => {
  if (result.ok) console.log('loaded, targets:', result.targets)
  else console.error('rejected:', result.message)
})
// ...later
instance.clearIsfShader() // back to the built-in Julia scene
```

This is opt-in and additive: no existing integration (including the real
`stcksmsh.github.io` site) calls it today, so nothing changes unless a host
chooses to. Whether the production site itself should ever swap its
background to a loaded shader is a separate product decision, not something
this capability decides on its own.

## What's supported

A real subset, not a stub — anything accepted here renders for real:

- Single-pass shaders only (`PASSES` with more than one entry is rejected).
- Input types: `float`, `bool`, `long`, `color`, `point2D`, `hysteresisSignal`
  (see below — this repo's own real extension beyond standard ISF).
  - `color` and `point2D` inputs expand into separate scalar targets
    (`isf.tint.r`/`.g`/`.b`/`.a`, `isf.center.x`/`.y`) since every patch
    graph node is scalar-in/scalar-out.
  - `long` becomes a target over the input's value *index* (0..N-1), not
    its raw values — route a signal, then use a `map` node if you need it
    scaled to a specific index range.
- The standard ISF built-ins a single-pass shader can use: `TIME`,
  `TIMEDELTA`, `RENDERSIZE`, `PASSINDEX` (always `0`), `FRAMEINDEX`, `DATE`,
  `isf_FragNormCoord`, `gl_FragColor`, `texture2D`/`textureCube`.

## The Hysteresis format: `hysteresisSignal` inputs

Standard ISF has no concept of "the beat" or "how novel does the mix sound
right now" — a shader author has to fall back to a generic `float` and hope
whoever's patching it knows to route the right thing in. `hysteresisSignal`
is this repo's own real extension: a shader declares it wants a *specific*
live Feature Engine signal by name, not an anonymous knob.

```json
{ "NAME": "novelty", "TYPE": "hysteresisSignal", "SIGNAL": "noveltyLocal", "DEFAULT": 0 }
```

`SIGNAL` must be one of the ~35 real, currently-live bus signal names (see
`SIGNAL_TAGS` in `src/render/conductor/types.ts` for the exact list — things
like `noveltyLocal`/`noveltySection`, `familiarity`, `harmonicNovelty`,
`chromaRootHue`, `fullness`, `onsetDensity`, every per-band energy, and the
sidecar-only stem-presence signals). An unknown `SIGNAL` name is rejected at
load time with the full valid list in the error message, same discipline as
every other rejection this importer does.

It becomes a real, routable target — **exactly the same as every other ISF
input type**: it shows up as `isf.<name>` in the editor's target catalog and
graph canvas, with a default range of `0..1` (or `-1..1` for the handful of
known bipolar signals, e.g. `bandTilt`/`pan`) instead of an arbitrary one.
There's no implicit auto-wiring — you (or a default config) still route a
`signal` node into it via the patch graph like anything else. The only real
difference from a plain `float` input is that it's self-documenting about
which live signal it's shaped for, and gets a sensible default range for
free.

## `HYSTERESIS_SCRIPT` — reserved, not executed yet

A shader's header may declare `"HYSTERESIS_SCRIPT": "..."` — a **planned**
per-frame stateful JS companion (orbit tracking, target-seeking, anything a
single GLSL fragment shader can't express on its own, since ISF's model has
no concept of persistent JS-side state at all). This key is currently
**rejected at load time with a clear error** rather than silently ignored —
a shader that depends on it for correct rendering should fail loudly, not
mis-render. The real execution engine (persistent per-frame state, typed bus
access, producing extra uniforms beyond plain signal routing) is real,
separate, not-yet-built work — this is deliberately reserved now so a
future shader authored against it won't need a breaking format change once
it lands.

## What's not supported (yet)

Rejected at load time with a specific error, rather than silently
mis-rendering:

- **Multi-pass shaders** (`PASSES` with more than one entry) and
  **`PERSISTENT` buffers** — these need their own ping-pong buffer
  management per shader; only a single fullscreen draw exists today.
- **`image`/`audio`/`audioFFT` inputs** — there's no asset-import or
  audio-texture pipeline yet.
- **`IMPORTED` images** — same reason.
- **`event`-type inputs** — not yet mapped to anything in the patch graph.

If a shader uses any of these, the error message names exactly which input
or feature is the problem, so you know whether it's worth trimming the
shader down or waiting for that capability to land.

## How routing works under the hood

An ISF shader's inputs bypass the screen's own hand-tuned parameter math
(`flowStrength`/`symmetry`/`fieldDecay`, still computed from `screen.*`
targets as usual — a loaded shader still gets the memory-field/bloom
pipeline applied on top, same as the Julia scene) — they're fed straight
from that frame's resolved patch-graph values into the shader's own GLSL
uniforms. This is why they behave exactly like any other target: gain,
offset, curves, thresholds, and envelopes all work on them the same way
they work on a `screen.*` or fixture target.
