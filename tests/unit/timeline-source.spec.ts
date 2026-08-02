import { describe, it, expect } from 'vitest'
import { TimelineSource } from '../../src/audio/TimelineSource'
import type { Timeline } from '../../src/shared/timeline'
import type { StateFrame } from '../../src/shared/types'

function encodeEnvelope(values: number[]): string {
  let binary = ''
  for (const v of values) binary += String.fromCharCode(v)
  return btoa(binary)
}

// Two stems over 2s at 10Hz envelope rate: a low "kick" pulsing every 0.5s,
// a bright "hat" pulsing offset by 0.2s, panned hard right — mirrors the
// synthetic fixture shape used in tests/unit/compile.spec.ts.
function makeTimeline(): Timeline {
  const rate = 10
  const samples = 20
  const kickLevel = Array.from({ length: samples }, (_, i) => (i % 5 === 0 ? 200 : 15))
  const kickTone = Array.from({ length: samples }, () => 30)
  const hatLevel = Array.from({ length: samples }, (_, i) => (i % 5 === 2 ? 180 : 10))
  const hatTone = Array.from({ length: samples }, () => 220)

  return {
    version: 1,
    duration: 2,
    tempoMap: [{ t: 0, bpm: 120, num: 4, den: 4 }],
    markers: [],
    tracks: [
      { name: 'Kick', pan: 0, tone: 0.1 },
      { name: 'Hat', pan: 0.8, tone: 0.9 },
    ],
    events: [
      { t: 0.5, track: 0, level: 0.9, tone: 0.1, pan: 0 },
      { t: 1.0, track: 1, level: 0.7, tone: 0.9, pan: 0.8 },
      { t: 1.5, track: 0, level: 0.85, tone: 0.1, pan: 0 },
    ],
    envelopes: {
      rate,
      tracks: [
        { level: encodeEnvelope(kickLevel), tone: encodeEnvelope(kickTone) },
        { level: encodeEnvelope(hatLevel), tone: encodeEnvelope(hatTone) },
      ],
    },
  }
}

describe('TimelineSource', () => {
  it('emits StateFrames with non-decreasing t for a monotonic clock', () => {
    const timeline = makeTimeline()
    let now = 0
    const source = new TimelineSource(timeline, () => now)
    const frames: StateFrame[] = []
    source.onStateFrame((f) => frames.push(f))
    for (let i = 0; i < 20; i++) {
      now += 0.1
      source.tick()
    }
    for (let i = 1; i < frames.length; i++) {
      expect(frames[i].t).toBeGreaterThanOrEqual(frames[i - 1].t)
    }
  })

  it('delivers every baked event exactly once, none dropped or duplicated', () => {
    const timeline = makeTimeline()
    let now = 0
    const source = new TimelineSource(timeline, () => now)
    const seenTimes: number[] = []
    source.onStateFrame((f) => {
      for (const e of f.events) seenTimes.push(e.t)
    })
    for (let i = 0; i < 20; i++) {
      now += 0.1
      source.tick()
    }
    expect(seenTimes).toEqual([0.5, 1.0, 1.5])
  })

  it('does not re-emit an event when ticked again at the same time', () => {
    const timeline = makeTimeline()
    let now = 0.5
    const source = new TimelineSource(timeline, () => now)
    let eventCount = 0
    source.onStateFrame((f) => {
      eventCount += f.events.length
    })
    source.tick()
    source.tick()
    source.tick()
    expect(eventCount).toBe(0) // window [0, 0.5) never includes t=0.5 itself
  })

  it('reads tempo/beat phase from the tempo map, not from integration', () => {
    const timeline = makeTimeline()
    const source = new TimelineSource(timeline, () => 1.0)
    let frame: StateFrame | null = null
    source.onStateFrame((f) => (frame = f))
    source.tick()
    expect(frame!.tempo).toBe(120)
    // 1.0s at 120bpm = 2 beats elapsed exactly -> phase 0.
    expect(frame!.beatPhase).toBeCloseTo(0, 5)
  })

  it('reconstructs energy/pan from per-track envelopes when a stem is active', () => {
    const timeline = makeTimeline()
    // Sample index 0 of both envelopes: kick loud+low, hat quiet.
    const source = new TimelineSource(timeline, () => 0)
    let frame: StateFrame | null = null
    source.onStateFrame((f) => (frame = f))
    source.tick()
    expect(frame!.energy).toBeGreaterThan(0)
    expect(frame!.bandsRaw.sub + frame!.bandsRaw.low).toBeGreaterThan(frame!.bandsRaw.air)
  })
})
