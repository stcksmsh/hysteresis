import type { ParamBus } from '../../../shared/types'

export interface SceneContext {
  gl: WebGL2RenderingContext
  width: number
  height: number
  dpr: number
  reducedMotion: boolean
  floatFbo: boolean
}

// The only thing a scene ever sees is a ParamBus (choreographed, spring-
// driven output) — never raw audio, never Layer 1/2 internals, with the one
// deliberate exception of ParamBus.scope (the oscilloscope beam's waveform
// trace, HYSTERESIS.md §4b). This is what lets an alternate scene (e.g. the
// Mandelbulb hero) get added without touching anything upstream.
export interface Scene {
  readonly id: string
  // Does this scene want the generic persistence/feedback pass applied to
  // its output, for trail/glow memory? The Julia scene's own `c` already
  // carries frame-to-frame state on its own, so it opts out by default.
  // Not `readonly` literals: a scene may want to change this at runtime.
  readonly wantsPersistencePass: boolean
  readonly wantsBloom: boolean

  init(ctx: SceneContext): void
  resize(ctx: SceneContext): void
  update(dt: number, params: ParamBus): void
  render(targetFbo: WebGLFramebuffer | null): void
  dispose(): void

  // Optional adaptive-quality hooks. The render worker drives these from
  // measured frame time; scenes that have no cost to trade can omit them.
  // `scale` is a 0..1 multiplier on per-frame simulation work (cheap, no
  // reallocation); `setSimMaxEdge` changes internal buffer resolution and
  // may reset scene state, so the worker uses it sparingly.
  setQuality?(scale: number): void
  setSimMaxEdge?(maxEdge: number): void

  // Host accent color (HYSTERESIS.md §7's setAccent), forwarded as linear
  // 0..1 RGB — parsing the host's CSS color string happens on the main
  // thread (src/index.ts), not in the worker.
  setAccent?(rgb: [number, number, number]): void
}
