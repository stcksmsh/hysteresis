import { screenOnlyConfig } from '../../patchbay/configs/screen-only'
import { SCREEN_TARGETS } from '../../outputs/screen-targets'
import { migrateRouteConfigToGraph } from '../migrate-route-config'
import type { PatchGraph } from '../types'
import type { Route } from '../../patchbay/types'

// The default screen graph — the unified-engine replacement for
// screen-only.ts's Route-based config (SINTEZA_SIGNAL_BUS.md's original
// §5.1 model), now that ScreenOutput consumes a PatchGraph like every other
// output. Derived from screen-only.ts via migrateRouteConfigToGraph rather
// than hand-transcribed, specifically so there's exactly one source of
// truth for "what the default screen wiring is" and no risk of the two
// drifting apart or a hand-copy transcription error — see
// tests/unit/migrate-route-config.spec.ts for the numeric proof this
// reproduces screen-only.ts's actual behavior. screen-only.ts itself is
// kept only as that source (and as Patchbay's own still-used, still-tested
// legacy implementation) — nothing in the live render path reads it anymore.
const migrated = migrateRouteConfigToGraph(screenOnlyConfig, SCREEN_TARGETS)

export const screenGraph: PatchGraph = migrated.graph

// idle/scope — can't be graph nodes at all (see migrate-route-config.ts's
// header comment); resolve-screen-targets.ts copies them straight from the
// bus using this list, exactly like Patchbay always did.
export const screenPassThroughRoutes: Route[] = migrated.passThroughRoutes
