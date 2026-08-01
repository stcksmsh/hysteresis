/// <reference lib="webworker" />
import type { MainToRenderWorker, RenderWorkerToMain, SpectralHit, StateFrame, StructuralEvent } from '../../shared/types'
import { createGlContext, WebGL2UnavailableError, type GlCapabilities } from './gl/context'
import { createFbo, deleteFbo, type Fbo } from './gl/fbo'
import { sceneRegistry, DEFAULT_SCENE_ID } from './scenes/registry'
import type { Scene, SceneContext } from './scenes/Scene'
import { Choreographer } from '../choreography/Choreographer'
import { PersistencePass } from './passes/persistence-pass'
import { BloomPass } from './passes/bloom-pass'
import { CompositePass } from './passes/composite-pass'

declare const self: DedicatedWorkerGlobalScope

const PERSISTENCE_DECAY = 0.85
const BLOOM_THRESHOLD = 0.55
const BLOOM_STRENGTH = 0.6

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
let scene: Scene | null = null
let currentDpr = 1

let smoothedFrameMs = 16
let qualityScale = 1
let resolutionStep = 0
let overrunSinceMs: number | null = null
let lastStatsPost = 0

let sceneFbo: Fbo | null = null
let persistencePass: PersistencePass | null = null
let bloomPass: BloomPass | null = null
let compositePass: CompositePass | null = null

const choreographer = new Choreographer()

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
}

// StateFrames arrive at analysis-hop rate (~90Hz), rendering at display
// refresh (~60Hz) — a rate mismatch. Continuous fields use the latest frame
// (overwrite, not queue: queuing would build lag and break the anticipation-
// then-release feel), but discrete events accumulate here and get drained
// once per rendered frame so a transient between two rAF ticks is never lost.
let pendingEvents: StructuralEvent[] = []
let pendingHits: SpectralHit[] = []

// Debug-only overrides (?debug=1 scene-tuning sliders): patched onto
// whichever StateFrame is active each frame, so the full real choreography
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
  if (!running || !caps || !scene || !sceneFbo || !compositePass) return
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

  const params = choreographer.update(effectiveFrame, dt)
  scene.update(dt, params)
  scene.render(sceneFbo.framebuffer)

  let currentTexture = sceneFbo.texture
  if (scene.wantsPersistencePass && persistencePass && !reducedMotion) {
    currentTexture = persistencePass.apply(currentTexture, PERSISTENCE_DECAY)
  }

  let bloomTexture: WebGLTexture | null = null
  if (scene.wantsBloom && bloomPass && !reducedMotion) {
    bloomTexture = bloomPass.apply(currentTexture, BLOOM_THRESHOLD)
  }

  compositePass.apply(null, sceneFbo.width, sceneFbo.height, currentTexture, bloomTexture, BLOOM_STRENGTH)

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
  scene?.setQuality?.(qualityScale)

  // Substeps are already floored; if we're still over budget after a
  // sustained stretch, the resolution itself is the problem.
  const stuckAtMinQuality = qualityScale <= 0.2
  const sustained = overrunSinceMs !== null && t - overrunSinceMs > RESOLUTION_STEP_AFTER_MS
  if (stuckAtMinQuality && sustained && resolutionStep < RESOLUTION_STEPS.length - 1) {
    resolutionStep++
    scene?.setSimMaxEdge?.(RESOLUTION_STEPS[resolutionStep])
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

// (Re)allocates the offscreen scene target + polish passes at the given
// resolution. Called on init and on every resize.
function allocatePipeline(width: number, height: number) {
  if (!caps) return
  const gl = caps.gl
  if (sceneFbo) deleteFbo(gl, sceneFbo)
  sceneFbo = createFbo(gl, Math.max(1, width), Math.max(1, height), caps.floatFbo)

  if (persistencePass) persistencePass.resize(width, height)
  else persistencePass = new PersistencePass(gl, width, height, caps.floatFbo)

  if (bloomPass) bloomPass.resize(width, height)
  else bloomPass = new BloomPass(gl, width, height, caps.floatFbo)

  if (!compositePass) compositePass = new CompositePass(gl)
}

function switchScene(sceneId: string) {
  const factory = sceneRegistry[sceneId]
  // Ignore unknown ids rather than throwing — a stale picker value should
  // never take down the render loop.
  if (!factory || !caps || !canvasRef || sceneId === scene?.id) return

  scene?.dispose()
  scene = factory()
  scene.init({
    gl: caps.gl,
    width: canvasRef.width,
    height: canvasRef.height,
    dpr: currentDpr,
    reducedMotion,
    floatFbo: caps.floatFbo,
  })

  // Cost differs per scene, so previous backoff decisions don't carry over.
  qualityScale = 1
  overrunSinceMs = null
  scene.setQuality?.(qualityScale)
}

function sceneContext(width: number, height: number, dpr: number): SceneContext | null {
  if (!caps) return null
  return { gl: caps.gl, width, height, dpr, reducedMotion, floatFbo: caps.floatFbo }
}

function resize(canvas: OffscreenCanvas, cssWidth: number, cssHeight: number, dpr: number) {
  // Cap DPR and absolute resolution so a 4K/high-DPR display doesn't melt.
  const cappedDpr = Math.min(dpr, 2)
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
    allocatePipeline(canvas.width, canvas.height)
    const ctx = sceneContext(canvas.width, canvas.height, dpr)
    if (ctx) scene?.resize(ctx)
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
      allocatePipeline(msg.canvas.width, msg.canvas.height)
      scene = sceneRegistry[DEFAULT_SCENE_ID]()
      scene.init({
        gl: caps.gl,
        width: msg.canvas.width,
        height: msg.canvas.height,
        dpr: msg.dpr,
        reducedMotion,
        floatFbo: caps.floatFbo,
      })
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
      if (canvasRef) {
        const ctx = sceneContext(canvasRef.width, canvasRef.height, currentDpr)
        if (ctx) scene?.resize(ctx)
      }
      break
    }
    case 'setScene': {
      switchScene(msg.sceneId)
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
