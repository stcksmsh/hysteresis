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
}

const NOISE_SIZE = 128
const FLOW_SCALE = 2.5 // spatial frequency of the curl sample relative to screen UV
const FLOW_DRIFT_SPEED = 0.04 // noise-sample drift per second, at flowStrength's groove baseline (1)
const FOLD_MIN = 1
const FOLD_MAX = 7
const MIRROR_ONSET = 0.1 // symmetry has to clear this floor before any fold blends in at all

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
    this.flowUvX = (this.flowUvX + drift * dt * 0.7) % 1000
    this.flowUvY = (this.flowUvY + drift * dt * 0.31) % 1000

    const symmetry = clamp01(params.symmetry)
    const foldCount = FOLD_MIN + (FOLD_MAX - FOLD_MIN) * symmetry
    const mirrorStrength = clamp01((symmetry - MIRROR_ONSET) / (1 - MIRROR_ONSET))

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
    gl.uniform1f(this.uniforms.uFoldCount, foldCount)
    gl.uniform1f(this.uniforms.uMirrorStrength, mirrorStrength)

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
