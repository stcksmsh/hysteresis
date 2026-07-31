// Attack/release envelope follower, run once per analysis hop (not per
// sample). Fast attack + slow release makes band energies bloom and decay
// like the sound instead of flickering per-frame.
export class EnvelopeFollower {
  private value = 0
  private initialized = false
  private readonly attackCoeff: number
  private readonly releaseCoeff: number

  constructor(attackMs: number, releaseMs: number, hopMs: number) {
    this.attackCoeff = Math.exp(-hopMs / attackMs)
    this.releaseCoeff = Math.exp(-hopMs / releaseMs)
  }

  update(input: number): number {
    // Seed from the first real input rather than climbing from 0 — without
    // this, any paired fast/slow envelope pair (build detector, break
    // detector) reads a spurious "rise" for the first several seconds of
    // playback as the slower one lags behind catching up from zero.
    if (!this.initialized) {
      this.value = input
      this.initialized = true
      return this.value
    }
    const coeff = input > this.value ? this.attackCoeff : this.releaseCoeff
    this.value = coeff * this.value + (1 - coeff) * input
    return this.value
  }
}

// Raw band/flux magnitudes have no fixed scale (depends on input gain,
// source loudness, file mastering). This tracks a slowly-decaying running
// peak and normalizes against it, so values settle into a usable 0..1 range
// without a manual calibration step, adapting over tens of seconds if the
// input's overall level changes.
export class AdaptiveNormalizer {
  private peak = 1e-6
  private readonly decayCoeff: number

  constructor(decayMs: number, hopMs: number) {
    this.decayCoeff = Math.exp(-hopMs / decayMs)
  }

  normalize(value: number): number {
    this.peak = Math.max(value, this.peak * this.decayCoeff)
    return this.peak > 1e-6 ? Math.min(1, value / this.peak) : 0
  }
}
