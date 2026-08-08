/// <reference types="audioworklet" />
import { WindowedFFT } from './fft'
import { computeBandRanges, bandEnergiesFromMagnitudes, dominantBandTone, BAND_NAMES, type BandName, type BandRanges } from './bands'
import { spectralCentroidHz, spectralFlatness } from './spectral'
import { SpectralFlux } from './onset'
import { EnvelopeFollower, AdaptiveNormalizer } from './envelope'
import { BeatTracker, BarTracker } from './brain/beat-tracker'
import { BuildDetector } from './brain/build-detector'
import { DropDetector } from './brain/drop-detector'
import { BreakDetector } from './brain/break-detector'
import { PlacementBands } from './placement-bands'
import { FFT_SIZE, HOP_SIZE, SCOPE_SIZE } from '../../shared/constants'
import type { BandEnergies, SpectralHit, StateFrame, StructuralEvent, WorkletToMain } from '../../shared/types'

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

// Much longer horizon than the display normaliser: the reference level must
// outlive a whole breakdown, otherwise it adapts down to the quiet section
// and the drop's return to full level registers as no change at all.
const DROP_NORMALIZER_DECAY_MS = 45000

// Pan is a slow, structural property of the mix — smoothing it keeps a
// single off-centre hi-hat from throwing the whole placement sideways.
const PAN_SMOOTHING = 0.15

class FeatureProcessor extends AudioWorkletProcessor implements AudioWorkletProcessorImpl {
  private ringL = new Float32Array(FFT_SIZE)
  private ringR = new Float32Array(FFT_SIZE)
  private ringWritePos = 0
  private samplesSinceHop = 0
  private filled = false

  private fft = new WindowedFFT(FFT_SIZE)
  private mags = new Float32Array(this.fft.bins) // mono, for existing analysis
  private magsL = new Float32Array(this.fft.bins)
  private magsR = new Float32Array(this.fft.bins)
  private flux = new SpectralFlux(this.fft.bins)
  private orderedL = new Float32Array(FFT_SIZE)
  private orderedR = new Float32Array(FFT_SIZE)
  private scopeBuffer = new Float32Array(SCOPE_SIZE)
  private placementBands: PlacementBands

  private bandRanges: BandRanges
  private bandEnvelopes: Record<BandName, EnvelopeFollower>
  private bandNormalizers: Record<BandName, AdaptiveNormalizer>
  private fluxNormalizer: AdaptiveNormalizer
  private energyTrajectory: EnvelopeFollower
  private dropEnergyEnvelope: EnvelopeFollower
  private dropEnergyNormalizer: AdaptiveNormalizer

  private beatTracker: BeatTracker
  private barTracker = new BarTracker()
  private buildDetector: BuildDetector
  private dropDetector: DropDetector
  private breakDetector: BreakDetector

  private wasAboveOnsetThreshold = false
  private lastBarPhase = 0
  private leftEnergyAccum = 0
  private rightEnergyAccum = 0
  private energyAccumCount = 0
  private smoothedPan = 0

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
    this.dropEnergyEnvelope = new EnvelopeFollower(30, 220, hopMs)
    this.dropEnergyNormalizer = new AdaptiveNormalizer(DROP_NORMALIZER_DECAY_MS, hopMs)

    this.placementBands = new PlacementBands(FFT_SIZE, sampleRate, hopMs)
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
    const left = input[0]
    const right = channelCount > 1 ? input[1] : input[0]
    for (let i = 0; i < frameCount; i++) {
      this.ringL[this.ringWritePos] = left[i]
      this.ringR[this.ringWritePos] = right[i]
      this.ringWritePos = (this.ringWritePos + 1) % FFT_SIZE
      this.samplesSinceHop++
      if (this.ringWritePos === 0) this.filled = true

      // Whole-mix balance, kept alongside the per-band pans for choreography
      // use; per-band placement uses the spectra instead.
      this.leftEnergyAccum += Math.abs(left[i])
      this.rightEnergyAccum += Math.abs(right[i])
      this.energyAccumCount++
    }

    while (this.samplesSinceHop >= HOP_SIZE) {
      this.samplesSinceHop -= HOP_SIZE
      if (this.filled) this.analyze()
    }

    return true
  }

  private consumePan(): number {
    if (this.energyAccumCount > 0) {
      const l = this.leftEnergyAccum
      const r = this.rightEnergyAccum
      const total = l + r
      const instantaneous = total > 1e-6 ? (r - l) / total : 0
      this.smoothedPan += (instantaneous - this.smoothedPan) * PAN_SMOOTHING
      this.leftEnergyAccum = 0
      this.rightEnergyAccum = 0
      this.energyAccumCount = 0
    }
    return Math.max(-1, Math.min(1, this.smoothedPan))
  }

  private analyze(): void {
    for (let i = 0; i < FFT_SIZE; i++) {
      const idx = (this.ringWritePos + i) % FFT_SIZE
      this.orderedL[i] = this.ringL[idx]
      this.orderedR[i] = this.ringR[idx]
    }

    // Transform each channel rather than a mono downmix: per-band pan is
    // only recoverable from separate L/R spectra. The mono magnitudes the
    // rest of the analysis uses are averaged from these, which also avoids
    // the phase cancellation a summed downmix can suffer.
    this.fft.transform(this.orderedL, this.magsL)
    this.fft.transform(this.orderedR, this.magsR)
    for (let i = 0; i < this.mags.length; i++) {
      this.mags[i] = (this.magsL[i] + this.magsR[i]) * 0.5
    }

    const spectralHits: SpectralHit[] = []
    this.placementBands.update(this.magsL, this.magsR, spectralHits)

    const bandsRaw = {} as BandEnergies
    bandEnergiesFromMagnitudes(this.mags, this.bandRanges, bandsRaw)

    // Captured before per-band normalisation. The 6s adaptive normaliser
    // rescales each band against its own recent peak, which is right for
    // display but erases exactly the contrast a drop is made of: during a
    // breakdown the sub peak decays until quiet bass hits read ~1.0, so the
    // bass "returning" at the drop shows no step at all. The drop detector
    // needs a signal where loud and quiet stay distinguishable.
    const rawLowEnergy = (bandsRaw.sub + bandsRaw.low) / 2

    for (const name of BAND_NAMES) {
      const enveloped = this.bandEnvelopes[name].update(bandsRaw[name])
      bandsRaw[name] = this.bandNormalizers[name].normalize(enveloped)
    }

    const centroidHz = spectralCentroidHz(this.mags, sampleRate, FFT_SIZE)
    const centroid = Math.min(1, centroidHz / CENTROID_NORMALIZATION_CEILING_HZ)
    const flatness = spectralFlatness(this.mags)

    const rawFlux = this.flux.update(this.mags)
    const novelty = this.fluxNormalizer.normalize(rawFlux)

    const pan = this.consumePan()

    const tNow = currentTime
    const events: StructuralEvent[] = []

    const { tempoBpm, tempoConfidence, beatPhase } = this.beatTracker.update(novelty, tNow)
    const barPhase = this.barTracker.update(beatPhase, novelty)

    if (barPhase < this.lastBarPhase - 0.5) {
      events.push({ type: 'downbeat', strength: 1, t: tNow })
    }
    this.lastBarPhase = barPhase

    if (novelty > ONSET_EVENT_THRESHOLD && !this.wasAboveOnsetThreshold) {
      // Tag the hit with where it sits in the mix so the visual can place it:
      // dominant band gives the vertical position, pan the horizontal.
      events.push({ type: 'onset', strength: novelty, t: tNow, tone: dominantBandTone(bandsRaw), pan })
    }
    this.wasAboveOnsetThreshold = novelty > ONSET_EVENT_THRESHOLD

    const buildProgress = this.buildDetector.update(centroid, bandsRaw.sub)

    const broadbandEnergy = (bandsRaw.sub + bandsRaw.low + bandsRaw.mid + bandsRaw.presence + bandsRaw.air) / 5
    const lowEnergy = (bandsRaw.sub + bandsRaw.low) / 2

    // Break/tension is computed first because the drop detector consumes it:
    // a drop is defined as the *resolution of a thinned section*, so it needs
    // this hop's tension to decide whether a jump qualifies at all.
    const { tension, event: breakEvent } = this.breakDetector.update(lowEnergy, novelty, tNow)
    if (breakEvent) events.push(breakEvent)

    // The drop's signature is the bass reappearing on the beat, not overall
    // loudness rising — a buildup/riser is often already loud and bright
    // (high bands maxed) while sub/low stays suppressed right up to the
    // drop, so the jump is evaluated on low-band energy.
    const dropSignal = this.dropEnergyNormalizer.normalize(this.dropEnergyEnvelope.update(rawLowEnergy))
    const dropEvent = this.dropDetector.update(dropSignal, tension, beatPhase, tempoBpm, tNow)
    if (dropEvent) {
      events.push({ type: 'drop', strength: dropEvent.strength, t: dropEvent.t })
      this.buildDetector.reset()
    }

    const energy = this.energyTrajectory.update(broadbandEnergy)
    const scope = this.extractScope()

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
      pan,
      spectralHits,
      events,
      scope,
    }
    this.port.postMessage({ kind: 'state', frame } satisfies WorkletToMain)
  }

  // Beam waveform: trigger on the first rising zero-crossing in the ordered
  // (chronological) ring buffer so the trace sits still frame to frame
  // instead of jittering — a static window would resample a different phase
  // of a periodic waveform every hop. Search is bounded to leave room for a
  // full SCOPE_SIZE window after the trigger.
  private extractScope(): Float32Array {
    const maxStart = FFT_SIZE - SCOPE_SIZE
    let trigger = 0
    for (let i = 1; i < maxStart; i++) {
      if (this.orderedL[i - 1] <= 0 && this.orderedL[i] > 0) {
        trigger = i
        break
      }
    }
    for (let i = 0; i < SCOPE_SIZE; i++) this.scopeBuffer[i] = this.orderedL[trigger + i]
    return this.scopeBuffer
  }
}

registerProcessor('feature-processor', FeatureProcessor)
