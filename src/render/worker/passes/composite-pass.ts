import { createProgram } from '../gl/program'
import { createFullscreenQuad, drawFullscreenQuad } from '../gl/fullscreen-quad'
import vertSrc from '../gl/fullscreen.vert.glsl?raw'
import fragSrc from './composite.frag.glsl?raw'

export class CompositePass {
  private program: WebGLProgram
  private quad: WebGLVertexArrayObject
  private uniforms: {
    uScene: WebGLUniformLocation | null
    uBloom: WebGLUniformLocation | null
    uBloomStrength: WebGLUniformLocation | null
    uHasBloom: WebGLUniformLocation | null
  }

  constructor(private gl: WebGL2RenderingContext) {
    this.program = createProgram(gl, vertSrc, fragSrc)
    this.quad = createFullscreenQuad(gl)
    this.uniforms = {
      uScene: gl.getUniformLocation(this.program, 'uScene'),
      uBloom: gl.getUniformLocation(this.program, 'uBloom'),
      uBloomStrength: gl.getUniformLocation(this.program, 'uBloomStrength'),
      uHasBloom: gl.getUniformLocation(this.program, 'uHasBloom'),
    }
  }

  apply(
    targetFbo: WebGLFramebuffer | null,
    width: number,
    height: number,
    sceneTexture: WebGLTexture,
    bloomTexture: WebGLTexture | null,
    bloomStrength: number,
  ): void {
    const gl = this.gl
    gl.bindFramebuffer(gl.FRAMEBUFFER, targetFbo)
    gl.viewport(0, 0, width, height)
    gl.useProgram(this.program)
    gl.activeTexture(gl.TEXTURE0)
    gl.bindTexture(gl.TEXTURE_2D, sceneTexture)
    gl.uniform1i(this.uniforms.uScene, 0)
    if (bloomTexture) {
      gl.activeTexture(gl.TEXTURE1)
      gl.bindTexture(gl.TEXTURE_2D, bloomTexture)
      gl.uniform1i(this.uniforms.uBloom, 1)
    }
    gl.uniform1f(this.uniforms.uBloomStrength, bloomTexture ? bloomStrength : 0)
    gl.uniform1i(this.uniforms.uHasBloom, bloomTexture ? 1 : 0)
    drawFullscreenQuad(gl, this.quad)
  }

  dispose(): void {
    const gl = this.gl
    gl.deleteProgram(this.program)
    gl.deleteVertexArray(this.quad)
  }
}
