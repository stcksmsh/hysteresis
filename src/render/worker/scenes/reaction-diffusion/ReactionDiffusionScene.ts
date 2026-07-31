import type { Scene, SceneContext } from '../Scene'
import { createFbo, deleteFbo, type Fbo } from '../../gl/fbo'
import { createProgram } from '../../gl/program'
import { createFullscreenQuad, drawFullscreenQuad } from '../../gl/fullscreen-quad'
import fullscreenVertSrc from '../../gl/fullscreen.vert.glsl?raw'
import simFragSrc from './shaders/rd-sim.frag.glsl?raw'
import renderFragSrc from './shaders/rd-render.frag.glsl?raw'
import seedFragSrc from './shaders/rd-seed.frag.glsl?raw'
import type { ParamBus } from '../../../../shared/types'

// Baseline (calm, groove) Gray-Scott regime vs. a more turbulent regime the
// build interpolates toward — Pearson-parameter-space points chosen to sit
// near the "spots -> worms/chaos" boundary so the transition reads visibly.
const BASE_FEED = 0.037
const BASE_KILL = 0.06
const BUILD_FEED = 0.03
const BUILD_KILL = 0.056
const RELEASE_FEED = 0.09
const RELEASE_KILL = 0.045
const RELEASE_DECAY_SEC = 0.5

const DIFF_U = 1.0
const DIFF_V = 0.5
const TENSION_DIFFUSION_SCALE = 0.3 // break/suspension: field visibly freezes/holds

const BASE_SUBSTEPS = 4
const BUILD_MAX_SUBSTEPS = 16
const TENSION_MIN_SUBSTEPS = 1
const DT = 1.0

// The pattern is inherently smooth/low-frequency — it doesn't need per-pixel
// simulation fidelity at display resolution. Simulating at a capped
// resolution and letting the render pass upscale (LINEAR-filtered) keeps
// per-substep cost roughly constant regardless of display/DPR, which matters
// since this scene runs the sim loop up to 16x per rendered frame.
const SIM_MAX_EDGE = 480

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * Math.max(0, Math.min(1, t))
}

interface SimUniforms {
  uState: WebGLUniformLocation | null
  uTexel: WebGLUniformLocation | null
  uFeed: WebGLUniformLocation | null
  uKill: WebGLUniformLocation | null
  uDiffU: WebGLUniformLocation | null
  uDiffV: WebGLUniformLocation | null
  uDt: WebGLUniformLocation | null
}

interface RenderUniforms {
  uState: WebGLUniformLocation | null
  uHueShift: WebGLUniformLocation | null
  uPaletteMix: WebGLUniformLocation | null
}

interface SeedUniforms {
  uSeedPhase: WebGLUniformLocation | null
  uStrength: WebGLUniformLocation | null
}

export class ReactionDiffusionScene implements Scene {
  readonly id = 'reaction-diffusion'
  readonly wantsPersistencePass = false
  readonly wantsBloom = true

  private gl!: WebGL2RenderingContext
  private simProgram!: WebGLProgram
  private renderProgram!: WebGLProgram
  private seedProgram!: WebGLProgram
  private quad!: WebGLVertexArrayObject
  private simUniforms!: SimUniforms
  private renderUniforms!: RenderUniforms
  private seedUniforms!: SeedUniforms

  private front!: Fbo
  private back!: Fbo
  private width = 0 // full display resolution — used for render()'s viewport
  private height = 0
  private simWidth = 0 // capped sim resolution — used for update()'s sim passes
  private simHeight = 0
  private useFloat = false

  private releaseAge = Infinity
  private pendingSeedStrength = 0
  private hueShift = 0
  private paletteMix = 0
  private reducedMotion = false

  init(ctx: SceneContext): void {
    this.gl = ctx.gl
    this.useFloat = ctx.floatFbo
    this.reducedMotion = ctx.reducedMotion
    this.simProgram = createProgram(ctx.gl, fullscreenVertSrc, simFragSrc)
    this.renderProgram = createProgram(ctx.gl, fullscreenVertSrc, renderFragSrc)
    this.seedProgram = createProgram(ctx.gl, fullscreenVertSrc, seedFragSrc)
    this.quad = createFullscreenQuad(ctx.gl)
    this.cacheUniforms()
    this.allocate(ctx.width, ctx.height)
  }

  resize(ctx: SceneContext): void {
    this.reducedMotion = ctx.reducedMotion
    this.allocate(ctx.width, ctx.height)
  }

  update(dt: number, params: ParamBus): void {
    const gl = this.gl
    const build = params.buildProgress
    const suspension = Math.max(params.tension, params.suspension)
    this.hueShift = params.hueShift
    this.paletteMix = params.paletteMix

    if (params.dropTrigger?.active) {
      this.pendingSeedStrength = 0.35 + 0.35 * params.dropTrigger.strength
      this.releaseAge = 0
    } else {
      this.releaseAge += dt
    }

    if (this.pendingSeedStrength > 0) {
      this.runSeedPass(this.front, this.pendingSeedStrength)
      this.pendingSeedStrength = 0
    }

    const releaseBlend = Math.exp(-this.releaseAge / RELEASE_DECAY_SEC)
    const feed = lerp(lerp(BASE_FEED, BUILD_FEED, build), RELEASE_FEED, releaseBlend)
    const kill = lerp(lerp(BASE_KILL, BUILD_KILL, build), RELEASE_KILL, releaseBlend)

    const diffScale = lerp(1, TENSION_DIFFUSION_SCALE, suspension)
    const diffU = DIFF_U * diffScale
    const diffV = DIFF_V * diffScale

    const maxSubsteps = this.reducedMotion ? Math.round(BUILD_MAX_SUBSTEPS / 2) : BUILD_MAX_SUBSTEPS
    const builtSubsteps = lerp(BASE_SUBSTEPS, maxSubsteps, build)
    const substeps = Math.max(TENSION_MIN_SUBSTEPS, Math.round(lerp(builtSubsteps, TENSION_MIN_SUBSTEPS, suspension)))

    gl.useProgram(this.simProgram)
    gl.viewport(0, 0, this.simWidth, this.simHeight)
    gl.uniform1f(this.simUniforms.uFeed, feed)
    gl.uniform1f(this.simUniforms.uKill, kill)
    gl.uniform1f(this.simUniforms.uDiffU, diffU)
    gl.uniform1f(this.simUniforms.uDiffV, diffV)
    gl.uniform1f(this.simUniforms.uDt, DT)
    gl.uniform2f(this.simUniforms.uTexel, 1 / this.simWidth, 1 / this.simHeight)
    gl.activeTexture(gl.TEXTURE0)

    for (let i = 0; i < substeps; i++) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.back.framebuffer)
      gl.bindTexture(gl.TEXTURE_2D, this.front.texture)
      gl.uniform1i(this.simUniforms.uState, 0)
      drawFullscreenQuad(gl, this.quad)
      this.swap()
    }
  }

  render(targetFbo: WebGLFramebuffer | null): void {
    const gl = this.gl
    gl.bindFramebuffer(gl.FRAMEBUFFER, targetFbo)
    gl.viewport(0, 0, this.width, this.height)
    gl.useProgram(this.renderProgram)
    gl.activeTexture(gl.TEXTURE0)
    gl.bindTexture(gl.TEXTURE_2D, this.front.texture)
    gl.uniform1i(this.renderUniforms.uState, 0)
    gl.uniform1f(this.renderUniforms.uHueShift, this.hueShift)
    gl.uniform1f(this.renderUniforms.uPaletteMix, this.paletteMix)
    drawFullscreenQuad(gl, this.quad)
  }

  dispose(): void {
    const gl = this.gl
    deleteFbo(gl, this.front)
    deleteFbo(gl, this.back)
    gl.deleteProgram(this.simProgram)
    gl.deleteProgram(this.renderProgram)
    gl.deleteProgram(this.seedProgram)
    gl.deleteVertexArray(this.quad)
  }

  private swap(): void {
    const tmp = this.front
    this.front = this.back
    this.back = tmp
  }

  private allocate(width: number, height: number): void {
    const gl = this.gl
    if (this.front) deleteFbo(gl, this.front)
    if (this.back) deleteFbo(gl, this.back)
    this.width = Math.max(1, width)
    this.height = Math.max(1, height)

    const longEdge = Math.max(this.width, this.height)
    const simScale = longEdge > SIM_MAX_EDGE ? SIM_MAX_EDGE / longEdge : 1
    this.simWidth = Math.max(1, Math.round(this.width * simScale))
    this.simHeight = Math.max(1, Math.round(this.height * simScale))

    this.front = createFbo(gl, this.simWidth, this.simHeight, this.useFloat)
    this.back = createFbo(gl, this.simWidth, this.simHeight, this.useFloat)
    this.seedBaseline()
  }

  // Reseed to a near-homogeneous baseline plus a small scattered burst — a
  // chaotic field can't be meaningfully resampled to a new resolution, so
  // resize just restarts the pattern rather than trying to preserve it.
  private seedBaseline(): void {
    const gl = this.gl
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.front.framebuffer)
    gl.viewport(0, 0, this.front.width, this.front.height)
    gl.disable(gl.BLEND)
    gl.clearColor(1, 0, 0, 1)
    gl.clear(gl.COLOR_BUFFER_BIT)
    this.runSeedPass(this.front, 0.5)
  }

  private runSeedPass(target: Fbo, strength: number): void {
    const gl = this.gl
    gl.bindFramebuffer(gl.FRAMEBUFFER, target.framebuffer)
    gl.viewport(0, 0, target.width, target.height)
    gl.enable(gl.BLEND)
    gl.blendFunc(gl.ONE, gl.ONE)
    gl.useProgram(this.seedProgram)
    gl.uniform1f(this.seedUniforms.uSeedPhase, Math.random())
    gl.uniform1f(this.seedUniforms.uStrength, strength)
    drawFullscreenQuad(gl, this.quad)
    gl.disable(gl.BLEND)
  }

  private cacheUniforms(): void {
    const gl = this.gl
    this.simUniforms = {
      uState: gl.getUniformLocation(this.simProgram, 'uState'),
      uTexel: gl.getUniformLocation(this.simProgram, 'uTexel'),
      uFeed: gl.getUniformLocation(this.simProgram, 'uFeed'),
      uKill: gl.getUniformLocation(this.simProgram, 'uKill'),
      uDiffU: gl.getUniformLocation(this.simProgram, 'uDiffU'),
      uDiffV: gl.getUniformLocation(this.simProgram, 'uDiffV'),
      uDt: gl.getUniformLocation(this.simProgram, 'uDt'),
    }
    this.renderUniforms = {
      uState: gl.getUniformLocation(this.renderProgram, 'uState'),
      uHueShift: gl.getUniformLocation(this.renderProgram, 'uHueShift'),
      uPaletteMix: gl.getUniformLocation(this.renderProgram, 'uPaletteMix'),
    }
    this.seedUniforms = {
      uSeedPhase: gl.getUniformLocation(this.seedProgram, 'uSeedPhase'),
      uStrength: gl.getUniformLocation(this.seedProgram, 'uStrength'),
    }
  }
}
