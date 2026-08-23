import { createFbo, deleteFbo, type Fbo } from '../gl/fbo'
import { createProgram } from '../gl/program'
import { createFullscreenQuad, drawFullscreenQuad } from '../gl/fullscreen-quad'
import { createNoiseTexture } from '../gl/noise-texture'
import vertSrc from '../gl/fullscreen.vert.glsl?raw'
import fragSrc from './memory-field.frag.glsl?raw'

export interface MemoryFieldParams {
  decay: number
  flowStrength: number
  symmetry: number // 0..1 — converted to fold count + mirror strength here
  aspect: number
  // SINTEZA_SIGNAL_BUS.md §4.1 groove reactivity: bipolar -1..1, biases the
  // curl-noise drift axis toward one component of the flow so a low-heavy
  // vs. high-heavy mix visibly flows differently, not just faster/slower.
  // Optional/defaults to 0 (today's fixed axis) for any caller that doesn't
  // pass it.
  flowDirection?: number
}

const NOISE_SIZE = 128
const FLOW_SCALE = 2.5 // spatial frequency of the curl sample relative to screen UV
const FLOW_DRIFT_SPEED = 0.04 // noise-sample drift per second, at flowStrength's groove baseline (1)
// Wedge count used to be interpolated with symmetry (1 fold at rest, up to
// 7 at full strength) — but the wedge boundaries are angle-anchored at
// theta=0, so a *changing* fold count visibly slides/rotates the mirrored
// copies against each other as symmetry rises and falls. That's the "spin"
// during a drop: not intentional motion, just the wedge geometry itself
// changing shape every frame. Fixed at a single count instead, so only
// uMirrorStrength (a plain blend, no geometry change) responds to symmetry.
const FOLD_COUNT = 6
const MIRROR_ONSET = 0.1 // symmetry has to clear this floor before any fold blends in at all

// This feedback loop's steady-state brightness is cur/(1-decay) — raising
// decay to hold a build/break longer was ALSO multiplying brightness by the
// same factor (up to ~67-200x at the highest decay tiers screen-composites.ts
// uses), well past where the composite pass's Reinhard tonemap crushes all
// contrast into a washed-out mush. Reported as "too bright/psychedelic
// sometimes" — worse exactly during builds/breaks, since that's when decay
// (and separately, symmetry) both rise together off the same signals.
// DECAY_REFERENCE matches screen-composites.ts's FIELD_DECAY_GROOVE (today's
// resting decay) so scaling cur's contribution by (1-decay)/(1-REFERENCE)
// leaves the look at rest completely unchanged, while every higher decay
// tier now holds the SAME steady-state brightness longer instead of a
// brighter one — decoupling "how long it persists" from "how bright it
// gets", which is what was actually wanted.
const DECAY_REFERENCE = 0.86

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v))
}

// THE signature layer (SINTEZA_VIZ.md §4b): each tick the whole scene
// (Julia + beam) is fed back into a ping-pong buffer, advected through a
// curl-noise flow field, and decayed — so the screen becomes a record of
// the last few seconds rather than a snapshot. Earned-symmetry domain warp
// (§4d) folds only the *advection sampling coordinate*, never the fresh
// frame, so the memory can organize without the whole image ever becoming a
// static kaleidoscope. Reuses the baked curl-potential noise texture that
// gl/noise-texture.ts already provides (leftover, unused infra from an
// earlier reaction-diffusion scene) instead of a fresh simulation.
export class MemoryFieldPass {
  private program: WebGLProgram
  private quad: WebGLVertexArrayObject
  private noiseTexture: WebGLTexture
  private front!: Fbo
  private back!: Fbo
  private flowUvX = 0
  private flowUvY = 0

  private uniforms: {
    uCurrent: WebGLUniformLocation | null
    uPrev: WebGLUniformLocation | null
    uNoise: WebGLUniformLocation | null
    uNoiseTexel: WebGLUniformLocation | null
    uDecay: WebGLUniformLocation | null
    uAspect: WebGLUniformLocation | null
    uFlowUv: WebGLUniformLocation | null
    uFlowScale: WebGLUniformLocation | null
    uFlowStrength: WebGLUniformLocation | null
    uFoldCount: WebGLUniformLocation | null
    uMirrorStrength: WebGLUniformLocation | null
    uCurGain: WebGLUniformLocation | null
  }

  constructor(
    private gl: WebGL2RenderingContext,
    width: number,
    height: number,
    private useFloat: boolean,
  ) {
    this.program = createProgram(gl, vertSrc, fragSrc)
    this.quad = createFullscreenQuad(gl)
    this.noiseTexture = createNoiseTexture(gl, NOISE_SIZE)
    this.uniforms = {
      uCurrent: gl.getUniformLocation(this.program, 'uCurrent'),
      uPrev: gl.getUniformLocation(this.program, 'uPrev'),
      uNoise: gl.getUniformLocation(this.program, 'uNoise'),
      uNoiseTexel: gl.getUniformLocation(this.program, 'uNoiseTexel'),
      uDecay: gl.getUniformLocation(this.program, 'uDecay'),
      uAspect: gl.getUniformLocation(this.program, 'uAspect'),
      uFlowUv: gl.getUniformLocation(this.program, 'uFlowUv'),
      uFlowScale: gl.getUniformLocation(this.program, 'uFlowScale'),
      uFlowStrength: gl.getUniformLocation(this.program, 'uFlowStrength'),
      uFoldCount: gl.getUniformLocation(this.program, 'uFoldCount'),
      uMirrorStrength: gl.getUniformLocation(this.program, 'uMirrorStrength'),
      uCurGain: gl.getUniformLocation(this.program, 'uCurGain'),
    }
    this.resize(width, height)
  }

  resize(width: number, height: number): void {
    const gl = this.gl
    if (this.front) deleteFbo(gl, this.front)
    if (this.back) deleteFbo(gl, this.back)
    this.front = createFbo(gl, Math.max(1, width), Math.max(1, height), this.useFloat)
    this.back = createFbo(gl, Math.max(1, width), Math.max(1, height), this.useFloat)
  }

  // Advects/decays the memory buffer, composites `currentTexture` (this
  // frame's Julia+beam render) on top, and returns the resulting Fbo — the
  // caller draws onset particles straight into it (additive) so particles
  // get the same persistence treatment as everything else in the field.
  apply(currentTexture: WebGLTexture, dt: number, params: MemoryFieldParams): Fbo {
    const gl = this.gl

    // The sampled noise region drifts continuously, scaled by flowStrength
    // so the field visibly churns faster when the music is doing more —
    // without this the curl pattern would be static (same vectors every
    // frame, just decaying), never actually "flowing".
    const drift = FLOW_DRIFT_SPEED * Math.max(0, params.flowStrength)
    // flowDirection biases the drift ratio between the two axes rather than
    // introducing a new uniform/shader change — 0 reproduces today's fixed
    // 0.7/0.31 ratio exactly.
    const direction = Math.max(-1, Math.min(1, params.flowDirection ?? 0))
    this.flowUvX = (this.flowUvX + drift * dt * (0.7 + 0.3 * direction)) % 1000
    this.flowUvY = (this.flowUvY + drift * dt * (0.31 - 0.15 * direction)) % 1000

    const symmetry = clamp01(params.symmetry)
    const mirrorStrength = clamp01((symmetry - MIRROR_ONSET) / (1 - MIRROR_ONSET))
    // Clamped to >=0 only — deliberately NOT capped at 1, so a decay lower
    // than DECAY_REFERENCE (none currently exist, but nothing enforces that)
    // would correctly boost cur's contribution rather than silently doing
    // nothing; capping would only hide that case, not prevent it.
    const curGain = Math.max(0, (1 - params.decay) / (1 - DECAY_REFERENCE))

    gl.bindFramebuffer(gl.FRAMEBUFFER, this.back.framebuffer)
    gl.viewport(0, 0, this.back.width, this.back.height)
    gl.useProgram(this.program)

    gl.activeTexture(gl.TEXTURE0)
    gl.bindTexture(gl.TEXTURE_2D, currentTexture)
    gl.uniform1i(this.uniforms.uCurrent, 0)
    gl.activeTexture(gl.TEXTURE1)
    gl.bindTexture(gl.TEXTURE_2D, this.front.texture)
    gl.uniform1i(this.uniforms.uPrev, 1)
    gl.activeTexture(gl.TEXTURE2)
    gl.bindTexture(gl.TEXTURE_2D, this.noiseTexture)
    gl.uniform1i(this.uniforms.uNoise, 2)

    gl.uniform2f(this.uniforms.uNoiseTexel, 1 / NOISE_SIZE, 1 / NOISE_SIZE)
    gl.uniform1f(this.uniforms.uDecay, params.decay)
    gl.uniform1f(this.uniforms.uAspect, params.aspect)
    gl.uniform2f(this.uniforms.uFlowUv, this.flowUvX, this.flowUvY)
    gl.uniform1f(this.uniforms.uFlowScale, FLOW_SCALE)
    // Raw curl-gradient samples are already small (baked fbm varies gently
    // texel-to-texel), so flowStrength can act as a direct multiplier
    // without a separate free scale constant here.
    gl.uniform1f(this.uniforms.uFlowStrength, params.flowStrength * 0.02)
    gl.uniform1f(this.uniforms.uFoldCount, FOLD_COUNT)
    gl.uniform1f(this.uniforms.uMirrorStrength, mirrorStrength)
    gl.uniform1f(this.uniforms.uCurGain, curGain)

    drawFullscreenQuad(gl, this.quad)

    const tmp = this.front
    this.front = this.back
    this.back = tmp
    return this.front
  }

  dispose(): void {
    const gl = this.gl
    deleteFbo(gl, this.front)
    deleteFbo(gl, this.back)
    gl.deleteProgram(this.program)
    gl.deleteVertexArray(this.quad)
    gl.deleteTexture(this.noiseTexture)
  }
}
