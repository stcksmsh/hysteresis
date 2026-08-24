import type { ExternalInputs, PatchGraphEvaluator } from '../patchgraph/PatchGraphEvaluator'
import type { ResolvedTargets, SignalBus, TargetDecl } from '../types'

// Bridges PatchGraphEvaluator's plain `{ [targetId]: number }` (only ever
// contains a target an actual route reaches — see its own doc comment) into
// the full ResolvedTargets contract ScreenParamAssembler depends on
// (SINTEZA_SIGNAL_BUS.md §5.1: an unrouted target holds its own
// `defaultValue`, not silently 0) plus the two passThrough targets
// (`screen.idle`/`screen.scope`), which can never be graph nodes at all —
// their values aren't scalars (see migrate-route-config.ts's header
// comment for why). This function is what used to be Patchbay.resolve()'s
// job for the screen; it's the one place that guarantee still lives now
// that ScreenOutput is driven by a PatchGraph instead.
export function resolveScreenTargets(evaluator: PatchGraphEvaluator, targets: TargetDecl[], bus: SignalBus, dt: number, external?: ExternalInputs): ResolvedTargets {
  const resolved: ResolvedTargets = {}
  for (const target of targets) {
    resolved[target.id] = target.passThrough ? null : target.defaultValue
  }

  const evaluated = evaluator.evaluate(bus, dt, external)
  for (const target of targets) {
    if (target.passThrough) continue
    if (target.id in evaluated) resolved[target.id] = evaluated[target.id]
  }

  // Hardcoded rather than driven by a passThroughRoutes list: this function
  // is screen-specific by name already (screen-targets.ts itself hardcodes
  // these same two ids), and there are exactly two, unlikely to ever grow —
  // not worth a generic mapping for.
  resolved['screen.idle'] = bus.idle
  resolved['screen.scope'] = bus.scope

  return resolved
}
