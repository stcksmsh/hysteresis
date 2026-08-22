import { describe, it, expect } from 'vitest'
import { Patchbay } from '../../src/render/conductor/patchbay/Patchbay'
import { applyCurve } from '../../src/render/conductor/patchbay/curves'
import { SERVO_TARGETS } from '../../src/render/conductor/patchbay/configs/servo-targets'
import type { PatchbayConfig } from '../../src/render/conductor/patchbay/types'
import type { SignalBus, TargetDecl } from '../../src/render/conductor/types'

function makeBus(overrides: Partial<SignalBus> = {}): SignalBus {
  return {
    energy: 0,
    sub: 0,
    low: 0,
    mid: 0,
    presence: 0,
    air: 0,
    bandTilt: 0,
    centroid: 0,
    flatness: 0,
    pan: 0,
    familiarity: 0,
    beatPhase: 0,
    beatPulse: 0,
    barPhase: 0,
    downbeatPulse: 0,
    buildWindup: 0,
    buildProgress: 0,
    tension: 0,
    suspension: 0,
    dropImpulse: 0,
    onsetImpulse: 0,
    dropTrigger: null,
    scope: null,
    idle: false,
    tempoBpm: 120,
    tempoConfidence: 1,
    ...overrides,
  }
}

describe('curves', () => {
  it('linear is identity', () => {
    expect(applyCurve('linear', 0.42)).toBe(0.42)
  })

  it('smoothstep eases at the domain edges and holds the midpoint', () => {
    expect(applyCurve('smoothstep', 0)).toBeCloseTo(0, 5)
    expect(applyCurve('smoothstep', 1)).toBeCloseTo(1, 5)
    expect(applyCurve('smoothstep', 0.5)).toBeCloseTo(0.5, 5)
    expect(applyCurve('smoothstep', 0.25)).toBeLessThan(0.25) // eased in
  })

  it('threshold gates at the cut', () => {
    expect(applyCurve({ kind: 'threshold', cut: 0.5 }, 0.4)).toBe(0)
    expect(applyCurve({ kind: 'threshold', cut: 0.5 }, 0.6)).toBe(1)
  })
})

describe('Patchbay.resolve', () => {
  const targets: TargetDecl[] = [
    { id: 'out.a', acceptsTags: ['continuous'], defaultValue: 0.25, range: [0, 1] },
    { id: 'out.b', acceptsTags: ['continuous', 'section'], defaultValue: 0, range: [0, 2] },
    { id: 'out.scope', acceptsTags: ['continuous'], defaultValue: 0, range: [0, 0], passThrough: true },
  ]

  it('a target with no route holds its defaultValue', () => {
    const config: PatchbayConfig = { id: 'test', routes: [] }
    const patchbay = new Patchbay(config, [targets])
    const resolved = patchbay.resolve(makeBus(), 1 / 60, targets)
    expect(resolved['out.a']).toBe(0.25)
  })

  it('gain/offset/invert apply, then the result clamps to the target range', () => {
    const config: PatchbayConfig = {
      id: 'test',
      routes: [{ from: 'energy', to: 'out.b', gain: 2, offset: 1 }],
    }
    const patchbay = new Patchbay(config, [targets])
    // energy=0.8 -> 0.8*2+1=2.6, clamps to out.b's range [0,2]
    const resolved = patchbay.resolve(makeBus({ energy: 0.8 }), 1 / 60, targets)
    expect(resolved['out.b']).toBe(2)
  })

  it('invert reflects within the target range', () => {
    const config: PatchbayConfig = { id: 'test', routes: [{ from: 'energy', to: 'out.a', invert: true }] }
    const patchbay = new Patchbay(config, [targets])
    const resolved = patchbay.resolve(makeBus({ energy: 0.3 }), 1 / 60, targets)
    expect(resolved['out.a']).toBeCloseTo(0.7, 5) // range [0,1]: 0+1-0.3
  })

  it('multiple routes to the same target sum, then clamp (§5.1 default combine mode)', () => {
    const config: PatchbayConfig = {
      id: 'test',
      routes: [
        { from: 'energy', to: 'out.b' },
        { from: 'tension', to: 'out.b' },
      ],
    }
    const patchbay = new Patchbay(config, [targets])
    const resolved = patchbay.resolve(makeBus({ energy: 0.9, tension: 0.9 }), 1 / 60, targets)
    expect(resolved['out.b']).toBe(1.8) // 0.9+0.9, under the [0,2] clamp
  })

  it('a smoothing route eases toward the input rather than snapping', () => {
    const config: PatchbayConfig = {
      id: 'test',
      routes: [{ from: 'energy', to: 'out.a', smoothing: { attackSec: 0.5, releaseSec: 0.5 } }],
    }
    const patchbay = new Patchbay(config, [targets])
    let resolved = patchbay.resolve(makeBus({ energy: 1 }), 0, targets) // dt=0 seeds from first input
    expect(resolved['out.a']).toBe(1)
    resolved = patchbay.resolve(makeBus({ energy: 1 }), 0, targets) // dt=0 again: no further movement possible
    expect(resolved['out.a']).toBe(1)
  })

  it('passThrough routes copy the bus field verbatim, bypassing curve/range/clamp', () => {
    const config: PatchbayConfig = { id: 'test', routes: [{ from: 'scope', to: 'out.scope', passThrough: true }] }
    const patchbay = new Patchbay(config, [targets])
    const scope = new Float32Array([1, 2, 3])
    const resolved = patchbay.resolve(makeBus({ scope }), 1 / 60, targets)
    expect(resolved['out.scope']).toBe(scope)
  })

  it('rejects a route to an unknown target at construction', () => {
    const config: PatchbayConfig = { id: 'test', routes: [{ from: 'energy', to: 'out.nonexistent' }] }
    expect(() => new Patchbay(config, [targets])).toThrow(/unknown target/)
  })
})

describe('Patchbay validation — timescale-tag safety (§5.3)', () => {
  // Screen accepts every tag, so the rejection path can't be exercised
  // against it — validate against the servo target declarations instead
  // (SPEC ONLY, never wired into a runtime output; see servo-targets.ts's
  // header comment). This is the concrete proof R4/R5 hold and the
  // interface generalizes to a second, physically-constrained output
  // without building one.
  it('rejects a transient-tagged signal routed to a servo target', () => {
    const config: PatchbayConfig = { id: 'full-physical', routes: [{ from: 'onsetImpulse', to: 'servo.axis0' }] }
    expect(() => new Patchbay(config, [SERVO_TARGETS])).toThrow(/rejected/)
  })

  it('rejects a beat-tagged signal routed to a servo target', () => {
    const config: PatchbayConfig = { id: 'full-physical', routes: [{ from: 'beatPulse', to: 'servo.axis0' }] }
    expect(() => new Patchbay(config, [SERVO_TARGETS])).toThrow(/rejected/)
  })

  it('accepts a continuous-tagged signal routed to a servo target', () => {
    const config: PatchbayConfig = { id: 'full-physical', routes: [{ from: 'energy', to: 'servo.axis0' }] }
    expect(() => new Patchbay(config, [SERVO_TARGETS])).not.toThrow()
  })

  it('accepts a section-tagged signal routed to a servo target', () => {
    const config: PatchbayConfig = { id: 'full-physical', routes: [{ from: 'buildWindup', to: 'servo.axis1' }] }
    expect(() => new Patchbay(config, [SERVO_TARGETS])).not.toThrow()
  })
})
