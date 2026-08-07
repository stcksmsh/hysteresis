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

function makeSidecar(overrides: Partial<Sidecar> = {}): Sidecar {
  return {
    schema: 1,
    duration: 20,
    tempo: 128,
    beats: [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4],
    sections: [{ start: 4, end: 8, kind: 'build' }],
    events: [
      { type: 'drop', t: 8, strength: 1 },
      { type: 'breakStart', t: 10, strength: 0.9 },
      { type: 'breakEnd', t: 12, strength: 0.1 },
    ],
    energyEnvelope: [],
    envelopeRate: 20,
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
})
