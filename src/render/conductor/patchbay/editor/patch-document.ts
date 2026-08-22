import type { PatchbayConfig, Route } from '../types'

// The editor's in-memory model of a patchbay config. Deliberately NOT the
// same type as PatchbayConfig: a document's routes carry a stable `id` the
// UI can key React lists / drag interactions on, which PatchbayConfig has
// no business knowing about (Patchbay.resolve() doesn't need it, and a
// hand-authored config file shouldn't have to invent one).
//
// This file is the one seam the whole editor is built around: every edit
// is a pure function (document in, document out), with zero knowledge of
// how it's displayed. The table UI calls these same functions a future
// node-graph view would call — dragging a cable between two nodes and
// dropping a row into a `<select>` both bottom out in `updateRoute()`.
// Neither view is allowed to mutate a document directly or reach into
// Patchbay/Conductor itself; that keeps the door to a second (graph) view
// open for free instead of requiring a rewrite.
export interface PatchRoute extends Route {
  readonly id: string
}

export interface PatchDocument {
  readonly id: string
  readonly routes: readonly PatchRoute[]
}

let nextId = 1
// Monotonic, not random (crypto.randomUUID etc.) — the editor's undo/redo
// and React keys only need uniqueness *within one session*, and a short
// counter-based id is far more readable in devtools / console logs while
// debugging the editor itself than a UUID would be.
function makeRouteId(): string {
  return `r${nextId++}`
}

export function fromConfig(config: PatchbayConfig): PatchDocument {
  return {
    id: config.id,
    routes: config.routes.map((route) => ({ ...route, id: makeRouteId() })),
  }
}

// Strips editor-only fields back out — this is what actually gets handed
// to `new Patchbay(...)` for live preview, and what gets serialized on save.
export function toConfig(doc: PatchDocument): PatchbayConfig {
  return {
    id: doc.id,
    routes: doc.routes.map(({ id: _id, ...route }) => route),
  }
}

export function renameDocument(doc: PatchDocument, id: string): PatchDocument {
  return { ...doc, id }
}

export function addRoute(doc: PatchDocument, route: Route): PatchDocument {
  return { ...doc, routes: [...doc.routes, { ...route, id: makeRouteId() }] }
}

export function updateRoute(doc: PatchDocument, routeId: string, patch: Partial<Route>): PatchDocument {
  return {
    ...doc,
    routes: doc.routes.map((r) => (r.id === routeId ? { ...r, ...patch } : r)),
  }
}

export function removeRoute(doc: PatchDocument, routeId: string): PatchDocument {
  return { ...doc, routes: doc.routes.filter((r) => r.id !== routeId) }
}

// Moves the route at `fromIndex` to sit at `toIndex` (post-removal
// position — same semantics as Array.prototype.splice's target index).
// Reordering never changes resolve()'s output today (multi-route combine
// is sum-then-clamp, order-independent — see Patchbay.resolve()), but it's
// still real editor-visible state: it's how a route list stays readable,
// and it's the natural undo-able operation a future graph view's "which
// cable was dragged where" needs a home for too.
export function reorderRoutes(doc: PatchDocument, fromIndex: number, toIndex: number): PatchDocument {
  const routes = doc.routes.slice()
  const [moved] = routes.splice(fromIndex, 1)
  if (!moved) return doc
  routes.splice(toIndex, 0, moved)
  return { ...doc, routes }
}
