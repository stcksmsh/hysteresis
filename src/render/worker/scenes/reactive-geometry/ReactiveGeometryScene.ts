import type { Scene, SceneContext } from '../Scene'
import { createProgram } from '../../gl/program'
import vertSrc from './shaders/geo.vert.glsl?raw'
import fragSrc from './shaders/geo.frag.glsl?raw'
import type { ParamBus } from '../../../../shared/types'

const MAX_SHAPES = 192
const FLOATS_PER_SHAPE = 6 // centerX, centerY, size, age, tone, strength

const LIFETIME_SEC = 0.75
const DROP_LIFETIME_SEC = 1.2

// Placement matches the reaction-diffusion scene so switching between them
// compares like with like: pan drives x, band position drives y.
const TONE_Y_MIN = 0.12
const TONE_Y_MAX = 0.88
const PAN_X_SPREAD = 0.36
const JITTER_X = 0.1
const JITTER_Y = 0.04

// Low hits are physically bigger, which reads as weight.
const SIZE_LOW = 0.17
const SIZE_HIGH = 0.06
const SIZE_STRENGTH_GAIN = 0.5
const WINDUP_SIZE_GAIN = 0.45

const BEAT_PULSE_SIZE = 0.1
const DROP_SIZE = 0.75

interface Shape {
  x: number
  y: number
  size: number
  tone: number
  strength: number
  ageSec: number
  lifetimeSec: number
}

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

// Each musical event becomes one discrete, hard-edged mark that expands and
// fades. Unlike the reaction-diffusion field, individual hits stay countable,
// which is the whole point of this metaphor.
export class ReactiveGeometryScene implements Scene {
  readonly id = 'reactive-geometry'
  // Memoryless per frame, so it opts into the generic trail pass — the one
  // reaction-diffusion skips because its own sim is already a feedback loop.
  readonly wantsPersistencePass = true
  readonly wantsBloom = true

  private gl!: WebGL2RenderingContext
  private program!: WebGLProgram
  private vao!: WebGLVertexArrayObject
  private cornerBuffer!: WebGLBuffer
  private instanceBuffer!: WebGLBuffer
  private uAspect: WebGLUniformLocation | null = null
  private uHueShift: WebGLUniformLocation | null = null

  private shapes: Shape[] = []
  private instanceData = new Float32Array(MAX_SHAPES * FLOATS_PER_SHAPE)
  private width = 1
  private height = 1
  private hueShift = 0
  private counter = 0
  private lastBeatPhase = 0
  private qualityScale = 1

  init(ctx: SceneContext): void {
    const gl = ctx.gl
    this.gl = gl
    this.program = createProgram(gl, vertSrc, fragSrc)
    this.uAspect = gl.getUniformLocation(this.program, 'uAspect')
    this.uHueShift = gl.getUniformLocation(this.program, 'uHueShift')

    const vao = gl.createVertexArray()
    if (!vao) throw new Error('Failed to create VAO')
    this.vao = vao
    gl.bindVertexArray(vao)

    const corners = new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1])
    const cornerBuffer = gl.createBuffer()
    if (!cornerBuffer) throw new Error('Failed to create buffer')
    this.cornerBuffer = cornerBuffer
    gl.bindBuffer(gl.ARRAY_BUFFER, cornerBuffer)
    gl.bufferData(gl.ARRAY_BUFFER, corners, gl.STATIC_DRAW)
    gl.enableVertexAttribArray(0)
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0)

    const instanceBuffer = gl.createBuffer()
    if (!instanceBuffer) throw new Error('Failed to create buffer')
    this.instanceBuffer = instanceBuffer
    gl.bindBuffer(gl.ARRAY_BUFFER, instanceBuffer)
    gl.bufferData(gl.ARRAY_BUFFER, this.instanceData.byteLength, gl.DYNAMIC_DRAW)

    const stride = FLOATS_PER_SHAPE * 4
    const layout: [number, number, number][] = [
      [1, 2, 0], // center
      [2, 1, 8], // size
      [3, 1, 12], // age
      [4, 1, 16], // tone
      [5, 1, 20], // strength
    ]
    for (const [location, size, offset] of layout) {
      gl.enableVertexAttribArray(location)
      gl.vertexAttribPointer(location, size, gl.FLOAT, false, stride, offset)
      gl.vertexAttribDivisor(location, 1)
    }

    gl.bindVertexArray(null)
    this.resize(ctx)
  }

  resize(ctx: SceneContext): void {
    this.width = Math.max(1, ctx.width)
    this.height = Math.max(1, ctx.height)
  }

  setQuality(scale: number): void {
    this.qualityScale = Math.max(0.2, Math.min(1, scale))
  }

  update(dt: number, params: ParamBus): void {
    this.hueShift = params.hueShift

    for (const pulse of params.onsetPulses) {
      const i = this.counter++
      const size = lerp(SIZE_LOW, SIZE_HIGH, pulse.tone) *
        (1 + SIZE_STRENGTH_GAIN * pulse.strength) *
        (1 + WINDUP_SIZE_GAIN * params.windup)
      this.spawn({
        x: clamp01(0.5 + pulse.pan * PAN_X_SPREAD + (hash01(i * 2) - 0.5) * JITTER_X),
        y: clamp01(lerp(TONE_Y_MIN, TONE_Y_MAX, pulse.tone) + (hash01(i * 2 + 1) - 0.5) * JITTER_Y),
        size,
        tone: pulse.tone,
        strength: pulse.strength,
        ageSec: 0,
        lifetimeSec: LIFETIME_SEC,
      })
    }

    // A quiet mark on each beat keeps the grid legible even in bars where
    // nothing crosses the onset threshold.
    if (params.beatPhase < this.lastBeatPhase) {
      this.spawn({
        x: 0.5,
        y: 0.5,
        size: BEAT_PULSE_SIZE * (1 + params.windup),
        tone: 0.5,
        strength: 0.25 * params.tempoConfidence,
        ageSec: 0,
        lifetimeSec: LIFETIME_SEC,
      })
    }
    this.lastBeatPhase = params.beatPhase

    if (params.dropTrigger?.active) {
      this.spawn({
        x: 0.5,
        y: 0.5,
        size: DROP_SIZE * (0.7 + 0.6 * params.dropTrigger.strength),
        tone: 0.25,
        strength: 1,
        ageSec: 0,
        lifetimeSec: DROP_LIFETIME_SEC,
      })
    }

    for (let i = this.shapes.length - 1; i >= 0; i--) {
      const s = this.shapes[i]
      s.ageSec += dt
      if (s.ageSec >= s.lifetimeSec) this.shapes.splice(i, 1)
    }
  }

  render(targetFbo: WebGLFramebuffer | null): void {
    const gl = this.gl
    gl.bindFramebuffer(gl.FRAMEBUFFER, targetFbo)
    gl.viewport(0, 0, this.width, this.height)
    gl.clearColor(0, 0, 0, 1)
    gl.clear(gl.COLOR_BUFFER_BIT)

    const count = Math.min(this.shapes.length, MAX_SHAPES)
    if (count === 0) return

    for (let i = 0; i < count; i++) {
      const s = this.shapes[i]
      const o = i * FLOATS_PER_SHAPE
      this.instanceData[o] = s.x
      this.instanceData[o + 1] = s.y
      this.instanceData[o + 2] = s.size
      this.instanceData[o + 3] = clamp01(s.ageSec / s.lifetimeSec)
      this.instanceData[o + 4] = s.tone
      this.instanceData[o + 5] = s.strength
    }

    gl.bindVertexArray(this.vao)
    gl.bindBuffer(gl.ARRAY_BUFFER, this.instanceBuffer)
    gl.bufferSubData(gl.ARRAY_BUFFER, 0, this.instanceData, 0, count * FLOATS_PER_SHAPE)

    gl.useProgram(this.program)
    gl.uniform1f(this.uAspect, this.width / this.height)
    gl.uniform1f(this.uHueShift, this.hueShift)

    gl.enable(gl.BLEND)
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA) // premultiplied, set by the shader
    gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, count)
    gl.disable(gl.BLEND)
    gl.bindVertexArray(null)
  }

  dispose(): void {
    const gl = this.gl
    gl.deleteProgram(this.program)
    gl.deleteVertexArray(this.vao)
    gl.deleteBuffer(this.cornerBuffer)
    gl.deleteBuffer(this.instanceBuffer)
  }

  // Fixed pool with oldest-first eviction, so a dense passage can never grow
  // the buffer or stall the frame.
  private spawn(shape: Shape): void {
    const budget = Math.max(16, Math.round(MAX_SHAPES * this.qualityScale))
    while (this.shapes.length >= budget) this.shapes.shift()
    this.shapes.push(shape)
  }
}
