import type { Scene } from './Scene'
import { JuliaScene } from './julia/JuliaScene'
import { MandelbulbScene } from './mandelbulb/MandelbulbScene'

// One fixed visual identity (SINTEZA_VIZ.md §4) — no scene picker in the
// package API (§1). `julia` is the only scene render-worker.ts ever
// switches to by default; `mandelbulb-hero` is registered for a future
// host-driven landing view (§4c) but nothing in this repo activates it yet.
export const DEFAULT_SCENE_ID = 'julia'

export const sceneRegistry: Record<string, () => Scene> = {
  julia: () => new JuliaScene(),
  'mandelbulb-hero': () => new MandelbulbScene(),
}
