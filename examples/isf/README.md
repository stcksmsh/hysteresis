# Example ISF / `.hyst` shaders

Real, working shaders demonstrating this repo's ISF importer and its
`.hyst` extensions (`hysteresisSignal` inputs, `HYSTERESIS_VERSION`'s real
multi-pass `PASSES`/`resource` inputs) — see [../../docs/isf-shaders.md](../../docs/isf-shaders.md)
for the full format reference.

- **`julia.hyst`** — a self-contained port of the built-in Julia scene
  (`src/render/worker/scenes/julia/`): the same Mandelbrot-cardioid-boundary
  Julia set math (`boundary.ts`'s `cardioidPoint`), driven live by 7
  `hysteresisSignal` inputs (`buildWindup`/`energy`/`tension`/`suspension`/
  `dropImpulse`/`centroid`/`beatPulse`), plus the real oscilloscope beam as
  a `lineTrace` pass — not a bolted-on overlay, a real part of the shader's
  own composited output. Not full parity with the built-in scene: it has no
  autopilot navigation (vortex-search, perturbation-orbit deep zoom) — that
  needs the still-unbuilt `HYSTERESIS_SCRIPT` stateful-script engine.
  θ/zoom are closed-form functions of `TIME` that live signals nudge
  directly instead.

Load one via the patchbay editor's **Load .fs shader…** picker (it accepts
`.hyst` files too — the extension is a naming convention, not something the
parser checks), or pass `--isf examples/isf/julia.hyst` to
`npm run render-video` for an offline render.
