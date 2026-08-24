import { describe, it, expect } from 'vitest'
import { Conductor } from '../../src/render/conductor/Conductor'
import type { StateFrame } from '../../src/shared/types'

function makeFrame(t: number, beatPhase: number, overrides: Partial<StateFrame> = {}): StateFrame {
  return {
    t,
    tempo: 120,
    tempoConfidence: 1,
    beatPhase,
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

// Drives a Conductor through a click-train of beat boundaries (beatPhase
// sawtooth 0->1, wrapping every `beatPeriodSec`), several render frames per
// beat, so beat-boundary edges are actually crossed the way real playback
// would — unlike a fixed beatPhase, which (correctly) never triggers a push.
// The similarity trackers sample exactly once per beat (at each beat's
// first frame, phase 0, which is where the wraparound crossing lands).
function driveBeats(
  conductor: Conductor,
  beats: number,
  beatPeriodSec: number,
  framesPerBeat: number,
  vecAt: (beatIndex: number) => Partial<StateFrame>,
) {
  const dt = beatPeriodSec / framesPerBeat
  let t = 0
  // Seed lastBeatPhase near the end of a beat cycle so beat 0's very first
  // frame (phase 0) registers as a real boundary crossing, not a no-op
  // (both start at 0, which would never satisfy the "wrapped" check).
  let bus = conductor.update(makeFrame(t, (framesPerBeat - 1) / framesPerBeat, vecAt(0)), dt)
  for (let beat = 0; beat < beats; beat++) {
    for (let f = 0; f < framesPerBeat; f++) {
      t += dt
      const beatPhase = f / framesPerBeat
      bus = conductor.update(makeFrame(t, beatPhase, vecAt(beat)), dt)
    }
  }
  return bus
}

describe('multi-scale novelty (noveltyLocal/noveltySection, beat-synchronous)', () => {
  it('reacts to a sudden vector change while familiarity/noveltySection has not built up yet — both trackers agree at first', () => {
    const conductor = new Conductor()
    const bus = driveBeats(conductor, 1, 0.5, 4, () => ({
      bandsRaw: { sub: 0.5, low: 0.5, mid: 0.5, presence: 0.5, air: 0.5 },
    }))
    // Nothing has been seen before the very first sample in either buffer,
    // so both read novel (0 familiarity / max novelty) at the very start.
    expect(bus.noveltySection).toBeGreaterThan(0.9)
    expect(bus.noveltyLocal).toBeGreaterThan(0.9)
  })

  it('the short window forgets a motif faster than the long one — the real point of two timescales', () => {
    const conductor = new Conductor()
    const motifA = { sub: 0.8, low: 0.1, mid: 0.05, presence: 0.02, air: 0.01 }
    const motifB = { sub: 0.05, low: 0.1, mid: 0.2, presence: 0.7, air: 0.6 }
    // One continuous timeline (driveBeats resets its own clock per call, so
    // the whole A/B/A sequence must be one call — beat 0-5: motif A (3s,
    // inside both windows). Beat 6-19: motif B (7s — long enough that A's
    // last sample, ~7s old by the end, has fallen out of the short ~5s
    // window but is still inside the long ~12s one). Beat 20: motif A
    // again — the short tracker's buffer now holds only recent motif-B
    // samples (unfamiliar -> high noveltyLocal); the long tracker's buffer
    // still holds motif-A samples from ~7s ago (familiar -> low noveltySection).
    const bus = driveBeats(conductor, 21, 0.5, 4, (beat) => ({
      bandsRaw: beat >= 6 && beat < 20 ? motifB : motifA,
      centroid: beat >= 6 && beat < 20 ? 0.8 : 0.2,
      flatness: beat >= 6 && beat < 20 ? 0.7 : 0.1,
    }))
    expect(bus.noveltyLocal).toBeGreaterThan(0.5)
    expect(bus.noveltySection).toBeLessThan(bus.noveltyLocal)
  })

  it('noveltySection matches 1 - familiarity exactly (same computation read two ways)', () => {
    const conductor = new Conductor()
    const bus = driveBeats(conductor, 4, 0.5, 4, () => ({
      bandsRaw: { sub: 0.4, low: 0.3, mid: 0.2, presence: 0.1, air: 0.05 },
      centroid: 0.4,
      flatness: 0.2,
    }))
    expect(bus.noveltySection).toBeCloseTo(1 - bus.familiarity, 10)
  })

  it('does not push a new sample between beat boundaries — dense per-frame novelty at a fixed beatPhase stays flat', () => {
    const conductor = new Conductor()
    // beatPhase pinned at 0 for every call: no boundary is ever crossed
    // (matches how the beat tracker holds phase during silence/no lock),
    // so both trackers should never accumulate anything and stay at their
    // initial "nothing to compare against yet" reading regardless of how
    // much distinct material streams past.
    let bus = conductor.update(makeFrame(0, 0, { bandsRaw: { sub: 0.1, low: 0, mid: 0, presence: 0, air: 0 } }), 1 / 30)
    for (let t = 1; t < 300; t++) {
      bus = conductor.update(
        makeFrame(t / 30, 0, { bandsRaw: { sub: (t % 7) / 7, low: 0, mid: 0, presence: 0, air: 0 } }),
        1 / 30,
      )
    }
    expect(bus.familiarity).toBe(0)
    expect(bus.noveltySection).toBe(1)
    expect(bus.noveltyLocal).toBe(1)
  })
})
