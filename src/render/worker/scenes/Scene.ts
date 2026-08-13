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
// trace, SINTEZA_VIZ.md §4b). This is what lets an alternate scene (e.g. the
// Mandelbulb hero) get added without touching anything upstream.
export interface Scene {
  readonly id: string
  // Does this scene want the generic persistence/feedback pass applied to
  // its output, for trail/glow memory? The Julia scene's own `c` already
  // carries frame-to-frame state on its own, so it opts out by default.
  // Not `readonly` literals: a scene may want to change this at runtime.
  readonly wantsPersistencePass: boolean
  // THE signature layer (SINTEZA_VIZ.md §4b): curl-noise-advected feedback
  // ping-pong buffer, mutually exclusive with wantsPersistencePass in
  // practice (a scene picks one memory mechanism, not both). Raymarched
  // scenes (e.g. the Mandelbulb landing hero) opt out — running an already-
  // expensive raymarch through an extra feedback pass isn't worth it for a
  // one-off foreground hero that was never meant to be the persistent field.
  readonly wantsMemoryField: boolean
  readonly wantsBloom: boolean

  init(ctx: SceneContext): void
  resize(ctx: SceneContext): void
  update(dt: number, params: ParamBus): void
  render(targetFbo: WebGLFramebuffer | null): void
  // Optional foreground layer, for scenes with wantsMemoryField=true that
  // want a sharp element on top of the smeared result — drawn additively
  // (no clear) by the render worker AFTER the memory field pass, so it
  // reads crisp against the softened substrate instead of getting pre-mixed
  // into it every frame (SINTEZA_VIZ.md §4c: the beam is rhythm — sharp,
  // thin — the substrate is mood — slow, smeared; they need to read as
  // different bands of the image). Scenes without a foreground layer, or
  // that don't use the memory field, just omit this.
  renderForeground?(targetFbo: WebGLFramebuffer | null): void
  dispose(): void

  // Optional adaptive-quality hooks. The render worker drives these from
  // measured frame time; scenes that have no cost to trade can omit them.
  // `scale` is a 0..1 multiplier on per-frame simulation work (cheap, no
  // reallocation); `setSimMaxEdge` changes internal buffer resolution and
  // may reset scene state, so the worker uses it sparingly.
  setQuality?(scale: number): void
  setSimMaxEdge?(maxEdge: number): void

  // Host accent color (SINTEZA_VIZ.md §7's setAccent), forwarded as linear
  // 0..1 RGB — parsing the host's CSS color string happens on the main
  // thread (src/index.ts), not in the worker.
  setAccent?(rgb: [number, number, number]): void

  // Host toggle for the idle-state oscilloscope figure (SINTEZA_VIZ.md
  // §4c's Lissajous beam) — some hosts find its constant motion distracting
  // against the rest of a page when no track is playing. Scenes without an
  // idle beam just omit this.
  setShowIdleBeam?(value: boolean): void
}
