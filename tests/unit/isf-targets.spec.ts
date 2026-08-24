import { describe, it, expect } from 'vitest'
import { parseIsf } from '../../src/isf/parse-isf'
import { isfInputsToTargets, resolvedTargetsToIsfUniforms, ISF_TARGET_PREFIX } from '../../src/isf/isf-targets'

const SRC = `/*{
  "INPUTS": [
    { "NAME": "speed", "TYPE": "float", "DEFAULT": 1.0, "MIN": 0.0, "MAX": 4.0 },
    { "NAME": "invert", "TYPE": "bool", "DEFAULT": true },
    { "NAME": "mode", "TYPE": "long", "DEFAULT": 2, "VALUES": [0, 1, 2] },
    { "NAME": "tint", "TYPE": "color", "DEFAULT": [0.1, 0.2, 0.3, 0.4] },
    { "NAME": "center", "TYPE": "point2D", "DEFAULT": [0.25, 0.75], "MIN": [-1.0, -2.0], "MAX": [1.0, 2.0] }
  ]
}*/
void main() { gl_FragColor = vec4(1.0); }
`

describe('isfInputsToTargets', () => {
  const doc = parseIsf(SRC)
  const targets = isfInputsToTargets(doc)
  const byId = Object.fromEntries(targets.map((t) => [t.id, t]))

  it('expands a float input to one target with its declared range/default', () => {
    expect(byId[`${ISF_TARGET_PREFIX}speed`]).toMatchObject({ defaultValue: 1, range: [0, 4] })
  })

  it('expands a bool input to a 0/1 target', () => {
    expect(byId[`${ISF_TARGET_PREFIX}invert`]).toMatchObject({ defaultValue: 1, range: [0, 1] })
  })

  it('expands a long input to an index-range target', () => {
    expect(byId[`${ISF_TARGET_PREFIX}mode`]).toMatchObject({ defaultValue: 2, range: [0, 2] })
  })

  it('expands a color input into four r/g/b/a scalar targets', () => {
    expect(byId[`${ISF_TARGET_PREFIX}tint.r`]).toMatchObject({ defaultValue: 0.1, range: [0, 1] })
    expect(byId[`${ISF_TARGET_PREFIX}tint.g`]).toMatchObject({ defaultValue: 0.2, range: [0, 1] })
    expect(byId[`${ISF_TARGET_PREFIX}tint.b`]).toMatchObject({ defaultValue: 0.3, range: [0, 1] })
    expect(byId[`${ISF_TARGET_PREFIX}tint.a`]).toMatchObject({ defaultValue: 0.4, range: [0, 1] })
  })

  it('expands a point2D input into x/y scalar targets with per-axis range', () => {
    expect(byId[`${ISF_TARGET_PREFIX}center.x`]).toMatchObject({ defaultValue: 0.25, range: [-1, 1] })
    expect(byId[`${ISF_TARGET_PREFIX}center.y`]).toMatchObject({ defaultValue: 0.75, range: [-2, 2] })
  })

  it('produces exactly 9 targets for the 5 declared inputs (1+1+1+4+2)', () => {
    expect(targets).toHaveLength(9)
  })
})

describe('resolvedTargetsToIsfUniforms', () => {
  const doc = parseIsf(SRC)

  it('reassembles component targets back into typed uniform values', () => {
    const resolved = {
      [`${ISF_TARGET_PREFIX}speed`]: 2.5,
      [`${ISF_TARGET_PREFIX}invert`]: 0,
      [`${ISF_TARGET_PREFIX}mode`]: 1,
      [`${ISF_TARGET_PREFIX}tint.r`]: 0.9,
      [`${ISF_TARGET_PREFIX}tint.g`]: 0.8,
      [`${ISF_TARGET_PREFIX}tint.b`]: 0.7,
      [`${ISF_TARGET_PREFIX}tint.a`]: 0.6,
      [`${ISF_TARGET_PREFIX}center.x`]: -0.5,
      [`${ISF_TARGET_PREFIX}center.y`]: 1.5,
    }
    const uniforms = resolvedTargetsToIsfUniforms(doc, resolved)
    expect(uniforms.speed).toBe(2.5)
    expect(uniforms.invert).toBe(false)
    expect(uniforms.mode).toBe(1)
    expect(uniforms.tint).toEqual([0.9, 0.8, 0.7, 0.6])
    expect(uniforms.center).toEqual([-0.5, 1.5])
  })

  it('falls back to 0/defaults for missing keys instead of throwing', () => {
    const uniforms = resolvedTargetsToIsfUniforms(doc, {})
    expect(uniforms.speed).toBe(0)
    expect(uniforms.invert).toBe(false)
    expect(uniforms.tint).toEqual([0, 0, 0, 0])
  })
})
