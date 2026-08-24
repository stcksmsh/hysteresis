import { describe, it, expect } from 'vitest'
import { evaluateNode, type ThresholdState, type EnvelopeState } from '../../src/render/conductor/patchgraph/evaluate-node'
import type { CurveNode } from '../../src/render/conductor/patchgraph/types'

function evalCurve(curve: CurveNode['curve'], input: number): number {
  const node: CurveNode = { id: 'c', kind: 'curve', inputs: ['x'], curve }
  const thresholdState: ThresholdState = { active: false }
  const envelopeState: EnvelopeState = { value: 0 }
  return evaluateNode(node, [input], 1 / 60, thresholdState, envelopeState)
}

describe('applyCurve — smoothstep', () => {
  it('is sign-preserving for a bipolar signal, like exp/log', () => {
    // bandTilt/pan are bipolar (-1..1) — smoothstep used to clamp any
    // negative value straight to 0 before applying the curve at all,
    // silently discarding the entire negative half of the signal's range.
    expect(evalCurve('smoothstep', -0.5)).toBeLessThan(0)
    expect(evalCurve('smoothstep', -1)).toBeCloseTo(-1, 5)
  })

  it('still eases the positive domain exactly as before (0/0.5/1 unchanged)', () => {
    expect(evalCurve('smoothstep', 0)).toBeCloseTo(0, 5)
    expect(evalCurve('smoothstep', 0.5)).toBeCloseTo(0.5, 5)
    expect(evalCurve('smoothstep', 1)).toBeCloseTo(1, 5)
    expect(evalCurve('smoothstep', 0.25)).toBeLessThan(0.25) // eased in
  })

  it('is symmetric: f(-x) === -f(x)', () => {
    for (const x of [0.1, 0.3, 0.7, 0.9]) {
      expect(evalCurve('smoothstep', -x)).toBeCloseTo(-evalCurve('smoothstep', x), 10)
    }
  })
})
