import { describe, it, expect } from 'vitest'
import { computeBandRanges, bandEnergiesFromMagnitudes, BAND_NAMES } from '../../src/audio/worklet/bands'
import type { BandEnergies } from '../../src/shared/types'

describe('computeBandRanges', () => {
  it('produces monotonically increasing, non-overlapping bin ranges', () => {
    const ranges = computeBandRanges(2048, 48000)
    let prevHi = 0
    for (const name of BAND_NAMES) {
      const [lo, hi] = ranges[name]
      expect(lo).toBeGreaterThanOrEqual(prevHi)
      expect(hi).toBeGreaterThan(lo)
      prevHi = hi
    }
  })

  it('scales bin edges with sample rate', () => {
    const at48k = computeBandRanges(2048, 48000)
    const at44k = computeBandRanges(2048, 44100)
    // a lower sample rate means fewer Hz per bin, so the same Hz edge lands
    // at a higher (or equal) bin index
    expect(at44k.sub[1]).toBeGreaterThanOrEqual(at48k.sub[1])
  })
})

describe('bandEnergiesFromMagnitudes', () => {
  it('attributes energy to the band containing the excited bins', () => {
    const fftSize = 2048
    const sampleRate = 48000
    const ranges = computeBandRanges(fftSize, sampleRate)
    const bins = fftSize / 2 + 1
    const mags = new Float32Array(bins)

    // Put all energy in a bin squarely inside the "sub" band (e.g. ~50Hz).
    const binHz = sampleRate / fftSize
    const subBinIndex = Math.round(50 / binHz)
    mags[subBinIndex] = 10

    const out = {} as BandEnergies
    bandEnergiesFromMagnitudes(mags, ranges, out)

    expect(out.sub).toBeGreaterThan(0)
    expect(out.low).toBe(0)
    expect(out.mid).toBe(0)
    expect(out.presence).toBe(0)
    expect(out.air).toBe(0)
  })

  it('returns 0 for a silent spectrum', () => {
    const ranges = computeBandRanges(2048, 48000)
    const mags = new Float32Array(1025)
    const out = {} as BandEnergies
    bandEnergiesFromMagnitudes(mags, ranges, out)
    for (const name of BAND_NAMES) {
      expect(out[name]).toBe(0)
    }
  })
})
