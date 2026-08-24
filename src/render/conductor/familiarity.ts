// similarity tracking (AGENTS.md §4.2, §4.4): the online, continuous "how
// much does now resemble the recent past" primitive. `familiarity` (the
// default ~12s window) was the first, genuinely novel bus signal — alive
// every frame instead of only inside a detected build/break span. `§4.4`
// generalizes this into `SimilarityTracker`, parameterized by window size,
// so the Conductor can run a second, shorter-window instance for
// `noveltyLocal` (phrase-scale novelty) alongside the original for
// `noveltySection`/`familiarity` (section-scale) — "the same computation
// read two ways", per the design doc. Pure math, no output-shaped imports
// (R1) — this module and Conductor.ts are what the R1 grep covers.
//
// Time-bucketed eviction, not a fixed-size ring: the Conductor runs once per
// rendered frame, and frame rate varies under adaptive quality/tier — a
// fixed-count ring would silently shrink/grow its effective time window
// under load. A `{t, vec}` buffer evicted by age keeps the window's real
// duration constant regardless of frame rate.
import type { StateFrame } from '../../shared/types'
import { cosineSimilarity } from '../../audio/worklet/brain/novelty'

const DEFAULT_WINDOW_SEC = 12 // "the last N seconds", tuned by feel per the spec's own N=8-16s guidance
const MAX_COMPARISONS = 24 // bound cost to "a few dot products" per frame
const MIN_BUFFER_AGE_SEC = 0.5 // don't compare against near-duplicate very-recent samples

export interface FeatureVector {
  t: number
  vec: number[]
}

export class SimilarityTracker {
  private buffer: FeatureVector[] = []

  constructor(private readonly windowSec: number = DEFAULT_WINDOW_SEC) {}

  // Exposed for tests: current buffer size after eviction.
  get size(): number {
    return this.buffer.length
  }

  sample(t: number, vec: number[]): number {
    // Self-heal a backward time jump — a position-only loop repeat or seek.
    // `StructureSource.synthesize()` feeds `t: positionSec` straight from
    // the host's own position feed, and that position-only path IS this
    // package's actual production integration (AGENTS.md's "Position-only
    // sync mode" section) — a loop repeat or seek genuinely moves `t`
    // backward. The age-based eviction below assumes `t` only ever
    // increases: once it moves backward, `buffer[0].t < cutoff` can go
    // permanently false and eviction silently stops working for the rest
    // of a multi-day unattended run — unbounded growth, plus a
    // now-out-of-order buffer that no longer means "the recent past" at
    // all. This is the same bug class `StructureSource`'s own
    // `healPositionRegression()` already exists to fix, just never applied
    // to this tracker until now. A similarity window has no sane partial
    // recovery from a jump (the "recent past" it held is genuinely gone),
    // so the correct self-heal is a full reset, not a resync.
    const last = this.buffer[this.buffer.length - 1]
    if (last && t < last.t - 1e-6) this.buffer.length = 0

    // Evict anything older than the window before comparing, so the buffer
    // never grows unbounded and the comparison set always reflects "the
    // recent past", not the whole track.
    const cutoff = t - this.windowSec
    while (this.buffer.length > 0 && this.buffer[0].t < cutoff) this.buffer.shift()

    const comparisonSet = this.buffer.filter((entry) => t - entry.t >= MIN_BUFFER_AGE_SEC)
    const familiarity = comparisonSet.length === 0 ? 0 : maxCosineSimilarity(vec, comparisonSet, MAX_COMPARISONS)

    this.buffer.push({ t, vec })
    return familiarity
  }
}

// Kept as the name most call sites/tests know — a plain alias, same class,
// always constructed at the default (~12s, "section-scale") window.
export { SimilarityTracker as FamiliarityTracker }

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
// features already carried on the bus) — cheap, and exactly the shape that
// makes "the mix resembles the recent past" meaningful (a repeating
// motif/loop reads as similar band balance + brightness + tonality, not
// similar loudness alone). Shared by every SimilarityTracker instance
// (familiarity/noveltySection's long window and noveltyLocal's short one)
// so "the same computation read two ways" really is the same computation.
export function buildSimilarityVector(frame: StateFrame): number[] {
  const { sub, low, mid, presence, air } = frame.bandsRaw
  return [sub, low, mid, presence, air, frame.centroid, frame.flatness]
}

export function computeFamiliarity(tracker: SimilarityTracker, frame: StateFrame, _dt: number): number {
  return tracker.sample(frame.t, buildSimilarityVector(frame))
}
