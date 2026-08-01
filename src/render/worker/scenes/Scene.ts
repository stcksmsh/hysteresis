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
// driven output) — never raw audio, never Layer 1/2 internals. This is what
// lets particles/fluid/reactive-geometry get added later as alternate
// scenes without touching anything upstream.
export interface Scene {
  readonly id: string
  // Does this scene want the generic persistence/feedback pass applied to
  // its output? Reaction-diffusion's own ping-pong sim already is long-
  // memory feedback, so it opts out; a memoryless scene (geometry, particles)
  // opts in for trail/glow memory.
  // Not `readonly` literals: variants of one scene differ on these — the
  // graphic reaction-diffusion opts out of bloom to avoid the soft wash.
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
}
