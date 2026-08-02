import type { StructuralEvent } from './types'

// The baked timeline format. Produced offline by the compiler from a REAPER
// project plus its stems; consumed by the browser to drive visuals in sync
// with a bounced mix.
//
// The point of baking is that the browser never needs the stems or the DAW:
// per-track separation, exact pan and exact timing are resolved once, offline,
// where there is no realtime budget and no ambiguity. Only this file and the
// mix ship.
//
// v2 adds `sections`/`structuralEvents` and baked `buildProgress`/`tension`
// envelopes — musical structure the compiler now derives offline (see
// tools/compile/structure.ts) instead of leaving entirely to the realtime
// worklet. `sections`/`structuralEvents`/the two new envelope tracks are all
// optional so a v1-shaped file (or one from a stripped-down producer) still
// type-checks; a consumer without them just gets flat 0 for those signals,
// same as before v2 existed.
export const HYST_FORMAT_VERSION = 2

export interface TempoMarker {
  t: number // seconds
  bpm: number
  num: number // time signature numerator
  den: number
}

export interface TimelineMarker {
  t: number
  end?: number // present for regions
  name: string
}

export interface TimelineTrack {
  name: string
  // Exact project pan, -1..1. This is the value the centring problem needed:
  // no inference from L/R energy, which averages to zero in a dense mix.
  pan: number
  // Median measured brightness of this track's stem, 0..1. Gives each track a
  // stable home height derived from what it actually sounds like rather than
  // its position in the project.
  tone: number
  color?: string
}

// A discrete hit. `tone` is measured at the event from the isolated stem, so
// it is accurate in a way a mixed signal never allows.
export interface TimelineEvent {
  t: number
  track: number
  level: number // 0..1
  tone: number // 0..1
  pan: number // -1..1
}

// Coarse per-track envelopes, base64-encoded Uint8 arrays sampled at `rate`
// Hz. Transient events alone would render nothing for sustained material — a
// pad or a held bass has no onsets to speak of — so level and brightness are
// also carried continuously. `buildProgress`/`tension` are the same idea
// applied to musical structure: baked once offline (non-causally — see
// tools/compile/structure.ts) instead of integrated live from a cold start
// every time the file is opened.
export interface TimelineEnvelopes {
  rate: number
  tracks: { level: string; tone: string }[]
  buildProgress?: string
  tension?: string
}

// A labelled span of the arrangement, e.g. a build ramping into a drop, or a
// breakdown. Comes from REAPER regions the project already names (via
// `classifyMarker`) where present; detection fills in the rest.
export interface TimelineSection {
  start: number
  end: number
  kind: SectionKind
}

export interface Timeline {
  version: number
  duration: number
  tempoMap: TempoMarker[]
  markers: TimelineMarker[]
  tracks: TimelineTrack[]
  events: TimelineEvent[]
  envelopes?: TimelineEnvelopes
  sections?: TimelineSection[]
  // drop/breakStart/breakEnd/downbeat — the same shape the realtime worklet
  // emits in StateFrame.events, so a Timeline consumer can replay these
  // directly rather than reinventing a schema. Per-instrument onsets are
  // *not* duplicated here — they're already exact in `events` above.
  structuralEvents?: StructuralEvent[]
}

export function decodeEnvelope(base64: string): Uint8Array {
  const binary = atob(base64)
  const out = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i)
  return out
}

// Musical position at a given time, walking the tempo map. Exact, rather than
// the autocorrelation-plus-PLL estimate the audio path has to make.
export function musicalPositionAt(tempoMap: TempoMarker[], t: number): {
  bpm: number
  beatPhase: number
  barPhase: number
} {
  if (tempoMap.length === 0) return { bpm: 120, beatPhase: 0, barPhase: 0 }

  let active = tempoMap[0]
  let beatsBefore = 0
  for (let i = 0; i < tempoMap.length; i++) {
    const marker = tempoMap[i]
    if (marker.t > t) break
    if (i > 0) {
      const prev = tempoMap[i - 1]
      beatsBefore += ((marker.t - prev.t) * prev.bpm) / 60
    }
    active = marker
  }

  const beats = beatsBefore + ((t - active.t) * active.bpm) / 60
  const beatsPerBar = Math.max(1, active.num)
  return {
    bpm: active.bpm,
    beatPhase: beats - Math.floor(beats),
    barPhase: (beats % beatsPerBar) / beatsPerBar,
  }
}

// Section labels the compiler recognises in marker/region names. A project
// that labels its arrangement gives us structure for free — no inference.
export type SectionKind = 'build' | 'drop' | 'break' | 'other'

export function classifyMarker(name: string): SectionKind {
  const n = name.toLowerCase()
  if (n.includes('drop')) return 'drop'
  if (n.includes('build') || n.includes('riser') || n.includes('rise')) return 'build'
  if (n.includes('break') || n.includes('breakdown')) return 'break'
  return 'other'
}
