import { describe, it, expect } from 'vitest'
import { analyzeMix, computeStemPresence } from '../../scripts/structure'
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
  it('produces a schema-3 sidecar (without stemPresence, unless --stems separation is passed) with the right duration', () => {
    const wav = makeKickTrain(120, 10)
    const sidecar = analyzeMix(wav)
    expect(sidecar.schema).toBe(3)
    expect(sidecar.stemPresence).toBeUndefined()
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

function silentWav(durationSec: number): DecodedWav {
  return { sampleRate: SAMPLE_RATE, channels: [new Float32Array(Math.floor(durationSec * SAMPLE_RATE))], duration: durationSec }
}

function loudWav(durationSec: number): DecodedWav {
  const n = Math.floor(durationSec * SAMPLE_RATE)
  const data = new Float32Array(n)
  for (let i = 0; i < n; i++) data[i] = Math.sin((2 * Math.PI * 220 * i) / SAMPLE_RATE) * 0.8
  return { sampleRate: SAMPLE_RATE, channels: [data], duration: durationSec }
}

// AGENTS.md §4.3/§4.5 step 5 — computeStemPresence itself (not the Demucs
// subprocess, which needs a real Python env and is exercised only by a
// manual run per this session's own scoping) against synthetic per-stem
// audio: a present (loud, sustained) stem should read high, a silent one low.
describe('computeStemPresence', () => {
  it('reads high presence for a loud, sustained stem and low for a silent one', () => {
    const presence = computeStemPresence({
      vocals: loudWav(6),
      drums: silentWav(6),
      bass: silentWav(6),
      other: silentWav(6),
    })
    const avg = (arr: number[]) => arr.reduce((s, v) => s + v, 0) / Math.max(1, arr.length)
    expect(avg(presence.vocals)).toBeGreaterThan(0.5)
    expect(avg(presence.drums)).toBeLessThan(0.1)
    expect(avg(presence.bass)).toBeLessThan(0.1)
  })

  it('every presence/leadPresence sample is a finite 0..1 value', () => {
    const presence = computeStemPresence({
      vocals: loudWav(4),
      drums: loudWav(4),
      bass: silentWav(4),
      other: loudWav(4),
    })
    for (const arr of [presence.vocals, presence.drums, presence.bass, presence.other, presence.leadPresence]) {
      expect(arr.length).toBeGreaterThan(0)
      for (const v of arr) {
        expect(Number.isFinite(v)).toBe(true)
        expect(v).toBeGreaterThanOrEqual(0)
        expect(v).toBeLessThanOrEqual(1)
      }
    }
  })

  it('leadPresence favors a sustained tone over a louder-but-transient competitor', () => {
    // A steady 220Hz tone throughout, mixed with a single loud broadband
    // click at the very start — the sustained tone should dominate the
    // *envelope-followed* leadPresence reading by the end of the clip, even
    // though the click is momentarily louder.
    const n = Math.floor(4 * SAMPLE_RATE)
    const data = new Float32Array(n)
    for (let i = 0; i < n; i++) data[i] = Math.sin((2 * Math.PI * 220 * i) / SAMPLE_RATE) * 0.3
    for (let i = 0; i < 200; i++) data[i] += 1 // a single-hop broadband transient spike at t=0
    const wav: DecodedWav = { sampleRate: SAMPLE_RATE, channels: [data], duration: 4 }
    const presence = computeStemPresence({ vocals: silentWav(4), drums: silentWav(4), bass: silentWav(4), other: wav })
    const last = presence.leadPresence[presence.leadPresence.length - 1]
    expect(last).toBeGreaterThan(0.1) // the sustained tone still reads as present well after the transient decayed
  })
})
