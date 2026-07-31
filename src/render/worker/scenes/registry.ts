import type { Scene } from './Scene'
import { ReactionDiffusionScene } from './reaction-diffusion/ReactionDiffusionScene'

export const DEFAULT_SCENE_ID = 'reaction-diffusion'

export const sceneRegistry: Record<string, () => Scene> = {
  'reaction-diffusion': () => new ReactionDiffusionScene(),
}
