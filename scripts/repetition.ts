// SINTEZA_OFFLINE_SSM.md build order steps 1-6, orchestrated: beat features
// -> SSM -> (fallback) checkerboard novelty/peaks -> boundary-informed build
// windows -> repetition map -> schema-4 sidecar. allin1 (§0b's preferred
// beat/boundary source) was infeasible to stand up here — see
// scripts/README.md — so this runs entirely over the existing causal beat
// grid from structure.ts's analyzeMixDetailed().
import type { DecodedWav } from './wav'
import { analyzeMixDetailed } from './structure'
import {
  computeBeatFeatures,
  buildSSM,
  checkerboardNovelty,
  pickPeaks,
  backwardWalkToBoundary,
  computeRepetitionMap,
} from './ssm'
import type { SidecarSection } from '../src/shared/sidecar'
import type { Schema4Sidecar, Schema4Section } from './schema4'

const LOCAL_KERNEL_RADIUS_BEATS = 6 // ~2 bars at 4/4 — phrase-scale
const SECTION_KERNEL_RADIUS_BEATS = 24 // ~8 bars at 4/4 — section-scale (start point, tune by ear)
const MIN_PEAK_SPACING_BEATS = 8
const BUILD_WINDOW_BARS = 8 // matches structure.ts's own fallback constant

function resampleToEnvelopeRate(beatValues: number[], beats: number[], envelopeRate: number, length: number): number[] {
  const out = new Array<number>(length).fill(0)
  let idx = 0
  for (let i = 0; i < length; i++) {
    const t = i / envelopeRate
    while (idx + 1 < beats.length && beats[idx + 1] <= t) idx++
    out[i] = beatValues[idx] ?? 0
  }
  return out
}

export function computeSchema4Sidecar(wav: DecodedWav): Schema4Sidecar {
  const { sidecar, bandRaw, centroidRaw, flatnessRaw, hopSec, dropTimes } = analyzeMixDetailed(wav)
  const { beats, duration, tempo } = sidecar

  const beatFeatures = computeBeatFeatures(beats, bandRaw, centroidRaw, flatnessRaw, hopSec)
  const ssm = buildSSM(beatFeatures)
  const noveltyLocal = checkerboardNovelty(ssm, LOCAL_KERNEL_RADIUS_BEATS)
  const noveltySection = checkerboardNovelty(ssm, SECTION_KERNEL_RADIUS_BEATS)
  const boundaryPeaks = pickPeaks(noveltySection, MIN_PEAK_SPACING_BEATS)
  const boundaryTimes = boundaryPeaks.map((i) => beats[i])

  // Boundary-informed build windows (§1.4), fixed-bar fallback retained.
  const barSec = (4 * 60) / Math.max(1, tempo)
  const fallbackWindowSec = BUILD_WINDOW_BARS * barSec
  const sortedDrops = [...dropTimes].sort((a, b) => a - b)
  const refinedBuildSections: SidecarSection[] = []
  for (let i = 0; i < sortedDrops.length; i++) {
    const drop = sortedDrops[i]
    const prevFloor = i > 0 ? sortedDrops[i - 1] : 0
    const start = backwardWalkToBoundary(drop, prevFloor, boundaryTimes, fallbackWindowSec)
    if (drop > start) refinedBuildSections.push({ start, end: drop, kind: 'build' })
  }
  const nonBuildSections: Schema4Section[] = sidecar.sections.filter((s) => s.kind !== 'build')
  const labeledBuildSections: Schema4Section[] = refinedBuildSections.map((s) => {
    let nearestPeakIdx = -1
    let nearestDist = Infinity
    for (let i = 0; i < boundaryPeaks.length; i++) {
      const d = Math.abs(boundaryTimes[i] - s.start)
      if (d < nearestDist) {
        nearestDist = d
        nearestPeakIdx = i
      }
    }
    const boundaryConfidence = nearestPeakIdx >= 0 ? noveltySection[boundaryPeaks[nearestPeakIdx]] : undefined
    return { ...s, label: 'build', boundaryConfidence }
  })
  const mergedSections: Schema4Section[] = [...labeledBuildSections, ...nonBuildSections].sort((a, b) => a.start - b.start)

  const boundaryBeatIndices = [0, ...boundaryPeaks, beats.length]
  const beatTimesWithDuration = [...beats, duration]
  const repeats = computeRepetitionMap({ ssm, beatTimesWithDuration, boundaryBeatIndices })

  const envelopeLength = sidecar.energyEnvelope.length
  const noveltyLocalEnvelope = resampleToEnvelopeRate(noveltyLocal, beats, sidecar.envelopeRate, envelopeLength)
  const noveltySectionEnvelope = resampleToEnvelopeRate(noveltySection, beats, sidecar.envelopeRate, envelopeLength)

  return {
    ...sidecar,
    schema: 4,
    sections: mergedSections,
    repeats,
    noveltyLocalEnvelope,
    noveltySectionEnvelope,
  }
}
