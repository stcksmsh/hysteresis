export interface BandEnergies {
  sub: number
  low: number
  mid: number
  presence: number
  air: number
}

export interface StructuralEvent {
  type: 'onset' | 'drop' | 'breakStart' | 'breakEnd' | 'downbeat'
  strength: number
  t: number
}

export interface StateFrame {
  t: number
  tempo: number
  tempoConfidence: number
  beatPhase: number
  barPhase: number
  buildProgress: number
  tension: number
  energy: number
  bandsRaw: BandEnergies
  centroid: number
  flatness: number
  events: StructuralEvent[]
}

export interface DropTrigger {
  active: boolean
  strength: number
  age: number
}

export interface OnsetPulse {
  strength: number
}

export interface ParamBus {
  beatPhase: number
  barPhase: number
  tempoBpm: number
  tempoConfidence: number

  windup: number
  buildProgress: number
  tension: number
  suspension: number

  dropTrigger: DropTrigger | null
  onsetPulses: OnsetPulse[]

  bands: BandEnergies
  centroid: number
  flatness: number
  energy: number

  paletteMix: number
  hueShift: number
}

export type WorkletToMain =
  | { kind: 'state'; frame: StateFrame }
  | { kind: 'ready' }
  | { kind: 'error'; message: string }

export type MainToRenderWorker =
  | { kind: 'init'; canvas: OffscreenCanvas; dpr: number; reducedMotion: boolean }
  | { kind: 'state'; frame: StateFrame }
  | { kind: 'resize'; cssWidth: number; cssHeight: number; dpr: number }
  | { kind: 'visibility'; hidden: boolean }
  | { kind: 'setScene'; sceneId: string }
  | { kind: 'setReducedMotion'; value: boolean }
  // Phase-4 scene tuning: manually nudge choreography params before the real
  // Choreographer is wired in (Phase 5). Not used once that lands.
  | { kind: 'debugSetParam'; key: 'buildProgress' | 'tension'; value: number }
  | { kind: 'debugTriggerDrop' }

export type RenderWorkerToMain = { kind: 'error'; message: string } | { kind: 'stats'; fps: number }
