import { describe, it, expect } from 'vitest'
import {
  fromConfig,
  toConfig,
  addRoute,
  updateRoute,
  removeRoute,
  reorderRoutes,
} from '../../src/render/conductor/patchbay/editor/patch-document'
import { Patchbay } from '../../src/render/conductor/patchbay/Patchbay'
import type { PatchbayConfig } from '../../src/render/conductor/patchbay/types'
import { SCREEN_TARGETS } from '../../src/render/conductor/outputs/screen-targets'

function makeConfig(): PatchbayConfig {
  return {
    id: 'test',
    routes: [
      { from: 'energy', to: 'screen.energy', curve: 'linear' },
      { from: 'tension', to: 'screen.tension' },
    ],
  }
}

describe('patch-document', () => {
  it('round-trips through fromConfig/toConfig unchanged (ids stripped)', () => {
    const config = makeConfig()
    const doc = fromConfig(config)
    expect(toConfig(doc)).toEqual(config)
  })

  it('assigns each route a stable, unique id', () => {
    const doc = fromConfig(makeConfig())
    const ids = doc.routes.map((r) => r.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('addRoute appends without mutating the original document', () => {
    const doc = fromConfig(makeConfig())
    const next = addRoute(doc, { from: 'pan', to: 'screen.pan' })
    expect(doc.routes.length).toBe(2)
    expect(next.routes.length).toBe(3)
    expect(next.routes[2].from).toBe('pan')
  })

  it('updateRoute patches only the targeted route', () => {
    const doc = fromConfig(makeConfig())
    const targetId = doc.routes[0].id
    const next = updateRoute(doc, targetId, { gain: 2 })
    expect(next.routes[0].gain).toBe(2)
    expect(next.routes[1]).toEqual(doc.routes[1])
    // original untouched
    expect(doc.routes[0].gain).toBeUndefined()
  })

  it('removeRoute drops exactly the targeted route', () => {
    const doc = fromConfig(makeConfig())
    const targetId = doc.routes[0].id
    const next = removeRoute(doc, targetId)
    expect(next.routes.length).toBe(1)
    expect(next.routes[0].from).toBe('tension')
  })

  it('reorderRoutes moves a route to the requested index', () => {
    const doc = fromConfig(makeConfig())
    const next = reorderRoutes(doc, 0, 1)
    expect(next.routes.map((r) => r.from)).toEqual(['tension', 'energy'])
  })

  it('reorderRoutes is a no-op for an out-of-range source index', () => {
    const doc = fromConfig(makeConfig())
    const next = reorderRoutes(doc, 5, 0)
    expect(next).toBe(doc)
  })

  it('toConfig output is accepted by the real Patchbay constructor', () => {
    const doc = fromConfig(makeConfig())
    const withAdd = addRoute(doc, { from: 'familiarity', to: 'screen.familiarity', curve: 'smoothstep' })
    expect(() => new Patchbay(toConfig(withAdd), [SCREEN_TARGETS])).not.toThrow()
  })

  it('a document with a bad route is caught by collectIssues, not a throw', () => {
    const doc = fromConfig(makeConfig())
    const bad = addRoute(doc, { from: 'not-a-real-signal', to: 'screen.energy' })
    const issues = Patchbay.collectIssues(toConfig(bad), SCREEN_TARGETS)
    expect(issues.length).toBe(1)
    expect(issues[0].message).toMatch(/not a known bus signal/)
  })
})
