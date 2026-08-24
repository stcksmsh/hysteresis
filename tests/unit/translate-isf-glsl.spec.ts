import { describe, it, expect } from 'vitest'
import { parseIsf } from '../../src/isf/parse-isf'
import { translateIsfFragmentShader } from '../../src/isf/translate-isf-glsl'

const SRC = `/*{
  "INPUTS": [
    { "NAME": "speed", "TYPE": "float", "DEFAULT": 1.0, "MIN": 0.0, "MAX": 4.0 },
    { "NAME": "tint", "TYPE": "color", "DEFAULT": [1.0, 1.0, 1.0, 1.0] }
  ]
}*/
void main() {
  vec2 uv = isf_FragNormCoord;
  vec4 c = texture2D(gl_FragCoord.xy, uv);
  gl_FragColor = c * tint * sin(TIME * speed);
}
`

describe('translateIsfFragmentShader', () => {
  const doc = parseIsf(SRC)
  const out = translateIsfFragmentShader(doc)

  it('emits a GLSL ES 300 shader with the ISF built-in uniforms declared', () => {
    expect(out).toContain('#version 300 es')
    expect(out).toContain('uniform float TIME;')
    expect(out).toContain('uniform vec2 RENDERSIZE;')
    expect(out).toContain('uniform int PASSINDEX;')
  })

  it('declares a real uniform for every declared input, correctly typed', () => {
    expect(out).toContain('uniform float speed;')
    expect(out).toContain('uniform vec4 tint;')
  })

  it('replaces gl_FragColor with a real out variable', () => {
    expect(out).toContain('out vec4 isf_FragColor;')
    expect(out).not.toMatch(/[^_]gl_FragColor/)
    expect(out).toContain('isf_FragColor = c * tint')
  })

  it('replaces texture2D( with texture(', () => {
    expect(out).not.toContain('texture2D(')
    expect(out).toContain('texture(gl_FragCoord.xy, uv)')
  })

  it('computes isf_FragNormCoord as a local inside main(), not a global initializer', () => {
    const mainIdx = out.indexOf('void main()')
    const normCoordIdx = out.indexOf('vec2 isf_FragNormCoord')
    expect(normCoordIdx).toBeGreaterThan(mainIdx)
  })

  it('throws a clear error when the body has no main()', () => {
    const noMainDoc = { ...doc, body: '// no main here' }
    expect(() => translateIsfFragmentShader(noMainDoc)).toThrow(/main/)
  })
})
