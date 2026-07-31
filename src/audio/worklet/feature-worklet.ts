/// <reference types="audioworklet" />
import { WindowedFFT } from './fft'
import { computeBandRanges, bandEnergiesFromMagnitudes, BAND_NAMES, type BandName, type BandRanges } from './bands'
import { spectralCentroidHz, spectralFlatness } from './spectral'
import { SpectralFlux } from './onset'
import { EnvelopeFollower, AdaptiveNormalizer } from './envelope'
import { BeatTracker, BarTracker } from './brain/beat-tracker'
import { BuildDetector } from './brain/build-detector'
import { DropDetector } from './brain/drop-detector'
import { BreakDetector } from './brain/break-detector'
import { FFT_SIZE, HOP_SIZE } from '../../shared/constants'
import type { BandEnergies, StateFrame, StructuralEvent, WorkletToMain } from '../../shared/types'

// Centroid is normalized against this practical ceiling (Hz), not Nyquist —
// most perceptually relevant brightness/build movement happens well below
// Nyquist at typical sample rates, so dividing by Nyquist would compress
// the useful range into a tiny fraction of 0..1.
const CENTROID_NORMALIZATION_CEILING_HZ = 8000

// How long the adaptive-gain "running peak" takes to forget a loud moment.
// Long enough that it doesn't renormalize on every beat, short enough to
// adapt if the input's overall level genuinely changes (new track, etc.).
const NORMALIZER_DECAY_MS = 6000

const ENERGY_TRAJECTORY_MS = 6000 // "energy over the last several bars", not instantaneous
const ONSET_EVENT_THRESHOLD = 0.4

class FeatureProcessor extends AudioWorkletProcessor implements AudioWorkletProcessorImpl {
  private ring = new Float32Array(FFT_SIZE)
  private ringWritePos = 0
  private samplesSinceHop = 0
  private filled = false

  private fft = new WindowedFFT(FFT_SIZE)
  private mags = new Float32Array(this.fft.bins)
  private flux = new SpectralFlux(this.fft.bins)
  private orderedSamples = new Float32Array(FFT_SIZE)

  private bandRanges: BandRanges
  private bandEnvelopes: Record<BandName, EnvelopeFollower>
  private bandNormalizers: Record<BandName, AdaptiveNormalizer>
  private fluxNormalizer: AdaptiveNormalizer
  private energyTrajectory: EnvelopeFollower

  private beatTracker: BeatTracker
  private barTracker = new BarTracker()
  private buildDetector: BuildDetector
  private dropDetector: DropDetector
  private breakDetector: BreakDetector

  private wasAboveOnsetThreshold = false
  private lastBarPhase = 0

  constructor() {
    super()
    const hopMs = (HOP_SIZE / sampleRate) * 1000
    const hopSec = HOP_SIZE / sampleRate
    this.bandRanges = computeBandRanges(FFT_SIZE, sampleRate)

    // Slightly slower release on low bands: a kick/bassline should bloom
    // and settle like the sound decaying, not snap off like a hi-hat.
    this.bandEnvelopes = {
      sub: new EnvelopeFollower(10, 300, hopMs),
      low: new EnvelopeFollower(10, 250, hopMs),
      mid: new EnvelopeFollower(8, 200, hopMs),
      presence: new EnvelopeFollower(6, 150, hopMs),
      air: new EnvelopeFollower(5, 120, hopMs),
    }
    this.bandNormalizers = {
      sub: new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs),
      low: new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs),
      mid: new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs),
      presence: new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs),
      air: new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs),
    }
    this.fluxNormalizer = new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs)
    this.energyTrajectory = new EnvelopeFollower(ENERGY_TRAJECTORY_MS, ENERGY_TRAJECTORY_MS, hopMs)

    this.beatTracker = new BeatTracker(hopSec)
    this.buildDetector = new BuildDetector(hopMs)
    this.dropDetector = new DropDetector(hopMs)
    this.breakDetector = new BreakDetector(hopMs)

    this.port.postMessage({ kind: 'ready' } satisfies WorkletToMain)
  }

  process(inputs: Float32Array[][]): boolean {
    const input = inputs[0]
    const frameCount = input?.[0]?.length ?? 0
    if (!input || frameCount === 0) return true

    const channelCount = input.length
    for (let i = 0; i < frameCount; i++) {
      let sum = 0
      for (let c = 0; c < channelCount; c++) sum += input[c][i]
      this.ring[this.ringWritePos] = sum / channelCount
      this.ringWritePos = (this.ringWritePos + 1) % FFT_SIZE
      this.samplesSinceHop++
      if (this.ringWritePos === 0) this.filled = true
    }

    while (this.samplesSinceHop >= HOP_SIZE) {
      this.samplesSinceHop -= HOP_SIZE
      if (this.filled) this.analyze()
    }

    return true
  }

  private analyze(): void {
    for (let i = 0; i < FFT_SIZE; i++) {
      this.orderedSamples[i] = this.ring[(this.ringWritePos + i) % FFT_SIZE]
    }

    this.fft.transform(this.orderedSamples, this.mags)

    const bandsRaw = {} as BandEnergies
    bandEnergiesFromMagnitudes(this.mags, this.bandRanges, bandsRaw)
    for (const name of BAND_NAMES) {
      const enveloped = this.bandEnvelopes[name].update(bandsRaw[name])
      bandsRaw[name] = this.bandNormalizers[name].normalize(enveloped)
    }

    const centroidHz = spectralCentroidHz(this.mags, sampleRate, FFT_SIZE)
    const centroid = Math.min(1, centroidHz / CENTROID_NORMALIZATION_CEILING_HZ)
    const flatness = spectralFlatness(this.mags)

    const rawFlux = this.flux.update(this.mags)
    const novelty = this.fluxNormalizer.normalize(rawFlux)

    const tNow = currentTime
    const events: StructuralEvent[] = []

    const { tempoBpm, tempoConfidence, beatPhase } = this.beatTracker.update(novelty, tNow)
    const barPhase = this.barTracker.update(beatPhase, novelty)

    if (barPhase < this.lastBarPhase - 0.5) {
      events.push({ type: 'downbeat', strength: 1, t: tNow })
    }
    this.lastBarPhase = barPhase

    if (novelty > ONSET_EVENT_THRESHOLD && !this.wasAboveOnsetThreshold) {
      events.push({ type: 'onset', strength: novelty, t: tNow })
    }
    this.wasAboveOnsetThreshold = novelty > ONSET_EVENT_THRESHOLD

    const buildProgress = this.buildDetector.update(centroid, bandsRaw.sub)

    const broadbandEnergy = (bandsRaw.sub + bandsRaw.low + bandsRaw.mid + bandsRaw.presence + bandsRaw.air) / 5
    const lowEnergy = (bandsRaw.sub + bandsRaw.low) / 2

    // The drop's signature is the bass reappearing on the beat, not overall
    // loudness rising — a buildup/riser is often already loud and bright
    // (high bands maxed) while sub/low stays suppressed right up to the
    // drop, so "thinned" and "jump" are evaluated on low-band energy.
    const dropEvent = this.dropDetector.update(lowEnergy, beatPhase, tNow)
    if (dropEvent) {
      events.push({ type: 'drop', strength: dropEvent.strength, t: dropEvent.t })
      this.buildDetector.reset()
    }

    const { tension, event: breakEvent } = this.breakDetector.update(lowEnergy, novelty, tNow)
    if (breakEvent) events.push(breakEvent)

    const energy = this.energyTrajectory.update(broadbandEnergy)

    const frame: StateFrame = {
      t: tNow,
      tempo: tempoBpm,
      tempoConfidence,
      beatPhase,
      barPhase,
      buildProgress,
      tension,
      energy,
      bandsRaw,
      centroid,
      flatness,
      events,
    }
    this.port.postMessage({ kind: 'state', frame } satisfies WorkletToMain)
  }
}

registerProcessor('feature-processor', FeatureProcessor)
