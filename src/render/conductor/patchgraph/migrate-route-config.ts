import { SIGNAL_TAGS, type RoutableSignalName, type TargetDecl } from '../types'
import type { PatchbayConfig, Route } from '../patchbay/types'
import type { PatchGraphNode, PatchGraph } from './types'

// Converts a legacy flat Route-based PatchbayConfig (SINTEZA_SIGNAL_BUS.md
// §5.1's original 1-signal-in/1-target-out model) into an equivalent
// PatchGraph, node for node. Written to produce the default screen graph
// (configs/screen-graph.ts) from the pre-unification screen-only.ts exactly
// once — see tests/unit/migrate-route-config.spec.ts for the numeric
// equivalence proof this is trustworthy — and kept general so anyone who
// saved a Route-shaped config before this session has a real starting point
// in the node canvas instead of hand-rebuilding it.
//
// `passThrough` routes (idle/scope) CANNOT become graph nodes at all: a
// PatchGraph `signal` node's `signal` field is typed `RoutableSignalName`
// (`keyof typeof SIGNAL_TAGS`), and SIGNAL_TAGS deliberately excludes both
// (see types.ts's own comment) because a graph node's contract is
// `(inputs: number[]) => number` — idle is a boolean, scope a Float32Array,
// neither a scalar a curve/map/combine chain could operate on. Callers get
// these back separately and must keep resolving them directly from the bus,
// exactly like Patchbay.resolve() always did (see resolve-screen-targets.ts).
export interface MigratedGraph {
  graph: PatchGraph
  passThroughRoutes: Route[]
}

let nextMigratedId = 0
function freshId(prefix: string): string {
  return `${prefix}-${nextMigratedId++}`
}

export function migrateRouteConfigToGraph(config: PatchbayConfig, targets: TargetDecl[]): MigratedGraph {
  const targetsById = new Map(targets.map((t) => [t.id, t]))
  const nodes: PatchGraphNode[] = []
  const passThroughRoutes: Route[] = []
  const perTargetInputs = new Map<string, string[]>()

  for (const route of config.routes) {
    if (route.passThrough) {
      passThroughRoutes.push(route)
      continue
    }
    if (!(route.from in SIGNAL_TAGS)) {
      throw new Error(`migrateRouteConfigToGraph: route "${route.from}" -> "${route.to}" is not a known bus signal`)
    }
    const signal = route.from as RoutableSignalName
    let cur = freshId(`sig-${signal}`)
    nodes.push({ id: cur, kind: 'signal', inputs: [], signal, label: signal })

    if (route.curve && route.curve !== 'linear') {
      const curveId = freshId(`curve-${signal}`)
      if (typeof route.curve === 'object') {
        // {kind:'threshold', cut} was a stateless immediate cut (v>=cut?1:0,
        // no hysteresis/dead-band) — ThresholdNode with hysteresis 0 matches
        // it in steady state; the only difference is one transition-frame
        // edge case around the exact cut value, negligible for a route no
        // current config actually uses.
        nodes.push({ id: curveId, kind: 'threshold', inputs: [cur], cut: route.curve.cut, hysteresis: 0, label: `threshold ${route.curve.cut}` })
      } else {
        nodes.push({ id: curveId, kind: 'curve', inputs: [cur], curve: route.curve, label: route.curve })
      }
      cur = curveId
    }

    if (route.smoothing) {
      const envId = freshId(`envelope-${signal}`)
      nodes.push({
        id: envId,
        kind: 'envelope',
        inputs: [cur],
        attackSec: route.smoothing.attackSec,
        releaseSec: route.smoothing.releaseSec,
        label: 'smoothing',
      })
      cur = envId
    }

    const gain = route.gain ?? 1
    const offset = route.offset ?? 0
    if (gain !== 1 || offset !== 0 || route.invert) {
      const mapId = freshId(`map-${signal}`)
      if (route.invert) {
        const target = targetsById.get(route.to)
        // Patchbay's invert reflects across the TARGET's own range midpoint
        // (target.range[0] + target.range[1] - v), applied after gain/offset
        // — matched here by folding the same reflection into the map's
        // output range rather than the input, since MapNode's affine formula
        // (out = outLo + t*(outHi-outLo), t = v when inRange is [0,1]) is
        // exact for any real v when clamp is false, not just v in [0,1].
        const c = target ? target.range[0] + target.range[1] : 0
        nodes.push({ id: mapId, kind: 'map', inputs: [cur], inRange: [0, 1], outRange: [c - offset, c - offset - gain], clamp: false, label: 'invert' })
      } else {
        nodes.push({ id: mapId, kind: 'map', inputs: [cur], inRange: [0, 1], outRange: [offset, offset + gain], clamp: false, label: 'gain/offset' })
      }
      cur = mapId
    }

    const list = perTargetInputs.get(route.to) ?? []
    list.push(cur)
    perTargetInputs.set(route.to, list)
  }

  for (const [targetId, inputIds] of perTargetInputs) {
    let source = inputIds[0]
    if (inputIds.length > 1) {
      const combineId = freshId(`sum-${targetId}`)
      nodes.push({ id: combineId, kind: 'combine', op: 'add', inputs: inputIds, label: `${targetId} (summed)` })
      source = combineId
    }
    const targetNodeId = freshId(`target-${targetId}`)
    nodes.push({ id: targetNodeId, kind: 'target', inputs: [source], targetId, label: targetId })
  }

  return { graph: { id: `${config.id}-migrated`, nodes }, passThroughRoutes }
}
