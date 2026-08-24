import { describe, it, expect } from 'vitest'
import { parseIsf } from '../../src/isf/parse-isf'
import { IsfParseError, IsfUnsupportedFeatureError } from '../../src/isf/types'

// A real-shaped ISF generator (color-cycling plasma, single pass, only
// supported input types) — the kind of file this subset is meant to
// actually load, not a synthetic minimal fixture.
const PLASMA_SRC = `/*{
  "DESCRIPTION": "simple plasma",
  "CREDIT": "test fixture",
  "CATEGORIES": ["Generator"],
  "INPUTS": [
    { "NAME": "speed", "TYPE": "float", "DEFAULT": 1.0, "MIN": 0.0, "MAX": 4.0 },
    { "NAME": "invert", "TYPE": "bool", "DEFAULT": false },
    { "NAME": "paletteIndex", "TYPE": "long", "DEFAULT": 1, "VALUES": [0, 1, 2], "LABELS": ["fire", "ice", "mono"] },
    { "NAME": "tint", "TYPE": "color", "DEFAULT": [1.0, 0.5, 0.2, 1.0] },
    { "NAME": "center", "TYPE": "point2D", "DEFAULT": [0.5, 0.5], "MIN": [0.0, 0.0], "MAX": [1.0, 1.0] }
  ]
}*/

void main() {
  vec2 uv = isf_FragNormCoord.xy;
  float v = sin((uv.x + center.x) * 10.0 + TIME * speed);
  gl_FragColor = vec4(tint.rgb * v, 1.0);
}
`

describe('parseIsf', () => {
  it('parses a real-shaped single-pass generator end to end', () => {
    const doc = parseIsf(PLASMA_SRC)
    expect(doc.description).toBe('simple plasma')
    expect(doc.categories).toEqual(['Generator'])
    expect(doc.inputs).toHaveLength(5)
    expect(doc.body).toContain('void main()')
    expect(doc.body).toContain('gl_FragColor')
  })

  it('parses each supported input type with its real fields', () => {
    const doc = parseIsf(PLASMA_SRC)
    const byName = Object.fromEntries(doc.inputs.map((i) => [i.name, i]))

    expect(byName.speed).toMatchObject({ type: 'float', default: 1, min: 0, max: 4 })
    expect(byName.invert).toMatchObject({ type: 'bool', default: false })
    expect(byName.paletteIndex).toMatchObject({ type: 'long', default: 1, values: [0, 1, 2], labels: ['fire', 'ice', 'mono'] })
    expect(byName.tint).toMatchObject({ type: 'color', default: [1, 0.5, 0.2, 1] })
    expect(byName.center).toMatchObject({ type: 'point2D', default: [0.5, 0.5], min: [0, 0], max: [1, 1] })
  })

  it('rejects a missing header comment', () => {
    expect(() => parseIsf('void main() { gl_FragColor = vec4(1.0); }')).toThrow(IsfParseError)
  })

  it('rejects an unclosed header comment', () => {
    expect(() => parseIsf('/*{ "INPUTS": [] } void main() {}')).toThrow(IsfParseError)
  })

  it('rejects invalid JSON in the header', () => {
    expect(() => parseIsf('/*{ not json }*/ void main() {}')).toThrow(IsfParseError)
  })

  it('rejects an image input with a specific message', () => {
    const src = `/*{ "INPUTS": [ { "NAME": "srcImg", "TYPE": "image" } ] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
    expect(() => parseIsf(src)).toThrow(IsfUnsupportedFeatureError)
    expect(() => parseIsf(src)).toThrow(/srcImg \(image\)/)
  })

  it('rejects an audioFFT input', () => {
    const src = `/*{ "INPUTS": [ { "NAME": "fft", "TYPE": "audioFFT" } ] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
    expect(() => parseIsf(src)).toThrow(IsfUnsupportedFeatureError)
  })

  it('rejects a multi-pass shader', () => {
    const src = `/*{ "PASSES": [ {"TARGET":"a"}, {"TARGET":"b"} ], "INPUTS": [] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
    expect(() => parseIsf(src)).toThrow(IsfUnsupportedFeatureError)
    expect(() => parseIsf(src)).toThrow(/Multi-pass/)
  })

  it('rejects a PERSISTENT buffer pass', () => {
    const src = `/*{ "PASSES": [ {"TARGET":"buf","PERSISTENT":true} ], "INPUTS": [] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
    expect(() => parseIsf(src)).toThrow(IsfUnsupportedFeatureError)
    expect(() => parseIsf(src)).toThrow(/PERSISTENT/)
  })

  it('rejects declared IMPORTED images', () => {
    const src = `/*{ "IMPORTED": { "logo": { "PATH": "logo.png" } }, "INPUTS": [] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
    expect(() => parseIsf(src)).toThrow(IsfUnsupportedFeatureError)
  })

  it('accepts a shader with no INPUTS at all', () => {
    const src = `/*{ "DESCRIPTION": "flat color" }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
    const doc = parseIsf(src)
    expect(doc.inputs).toEqual([])
  })

  // AGENTS.md's "Hysteresis format" — the real extension beyond standard ISF: a shader
  // declaring it wants a live Feature Engine signal by name.
  describe('hysteresisSignal (the Hysteresis-format extension)', () => {
    it('parses a valid hysteresisSignal input', () => {
      const src = `/*{ "INPUTS": [ { "NAME": "novelty", "TYPE": "hysteresisSignal", "SIGNAL": "noveltyLocal", "DEFAULT": 0.2 } ] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
      const doc = parseIsf(src)
      expect(doc.inputs).toEqual([{ type: 'hysteresisSignal', name: 'novelty', label: undefined, signal: 'noveltyLocal', default: 0.2 }])
    })

    it('defaults to 0 when DEFAULT is omitted', () => {
      const src = `/*{ "INPUTS": [ { "NAME": "fam", "TYPE": "hysteresisSignal", "SIGNAL": "familiarity" } ] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
      const doc = parseIsf(src)
      expect(doc.inputs[0]).toMatchObject({ default: 0 })
    })

    it('rejects an unknown SIGNAL name with a specific message listing valid ones', () => {
      const src = `/*{ "INPUTS": [ { "NAME": "bad", "TYPE": "hysteresisSignal", "SIGNAL": "totallyMadeUp" } ] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
      expect(() => parseIsf(src)).toThrow(IsfParseError)
      expect(() => parseIsf(src)).toThrow(/unknown SIGNAL "totallyMadeUp"/)
    })

    it('rejects a missing SIGNAL', () => {
      const src = `/*{ "INPUTS": [ { "NAME": "bad", "TYPE": "hysteresisSignal" } ] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
      expect(() => parseIsf(src)).toThrow(IsfParseError)
    })
  })

  it('rejects a declared HYSTERESIS_SCRIPT with a clear "not executed yet" message', () => {
    const src = `/*{ "HYSTERESIS_SCRIPT": "export function step() {}", "INPUTS": [] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
    expect(() => parseIsf(src)).toThrow(IsfUnsupportedFeatureError)
    expect(() => parseIsf(src)).toThrow(/not executed yet/)
  })

  it('does not reject a shader with an empty/absent HYSTERESIS_SCRIPT', () => {
    const src = `/*{ "HYSTERESIS_SCRIPT": "", "INPUTS": [] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
    expect(() => parseIsf(src)).not.toThrow()
  })

  // HYSTERESIS_VERSION 1: real multi-pass (lineTrace) + resource inputs.
  describe('HYSTERESIS_VERSION and real multi-pass', () => {
    it('a plain file with no HYSTERESIS_VERSION/PASSES gets the implicit single fullscreen pass', () => {
      const doc = parseIsf(PLASMA_SRC)
      expect(doc.hysteresisVersion).toBeUndefined()
      expect(doc.passes).toEqual([{ kind: 'fullscreen', target: '' }])
    })

    it('rejects an unrecognized HYSTERESIS_VERSION', () => {
      const src = `/*{ "HYSTERESIS_VERSION": 99, "INPUTS": [] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
      expect(() => parseIsf(src)).toThrow(IsfUnsupportedFeatureError)
      expect(() => parseIsf(src)).toThrow(/HYSTERESIS_VERSION/)
    })

    it('a stock multi-pass ISF shader without HYSTERESIS_VERSION is still rejected the same as before', () => {
      const src = `/*{ "PASSES": [ {"TARGET":"a"}, {"TARGET":"b"} ], "INPUTS": [] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
      expect(() => parseIsf(src)).toThrow(/Multi-pass/)
    })

    it('parses a real lineTrace + fullscreen PASSES pair', () => {
      const src = `/*{
        "HYSTERESIS_VERSION": 1,
        "PASSES": [
          { "TARGET": "beamTex", "KIND": "lineTrace", "POINTS": "scope", "WIDTH": "beamWidth" },
          { "TARGET": "", "KIND": "fullscreen" }
        ],
        "INPUTS": [
          { "NAME": "scope", "TYPE": "resource", "RESOURCE": "scope" },
          { "NAME": "beamWidth", "TYPE": "float", "DEFAULT": 0.01, "MIN": 0.001, "MAX": 0.05 }
        ]
      }*/
      uniform sampler2D beamTex;
      void main() { gl_FragColor = texture2D(beamTex, isf_FragNormCoord); }`
      const doc = parseIsf(src)
      expect(doc.hysteresisVersion).toBe(1)
      expect(doc.passes).toEqual([
        { kind: 'lineTrace', target: 'beamTex', points: 'scope', width: 'beamWidth' },
        { kind: 'fullscreen', target: '' },
      ])
      expect(doc.inputs).toContainEqual({ type: 'resource', name: 'scope', label: undefined, resource: 'scope' })
    })

    it('rejects an unknown RESOURCE', () => {
      const src = `/*{ "HYSTERESIS_VERSION": 1, "INPUTS": [ { "NAME": "x", "TYPE": "resource", "RESOURCE": "madeUp" } ] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
      expect(() => parseIsf(src)).toThrow(IsfParseError)
      expect(() => parseIsf(src)).toThrow(/unknown RESOURCE "madeUp"/)
    })

    it('rejects a lineTrace pass with an unknown KIND', () => {
      const src = `/*{ "HYSTERESIS_VERSION": 1, "PASSES": [ {"TARGET":"a","KIND":"particles"}, {"TARGET":"","KIND":"fullscreen"} ], "INPUTS": [] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
      expect(() => parseIsf(src)).toThrow(IsfUnsupportedFeatureError)
      expect(() => parseIsf(src)).toThrow(/unknown KIND "particles"/)
    })

    it('rejects a lineTrace pass whose POINTS does not match a declared resource input', () => {
      const src = `/*{
        "HYSTERESIS_VERSION": 1,
        "PASSES": [ { "TARGET": "beamTex", "KIND": "lineTrace", "POINTS": "nope" }, { "TARGET": "", "KIND": "fullscreen" } ],
        "INPUTS": []
      }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
      expect(() => parseIsf(src)).toThrow(IsfParseError)
      expect(() => parseIsf(src)).toThrow(/POINTS "nope"/)
    })

    it('still rejects PERSISTENT even under HYSTERESIS_VERSION', () => {
      const src = `/*{ "HYSTERESIS_VERSION": 1, "PASSES": [ {"TARGET":"buf","PERSISTENT":true} ], "INPUTS": [] }*/\nvoid main() { gl_FragColor = vec4(1.0); }`
      expect(() => parseIsf(src)).toThrow(/PERSISTENT/)
    })
  })
})
