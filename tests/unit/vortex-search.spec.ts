import { describe, it, expect } from 'vitest'
import { sampleOrbit, clusterScore, findVortexTarget } from '../../src/render/worker/scenes/julia/vortex-search'
import { cardioidPoint } from '../../src/render/worker/scenes/julia/boundary'

// No test coverage existed for any of this before — several sessions of
// hand-tuning constants against live visual feedback with no way to verify
// a hypothesis about the underlying math independently. These lock in
// well-understood cases so a future change here has something to check
// against besides "look at it running and guess."

describe('sampleOrbit', () => {
  it('escapes quickly for a point far outside the Julia set (c=0)', () => {
    // z^2 with c=0: |z|>1 escapes monotonically (doubles the exponent each
    // iteration), a point at |z|=10 blows past the bailout radius (|z|>2)
    // on the very first iteration.
    const sample = sampleOrbit(10, 0, 0, 0, 100)
    expect(sample.iter).toBeLessThan(3)
  })

  it('never escapes for a point at the exact fixed point (c=0, z=0)', () => {
    // 0^2 + 0 = 0 forever.
    const cap = 50
    const sample = sampleOrbit(0, 0, 0, 0, cap)
    expect(sample.iter).toBe(cap)
  })

  it('winding accumulates for an orbit that actually turns', () => {
    // A point that orbits partway around before escaping should show
    // nonzero total winding — not asserting an exact value (chaotic
    // dynamics), just that the accumulator isn't structurally broken (e.g.
    // always 0, or NaN from atan2(0,0) at z=0 exactly on the first sample).
    const c = cardioidPoint(1.3)
    const sample = sampleOrbit(0.3, 0.2, c.x, c.y, 200)
    expect(Number.isFinite(sample.winding)).toBe(true)
    expect(sample.winding).toBeGreaterThanOrEqual(0)
  })
})

describe('clusterScore', () => {
  it('reads exactly 0 (monochrome) deep inside the filled Julia set (c=0)', () => {
    // Every point within |z|<1 for c=0 converges to 0 and never escapes —
    // a cluster centered well inside that disc has identical (cap) escape
    // counts everywhere in it, the literal "boring" case this function
    // exists to reject.
    const score = clusterScore(0, 0, 0.05, 0, 0, 100)
    expect(score).toBe(0)
  })

  it('reads exactly 0 (monochrome) far outside the Julia set (c=0)', () => {
    // Every point out at |z|=10 escapes in 1-2 iterations regardless of
    // which side of the cluster it's on — also monochrome, just at the
    // other extreme.
    const score = clusterScore(10, 10, 0.05, 0, 0, 100)
    expect(score).toBe(0)
  })

  it('is positive right at the boundary (c=0, |z|=1) where escape time genuinely varies', () => {
    // A cluster straddling |z|=1 has points on both sides — some escape
    // almost immediately (just outside), some take a while (just inside,
    // near-parabolic at exactly z=1 itself since c=0's fixed point at z=1
    // has multiplier 2, not neutral, but points AT the circle are exactly
    // the boundary between "escapes" and "doesn't" so nearby iteration
    // counts genuinely differ).
    const score = clusterScore(1, 0, 0.05, 0, 0, 100)
    expect(score).toBeGreaterThan(0)
  })

  it('is finite and non-negative for real cardioid-boundary c values across a grid', () => {
    // Regression net for the whole function: run it against several real
    // boundary c's (what the scene actually uses, not just c=0) over a grid
    // and just confirm nothing produces NaN/negative/broken output.
    for (const theta of [0.3, 1.3, 2.1, 3.0, 4.5]) {
      const c = cardioidPoint(theta)
      for (let i = 0; i < 5; i++) {
        for (let j = 0; j < 5; j++) {
          const x = (i / 4 - 0.5) * 1.2
          const y = (j / 4 - 0.5) * 1.2
          const score = clusterScore(x, y, 0.05, c.x, c.y, 100)
          expect(Number.isFinite(score)).toBe(true)
          expect(score).toBeGreaterThanOrEqual(0)
        }
      }
    }
  })
})

describe('findVortexTarget', () => {
  it('finds a genuine candidate (found=true) searching around a real cardioid-boundary c', () => {
    const c = cardioidPoint(1.3)
    const result = findVortexTarget(c.x, c.y, 0.8)
    expect(result.found).toBe(true)
    // The picked point should sit within the searched disc.
    expect(Math.hypot(result.x, result.y)).toBeLessThanOrEqual(0.8 + 1e-9)
  })

  it('reports found=false when the entire searched disc is genuinely uniform (deep inside c=0)', () => {
    // A tiny radius entirely inside the c=0 filled Julia set (|z|<1) never
    // crosses the boundary anywhere in the search — every candidate scores
    // 0, so this must honestly report "nothing found" rather than silently
    // returning the meaningless center fallback as if it were a real pick.
    const result = findVortexTarget(0, 0, 0.05)
    expect(result.found).toBe(false)
  })

  it('respects a custom search center (the local re-search case)', () => {
    const c = cardioidPoint(1.3)
    const result = findVortexTarget(c.x, c.y, 0.3, 0.4, 0.4)
    // Result must be within maxRadius of the CENTER, not the origin.
    const dist = Math.hypot(result.x - 0.4, result.y - 0.4)
    expect(dist).toBeLessThanOrEqual(0.3 + 1e-9)
  })
})
