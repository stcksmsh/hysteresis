import type { Scene, SceneContext } from '../Scene'
import { createFbo, deleteFbo, type Fbo } from '../../gl/fbo'
import { createProgram } from '../../gl/program'
import { createFullscreenQuad, drawFullscreenQuad } from '../../gl/fullscreen-quad'
import { createNoiseTexture } from '../../gl/noise-texture'
import fullscreenVertSrc from '../../gl/fullscreen.vert.glsl?raw'
import simFragSrc from './shaders/rd-sim.frag.glsl?raw'
import renderFragSrc from './shaders/rd-render.frag.glsl?raw'
import seedFragSrc from './shaders/rd-seed.frag.glsl?raw'
import injectFragSrc from './shaders/rd-inject.frag.glsl?raw'
import type { BandEnergies, ParamBus } from '../../../../shared/types'

// Baseline sits in the self-replicating "worms/mitosis" neighbourhood rather
// than the stable-spots regime — the latter converges and visibly stops. The
// build interpolates toward an even more unstable point.
const BASE_FEED = 0.037
const BASE_KILL = 0.059
const BUILD_FEED = 0.03
const BUILD_KILL = 0.056

// A drop shifts the regime rather than resetting it. A large excursion here
// (v1 used 0.09, >3x baseline) wipes the pattern and reads as a restart.
const RELEASE_FEED = 0.046
const RELEASE_KILL = 0.056
const RELEASE_DECAY_SEC = 0.35

// Spatial feed/kill spread. Widened by windup so a build visibly loads:
// more of the field is pushed toward unstable regimes at once.
// Kept deliberately narrow. Wide spatial spread pushes regions out of the
// pattern-forming band entirely and the field turns to smooth mush — it
// measures as "more motion" while looking strictly worse.
const FEED_RANGE = 0.005
const KILL_RANGE = 0.0035
const RANGE_WINDUP_GAIN = 0.5

// Drift rate is the always-on "flow" and it has to be fast enough to matter:
// the noise texture holds 4 lattice cells, so at 0.05 uv/sec the feed/kill
// field sweeps one cell every ~5s — slow enough that structure can form and
// track it, fast enough that the field never reaches equilibrium. (An early
// value of 0.004 was ~60s per cell, which measured as no better than a
// static field.)
const NOISE_SCALE = 1.4
const NOISE_DRIFT_BASE = 0.05
const NOISE_DRIFT_ENERGY_GAIN = 0.05

// Advection is the primary motion source: it transports the pattern along a
// curl-noise flow, so shapes visibly travel and swirl while keeping their
// crisp edges. Modulating the chemistry instead produces motion only by
// dissolving structure, which measures as "moving" but looks like mush.
// Applied on the first substep of each frame only. Every advected substep
// costs a bilinear resample, and that interpolation blur accumulates — at
// 4-12 substeps/frame it smears the sharp reaction fronts away faster than
// they can reform. One transport per frame keeps the same net flow speed for
// a fraction of the numerical diffusion.
const FLOW_SCALE = 0.8
const ADVECT_BASE = 0.12 // texels per frame
const ADVECT_ENERGY_GAIN = 0.2
const ADVECT_WINDUP_GAIN = 0.4
const ADVECT_SUSPENSION_SCALE = 0.25 // a break should feel held, not flowing

const DIFF_U = 1.0
const DIFF_V = 0.5
const TENSION_DIFFUSION_SCALE = 0.3 // break/suspension: field visibly freezes/holds
const SUB_DIFFUSION_GAIN = 0.15

// Per-beat breathing, felt as an undercurrent rather than a strobe.
const BEAT_FEED_PULSE = 0.0025
const BEAT_PULSE_SHARPNESS = 4

// Per-hit values are much smaller than when a single global onset fired a
// couple of times a second: per-band detection produces ~35 hits/sec, and at
// the old strength that floods the field with V and washes it out.
const ONSET_RADIUS = 0.032
const ONSET_STRENGTH = 0.11

// Onset placement: dominant band -> height, stereo pan -> left/right.
// Ranges stay inside the frame so hits never clip against an edge.
const TONE_Y_MIN = 0.14
const TONE_Y_MAX = 0.86
const PAN_X_SPREAD = 0.34
const PLACEMENT_JITTER_X = 0.14
const PLACEMENT_JITTER_Y = 0.05
const DROP_SITE_COUNT = 3
const DROP_RADIUS = 0.22
const DROP_STRENGTH = 0.55

const MAX_SITES = 16

const BASE_SUBSTEPS = 4
const BUILD_MAX_SUBSTEPS = 12
const TENSION_MIN_SUBSTEPS = 1
const DT = 1.0

// The pattern is inherently smooth/low-frequency — it doesn't need per-pixel
// simulation fidelity at display resolution. Simulating at a capped
// resolution and letting the render pass upscale (LINEAR-filtered) keeps
// per-substep cost roughly constant regardless of display/DPR, which matters
// since this scene runs the sim loop many times per rendered frame.
const DEFAULT_SIM_MAX_EDGE = 420

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * Math.max(0, Math.min(1, t))
}

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v))
}

function hash01(n: number): number {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453123
  return x - Math.floor(x)
}

interface SimUniforms {
  uState: WebGLUniformLocation | null
  uNoiseTex: WebGLUniformLocation | null
  uTexel: WebGLUniformLocation | null
  uFeed: WebGLUniformLocation | null
  uKill: WebGLUniformLocation | null
  uDiffU: WebGLUniformLocation | null
  uDiffV: WebGLUniformLocation | null
  uDt: WebGLUniformLocation | null
  uNoiseScale: WebGLUniformLocation | null
  uNoiseDrift: WebGLUniformLocation | null
  uFeedRange: WebGLUniformLocation | null
  uKillRange: WebGLUniformLocation | null
  uAdvect: WebGLUniformLocation | null
  uFlowScale: WebGLUniformLocation | null
}

interface RenderUniforms {
  uState: WebGLUniformLocation | null
  uHueShift: WebGLUniformLocation | null
  uPaletteMix: WebGLUniformLocation | null
  uStyle: WebGLUniformLocation | null
}

interface SeedUniforms {
  uSeedPhase: WebGLUniformLocation | null
  uStrength: WebGLUniformLocation | null
}

interface InjectUniforms {
  uSites: WebGLUniformLocation | null
  uSiteRadius: WebGLUniformLocation | null
  uSiteStrength: WebGLUniformLocation | null
  uSiteCount: WebGLUniformLocation | null
  uAspect: WebGLUniformLocation | null
}

interface Site {
  x: number
  y: number
  radius: number
  strength: number
}

export type RdStyle = 'organic' | 'graphic'

export class ReactionDiffusionScene implements Scene {
  readonly id: string
  readonly wantsPersistencePass = false
  // The graphic style deliberately skips bloom: the blur is a large part of
  // what makes the organic variant read as soft and washed out.
  readonly wantsBloom: boolean
  private readonly style: RdStyle

  constructor(style: RdStyle = 'organic') {
    this.style = style
    this.id = style === 'graphic' ? 'reaction-diffusion-graphic' : 'reaction-diffusion'
    this.wantsBloom = style === 'organic'
  }

  private gl!: WebGL2RenderingContext
  private simProgram!: WebGLProgram
  private renderProgram!: WebGLProgram
  private seedProgram!: WebGLProgram
  private injectProgram!: WebGLProgram
  private quad!: WebGLVertexArrayObject
  private noiseTexture!: WebGLTexture
  private simUniforms!: SimUniforms
  private renderUniforms!: RenderUniforms
  private seedUniforms!: SeedUniforms
  private injectUniforms!: InjectUniforms

  private front!: Fbo
  private back!: Fbo
  private width = 0 // full display resolution — used for render()'s viewport
  private height = 0
  private simWidth = 0 // capped sim resolution — used for update()'s sim passes
  private simHeight = 0
  private useFloat = false
  private simMaxEdge = DEFAULT_SIM_MAX_EDGE

  private releaseAge = Infinity
  private hueShift = 0
  private paletteMix = 0
  private reducedMotion = false
  private driftX = 0
  private driftY = 0
  private onsetCounter = 0
  private qualityScale = 1

  private pendingSites: Site[] = []
  private siteXY = new Float32Array(MAX_SITES * 2)
  private siteRadii = new Float32Array(MAX_SITES)
  private siteStrengths = new Float32Array(MAX_SITES)

  init(ctx: SceneContext): void {
    this.gl = ctx.gl
    this.useFloat = ctx.floatFbo
    this.reducedMotion = ctx.reducedMotion
    this.simProgram = createProgram(ctx.gl, fullscreenVertSrc, simFragSrc)
    this.renderProgram = createProgram(ctx.gl, fullscreenVertSrc, renderFragSrc)
    this.seedProgram = createProgram(ctx.gl, fullscreenVertSrc, seedFragSrc)
    this.injectProgram = createProgram(ctx.gl, fullscreenVertSrc, injectFragSrc)
    this.quad = createFullscreenQuad(ctx.gl)
    this.noiseTexture = createNoiseTexture(ctx.gl)
    this.cacheUniforms()
    this.allocate(ctx.width, ctx.height)
  }

  resize(ctx: SceneContext): void {
    this.reducedMotion = ctx.reducedMotion
    this.allocate(ctx.width, ctx.height)
  }

  // Substep count scales directly with this — the cheapest quality lever,
  // since it needs no reallocation and no visual discontinuity.
  setQuality(scale: number): void {
    this.qualityScale = Math.max(0.15, Math.min(1, scale))
  }

  // Lets the render worker trade simulation resolution for frame time on
  // weak/software renderers without the scene needing to know why.
  setSimMaxEdge(maxEdge: number): void {
    if (maxEdge === this.simMaxEdge) return
    this.simMaxEdge = maxEdge
    this.allocate(this.width, this.height)
  }

  update(dt: number, params: ParamBus): void {
    const gl = this.gl
    const build = params.buildProgress
    const suspension = Math.max(params.tension, params.suspension)
    this.hueShift = params.hueShift
    this.paletteMix = params.paletteMix

    this.queueMusicSites(params)

    if (params.dropTrigger?.active) {
      this.queueDropSites(params.dropTrigger.strength)
      this.releaseAge = 0
    } else {
      this.releaseAge += dt
    }

    if (this.pendingSites.length > 0) {
      this.runInjectPass(this.front, this.pendingSites)
      this.pendingSites.length = 0
    }

    // Always-on drift: this is what keeps the field flowing even in a
    // passage with no onsets at all.
    const driftSpeed = NOISE_DRIFT_BASE + NOISE_DRIFT_ENERGY_GAIN * params.energy
    this.driftX = (this.driftX + dt * driftSpeed) % 1
    this.driftY = (this.driftY + dt * driftSpeed * 0.6) % 1

    const releaseBlend = Math.exp(-this.releaseAge / RELEASE_DECAY_SEC)
    const beatPulse = Math.exp(-params.beatPhase * BEAT_PULSE_SHARPNESS)
    const beatFeed = BEAT_FEED_PULSE * beatPulse * (0.3 + 0.7 * params.bands.sub)

    const feed = lerp(lerp(BASE_FEED, BUILD_FEED, build), RELEASE_FEED, releaseBlend) + beatFeed
    const kill = lerp(lerp(BASE_KILL, BUILD_KILL, build), RELEASE_KILL, releaseBlend)

    const rangeGain = 1 + params.windup * RANGE_WINDUP_GAIN
    const feedRange = FEED_RANGE * rangeGain
    const killRange = KILL_RANGE * rangeGain

    const diffScale = lerp(1, TENSION_DIFFUSION_SCALE, suspension) * (1 + SUB_DIFFUSION_GAIN * params.bands.sub)
    const diffU = DIFF_U * diffScale
    const diffV = DIFF_V * diffScale

    const maxSubsteps = this.reducedMotion ? Math.round(BUILD_MAX_SUBSTEPS / 2) : BUILD_MAX_SUBSTEPS
    const builtSubsteps = lerp(BASE_SUBSTEPS, maxSubsteps, build)
    const shapedSubsteps = lerp(builtSubsteps, TENSION_MIN_SUBSTEPS, suspension) * this.qualityScale
    const substeps = Math.max(TENSION_MIN_SUBSTEPS, Math.round(shapedSubsteps))

    gl.useProgram(this.simProgram)
    gl.viewport(0, 0, this.simWidth, this.simHeight)
    gl.uniform1f(this.simUniforms.uFeed, feed)
    gl.uniform1f(this.simUniforms.uKill, kill)
    gl.uniform1f(this.simUniforms.uDiffU, diffU)
    gl.uniform1f(this.simUniforms.uDiffV, diffV)
    gl.uniform1f(this.simUniforms.uDt, DT)
    gl.uniform2f(this.simUniforms.uTexel, 1 / this.simWidth, 1 / this.simHeight)
    gl.uniform1f(this.simUniforms.uNoiseScale, NOISE_SCALE)
    gl.uniform2f(this.simUniforms.uNoiseDrift, this.driftX, this.driftY)
    gl.uniform1f(this.simUniforms.uFeedRange, feedRange)
    gl.uniform1f(this.simUniforms.uKillRange, killRange)

    const advect =
      (ADVECT_BASE + ADVECT_ENERGY_GAIN * params.energy + ADVECT_WINDUP_GAIN * params.windup) *
      lerp(1, ADVECT_SUSPENSION_SCALE, suspension)
    gl.uniform1f(this.simUniforms.uFlowScale, FLOW_SCALE)

    gl.activeTexture(gl.TEXTURE1)
    gl.bindTexture(gl.TEXTURE_2D, this.noiseTexture)
    gl.uniform1i(this.simUniforms.uNoiseTex, 1)
    gl.uniform1i(this.simUniforms.uState, 0)
    gl.activeTexture(gl.TEXTURE0)

    for (let i = 0; i < substeps; i++) {
      // Transport happens on the first substep only; the rest are pure
      // reaction-diffusion, which lets the fronts re-sharpen after the move.
      gl.uniform1f(this.simUniforms.uAdvect, i === 0 ? advect : 0)
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.back.framebuffer)
      gl.bindTexture(gl.TEXTURE_2D, this.front.texture)
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
    gl.uniform1i(this.renderUniforms.uStyle, this.style === 'graphic' ? 1 : 0)
    drawFullscreenQuad(gl, this.quad)
  }

  dispose(): void {
    const gl = this.gl
    deleteFbo(gl, this.front)
    deleteFbo(gl, this.back)
    gl.deleteTexture(this.noiseTexture)
    gl.deleteProgram(this.simProgram)
    gl.deleteProgram(this.renderProgram)
    gl.deleteProgram(this.seedProgram)
    gl.deleteProgram(this.injectProgram)
    gl.deleteVertexArray(this.quad)
  }

  // One injection site per onset, placed where the hit actually sits in the
  // mix: its dominant band sets the height (a kick lands low, a hi-hat high)
  // and its stereo position sets left/right. A small deterministic jitter
  // keeps repeated identical hits from stacking on exactly one pixel.
  private queueMusicSites(params: ParamBus): void {
    for (const pulse of params.onsetPulses) {
      if (this.pendingSites.length >= MAX_SITES) break
      const i = this.onsetCounter++
      const jitterX = (hash01(i * 2) - 0.5) * PLACEMENT_JITTER_X
      const jitterY = (hash01(i * 2 + 1) - 0.5) * PLACEMENT_JITTER_Y
      // vUv y=0 is the bottom of the field, so low tone -> low on screen.
      const y = lerp(TONE_Y_MIN, TONE_Y_MAX, pulse.tone) + jitterY
      const x = 0.5 + pulse.pan * PAN_X_SPREAD + jitterX
      this.pendingSites.push({
        x: clamp01(x),
        y: clamp01(y),
        radius: ONSET_RADIUS * (0.7 + 0.6 * pulse.strength),
        strength: ONSET_STRENGTH * (0.5 + 0.5 * pulse.strength),
      })
    }
  }

  // A few large sites rather than a global spray: the surrounding structure
  // survives, so the drop reads as a rupture of what was there rather than
  // a fresh start.
  private queueDropSites(strength: number): void {
    for (let n = 0; n < DROP_SITE_COUNT; n++) {
      if (this.pendingSites.length >= MAX_SITES) break
      const i = this.onsetCounter++
      this.pendingSites.push({
        x: 0.2 + 0.6 * hash01(i * 3),
        y: 0.2 + 0.6 * hash01(i * 3 + 1),
        radius: DROP_RADIUS * (0.8 + 0.4 * strength),
        strength: DROP_STRENGTH * (0.6 + 0.4 * strength),
      })
    }
  }

  private brightnessBias(bands: BandEnergies): number {
    return clamp01(bands.air + bands.presence - bands.sub)
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
    const simScale = longEdge > this.simMaxEdge ? this.simMaxEdge / longEdge : 1
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

  // Global scatter — only correct for initialisation/resize, never for
  // music events (that is what runInjectPass is for).
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

  private runInjectPass(target: Fbo, sites: Site[]): void {
    const gl = this.gl
    const count = Math.min(sites.length, MAX_SITES)
    for (let i = 0; i < count; i++) {
      const site = sites[i]
      this.siteXY[i * 2] = site.x
      this.siteXY[i * 2 + 1] = site.y
      this.siteRadii[i] = site.radius
      this.siteStrengths[i] = site.strength
    }

    gl.bindFramebuffer(gl.FRAMEBUFFER, target.framebuffer)
    gl.viewport(0, 0, target.width, target.height)
    gl.enable(gl.BLEND)
    gl.blendFunc(gl.ONE, gl.ONE)
    gl.useProgram(this.injectProgram)
    gl.uniform2fv(this.injectUniforms.uSites, this.siteXY)
    gl.uniform1fv(this.injectUniforms.uSiteRadius, this.siteRadii)
    gl.uniform1fv(this.injectUniforms.uSiteStrength, this.siteStrengths)
    gl.uniform1i(this.injectUniforms.uSiteCount, count)
    gl.uniform1f(this.injectUniforms.uAspect, target.width / Math.max(1, target.height))
    drawFullscreenQuad(gl, this.quad)
    gl.disable(gl.BLEND)
  }

  private cacheUniforms(): void {
    const gl = this.gl
    this.simUniforms = {
      uState: gl.getUniformLocation(this.simProgram, 'uState'),
      uNoiseTex: gl.getUniformLocation(this.simProgram, 'uNoiseTex'),
      uTexel: gl.getUniformLocation(this.simProgram, 'uTexel'),
      uFeed: gl.getUniformLocation(this.simProgram, 'uFeed'),
      uKill: gl.getUniformLocation(this.simProgram, 'uKill'),
      uDiffU: gl.getUniformLocation(this.simProgram, 'uDiffU'),
      uDiffV: gl.getUniformLocation(this.simProgram, 'uDiffV'),
      uDt: gl.getUniformLocation(this.simProgram, 'uDt'),
      uNoiseScale: gl.getUniformLocation(this.simProgram, 'uNoiseScale'),
      uNoiseDrift: gl.getUniformLocation(this.simProgram, 'uNoiseDrift'),
      uFeedRange: gl.getUniformLocation(this.simProgram, 'uFeedRange'),
      uKillRange: gl.getUniformLocation(this.simProgram, 'uKillRange'),
      uAdvect: gl.getUniformLocation(this.simProgram, 'uAdvect'),
      uFlowScale: gl.getUniformLocation(this.simProgram, 'uFlowScale'),
    }
    this.renderUniforms = {
      uState: gl.getUniformLocation(this.renderProgram, 'uState'),
      uHueShift: gl.getUniformLocation(this.renderProgram, 'uHueShift'),
      uPaletteMix: gl.getUniformLocation(this.renderProgram, 'uPaletteMix'),
      uStyle: gl.getUniformLocation(this.renderProgram, 'uStyle'),
    }
    this.seedUniforms = {
      uSeedPhase: gl.getUniformLocation(this.seedProgram, 'uSeedPhase'),
      uStrength: gl.getUniformLocation(this.seedProgram, 'uStrength'),
    }
    this.injectUniforms = {
      uSites: gl.getUniformLocation(this.injectProgram, 'uSites[0]'),
      uSiteRadius: gl.getUniformLocation(this.injectProgram, 'uSiteRadius[0]'),
      uSiteStrength: gl.getUniformLocation(this.injectProgram, 'uSiteStrength[0]'),
      uSiteCount: gl.getUniformLocation(this.injectProgram, 'uSiteCount'),
      uAspect: gl.getUniformLocation(this.injectProgram, 'uAspect'),
    }
  }
}
