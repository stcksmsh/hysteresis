// familiarity (SINTEZA_SIGNAL_BUS.md §4.2): the online, continuous "have I
// heard this recently" scalar — the one genuinely novel bus signal, and the
// highest-leverage single addition, because it's alive every frame instead
// of only inside a detected build/break span. Pure math, no output-shaped
// imports (R1) — this module and Conductor.ts are what the R1 grep covers.
//
// Time-bucketed eviction, not a fixed-size ring: the Conductor runs once per
// rendered frame, and frame rate varies under adaptive quality/tier — a
// fixed-count ring would silently shrink/grow its effective time window
// under load. A `{t, vec}` buffer evicted by age keeps the window's real
// duration constant regardless of frame rate.
import type { StateFrame } from '../../shared/types'
import { cosineSimilarity } from '../../audio/worklet/brain/novelty'

const WINDOW_SEC = 12 // "the last N seconds", tuned by feel per the spec's own N=8-16s guidance
const MAX_COMPARISONS = 24 // bound cost to "a few dot products" per frame (§4.2)
const MIN_BUFFER_AGE_SEC = 0.5 // don't compare against near-duplicate very-recent samples

export interface FeatureVector {
  t: number
  vec: number[]
}

export class FamiliarityTracker {
  private buffer: FeatureVector[] = []

  // Exposed for tests: current buffer size after eviction.
  get size(): number {
    return this.buffer.length
  }

  sample(t: number, vec: number[]): number {
    // Evict anything older than the window before comparing, so the buffer
    // never grows unbounded and the comparison set always reflects "the
    // recent past", not the whole track.
    const cutoff = t - WINDOW_SEC
    while (this.buffer.length > 0 && this.buffer[0].t < cutoff) this.buffer.shift()

    const comparisonSet = this.buffer.filter((entry) => t - entry.t >= MIN_BUFFER_AGE_SEC)
    const familiarity = comparisonSet.length === 0 ? 0 : maxCosineSimilarity(vec, comparisonSet, MAX_COMPARISONS)

    this.buffer.push({ t, vec })
    return familiarity
  }
}

function maxCosineSimilarity(vec: number[], buffer: FeatureVector[], maxComparisons: number): number {
  const step = Math.max(1, Math.floor(buffer.length / maxComparisons))
  let best = 0
  for (let i = 0; i < buffer.length; i += step) {
    const similarity = cosineSimilarity(vec, buffer[i].vec)
    if (similarity > best) best = similarity
  }
  // Cosine similarity of non-negative feature vectors (bands/flatness are
  // 0..1) is already 0..1 in practice, but clamp defensively — centroid is
  // also 0..1 so this holds for the whole vector.
  return Math.max(0, Math.min(1, best))
}

// Feature vector = band energies + centroid + flatness (the same continuous
// features §3.1 already carries on the bus) — cheap, and exactly the shape
// that makes "the mix resembles the recent past" meaningful (a repeating
// motif/loop reads as similar band balance + brightness + tonality, not
// similar loudness alone).
export function computeFamiliarity(tracker: FamiliarityTracker, frame: StateFrame, _dt: number): number {
  const { sub, low, mid, presence, air } = frame.bandsRaw
  const vec = [sub, low, mid, presence, air, frame.centroid, frame.flatness]
  return tracker.sample(frame.t, vec)
}
