// Shared self-similarity/novelty primitive (SINTEZA_SIGNAL_BUS.md §4.2,
// §4b(2)): cosine similarity of a feature vector against a recent buffer of
// them. Used independently by two different consumers running on two
// different threads/cadences — the live DropDetector's novelty-contrast term
// (this file, audio-worklet hop rate) and the render side's `familiarity`
// bus signal (src/render/conductor/familiarity.ts, render-frame rate) — so
// they share one algorithm without threading a value backwards across the
// worklet/render-worker boundary (which would violate the one-way
// StateFrame -> Conductor flow). The two buffers are NOT the same instance
// and don't need to agree bit-for-bit; one gates drop detection, the other
// drives the screen's organization signal.
export function cosineSimilarity(a: readonly number[], b: readonly number[]): number {
  let dot = 0
  let normA = 0
  let normB = 0
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i]
    normA += a[i] * a[i]
    normB += b[i] * b[i]
  }
  const denom = Math.sqrt(normA) * Math.sqrt(normB)
  return denom > 1e-6 ? dot / denom : 0
}

// Fixed-capacity ring buffer of feature vectors. A fixed hop-count capacity
// (not a time-bucketed one) is fine here, unlike the render-side
// familiarity buffer: the audio worklet ticks at a constant hop rate, so a
// fixed count IS a fixed time window — no adaptive-quality frame-rate
// variance to account for.
export class NoveltyRingBuffer {
  private buffer: (readonly number[])[] = []
  private writeIndex = 0

  constructor(private capacity: number) {}

  // Max similarity of `vec` against everything currently buffered (0 if the
  // buffer is empty — "nothing to be similar to yet" reads as fully novel).
  maxSimilarity(vec: readonly number[]): number {
    let best = 0
    for (const other of this.buffer) {
      const s = cosineSimilarity(vec, other)
      if (s > best) best = s
    }
    return best
  }

  push(vec: readonly number[]): void {
    if (this.buffer.length < this.capacity) {
      this.buffer.push(vec)
    } else {
      this.buffer[this.writeIndex] = vec
      this.writeIndex = (this.writeIndex + 1) % this.capacity
    }
  }
}
