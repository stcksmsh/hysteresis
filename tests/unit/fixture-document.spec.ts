import { describe, it, expect } from 'vitest'
import {
  emptyFixtureDocument,
  addFixture,
  renameFixture,
  removeFixture,
  fixtureTargetCatalog,
} from '../../src/render/conductor/patchgraph/fixture-document'
import { fixtureTargetId } from '../../src/render/conductor/patchgraph/fixture-types'

describe('fixture-document', () => {
  it('starts empty', () => {
    expect(emptyFixtureDocument().fixtures).toEqual([])
  })

  it('addFixture assigns a stable id and does not mutate the original', () => {
    const doc = emptyFixtureDocument()
    const next = addFixture(doc, 'Stage Left Servo', 'servo')
    expect(doc.fixtures.length).toBe(0)
    expect(next.fixtures.length).toBe(1)
    expect(next.fixtures[0].name).toBe('Stage Left Servo')
    expect(next.fixtures[0].typeId).toBe('servo')
  })

  it('renameFixture only touches the targeted instance', () => {
    let doc = addFixture(emptyFixtureDocument(), 'A', 'dimmer')
    doc = addFixture(doc, 'B', 'servo')
    const id = doc.fixtures[0].id
    const renamed = renameFixture(doc, id, 'A renamed')
    expect(renamed.fixtures[0].name).toBe('A renamed')
    expect(renamed.fixtures[1].name).toBe('B')
  })

  it('removeFixture drops exactly the targeted instance', () => {
    let doc = addFixture(emptyFixtureDocument(), 'A', 'dimmer')
    doc = addFixture(doc, 'B', 'servo')
    const idToRemove = doc.fixtures[0].id
    const next = removeFixture(doc, idToRemove)
    expect(next.fixtures.length).toBe(1)
    expect(next.fixtures[0].name).toBe('B')
  })

  it('fixtureTargetCatalog produces one target per channel, correctly ided', () => {
    const doc = addFixture(emptyFixtureDocument(), 'Front Wash', 'mover')
    const id = doc.fixtures[0].id
    const targets = fixtureTargetCatalog(doc)
    expect(targets.map((t) => t.id).sort()).toEqual(
      [fixtureTargetId(id, 'pan'), fixtureTargetId(id, 'tilt'), fixtureTargetId(id, 'intensity')].sort(),
    )
  })

  it('an instance referencing an unknown fixture type contributes no targets, not a crash', () => {
    const doc = addFixture(emptyFixtureDocument(), 'Mystery', 'not-a-real-type')
    expect(fixtureTargetCatalog(doc)).toEqual([])
  })

  it('adding/removing fixtures changes the catalog live', () => {
    let doc = emptyFixtureDocument()
    expect(fixtureTargetCatalog(doc).length).toBe(0)
    doc = addFixture(doc, 'Light 1', 'dimmer')
    expect(fixtureTargetCatalog(doc).length).toBe(1)
    doc = removeFixture(doc, doc.fixtures[0].id)
    expect(fixtureTargetCatalog(doc).length).toBe(0)
  })
})
