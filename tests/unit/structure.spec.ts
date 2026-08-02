import { describe, it, expect } from 'vitest'
import { detectDropsFromStems, detectBreaksFromStems, synthesizeBuildCurve } from '../../tools/compile/structure'
import type { TempoMarker } from '../../src/shared/timeline'

function makeEnvelope(rate: number, duration: number, levelAt: (t: number) => number): Uint8Array {
  const n = Math.ceil(duration * rate)
  const out = new Uint8Array(n)
  for (let i = 0; i < n; i++) out[i] = Math.round(Math.max(0, Math.min(1, levelAt(i / rate))) * 255)
  return out
}

describe('detectDropsFromStems', () => {
  const rate = 10
  const duration = 10

  it('detects a drop where multiple stems jump together', () => {
    const jumpAt = 5
    const kick = makeEnvelope(rate, duration, (t) => (t < jumpAt ? 0.1 : 0.9))
    const bass = makeEnvelope(rate, duration, (t) => (t < jumpAt ? 0.15 : 0.85))
    const drops = detectDropsFromStems([kick, bass], rate, duration)
    expect(drops.length).toBeGreaterThan(0)
    expect(Math.abs(drops[0].t - jumpAt)).toBeLessThan(1)
    expect(drops[0].strength).toBeGreaterThan(0)
  })

  it('does not fire when only one of several stems jumps', () => {
    const jumpAt = 5
    const kick = makeEnvelope(rate, duration, (t) => (t < jumpAt ? 0.1 : 0.9))
    const steady = makeEnvelope(rate, duration, () => 0.2)
    const drops = detectDropsFromStems([kick, steady], rate, duration, { minCoincidence: 2 })
    expect(drops).toHaveLength(0)
  })
})

describe('detectBreaksFromStems', () => {
  const rate = 10
  const duration = 10

  it('finds a two-sided low-activity span with both edges', () => {
    const lowStart = 3
    const lowEnd = 7
    const stem = makeEnvelope(rate, duration, (t) => (t >= lowStart && t < lowEnd ? 0.05 : 0.8))
    const events = detectBreaksFromStems([stem], rate, duration, { activityFloor: 0.35, minBreakSec: 1 })
    const starts = events.filter((e) => e.type === 'breakStart')
    const ends = events.filter((e) => e.type === 'breakEnd')
    expect(starts).toHaveLength(1)
    expect(ends).toHaveLength(1)
    expect(Math.abs(starts[0].t - lowStart)).toBeLessThan(0.5)
    expect(Math.abs(ends[0].t - lowEnd)).toBeLessThan(0.5)
  })

  it('ignores a dip shorter than the minimum break duration', () => {
    const stem = makeEnvelope(rate, duration, (t) => (t >= 5 && t < 5.2 ? 0.05 : 0.8))
    const events = detectBreaksFromStems([stem], rate, duration, { activityFloor: 0.35, minBreakSec: 2 })
    expect(events).toHaveLength(0)
  })
})

describe('synthesizeBuildCurve', () => {
  const tempoMap: TempoMarker[] = [{ t: 0, bpm: 120, num: 4, den: 4 }]

  it('peaks at exactly 1 at the drop time, and is 0 well before it', () => {
    const rate = 10
    const duration = 15
    const dropAt = 10
    const { curve } = synthesizeBuildCurve([dropAt], tempoMap, duration, rate, 8)
    const dropIndex = Math.round(dropAt * rate)
    expect(curve[dropIndex]).toBe(255)
    expect(curve[0]).toBe(0)
  })

  it('is monotonically non-decreasing across the ramp into a drop', () => {
    const rate = 10
    const duration = 15
    const dropAt = 10
    const { curve } = synthesizeBuildCurve([dropAt], tempoMap, duration, rate, 8)
    const dropIndex = Math.round(dropAt * rate)
    for (let i = 1; i <= dropIndex; i++) {
      expect(curve[i]).toBeGreaterThanOrEqual(curve[i - 1])
    }
  })

  it('does not let one drop\'s ramp start before the previous drop', () => {
    const rate = 10
    const duration = 20
    const { curve, windows } = synthesizeBuildCurve([5, 6], tempoMap, duration, rate, 8)
    expect(windows[1].start).toBeGreaterThanOrEqual(5)
    // Second drop's own value is still a clean peak, unclobbered by overlap.
    expect(curve[Math.round(6 * rate)]).toBe(255)
  })
})
