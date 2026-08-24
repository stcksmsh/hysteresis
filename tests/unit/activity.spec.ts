import { describe, it, expect } from 'vitest'
import { FullnessTracker, OnsetDensityTracker } from '../../src/audio/worklet/brain/activity'
import { Conductor } from '../../src/render/conductor/Conductor'
import { HOP_SIZE } from '../../src/shared/constants'
import type { StateFrame } from '../../src/shared/types'

const SAMPLE_RATE = 48000
const HOP_MS = (HOP_SIZE / SAMPLE_RATE) * 1000
const HOP_SEC = HOP_MS / 1000

// These are the extracted DropDetector primitives (AGENTS.md §4.2/§4.5 step
// 3) — same math, now reusable so feature-worklet.ts can expose them as
// always-alive bus signals too. drop-detector.spec.ts already proves
// DropDetector's end-to-end behavior is unchanged after the extraction
// (parity, not a rewrite); these tests exercise the trackers directly, in
// isolation, the way a bus-signal consumer would use them.

function runFullness(durationSec: number, lowEnergyAt: (t: number) => number): number {
  const tracker = new FullnessTracker(HOP_MS)
  let fullness = 0
  for (let t = 0; t < durationSec; t += HOP_SEC) {
    ;({ fullness } = tracker.update(lowEnergyAt(t)))
  }
  return fullness
}

describe('FullnessTracker', () => {
  it('reads high for energy sustained continuously over several seconds', () => {
    const fullness = runFullness(6, () => 0.9)
    expect(fullness).toBeGreaterThan(0.5)
  })

  it('reads low for a pulsing source even at the same average level (crest-factor penalty)', () => {
    // A reverb tail pulsing between hits every 0.5s, same as
    // drop-detector.spec.ts's steady-groove fixture — the exact case the
    // fullness primitive exists to reject.
    const fullness = runFullness(6, (t) => (t % 0.5 < 0.1 ? 0.9 : 0.1))
    expect(fullness).toBeLessThan(0.5)
  })

})

describe('OnsetDensityTracker', () => {
  it('jump stays near 0 for a constant onset-activity rate (no jump = no jump)', () => {
    const tracker = new OnsetDensityTracker(HOP_MS)
    let jump = 0
    for (let t = 0; t < 6; t += HOP_SEC) {
      ;({ jump } = tracker.update(0.3))
    }
    expect(Math.abs(jump)).toBeLessThan(0.05)
  })

  it('jump goes positive when onset activity rises after a quiet baseline', () => {
    const tracker = new OnsetDensityTracker(HOP_MS)
    let jump = 0
    for (let t = 0; t < 4; t += HOP_SEC) {
      ;({ jump } = tracker.update(0.02))
    }
    for (let t = 0; t < 2; t += HOP_SEC) {
      ;({ jump } = tracker.update(0.8))
    }
    expect(jump).toBeGreaterThan(0)
  })

  it('rate is a scaled, always-positive-ish reading of onset activity, not just the jump', () => {
    const tracker = new OnsetDensityTracker(HOP_MS)
    let rate = 0
    for (let t = 0; t < 3; t += HOP_SEC) {
      ;({ rate } = tracker.update(0.5))
    }
    expect(rate).toBeGreaterThan(0)
  })
})

describe('fullness/onsetDensity on the Signal Bus (always-alive, not detector-gated)', () => {
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

  it('threads frame.fullness/frame.onsetDensity straight onto the bus, clamped to 0..1', () => {
    const conductor = new Conductor()
    const bus = conductor.update(makeFrame({ fullness: 0.7, onsetDensity: 1.4 }), 1 / 60)
    expect(bus.fullness).toBeCloseTo(0.7)
    expect(bus.onsetDensity).toBe(1) // clamped — the tracker's raw scale can exceed 1
  })

  it('defaults to 0 when the frame has no fullness/onsetDensity at all (sidecar/position-only path)', () => {
    const conductor = new Conductor()
    const bus = conductor.update(makeFrame(), 1 / 60)
    expect(bus.fullness).toBe(0)
    expect(bus.onsetDensity).toBe(0)
  })
})
