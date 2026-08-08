# the СИНТЕЗА visualizer

A framework-agnostic visualizer package that reacts to musical *structure* —
builds, drops, breaks, groove — instead of instantaneous amplitude. It's
built on hysteresis: the image itself accumulates history, so what's on
screen depends on the whole recent signal, not just this instant. It winds
up during builds, releases on drops, and goes suspended during breaks.

See `SINTEZA_VIZ.md` for the design doc and `IO_PAGE_CHANGESET.md` §6 (in
`stcksmsh.github.io`) for the interface as actually integrated. Ships as a
package the host mounts once:

```ts
import { init } from 'sinteza-viz'

const instance = init(canvas, {
  accent: [0.68, 0.2, 33], // OKLCH [L, C, H]
  tier: 'full',
  getAudioContext: () => audioBus?.ctx ?? null, // null until the host's first play click
  getAnalyser: () => audioBus?.analyser ?? null,
})
instance.setAccent([0.7, 0.15, 200])
instance.setTier('cheap')
instance.resize()
instance.destroy()
```

No DOM ownership beyond the canvas, no routing, no player UI, no
`AudioContext` creation — all of that is the host's job (the IO page repo).
Transport (`play`/`pause`/`seek`/`trackchange`/`position`) and the
precomputed sidecar URL (`trackchange`'s `track.envelope`) aren't pushed
through this API at all — `init()` listens for them itself on a `window`
`"player:transport"` `CustomEvent` bus, matching the host's own
`src/lib/player-bus.ts`. `getAudioContext`/`getAnalyser` are polled (not
assumed present at call time) since the shared bus is created lazily on the
host's first play click, well after this package typically mounts.

Three-layer architecture:

- **Layer 1 (`src/audio/worklet/`)** — feature extraction in an
  `AudioWorklet`: own windowed FFT, perceptual band split (sub/low/mid/
  presence/air), spectral centroid, spectral flatness, spectral-flux novelty,
  a trigger-locked waveform ring buffer for the oscilloscope beam.
- **Layer 2 (`src/audio/worklet/brain/`)** — musical state: beat tracking
  (tempo + a phase-locked oscillator that free-runs through breaks), build
  detector, drop detector, break/tension detector. Fused with a precomputed
  sidecar's structure when one is loaded (`src/audio/StructureSource.ts`) —
  detail (bands/onsets/energy) is always live either way.
- **Layer 3 (`src/render/choreography/`, `src/render/worker/scenes/julia/`,
  `src/render/worker/passes/`)** — choreography (spring-damper driven
  parameters) and the visual scene, rendered via WebGL2 on an
  `OffscreenCanvas` in a dedicated Worker: an animated Julia-set substrate,
  fed into a curl-noise-advected feedback field that is THE signature
  layer — the image itself accumulates and decays the last few seconds of
  the song — an oscilloscope beam riding on top, and onset-triggered
  particles dragged through the same flow field. Earned symmetry (a
  tension/build-driven domain warp, snapping to full symmetry for one bar
  on a drop) modulates the feedback field's own advection, never applied as
  a constant filter.

## Offline sidecar tool

```sh
npm run analyze -- path/to/master.wav [output.sidecar.json]
```

Ingests one WAV master (no DAW project, no stems) and emits a
`<slug>.sidecar.json` (schema 2) — tempo, beats, sections, structural events,
an onset list, and per-band/centroid/flatness energy envelopes. This repo
produces it; the host serves it as a static asset and calls `loadSidecar(url)`
on `trackchange`.

**Two ways a host can use it**, and `init()` picks automatically based on
whether live audio ever attaches:
- **Self-hosted `<audio>`/AudioContext**: sidecar supplies structure (beats,
  drops, sections — with look-ahead), live analysis supplies detail. This is
  the original mode.
- **SoundCloud/Bandcamp embeds (no `AnalyserNode` reachable at all)**: if
  it's your own track, run `analyze` against the original master and the
  richer schema-2 sidecar drives the *entire* visual from playback position
  alone — feed `setPosition` from the embed's own position API (e.g.
  SoundCloud Widget's `PLAY_PROGRESS`), no Worklet attach needed. The
  oscilloscope beam falls back to its idle Lissajous (no real waveform
  survives an offline envelope) — everything else is genuinely reactive.

See `SINTEZA_VIZ.md` §5 for the full fusion rules.

## Develop

```sh
npm install
npm run dev
```

Opens at `http://localhost:5173/sinteza-viz/`. This is a local dev harness
only (`src/main.ts`) — a bare file picker exercising the real `init()` API,
not what ships. Building the actual package is `npm run build:lib`.

## Build

```sh
npm run build:lib   # the package: dist/index.js + dist/index.d.ts + dist/worklets/
npm run build       # the local dev-harness demo site (GitHub Pages)
npm run preview
```

`vite.config.ts` sets `base: '/sinteza-viz/'` to match the demo's GitHub
Pages project-pages subpath; it does not affect the library build.

## Test

```sh
npm run typecheck
npm test
```

Unit tests use deterministic synthetic signals (click trains, synthetic
spectra) for CI-verifiable regression coverage of the DSP/detector math.
Perceptual tuning against real audio happens via the dev harness, not in CI.

## Notes

- No microphone input — file-load only in the dev harness.
- The AudioWorklet is bundled separately (`vite.worklet.config.ts`) into
  `public/worklets/feature-worklet.js`, since Vite's `new URL(...)` idiom only
  special-cases `new Worker()`, not `audioWorklet.addModule()`. Consumers of
  the published package may need to pass `workletUrl` explicitly if their
  bundler doesn't resolve the default (see `src/index.ts`).
