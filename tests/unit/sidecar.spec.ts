import { describe, it, expect } from 'vitest'
import { isSidecar, SIDECAR_SCHEMA_VERSION, type Sidecar } from '../../src/shared/sidecar'

function baseSidecar(overrides: Partial<Sidecar> = {}): Sidecar {
  return {
    schema: 2,
    duration: 10,
    tempo: 120,
    beats: [0, 0.5],
    sections: [],
    events: [],
    onsets: [],
    energyEnvelope: [0],
    bandEnvelope: { sub: [0], low: [0], mid: [0], presence: [0], air: [0] },
    centroidEnvelope: [0],
    flatnessEnvelope: [0],
    envelopeRate: 20,
    ...overrides,
  }
}

describe('sidecar schema versioning (AGENTS.md §4.3/§4.5 step 5)', () => {
  it('SIDECAR_SCHEMA_VERSION is 3 — what analyze.ts now writes for any newly-generated sidecar', () => {
    expect(SIDECAR_SCHEMA_VERSION).toBe(3)
  })

  it('isSidecar still accepts an already-published schema-2 sidecar (never break the live production path)', () => {
    expect(isSidecar(baseSidecar({ schema: 2 }))).toBe(true)
  })

  it('isSidecar accepts a schema-3 sidecar with no stemPresence (the --stems flag was not used)', () => {
    expect(isSidecar(baseSidecar({ schema: 3 }))).toBe(true)
  })

  it('isSidecar accepts a schema-3 sidecar with stemPresence', () => {
    const sidecar = baseSidecar({
      schema: 3,
      stemPresence: { vocals: [0.1], drums: [0.2], bass: [0.3], other: [0.4], leadPresence: [0.5] },
    })
    expect(isSidecar(sidecar)).toBe(true)
    expect(sidecar.stemPresence?.vocals).toEqual([0.1])
  })

  it('rejects a schema it does not recognize', () => {
    expect(isSidecar(baseSidecar({ schema: 99 as unknown as 2 }))).toBe(false)
  })

  it('rejects a non-sidecar value', () => {
    expect(isSidecar(null)).toBe(false)
    expect(isSidecar({})).toBe(false)
    expect(isSidecar({ schema: 3 })).toBe(false) // missing beats/onsets/bandEnvelope
  })

  it('a section label is optional and round-trips when present', () => {
    const sidecar = baseSidecar({ sections: [{ start: 0, end: 4, kind: 'build', label: 'build' }] })
    expect(sidecar.sections[0].label).toBe('build')
  })
})
