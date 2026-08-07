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

  // Needed for float-format FBOs (the bloom/persistence passes' ping-pong
  // buffers). Absence is not fatal here — they fall back to a packed 8-bit
  // encoding; this just records whether that fallback is required.
  const floatFbo = gl.getExtension('EXT_color_buffer_float') !== null

  return { gl, floatFbo }
}
