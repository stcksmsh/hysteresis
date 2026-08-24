import { describe, it, expect } from 'vitest'
import { computeChroma, dominantPitchClassHue, CHROMA_BINS } from '../../src/audio/worklet/chroma'
import { Conductor } from '../../src/render/conductor/Conductor'
import type { StateFrame } from '../../src/shared/types'

const SAMPLE_RATE = 48000
const FFT_SIZE = 2048
const BINS = FFT_SIZE / 2 + 1
const BIN_HZ = SAMPLE_RATE / FFT_SIZE

// A synthetic magnitude spectrum with all its energy in the single bin
// closest to `freqHz` — no need to run a real FFT to test chroma's own
// bin->pitch-class folding math in isolation.
function pureToneMags(freqHz: number): Float32Array {
  const mags = new Float32Array(BINS)
  const bin = Math.round(freqHz / BIN_HZ)
  mags[bin] = 1
  return mags
}

describe('computeChroma', () => {
  it('folds a pure A4 (440Hz) tone into pitch class 9 (A)', () => {
    const out = new Float32Array(CHROMA_BINS)
    computeChroma(pureToneMags(440), SAMPLE_RATE, FFT_SIZE, out)
    let best = 0
    for (let i = 1; i < CHROMA_BINS; i++) if (out[i] > out[best]) best = i
    expect(best).toBe(9)
    expect(out[9]).toBeCloseTo(1, 5) // sum-normalized, all energy in one bin -> that class reads 1
  })

  it('folds a pure C (~261.63Hz, C4) tone into pitch class 0 (C)', () => {
    const out = new Float32Array(CHROMA_BINS)
    computeChroma(pureToneMags(261.63), SAMPLE_RATE, FFT_SIZE, out)
    let best = 0
    for (let i = 1; i < CHROMA_BINS; i++) if (out[i] > out[best]) best = i
    expect(best).toBe(0)
  })

  it('returns an all-zero vector for a silent spectrum', () => {
    const out = new Float32Array(CHROMA_BINS)
    computeChroma(new Float32Array(BINS), SAMPLE_RATE, FFT_SIZE, out)
    expect(Array.from(out)).toEqual(new Array(CHROMA_BINS).fill(0))
  })
})

describe('dominantPitchClassHue', () => {
  it('maps the dominant pitch class to a 0..1 hue-ready value', () => {
    const chroma = new Float32Array(CHROMA_BINS)
    chroma[9] = 0.8 // A
    chroma[0] = 0.1
    expect(dominantPitchClassHue(chroma)).toBeCloseTo(9 / 12, 10)
  })
})

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

// Same beat-driving helper as novelty-multiscale.spec.ts — the similarity
// trackers (including harmonicNovelty's) only sample on a beat-boundary edge.
function driveBeats(
  conductor: Conductor,
  beats: number,
  beatPeriodSec: number,
  framesPerBeat: number,
  chromaAt: (beatIndex: number) => Float32Array,
) {
  const dt = beatPeriodSec / framesPerBeat
  let t = 0
  let bus = conductor.update(makeFrame(t, (framesPerBeat - 1) / framesPerBeat, { chroma: chromaAt(0) }), dt)
  for (let beat = 0; beat < beats; beat++) {
    for (let f = 0; f < framesPerBeat; f++) {
      t += dt
      const beatPhase = f / framesPerBeat
      bus = conductor.update(makeFrame(t, beatPhase, { chroma: chromaAt(beat) }), dt)
    }
  }
  return bus
}

function chromaAtClass(pc: number): Float32Array {
  const chroma = new Float32Array(CHROMA_BINS)
  chroma[pc] = 1
  return chroma
}

describe('harmonicNovelty on the Signal Bus', () => {
  it('is alive on the very first sample (nothing to compare against yet)', () => {
    const conductor = new Conductor()
    const bus = driveBeats(conductor, 1, 0.5, 4, () => chromaAtClass(0))
    expect(bus.harmonicNovelty).toBeGreaterThan(0.9)
  })

  it('settles low once the same chord/key repeats for a while', () => {
    const conductor = new Conductor()
    const bus = driveBeats(conductor, 8, 0.5, 4, () => chromaAtClass(0))
    expect(bus.harmonicNovelty).toBeLessThan(0.2)
  })

  it('spikes on a real key change after settling', () => {
    const conductor = new Conductor()
    const bus = driveBeats(conductor, 9, 0.5, 4, (beat) => chromaAtClass(beat < 8 ? 0 : 7)) // C -> G, beat 8
    expect(bus.harmonicNovelty).toBeGreaterThan(0.8)
  })

  it('chromaRootHue tracks the current dominant pitch class every frame (not beat-gated)', () => {
    const conductor = new Conductor()
    const bus = conductor.update(makeFrame(0, 0, { chroma: chromaAtClass(9) }), 1 / 60)
    expect(bus.chromaRootHue).toBeCloseTo(9 / 12, 10)
  })
})
