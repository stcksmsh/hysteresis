import FFT from 'fft.js'

// Own windowed FFT (Hann window) rather than relying on AnalyserNode, so we
// control window function, hop timing, and get raw bin magnitudes without
// AnalyserNode's built-in smoothing.
export class WindowedFFT {
  readonly size: number
  readonly bins: number // size/2 + 1 (DC..Nyquist inclusive)

  private fft: FFT
  private window: Float32Array
  private windowed: Float32Array
  private complex: number[]

  constructor(size: number) {
    this.size = size
    this.bins = size / 2 + 1
    this.fft = new FFT(size)
    this.window = makeHannWindow(size)
    this.windowed = new Float32Array(size)
    this.complex = this.fft.createComplexArray()
  }

  // `samples` must have length `this.size`. `magnitudeOut` must have length
  // `this.bins`; filled with the magnitude spectrum (DC..Nyquist).
  transform(samples: Float32Array, magnitudeOut: Float32Array): void {
    const { window, windowed, size, fft, complex, bins } = this
    for (let i = 0; i < size; i++) {
      windowed[i] = samples[i] * window[i]
    }
    // realTransform fills complex[0..bins) (DC..Nyquist); the mirrored upper
    // half (completeSpectrum) isn't needed since we only ever want magnitude
    // up to Nyquist.
    fft.realTransform(complex, windowed)
    for (let i = 0; i < bins; i++) {
      const re = complex[2 * i]
      const im = complex[2 * i + 1]
      magnitudeOut[i] = Math.sqrt(re * re + im * im)
    }
  }
}

function makeHannWindow(size: number): Float32Array {
  const w = new Float32Array(size)
  for (let i = 0; i < size; i++) {
    w[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / (size - 1))
  }
  return w
}
