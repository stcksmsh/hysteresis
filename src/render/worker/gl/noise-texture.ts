const LATTICE = 4 // noise cells across the texture; low = large, slow-moving features
const OCTAVES = 3

function hash2(x: number, y: number, seed: number): number {
  const n = Math.sin(x * 127.1 + y * 311.7 + seed * 74.7) * 43758.5453123
  return n - Math.floor(n)
}

// Value noise on a wrapping lattice, so the baked texture tiles seamlessly
// under GL_REPEAT — the sim samples it with a drifting offset forever.
function valueNoise(x: number, y: number, period: number, seed: number): number {
  const xi = Math.floor(x)
  const yi = Math.floor(y)
  const xf = x - xi
  const yf = y - yi
  const u = xf * xf * (3 - 2 * xf)
  const v = yf * yf * (3 - 2 * yf)
  const wrap = (n: number) => ((n % period) + period) % period
  const x0 = wrap(xi)
  const x1 = wrap(xi + 1)
  const y0 = wrap(yi)
  const y1 = wrap(yi + 1)
  const a = hash2(x0, y0, seed)
  const b = hash2(x1, y0, seed)
  const c = hash2(x0, y1, seed)
  const d = hash2(x1, y1, seed)
  return a * (1 - u) * (1 - v) + b * u * (1 - v) + c * (1 - u) * v + d * u * v
}

function fbm(x: number, y: number, seed: number): number {
  let sum = 0
  let amp = 0.5
  let freq = 1
  let norm = 0
  for (let o = 0; o < OCTAVES; o++) {
    sum += amp * valueNoise(x * freq, y * freq, LATTICE * freq, seed + o * 17)
    norm += amp
    amp *= 0.5
    freq *= 2
  }
  return sum / norm
}

// Baked once at init: R drives the per-fragment feed offset, G the kill
// offset, B a flow potential (all decorrelated by seed). Sampling this is a
// texture fetch, versus dozens of ALU ops for per-fragment fbm — and the sim
// shader runs many substeps per rendered frame, so that cost would multiply.
export function createNoiseTexture(gl: WebGL2RenderingContext, size = 128): WebGLTexture {
  const data = new Uint8Array(size * size * 4)
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const u = (x / size) * LATTICE
      const v = (y / size) * LATTICE
      const i = (y * size + x) * 4
      data[i] = Math.round(fbm(u, v, 0) * 255)
      data[i + 1] = Math.round(fbm(u, v, 101) * 255)
      // B is a scalar potential; the sim takes its curl to get a smooth,
      // divergence-free flow field for advecting the pattern.
      data[i + 2] = Math.round(fbm(u, v, 211) * 255)
      data[i + 3] = 255
    }
  }

  const texture = gl.createTexture()
  if (!texture) throw new Error('Failed to create noise texture')
  gl.bindTexture(gl.TEXTURE_2D, texture)
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, size, size, 0, gl.RGBA, gl.UNSIGNED_BYTE, data)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT)
  return texture
}
