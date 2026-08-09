import type { BandEnergies, SpectralHit, StateFrame, StructuralEvent } from '../shared/types'
import type { Sidecar } from '../shared/sidecar'
import { BAND_NAMES } from './worklet/bands'

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v))
}

// Linear interpolation between the two nearest envelopeRate-Hz samples —
// smooths out the 20Hz (typical) sampling instead of stepping visibly.
function sampleEnvelope(envelope: number[], rate: number, t: number): number {
  const n = envelope.length
  if (n === 0) return 0
  const pos = Math.max(0, t * rate)
  const i0 = Math.min(n - 1, Math.floor(pos))
  const i1 = Math.min(n - 1, i0 + 1)
  const frac = pos - i0
  return envelope[i0] + (envelope[i1] - envelope[i0]) * frac
}

// Beat/bar phase at `t` from the sidecar's beat grid — assumes 4/4 (bar
// boundary every 4th beat), same assumption the live BarTracker makes.
function beatPositionAt(beats: number[], t: number): { beatPhase: number; barPhase: number } {
  if (beats.length < 2) return { beatPhase: 0, barPhase: 0 }
  let i = 0
  while (i < beats.length - 2 && beats[i + 1] <= t) i++
  const b0 = beats[i]
  const b1 = beats[i + 1]
  const period = Math.max(1e-3, b1 - b0)
  const beatPhase = clamp01((t - b0) / period)
  const barPhase = ((i % 4) + beatPhase) / 4
  return { beatPhase, barPhase }
}

// Eased ramp across whichever 'build' section contains `t`, 0 outside one —
// synthesized on the fly rather than stored, since the sidecar only carries
// section spans (SINTEZA_VIZ.md §6), not a baked curve.
function buildProgressAt(sidecar: Sidecar, t: number): number {
  for (const s of sidecar.sections) {
    if (s.kind === 'build' && t >= s.start && t <= s.end) {
      const lin = clamp01((t - s.start) / Math.max(1e-3, s.end - s.start))
      return lin * lin
    }
  }
  return 0
}

const BREAK_TENSION_RAMP_SEC = 2

function tensionAt(sidecar: Sidecar, t: number): number {
  for (const s of sidecar.sections) {
    if (s.kind === 'break' && t >= s.start && t <= s.end) {
      return clamp01((t - s.start) / BREAK_TENSION_RAMP_SEC)
    }
  }
  return 0
}

// Fuses precomputed sidecar structure onto live StateFrames (SINTEZA_VIZ.md
// §5's fusion rule): structure — tempo/beatPhase/barPhase/buildProgress/
// tension/drop|break|downbeat events — comes from the sidecar once loaded;
// detail — bands, onsets, energy, the scope buffer — stays live whenever
// live audio exists to produce it. When it doesn't (a cross-origin embed,
// e.g. SoundCloud — no AnalyserNode to attach to at all), synthesize()
// derives a full StateFrame from the sidecar's schema-2 envelopes/onsets
// instead — position-only, no live signal required.
export class StructureSource {
  private sidecar: Sidecar | null = null
  private nextEventIndex = 0
  private nextOnsetIndex = 0
  private lastPosition = 0

  get active(): boolean {
    return this.sidecar !== null
  }

  load(sidecar: Sidecar): void {
    this.sidecar = sidecar
    this.nextEventIndex = 0
    this.nextOnsetIndex = 0
    this.lastPosition = 0
  }

  clear(): void {
    this.sidecar = null
  }

  // Called on every host setPosition/seek so the event scan tracks the live
  // clock instead of replaying history after a jump.
  resyncTo(seconds: number): void {
    this.lastPosition = seconds
    if (!this.sidecar) return
    let idx = this.sidecar.events.findIndex((e) => e.t >= seconds)
    if (idx < 0) idx = this.sidecar.events.length
    this.nextEventIndex = idx

    let onsetIdx = this.sidecar.onsets.findIndex((o) => o.t >= seconds)
    if (onsetIdx < 0) onsetIdx = this.sidecar.onsets.length
    this.nextOnsetIndex = onsetIdx
  }

  fuse(frame: StateFrame, positionSec: number): StateFrame {
    if (!this.sidecar) return frame
    const sidecar = this.sidecar
    const { beatPhase, barPhase } = beatPositionAt(sidecar.beats, positionSec)
    const structuralEvents = this.collectEvents(positionSec)
    const liveDetailEvents = frame.events.filter((e) => e.type === 'onset')
    this.lastPosition = positionSec

    return {
      ...frame,
      tempo: sidecar.tempo,
      tempoConfidence: 1,
      beatPhase,
      barPhase,
      buildProgress: buildProgressAt(sidecar, positionSec),
      tension: tensionAt(sidecar, positionSec),
      events: [...liveDetailEvents, ...structuralEvents],
    }
  }

  // Position-only synthesis (SINTEZA_VIZ.md §5's "SoundCloud / position-only
  // mode"): builds a complete StateFrame from the sidecar alone, for hosts
  // with no live AnalyserNode at all. `idle: true` is deliberate here even
  // though music is genuinely playing — it's the existing lever
  // (JuliaScene's idleClockSec) that keeps the beam animating its idle
  // Lissajous, since there is no real waveform to trace (SCOPE_SIZE samples
  // aren't recoverable from an offline band envelope); every other field
  // carries real sidecar-derived structure and detail.
  synthesize(positionSec: number): StateFrame {
    const sidecar = this.sidecar
    if (!sidecar) throw new Error('StructureSource.synthesize() called with no sidecar loaded')

    const { beatPhase, barPhase } = beatPositionAt(sidecar.beats, positionSec)
    const bandsRaw = {} as BandEnergies
    for (const name of BAND_NAMES) {
      bandsRaw[name] = sampleEnvelope(sidecar.bandEnvelope[name], sidecar.envelopeRate, positionSec)
    }
    const centroid = sampleEnvelope(sidecar.centroidEnvelope, sidecar.envelopeRate, positionSec)
    const flatness = sampleEnvelope(sidecar.flatnessEnvelope, sidecar.envelopeRate, positionSec)
    const energy = sampleEnvelope(sidecar.energyEnvelope, sidecar.envelopeRate, positionSec)
    const spectralHits = this.collectOnsets(positionSec)
    const events = this.collectEvents(positionSec)
    this.lastPosition = positionSec

    return {
      t: positionSec,
      tempo: sidecar.tempo,
      tempoConfidence: 1,
      beatPhase,
      barPhase,
      buildProgress: buildProgressAt(sidecar, positionSec),
      tension: tensionAt(sidecar, positionSec),
      energy,
      bandsRaw,
      centroid,
      flatness,
      pan: 0, // no real stereo source survives the offline mono downmix (scripts/structure.ts)
      spectralHits,
      events,
      scope: null,
      idle: true,
    }
  }

  // Structural events due in the half-open window [lastPosition, t).
  private collectEvents(t: number): StructuralEvent[] {
    if (!this.sidecar) return []
    const events: StructuralEvent[] = []
    while (this.nextEventIndex < this.sidecar.events.length && this.sidecar.events[this.nextEventIndex].t < t) {
      const e = this.sidecar.events[this.nextEventIndex]
      this.nextEventIndex++
      if (e.t < this.lastPosition) continue
      events.push({ type: e.type, strength: e.strength, t: e.t })
    }
    return events
  }

  // Onsets due in the half-open window [lastPosition, t) — mirrors
  // collectEvents but against the separate onsets list/cursor and produces
  // SpectralHit (StateFrame.spectralHits' element type), not StructuralEvent.
  private collectOnsets(t: number): SpectralHit[] {
    if (!this.sidecar) return []
    const hits: SpectralHit[] = []
    while (this.nextOnsetIndex < this.sidecar.onsets.length && this.sidecar.onsets[this.nextOnsetIndex].t < t) {
      const o = this.sidecar.onsets[this.nextOnsetIndex]
      this.nextOnsetIndex++
      if (o.t < this.lastPosition) continue
      hits.push({ tone: o.tone, pan: o.pan, strength: o.strength })
    }
    return hits
  }
}
