import { describe, it, expect } from 'vitest'
import {
  computeBeatFeatures,
  buildSSM,
  cosineSimilarity,
  checkerboardNovelty,
  pickPeaks,
  backwardWalkToBoundary,
  computeRepetitionMap,
  FEATURE_DIMS,
} from '../../scripts/ssm'
import type { BandName } from '../../src/audio/worklet/bands'

function makeBandRaw(totalHops: number, fn: (h: number) => number): Record<BandName, Float32Array> {
  const arr = new Float32Array(totalHops)
  for (let h = 0; h < totalHops; h++) arr[h] = fn(h)
  const names: BandName[] = ['sub', 'low', 'mid', 'presence', 'air']
  const out = {} as Record<BandName, Float32Array>
  for (const n of names) out[n] = arr.slice()
  return out
}

describe('computeBeatFeatures', () => {
  it('averages hops within each beat interval and z-score normalizes each dim', () => {
    // 4 beats, 1s apart, hopSec = 0.1s -> 10 hops per beat. Two distinct
    // constant levels alternating per beat: normalization should map the low
    // level to a negative z-score and the high level to a positive one.
    const hopSec = 0.1
    const totalHops = 40
    const bandRaw = makeBandRaw(totalHops, (h) => (Math.floor(h / 10) % 2 === 0 ? 0.2 : 0.8))
    const centroidRaw = new Float32Array(totalHops).fill(0.5)
    const flatnessRaw = new Float32Array(totalHops).fill(0.5)
    const beats = [0, 1, 2, 3]
    const features = computeBeatFeatures(beats, bandRaw, centroidRaw, flatnessRaw, hopSec)
    expect(features.length).toBe(4)
    expect(features[0].length).toBe(FEATURE_DIMS)
    // beat 0 and 2 are the "low" level, beat 1 and 3 the "high" level
    expect(features[0][0]).toBeLessThan(0)
    expect(features[1][0]).toBeGreaterThan(0)
    expect(features[0][0]).toBeCloseTo(features[2][0], 5)
    expect(features[1][0]).toBeCloseTo(features[3][0], 5)
  })
})

describe('cosineSimilarity', () => {
  it('is 1 for identical vectors, 0 for a zero vector', () => {
    const a = new Float32Array([1, 2, 3])
    expect(cosineSimilarity(a, a)).toBeCloseTo(1, 5)
    expect(cosineSimilarity(a, new Float32Array([0, 0, 0]))).toBe(0)
  })
})

// The real bite: a synthetic track built from two identical halves must show
// an obvious repeated block in the SSM — the cross-block mean similarity
// between the two halves should be near 1 and clearly higher than a
// shuffled/different-halves control.
describe('buildSSM', () => {
  // A "section" = many beats all pointing near one base direction (real
  // sustained material, e.g. a chorus, is much more self-similar than
  // cross-material) with small per-beat jitter so it's not a trivial
  // constant vector.
  function makeSection(base: number[], count: number, jitterSeed = 1): Float32Array[] {
    const out: Float32Array[] = []
    for (let k = 0; k < count; k++) {
      const jitter = Math.sin(k * jitterSeed) * 0.01
      out.push(new Float32Array(base.map((v, d) => v + jitter * (d + 1))))
    }
    return out
  }

  it('shows a strong repeated block for two identical halves, weak for a different-halves control', () => {
    const baseA = [1, 0, 0, 0, 0, 0, 0]
    const half = 20
    const identicalHalves = [...makeSection(baseA, half), ...makeSection(baseA, half)]
    const ssm = buildSSM(identicalHalves)
    const n = identicalHalves.length

    let sum = 0
    let count = 0
    for (let i = 0; i < half; i++) for (let j = half; j < n; j++) { sum += ssm[i][j]; count++ }
    const repeatedMeanSim = sum / count
    expect(repeatedMeanSim).toBeGreaterThan(0.95)

    // Control: second half is genuinely different material (orthogonal base
    // direction), not just a reordering.
    const baseB = [0, 1, 1, 0, 0, 0, 0]
    const differentHalves = [...makeSection(baseA, half), ...makeSection(baseB, half)]
    const controlSsm = buildSSM(differentHalves)
    let csum = 0
    let ccount = 0
    for (let i = 0; i < half; i++) for (let j = half; j < n; j++) { csum += controlSsm[i][j]; ccount++ }
    const controlMeanSim = csum / ccount
    expect(controlMeanSim).toBeLessThan(repeatedMeanSim)
    expect(controlMeanSim).toBeLessThan(0.3)
  })
})

describe('checkerboardNovelty + pickPeaks', () => {
  it('places a boundary peak near a synthetic section change', () => {
    // Two 16-beat sections with clearly different feature vectors — a real
    // boundary should land near beat 16.
    const sectionA = (k: number): number[] => [1, 0, 0, 0, 0, Math.sin(k), Math.cos(k)]
    const sectionB = (k: number): number[] => [0, 1, 1, 0, 0, Math.sin(k * 2), Math.cos(k * 2)]
    const features: Float32Array[] = []
    for (let k = 0; k < 16; k++) features.push(new Float32Array(sectionA(k)))
    for (let k = 0; k < 16; k++) features.push(new Float32Array(sectionB(k)))
    const ssm = buildSSM(features)
    const novelty = checkerboardNovelty(ssm, 6)
    const peaks = pickPeaks(novelty, 4)
    expect(peaks.length).toBeGreaterThan(0)
    const nearest = peaks.reduce((best, p) => (Math.abs(p - 16) < Math.abs(best - 16) ? p : best))
    expect(Math.abs(nearest - 16)).toBeLessThanOrEqual(4)
  })
})

describe('backwardWalkToBoundary', () => {
  it('walks back to the nearest preceding boundary', () => {
    const boundaries = [2, 10, 20]
    expect(backwardWalkToBoundary(22, 0, boundaries, 8)).toBe(20)
  })

  it('falls back to the fixed window when no boundary precedes the drop within the outer limit', () => {
    const boundaries = [2]
    expect(backwardWalkToBoundary(100, 0, boundaries, 8, 16)).toBe(92) // 100 - 8, since 2 is outside the 16-unit outer limit
  })
})

describe('computeRepetitionMap', () => {
  it('finds a repeat between two non-adjacent, similar sections and not the adjacent one', () => {
    const period = 8
    const jitter = (base: number[], k: number) => base.map((v, d) => v + Math.sin(k * 1.7) * 0.01 * (d + 1))
    const baseA = [1, 0, 0, 0, 0, 0, 0]
    const baseB = [0, 1, 1, 0, 0, 0, 0]
    const features: Float32Array[] = []
    // A B A (A repeats non-adjacently at sections 0 and 2)
    for (let k = 0; k < period; k++) features.push(new Float32Array(jitter(baseA, k)))
    for (let k = 0; k < period; k++) features.push(new Float32Array(jitter(baseB, k)))
    for (let k = 0; k < period; k++) features.push(new Float32Array(jitter(baseA, k)))
    const ssm = buildSSM(features)
    const n = features.length
    const beatTimesWithDuration = Array.from({ length: n + 1 }, (_, i) => i * 0.5) // 0.5s/beat
    const repeats = computeRepetitionMap({
      ssm,
      beatTimesWithDuration,
      boundaryBeatIndices: [0, period, period * 2, n],
    })
    expect(repeats.length).toBeGreaterThan(0)
    const r = repeats[0]
    expect(r.aStart).toBeCloseTo(0, 5)
    expect(r.bStart).toBeCloseTo(period * 2 * 0.5, 5)
    expect(r.similarity).toBeGreaterThan(0.9)
  })
})
