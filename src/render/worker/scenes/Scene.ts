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
  // memory feedback, so it opts out; a memoryless scene (particles etc.)
  // would opt in for trail/glow memory.
  readonly wantsPersistencePass: boolean
  readonly wantsBloom: boolean

  init(ctx: SceneContext): void
  resize(ctx: SceneContext): void
  update(dt: number, params: ParamBus): void
  render(targetFbo: WebGLFramebuffer | null): void
  dispose(): void
}
