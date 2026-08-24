// Type-only, so this doesn't create a real runtime import cycle even though
// render/conductor/types.ts imports DropTrigger from this same file below —
// both sides are erased at compile time.
import type { SignalBus, TargetDecl } from '../render/conductor/types'
import type { PatchGraph } from '../render/conductor/patchgraph/types'
import type { FixtureDocument } from '../render/conductor/patchgraph/fixture-document'
import type { DropDetectorDebug } from '../audio/worklet/brain/drop-detector'
import type { FixtureOutConfig } from '../render/conductor/outputs/FixtureOutput'
export type { FixtureOutConfig } from '../render/conductor/outputs/FixtureOutput'

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
  // AGENTS.md §4.2 — drum-onset density & fullness, exposed as real,
  // generally-routable continuous signals (previously only ever computed
  // inside DropDetector's own internals, per-instance, unexposed). Optional
  // because StructureSource's sidecar/position-only path has no live
  // energy/onset stream to derive them from yet (§4.6's known limitation,
  // same category as `pan: 0` there) — Conductor defaults to 0 when absent.
  fullness?: number // 0..1, sustained low-band energy, crest-penalized
  onsetDensity?: number // rhythmic events/sec, scaled — same units DropDetector's onsetJump reads
  // AGENTS.md §4.2/§4.5 step 4 — 12-bin pitch-class energy (see
  // src/audio/worklet/chroma.ts), raw pass-through like `scope` (not a
  // scalar signal — SIGNAL_TAGS excludes it the same way). Optional/null
  // for the same reason as `fullness`/`onsetDensity`: no live spectrum
  // exists on the sidecar/position-only path.
  chroma?: Float32Array | null
  // AGENTS.md §4.3/§4.5 step 5 — sidecar-only (schema-3 `stemPresence`),
  // populated by StructureSource.fuse()/synthesize() when a schema-3
  // sidecar with stem data is loaded; absent/0 otherwise (the same
  // sidecar-only precedent `buildProgress`/`tension` already set for a
  // schema-2-only or no-sidecar track — see AGENTS.md's known-limitations
  // note). No live equivalent exists or is planned (§4.3: "do not attempt
  // live stem separation").
  vocalPresence?: number
  drumsPresence?: number
  bassPresence?: number
  otherPresence?: number
  leadPresence?: number // approximate — see SidecarStemPresence's doc comment
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
  // Debug-only, live-worklet-only: the drop detector's own live qualifying
  // values (see DropDetectorDebug's doc comment) — "dropImpulse reads a flat
  // 0 on real audio" can't be diagnosed from outside the detector at all
  // otherwise. Never set by StructureSource's sidecar/position-only path
  // (there's no live DropDetector instance there to read from).
  dropDebug?: DropDetectorDebug
}

export interface DropTrigger {
  active: boolean
  strength: number
  age: number
}

// ScreenOutput's internal struct (SINTEZA_SIGNAL_BUS.md §2, §6.2) — what it
// hands to `Scene.update()`. No longer the cross-boundary contract: that's
// the Signal Bus (src/render/conductor/types.ts's `SignalBus`), produced by
// the Conductor and routed through the Patchbay into this shape by
// ScreenOutput/ScreenParamAssembler. Kept here since `Scene` (unchanged by
// the refactor) still imports it.
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
  // `startLoop` (optional, default true — every existing caller omits it,
  // so behavior is unchanged): false skips the automatic rAF `start()` call,
  // for a caller that drives frames deterministically via `renderFrame`
  // below instead (tools/render-video/'s offline harness) rather than real
  // wall-clock time.
  | { kind: 'init'; canvas: OffscreenCanvas; dpr: number; reducedMotion: boolean; startLoop?: boolean }
  | { kind: 'state'; frame: StateFrame }
  // Deterministic single-frame render (tools/render-video/'s offline
  // harness): runs the exact same per-frame pipeline `tick()` runs live
  // (renderStep(effectiveFrame, dt) — see render-worker.ts), but with a
  // caller-supplied StateFrame and dt instead of the latest live/fallback
  // frame and a wall-clock delta, then replies with the rendered frame as a
  // transferred ImageBitmap (see `frameRendered` below). Only meaningful
  // after `init` with `startLoop: false` — otherwise the live rAF loop is
  // also drawing to the same canvas concurrently.
  | { kind: 'renderFrame'; frame: StateFrame; dt: number }
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
  // Dev-only, for the patchbay editor tool (tools/patchbay-editor): hot-swaps
  // the worker's live screen PatchGraph (screen's own node-graph engine, same
  // one physical fixtures use — see configs/screen-graph.ts and this
  // session's "unify screen + physical patch graphs" note in AGENTS.md).
  // PatchGraph is plain data, so this is still R4's "rerouting = editing a
  // config, no code path" made interactive, just on the unified engine
  // instead of the old flat Patchbay/Route model. Never sent by the real
  // package/site. The editor only ever sends the subset of a larger authored
  // graph that actually targets `screen.*` (see prune.ts's pruneGraphToTargets)
  // — the worker has no idea a physical-fixture half of the graph exists.
  | { kind: 'debugSetScreenGraph'; graph: PatchGraph }
  // Dev-only: starts/stops posting `signalBus` messages back (see below).
  // Off by default so the real site never pays the postMessage cost of
  // cloning a fresh SignalBus every frame just to have somewhere to send it.
  | { kind: 'debugSetSignalBusStream'; value: boolean }
  // Hot-swaps the active screen scene to a loaded ISF shader (source: null
  // reverts to the default julia scene). Unlike the debugSet*/dev-only
  // messages above, this one IS real public API surface — src/index.ts's
  // VizInstance.loadIsfShader()/clearIsfShader() send it too, not just the
  // patchbay editor tool — but it's opt-in and additive: a host that never
  // calls loadIsfShader() never triggers this, so the default julia scene
  // is unaffected. See ScreenOutput.setIsfScene/resetToDefaultScene and IsfScene.
  | { kind: 'setIsfShader'; source: string | null }
  // Real public API (src/index.ts's VizInstance.setOscOut) as well as
  // usable by the editor tool: starts/stops streaming the signal bus out
  // as OSC over a WebSocket connection (wsUrl: null disconnects). See
  // src/osc/osc-out-bridge.ts and docs/osc.md — a browser has no raw UDP
  // API, so real OSC-over-UDP interop needs a local relay on the other end
  // (scripts/udp-relay.ts), not a bridge daemon this repo doesn't have yet.
  | { kind: 'setOscOut'; wsUrl: string | null }
  // Real public API (src/index.ts's VizInstance.setFixtureDocument/
  // setFixtureGraph/setFixtureOut), also usable by the editor tool — the
  // production-side counterpart to fixture-document.ts/DmxOutPanel's
  // previously editor-only ephemeral evaluation (see FixtureOutput.ts's
  // own doc comment). setFixtureDocument replaces which fixtures/DMX
  // patches exist (and rebuilds the fixture graph's target catalog);
  // setFixtureGraph replaces the routing driving them; setFixtureOut
  // connects/disconnects (config: null) the real Art-Net/sACN/WLED
  // transport. USB (Web Serial) is deliberately not covered by this
  // message — it needs a main-thread user-gesture requestPort() call.
  | { kind: 'setFixtureDocument'; doc: FixtureDocument }
  | { kind: 'setFixtureGraph'; graph: PatchGraph }
  | { kind: 'setFixtureOut'; config: FixtureOutConfig | null }
  // Real public API (src/index.ts's VizInstance.connectMidiIn/setOscIn) as
  // well as usable by the editor tool — live external inputs a midiCc/
  // oscIn patch graph node reads (see patchgraph/types.ts's own doc
  // comments on those node kinds). `midiCc` fires once per real CC message
  // (already 0..1 normalized — src/midi/midi-cc-input.ts's own contract);
  // `oscIn` connects/disconnects (config: null) the WebSocket relay
  // connection an OscInBridge listens on for inbound OSC.
  | { kind: 'midiCc'; key: string; value: number }
  | { kind: 'setOscIn'; wsUrl: string | null }

export type RenderWorkerToMain =
  | { kind: 'error'; message: string }
  | { kind: 'stats'; fps: number }
  // Dev-only: a live SignalBus snapshot, throttled (see render-worker.ts),
  // sent only while debugSetSignalBusStream(true) is active. Feeds the
  // patchbay editor's live signal meters. dropDebug rides along (from
  // whatever StateFrame is currently active) purely for diagnosing
  // "dropImpulse never fires" against real audio — null on the synthetic
  // fallback frame and on any sidecar/position-only frame (no live
  // DropDetector instance to read from in either case). fixtureValues is
  // the worker-resident fixture graph's latest evaluation (empty until a
  // host ever calls setFixtureGraph) — the editor's FixtureVisuals/
  // DmxOutPanel read it here instead of running their own copy of the
  // evaluator (see AGENTS.md's "dogfood the fixture API" session).
  | { kind: 'signalBus'; bus: SignalBus; dropDebug: DropDetectorDebug | null; fixtureValues: Record<string, number> }
  // Reply to `renderFrame` above — the composited frame (an ImageBitmap,
  // transferred, from OffscreenCanvas.transferToImageBitmap()) plus the
  // same bus/dropDebug/fixtureValues shape `signalBus` carries, but for the
  // exact frame just rendered rather than a separately-throttled snapshot —
  // an offline compositor (tools/render-video/) needs data synchronized to
  // the frame it's drawing, not racing a live 20Hz timer.
  | { kind: 'frameRendered'; bitmap: ImageBitmap; bus: SignalBus; dropDebug: DropDetectorDebug | null; fixtureValues: Record<string, number> }
  // Dev-only: acks debugSetScreenGraph — either it was applied, or (most
  // usefully) it failed PatchGraphEvaluator's construction-time validation
  // (§5.3-equivalent: throws on any error-severity issue) and the worker
  // kept running the previous graph instead of crashing.
  | { kind: 'patchbayConfigResult'; ok: true }
  | { kind: 'patchbayConfigResult'; ok: false; message: string }
  // Acks setIsfShader — parse/compile errors (a bad header, an unsupported
  // input type, a GLSL compile failure) come back here instead of crashing
  // the worker; `targets` lists the shader's own declared inputs as patch
  // targets (ISF_TARGET_PREFIX-qualified ids) for a caller (the editor, or
  // a host via loadIsfShader's callback) to do something with.
  | { kind: 'isfShaderResult'; ok: true; targets: TargetDecl[] }
  | { kind: 'isfShaderResult'; ok: false; message: string }
  // Fires on every connect/disconnect/error of the setOscOut WebSocket —
  // not one-shot like isfShaderResult, since a long-lived connection can
  // legitimately change state multiple times over its life.
  | { kind: 'oscOutStatus'; connected: boolean; message?: string }
  // Acks setFixtureGraph, same construction-time-validation-rejection
  // contract as patchbayConfigResult/isfShaderResult above.
  | { kind: 'fixtureGraphResult'; ok: true }
  | { kind: 'fixtureGraphResult'; ok: false; message: string }
  // Fires on every connect/disconnect/error of the setFixtureOut transport
  // — not one-shot, same as oscOutStatus above.
  | { kind: 'fixtureOutStatus'; connected: boolean; message?: string }
  // Fires on every connect/disconnect/error of the setOscIn WebSocket —
  // same persistent, fires-multiple-times contract as oscOutStatus above.
  | { kind: 'oscInStatus'; connected: boolean; message?: string }

// Main thread -> live AudioWorklet (a separate execution context from the
// render worker — AudioEngine.ts owns this channel). Two independent callers
// use the same message: (1) debug-only (?debug=1), forcing detectors off so
// SINTEZA_SIGNAL_BUS.md §4.1's acceptance test can be checked by hand — with
// detectors disabled, the screen must still obviously follow the music via
// the continuous/beat/bar signal groups alone; (2) src/index.ts disables
// them automatically whenever a sidecar is active (§4b(1)) — StructureSource
// .fuse() already overwrites their output from the sidecar timeline, so
// running them live would just be wasted computation for that track.
export type MainToWorklet = { kind: 'debugSetDetectorsEnabled'; value: boolean }
