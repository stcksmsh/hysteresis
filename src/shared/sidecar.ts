// The precomputed sidecar format (SINTEZA_VIZ.md §6). Produced offline by
// scripts/analyze.ts from a single WAV master; consumed by StructureSource
// to fuse reliable, look-ahead structure (beats/sections/events) onto the
// live per-frame signal. Detail (bands/onsets/energy) is never carried here
// — it is always live (SINTEZA_VIZ.md §5's fusion rule).
export const SIDECAR_SCHEMA_VERSION = 1

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

export interface Sidecar {
  schema: 1
  duration: number
  tempo: number
  beats: number[]
  sections: SidecarSection[]
  events: SidecarEvent[]
  energyEnvelope: number[] // 0..1, sampled at envelopeRate Hz
  envelopeRate: number
}

export function isSidecar(value: unknown): value is Sidecar {
  return (
    typeof value === 'object' &&
    value !== null &&
    (value as Sidecar).schema === SIDECAR_SCHEMA_VERSION &&
    Array.isArray((value as Sidecar).beats)
  )
}
