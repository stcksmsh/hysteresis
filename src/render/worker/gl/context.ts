export interface GlCapabilities {
  gl: WebGL2RenderingContext
  floatFbo: boolean
}

export class WebGL2UnavailableError extends Error {
  constructor() {
    super('WebGL2 is not available in this browser/context')
    this.name = 'WebGL2UnavailableError'
  }
}

export function createGlContext(canvas: OffscreenCanvas): GlCapabilities {
  const gl = canvas.getContext('webgl2', {
    alpha: false,
    antialias: false,
    depth: false,
    stencil: false,
    powerPreference: 'high-performance',
  })

  if (!gl) {
    throw new WebGL2UnavailableError()
  }

  // Needed for float-format ping-pong FBOs (reaction-diffusion sim, Phase 4).
  // Absence is not fatal here — scenes that need it fall back to a packed
  // 8-bit encoding; this just records whether that fallback is required.
  const floatFbo = gl.getExtension('EXT_color_buffer_float') !== null

  return { gl, floatFbo }
}
