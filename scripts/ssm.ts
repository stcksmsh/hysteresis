// SINTEZA_OFFLINE_SSM.md §1.1/§1.2/§1.3/§1.4/§1.5 — beat-synchronous
// features, full self-similarity matrix, checkerboard novelty + peak-picking
// (fallback boundary source, since allin1 is infeasible here — see
// scripts/README.md), and the repetition map.
import type { BandName } from '../src/audio/worklet/bands'
import type { SidecarRepeat } from './schema4'

export const FEATURE_DIMS = 7 // sub, low, mid, presence, air, centroid, flatness

// §1.1 — average per-hop bandRaw/centroidRaw/flatnessRaw into one 7-dim
// vector per inter-beat interval, then z-score normalize each dim
// independently across the whole track.
export function computeBeatFeatures(
  beats: number[],
  bandRaw: Record<BandName, Float32Array>,
  centroidRaw: Float32Array,
  flatnessRaw: Float32Array,
  hopSec: number,
): Float32Array[] {
  const totalHops = centroidRaw.length
  const trackEndSec = totalHops * hopSec
  const vectors: Float32Array[] = []
  for (let i = 0; i < beats.length; i++) {
    const endSec = i + 1 < beats.length ? beats[i + 1] : trackEndSec
    const h0 = Math.max(0, Math.floor(beats[i] / hopSec))
    const h1 = Math.min(totalHops, Math.max(h0 + 1, Math.floor(endSec / hopSec)))
    const vec = new Float32Array(FEATURE_DIMS)
    let n = 0
    for (let h = h0; h < h1; h++) {
      vec[0] += bandRaw.sub[h]
      vec[1] += bandRaw.low[h]
      vec[2] += bandRaw.mid[h]
      vec[3] += bandRaw.presence[h]
      vec[4] += bandRaw.air[h]
      vec[5] += centroidRaw[h]
      vec[6] += flatnessRaw[h]
      n++
    }
    if (n > 0) for (let d = 0; d < FEATURE_DIMS; d++) vec[d] /= n
    vectors.push(vec)
  }
  for (let d = 0; d < FEATURE_DIMS; d++) {
    let mean = 0
    for (const v of vectors) mean += v[d]
    mean /= Math.max(1, vectors.length)
    let variance = 0
    for (const v of vectors) variance += (v[d] - mean) ** 2
    variance /= Math.max(1, vectors.length)
    const std = Math.sqrt(variance) || 1
    for (const v of vectors) v[d] = (v[d] - mean) / std
  }
  return vectors
}

export function cosineSimilarity(a: Float32Array, b: Float32Array): number {
  let dot = 0
  let na = 0
  let nb = 0
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i]
    na += a[i] * a[i]
    nb += b[i] * b[i]
  }
  if (na === 0 || nb === 0) return 0
  return dot / (Math.sqrt(na) * Math.sqrt(nb))
}

// §1.2 — full N x N SSM, symmetric (upper triangle computed, mirrored).
export function buildSSM(beatFeatures: Float32Array[]): Float32Array[] {
  const n = beatFeatures.length
  const ssm: Float32Array[] = Array.from({ length: n }, () => new Float32Array(n))
  for (let i = 0; i < n; i++) {
    ssm[i][i] = 1
    for (let j = i + 1; j < n; j++) {
      const s = cosineSimilarity(beatFeatures[i], beatFeatures[j])
      ssm[i][j] = s
      ssm[j][i] = s
    }
  }
  return ssm
}

function medianMad(values: number[]): { median: number; mad: number } {
  if (values.length === 0) return { median: 0, mad: 0 }
  const sorted = [...values].sort((a, b) => a - b)
  const median = sorted[Math.floor(sorted.length / 2)]
  const devs = sorted.map((v) => Math.abs(v - median)).sort((a, b) => a - b)
  const mad = devs[Math.floor(devs.length / 2)]
  return { median, mad }
}

// §1.3 (fallback path only — allin1 unavailable here, see scripts/README.md)
// — Foote checkerboard novelty along the SSM's main diagonal, zero-padded
// past the edges. Returned un-normalized-to-magnitude but clamped to >=0
// (novelty is a "how different" measure, negative correlation isn't a
// bigger novelty).
export function checkerboardNovelty(ssm: Float32Array[], radius: number): number[] {
  const n = ssm.length
  const novelty = new Array<number>(n).fill(0)
  for (let i = 0; i < n; i++) {
    let sum = 0
    for (let a = -radius; a < radius; a++) {
      const r = i + a
      if (r < 0 || r >= n) continue
      for (let b = -radius; b < radius; b++) {
        const c = i + b
        if (c < 0 || c >= n) continue
        const sign = (a >= 0) === (b >= 0) ? 1 : -1
        sum += sign * ssm[r][c]
      }
    }
    novelty[i] = Math.max(0, sum)
  }
  const max = Math.max(...novelty, 1e-9)
  return novelty.map((v) => v / max)
}

// §1.4 — local-maximum peak-picking, adaptive (median + k*MAD) threshold.
export function pickPeaks(novelty: number[], minSpacing: number, madMultiplier = 2): number[] {
  const { median, mad } = medianMad(novelty)
  const threshold = median + madMultiplier * mad
  const peaks: number[] = []
  for (let i = 0; i < novelty.length; i++) {
    if (novelty[i] < threshold) continue
    let isLocalMax = true
    for (let k = Math.max(0, i - minSpacing); k <= Math.min(novelty.length - 1, i + minSpacing); k++) {
      if (novelty[k] > novelty[i]) {
        isLocalMax = false
        break
      }
    }
    if (isLocalMax && (peaks.length === 0 || i - peaks[peaks.length - 1] >= minSpacing)) peaks.push(i)
  }
  return peaks
}

// §1.4's build-window derivation: walk backward from a drop to the nearest
// preceding boundary time. Falls back to the fixed-bar window if no boundary
// exists before the drop within `outerLimitSec` (a drop with no real
// lead-in, e.g. right after the intro).
export function backwardWalkToBoundary(
  dropTime: number,
  prevBoundaryFloor: number,
  boundaryTimes: number[],
  fallbackWindowSec: number,
  outerLimitSec = fallbackWindowSec * 4,
): number {
  let nearest = -Infinity
  for (const t of boundaryTimes) if (t < dropTime && t > nearest) nearest = t
  if (nearest > prevBoundaryFloor && dropTime - nearest <= outerLimitSec) return nearest
  return Math.max(prevBoundaryFloor, dropTime - fallbackWindowSec)
}

export interface RepetitionMapInput {
  ssm: Float32Array[]
  // beat onset times, PLUS one trailing entry = track duration (so the last
  // section's end resolves to a real time, not undefined) — length N+1 for
  // an N-beat SSM.
  beatTimesWithDuration: number[]
  // section boundaries in beat-index space (0..N inclusive), sorted; 0 and N
  // (=beats.length) are implied and added if missing.
  boundaryBeatIndices: number[]
  madMultiplier?: number
}

// §1.5 — the repetition map. Off-diagonal, non-adjacent, boundary-delimited
// section pairs whose cross-block mean SSM similarity clears an adaptive
// (median/MAD) threshold. 1.5x MAD tuned against real tracks (see
// scripts/README.md) — 2x was too strict to surface any real repeat on an
// actual song's noisier similarity distribution, 1.0x let through too many
// marginal pairs.
export function computeRepetitionMap({
  ssm,
  beatTimesWithDuration,
  boundaryBeatIndices,
  madMultiplier = 1.5,
}: RepetitionMapInput): SidecarRepeat[] {
  const n = ssm.length
  const bounds = [...new Set(boundaryBeatIndices)].sort((a, b) => a - b)
  if (bounds[0] !== 0) bounds.unshift(0)
  if (bounds[bounds.length - 1] !== n) bounds.push(n)

  const sections: Array<[number, number]> = []
  for (let i = 0; i + 1 < bounds.length; i++) if (bounds[i + 1] > bounds[i]) sections.push([bounds[i], bounds[i + 1]])

  const pairs: Array<[number, number, number]> = []
  for (let a = 0; a < sections.length; a++) {
    for (let b = a + 1; b < sections.length; b++) {
      if (b === a + 1) continue // adjacent — not a repeat, just the next section
      const [as, ae] = sections[a]
      const [bs, be] = sections[b]
      let sum = 0
      let count = 0
      for (let i = as; i < ae; i++) for (let j = bs; j < be; j++) { sum += ssm[i][j]; count++ }
      if (count > 0) pairs.push([a, b, sum / count])
    }
  }

  // Fewer than 2 candidate pairs makes median/MAD degenerate (mad=0, the
  // lone value equals its own "threshold"); fall back to an absolute bar.
  const { median, mad } = medianMad(pairs.map((p) => p[2]))
  const threshold = pairs.length >= 2 ? median + madMultiplier * mad : 0.5
  const repeats: SidecarRepeat[] = []
  for (const [a, b, similarity] of pairs) {
    if (similarity < threshold) continue
    const [as, ae] = sections[a]
    const [bs, be] = sections[b]
    repeats.push({
      aStart: beatTimesWithDuration[as],
      aEnd: beatTimesWithDuration[ae],
      bStart: beatTimesWithDuration[bs],
      bEnd: beatTimesWithDuration[be],
      similarity: Math.max(0, Math.min(1, similarity)),
    })
  }
  return repeats
}
