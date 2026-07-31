import { createFbo, deleteFbo, type Fbo } from '../gl/fbo'
import { createProgram } from '../gl/program'
import { createFullscreenQuad, drawFullscreenQuad } from '../gl/fullscreen-quad'
import vertSrc from '../gl/fullscreen.vert.glsl?raw'
import brightFragSrc from './bright-pass.frag.glsl?raw'
import blurFragSrc from './blur.frag.glsl?raw'

const DOWNSAMPLE = 4 // bloom runs at 1/4 resolution — glow is inherently low-frequency, cheap
const BLUR_PASSES = 2 // each pass = 1 horizontal + 1 vertical

export class BloomPass {
  private brightProgram: WebGLProgram
  private blurProgram: WebGLProgram
  private quad: WebGLVertexArrayObject
  private pingA!: Fbo
  private pingB!: Fbo
  private brightUniforms: { uScene: WebGLUniformLocation | null; uThreshold: WebGLUniformLocation | null }
  private blurUniforms: {
    uTex: WebGLUniformLocation | null
    uDirection: WebGLUniformLocation | null
    uTexel: WebGLUniformLocation | null
  }

  constructor(
    private gl: WebGL2RenderingContext,
    width: number,
    height: number,
    private useFloat: boolean,
  ) {
    this.brightProgram = createProgram(gl, vertSrc, brightFragSrc)
    this.blurProgram = createProgram(gl, vertSrc, blurFragSrc)
    this.quad = createFullscreenQuad(gl)
    this.brightUniforms = {
      uScene: gl.getUniformLocation(this.brightProgram, 'uScene'),
      uThreshold: gl.getUniformLocation(this.brightProgram, 'uThreshold'),
    }
    this.blurUniforms = {
      uTex: gl.getUniformLocation(this.blurProgram, 'uTex'),
      uDirection: gl.getUniformLocation(this.blurProgram, 'uDirection'),
      uTexel: gl.getUniformLocation(this.blurProgram, 'uTexel'),
    }
    this.resize(width, height)
  }

  resize(width: number, height: number): void {
    const gl = this.gl
    if (this.pingA) deleteFbo(gl, this.pingA)
    if (this.pingB) deleteFbo(gl, this.pingB)
    const w = Math.max(1, Math.round(width / DOWNSAMPLE))
    const h = Math.max(1, Math.round(height / DOWNSAMPLE))
    this.pingA = createFbo(gl, w, h, this.useFloat)
    this.pingB = createFbo(gl, w, h, this.useFloat)
  }

  // Returns a texture containing the blurred bright-pass result, meant to
  // be additively combined with the base scene by the composite pass.
  apply(sceneTexture: WebGLTexture, threshold: number): WebGLTexture {
    const gl = this.gl
    const w = this.pingA.width
    const h = this.pingA.height

    gl.bindFramebuffer(gl.FRAMEBUFFER, this.pingA.framebuffer)
    gl.viewport(0, 0, w, h)
    gl.useProgram(this.brightProgram)
    gl.activeTexture(gl.TEXTURE0)
    gl.bindTexture(gl.TEXTURE_2D, sceneTexture)
    gl.uniform1i(this.brightUniforms.uScene, 0)
    gl.uniform1f(this.brightUniforms.uThreshold, threshold)
    drawFullscreenQuad(gl, this.quad)

    let readFbo = this.pingA
    let writeFbo = this.pingB
    gl.useProgram(this.blurProgram)
    gl.uniform2f(this.blurUniforms.uTexel, 1 / w, 1 / h)

    for (let i = 0; i < BLUR_PASSES; i++) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, writeFbo.framebuffer)
      gl.viewport(0, 0, w, h)
      gl.activeTexture(gl.TEXTURE0)
      gl.bindTexture(gl.TEXTURE_2D, readFbo.texture)
      gl.uniform1i(this.blurUniforms.uTex, 0)
      gl.uniform2f(this.blurUniforms.uDirection, 1, 0)
      drawFullscreenQuad(gl, this.quad)
      ;[readFbo, writeFbo] = [writeFbo, readFbo]

      gl.bindFramebuffer(gl.FRAMEBUFFER, writeFbo.framebuffer)
      gl.viewport(0, 0, w, h)
      gl.bindTexture(gl.TEXTURE_2D, readFbo.texture)
      gl.uniform2f(this.blurUniforms.uDirection, 0, 1)
      drawFullscreenQuad(gl, this.quad)
      ;[readFbo, writeFbo] = [writeFbo, readFbo]
    }

    return readFbo.texture
  }

  dispose(): void {
    const gl = this.gl
    deleteFbo(gl, this.pingA)
    deleteFbo(gl, this.pingB)
    gl.deleteProgram(this.brightProgram)
    gl.deleteProgram(this.blurProgram)
    gl.deleteVertexArray(this.quad)
  }
}
