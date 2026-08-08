import { describe, it, expect } from 'vitest'
import { Choreographer } from '../../src/render/choreography/Choreographer'
import type { StateFrame, StructuralEvent } from '../../src/shared/types'

function makeFrame(overrides: Partial<StateFrame> = {}): StateFrame {
  return {
    t: 0,
    tempo: 120,
    tempoConfidence: 1,
    beatPhase: 0,
    barPhase: 0,
    buildProgress: 0,
    tension: 0,
    energy: 0,
    bandsRaw: { sub: 0, low: 0, mid: 0, presence: 0, air: 0 },
    centroid: 0,
    flatness: 0,
    pan: 0,
    spectralHits: [],
    events: [],
    scope: null,
    ...overrides,
  }
}

// Drives the choreographer for `seconds` at a fixed dt, feeding the same
// frame shape each tick (mutating `t`); returns the final ParamBus.
function run(choreographer: Choreographer, frame: (t: number) => StateFrame, seconds: number, dt = 1 / 60) {
  const steps = Math.round(seconds / dt)
  let params = choreographer.update(frame(0), 0)
  for (let i = 1; i <= steps; i++) {
    params = choreographer.update(frame(i * dt), dt)
  }
  return params
}

describe('Choreographer — memory field drivers (SINTEZA_VIZ.md §4b/§4d)', () => {
  it('groove/idle settles to short memory, baseline flow, and no symmetry', () => {
    const choreographer = new Choreographer()
    const params = run(choreographer, () => makeFrame(), 2)
    expect(params.fieldDecay).toBeCloseTo(0.86, 1)
    expect(params.flowStrength).toBeCloseTo(1, 0)
    expect(params.symmetry).toBeLessThan(0.05)
  })

  it('a sustained build lengthens memory and raises symmetry ("processing")', () => {
    const choreographer = new Choreographer()
    const params = run(choreographer, (t) => makeFrame({ t, buildProgress: 1, tension: 0.6 }), 3)
    expect(params.fieldDecay).toBeGreaterThan(0.9)
    expect(params.symmetry).toBeGreaterThan(0.3)
    expect(params.flowStrength).toBeGreaterThan(1.5) // "the frame visibly densifies"
  })

  it('a drop snaps symmetry toward full and shocks the flow field, then both release', () => {
    const choreographer = new Choreographer()
    // Settle in a build first, like a real windup would produce.
    const beforeDrop = run(choreographer, (t) => makeFrame({ t, buildProgress: 1, tension: 0.6 }), 2)

    const dropEvent: StructuralEvent = { type: 'drop', strength: 1, t: 2 }
    const atDrop = choreographer.update(makeFrame({ t: 2, buildProgress: 0, tension: 0, events: [dropEvent] }), 1 / 60)
    // The impulse lands on flowStrengthSpring's velocity before this same
    // frame's update() integrates it — so unlike symmetry's eased attack,
    // the shockwave is visible on the very frame the drop fires.
    expect(atDrop.flowStrength).toBeGreaterThan(beforeDrop.flowStrength + 0.3)

    // Everything in this codebase is eased, never a hard binary jump (see
    // SpringDamper's own docstring) — "snaps" means a fast attack toward the
    // target, not an instant step, so this checks the target actually
    // reached 1 and the value is well on its way there within one attack
    // time constant (SYMMETRY_ATTACK_SEC), not that it arrived this tick.
    const afterAttack = run(choreographer, (t) => makeFrame({ t }), 0.5)
    expect(afterAttack.symmetry).toBeGreaterThan(0.9)

    // And well after — past both the hold and the release time constant —
    // both settle back down: "for a bar", not "stuck at full symmetry
    // forever".
    const after = run(choreographer, (t) => makeFrame({ t }), 8)
    expect(after.symmetry).toBeLessThan(0.3)
    expect(after.fieldDecay).toBeCloseTo(0.86, 1)
  })

  it('sustained suspension (a held break) pushes memory to linger further than a build does', () => {
    const choreographer = new Choreographer()
    // tension alone (no buildProgress) drives the slow suspension envelope,
    // modelling a held break — SINTEZA_VIZ.md §3a: "the last drop's trace
    // hangs suspended".
    const params = run(choreographer, (t) => makeFrame({ t, tension: 0.8 }), 6)
    expect(params.fieldDecay).toBeGreaterThan(0.95)
  })
})
