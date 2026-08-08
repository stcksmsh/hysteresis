import { createProgram } from '../gl/program'
import vertSrc from './onset-particle.vert.glsl?raw'
import fragSrc from './onset-particle.frag.glsl?raw'
import type { OnsetPulse } from '../../../shared/types'

const MAX_PARTICLES = 96
const LIFETIME_BASE_SEC = 0.9
const LIFETIME_STRENGTH_GAIN = 0.6
const SPEED_BASE = 0.35
const SPEED_STRENGTH_GAIN = 0.5
const DRAG_PER_SEC = 0.6 // velocity decays toward 0 at this rate, independent of the flow pull
const FLOW_PULL = 0.9 // how strongly the shared curl field bends a particle's own drift
const SIZE_BASE = 0.03
const SIZE_STRENGTH_GAIN = 0.05

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v))
}

// Cheap analytic curl noise for CPU-side particle advection (SINTEZA_VIZ.md
// §4d) — NOT the field MemoryFieldPass reads (that one samples a baked GPU
// texture; reading it back here would cost a stall). This is a separate,
// divergence-free-by-construction approximation (each axis reads the
// other's phase, à la classic curl-noise-from-sines) tuned to *look* like it
// belongs to the same flow, not to match it bit-for-bit.
function curl2D(x: number, y: number, t: number): { x: number; y: number } {
  const a = x * 1.7 + t * 0.15
  const b = y * 1.7 - t * 0.11
  const a2 = x * 2.9 - t * 0.09 + 1.7
  const b2 = y * 2.9 + t * 0.13 + 4.1
  return {
    x: (Math.cos(b) + Math.cos(b2)) * 0.5,
    y: (Math.sin(a) + Math.sin(a2)) * 0.5,
  }
}

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  life: number // 1 (just spawned) .. 0 (dead/free)
  maxLifeSec: number
  size: number
}

// Onset particles (SINTEZA_VIZ.md §4d): sparks injected from
// ParamBus.onsetPulses, dragged by the same curl-noise flow the memory
// field itself uses (a CPU approximation of it — see curl2D above), and
// rendered additively straight onto the memory field's own FBO so their
// trails persist and smear exactly like everything else living in the
// field — that's what keeps the four layers reading as one organism.
export class OnsetParticles {
  private program: WebGLProgram
  private vao: WebGLVertexArrayObject
  private cornerBuffer: WebGLBuffer
  private centerBuffer: WebGLBuffer
  private sizeAlphaBuffer: WebGLBuffer
  private centerData = new Float32Array(MAX_PARTICLES * 2)
  private sizeAlphaData = new Float32Array(MAX_PARTICLES * 2)
  private particles: Particle[] = []
  private clockSec = 0

  private uniforms: {
    uAspect: WebGLUniformLocation | null
    uColor: WebGLUniformLocation | null
  }

  constructor(private gl: WebGL2RenderingContext) {
    this.program = createProgram(gl, vertSrc, fragSrc)
    this.uniforms = {
      uAspect: gl.getUniformLocation(this.program, 'uAspect'),
      uColor: gl.getUniformLocation(this.program, 'uColor'),
    }
    for (let i = 0; i < MAX_PARTICLES; i++) {
      this.particles.push({ x: 0, y: 0, vx: 0, vy: 0, life: 0, maxLifeSec: 1, size: 0 })
    }
    const geometry = this.createGeometry()
    this.vao = geometry.vao
    this.cornerBuffer = geometry.cornerBuffer
    this.centerBuffer = geometry.centerBuffer
    this.sizeAlphaBuffer = geometry.sizeAlphaBuffer
  }

  private createGeometry(): {
    vao: WebGLVertexArrayObject
    cornerBuffer: WebGLBuffer
    centerBuffer: WebGLBuffer
    sizeAlphaBuffer: WebGLBuffer
  } {
    const gl = this.gl
    const vao = gl.createVertexArray()
    if (!vao) throw new Error('Failed to create particle VAO')
    gl.bindVertexArray(vao)

    const cornerBuffer = gl.createBuffer()
    if (!cornerBuffer) throw new Error('Failed to create corner buffer')
    gl.bindBuffer(gl.ARRAY_BUFFER, cornerBuffer)
    // Triangle strip: BL, BR, TL, TR
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-0.5, -0.5, 0.5, -0.5, -0.5, 0.5, 0.5, 0.5]), gl.STATIC_DRAW)
    gl.enableVertexAttribArray(0)
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0)

    const centerBuffer = gl.createBuffer()
    if (!centerBuffer) throw new Error('Failed to create center buffer')
    gl.bindBuffer(gl.ARRAY_BUFFER, centerBuffer)
    gl.bufferData(gl.ARRAY_BUFFER, this.centerData.byteLength, gl.DYNAMIC_DRAW)
    gl.enableVertexAttribArray(1)
    gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 0, 0)
    gl.vertexAttribDivisor(1, 1)

    const sizeAlphaBuffer = gl.createBuffer()
    if (!sizeAlphaBuffer) throw new Error('Failed to create size/alpha buffer')
    gl.bindBuffer(gl.ARRAY_BUFFER, sizeAlphaBuffer)
    gl.bufferData(gl.ARRAY_BUFFER, this.sizeAlphaData.byteLength, gl.DYNAMIC_DRAW)
    gl.enableVertexAttribArray(2)
    gl.vertexAttribPointer(2, 2, gl.FLOAT, false, 0, 0)
    gl.vertexAttribDivisor(2, 1)

    gl.bindVertexArray(null)
    return { vao, cornerBuffer, centerBuffer, sizeAlphaBuffer }
  }

  // Spawns from this frame's pulses (dropping a pulse if every slot is
  // already occupied — bounded cost, no growth), integrates every live
  // particle through the shared (approximated) flow field, and ages them
  // out. `flowStrength` is the same driven parameter MemoryFieldPass reads
  // — a particle bends harder through the field exactly when the field
  // itself is churning harder.
  update(dt: number, pulses: OnsetPulse[], flowStrength: number): void {
    this.clockSec += dt

    for (const pulse of pulses) {
      const free = this.particles.find((p) => p.life <= 0)
      if (!free) continue
      const angle = Math.random() * Math.PI * 2
      const speed = SPEED_BASE + SPEED_STRENGTH_GAIN * pulse.strength
      free.x = clamp01((pulse.pan + 1) / 2) * 1.7 - 0.85
      free.y = clamp01(pulse.tone) * 1.4 - 0.7
      free.vx = Math.cos(angle) * speed
      free.vy = Math.sin(angle) * speed * 0.6 + speed * 0.3 // slight upward bias
      free.maxLifeSec = LIFETIME_BASE_SEC + LIFETIME_STRENGTH_GAIN * pulse.strength
      free.life = 1
      free.size = SIZE_BASE + SIZE_STRENGTH_GAIN * pulse.strength
    }

    const drag = Math.max(0, 1 - DRAG_PER_SEC * dt)
    for (const p of this.particles) {
      if (p.life <= 0) continue
      const flow = curl2D(p.x * 1.5, p.y * 1.5, this.clockSec)
      p.vx = p.vx * drag + flow.x * FLOW_PULL * flowStrength * dt
      p.vy = p.vy * drag + flow.y * FLOW_PULL * flowStrength * dt
      p.x += p.vx * dt
      p.y += p.vy * dt
      p.life = Math.max(0, p.life - dt / p.maxLifeSec)
    }
  }

  // Draws every live particle additively into `targetFbo` — expected to be
  // the memory field's own current FBO (see MemoryFieldPass.apply), so
  // particle trails persist and smear through the same ping-pong buffer as
  // everything else. Does not clear the target.
  render(targetFbo: WebGLFramebuffer, width: number, height: number, aspect: number, accent: [number, number, number]): void {
    const gl = this.gl
    let count = 0
    for (const p of this.particles) {
      if (p.life <= 0) continue
      this.centerData[count * 2] = p.x
      this.centerData[count * 2 + 1] = p.y
      this.sizeAlphaData[count * 2] = p.size
      // sin() fade-in/fade-out over the particle's own lifespan reads as a
      // spark igniting and dying, not a linear cut to zero.
      this.sizeAlphaData[count * 2 + 1] = Math.sin(Math.min(1, p.life) * Math.PI)
      count++
    }
    if (count === 0) return

    gl.bindFramebuffer(gl.FRAMEBUFFER, targetFbo)
    gl.viewport(0, 0, width, height)
    gl.enable(gl.BLEND)
    gl.blendFunc(gl.ONE, gl.ONE)
    gl.useProgram(this.program)
    gl.uniform1f(this.uniforms.uAspect, aspect)
    gl.uniform3f(this.uniforms.uColor, accent[0], accent[1], accent[2])

    gl.bindBuffer(gl.ARRAY_BUFFER, this.centerBuffer)
    gl.bufferSubData(gl.ARRAY_BUFFER, 0, this.centerData, 0, count * 2)
    gl.bindBuffer(gl.ARRAY_BUFFER, this.sizeAlphaBuffer)
    gl.bufferSubData(gl.ARRAY_BUFFER, 0, this.sizeAlphaData, 0, count * 2)

    gl.bindVertexArray(this.vao)
    gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, count)
    gl.bindVertexArray(null)
    gl.disable(gl.BLEND)
  }

  dispose(): void {
    const gl = this.gl
    gl.deleteProgram(this.program)
    gl.deleteVertexArray(this.vao)
    gl.deleteBuffer(this.cornerBuffer)
    gl.deleteBuffer(this.centerBuffer)
    gl.deleteBuffer(this.sizeAlphaBuffer)
  }
}
