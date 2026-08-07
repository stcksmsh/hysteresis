import type { MainToRenderWorker, PowerTier, RenderWorkerToMain, StateFrame } from './shared/types'
import type { Sidecar } from './shared/sidecar'
import { isSidecar } from './shared/sidecar'
import { AudioEngine } from './audio/AudioEngine'
import { StructureSource } from './audio/StructureSource'

export type { PowerTier } from './shared/types'
export type { Sidecar } from './shared/sidecar'

export type TransportEvent =
  | { type: 'play' }
  | { type: 'pause' }
  | { type: 'seek'; seconds: number }
  | { type: 'trackchange' }

export interface InitOptions {
  analyser: AnalyserNode
  audioContext: AudioContext
  source?: AudioNode
  // Where the compiled feature-worklet module lives. `audioWorklet.addModule()`
  // targets aren't asset-scanned by bundlers the way `new Worker(new URL(...))`
  // is, so this can't always be defaulted correctly for every consumer's build
  // — pass the URL the host serves `worklets/feature-worklet.js` at if the
  // default (relative to this module) doesn't resolve.
  workletUrl?: string | URL
}

export interface HysteresisHandle {
  resize(): void
  setTransport(evt: TransportEvent): void
  setPosition(seconds: number): void
  loadSidecar(url: string): Promise<void>
  setAccent(cssColor: string): void
  setTier(tier: PowerTier): void
  destroy(): void
}

function cssColorToRgb(cssColor: string): [number, number, number] {
  const probe = document.createElement('canvas')
  probe.width = 1
  probe.height = 1
  const ctx = probe.getContext('2d')
  if (!ctx) return [1, 1, 1]
  ctx.fillStyle = cssColor
  ctx.fillRect(0, 0, 1, 1)
  const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data
  return [r / 255, g / 255, b / 255]
}

export function init(canvas: HTMLCanvasElement, opts: InitOptions): HysteresisHandle {
  const engine = new AudioEngine()
  const structureSource = new StructureSource()
  const workletUrl = opts.workletUrl ?? new URL('./worklets/feature-worklet.js', import.meta.url)

  let positionSec = 0
  let tier: PowerTier = 'full'
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

  // `tier` starts at 'full' (idle-only is only ever entered via setTier), so
  // the initial attach is unconditional.
  void engine.attach(opts.audioContext, workletUrl, opts.source)

  return {
    resize() {
      if (!postToWorker) return
      const rect = canvas.getBoundingClientRect()
      postToWorker({ kind: 'resize', cssWidth: rect.width, cssHeight: rect.height, dpr: window.devicePixelRatio })
    },

    setTransport(evt) {
      if (evt.type === 'seek') {
        positionSec = evt.seconds
        structureSource.resyncTo(positionSec)
      } else if (evt.type === 'trackchange') {
        structureSource.clear()
        positionSec = 0
      }
    },

    setPosition(seconds) {
      positionSec = seconds
    },

    async loadSidecar(url) {
      const res = await fetch(url)
      const json: unknown = await res.json()
      if (!isSidecar(json)) {
        console.error(`[hysteresis] ${url} is not a recognised sidecar (schema mismatch)`)
        return
      }
      structureSource.load(json as Sidecar)
      structureSource.resyncTo(positionSec)
    },

    setAccent(cssColor) {
      post({ kind: 'setAccent', rgb: cssColorToRgb(cssColor) })
    },

    setTier(next) {
      if (tier === next) return
      tier = next
      post({ kind: 'setTier', tier })
      if (tier === 'idle-only') {
        engine.detach()
      } else if (!engine.attached) {
        void engine.attach(opts.audioContext, workletUrl, opts.source)
      }
    },

    destroy() {
      if (destroyed) return
      destroyed = true
      engine.detach()
      resizeObserver?.disconnect()
      reducedMotionQuery.removeEventListener('change', onReducedMotionChange)
      worker?.terminate()
      worker = null
      postToWorker = null
    },
  }
}
