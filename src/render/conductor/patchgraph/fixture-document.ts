import { getFixtureType, channelToTargetDecl, type FixtureTypeSpec } from './fixture-types'
import type { PatchTargetDecl } from './types'

// A named instance of a fixture type — "Stage Left Servo" is a `servo`.
// This is the user-facing degree of freedom fixture-types.ts's static
// specs don't have: how many fixtures exist and what they're called is
// entirely up to the user, not baked into code (the whole point of this
// tool per the original ask — versatility comes from the user's own
// routes/settings, not from new code being written per rig).
export interface FixtureInstance {
  readonly id: string
  readonly name: string
  readonly typeId: string
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
