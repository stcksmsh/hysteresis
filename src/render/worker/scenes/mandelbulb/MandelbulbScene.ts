import type { Scene, SceneContext } from '../Scene'
import { createProgram } from '../../gl/program'
import { createFullscreenQuad, drawFullscreenQuad } from '../../gl/fullscreen-quad'
import fullscreenVertSrc from '../../gl/fullscreen.vert.glsl?raw'
import fragSrc from './shaders/mandelbulb.frag.glsl?raw'
import type { ParamBus } from '../../../../shared/types'

const BASE_POWER = 8
const BUILD_POWER_GAIN = 1.5
const ROTATION_SPEED_BASE = 0.06
const ROTATION_SPEED_WINDUP_GAIN = 0.25
const FULL_STEPS = 160
const CHEAP_STEPS = 70

interface Uniforms {
  uAspect: WebGLUniformLocation | null
  uPower: WebGLUniformLocation | null
  uRotation: WebGLUniformLocation | null
  uAccent: WebGLUniformLocation | null
  uMaxSteps: WebGLUniformLocation | null
}

// Optional landing-view hero (HYSTERESIS.md §4c) — NOT part of the default
// persistent-background registry entry. Raymarching is too expensive to run
// always-on; a host that wants this needs to swap it in for a dedicated
// landing canvas and pause it off-screen itself (IntersectionObserver is a
// DOM/host concern, out of scope per §10 — see Scene.setQuality for the only
// cost lever this repo exposes: reduced march steps).
export class MandelbulbScene implements Scene {
  readonly id = 'mandelbulb-hero'
  readonly wantsPersistencePass = false
  readonly wantsBloom = true

  private gl!: WebGL2RenderingContext
  private program!: WebGLProgram
  private quad!: WebGLVertexArrayObject
  private uniforms!: Uniforms

  private width = 0
  private height = 0
  private aspect = 1
  private accent: [number, number, number] = [1, 0.36, 0.22]
  private rotation = 0
  private maxSteps = FULL_STEPS
  private qualityScale = 1
  private power = BASE_POWER

  init(ctx: SceneContext): void {
    this.gl = ctx.gl
    this.program = createProgram(ctx.gl, fullscreenVertSrc, fragSrc)
    this.quad = createFullscreenQuad(ctx.gl)
    this.uniforms = {
      uAspect: this.gl.getUniformLocation(this.program, 'uAspect'),
      uPower: this.gl.getUniformLocation(this.program, 'uPower'),
      uRotation: this.gl.getUniformLocation(this.program, 'uRotation'),
      uAccent: this.gl.getUniformLocation(this.program, 'uAccent'),
      uMaxSteps: this.gl.getUniformLocation(this.program, 'uMaxSteps'),
    }
    this.resize(ctx)
  }

  resize(ctx: SceneContext): void {
    this.width = ctx.width
    this.height = ctx.height
    this.aspect = ctx.width / Math.max(1, ctx.height)
  }

  setQuality(scale: number): void {
    this.qualityScale = Math.max(0.15, Math.min(1, scale))
    this.maxSteps = Math.round((CHEAP_STEPS + (FULL_STEPS - CHEAP_STEPS) * this.qualityScale))
  }

  setAccent(rgb: [number, number, number]): void {
    this.accent = rgb
  }

  update(dt: number, params: ParamBus): void {
    this.power = BASE_POWER + BUILD_POWER_GAIN * params.windup
    const speed = ROTATION_SPEED_BASE + ROTATION_SPEED_WINDUP_GAIN * params.windup
    this.rotation += dt * speed
  }

  render(targetFbo: WebGLFramebuffer | null): void {
    const gl = this.gl
    gl.bindFramebuffer(gl.FRAMEBUFFER, targetFbo)
    gl.viewport(0, 0, this.width, this.height)
    gl.useProgram(this.program)
    gl.uniform1f(this.uniforms.uAspect, this.aspect)
    gl.uniform1f(this.uniforms.uPower, this.power)
    gl.uniform1f(this.uniforms.uRotation, this.rotation)
    gl.uniform3f(this.uniforms.uAccent, this.accent[0], this.accent[1], this.accent[2])
    gl.uniform1i(this.uniforms.uMaxSteps, this.maxSteps)
    drawFullscreenQuad(gl, this.quad)
  }

  dispose(): void {
    const gl = this.gl
    gl.deleteProgram(this.program)
    gl.deleteVertexArray(this.quad)
  }
}
