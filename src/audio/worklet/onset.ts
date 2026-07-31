// Spectral flux: sum of positive bin-to-bin magnitude increases between
// consecutive analysis hops. Broadband energy jumps (onsets, drops) show up
// as spikes here; steady/decaying spectra contribute nothing (only rises
// count). This is a continuous novelty function — turning it into discrete
// onset/drop events is Layer 2's job (beat-tracker/drop-detector), not this
// module's.
export class SpectralFlux {
  private prev: Float32Array

  constructor(bins: number) {
    this.prev = new Float32Array(bins)
  }

  update(mags: Float32Array): number {
    let flux = 0
    for (let i = 0; i < mags.length; i++) {
      const diff = mags[i] - this.prev[i]
      if (diff > 0) flux += diff
      this.prev[i] = mags[i]
    }
    return flux
  }
}
