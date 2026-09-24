// Schema-4 additive fields (SINTEZA_OFFLINE_SSM.md §2, directional spec —
// not verified-current, but its shape is what this workstream implements and
// matches crates/hyst-core/src/sidecar.rs's schema-4 fields field-for-field
// (same camelCase JSON keys), since both will eventually read the same JSON.
//
// The frozen src/shared/sidecar.ts stays untouched (schema 2/3 only,
// SIDECAR_SCHEMA_VERSION = 3) — this is a NEW type defined here that extends
// it additively, per AGENTS.md §3 rule 2's correction.
import type { Sidecar, SidecarSection } from '../src/shared/sidecar'

export interface SidecarRepeat {
  aStart: number
  aEnd: number
  bStart: number
  bEnd: number
  similarity: number // 0..1
}

export interface Schema4Section extends SidecarSection {
  boundaryConfidence?: number // 0..1, the novelty peak's own magnitude at this boundary
}

export interface Schema4Sidecar extends Omit<Sidecar, 'schema' | 'sections'> {
  schema: 4
  sections: Schema4Section[]
  repeats?: SidecarRepeat[]
  noveltyLocalEnvelope?: number[]
  noveltySectionEnvelope?: number[]
}
