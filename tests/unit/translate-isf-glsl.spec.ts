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

describe('translateIsfFragmentShader — HYSTERESIS_VERSION 1 multi-pass', () => {
  const MULTI_PASS_SRC = `/*{
    "HYSTERESIS_VERSION": 1,
    "PASSES": [
      { "TARGET": "beamTex", "KIND": "lineTrace", "POINTS": "scope" },
      { "TARGET": "", "KIND": "fullscreen" }
    ],
    "INPUTS": [
      { "NAME": "scope", "TYPE": "resource", "RESOURCE": "scope" },
      { "NAME": "drive", "TYPE": "float", "DEFAULT": 0.0, "MIN": 0.0, "MAX": 1.0 }
    ]
  }*/
  void main() {
    vec4 beam = texture2D(beamTex, isf_FragNormCoord);
    gl_FragColor = beam * drive;
  }
  `
  const doc = parseIsf(MULTI_PASS_SRC)
  const out = translateIsfFragmentShader(doc)

  it('declares a sampler2D uniform for the lineTrace pass target', () => {
    expect(out).toContain('uniform sampler2D beamTex;')
  })

  it('does not declare a uniform for the resource input itself', () => {
    expect(out).not.toContain('uniform float scope;')
    expect(out).not.toContain('uniform sampler2D scope;')
  })

  it('still declares a real uniform for ordinary scalar inputs', () => {
    expect(out).toContain('uniform float drive;')
  })

  it('never declares a uniform for the final ("") output target', () => {
    // Only one sampler2D decl should exist (beamTex) — no stray `uniform sampler2D ;`
    expect(out.match(/uniform sampler2D/g)).toHaveLength(1)
  })
})
