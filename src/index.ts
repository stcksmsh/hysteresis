import type { MainToRenderWorker, PowerTier, RenderWorkerToMain, StateFrame } from './shared/types'
import type { Sidecar } from './shared/sidecar'
import { isSidecar } from './shared/sidecar'
import { AudioEngine } from './audio/AudioEngine'
import { StructureSource } from './audio/StructureSource'

export type { PowerTier } from './shared/types'
export type { Sidecar } from './shared/sidecar'

// Matches the IO page's actual §6 contract (IO_PAGE_CHANGESET.md, and
// src/lib/{viz-bus,player-bus,audio-bus}.ts in stcksmsh.github.io) — not the
// original HYSTERESIS.md draft, which predates real integration constraints
// (getAudioContext/getAnalyser can be null at init time; accent is OKLCH,
// not a CSS string; transport arrives on a window CustomEvent bus, not
// pushed through this API). Kept intentionally this small — see the "don't
// grow the surface" note in the IO page's viz-bus.ts.
export interface VizOpts {
  accent: [number, number, number] // OKLCH [L, C, H] — site's current --accent
  tier: PowerTier
  getAudioContext: () => AudioContext | null
  getAnalyser: () => AnalyserNode | null
  // Where the compiled feature-worklet module lives. `audioWorklet.addModule()`
  // targets aren't asset-scanned by bundlers the way `new Worker(new URL(...))`
  // is, so this can't always be defaulted correctly for every consumer's
  // build. Optional, not part of the site's own contract — defaults to a
  // path relative to this module, which works when this package is built
  // and consumed as a normal dependency (see vite.lib.config.ts).
  workletUrl?: string | URL
}

export interface VizInstance {
  resize(): void
  destroy(): void
  setAccent(accent: [number, number, number]): void
  setTier(tier: PowerTier): void
}

// ---- window CustomEvent bus this listens to (IO_PAGE_CHANGESET.md §6.3) ----
// Mirrors stcksmsh.github.io's src/lib/player-bus.ts by convention, not by
// import — the two repos can't share TS types across the package boundary,
// and a raw `window` CustomEvent bus is exactly what makes that unnecessary:
// both sides only need to agree on the event name and payload shape below.
interface PlayerTrack {
  slug: string
  title: string
  accent?: [number, number, number]
  envelope?: string // precomputed sidecar URL for this track (IO_PAGE_CHANGESET.md §6.4)
  opus?: string
  m4a?: string
  durationSec?: number
}

type TransportEvent =
  | { type: 'play' }
  | { type: 'pause' }
  | { type: 'seek'; positionSec: number }
  | { type: 'trackchange'; track: PlayerTrack }
  | { type: 'position'; positionSec: number }

const TRANSPORT_EVENT = 'player:transport'
const AUDIO_POLL_INTERVAL_MS = 300

// OKLCH -> linear sRGB (Björn Ottosson's OKLab, the same math CSS Color 4's
// oklch() uses). Produces LINEAR 0..1 values, matching what uAccent expects
// — the render pipeline's own gamma correction happens once, at the very
// end of the composite pass, so accent must arrive un-gamma-encoded or that
// correction gets applied twice.
function oklchToLinearSrgb(l: number, c: number, hDeg: number): [number, number, number] {
  const h = (hDeg * Math.PI) / 180
  const a = c * Math.cos(h)
  const b = c * Math.sin(h)

  const l_ = l + 0.3963377774 * a + 0.2158037573 * b
  const m_ = l - 0.1055613458 * a - 0.0638541728 * b
  const s_ = l - 0.0894841775 * a - 1.291485548 * b
  const ll = l_ ** 3
  const mm = m_ ** 3
  const ss = s_ ** 3

  const r = 4.0767416621 * ll - 3.3077115913 * mm + 0.2309699292 * ss
  const g = -1.2684380046 * ll + 2.6097574011 * mm - 0.3413193965 * ss
  const bl = -0.0041960863 * ll - 0.7034186147 * mm + 1.707614701 * ss
  const clamp01 = (v: number) => Math.max(0, Math.min(1, v))
  return [clamp01(r), clamp01(g), clamp01(bl)]
}

export function init(canvas: HTMLCanvasElement, opts: VizOpts): VizInstance {
  const engine = new AudioEngine()
  const structureSource = new StructureSource()
  const workletUrl = opts.workletUrl ?? new URL('./worklets/feature-worklet.js', import.meta.url)

  let positionSec = 0
  let tier: PowerTier = opts.tier
  let destroyed = false
  let worker: Worker | null = null
  let postToWorker: ((msg: MainToRenderWorker, transfer?: Transferable[]) => void) | null = null

  const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  const onReducedMotionChange = (e: MediaQueryListEvent) => post({ kind: 'setReducedMotion', value: e.matches })

  function post(msg: MainToRenderWorker, transfer?: Transferable[]): void {
    if (!worker) return
    if (transfer) worker.postMessage(msg, transfer)
    else worker.postMessage(msg)
  }

  function dispatchFrame(frame: StateFrame): void {
    const fused = structureSource.active ? structureSource.fuse(frame, positionSec) : frame
    post({ kind: 'state', frame: fused })
  }

  engine.onStateFrame(dispatchFrame)

  let resizeObserver: ResizeObserver | null = null
  if ('transferControlToOffscreen' in canvas) {
    worker = new Worker(new URL('./render/worker/render-worker.ts', import.meta.url), { type: 'module' })
    postToWorker = post
    worker.onmessage = (e: MessageEvent<RenderWorkerToMain>) => {
      if (e.data.kind === 'error') console.error('[hysteresis]', e.data.message)
    }

    const offscreen = canvas.transferControlToOffscreen()
    post(
      { kind: 'init', canvas: offscreen, dpr: window.devicePixelRatio, reducedMotion: reducedMotionQuery.matches },
      [offscreen],
    )

    resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const { width, height } = entry.contentRect
      post({ kind: 'resize', cssWidth: width, cssHeight: height, dpr: window.devicePixelRatio })
    })
    resizeObserver.observe(canvas)
    reducedMotionQuery.addEventListener('change', onReducedMotionChange)
  } else {
    console.error('[hysteresis] OffscreenCanvas is not supported in this browser; the visual will not render')
  }

  post({ kind: 'setAccent', rgb: oklchToLinearSrgb(...opts.accent) })
  post({ kind: 'setTier', tier })

  // opts.getAudioContext()/getAnalyser() are null until the shared bus is
  // created on the site's first play click (IO_PAGE_CHANGESET.md §3) — this
  // package mounts well before that's guaranteed to exist, so poll rather
  // than assume it's there at init time. Attaches downstream of the
  // AnalyserNode itself (not a separate "source" node — the site's contract
  // doesn't expose one) — an AnalyserNode taps the signal without altering
  // it, so it's an equally valid attach point for our own Worklet.
  let audioPollHandle: ReturnType<typeof setInterval> | null = null
  function tryAttachAudio(): void {
    if (tier === 'idle-only' || engine.attached) return
    const ctx = opts.getAudioContext()
    const analyser = opts.getAnalyser()
    if (!ctx || !analyser) return
    void engine.attach(ctx, workletUrl, analyser)
    if (audioPollHandle !== null) {
      clearInterval(audioPollHandle)
      audioPollHandle = null
    }
  }
  tryAttachAudio()
  if (!engine.attached && tier !== 'idle-only') {
    audioPollHandle = setInterval(tryAttachAudio, AUDIO_POLL_INTERVAL_MS)
  }

  async function loadSidecar(url: string): Promise<void> {
    const res = await fetch(url)
    const json: unknown = await res.json()
    if (!isSidecar(json)) {
      console.error(`[hysteresis] ${url} is not a recognised sidecar (schema mismatch)`)
      return
    }
    structureSource.load(json as Sidecar)
    structureSource.resyncTo(positionSec)
  }

  function onTransport(e: Event): void {
    const evt = (e as CustomEvent<TransportEvent>).detail
    switch (evt.type) {
      case 'seek':
        positionSec = evt.positionSec
        structureSource.resyncTo(positionSec)
        break
      case 'position':
        positionSec = evt.positionSec
        break
      case 'trackchange':
        structureSource.clear()
        positionSec = 0
        if (evt.track.envelope) void loadSidecar(evt.track.envelope)
        break
      // 'play'/'pause' need no action here — the worklet keeps analysing
      // whatever the shared graph is doing regardless, and StateFrame's own
      // idle flag already tracks "has any real audio frame ever arrived",
      // not moment-to-moment play state.
    }
  }
  window.addEventListener(TRANSPORT_EVENT, onTransport)

  return {
    resize() {
      if (!postToWorker) return
      const rect = canvas.getBoundingClientRect()
      postToWorker({ kind: 'resize', cssWidth: rect.width, cssHeight: rect.height, dpr: window.devicePixelRatio })
    },

    setAccent(accent) {
      post({ kind: 'setAccent', rgb: oklchToLinearSrgb(...accent) })
    },

    setTier(next) {
      if (tier === next) return
      tier = next
      post({ kind: 'setTier', tier })
      if (tier === 'idle-only') {
        engine.detach()
        if (audioPollHandle !== null) {
          clearInterval(audioPollHandle)
          audioPollHandle = null
        }
      } else if (!engine.attached) {
        tryAttachAudio()
        if (!engine.attached && audioPollHandle === null) {
          audioPollHandle = setInterval(tryAttachAudio, AUDIO_POLL_INTERVAL_MS)
        }
      }
    },

    destroy() {
      if (destroyed) return
      destroyed = true
      window.removeEventListener(TRANSPORT_EVENT, onTransport)
      if (audioPollHandle !== null) clearInterval(audioPollHandle)
      engine.detach()
      resizeObserver?.disconnect()
      reducedMotionQuery.removeEventListener('change', onReducedMotionChange)
      worker?.terminate()
      worker = null
      postToWorker = null
    },
  }
}
