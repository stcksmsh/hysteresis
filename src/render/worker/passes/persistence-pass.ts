import { createFbo, deleteFbo, type Fbo } from '../gl/fbo'
import { createProgram } from '../gl/program'
import { createFullscreenQuad, drawFullscreenQuad } from '../gl/fullscreen-quad'
import vertSrc from '../gl/fullscreen.vert.glsl?raw'
import fragSrc from './persistence.frag.glsl?raw'

// Generic decay/blend feedback pass for memoryless scenes that want trail
// memory (particles, reactive geometry). Reaction-diffusion's own ping-pong
// sim already IS long-memory feedback, so it opts out (Scene.wantsPersistencePass
// = false) — this exists ready for scenes that do want it.
export class PersistencePass {
  private program: WebGLProgram
  private quad: WebGLVertexArrayObject
  private front!: Fbo
  private back!: Fbo
  private uCurrent: WebGLUniformLocation | null
  private uPrev: WebGLUniformLocation | null
  private uDecay: WebGLUniformLocation | null

  constructor(
    private gl: WebGL2RenderingContext,
    width: number,
    height: number,
    private useFloat: boolean,
  ) {
    this.program = createProgram(gl, vertSrc, fragSrc)
    this.quad = createFullscreenQuad(gl)
    this.uCurrent = gl.getUniformLocation(this.program, 'uCurrent')
    this.uPrev = gl.getUniformLocation(this.program, 'uPrev')
    this.uDecay = gl.getUniformLocation(this.program, 'uDecay')
    this.resize(width, height)
  }

  resize(width: number, height: number): void {
    const gl = this.gl
    if (this.front) deleteFbo(gl, this.front)
    if (this.back) deleteFbo(gl, this.back)
    this.front = createFbo(gl, Math.max(1, width), Math.max(1, height), this.useFloat)
    this.back = createFbo(gl, Math.max(1, width), Math.max(1, height), this.useFloat)
  }

  // Blends `currentTexture` onto the decayed previous persisted frame.
  // Returns the texture holding the new persisted result.
  apply(currentTexture: WebGLTexture, decay: number): WebGLTexture {
    const gl = this.gl
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.back.framebuffer)
    gl.viewport(0, 0, this.back.width, this.back.height)
    gl.useProgram(this.program)
    gl.activeTexture(gl.TEXTURE0)
    gl.bindTexture(gl.TEXTURE_2D, currentTexture)
    gl.uniform1i(this.uCurrent, 0)
    gl.activeTexture(gl.TEXTURE1)
    gl.bindTexture(gl.TEXTURE_2D, this.front.texture)
    gl.uniform1i(this.uPrev, 1)
    gl.uniform1f(this.uDecay, decay)
    drawFullscreenQuad(gl, this.quad)

    const tmp = this.front
    this.front = this.back
    this.back = tmp
    return this.front.texture
  }

  dispose(): void {
    const gl = this.gl
    deleteFbo(gl, this.front)
    deleteFbo(gl, this.back)
    gl.deleteProgram(this.program)
    gl.deleteVertexArray(this.quad)
  }
}
