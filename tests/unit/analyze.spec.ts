import { describe, it, expect } from 'vitest'
import { analyzeMix } from '../../scripts/structure'
import type { DecodedWav } from '../../scripts/wav'

const SAMPLE_RATE = 48000

// Synthetic "kick train": a short decaying low-frequency burst on a fixed
// grid, silence between — deterministic and DAW-independent, exactly the
// single-WAV-master case the offline tool (SINTEZA_VIZ.md §6) targets.
function makeKickTrain(bpm: number, durationSec: number): DecodedWav {
  const n = Math.floor(durationSec * SAMPLE_RATE)
  const data = new Float32Array(n)
  const periodSamples = Math.round((60 / bpm) * SAMPLE_RATE)
  const burstSamples = Math.round(0.08 * SAMPLE_RATE)
  for (let i = 0; i < n; i++) {
    const phase = i % periodSamples
    if (phase < burstSamples) {
      const decay = Math.exp(-phase / (burstSamples * 0.3))
      data[i] = Math.sin((2 * Math.PI * 60 * phase) / SAMPLE_RATE) * decay
    }
  }
  return { sampleRate: SAMPLE_RATE, channels: [data], duration: durationSec }
}

describe('analyzeMix', () => {
  it('produces a schema-2 sidecar with the right duration', () => {
    const wav = makeKickTrain(120, 10)
    const sidecar = analyzeMix(wav)
    expect(sidecar.schema).toBe(2)
    expect(sidecar.duration).toBeCloseTo(10, 1)
    expect(sidecar.envelopeRate).toBeGreaterThan(0)
    expect(sidecar.energyEnvelope.length).toBeGreaterThan(0)
  })

  it('emits per-band/centroid/flatness envelopes the same length as energyEnvelope', () => {
    const wav = makeKickTrain(120, 10)
    const sidecar = analyzeMix(wav)
    const n = sidecar.energyEnvelope.length
    expect(sidecar.bandEnvelope.sub.length).toBe(n)
    expect(sidecar.bandEnvelope.low.length).toBe(n)
    expect(sidecar.bandEnvelope.mid.length).toBe(n)
    expect(sidecar.bandEnvelope.presence.length).toBe(n)
    expect(sidecar.bandEnvelope.air.length).toBe(n)
    expect(sidecar.centroidEnvelope.length).toBe(n)
    expect(sidecar.flatnessEnvelope.length).toBe(n)
    for (const arr of [sidecar.bandEnvelope.sub, sidecar.centroidEnvelope, sidecar.flatnessEnvelope]) {
      for (const v of arr) {
        expect(Number.isFinite(v)).toBe(true)
        expect(v).toBeGreaterThanOrEqual(0)
        expect(v).toBeLessThanOrEqual(1)
      }
    }
  })

  it('detects onsets on a kick train and tags each with a low-band tone', () => {
    const wav = makeKickTrain(120, 10)
    const sidecar = analyzeMix(wav)
    expect(sidecar.onsets.length).toBeGreaterThan(3)
    for (const onset of sidecar.onsets) {
      expect(onset.t).toBeGreaterThanOrEqual(0)
      expect(onset.t).toBeLessThanOrEqual(sidecar.duration)
      expect(onset.strength).toBeGreaterThan(0)
      expect(onset.pan).toBeGreaterThanOrEqual(-1)
      expect(onset.pan).toBeLessThanOrEqual(1)
    }
    // A 60Hz decaying burst is unambiguously sub/low, never presence/air.
    const avgTone = sidecar.onsets.reduce((s, o) => s + o.tone, 0) / sidecar.onsets.length
    expect(avgTone).toBeLessThan(0.5)
  })

  it('locks onto roughly the true tempo of a steady kick train', () => {
    const wav = makeKickTrain(128, 14)
    const sidecar = analyzeMix(wav)
    expect(sidecar.tempo).toBeGreaterThan(100)
    expect(sidecar.tempo).toBeLessThan(160)
  })

  it('reports a beat grid that roughly covers the track', () => {
    const wav = makeKickTrain(120, 12)
    const sidecar = analyzeMix(wav)
    expect(sidecar.beats.length).toBeGreaterThan(5)
    expect(sidecar.beats[0]).toBeGreaterThanOrEqual(0)
    expect(sidecar.beats[sidecar.beats.length - 1]).toBeLessThanOrEqual(sidecar.duration)
  })

  it('every energy envelope sample is a finite 0..1 value', () => {
    const wav = makeKickTrain(100, 6)
    const sidecar = analyzeMix(wav)
    for (const v of sidecar.energyEnvelope) {
      expect(Number.isFinite(v)).toBe(true)
      expect(v).toBeGreaterThanOrEqual(0)
      expect(v).toBeLessThanOrEqual(1)
    }
  })
})
