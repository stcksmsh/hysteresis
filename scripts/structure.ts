import { WindowedFFT } from '../src/audio/worklet/fft'
import {
  computeBandRanges,
  bandEnergiesFromMagnitudes,
  dominantBandTone,
  BAND_NAMES,
  type BandName,
  type BandRanges,
} from '../src/audio/worklet/bands'
import { spectralCentroidHz, spectralFlatness } from '../src/audio/worklet/spectral'
import { SpectralFlux } from '../src/audio/worklet/onset'
import { EnvelopeFollower, AdaptiveNormalizer } from '../src/audio/worklet/envelope'
import { BeatTracker, BarTracker } from '../src/audio/worklet/brain/beat-tracker'
import { BuildDetector } from '../src/audio/worklet/brain/build-detector'
import { DropDetector } from '../src/audio/worklet/brain/drop-detector'
import { BreakDetector } from '../src/audio/worklet/brain/break-detector'
import { FFT_SIZE, HOP_SIZE } from '../src/shared/constants'
import type { BandEnergies } from '../src/shared/types'
import type { Sidecar, SidecarBandEnvelope, SidecarEvent, SidecarOnset, SidecarSection } from '../src/shared/sidecar'
import { SIDECAR_SCHEMA_VERSION } from '../src/shared/sidecar'
import type { DecodedWav } from './wav'

// Same rising-edge threshold feature-worklet.ts uses live, so an offline
// onset means the same thing a live one does.
const ONSET_EVENT_THRESHOLD = 0.4

// scripts/structure.ts downmixes to mono before analysis (see `mono` below),
// so there is no real stereo signal left to place an onset with. This is a
// deterministic, non-measured stand-in purely so onset particles/beam
// placement in position-only mode (schema 2) has some spread instead of
// collapsing every onset onto the center.
function syntheticPan(t: number): number {
  return Math.sin(t * 37.13) * 0.6
}

// Downsamples a per-hop Float32Array to envelopeRate-Hz samples the same way
// the original energyEnvelope loop did — shared across every envelope field
// schema 2 adds so they all agree on timing.
function downsample(raw: Float32Array, hopsPerSample: number, envelopeLength: number): number[] {
  const out: number[] = new Array(envelopeLength)
  for (let i = 0; i < envelopeLength; i++) {
    const s = i * hopsPerSample
    const e = Math.min(raw.length, s + hopsPerSample)
    let sum = 0
    let n = 0
    for (let h = s; h < e; h++) {
      sum += raw[h]
      n++
    }
    out[i] = n > 0 ? clamp01(sum / n) : 0
  }
  return out
}

const CENTROID_CEILING_HZ = 8000
const NORMALIZER_DECAY_MS = 6000
const DROP_NORMALIZER_DECAY_MS = 45000
const BUILD_WINDOW_BARS = 8
export const ENVELOPE_RATE_HZ = 20

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v))
}

// Anticipation windows synthesized backward from known drop times, the same
// idea the old stem-based compiler used (see git history), just anchored to
// one estimated tempo instead of an exact DAW tempo map. StructureSource
// re-derives the eased 0->1 curve from these spans at playback time — the
// sidecar only carries the span, not a baked curve (SINTEZA_VIZ.md §6).
function buildWindowsFromDrops(dropTimes: number[], tempoBpm: number, duration: number): SidecarSection[] {
  const barSec = (4 * 60) / Math.max(1, tempoBpm)
  const windowSec = BUILD_WINDOW_BARS * barSec
  const sorted = [...dropTimes].sort((a, b) => a - b)
  const windows: SidecarSection[] = []
  for (let i = 0; i < sorted.length; i++) {
    const drop = sorted[i]
    const prevDrop = i > 0 ? sorted[i - 1] : -Infinity
    const start = Math.max(drop - windowSec, prevDrop, 0)
    if (drop <= start) continue
    windows.push({ start, end: drop, kind: 'build' })
  }
  return windows
}

function breakSectionsFromEvents(events: SidecarEvent[]): SidecarSection[] {
  const sections: SidecarSection[] = []
  for (let i = 0; i + 1 < events.length; i++) {
    if (events[i].type === 'breakStart' && events[i + 1].type === 'breakEnd') {
      sections.push({ start: events[i].t, end: events[i + 1].t, kind: 'break' })
    }
  }
  return sections
}

// Runs the same causal Layer 1/2 primitives the realtime worklet uses, but
// offline over the whole mix so tempo/beats/structure converge once rather
// than being estimated live from a cold start (SINTEZA_VIZ.md §6). Single WAV
// master in, no stems or DAW project required — the simpler model §6 asks
// for, trading away the per-stem precision the old REAPER-based pipeline had.
export function analyzeMix(wav: DecodedWav): Sidecar {
  const { sampleRate, channels } = wav
  const frameCount = channels[0]?.length ?? 0
  const duration = frameCount / sampleRate
  const mono = new Float32Array(frameCount)
  for (let i = 0; i < frameCount; i++) {
    let sum = 0
    for (const c of channels) sum += c[i]
    mono[i] = sum / channels.length
  }

  const fft = new WindowedFFT(FFT_SIZE)
  const mags = new Float32Array(fft.bins)
  const flux = new SpectralFlux(fft.bins)
  const hopSec = HOP_SIZE / sampleRate
  const hopMs = hopSec * 1000
  const bandRanges: BandRanges = computeBandRanges(FFT_SIZE, sampleRate)

  const bandEnvelopes: Record<BandName, EnvelopeFollower> = {
    sub: new EnvelopeFollower(10, 300, hopMs),
    low: new EnvelopeFollower(10, 250, hopMs),
    mid: new EnvelopeFollower(8, 200, hopMs),
    presence: new EnvelopeFollower(6, 150, hopMs),
    air: new EnvelopeFollower(5, 120, hopMs),
  }
  const bandNormalizers: Record<BandName, AdaptiveNormalizer> = {
    sub: new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs),
    low: new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs),
    mid: new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs),
    presence: new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs),
    air: new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs),
  }
  const fluxNormalizer = new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs)
  const dropEnergyEnvelope = new EnvelopeFollower(30, 220, hopMs)
  const dropEnergyNormalizer = new AdaptiveNormalizer(DROP_NORMALIZER_DECAY_MS, hopMs)

  const beatTracker = new BeatTracker(hopSec)
  const barTracker = new BarTracker()
  const buildDetector = new BuildDetector(hopMs)
  const dropDetector = new DropDetector(hopMs)
  const breakDetector = new BreakDetector(hopMs)

  const totalHops = Math.max(0, Math.floor((frameCount - FFT_SIZE) / HOP_SIZE) + 1)
  const window = new Float32Array(FFT_SIZE)
  const energyRaw = new Float32Array(totalHops)
  const bandRaw: Record<BandName, Float32Array> = {
    sub: new Float32Array(totalHops),
    low: new Float32Array(totalHops),
    mid: new Float32Array(totalHops),
    presence: new Float32Array(totalHops),
    air: new Float32Array(totalHops),
  }
  const centroidRaw = new Float32Array(totalHops)
  const flatnessRaw = new Float32Array(totalHops)

  const beats: number[] = []
  const events: SidecarEvent[] = []
  const onsets: SidecarOnset[] = []
  const dropTimes: number[] = []
  let lastBeatPhase = 0
  let lastBarPhase = 0
  let wasAboveOnsetThreshold = false
  let finalTempo = 120
  let tempoSum = 0
  let tempoSamples = 0

  for (let h = 0; h < totalHops; h++) {
    const start = h * HOP_SIZE
    window.fill(0)
    window.set(mono.subarray(start, Math.min(frameCount, start + FFT_SIZE)))
    fft.transform(window, mags)

    const bandsRaw = {} as BandEnergies
    bandEnergiesFromMagnitudes(mags, bandRanges, bandsRaw)
    const rawLowEnergy = (bandsRaw.sub + bandsRaw.low) / 2
    for (const name of BAND_NAMES) {
      const enveloped = bandEnvelopes[name].update(bandsRaw[name])
      bandsRaw[name] = bandNormalizers[name].normalize(enveloped)
    }
    const lowEnergy = (bandsRaw.sub + bandsRaw.low) / 2
    energyRaw[h] = (bandsRaw.sub + bandsRaw.low + bandsRaw.mid + bandsRaw.presence + bandsRaw.air) / 5
    for (const name of BAND_NAMES) bandRaw[name][h] = bandsRaw[name]

    const centroidHz = spectralCentroidHz(mags, sampleRate, FFT_SIZE)
    const centroid = Math.min(1, centroidHz / CENTROID_CEILING_HZ)
    centroidRaw[h] = centroid
    flatnessRaw[h] = spectralFlatness(mags)
    const novelty = fluxNormalizer.normalize(flux.update(mags))

    const tNow = start / sampleRate
    const { tempoBpm, beatPhase } = beatTracker.update(novelty, tNow)
    const barPhase = barTracker.update(beatPhase, novelty)

    if (beatPhase < lastBeatPhase - 0.5) beats.push(tNow)
    lastBeatPhase = beatPhase

    // Same rising-edge onset rule feature-worklet.ts uses live (SINTEZA_VIZ.md
    // §5) — for position-only playback (schema 2), this is the only source
    // of onset pulses at all.
    if (novelty > ONSET_EVENT_THRESHOLD && !wasAboveOnsetThreshold) {
      onsets.push({ t: tNow, strength: novelty, tone: dominantBandTone(bandsRaw), pan: syntheticPan(tNow) })
    }
    wasAboveOnsetThreshold = novelty > ONSET_EVENT_THRESHOLD

    if (barPhase < lastBarPhase - 0.5) events.push({ type: 'downbeat', t: tNow, strength: 1 })
    lastBarPhase = barPhase

    // Tempo converges over the first several seconds; average the back half
    // of the file (well past convergence) into the single reported value.
    if (tNow > duration * 0.5) {
      tempoSum += tempoBpm
      tempoSamples++
    }
    finalTempo = tempoSamples > 0 ? tempoSum / tempoSamples : tempoBpm

    const { tension, event: breakEvent } = breakDetector.update(lowEnergy, novelty, tNow)
    if (breakEvent && (breakEvent.type === 'breakStart' || breakEvent.type === 'breakEnd')) {
      events.push({ type: breakEvent.type, t: breakEvent.t, strength: breakEvent.strength })
    }

    const dropSignal = dropEnergyNormalizer.normalize(dropEnergyEnvelope.update(rawLowEnergy))
    const dropEvent = dropDetector.update(dropSignal, tension, beatPhase, tempoBpm, tNow)
    if (dropEvent) {
      events.push({ type: 'drop', t: dropEvent.t, strength: dropEvent.strength })
      dropTimes.push(dropEvent.t)
      buildDetector.reset()
    }

    buildDetector.update(centroid, bandsRaw.sub)
  }

  const buildSections = buildWindowsFromDrops(dropTimes, finalTempo, duration)
  const breakSections = breakSectionsFromEvents(events.filter((e) => e.type === 'breakStart' || e.type === 'breakEnd'))
  const sections = [...buildSections, ...breakSections].sort((a, b) => a.start - b.start)

  const hopsPerEnvelopeSample = Math.max(1, Math.round(1 / ENVELOPE_RATE_HZ / hopSec))
  const envelopeLength = Math.max(1, Math.ceil(totalHops / hopsPerEnvelopeSample))
  const energyEnvelope = downsample(energyRaw, hopsPerEnvelopeSample, envelopeLength)
  const bandEnvelope: SidecarBandEnvelope = {
    sub: downsample(bandRaw.sub, hopsPerEnvelopeSample, envelopeLength),
    low: downsample(bandRaw.low, hopsPerEnvelopeSample, envelopeLength),
    mid: downsample(bandRaw.mid, hopsPerEnvelopeSample, envelopeLength),
    presence: downsample(bandRaw.presence, hopsPerEnvelopeSample, envelopeLength),
    air: downsample(bandRaw.air, hopsPerEnvelopeSample, envelopeLength),
  }
  const centroidEnvelope = downsample(centroidRaw, hopsPerEnvelopeSample, envelopeLength)
  const flatnessEnvelope = downsample(flatnessRaw, hopsPerEnvelopeSample, envelopeLength)

  events.sort((a, b) => a.t - b.t)
  onsets.sort((a, b) => a.t - b.t)

  return {
    schema: SIDECAR_SCHEMA_VERSION,
    duration,
    tempo: finalTempo,
    beats,
    sections,
    events,
    onsets,
    energyEnvelope,
    bandEnvelope,
    centroidEnvelope,
    flatnessEnvelope,
    envelopeRate: ENVELOPE_RATE_HZ,
  }
}
