// Shared between the main-thread UI and the render worker's registry so the
// picker and the actual scenes can't drift apart — and so the UI never has to
// import worker/WebGL code into the main bundle just to list the options.
export interface SceneOption {
  id: string
  label: string
}

export const SCENE_OPTIONS: SceneOption[] = [
  { id: 'reaction-diffusion', label: 'Reaction-diffusion (organic)' },
  { id: 'reaction-diffusion-graphic', label: 'Reaction-diffusion (graphic)' },
  { id: 'reactive-geometry', label: 'Reactive geometry' },
]

export const DEFAULT_SCENE_ID = 'reaction-diffusion'
