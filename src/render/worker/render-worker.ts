/// <reference lib="webworker" />
import type { MainToRenderWorker, PowerTier, RenderWorkerToMain, SpectralHit, StateFrame, StructuralEvent } from '../../shared/types'
import { createGlContext, WebGL2UnavailableError, type GlCapabilities } from './gl/context'
import { Conductor } from '../conductor/Conductor'
import { Patchbay } from '../conductor/patchbay/Patchbay'
import { screenOnlyConfig } from '../conductor/patchbay/configs/screen-only'
import { ScreenOutput } from '../conductor/outputs/ScreenOutput'
import type { VizOutput } from '../conductor/types'

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
const patchbay = new Patchbay(screenOnlyConfig, outputs.map((o) => o.targets))

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

function loop(t: number) {
  if (!running || !caps) return
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
    const resolved = patchbay.resolve(bus, dt, output.targets)
    output.update(dt, resolved)
  }

  if (dt > 0) updateAdaptiveQuality(dt * 1000, t)

  rafHandle = raf(loop)
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
  }
}
