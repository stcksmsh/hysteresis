// Re-exported from ../types.ts for discoverability under outputs/ (this is
// where a reader looking for "the output interface" would expect to find
// it). The type itself lives with SignalBus/TargetDecl since patchbay
// validation (§5.3) needs it too.
export type { VizOutput, TargetDecl, ResolvedTargets, ResolvedTargetValue } from '../types'
