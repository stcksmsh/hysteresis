import { DtSmoother } from '../dt-smoother'
import { SIGNAL_TAGS, type ResolvedTargets, type SignalBus, type TargetDecl } from '../types'
import { applyCurve } from './curves'
import type { PatchbayConfig, Route } from './types'

// Sits between the bus and outputs: pure evaluation of a declarative config,
// no domain logic (SINTEZA_SIGNAL_BUS.md §5). Validates at construction
// (§5.3) so an output that can't safely follow a signal (e.g. a servo fed a
// transient) is rejected with a clear error at load time, not discovered by
// buzzing hardware later.
export class Patchbay {
  private smoothers = new Map<string, DtSmoother>()

  constructor(
    private config: PatchbayConfig,
    outputsTargets: TargetDecl[][],
  ) {
    Patchbay.validate(config, outputsTargets.flat())
  }

  // Throws with the first problem found — the right behavior for
  // construction-time validation (§5.3), where "no unsafe config ever
  // runs" matters more than seeing every problem at once.
  static validate(config: PatchbayConfig, targets: TargetDecl[]): void {
    for (const route of config.routes) {
      const message = Patchbay.checkRoute(config.id, route, targets)
      if (message) throw new Error(message)
    }
  }

  // Same rules as validate(), but collects every problem instead of
  // throwing on the first — what an editor needs to show every bad row at
  // once rather than crash on the first one. Shares checkRoute() so the
  // two never drift apart.
  static collectIssues(
    config: PatchbayConfig,
    targets: TargetDecl[],
  ): { routeIndex: number; route: Route; message: string }[] {
    const issues: { routeIndex: number; route: Route; message: string }[] = []
    config.routes.forEach((route, routeIndex) => {
      const message = Patchbay.checkRoute(config.id, route, targets)
      if (message) issues.push({ routeIndex, route, message })
    })
    return issues
  }

  // The one place these rules are written down — validate() and
  // collectIssues() both call this so "what makes a route valid" only
  // exists in one form.
  private static checkRoute(configId: string, route: Route, targets: TargetDecl[]): string | null {
    const target = targets.find((t) => t.id === route.to)
    if (!target) {
      return `patchbay "${configId}": route "${route.from}" -> "${route.to}" targets an unknown target`
    }
    if (target.passThrough || route.passThrough) {
      if (!target.passThrough || !route.passThrough) {
        return `patchbay "${configId}": route "${route.from}" -> "${route.to}" passThrough mismatch (both the route and the target must agree)`
      }
      if (route.from !== 'scope' && route.from !== 'idle') {
        return `patchbay "${configId}": route "${route.from}" -> "${route.to}" is not a valid pass-through bus field ("scope" or "idle")`
      }
      return null
    }
    // route.from is deliberately typed as a plain string (Route.ts), not
    // keyof SignalBus, since it also has to admit "scope"/"idle" above —
    // so a typo here isn't a compile error. Catching it at construction
    // time (rather than resolve()'s cast to number every frame) turns a
    // silent NaN-through-the-pipeline bug into a clear, immediate error.
    if (!(route.from in SIGNAL_TAGS)) {
      return `patchbay "${configId}": route "${route.from}" -> "${route.to}" is not a known bus signal`
    }
    const tag = SIGNAL_TAGS[route.from as keyof typeof SIGNAL_TAGS]
    if (tag && !target.acceptsTags.includes(tag)) {
      return (
        `patchbay "${configId}": route "${route.from}" (${tag}) -> "${route.to}" rejected — ` +
        `target only accepts [${target.acceptsTags.join(', ')}]`
      )
    }
    return null
  }

  // Resolves this config's routes against `bus` for one output's declared
  // targets. Multiple routes to the same target sum, then clamp to the
  // target's range (§5.1's documented default combine mode) — targets with
  // no route hold their `defaultValue`.
  resolve(bus: SignalBus, dt: number, outputTargets: TargetDecl[]): ResolvedTargets {
    const resolved: ResolvedTargets = {}
    for (const target of outputTargets) {
      resolved[target.id] = target.passThrough ? null : target.defaultValue
    }

    const sums = new Map<string, number>()
    const busRecord = bus as unknown as Record<string, unknown>

    for (const route of this.config.routes) {
      const target = outputTargets.find((t) => t.id === route.to)
      if (!target) continue // route belongs to a different output

      if (target.passThrough || route.passThrough) {
        resolved[route.to] = busRecord[route.from] as ResolvedTargets[string]
        continue
      }

      let v = busRecord[route.from] as number
      v = applyCurve(route.curve, v)
      if (route.smoothing) v = this.smootherFor(route).update(v, dt)
      v = v * (route.gain ?? 1) + (route.offset ?? 0)
      if (route.invert) v = target.range[0] + target.range[1] - v

      sums.set(route.to, (sums.get(route.to) ?? 0) + v)
    }

    for (const [to, v] of sums) {
      const target = outputTargets.find((t) => t.id === to)!
      resolved[to] = Math.min(target.range[1], Math.max(target.range[0], v))
    }

    return resolved
  }

  private smootherFor(route: Route): DtSmoother {
    const key = `${route.from}->${route.to}`
    let s = this.smoothers.get(key)
    if (!s) {
      s = new DtSmoother(route.smoothing!.attackSec, route.smoothing!.releaseSec)
      this.smoothers.set(key, s)
    }
    return s
  }
}
