# HYSTERESIS

A browser-based music visualizer that reacts to musical *structure* — builds,
drops, breaks, groove — instead of instantaneous amplitude. It has memory and
anticipation: it winds up during builds, releases on drops, and goes
suspended during breaks.

Three-layer architecture:

- **Layer 1 (`src/audio/worklet/`)** — feature extraction in an
  `AudioWorklet`: own windowed FFT, perceptual band split (sub/low/mid/
  presence/air), spectral centroid, spectral flatness, spectral-flux novelty.
- **Layer 2 (`src/audio/worklet/brain/`)** — musical state: beat tracking
  (tempo + a phase-locked oscillator that free-runs through breaks), build
  detector, drop detector, break/tension detector.
- **Layer 3 (`src/render/choreography/`, `src/render/worker/scenes/`)** —
  choreography (spring-damper driven parameters) and the visual scene
  (reaction-diffusion, Gray-Scott), rendered via WebGL2 on an `OffscreenCanvas`
  in a dedicated Worker.

## Develop

```sh
npm install
npm run dev
```

Opens at `http://localhost:5173/hysteresis/`. Drop in an audio file to play +
analyze it. Add `?debug=1` for a live readout of tempo/beat/build/tension/
events, a beat-synced flashing dot, and scene-tuning sliders.

## Build / deploy

```sh
npm run build
npm run preview
```

Deploys automatically to GitHub Pages on push to `main` (see
`.github/workflows/deploy.yml`). `vite.config.ts` sets `base: '/hysteresis/'`
to match the project-pages subpath.

## Test

```sh
npm run typecheck
npm test
```

Unit tests use deterministic synthetic signals (click trains, synthetic
spectra) for CI-verifiable regression coverage of the DSP/detector math.
Perceptual tuning against real audio happens via `?debug=1`, not in CI.

## Notes

- No microphone input — file-load only, so the embedded `<iframe>` demo needs
  no permission prompt.
- The AudioWorklet is bundled separately (`vite.worklet.config.ts`) into
  `public/worklets/feature-worklet.js`, since Vite's `new URL(...)` idiom only
  special-cases `new Worker()`, not `audioWorklet.addModule()`.
