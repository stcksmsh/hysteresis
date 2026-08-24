import { getFixtureType, channelToTargetDecl, type FixtureTypeSpec } from './fixture-types'
import type { PatchTargetDecl } from './types'

// A named instance of a fixture type — "Stage Left Servo" is a `servo`.
// This is the user-facing degree of freedom fixture-types.ts's static
// specs don't have: how many fixtures exist and what they're called is
// entirely up to the user, not baked into code (the whole point of this
// tool per the original ask — versatility comes from the user's own
// routes/settings, not from new code being written per rig).
// Real DMX addressing for an instance — universe (1..63999, sACN's range;
// Art-Net's Port-Address is narrower at 0..32767 but this field doesn't
// enforce that, since which protocol is actually in use is a choice made
// at send time, not patch time) plus the DMX512 start address (1..512) its
// first channel occupies. Optional: a fixture only needs this once you
// actually want to send it out over Art-Net/sACN (docs/dmx-out.md) — the
// simulated patchbay-editor visuals never needed real DMX addresses at all,
// so this stays unset by default and doesn't disturb that existing usage.
export interface DmxPatch {
  readonly universe: number
  readonly startAddress: number
}

export interface FixtureInstance {
  readonly id: string
  readonly name: string
  readonly typeId: string
  readonly dmxPatch?: DmxPatch
}

export interface FixtureDocument {
  readonly fixtures: readonly FixtureInstance[]
}

let nextId = 1
function makeFixtureId(): string {
  return `fx${nextId++}`
}

export function emptyFixtureDocument(): FixtureDocument {
  return { fixtures: [] }
}

export function addFixture(doc: FixtureDocument, name: string, typeId: string): FixtureDocument {
  return { fixtures: [...doc.fixtures, { id: makeFixtureId(), name, typeId }] }
}

export function renameFixture(doc: FixtureDocument, fixtureId: string, name: string): FixtureDocument {
  return { fixtures: doc.fixtures.map((f) => (f.id === fixtureId ? { ...f, name } : f)) }
}

export function removeFixture(doc: FixtureDocument, fixtureId: string): FixtureDocument {
  return { fixtures: doc.fixtures.filter((f) => f.id !== fixtureId) }
}

// `patch: null` clears it (a fixture that no longer needs a real DMX
// address, e.g. going back to simulation-only) — kept as a separate case
// from a real patch rather than overloading `undefined`, since a mutator's
// argument being merely omitted vs. explicitly "please clear this" reads
// very differently at the call site (setFixtureDmxPatch(doc, id, null) is
// unambiguous; a caller can't accidentally clear a patch by forgetting an
// optional argument).
export function setFixtureDmxPatch(doc: FixtureDocument, fixtureId: string, patch: DmxPatch | null): FixtureDocument {
  return { fixtures: doc.fixtures.map((f) => (f.id === fixtureId ? { ...f, dmxPatch: patch ?? undefined } : f)) }
}

// The whole point of fixture instances existing: every channel of every
// instance becomes a real target the patch graph can route into — this is
// what the graph editor's "to" dropdown and the validator's target catalog
// are built from, and it changes live the moment a fixture is added/removed
// (no code change, no restart).
export function fixtureTargetCatalog(doc: FixtureDocument): PatchTargetDecl[] {
  const targets: PatchTargetDecl[] = []
  for (const fixture of doc.fixtures) {
    const type = getFixtureType(fixture.typeId)
    if (!type) continue // an instance referencing a removed/unknown type just contributes nothing, rather than crashing the catalog
    for (const channel of type.channels) {
      targets.push(channelToTargetDecl(fixture.id, fixture.name, channel))
    }
  }
  return targets
}

export function fixtureTypeLabel(typeId: string): string {
  const type: FixtureTypeSpec | undefined = getFixtureType(typeId)
  return type?.label ?? typeId
}
