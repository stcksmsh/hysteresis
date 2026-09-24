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
import type { Sidecar, SidecarBandEnvelope, SidecarEvent, SidecarOnset, SidecarSection, SidecarStemPresence } from '../src/shared/sidecar'
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

// AGENTS.md §4.3/§4.5 step 6 — deterministic heuristic labeling, not ML/LLM
// (the design doc itself flags learned zero-shot labeling as an optional,
// heavy "ceiling" — no such infra exists in this repo). Two parts:
// (1) the sections this pipeline already detects (build/break) get a plain
// human label matching their kind; (2) genuinely new "intro"/"outro" spans
// are synthesized from whatever's *not* covered by a detected
// section/event — the track's start-to-first-structure and
// last-structure-to-end gaps — since those are otherwise silently unlabeled
// even though they're real, common structure (per §4.1: this project's
// sidecars are already section-sparse). Confidence is raised, not required,
// by stem presence when available: an intro/outro candidate that turns out
// to be LOUD across the board isn't a real intro/outro (e.g. a wall-of-noise
// track with no detected build/break at all) and is skipped rather than
// mislabeled — but the positional heuristic alone still applies without it,
// since analyzeMix() itself has no stem data (§4.5 step 5 is a separate,
// --stems-only pass) and needs to label sections before that ever runs.
const MIN_INTRO_OUTRO_SEC = 2
const LOW_PRESENCE_THRESHOLD = 0.3

function averageStemPresence(stemPresence: SidecarStemPresence, envelopeRate: number, start: number, end: number): number {
  const i0 = Math.max(0, Math.floor(start * envelopeRate))
  const i1 = Math.min(stemPresence.vocals.length, Math.ceil(end * envelopeRate))
  if (i1 <= i0) return 0
  let sum = 0
  let n = 0
  for (let i = i0; i < i1; i++) {
    sum += (stemPresence.vocals[i] ?? 0) + (stemPresence.drums[i] ?? 0) + (stemPresence.bass[i] ?? 0) + (stemPresence.other[i] ?? 0)
    n += 4
  }
  return n > 0 ? sum / n : 0
}

export function labelSections(
  sections: SidecarSection[],
  events: SidecarEvent[],
  duration: number,
  envelopeRate: number,
  stemPresence?: SidecarStemPresence,
): SidecarSection[] {
  const labeled: SidecarSection[] = sections.map((s) => ({
    ...s,
    label: s.kind === 'build' ? 'build' : s.kind === 'break' ? 'breakdown' : s.label,
  }))

  const boundaryTimes = [duration, ...sections.map((s) => s.start), ...events.map((e) => e.t)]
  const earliestBoundary = Math.min(...boundaryTimes)
  if (earliestBoundary >= MIN_INTRO_OUTRO_SEC) {
    const qualifies = !stemPresence || averageStemPresence(stemPresence, envelopeRate, 0, earliestBoundary) < LOW_PRESENCE_THRESHOLD
    if (qualifies) labeled.push({ start: 0, end: earliestBoundary, kind: 'other', label: 'intro' })
  }

  const latestBoundary = Math.max(0, ...sections.map((s) => s.end), ...events.map((e) => e.t))
  if (duration - latestBoundary >= MIN_INTRO_OUTRO_SEC) {
    const qualifies = !stemPresence || averageStemPresence(stemPresence, envelopeRate, latestBoundary, duration) < LOW_PRESENCE_THRESHOLD
    if (qualifies) labeled.push({ start: latestBoundary, end: duration, kind: 'other', label: 'outro' })
  }

  return labeled.sort((a, b) => a.start - b.start)
}

// Runs the same causal Layer 1/2 primitives the realtime worklet uses, but
// offline over the whole mix so tempo/beats/structure converge once rather
// than being estimated live from a cold start (SINTEZA_VIZ.md §6). Single WAV
// master in, no stems or DAW project required — the simpler model §6 asks
// for, trading away the per-stem precision the old REAPER-based pipeline had.
// Same as analyzeMix() but also exposes the per-hop raw arrays/hopSec/
// dropTimes that the SSM pass (scripts/ssm.ts, scripts/repetition.ts) needs
// and analyzeMix()'s own frozen Sidecar-shaped return doesn't carry.
// analyzeMix() itself stays byte-for-byte the same (schema 3, same shape,
// same tests) — this is a pure refactor, not a behavior change.
export interface AnalyzeMixDetailed {
  sidecar: Sidecar
  bandRaw: Record<BandName, Float32Array>
  centroidRaw: Float32Array
  flatnessRaw: Float32Array
  hopSec: number
  dropTimes: number[]
}

export function analyzeMix(wav: DecodedWav): Sidecar {
  return analyzeMixDetailed(wav).sidecar
}

export function analyzeMixDetailed(wav: DecodedWav): AnalyzeMixDetailed {
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

    const { event: breakEvent } = breakDetector.update(lowEnergy, novelty, tNow)
    if (breakEvent && (breakEvent.type === 'breakStart' || breakEvent.type === 'breakEnd')) {
      events.push({ type: breakEvent.type, t: breakEvent.t, strength: breakEvent.strength })
    }

    const dropSignal = dropEnergyNormalizer.normalize(dropEnergyEnvelope.update(rawLowEnergy))
    const dropFeatures = {
      lowEnergy: dropSignal,
      onsetActivity: novelty,
      vec: [bandsRaw.sub, bandsRaw.low, bandsRaw.mid, bandsRaw.presence, bandsRaw.air, centroid, flatnessRaw[h]],
    }
    const dropEvent = dropDetector.update(dropFeatures, beatPhase, tempoBpm, tNow)
    if (dropEvent) {
      events.push({ type: 'drop', t: dropEvent.t, strength: dropEvent.strength })
      dropTimes.push(dropEvent.t)
      buildDetector.reset()
    }

    buildDetector.update(centroid, bandsRaw.sub)
  }

  const buildSections = buildWindowsFromDrops(dropTimes, finalTempo, duration)
  const breakSections = breakSectionsFromEvents(events.filter((e) => e.type === 'breakStart' || e.type === 'breakEnd'))
  const unlabeledSections = [...buildSections, ...breakSections].sort((a, b) => a.start - b.start)
  const sections = labelSections(unlabeledSections, events, duration, ENVELOPE_RATE_HZ)

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
    sidecar: {
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
    },
    bandRaw,
    centroidRaw,
    flatnessRaw,
    hopSec,
    dropTimes,
  }
}

// AGENTS.md §4.3/§4.5 step 5 — offline per-stem presence from Demucs
// separation (`scripts/demucs.ts`), `analyze.ts --stems` only. "Presence",
// not "what note": a stem's own normalized loudness over time — the
// reliable, cheap-post-separation signal that's exactly what "track the
// vocal" visually needs (§4.3: "is it present, and how prominent, right
// now"). Same envelopeRate/downsample machinery as the main mix's
// envelopes, just applied per-stem, so `StructureSource.sampleEnvelope()`
// needs no special-casing.
export interface StemInputs {
  vocals: DecodedWav
  drums: DecodedWav
  bass: DecodedWav
  other: DecodedWav
}

function mixDownMono(wav: DecodedWav): Float32Array {
  const frameCount = wav.channels[0]?.length ?? 0
  const mono = new Float32Array(frameCount)
  for (let i = 0; i < frameCount; i++) {
    let sum = 0
    for (const c of wav.channels) sum += c[i]
    mono[i] = sum / wav.channels.length
  }
  return mono
}

// RMS-per-hop, envelope-followed and adaptively normalized against this
// stem's own dynamic range — deliberately simpler than the main mix's full
// band/FFT pipeline (bands.ts) since "is this stem present" only needs
// broadband loudness, not spectral shape.
function computePresenceEnvelope(mono: Float32Array, sampleRate: number): number[] {
  const hopSec = HOP_SIZE / sampleRate
  const hopMs = hopSec * 1000
  const totalHops = Math.max(0, Math.floor(mono.length / HOP_SIZE))
  const envelope = new EnvelopeFollower(15, 200, hopMs)
  const normalizer = new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs)
  const raw = new Float32Array(totalHops)
  for (let h = 0; h < totalHops; h++) {
    const start = h * HOP_SIZE
    const end = Math.min(mono.length, start + HOP_SIZE)
    let sumSq = 0
    for (let i = start; i < end; i++) sumSq += mono[i] * mono[i]
    raw[h] = normalizer.normalize(envelope.update(end > start ? Math.sqrt(sumSq / (end - start)) : 0))
  }
  const hopsPerEnvelopeSample = Math.max(1, Math.round(1 / ENVELOPE_RATE_HZ / hopSec))
  const envelopeLength = Math.max(1, Math.ceil(totalHops / hopsPerEnvelopeSample))
  return downsample(raw, hopsPerEnvelopeSample, envelopeLength)
}

// AGENTS.md §4.5 step 7 — lead salience within `other` (approximate, per the
// design doc's own simpler suggested approach: "the loudest *sustained*
// band-limited component" per hop, not a real isolated-instrument signal).
// A slower release than computePresenceEnvelope's (400ms vs 200ms) is the
// actual "sustained, not instantaneous peak" distinction — a single loud
// transient bin decays back out quickly; a real held lead tone doesn't.
function computeLeadPresenceEnvelope(mono: Float32Array, sampleRate: number): number[] {
  const hopSec = HOP_SIZE / sampleRate
  const hopMs = hopSec * 1000
  const totalHops = Math.max(0, Math.floor((mono.length - FFT_SIZE) / HOP_SIZE) + 1)
  const fft = new WindowedFFT(FFT_SIZE)
  const mags = new Float32Array(fft.bins)
  const window = new Float32Array(FFT_SIZE)
  const envelope = new EnvelopeFollower(30, 400, hopMs)
  const normalizer = new AdaptiveNormalizer(NORMALIZER_DECAY_MS, hopMs)
  const raw = new Float32Array(totalHops)
  for (let h = 0; h < totalHops; h++) {
    const start = h * HOP_SIZE
    window.fill(0)
    window.set(mono.subarray(start, Math.min(mono.length, start + FFT_SIZE)))
    fft.transform(window, mags)
    let peak = 0
    for (let i = 1; i < mags.length; i++) if (mags[i] > peak) peak = mags[i]
    raw[h] = normalizer.normalize(envelope.update(peak))
  }
  const hopsPerEnvelopeSample = Math.max(1, Math.round(1 / ENVELOPE_RATE_HZ / hopSec))
  const envelopeLength = Math.max(1, Math.ceil(totalHops / hopsPerEnvelopeSample))
  return downsample(raw, hopsPerEnvelopeSample, envelopeLength)
}

export function computeStemPresence(stems: StemInputs): SidecarStemPresence {
  const otherMono = mixDownMono(stems.other)
  return {
    vocals: computePresenceEnvelope(mixDownMono(stems.vocals), stems.vocals.sampleRate),
    drums: computePresenceEnvelope(mixDownMono(stems.drums), stems.drums.sampleRate),
    bass: computePresenceEnvelope(mixDownMono(stems.bass), stems.bass.sampleRate),
    other: computePresenceEnvelope(otherMono, stems.other.sampleRate),
    leadPresence: computeLeadPresenceEnvelope(otherMono, stems.other.sampleRate),
  }
}
