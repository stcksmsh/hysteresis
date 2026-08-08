// The precomputed sidecar format (SINTEZA_VIZ.md §6). Produced offline by
// scripts/analyze.ts from a single WAV master; consumed by StructureSource
// to fuse reliable, look-ahead structure (beats/sections/events) onto the
// live per-frame signal when live audio is available (self-hosted tracks).
//
// Schema 2 adds per-band/centroid/flatness envelopes and an onsets list —
// detail that used to be "always live" (SINTEZA_VIZ.md §5) now also has an
// offline source, because not every host has live audio to tap: a
// SoundCloud/Bandcamp-embedded track is cross-origin, so there is no
// AnalyserNode to attach to at all. For those, StructureSource.synthesize()
// derives a full StateFrame from the sidecar alone, position-driven only
// (see README's "SoundCloud / position-only mode"). Self-hosted tracks with
// a real AnalyserNode still get live detail — the sidecar there only
// contributes structure, same as schema 1 always did.
export const SIDECAR_SCHEMA_VERSION = 2

export type SidecarSectionKind = 'build' | 'drop' | 'break' | 'other'

export interface SidecarSection {
  start: number
  end: number
  kind: SidecarSectionKind
}

export interface SidecarEvent {
  type: 'drop' | 'breakStart' | 'breakEnd' | 'downbeat'
  t: number
  strength: number
}

// A single-band-resolution onset, for driving the beam/onset-particles in
// position-only mode the same way live SpectralHits do. `pan` has no real
// stereo source — scripts/structure.ts downmixes to mono before analysis —
// so it's a deterministic pseudo-position from `t`, a visual placement aid
// only, not a measurement.
export interface SidecarOnset {
  t: number
  strength: number
  tone: number // 0 = sub, 1 = air — dominant band at this onset
  pan: number // -1..1, synthetic (see above)
}

// Per-band energy, sampled at envelopeRate Hz alongside energyEnvelope —
// struct-of-arrays rather than an array of BandEnergies objects, so the
// JSON doesn't repeat five keys per sample.
export interface SidecarBandEnvelope {
  sub: number[]
  low: number[]
  mid: number[]
  presence: number[]
  air: number[]
}

export interface Sidecar {
  schema: 2
  duration: number
  tempo: number
  beats: number[]
  sections: SidecarSection[]
  events: SidecarEvent[]
  onsets: SidecarOnset[]
  energyEnvelope: number[] // 0..1, sampled at envelopeRate Hz
  bandEnvelope: SidecarBandEnvelope
  centroidEnvelope: number[]
  flatnessEnvelope: number[]
  envelopeRate: number
}

export function isSidecar(value: unknown): value is Sidecar {
  return (
    typeof value === 'object' &&
    value !== null &&
    (value as Sidecar).schema === SIDECAR_SCHEMA_VERSION &&
    Array.isArray((value as Sidecar).beats) &&
    Array.isArray((value as Sidecar).onsets) &&
    (value as Sidecar).bandEnvelope != null
  )
}
