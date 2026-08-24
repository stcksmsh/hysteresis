import { describe, it, expect } from 'vitest'
import { renderDmxUniverses, DMX_UNIVERSE_SIZE } from '../../src/dmx/render-dmx-universe'
import { addFixture, emptyFixtureDocument, setFixtureDmxPatch } from '../../src/render/conductor/patchgraph/fixture-document'
import { fixtureTargetId } from '../../src/render/conductor/patchgraph/fixture-types'

describe('renderDmxUniverses', () => {
  it('ignores fixtures with no dmxPatch set', () => {
    let doc = emptyFixtureDocument()
    doc = addFixture(doc, 'Unpatched', 'dimmer')
    const universes = renderDmxUniverses(doc, {})
    expect(universes.size).toBe(0)
  })

  it('writes a single-channel fixture at its patched start address', () => {
    let doc = emptyFixtureDocument()
    doc = addFixture(doc, 'Dimmer 1', 'dimmer')
    const id = doc.fixtures[0].id
    doc = setFixtureDmxPatch(doc, id, { universe: 1, startAddress: 5 })

    const universes = renderDmxUniverses(doc, { [fixtureTargetId(id, 'brightness')]: 1 })
    const buf = universes.get(1)!
    expect(buf).toBeInstanceOf(Uint8Array)
    expect(buf.length).toBe(DMX_UNIVERSE_SIZE)
    expect(buf[4]).toBe(255) // address 5 -> index 4, value 1 (range [0,1]) -> byte 255
  })

  it('lays out a multi-channel fixture across consecutive addresses', () => {
    let doc = emptyFixtureDocument()
    doc = addFixture(doc, 'RGB 1', 'rgb')
    const id = doc.fixtures[0].id
    doc = setFixtureDmxPatch(doc, id, { universe: 1, startAddress: 1 })

    const universes = renderDmxUniverses(doc, {
      [fixtureTargetId(id, 'r')]: 1,
      [fixtureTargetId(id, 'g')]: 0.5,
      [fixtureTargetId(id, 'b')]: 0,
    })
    const buf = universes.get(1)!
    expect(buf[0]).toBe(255)
    expect(buf[1]).toBe(128) // round(0.5 * 255)
    expect(buf[2]).toBe(0)
  })

  it('scales a non-[0,1]-range channel (a servo angle) onto the full DMX byte range', () => {
    let doc = emptyFixtureDocument()
    doc = addFixture(doc, 'Servo 1', 'servo')
    const id = doc.fixtures[0].id
    doc = setFixtureDmxPatch(doc, id, { universe: 1, startAddress: 1 })

    const universes = renderDmxUniverses(doc, { [fixtureTargetId(id, 'angle')]: 90 }) // mid of [0,180]
    expect(universes.get(1)![0]).toBe(128) // round(0.5 * 255)
  })

  it('falls back to the channel default when no resolved value is present', () => {
    let doc = emptyFixtureDocument()
    doc = addFixture(doc, 'Dimmer 1', 'dimmer')
    const id = doc.fixtures[0].id
    doc = setFixtureDmxPatch(doc, id, { universe: 1, startAddress: 1 })

    const universes = renderDmxUniverses(doc, {})
    expect(universes.get(1)![0]).toBe(0) // dimmer's default is 0
  })

  it('groups multiple fixtures in the same universe into one buffer', () => {
    let doc = emptyFixtureDocument()
    doc = addFixture(doc, 'Dimmer 1', 'dimmer')
    doc = addFixture(doc, 'Dimmer 2', 'dimmer')
    const [a, b] = doc.fixtures
    doc = setFixtureDmxPatch(doc, a.id, { universe: 7, startAddress: 1 })
    doc = setFixtureDmxPatch(doc, b.id, { universe: 7, startAddress: 2 })

    const universes = renderDmxUniverses(doc, {
      [fixtureTargetId(a.id, 'brightness')]: 1,
      [fixtureTargetId(b.id, 'brightness')]: 1,
    })
    expect(universes.size).toBe(1)
    const buf = universes.get(7)!
    expect(buf[0]).toBe(255)
    expect(buf[1]).toBe(255)
  })

  it('drops a channel whose patched address falls outside 1..512 rather than throwing', () => {
    let doc = emptyFixtureDocument()
    doc = addFixture(doc, 'RGB 1', 'rgb')
    const id = doc.fixtures[0].id
    // startAddress 511 + 3 channels (r,g,b) means the 'b' channel lands at address 513 — out of range.
    doc = setFixtureDmxPatch(doc, id, { universe: 1, startAddress: 511 })

    expect(() => renderDmxUniverses(doc, { [fixtureTargetId(id, 'b')]: 1 })).not.toThrow()
  })
})
