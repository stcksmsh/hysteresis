import { describe, it, expect } from 'vitest'
import { FamiliarityTracker, computeFamiliarity } from '../../src/render/conductor/familiarity'
import type { StateFrame } from '../../src/shared/types'

function makeFrame(t: number, overrides: Partial<StateFrame> = {}): StateFrame {
  return {
    t,
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

describe('familiarity (SINTEZA_SIGNAL_BUS.md §4.2)', () => {
  it('reads low the first few seconds — nothing to be similar to yet', () => {
    const tracker = new FamiliarityTracker()
    let familiarity = 0
    for (let t = 0; t < 0.4; t += 1 / 60) {
      familiarity = computeFamiliarity(tracker, makeFrame(t, { bandsRaw: { sub: 0.5, low: 0.5, mid: 0.5, presence: 0.5, air: 0.5 } }), 1 / 60)
    }
    expect(familiarity).toBe(0)
  })

  it('rises when the same material keeps repeating (a loop/motif)', () => {
    const tracker = new FamiliarityTracker()
    const loopVec = { sub: 0.6, low: 0.5, mid: 0.4, presence: 0.3, air: 0.2 }
    let familiarity = 0
    for (let t = 0; t < 6; t += 1 / 30) {
      familiarity = computeFamiliarity(tracker, makeFrame(t, { bandsRaw: loopVec, centroid: 0.5, flatness: 0.3 }), 1 / 30)
    }
    expect(familiarity).toBeGreaterThan(0.9)
  })

  it('drops when genuinely novel material arrives after a settled loop', () => {
    const tracker = new FamiliarityTracker()
    const loopVec = { sub: 0.8, low: 0.7, mid: 0.1, presence: 0.05, air: 0.02 }
    const novelVec = { sub: 0.02, low: 0.02, mid: 0.1, presence: 0.8, air: 0.9 }
    for (let t = 0; t < 6; t += 1 / 30) {
      computeFamiliarity(tracker, makeFrame(t, { bandsRaw: loopVec, centroid: 0.1, flatness: 0.1 }), 1 / 30)
    }
    const familiarity = computeFamiliarity(tracker, makeFrame(6, { bandsRaw: novelVec, centroid: 0.9, flatness: 0.9 }), 1 / 30)
    expect(familiarity).toBeLessThan(0.5)
  })

  it('evicts samples older than the window instead of growing unbounded', () => {
    const tracker = new FamiliarityTracker()
    for (let t = 0; t < 60; t += 1 / 30) {
      computeFamiliarity(tracker, makeFrame(t, { bandsRaw: { sub: 0.5, low: 0.5, mid: 0.5, presence: 0.5, air: 0.5 } }), 1 / 30)
    }
    // 60s of 1/30s-spaced samples is 1800 — the buffer must have evicted down
    // to roughly the window size, not kept everything.
    expect(tracker.size).toBeLessThan(600)
  })
})
