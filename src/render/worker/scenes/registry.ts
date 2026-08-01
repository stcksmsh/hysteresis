import type { Scene } from './Scene'
import { ReactionDiffusionScene } from './reaction-diffusion/ReactionDiffusionScene'
import { ReactiveGeometryScene } from './reactive-geometry/ReactiveGeometryScene'

export { DEFAULT_SCENE_ID } from '../../../shared/scenes'

// Ids must match SCENE_OPTIONS in src/shared/scenes.ts, which is what the
// picker UI is built from.
export const sceneRegistry: Record<string, () => Scene> = {
  'reaction-diffusion': () => new ReactionDiffusionScene('organic'),
  'reaction-diffusion-graphic': () => new ReactionDiffusionScene('graphic'),
  'reactive-geometry': () => new ReactiveGeometryScene(),
}
