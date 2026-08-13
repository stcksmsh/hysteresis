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
  // Where this event sat in the mix, when meaningful (onsets). `tone` is the
  // dominant band as 0..1 (sub -> air); `pan` is -1..1 (left -> right).
  tone?: number
  pan?: number
}

// One element of the mix that just moved, with where it sits: `tone` is its
// band position (0 = low, 1 = high), `pan` that band's own stereo balance.
export interface SpectralHit {
  tone: number
  pan: number
  strength: number
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
  pan: number // -1 (left) .. 1 (right), whole-mix balance
  // Per-band hits for this hop. Transient like `events` — the render worker
  // accumulates them across hops so none are lost between frames.
  spectralHits: SpectralHit[]
  events: StructuralEvent[]
  // Trigger-locked mono waveform (SCOPE_SIZE samples), for the oscilloscope
  // beam only — the one place the render path reads raw samples rather than
  // analysed state (SINTEZA_VIZ.md §4b). null when no audio is attached.
  scope: Float32Array | null
  // True for the render worker's synthetic fallback frame (no track ever
  // loaded/attached yet — SINTEZA_VIZ.md §8's "nothing playing" idle path)
  // AND for StructureSource.synthesize()'s position-only frames (music IS
  // playing, but there's no live waveform to trace — this is the existing
  // lever that keeps the beam's idle Lissajous animating instead of frozen).
  // Real live worklet/fused frames never set this.
  idle?: boolean
}

export interface DropTrigger {
  active: boolean
  strength: number
  age: number
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

  bands: BandEnergies
  centroid: number
  flatness: number
  energy: number
  pan: number

  paletteMix: number
  hueShift: number

  // Memory field (SINTEZA_VIZ.md §4b): ping-pong retention 0..1 (closer to 1
  // = longer memory), curl-noise advection strength this frame, and the
  // earned-symmetry domain-warp amount (0 = organic, 1 = full kaleidoscope
  // fold applied only to the field's own advection sampling, never the
  // fresh frame — see MemoryFieldPass).
  fieldDecay: number
  flowStrength: number
  symmetry: number

  // Raw waveform for the oscilloscope beam — passed through unshaped, never
  // spring-driven (see StateFrame.scope). null when idle/no audio.
  scope: Float32Array | null
  idle: boolean
}

// Power tiers (SINTEZA_VIZ.md §8): `full` runs Julia + beam + bloom +
// Mandelbulb hero; `cheap` drops bloom weight/DPR/FPS and the hero; `idle-
// only` drops live analysis entirely and only ever shows the idle c-drift.
export type PowerTier = 'full' | 'cheap' | 'idle-only'

export type WorkletToMain =
  | { kind: 'state'; frame: StateFrame }
  | { kind: 'ready' }
  | { kind: 'error'; message: string }

export type MainToRenderWorker =
  | { kind: 'init'; canvas: OffscreenCanvas; dpr: number; reducedMotion: boolean }
  | { kind: 'state'; frame: StateFrame }
  | { kind: 'resize'; cssWidth: number; cssHeight: number; dpr: number }
  | { kind: 'visibility'; hidden: boolean }
  | { kind: 'setReducedMotion'; value: boolean }
  | { kind: 'setAccent'; rgb: [number, number, number] }
  | { kind: 'setTier'; tier: PowerTier }
  | { kind: 'setShowIdleBeam'; value: boolean }
  // Debug-only (?debug=1): manually nudge choreography params without a
  // loaded track, and force a drop for tuning the release feel.
  | { kind: 'debugSetParam'; key: 'buildProgress' | 'tension'; value: number }
  | { kind: 'debugTriggerDrop' }

export type RenderWorkerToMain = { kind: 'error'; message: string } | { kind: 'stats'; fps: number }
