import { describe, it, expect } from 'vitest'
import { StructureSource } from '../../src/audio/StructureSource'
import type { Sidecar } from '../../src/shared/sidecar'
import type { StateFrame } from '../../src/shared/types'

function liveFrame(t: number, overrides: Partial<StateFrame> = {}): StateFrame {
  return {
    t,
    tempo: 100,
    tempoConfidence: 0,
    beatPhase: 0.5,
    barPhase: 0.5,
    buildProgress: 0,
    tension: 0,
    energy: 0.4,
    bandsRaw: { sub: 0, low: 0, mid: 0, presence: 0, air: 0 },
    centroid: 0.2,
    flatness: 0.3,
    pan: 0,
    spectralHits: [],
    events: [],
    scope: null,
    ...overrides,
  }
}

// Flat envelopes at a low rate (2Hz over the 20s test duration = 40 samples)
// are enough to exercise sampleEnvelope's interpolation without needing a
// real analysis run — individual synthesize() tests override specific
// envelopes/onsets where the value matters.
const ENVELOPE_LENGTH = 40
const ENVELOPE_RATE = 2
function flatEnvelope(value: number): number[] {
  return new Array(ENVELOPE_LENGTH).fill(value)
}

function makeSidecar(overrides: Partial<Sidecar> = {}): Sidecar {
  return {
    schema: 2,
    duration: 20,
    tempo: 128,
    beats: [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4],
    sections: [{ start: 4, end: 8, kind: 'build' }],
    events: [
      { type: 'drop', t: 8, strength: 1 },
      { type: 'breakStart', t: 10, strength: 0.9 },
      { type: 'breakEnd', t: 12, strength: 0.1 },
    ],
    onsets: [],
    energyEnvelope: flatEnvelope(0),
    bandEnvelope: {
      sub: flatEnvelope(0),
      low: flatEnvelope(0),
      mid: flatEnvelope(0),
      presence: flatEnvelope(0),
      air: flatEnvelope(0),
    },
    centroidEnvelope: flatEnvelope(0),
    flatnessEnvelope: flatEnvelope(0),
    envelopeRate: ENVELOPE_RATE,
    ...overrides,
  }
}

describe('StructureSource', () => {
  it('passes the live frame through unchanged when nothing is loaded', () => {
    const source = new StructureSource()
    const frame = liveFrame(1)
    expect(source.fuse(frame, 1)).toBe(frame)
    expect(source.active).toBe(false)
  })

  it('overrides tempo/beatPhase/barPhase from the sidecar beat grid once loaded', () => {
    const source = new StructureSource()
    source.load(makeSidecar())
    const fused = source.fuse(liveFrame(1.75), 1.75) // between beats[3]=1.5 and beats[4]=2
    expect(fused.tempo).toBe(128)
    expect(fused.tempoConfidence).toBe(1)
    expect(fused.beatPhase).toBeCloseTo(0.5, 5)
  })

  it('ramps buildProgress across a build section and holds 0 outside it', () => {
    const source = new StructureSource()
    source.load(makeSidecar())
    expect(source.fuse(liveFrame(2), 2).buildProgress).toBe(0) // before the build section
    expect(source.fuse(liveFrame(6), 6).buildProgress).toBeGreaterThan(0)
    expect(source.fuse(liveFrame(6), 6).buildProgress).toBeLessThan(1)
    expect(source.fuse(liveFrame(9), 9).buildProgress).toBe(0) // after it ends
  })

  it('emits each structural event exactly once as the clock advances past it', () => {
    const source = new StructureSource()
    source.load(makeSidecar())
    const seen = source.fuse(liveFrame(7.9), 7.9).events
    expect(seen.some((e) => e.type === 'drop')).toBe(false)

    const atDrop = source.fuse(liveFrame(8.1), 8.1).events
    expect(atDrop.filter((e) => e.type === 'drop')).toHaveLength(1)

    const afterDrop = source.fuse(liveFrame(8.2), 8.2).events
    expect(afterDrop.filter((e) => e.type === 'drop')).toHaveLength(0)
  })

  it('keeps live onset events alongside sidecar structural events', () => {
    const source = new StructureSource()
    source.load(makeSidecar())
    const frame = liveFrame(1, { events: [{ type: 'onset', t: 1, strength: 0.7 }] })
    const fused = source.fuse(frame, 1)
    expect(fused.events.some((e) => e.type === 'onset')).toBe(true)
  })

  it('resyncTo skips already-passed events instead of replaying them after a seek', () => {
    const source = new StructureSource()
    source.load(makeSidecar())
    source.resyncTo(9) // seek past the drop at t=8
    const fused = source.fuse(liveFrame(9), 9)
    expect(fused.events.some((e) => e.type === 'drop')).toBe(false)
  })

  it('clear() reverts to passthrough', () => {
    const source = new StructureSource()
    source.load(makeSidecar())
    source.clear()
    expect(source.active).toBe(false)
    const frame = liveFrame(1)
    expect(source.fuse(frame, 1)).toBe(frame)
  })

  describe('synthesize() — position-only mode (no live audio)', () => {
    it('throws with no sidecar loaded', () => {
      const source = new StructureSource()
      expect(() => source.synthesize(1)).toThrow()
    })

    it('marks the frame idle (keeps the beam animating with no real waveform) while structure stays real', () => {
      const source = new StructureSource()
      source.load(makeSidecar())
      const frame = source.synthesize(6) // inside the build section
      expect(frame.idle).toBe(true)
      expect(frame.scope).toBeNull()
      expect(frame.buildProgress).toBeGreaterThan(0)
      expect(frame.tempo).toBe(128)
    })

    it('interpolates band/centroid/flatness/energy envelopes at the given position', () => {
      const source = new StructureSource()
      source.load(
        makeSidecar({
          bandEnvelope: {
            sub: flatEnvelope(0.2),
            low: flatEnvelope(0.1),
            mid: flatEnvelope(0),
            presence: flatEnvelope(0),
            air: flatEnvelope(0),
          },
          centroidEnvelope: flatEnvelope(0.3),
          flatnessEnvelope: flatEnvelope(0.7),
          energyEnvelope: flatEnvelope(0.5),
        }),
      )
      const frame = source.synthesize(3)
      expect(frame.bandsRaw.sub).toBeCloseTo(0.2, 5)
      expect(frame.bandsRaw.low).toBeCloseTo(0.1, 5)
      expect(frame.centroid).toBeCloseTo(0.3, 5)
      expect(frame.flatness).toBeCloseTo(0.7, 5)
      expect(frame.energy).toBeCloseTo(0.5, 5)
    })

    it('emits each onset exactly once as position advances past it, as a spectralHit', () => {
      const source = new StructureSource()
      source.load(makeSidecar({ onsets: [{ t: 5, strength: 0.8, tone: 0.1, pan: -0.4 }] }))

      expect(source.synthesize(4.9).spectralHits).toHaveLength(0)
      const atOnset = source.synthesize(5.1).spectralHits
      expect(atOnset).toHaveLength(1)
      expect(atOnset[0]).toEqual({ tone: 0.1, pan: -0.4, strength: 0.8 })
      expect(source.synthesize(5.2).spectralHits).toHaveLength(0)
    })

    it('still fires structural events (drop) from the sidecar timeline', () => {
      const source = new StructureSource()
      source.load(makeSidecar())
      expect(source.synthesize(7.9).events.some((e) => e.type === 'drop')).toBe(false)
      expect(source.synthesize(8.1).events.some((e) => e.type === 'drop')).toBe(true)
    })

    it('resyncTo skips already-passed onsets after a seek, same as events', () => {
      const source = new StructureSource()
      source.load(makeSidecar({ onsets: [{ t: 5, strength: 0.8, tone: 0.1, pan: -0.4 }] }))
      source.resyncTo(6) // seek past the onset at t=5
      expect(source.synthesize(6).spectralHits).toHaveLength(0)
    })
  })
})
