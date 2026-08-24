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
- Input types: `float`, `bool`, `long`, `color`, `point2D`.
  - `color` and `point2D` inputs expand into separate scalar targets
    (`isf.tint.r`/`.g`/`.b`/`.a`, `isf.center.x`/`.y`) since every patch
    graph node is scalar-in/scalar-out.
  - `long` becomes a target over the input's value *index* (0..N-1), not
    its raw values — route a signal, then use a `map` node if you need it
    scaled to a specific index range.
- The standard ISF built-ins a single-pass shader can use: `TIME`,
  `TIMEDELTA`, `RENDERSIZE`, `PASSINDEX` (always `0`), `FRAMEINDEX`, `DATE`,
  `isf_FragNormCoord`, `gl_FragColor`, `texture2D`/`textureCube`.

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
