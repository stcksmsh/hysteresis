import { BAND_EDGES_HZ } from '../../shared/constants'
import type { BandEnergies } from '../../shared/types'

export const BAND_NAMES = ['sub', 'low', 'mid', 'presence', 'air'] as const
export type BandName = (typeof BAND_NAMES)[number]

export type BandRanges = Record<BandName, [number, number]>

// Perceptual (Bark-ish) band edges, not linear spacing — a kick and a hi-hat
// must land in clearly different bands. Bin ranges depend on sampleRate, so
// this is computed once per AudioContext rather than hardcoded.
export function computeBandRanges(fftSize: number, sampleRate: number): BandRanges {
  const binHz = sampleRate / fftSize
  const edgeBins = BAND_EDGES_HZ.map((hz) => Math.round(hz / binHz))
  const ranges = {} as BandRanges
  for (let i = 0; i < BAND_NAMES.length; i++) {
    const name = BAND_NAMES[i]
    const lo = edgeBins[i]
    const hi = Math.max(lo + 1, edgeBins[i + 1])
    ranges[name] = [lo, hi]
  }
  return ranges
}

// RMS magnitude per band (raw, pre-envelope, pre-normalization).
export function bandEnergiesFromMagnitudes(mags: Float32Array, ranges: BandRanges, out: BandEnergies): void {
  for (const name of BAND_NAMES) {
    const [lo, hi] = ranges[name]
    let sumSq = 0
    let count = 0
    const end = Math.min(hi, mags.length)
    for (let i = lo; i < end; i++) {
      sumSq += mags[i] * mags[i]
      count++
    }
    out[name] = count > 0 ? Math.sqrt(sumSq / count) : 0
  }
}
