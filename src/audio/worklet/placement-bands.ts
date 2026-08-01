import { AdaptiveNormalizer } from './envelope'

// Finer than the five perceptual bands used for choreography: these exist
// purely to place things on screen, so a dense mix resolves into many
// separate elements rather than collapsing onto one or two positions.
export const PLACEMENT_BAND_COUNT = 12
const LOW_HZ = 40
const HIGH_HZ = 16000

export interface SpectralHitRaw {
  tone: number // 0..1, band position low -> high
  pan: number // -1..1 from this band's own L/R balance
  strength: number // 0..1 normalized per-band flux
}

// Emit a hit when a band's own flux rises past this. Deliberately lower than
// the global onset threshold — the point is to catch everything in a dense
// arrangement, not just the loudest transient.
const HIT_THRESHOLD = 0.22
const NORMALIZER_DECAY_MS = 4000

// Safety net only — merging normally keeps this well under the cap.
const MAX_HITS_PER_HOP = 6

export class PlacementBands {
  private edges: number[] = []
  private prevEnergy: Float32Array
  private normalizers: AdaptiveNormalizer[] = []
  private wasAbove: boolean[] = []
  private triggered: boolean[] = []
  private bandStrength: Float32Array
  private bandTotal: Float32Array
  private bandBalance: Float32Array

  constructor(fftSize: number, sampleRate: number, hopMs: number) {
    const binHz = sampleRate / fftSize
    const nyquistBin = fftSize / 2
    for (let i = 0; i <= PLACEMENT_BAND_COUNT; i++) {
      const hz = LOW_HZ * Math.pow(HIGH_HZ / LOW_HZ, i / PLACEMENT_BAND_COUNT)
      this.edges.push(Math.min(nyquistBin, Math.max(1, Math.round(hz / binHz))))
    }
    this.prevEnergy = new Float32Array(PLACEMENT_BAND_COUNT)
    this.bandStrength = new Float32Array(PLACEMENT_BAND_COUNT)
    this.bandTotal = new Float32Array(PLACEMENT_BAND_COUNT)
    this.bandBalance = new Float32Array(PLACEMENT_BAND_COUNT)
    for (let i = 0; i < PLACEMENT_BAND_COUNT; i++) {
      this.normalizers.push(new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs))
      this.wasAbove.push(false)
      this.triggered.push(false)
    }
  }

  // `magsL`/`magsR` are the per-channel magnitude spectra. Working per
  // channel is what makes a per-band pan possible at all — a mono downmix
  // discards exactly the information that separates a hard-left stab from a
  // hard-right hat.
  update(magsL: Float32Array, magsR: Float32Array, out: SpectralHitRaw[]): void {
    for (let b = 0; b < PLACEMENT_BAND_COUNT; b++) {
      const lo = this.edges[b]
      const hi = Math.max(lo + 1, this.edges[b + 1])
      let sumL = 0
      let sumR = 0
      const end = Math.min(hi, magsL.length)
      for (let i = lo; i < end; i++) {
        sumL += magsL[i]
        sumR += magsR[i]
      }
      const total = sumL + sumR
      const energy = total * 0.5

      const flux = Math.max(0, energy - this.prevEnergy[b])
      this.prevEnergy[b] = energy
      const strength = this.normalizers[b].normalize(flux)

      const above = strength > HIT_THRESHOLD
      this.triggered[b] = above && !this.wasAbove[b]
      this.wasAbove[b] = above
      this.bandStrength[b] = strength
      this.bandTotal[b] = total
      this.bandBalance[b] = total > 1e-9 ? (sumR - sumL) / total : 0
    }

    this.emitMergedRuns(out)
  }

  // A percussive hit is broadband: one snare crosses threshold in five or six
  // adjacent bands at once, which as separate events becomes a vertical stack
  // of marks for a single drum. Merging each run of adjacent triggered bands
  // into one hit gets as close to "one hit, one mark" as is possible without
  // real source separation.
  private emitMergedRuns(out: SpectralHitRaw[]): void {
    let emitted = 0
    let b = 0
    while (b < PLACEMENT_BAND_COUNT) {
      if (!this.triggered[b]) {
        b++
        continue
      }

      let weightedTone = 0
      let weightedPan = 0
      let weight = 0
      let peak = 0
      while (b < PLACEMENT_BAND_COUNT && this.triggered[b]) {
        const w = Math.max(this.bandTotal[b], 1e-9)
        weightedTone += (b / (PLACEMENT_BAND_COUNT - 1)) * w
        weightedPan += this.bandBalance[b] * w
        weight += w
        peak = Math.max(peak, this.bandStrength[b])
        b++
      }

      if (emitted < MAX_HITS_PER_HOP) {
        out.push({ tone: weightedTone / weight, pan: weightedPan / weight, strength: peak })
        emitted++
      }
    }
  }
}
