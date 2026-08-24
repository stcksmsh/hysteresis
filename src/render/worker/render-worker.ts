/// <reference lib="webworker" />
import type { MainToRenderWorker, PowerTier, RenderWorkerToMain, SpectralHit, StateFrame, StructuralEvent } from '../../shared/types'
import { createGlContext, WebGL2UnavailableError, type GlCapabilities } from './gl/context'
import { Conductor } from '../conductor/Conductor'
import { PatchGraphEvaluator } from '../conductor/patchgraph/PatchGraphEvaluator'
import { screenGraph } from '../conductor/patchgraph/configs/screen-graph'
import { resolveScreenTargets } from '../conductor/outputs/resolve-screen-targets'
import { ScreenOutput } from '../conductor/outputs/ScreenOutput'
import { FixtureOutput } from '../conductor/outputs/FixtureOutput'
import type { VizOutput } from '../conductor/types'
import type { PatchGraph } from '../conductor/patchgraph/types'
import { parseIsf } from '../../isf/parse-isf'
import { isfInputsToTargets } from '../../isf/isf-targets'
import { OscOutBridge } from '../../osc/osc-out-bridge'
import { OscInBridge } from '../../osc/osc-in-bridge'
import type { ExternalInputs } from '../conductor/patchgraph/PatchGraphEvaluator'

declare const self: DedicatedWorkerGlobalScope

// Adaptive quality. Substep scaling reacts continuously (free); resolution
// steps down only after sustained overrun, and only one way, because
// reallocating sim buffers resets the pattern and would thrash visibly.
const FRAME_BUDGET_MS = 22 // ~45fps; above this we start shedding work
const FRAME_COMFORT_MS = 15 // below this we give work back
const FRAME_TIME_SMOOTHING = 0.1
const QUALITY_STEP = 0.04
const RESOLUTION_STEPS = [420, 300, 220]
const RESOLUTION_STEP_AFTER_MS = 3000 // sustained overrun before dropping resolution
const STATS_INTERVAL_MS = 500

let caps: GlCapabilities | null = null
let running = false
let reducedMotion = false
let rafHandle: number | ReturnType<typeof setTimeout> | null = null
let lastLoopTime: number | null = null
let canvasRef: OffscreenCanvas | null = null
let currentDpr = 1

let smoothedFrameMs = 16
let qualityScale = 1
let resolutionStep = 0
let overrunSinceMs: number | null = null
let lastStatsPost = 0

// The output registry R3 requires — a literal array, not a device manager.
// ScreenOutput is the only entry; adding a second output (later, per §8)
// means adding another VizOutput here and nothing else in this file.
const screenOutput = new ScreenOutput()
const outputs: VizOutput[] = [screenOutput]
// let, not const: the patchbay editor tool (dev-only, debugSetScreenGraph
// below) hot-swaps this. Every other caller still only ever sets it once.
let screenGraphEvaluator = new PatchGraphEvaluator(screenGraph, screenOutput.targets)
// The graph screenGraphEvaluator is currently built from — tracked
// separately so setIsfShader can rebuild the evaluator against the
// editor's actual authored graph (not the hardcoded default) when the
// target set changes underneath it (an ISF shader's inputs appearing or
// disappearing from screenOutput.targets).
let currentScreenGraph = screenGraph

// Real fixture output (FixtureOutput.ts's own doc comment) — null evaluator
// until a host ever calls setFixtureGraph, matching oscOutBridge's "entirely
// inert until opted into" posture below. Unlike screenGraphEvaluator there is
// no default graph: an unpatched install has zero fixtures and nothing to
// route, so there's nothing sane to default to.
const fixtureOutput = new FixtureOutput()
let fixtureGraphEvaluator: PatchGraphEvaluator | null = null
let currentFixtureGraph: PatchGraph | null = null

let currentAccent: [number, number, number] = [1, 0.36, 0.22] // vermilion default (#FF5C38), matches JuliaScene's own default

const conductor = new Conductor()

// Real audio hasn't necessarily started yet (loading a file is the user
// gesture that creates the AudioEngine) — this fallback frame keeps the
// scene animating on a plausible default beat grid until the first real
// StateFrame arrives, at which point `latestStateFrame` takes over.
let latestStateFrame: StateFrame | null = null
const fallbackFrame: StateFrame = {
  t: 0,
  tempo: 120,
  tempoConfidence: 0,
  beatPhase: 0,
  barPhase: 0,
  buildProgress: 0,
  tension: 0,
  energy: 0,
  bandsRaw: { sub: 0, low: 0, mid: 0, presence: 0, air: 0 },
  centroid: 0,
  flatness: 0,
  pan: 0,
  spectralHits: [],
  events: [],
  scope: null,
  idle: true,
}

let currentTier: PowerTier = 'full'

// StateFrames arrive at analysis-hop rate (~90Hz), rendering at display
// refresh (~60Hz) — a rate mismatch. Continuous fields use the latest frame
// (overwrite, not queue: queuing would build lag and break the anticipation-
// then-release feel), but discrete events accumulate here and get drained
// once per rendered frame so a transient between two rAF ticks is never lost.
let pendingEvents: StructuralEvent[] = []
let pendingHits: SpectralHit[] = []

// Debug-only overrides (?debug=1 scene-tuning sliders): patched onto
// whichever StateFrame is active each frame, so the full real conductor
// pipeline (springs, drop release, etc.) still runs on top of the manual
// nudge — useful for tuning without a loaded track.
const debugOverrides: Partial<Pick<StateFrame, 'buildProgress' | 'tension'>> = {}
let debugDropPending = false

// Dev-only, patchbay editor tool: streams a live SignalBus snapshot back to
// main, throttled well below render rate (postMessage-cloning a fresh bus
// every render frame would be wasteful for a meter UI that only needs to
// look smooth to a human, not sample-accurate). Entirely inert unless a
// debugSetSignalBusStream(true) message ever arrives.
const SIGNAL_BUS_STREAM_INTERVAL_MS = 50 // 20Hz
let streamSignalBus = false
let lastSignalBusPost = 0

// Real (non-debug) OSC-out feature — see setOscOut's own doc comment above
// and src/osc/osc-out-bridge.ts. Same 20Hz throttle as the signalBus debug
// stream: fast enough to feel live to an external tool, far below
// per-frame postMessage-clone cost.
const OSC_OUT_INTERVAL_MS = 50
let oscOutBridge: OscOutBridge | null = null
let lastOscOutSend = 0

// Real fixture DMX-out — same throttle rationale as OSC above, matching
// DmxOutPanel's own DMX_SEND_INTERVAL_MS (~25Hz, plenty for a reactive
// lighting look). The fixture graph itself is still evaluated every frame
// (cheap, and keeps envelope/threshold node state advancing on real dt) —
// only the actual send over the wire is throttled.
const FIXTURE_OUT_INTERVAL_MS = 40
let lastFixtureOutSend = 0
// Latest fixture-graph evaluation, kept for the dev-only signalBus debug
// stream below (the patchbay editor's own FixtureVisuals/DmxOutPanel need
// SOME way to see what the worker-resident evaluator is producing now that
// they no longer run their own copy — see AGENTS.md's "dogfood the fixture
// API in the patchbay editor" session). Empty until a fixture graph is
// ever set; a host that never calls setFixtureGraph never pays for this.
let lastFixtureResolved: Record<string, number> = {}

// Live external inputs both graphs (screen + fixture) read from — see
// patchgraph/types.ts's MidiCcNode/OscInNode doc comments. `midiCc` is a
// plain map updated in place by the 'midiCc' message case below (a real
// device fires CC messages at its own irregular rate, not once per
// render frame, so there's nothing to throttle — each message just
// updates the map immediately). `oscInBridge` owns its own map
// internally (OscInBridge.values) since it also needs connect/disconnect
// lifecycle, unlike the plain midiCc map which has no connection of its
// own to manage.
const midiCcValues = new Map<string, number>()
let oscInBridge: OscInBridge | null = null
function currentExternalInputs(): ExternalInputs {
  return { midiCc: midiCcValues, oscIn: oscInBridge?.values }
}

const raf: (cb: (t: number) => void) => number | ReturnType<typeof setTimeout> =
  typeof self.requestAnimationFrame === 'function'
    ? (cb) => self.requestAnimationFrame(cb)
    : (cb) => setTimeout(() => cb(performance.now()), 16)

const cancelRaf =
  typeof self.cancelAnimationFrame === 'function'
    ? (h: number) => self.cancelAnimationFrame(h)
    : (h: ReturnType<typeof setTimeout>) => clearTimeout(h)

function post(msg: RenderWorkerToMain) {
  self.postMessage(msg)
}

// Never let an uncaught exception anywhere in a frame kill the rAF chain.
// Before this, any throw inside loop() (Conductor, a Scene, adaptive
// quality, anything) meant the recursive raf(loop) call at the bottom never
// ran — the loop just stops forever, silently, freezing the canvas on
// whatever was last drawn. No error surfaced anywhere. If that last frame
// happened to be mid-flash (JuliaScene's zoom-floor reset blacks the screen
// out for its transition — see PRE_FLASH_LOG_WINDOW), the result is a
// canvas stuck fully black indefinitely with zero indication anything went
// wrong — plausible root cause for "the view went dark and stayed that
// way", reported twice now with no exception visible anywhere. Catching
// here can't fix whatever actually threw, but guarantees a broken frame is
// a logged, visible, recoverable-next-tick event instead of a silent,
// permanent freeze.
function loop(t: number) {
  if (!running || !caps) return
  try {
    tick(t)
  } catch (err) {
    console.error('[sinteza-viz] render loop threw, continuing:', err)
    post({ kind: 'error', message: `render loop threw: ${err instanceof Error ? err.message : String(err)}` })
  }
  rafHandle = raf(loop)
}

function tick(t: number) {
  const dt = lastLoopTime === null ? 0 : Math.min(0.1, (t - lastLoopTime) / 1000)
  lastLoopTime = t

  const base = latestStateFrame ?? fallbackFrame
  if (!latestStateFrame) {
    const beatPeriodSec = 60 / base.tempo
    fallbackFrame.beatPhase = (fallbackFrame.beatPhase + dt / beatPeriodSec) % 1
    fallbackFrame.barPhase = (fallbackFrame.barPhase + dt / (beatPeriodSec * 4)) % 1
  }

  const events = pendingEvents
  pendingEvents = []
  if (debugDropPending) {
    events.push({ type: 'drop', strength: 1, t: base.t })
    debugDropPending = false
  }

  const hits = pendingHits
  pendingHits = []

  const effectiveFrame: StateFrame = {
    ...base,
    buildProgress: debugOverrides.buildProgress ?? base.buildProgress,
    tension: debugOverrides.tension ?? base.tension,
    spectralHits: hits,
    events,
  }

  const bus = conductor.update(effectiveFrame, dt)
  for (const output of outputs) {
    // Only one output exists today (screenOutput) — resolveScreenTargets is
    // screen-specific (idle/scope passthrough by name). Adding a second real
    // output later needs its own PatchGraphEvaluator + a resolver of its
    // own, same as it would have needed its own Patchbay before.
    const resolved = resolveScreenTargets(screenGraphEvaluator, output.targets, bus, dt, currentExternalInputs())
    output.update(dt, resolved)
  }

  if (streamSignalBus && t - lastSignalBusPost > SIGNAL_BUS_STREAM_INTERVAL_MS) {
    lastSignalBusPost = t
    post({ kind: 'signalBus', bus, dropDebug: latestStateFrame?.dropDebug ?? null, fixtureValues: lastFixtureResolved })
  }

  if (oscOutBridge && t - lastOscOutSend > OSC_OUT_INTERVAL_MS) {
    lastOscOutSend = t
    oscOutBridge.send(bus)
  }

  if (fixtureGraphEvaluator) {
    lastFixtureResolved = fixtureGraphEvaluator.evaluate(bus, dt, currentExternalInputs())
    if (t - lastFixtureOutSend > FIXTURE_OUT_INTERVAL_MS) {
      lastFixtureOutSend = t
      fixtureOutput.send(lastFixtureResolved)
    }
  }

  if (dt > 0) updateAdaptiveQuality(dt * 1000, t)
}

function updateAdaptiveQuality(frameMs: number, t: number) {
  smoothedFrameMs += (frameMs - smoothedFrameMs) * FRAME_TIME_SMOOTHING

  if (smoothedFrameMs > FRAME_BUDGET_MS) {
    qualityScale = Math.max(0.15, qualityScale - QUALITY_STEP)
    if (overrunSinceMs === null) overrunSinceMs = t
  } else {
    if (smoothedFrameMs < FRAME_COMFORT_MS) {
      qualityScale = Math.min(1, qualityScale + QUALITY_STEP * 0.5)
    }
    overrunSinceMs = null
  }
  screenOutput.setQuality(qualityScale)

  // Substeps are already floored; if we're still over budget after a
  // sustained stretch, the resolution itself is the problem.
  const stuckAtMinQuality = qualityScale <= 0.2
  const sustained = overrunSinceMs !== null && t - overrunSinceMs > RESOLUTION_STEP_AFTER_MS
  if (stuckAtMinQuality && sustained && resolutionStep < RESOLUTION_STEPS.length - 1) {
    resolutionStep++
    screenOutput.setSimMaxEdge(RESOLUTION_STEPS[resolutionStep])
    qualityScale = 1
    overrunSinceMs = null
  }

  if (t - lastStatsPost > STATS_INTERVAL_MS) {
    lastStatsPost = t
    post({ kind: 'stats', fps: smoothedFrameMs > 0 ? 1000 / smoothedFrameMs : 0 })
  }
}

function start() {
  if (running || !caps) return
  running = true
  lastLoopTime = null
  rafHandle = raf(loop)
}

function stop() {
  running = false
  if (rafHandle !== null) {
    cancelRaf(rafHandle as never)
    rafHandle = null
  }
}

// Power tiers (SINTEZA_VIZ.md §8): `full` caps only against melting a 4K/
// high-DPR display; `cheap`/`idle-only` cap harder since neither needs to
// look crisp — cheap trades resolution for headroom, idle-only is nearly
// static content anyway.
const DPR_CAP: Record<PowerTier, number> = { full: 2, cheap: 1.25, 'idle-only': 1 }

function resize(canvas: OffscreenCanvas, cssWidth: number, cssHeight: number, dpr: number) {
  // Cap DPR and absolute resolution so a 4K/high-DPR display doesn't melt.
  const cappedDpr = Math.min(dpr, DPR_CAP[currentTier])
  const maxEdge = 2560
  let w = Math.round(cssWidth * cappedDpr)
  let h = Math.round(cssHeight * cappedDpr)
  const longEdge = Math.max(w, h)
  if (longEdge > maxEdge) {
    const scale = maxEdge / longEdge
    w = Math.round(w * scale)
    h = Math.round(h * scale)
  }
  canvas.width = Math.max(1, w)
  canvas.height = Math.max(1, h)
  currentDpr = dpr
  if (caps) {
    caps.gl.viewport(0, 0, canvas.width, canvas.height)
    screenOutput.resize(canvas.width, canvas.height, dpr)
  }
}

// Re-validates currentScreenGraph against screenOutput.targets after the
// target set changes (an ISF shader's inputs appearing/disappearing) — a
// route into a now-gone target fails construction-time validation, exactly
// like debugSetScreenGraph's own reject-and-keep-previous handling above.
// Failure here is left silent (no message posted): the ISF load itself
// already succeeded and got its own ack; a stale-but-internally-consistent
// evaluator is safe to keep running (resolveScreenTargets only reads
// target ids it currently iterates, per its own doc comment) — the visible
// effect is just that a route into a removed target stops applying until
// the editor's own graph is edited to drop it.
function rebuildScreenGraphEvaluator(): void {
  try {
    screenGraphEvaluator = new PatchGraphEvaluator(currentScreenGraph, screenOutput.targets)
  } catch {
    // keep the previous evaluator — see comment above
  }
}

// Same rebuild-against-a-changed-target-set pattern as
// rebuildScreenGraphEvaluator above, triggered by setFixtureDocument
// (adding/removing/renaming a fixture, or changing its type, changes which
// fixture:<id>.<channel> targets exist). No-op if no graph has been set
// yet — a host that only ever calls setFixtureDocument with no graph has
// nothing to route, same as fixtureGraphEvaluator's initial null state.
function rebuildFixtureGraphEvaluator(): void {
  if (!currentFixtureGraph) return
  try {
    fixtureGraphEvaluator = new PatchGraphEvaluator(currentFixtureGraph, fixtureOutput.targets())
  } catch {
    // keep the previous evaluator — a route into a now-gone fixture channel
    // just stops applying until the graph is edited to drop it, same as
    // the screen's own handling above
  }
}

self.onmessage = (e: MessageEvent<MainToRenderWorker>) => {
  const msg = e.data
  switch (msg.kind) {
    case 'init': {
      canvasRef = msg.canvas
      reducedMotion = msg.reducedMotion
      currentDpr = msg.dpr
      try {
        caps = createGlContext(msg.canvas)
      } catch (err) {
        const message = err instanceof WebGL2UnavailableError ? err.message : String(err)
        post({ kind: 'error', message })
        return
      }
      caps.gl.viewport(0, 0, msg.canvas.width, msg.canvas.height)
      screenOutput.init(caps, msg.canvas.width, msg.canvas.height, msg.dpr, reducedMotion)
      start()

      // No listener anywhere in this codebase previously handled WebGL
      // context loss at all — without calling preventDefault() on
      // 'webglcontextlost', the spec says the browser will NOT even attempt
      // to restore the context; the canvas just stays permanently dead
      // until something recreates a context on it, which nothing here ever
      // did. `powerPreference: 'high-performance'` (context.ts) makes this
      // a real, not just theoretical, risk on hybrid-graphics laptops,
      // where the OS/driver can force a GPU switch and take the context
      // down at any time — reads exactly like "the view vanished on its
      // own for no reason". The context object itself survives loss/restore
      // (the browser resets its resources, not the reference), so recovery
      // is just: stop rendering, then on restoration re-run the same
      // init() this case already does, reusing the still-valid `caps.gl`.
      msg.canvas.addEventListener('webglcontextlost', (ev) => {
        ev.preventDefault()
        stop()
        post({ kind: 'error', message: 'WebGL context lost — attempting to recover' })
      })
      msg.canvas.addEventListener('webglcontextrestored', () => {
        console.log('[sinteza-viz] WebGL context restored, reinitializing')
        if (!caps || !canvasRef) return
        screenOutput.init(caps, canvasRef.width, canvasRef.height, currentDpr, reducedMotion)
        start()
      })
      break
    }
    case 'resize': {
      if (canvasRef) resize(canvasRef, msg.cssWidth, msg.cssHeight, msg.dpr)
      break
    }
    case 'visibility': {
      if (msg.hidden) stop()
      else start()
      break
    }
    case 'state': {
      latestStateFrame = msg.frame
      pendingEvents.push(...msg.frame.events)
      pendingHits.push(...msg.frame.spectralHits)
      break
    }
    case 'setReducedMotion': {
      reducedMotion = msg.value
      screenOutput.setReducedMotion(msg.value)
      break
    }
    case 'setAccent': {
      currentAccent = msg.rgb
      screenOutput.setAccent(msg.rgb)
      break
    }
    case 'setTier': {
      currentTier = msg.tier
      screenOutput.setTier(msg.tier)
      if (canvasRef) resize(canvasRef, canvasRef.width / currentDpr, canvasRef.height / currentDpr, currentDpr)
      break
    }
    case 'setShowIdleBeam': {
      screenOutput.setShowIdleBeam(msg.value)
      break
    }
    case 'debugSetParam': {
      debugOverrides[msg.key] = msg.value
      break
    }
    case 'debugTriggerDrop': {
      debugDropPending = true
      break
    }
    case 'debugSetScreenGraph': {
      try {
        // Reconstructed, not mutated in place — PatchGraphEvaluator's
        // constructor validates (throws on any error-severity issue, the
        // same §5.3 "reject unsafe at load time" guarantee Patchbay used to
        // give the screen), so an invalid edit (typo'd signal name, a
        // dangling wire, a cycle) is caught here and rejected without ever
        // touching the live evaluator the render loop reads every frame above.
        const next = new PatchGraphEvaluator(msg.graph, screenOutput.targets)
        screenGraphEvaluator = next
        currentScreenGraph = msg.graph
        post({ kind: 'patchbayConfigResult', ok: true })
      } catch (err) {
        post({ kind: 'patchbayConfigResult', ok: false, message: err instanceof Error ? err.message : String(err) })
      }
      break
    }
    case 'debugSetSignalBusStream': {
      streamSignalBus = msg.value
      break
    }
    case 'setIsfShader': {
      if (msg.source === null) {
        screenOutput.resetToDefaultScene()
        rebuildScreenGraphEvaluator()
        post({ kind: 'isfShaderResult', ok: true, targets: [] })
        break
      }
      try {
        const doc = parseIsf(msg.source)
        screenOutput.setIsfScene(doc)
        rebuildScreenGraphEvaluator()
        post({ kind: 'isfShaderResult', ok: true, targets: isfInputsToTargets(doc) })
      } catch (err) {
        post({ kind: 'isfShaderResult', ok: false, message: err instanceof Error ? err.message : String(err) })
      }
      break
    }
    case 'setOscOut': {
      if (msg.wsUrl === null) {
        oscOutBridge?.disconnect()
        oscOutBridge = null
        break
      }
      if (!oscOutBridge) oscOutBridge = new OscOutBridge((status) => post({ kind: 'oscOutStatus', ...status }))
      oscOutBridge.connect(msg.wsUrl)
      break
    }
    case 'setFixtureDocument': {
      fixtureOutput.setDocument(msg.doc)
      rebuildFixtureGraphEvaluator()
      break
    }
    case 'setFixtureGraph': {
      try {
        // Same reconstructed-not-mutated, reject-and-keep-previous
        // validation guarantee as debugSetScreenGraph above.
        const next = new PatchGraphEvaluator(msg.graph, fixtureOutput.targets())
        fixtureGraphEvaluator = next
        currentFixtureGraph = msg.graph
        post({ kind: 'fixtureGraphResult', ok: true })
      } catch (err) {
        post({ kind: 'fixtureGraphResult', ok: false, message: err instanceof Error ? err.message : String(err) })
      }
      break
    }
    case 'setFixtureOut': {
      if (msg.config === null) {
        fixtureOutput.disconnect()
        break
      }
      fixtureOutput.connect(msg.config, (status) => post({ kind: 'fixtureOutStatus', ...status }))
      break
    }
    case 'midiCc': {
      midiCcValues.set(msg.key, msg.value)
      break
    }
    case 'setOscIn': {
      if (msg.wsUrl === null) {
        oscInBridge?.disconnect()
        break
      }
      if (!oscInBridge) oscInBridge = new OscInBridge((status) => post({ kind: 'oscInStatus', ...status }))
      oscInBridge.connect(msg.wsUrl)
      break
    }
  }
}
