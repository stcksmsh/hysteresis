import { WindowedFFT } from '../../src/audio/worklet/fft'
import { computeBandRanges, bandEnergiesFromMagnitudes, BAND_NAMES, type BandName, type BandRanges } from '../../src/audio/worklet/bands'
import { spectralCentroidHz } from '../../src/audio/worklet/spectral'
import { SpectralFlux } from '../../src/audio/worklet/onset'
import { EnvelopeFollower, AdaptiveNormalizer } from '../../src/audio/worklet/envelope'
import { BuildDetector } from '../../src/audio/worklet/brain/build-detector'
import { DropDetector } from '../../src/audio/worklet/brain/drop-detector'
import { BreakDetector } from '../../src/audio/worklet/brain/break-detector'
import { FFT_SIZE, HOP_SIZE } from '../../src/shared/constants'
import type { BandEnergies, StructuralEvent } from '../../src/shared/types'
import { type TempoMarker, type TimelineMarker, type TimelineSection, musicalPositionAt, classifyMarker } from '../../src/shared/timeline'
import type { DecodedWav } from './wav'
import type { StemAnalysis } from './analyze'

const CENTROID_CEILING_HZ = 8000
const NORMALIZER_DECAY_MS = 6000
const DROP_NORMALIZER_DECAY_MS = 45000

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v))
}

// Bar length at time `t`, from the tempo map's own time signature — the
// window a synthesized build ramp or a downbeat grid is measured in.
function barSecondsAt(tempoMap: TempoMarker[], t: number): number {
  let active: TempoMarker = tempoMap[0] ?? { t: 0, bpm: 120, num: 4, den: 4 }
  for (const marker of tempoMap) {
    if (marker.t > t) break
    active = marker
  }
  return (Math.max(1, active.num) * 60) / Math.max(1, active.bpm)
}

// Downbeats are usually *guessed* live (BarTracker assumes 4/4 and learns
// which beat-in-bar tends to land loudest). Offline, the tempo map already
// carries the real time signature at every marker, so bar boundaries are
// just arithmetic — no heuristic needed, and no 4/4 assumption either.
function downbeatsFromTempoMap(tempoMap: TempoMarker[], duration: number): StructuralEvent[] {
  if (tempoMap.length === 0) return []
  const events: StructuralEvent[] = []
  let lastBarPhase = 0
  const stepSec = 1 / 20 // fine enough to not miss a downbeat crossing
  for (let t = 0; t <= duration; t += stepSec) {
    const { barPhase } = musicalPositionAt(tempoMap, t)
    if (barPhase < lastBarPhase - 0.5) events.push({ type: 'downbeat', strength: 1, t })
    lastBarPhase = barPhase
  }
  return events
}

// Percussive stems are silent between hits, so a *mean* over a ~1s window
// is mostly silence and dilutes a genuine level increase down to noise —
// peak survives that: a beat period is well under either window length, so
// at least one real hit always lands in each window, and its post-percentile-
// normalization level is what actually changed.
function maxOverSamples(env: Uint8Array, start: number, end: number): number {
  if (end <= start || env.length === 0) return 0
  let peak = 0
  for (let i = start; i < end; i++) peak = Math.max(peak, env[Math.min(i, env.length - 1)] / 255)
  return peak
}

// The actually-novel piece: a drop is scored by how many *isolated stems*
// jump together, not by whole-mix low-band energy. This needs simultaneous
// knowledge of every stem's near-future trajectory, which only exists
// offline — no causal/realtime algorithm can look 1s ahead across N tracks
// at once.
export function detectDropsFromStems(
  stemLevelEnvelopes: Uint8Array[],
  rate: number,
  duration: number,
  opts: { beforeSec?: number; afterSec?: number; jumpThreshold?: number; minCoincidence?: number; refractorySec?: number } = {},
): StructuralEvent[] {
  if (stemLevelEnvelopes.length === 0) return []
  const beforeSec = opts.beforeSec ?? 1.5
  const afterSec = opts.afterSec ?? 1.0
  const jumpThreshold = opts.jumpThreshold ?? 0.15
  const minCoincidence = opts.minCoincidence ?? Math.max(1, Math.min(2, stemLevelEnvelopes.length))
  const refractorySec = opts.refractorySec ?? 3

  const n = Math.max(1, Math.ceil(duration * rate))
  const beforeSamples = Math.round(beforeSec * rate)
  const afterSamples = Math.round(afterSec * rate)

  const coincidence = new Float32Array(n)
  const avgJump = new Float32Array(n)
  for (let i = 0; i < n; i++) {
    let hits = 0
    let jumpSum = 0
    for (const env of stemLevelEnvelopes) {
      const before = maxOverSamples(env, Math.max(0, i - beforeSamples), i)
      const after = maxOverSamples(env, i, i + afterSamples)
      const jump = after - before
      if (jump > jumpThreshold) {
        hits++
        jumpSum += jump
      }
    }
    coincidence[i] = hits
    avgJump[i] = hits > 0 ? jumpSum / hits : 0
  }

  const events: StructuralEvent[] = []
  let lastAcceptedT = -Infinity
  const peakHalfWindow = Math.round((refractorySec / 2) * rate)
  for (let i = 0; i < n; i++) {
    if (coincidence[i] < minCoincidence) continue
    const t = i / rate
    if (t - lastAcceptedT < refractorySec) continue

    let isPeak = true
    for (let j = Math.max(0, i - peakHalfWindow); j <= Math.min(n - 1, i + peakHalfWindow); j++) {
      if (coincidence[j] > coincidence[i] || (coincidence[j] === coincidence[i] && avgJump[j] > avgJump[i])) {
        isPeak = false
        break
      }
    }
    if (!isPeak) continue

    events.push({ type: 'drop', strength: clamp01(avgJump[i] / 0.6), t })
    lastAcceptedT = t
  }
  return events
}

// Fraction of stems sounding at each sample, averaged — a proxy for "how
// full is the arrangement right now" that both break detection and the
// baked tension curve are built from.
function computeActivityCurve(stemLevelEnvelopes: Uint8Array[], rate: number, duration: number): Float32Array {
  const n = Math.max(1, Math.ceil(duration * rate))
  const activity = new Float32Array(n)
  if (stemLevelEnvelopes.length === 0) return activity
  for (let i = 0; i < n; i++) {
    let sum = 0
    for (const env of stemLevelEnvelopes) sum += env.length > 0 ? env[Math.min(i, env.length - 1)] / 255 : 0
    activity[i] = sum / stemLevelEnvelopes.length
  }
  return activity
}

// A break's edges are both already known offline — unlike the realtime
// hysteresis detector (which exists purely to survive not knowing whether a
// dip in energy will keep falling or bounce back), this just finds maximal
// low-activity spans directly.
export function detectBreaksFromStems(
  stemLevelEnvelopes: Uint8Array[],
  rate: number,
  duration: number,
  opts: { activityFloor?: number; minBreakSec?: number } = {},
): StructuralEvent[] {
  const activityFloor = opts.activityFloor ?? 0.35
  const minBreakSec = opts.minBreakSec ?? 2
  const activity = computeActivityCurve(stemLevelEnvelopes, rate, duration)
  const n = activity.length

  const events: StructuralEvent[] = []
  let spanStart: number | null = null
  let tensionSum = 0
  let count = 0

  const closeSpan = (spanEndT: number) => {
    if (spanStart === null) return
    if (spanEndT - spanStart >= minBreakSec) {
      const strength = count > 0 ? tensionSum / count : 0
      events.push({ type: 'breakStart', strength, t: spanStart })
      events.push({ type: 'breakEnd', strength: 1 - strength, t: spanEndT })
    }
    spanStart = null
  }

  for (let i = 0; i < n; i++) {
    const t = i / rate
    if (activity[i] < activityFloor) {
      if (spanStart === null) {
        spanStart = t
        tensionSum = 0
        count = 0
      }
      tensionSum += 1 - activity[i]
      count++
    } else {
      closeSpan(t)
    }
  }
  closeSpan(duration)

  return events
}

function downsampleCurve(curve: Float32Array, hopSec: number, rate: number, length: number): Uint8Array {
  const hopsPerSample = Math.max(1, Math.round(1 / rate / hopSec))
  const out = new Uint8Array(length)
  for (let i = 0; i < length; i++) {
    const start = i * hopsPerSample
    const end = Math.min(curve.length, start + hopsPerSample)
    let sum = 0
    let n = 0
    for (let h = start; h < end; h++) {
      sum += curve[h]
      n++
    }
    out[i] = n > 0 ? Math.round(clamp01(sum / n) * 255) : 0
  }
  return out
}

// Anticipation curve synthesized *backward* from known drop times, rather
// than integrated forward from silence: it's guaranteed to peak at exactly 1
// right at the drop, instead of approximating that peak via an integrator's
// gain/decay constants. Eased (quadratic) so it still reads as "winding up"
// rather than a linear ramp. Also returns the ramp windows used, so callers
// can label them as `build` sections.
export function synthesizeBuildCurve(
  dropTimes: number[],
  tempoMap: TempoMarker[],
  duration: number,
  rate: number,
  bars = 8,
): { curve: Uint8Array; windows: { start: number; end: number }[] } {
  const n = Math.max(1, Math.ceil(duration * rate))
  const out = new Uint8Array(n)
  const sorted = [...dropTimes].sort((a, b) => a - b)
  const windows: { start: number; end: number }[] = []

  for (let idx = 0; idx < sorted.length; idx++) {
    const drop = sorted[idx]
    const prevDrop = idx > 0 ? sorted[idx - 1] : -Infinity
    const windowSec = bars * barSecondsAt(tempoMap, drop)
    const rampStart = Math.max(drop - windowSec, prevDrop, 0)
    if (drop <= rampStart) continue
    windows.push({ start: rampStart, end: drop })

    const iStart = Math.max(0, Math.floor(rampStart * rate))
    const iEnd = Math.min(n - 1, Math.ceil(drop * rate))
    for (let i = iStart; i <= iEnd; i++) {
      const t = i / rate
      const linear = clamp01((t - rampStart) / (drop - rampStart))
      out[i] = Math.round(linear * linear * 255)
    }
  }

  return { curve: out, windows }
}

// Tier A: the causal/realtime detectors (BuildDetector/DropDetector/
// BreakDetector) reused verbatim, run offline over the full mix. This is a
// safety net for arrangements with no markers and no stem-level agreement —
// not the primary path (that's the per-stem detection above), since it
// inherits every causal limitation (false-negative-prone on quiet
// instruments, integrator lag) those algorithms have live. Beat phase/tempo
// come from the known tempo map rather than the realtime PLL beat tracker —
// offline, there's no reason to estimate what's already exact.
function detectStructureFromMix(
  wav: DecodedWav,
  tempoMap: TempoMarker[],
): { dropEvents: StructuralEvent[]; breakEvents: StructuralEvent[]; buildCurve: Float32Array; hopSec: number } {
  const { sampleRate, channels } = wav
  const frameCount = channels[0]?.length ?? 0
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

  const buildDetector = new BuildDetector(hopMs)
  const dropDetector = new DropDetector(hopMs)
  const breakDetector = new BreakDetector(hopMs)

  const totalHops = Math.max(0, Math.floor((frameCount - FFT_SIZE) / HOP_SIZE) + 1)
  const window = new Float32Array(FFT_SIZE)
  const dropEvents: StructuralEvent[] = []
  const breakEvents: StructuralEvent[] = []
  const buildCurve = new Float32Array(totalHops)

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

    const centroidHz = spectralCentroidHz(mags, sampleRate, FFT_SIZE)
    const centroid = Math.min(1, centroidHz / CENTROID_CEILING_HZ)
    const novelty = fluxNormalizer.normalize(flux.update(mags))

    const tNow = start / sampleRate
    const { bpm, beatPhase } = musicalPositionAt(tempoMap, tNow)
    const lowEnergy = (bandsRaw.sub + bandsRaw.low) / 2

    const { tension, event: breakEvent } = breakDetector.update(lowEnergy, novelty, tNow)
    if (breakEvent) breakEvents.push(breakEvent)

    const dropSignal = dropEnergyNormalizer.normalize(dropEnergyEnvelope.update(rawLowEnergy))
    const dropEvent = dropDetector.update(dropSignal, tension, beatPhase, bpm, tNow)
    if (dropEvent) {
      dropEvents.push({ type: 'drop', strength: dropEvent.strength, t: dropEvent.t })
      buildDetector.reset()
    }

    buildCurve[h] = buildDetector.update(centroid, bandsRaw.sub)
  }

  return { dropEvents, breakEvents, buildCurve, hopSec }
}

// Prioritized merge: a project's own named markers are ground truth, so they
// win outright; per-stem detection is the next most trustworthy (it has
// direct evidence, just not a human's intent); the causal mix-wide fallback
// only fills genuine gaps. "Near an already-accepted event" is treated as
// the same event rather than a second one.
function mergeByProximity(prioritizedGroups: StructuralEvent[][], proximitySec: number): StructuralEvent[] {
  const accepted: StructuralEvent[] = []
  for (const group of prioritizedGroups) {
    for (const e of [...group].sort((a, b) => a.t - b.t)) {
      if (accepted.some((a) => a.type === e.type && Math.abs(a.t - e.t) < proximitySec)) continue
      accepted.push(e)
    }
  }
  return accepted.sort((a, b) => a.t - b.t)
}

export interface StructureResult {
  structuralEvents: StructuralEvent[]
  sections: TimelineSection[]
  buildProgress: Uint8Array
  tension: Uint8Array
}

// Orchestrates the three tiers above into the Timeline's structural fields.
// See the module-level comments on each tier for what it contributes and why.
export function detectStructure(
  mix: DecodedWav,
  stemAnalyses: StemAnalysis[],
  tempoMap: TempoMarker[],
  markers: TimelineMarker[],
  duration: number,
  rate: number,
): StructureResult {
  const stemLevelEnvelopes = stemAnalyses.map((a) => a.envelopeLevel)

  const markerSections: TimelineSection[] = []
  const markerDropEvents: StructuralEvent[] = []
  for (const m of markers) {
    const kind = classifyMarker(m.name)
    if (kind === 'other') continue
    if (m.end !== undefined && m.end > m.t) {
      markerSections.push({ start: m.t, end: m.end, kind })
    } else if (kind === 'drop') {
      markerDropEvents.push({ type: 'drop', strength: 1, t: m.t })
    }
  }

  const stemDrops = detectDropsFromStems(stemLevelEnvelopes, rate, duration)
  const breakEvents = detectBreaksFromStems(stemLevelEnvelopes, rate, duration)
  const tierA = detectStructureFromMix(mix, tempoMap)

  const dropEvents = mergeByProximity([markerDropEvents, stemDrops, tierA.dropEvents], 3)
  const mergedBreaks = mergeByProximity([breakEvents, tierA.breakEvents], 2)
  const downbeats = downbeatsFromTempoMap(tempoMap, duration)

  const structuralEvents = [...dropEvents, ...mergedBreaks, ...downbeats].sort((a, b) => a.t - b.t)

  const n = Math.max(1, Math.ceil(duration * rate))
  const hasKnownDrops = dropEvents.length > 0
  const { curve: synthesizedBuild, windows: buildWindows } = synthesizeBuildCurve(
    dropEvents.map((e) => e.t),
    tempoMap,
    duration,
    rate,
  )
  // No known drop anywhere in the file (e.g. a non-EDM arrangement with no
  // drop shape at all): fall back to the causal integrator rather than a
  // permanently flat curve.
  const buildProgress = hasKnownDrops ? synthesizedBuild : downsampleCurve(tierA.buildCurve, tierA.hopSec, rate, n)

  // Already sampled at `rate` (one slot per output sample), so this just
  // needs float->byte scaling, not the hop-rate downsampling above.
  const activity = computeActivityCurve(stemLevelEnvelopes, rate, duration)
  const tension = new Uint8Array(n)
  for (let i = 0; i < n; i++) tension[i] = Math.round(clamp01(1 - activity[i]) * 255)

  const breakSections: TimelineSection[] = []
  for (let i = 0; i + 1 < mergedBreaks.length; i++) {
    if (mergedBreaks[i].type === 'breakStart' && mergedBreaks[i + 1].type === 'breakEnd') {
      breakSections.push({ start: mergedBreaks[i].t, end: mergedBreaks[i + 1].t, kind: 'break' })
    }
  }
  const buildSections: TimelineSection[] = buildWindows.map((w) => ({ start: w.start, end: w.end, kind: 'build' }))

  const sections = [...markerSections, ...breakSections, ...buildSections].sort((a, b) => a.start - b.start)

  return { structuralEvents, sections, buildProgress, tension }
}
