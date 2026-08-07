# HYSTERESIS

A framework-agnostic visualizer package that reacts to musical *structure* —
builds, drops, breaks, groove — instead of instantaneous amplitude. It has
memory and anticipation: it winds up during builds, releases on drops, and
goes suspended during breaks.

See `HYSTERESIS.md` for the full design doc. Ships as a package the host
mounts once:

```ts
import { init } from 'hysteresis'

const handle = init(canvas, { analyser, audioContext, source })
handle.setTransport({ type: 'play' })
handle.setPosition(seconds)
await handle.loadSidecar('/audio/track.sidecar.json')
handle.setAccent('#ff5c38')
handle.setTier('full')
```

No DOM ownership beyond the canvas, no routing, no player UI, no
`AudioContext` creation — all of that is the host's job (the IO page repo).

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
- **Layer 3 (`src/render/choreography/`, `src/render/worker/scenes/julia/`)**
  — choreography (spring-damper driven parameters) and the visual scene: an
  animated Julia-set substrate + oscilloscope beam, rendered via WebGL2 on an
  `OffscreenCanvas` in a dedicated Worker.

## Offline sidecar tool

```sh
npm run analyze -- path/to/master.wav [output.sidecar.json]
```

Ingests one WAV master (no DAW project, no stems) and emits a
`<slug>.sidecar.json` — tempo, beats, sections, structural events, an energy
envelope. This repo produces it; the host serves it as a static asset and
calls `loadSidecar(url)` on `trackchange`.

## Develop

```sh
npm install
npm run dev
```

Opens at `http://localhost:5173/hysteresis/`. This is a local dev harness
only (`src/main.ts`) — a bare file picker exercising the real `init()` API,
not what ships. Building the actual package is `npm run build:lib`.

## Build

```sh
npm run build:lib   # the package: dist/index.js + dist/index.d.ts + dist/worklets/
npm run build       # the local dev-harness demo site (GitHub Pages)
npm run preview
```

`vite.config.ts` sets `base: '/hysteresis/'` to match the demo's GitHub
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
