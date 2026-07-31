export interface Fbo {
  framebuffer: WebGLFramebuffer
  texture: WebGLTexture
  width: number
  height: number
}

// Gray-Scott's U/V both stay naturally within 0..1, so the fallback path
// (no EXT_color_buffer_float) is just a plain 8-bit UNORM texture — no
// custom bit-packing needed, only reduced precision over long runs.
export function createFbo(gl: WebGL2RenderingContext, width: number, height: number, useFloat: boolean): Fbo {
  const texture = gl.createTexture()
  if (!texture) throw new Error('Failed to create texture')
  gl.bindTexture(gl.TEXTURE_2D, texture)
  const internalFormat = useFloat ? gl.RGBA16F : gl.RGBA8
  const type = useFloat ? gl.HALF_FLOAT : gl.UNSIGNED_BYTE
  gl.texImage2D(gl.TEXTURE_2D, 0, internalFormat, width, height, 0, gl.RGBA, type, null)
  // LINEAR is safe for the sim's own Laplacian stencil reads too — the
  // uTexel offsets sample exact texel centers, where LINEAR degenerates to
  // the same value as NEAREST — and it gives free smooth upscaling when the
  // sim runs at a lower resolution than the display target.
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)

  const framebuffer = gl.createFramebuffer()
  if (!framebuffer) throw new Error('Failed to create framebuffer')
  gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer)
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0)

  const status = gl.checkFramebufferStatus(gl.FRAMEBUFFER)
  gl.bindFramebuffer(gl.FRAMEBUFFER, null)
  if (status !== gl.FRAMEBUFFER_COMPLETE) {
    throw new Error(`Framebuffer incomplete: 0x${status.toString(16)}`)
  }

  return { framebuffer, texture, width, height }
}

export function deleteFbo(gl: WebGL2RenderingContext, fbo: Fbo): void {
  gl.deleteFramebuffer(fbo.framebuffer)
  gl.deleteTexture(fbo.texture)
}
