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
//
// Schema 3 (AGENTS.md §4.3/§4.5 step 5) adds `stemPresence` — offline Demucs
// source-separation envelopes, `scripts/analyze.ts --stems` only — and
// `SidecarSection.label` (§4.5 step 6's heuristic labeler). Deliberately
// NOT a breaking bump the way earlier sidecar-format notes describe: both
// new fields are optional and every existing schema-2 field/shape is
// unchanged, so a schema-2 sidecar already published to a live site (this
// package's actual production constraint — see AGENTS.md §5's "never break
// the live production path") keeps validating and working exactly as
// before. `isSidecar` accepts either version; `SIDECAR_SCHEMA_VERSION` is
// simply what `analyze.ts` writes for any newly-generated sidecar now.
export const SIDECAR_SCHEMA_VERSION = 3
export type SidecarSchemaVersion = 2 | 3

export type SidecarSectionKind = 'build' | 'drop' | 'break' | 'other'

export interface SidecarSection {
  start: number
  end: number
  kind: SidecarSectionKind
  // AGENTS.md §4.5 step 6 — heuristic human-readable label (intro/build/
  // drop/breakdown/outro/other), computed deterministically from
  // sections/events/stemPresence, not ML. Absent for a schema-2 sidecar or
  // any section the heuristic doesn't confidently classify.
  label?: string
}

export interface SidecarEvent {
  type: 'drop' | 'breakStart' | 'breakEnd' | 'downbeat'
  t: number
  strength: number
}

// A single-band-resolution onset, matching live SpectralHits' shape so
// position-only mode (StructureSource.synthesize()) can populate
// StateFrame.spectralHits from the sidecar the same way live analysis does.
// `pan` has no real stereo source — scripts/structure.ts downmixes to mono
// before analysis — so it's a deterministic pseudo-position from `t`, a
// visual placement aid only, not a measurement.
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

// AGENTS.md §4.3 — per-stem presence/prominence envelopes from offline
// Demucs separation, same envelopeRate/timing as the rest of the sidecar's
// envelopes so `sampleEnvelope()` needs no special-casing. "Presence", not
// "what note" — a stem's normalized loudness over time, which is what
// "track the vocal" actually needs visually (is it present, how prominent,
// right now). `leadPresence` (§4.5 step 7) is the one approximate
// refinement: a per-hop sustained-spectral-peak tracker on the `other`
// stem, not a real "isolated lead instrument" signal.
export interface SidecarStemPresence {
  vocals: number[]
  drums: number[]
  bass: number[]
  other: number[]
  leadPresence: number[] // approximate — see doc comment above
}

export interface Sidecar {
  schema: SidecarSchemaVersion
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
  // schema-3, optional — see the header comment above `SIDECAR_SCHEMA_VERSION`.
  stemPresence?: SidecarStemPresence
}

export function isSidecar(value: unknown): value is Sidecar {
  return (
    typeof value === 'object' &&
    value !== null &&
    ((value as Sidecar).schema === 2 || (value as Sidecar).schema === 3) &&
    Array.isArray((value as Sidecar).beats) &&
    Array.isArray((value as Sidecar).onsets) &&
    (value as Sidecar).bandEnvelope != null
  )
}
