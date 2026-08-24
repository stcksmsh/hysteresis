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

- Single-pass shaders by default (`PASSES` with more than one entry is
  rejected) — unless `HYSTERESIS_VERSION` declares real Hysteresis-format
  multi-pass support (see below).
- Input types: `float`, `bool`, `long`, `color`, `point2D`, `hysteresisSignal`,
  `resource`, `scriptOutput` (the last three are this repo's own real
  extensions beyond standard ISF — see below).
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

## `HYSTERESIS_VERSION` and real multi-pass: the `.hyst` format

Files using the extensions below are conventionally named `.hyst` rather
than `.fs` — same physical shape (one file, `/*{ ... }*/` JSON header then
GLSL), just signaling "this uses the real Hysteresis-format extensions, not
just stock ISF". A plain `.fs`/`.hyst` file with no `HYSTERESIS_VERSION` at
all behaves identically either way — the extension is a naming convention,
not something the parser checks.

`"HYSTERESIS_VERSION": 1` at the header's top level is what actually makes
the extensions below available, and is the format's real future-proofing
mechanism: an unrecognized version (anything other than the one number this
parser currently knows) is rejected clearly at load time, rather than
guessed at — the same "reject clearly, never silently mis-render"
discipline every other unsupported feature here already follows. A file
with no `HYSTERESIS_VERSION` is 100% the plain single-pass model above,
unchanged.

### Real `PASSES`, typed by `KIND`

Under `HYSTERESIS_VERSION: 1`, `PASSES` becomes real — but a deliberately
scoped subset, not the entirety of what the real ISF spec allows (no
`PERSISTENT`/feedback buffers yet — see "What's not supported" below). Each
pass has a `KIND`:

- `"KIND": "fullscreen"` (the default if omitted) — exactly today's model:
  one GLSL `main()` (`doc.body`, shared by every fullscreen pass) drawn
  over a fullscreen quad.
- `"KIND": "lineTrace"` — draws an open polyline from a named `resource`
  input (see below), using the same cheap GPU-instanced-quad technique the
  built-in Julia scene's oscilloscope beam already uses (real hardware line
  rasterization — a naive "loop over every sample in the fragment shader"
  approach was costed out during this format's design and rejected: ~2
  billion segment evaluations per 1080p frame, versus near-free instanced
  geometry). A `lineTrace` pass has no shader-author GLSL body — it's
  structural, not a fragment shader.
  - `POINTS` (required): the `NAME` of a declared `resource` input
    supplying the polyline's points.
  - `WIDTH` (optional): the `NAME` of a declared `float`/`hysteresisSignal`
    input controlling line half-width; omitted uses a sensible runtime
    default.

Every pass's `TARGET` (a non-empty string, required for `lineTrace`,
optional for `fullscreen`) becomes a real `uniform sampler2D <TARGET>;`
automatically available to the shared fullscreen body — this is the actual
mechanism for "the beam is part of the shader": a `lineTrace` pass
rasterizes the waveform's shape into a texture (always full-brightness
white — tint/blend/warp is entirely the fullscreen pass's own GLSL's job,
not baked into the line pass), and the fullscreen shader samples/recolors/
composites it however it wants:

```json
{
  "HYSTERESIS_VERSION": 1,
  "PASSES": [
    { "TARGET": "beamTex", "KIND": "lineTrace", "POINTS": "scope", "WIDTH": "beamWidth" },
    { "TARGET": "", "KIND": "fullscreen" }
  ],
  "INPUTS": [
    { "NAME": "scope", "TYPE": "resource", "RESOURCE": "scope" },
    { "NAME": "beamWidth", "TYPE": "float", "DEFAULT": 0.01, "MIN": 0.001, "MAX": 0.05 }
  ]
}
```
```glsl
uniform sampler2D beamTex;
void main() {
  vec4 beam = texture2D(beamTex, isf_FragNormCoord);
  gl_FragColor = beam * vec4(1.0, 0.4, 0.2, 1.0); // shader decides the beam's own color/blend
}
```

### `resource` inputs — for live data that isn't a scalar

`hysteresisSignal` covers every *scalar* live signal, but not everything the
Feature Engine produces is a scalar — `scope` (`SignalBus.scope`, the raw
oscilloscope waveform) is a `Float32Array` snapshot, not a number. A
`resource` input is how a shader accesses one:

```json
{ "NAME": "scope", "TYPE": "resource", "RESOURCE": "scope" }
```

Unlike every other input type, a `resource` is **never a routable patch-
graph target** — the patch graph stays scalar-in/scalar-out throughout
(unchanged). It's bound automatically by name instead, the same category
`TIME`/`RENDERSIZE` already are, just opt-in per shader. `RESOURCE` is
validated against a small, explicit, real list (currently just `"scope"` —
the one non-scalar live signal that exists today) — an unknown name is
rejected at load time with the valid list, same discipline as
`hysteresisSignal`'s `SIGNAL` field. A `lineTrace` pass's `POINTS` names
which declared `resource` input feeds it.

## `HYSTERESIS_SCRIPT` — a real stateful JS companion

A shader's header may declare `"HYSTERESIS_SCRIPT": "..."` — a per-frame
stateful JS companion for anything a single GLSL fragment shader can't
express on its own, since ISF's model has no concept of persistent JS-side
state at all (orbit tracking, target-seeking navigation, spring-damped
drift — see `examples/isf/julia-autopilot.hyst`, a real port of the
built-in Julia scene's own autopilot onto this mechanism). Requires
`HYSTERESIS_VERSION` to be declared, same version-gating discipline real
multi-pass `PASSES` already uses.

**The script's shape.** The source must define (and leave in scope) a
function `update(dt, inputs, idle, time)`, called once per render frame:

- `dt` — seconds since the last call.
- `inputs` — the shader's own declared `hysteresisSignal` (and other
  patch-routed scalar) input values, exactly as resolved that frame — the
  script never sees the raw Feature Engine signal bus, only what the patch
  graph already resolved into this shader's own inputs, the same values its
  GLSL uniforms get.
- `idle` — true when there's no live audio driving the scene (not a
  routable signal; supplied the same direct, non-patch-graph way the
  built-in beam's idle Lissajous fallback already works).
- `time` — the shader's own running clock (matches the GLSL `TIME` uniform).

It must return `{ uniforms, textures }` (either may be omitted): `uniforms`
supplies the current-frame value for every declared `scriptOutput` input
(see below) by name; `textures` supplies a flat `number[]` for every
declared `scriptTexture` pass's `SOURCE` name (see below). All per-frame
state — springs, search targets, accumulated zoom — lives in the script's
own closure, exactly like a hand-written `Scene` class's private fields
would.

**`scriptOutput` inputs** — a value the script computes every frame instead
of the patch graph:

```json
{ "NAME": "zoom", "TYPE": "scriptOutput", "KIND": "float", "DEFAULT": 2.0 }
```

`KIND` is one of `float`/`bool`/`point2D`/`color` (mirrors the shape of the
matching ordinary input type; `long` isn't supported yet — no motivating
shader needs it). Like `resource`, a `scriptOutput` input is **never a
routable patch-graph target** — there's no ambiguity about which mechanism
owns its value. Requires `HYSTERESIS_SCRIPT` to be declared.

**`scriptTexture` passes** — the non-scalar counterpart, for data too big to
be a single uniform (a perturbation reference orbit, say):

```json
{ "TARGET": "refOrbit", "KIND": "scriptTexture", "SOURCE": "refOrbit", "LENGTH": 192 }
```

Generalizes the exact mechanism a `lineTrace` pass already established: `TARGET`
becomes a real `uniform sampler2D <TARGET>` the fullscreen body can
`texelFetch` from, just backed by the script's own per-frame data instead of
GPU-rasterized geometry. `SOURCE` names the field in the script's returned
`textures` object; `LENGTH` is the fixed **texel** count — the runtime
always uses two floats per texel (RG32F, height 1), so the script's array
for a `LENGTH: 192` pass must be 384 numbers long (interleaved R, G per
texel — exactly `JuliaScene.ts`'s own `Float32Array(REF_ORBIT_LENGTH * 2)`
shape). A wrong-length or non-finite array is padded/truncated/sanitized
(holding the last finite value) automatically — see "How it's executed"
below for where that happens. Requires `HYSTERESIS_SCRIPT` to be declared.

**How it's executed.** The script never runs on the render worker's own
thread. It runs inside a separate, sandboxed nested Worker, spawned fresh
for each loaded shader, talking to the render worker over `postMessage`.
Every frame, the render worker sends that frame's `{dt, inputs, idle,
time}` and immediately continues rendering with the **last completed
reply** — it never blocks waiting for a fresh one. In practice this is one
frame of latency at most, imperceptible at the timescales a script like
this actually operates on (springs settling over 100ms+, a navigation
re-check every 250ms, a zoom dive running for minutes). If the script hangs
(no reply within its timeout budget) or throws, its Worker is terminated
and a fresh one spawned — rendering keeps going on the last-known values
throughout, never blocking or crashing. After several consecutive faults,
the host stops retrying (a script that's fundamentally broken won't be
fixed by another restart) and reports the failure once, still rendering on
frozen values indefinitely.

Every value the script returns is validated and coerced against the
shader's own declared `scriptOutput`/`scriptTexture` shapes **inside** the
sandboxed Worker, before it's ever sent back — a malformed or wrong-length
value falls back to its declared default there, so it never reaches the
trusted render-worker side (and a real GL call) malformed.

**"Sandboxed" here means fault/crash isolation, not a security boundary.**
The script's Worker still has `fetch`/`XMLHttpRequest` and can make network
requests — it just can't touch the render worker's GL context, DOM, canvas,
or any other state directly, and a hang or crash inside it can never take
down rendering. Treat a `HYSTERESIS_SCRIPT` the same trust level as any
other shader source you'd load — this protects uptime, not against a
genuinely malicious script.

**One practical constraint**: spawning the nested Worker (a `blob:` URL)
and evaluating the script's own source (a real `Function` construction)
both need a permissive-enough Content-Security-Policy (`worker-src blob:`,
`script-src 'unsafe-eval'`) wherever this runs. `loadIsfShader` is opt-in
and the production site never calls it today, so this has no current
impact — it's a real constraint on whether a host page *could* load a
shader using this feature, not something this engine can work around.

## What's not supported (yet)

Rejected at load time with a specific error, rather than silently
mis-rendering:

- **Stock ISF multi-pass** (`PASSES` with more than one entry, no
  `HYSTERESIS_VERSION` declared) — real ISF ecosystem shaders using the
  spec's own `PASSINDEX`-branching multi-pass model aren't supported.
  `HYSTERESIS_VERSION: 1`'s own real (but scoped) `PASSES`/`KIND` model
  above is a different, Hysteresis-format-specific mechanism.
- **`PERSISTENT` buffers** — cross-*frame* GPU feedback, distinct from
  `HYSTERESIS_SCRIPT`'s own CPU-side state; rejected under
  `HYSTERESIS_VERSION` too, not just stock ISF.
- **Pass `KIND`s beyond `fullscreen`/`lineTrace`/`scriptTexture`** — no
  motivating shader yet (particles, SDF clouds, etc.).
- **`resource` kinds beyond `scope`** — no other *system-provided*
  non-scalar live signal exists yet (a future FFT-bins resource would
  extend `KNOWN_RESOURCES` in `parse-isf.ts`, not require a format change;
  a script-*produced* non-scalar value is `scriptTexture`, already real).
- **`scriptOutput` `KIND: "long"`** — no motivating shader needs it yet.
- **`image`/`audio`/`audioFFT` inputs** — there's no general asset-import
  or audio-texture pipeline (distinct from the narrow, system-provided
  `resource` mechanism above).
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
