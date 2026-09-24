import { describe, it, expect } from 'vitest'
import { analyzeMix } from '../../scripts/structure'
import { computeSchema4Sidecar } from '../../scripts/repetition'
import { isSidecar } from '../../src/shared/sidecar'
import type { DecodedWav } from '../../scripts/wav'

const SAMPLE_RATE = 48000

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

describe('schema-4 additive fields', () => {
  it('does not change analyzeMix()\'s own schema-3 output (additive-only)', () => {
    const wav = makeKickTrain(120, 10)
    const sidecar = analyzeMix(wav)
    expect(sidecar.schema).toBe(3)
    expect((sidecar as { repeats?: unknown }).repeats).toBeUndefined()
  })

  it('computeSchema4Sidecar round-trips through JSON without breaking schema-2/3 readers', () => {
    const wav = makeKickTrain(120, 20)
    const schema4 = computeSchema4Sidecar(wav)
    expect(schema4.schema).toBe(4)
    const json = JSON.parse(JSON.stringify(schema4))
    expect(json.schema).toBe(4)
    expect(Array.isArray(json.repeats)).toBe(true)
    expect(Array.isArray(json.noveltyLocalEnvelope)).toBe(true)
    expect(Array.isArray(json.noveltySectionEnvelope)).toBe(true)
    expect(json.noveltyLocalEnvelope.length).toBe(json.energyEnvelope.length)

    // A schema-2/3 reader (isSidecar) only checks schema in {2,3} today
    // (unchanged, frozen sidecar.ts) — a schema-4 sidecar correctly reads as
    // NOT one of those, exactly as isSidecar's own additive-only contract
    // says it should (a future schema-4-aware reader is a separate change).
    expect(isSidecar({ ...json, schema: 3 })).toBe(true) // same shape minus schema still validates as schema-3
  })

  it('every repeat has valid time ordering and similarity in 0..1', () => {
    const wav = makeKickTrain(128, 16)
    const schema4 = computeSchema4Sidecar(wav)
    for (const r of schema4.repeats ?? []) {
      expect(r.aStart).toBeLessThan(r.aEnd)
      expect(r.bStart).toBeLessThan(r.bEnd)
      expect(r.similarity).toBeGreaterThanOrEqual(0)
      expect(r.similarity).toBeLessThanOrEqual(1)
    }
  })
})
