// Spectral centroid in Hz, i.e. "where the brightness is" — the key build
// signal (rising centroid = filter opening). Bin 0 (DC) is skipped to avoid
// biasing the average toward zero.
export function spectralCentroidHz(mags: Float32Array, sampleRate: number, fftSize: number): number {
  const binHz = sampleRate / fftSize
  let weightedSum = 0
  let magSum = 0
  for (let i = 1; i < mags.length; i++) {
    weightedSum += i * binHz * mags[i]
    magSum += mags[i]
  }
  return magSum > 1e-9 ? weightedSum / magSum : 0
}

// Spectral flatness (Wiener entropy): geometric mean / arithmetic mean of
// the magnitude spectrum. Near 0 = tonal (pad, sustained note), near 1 =
// noisy/broadband (crash, riser, noise). Scale-invariant by construction, so
// unlike the band envelopes it needs no adaptive normalization.
export function spectralFlatness(mags: Float32Array): number {
  let logSum = 0
  let sum = 0
  let n = 0
  for (let i = 1; i < mags.length; i++) {
    const m = mags[i]
    if (m > 1e-9) {
      logSum += Math.log(m)
      sum += m
      n++
    }
  }
  if (n === 0 || sum === 0) return 0
  const geoMean = Math.exp(logSum / n)
  const arithMean = sum / n
  return arithMean > 1e-9 ? geoMean / arithMean : 0
}
