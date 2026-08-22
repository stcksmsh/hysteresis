import { SIGNAL_TAGS, type RoutableSignalName, type TargetDecl, type TimescaleTag } from '../../types'
import { SCREEN_TARGETS } from '../../outputs/screen-targets'
import type { Curve } from '../types'

// What the editor's dropdowns are populated from — a static description of
// "what signals/targets/curves exist", independent of any live SignalBus
// instance or running Conductor. The live runtime bridge (task 2) supplies
// the *values*; this supplies the *shape*, so the UI can render a complete,
// correct route form even before a live connection exists.

export interface SignalCatalogEntry {
  name: RoutableSignalName | 'scope' | 'idle'
  tag: TimescaleTag | 'pass-through'
}

// Every routable signal, plus the two pass-through fields (scope/idle) that
// Route.from also legally names (see Patchbay's checkRoute) but that don't
// carry a timescale tag since they're exempt from the curve/range pipeline.
export const SIGNAL_CATALOG: SignalCatalogEntry[] = [
  ...(Object.keys(SIGNAL_TAGS) as RoutableSignalName[]).map((name) => ({
    name,
    tag: SIGNAL_TAGS[name],
  })),
  { name: 'scope', tag: 'pass-through' as const },
  { name: 'idle', tag: 'pass-through' as const },
]

// Only ScreenOutput exists as a real output today (SINTEZA_SIGNAL_BUS.md
// §6.3 — ServoOutput is spec-only), so this is the only target catalog the
// editor has to offer. Exported as a function, not a constant, so a second
// real output later is a one-line addition here rather than a UI rewrite.
export function getTargetCatalog(): TargetDecl[] {
  return SCREEN_TARGETS
}

export const CURVE_OPTIONS: { label: string; value: Curve }[] = [
  { label: 'Linear', value: 'linear' },
  { label: 'Exponential', value: 'exp' },
  { label: 'Logarithmic', value: 'log' },
  { label: 'Smoothstep', value: 'smoothstep' },
  { label: 'Threshold', value: { kind: 'threshold', cut: 0.5 } },
]

export function curveKind(curve: Curve | undefined): string {
  if (!curve) return 'linear'
  return typeof curve === 'string' ? curve : curve.kind
}
