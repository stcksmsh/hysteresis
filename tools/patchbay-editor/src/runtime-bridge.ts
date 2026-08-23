import type { MainToRenderWorker, RenderWorkerToMain, StateFrame } from '../../../src/shared/types'
import type { PatchbayConfig } from '../../../src/render/conductor/patchbay/types'
import type { SignalBus } from '../../../src/render/conductor/types'
import type { DropDetectorDebug } from '../../../src/audio/worklet/brain/drop-detector'
import { AudioEngine } from '../../../src/audio/AudioEngine'

// Drives a REAL render-worker instance — the exact same worker the shipped
// package uses (imported by relative path into the worker's own module
// graph, not duplicated) — so the editor's "live preview" is the actual
// visual, not a mock of it. Deliberately bypasses the public init() API
// (src/index.ts): that's the stable host contract (see its own "don't grow
// the surface" note) and has no raw message channel to hang the editor's
// debug-only messages (debugSetPatchbayConfig/debugSetSignalBusStream) off
// of. This is dev-tool-only code, never shipped, so a bit of duplicated
// bootstrap (worker creation, resize wiring, AudioEngine attach) is the
// right trade against reaching into the public API's internals.
//
// Referencing render-worker.ts by URL, not by import, is deliberate too:
// Vite's `new Worker(new URL('...ts', import.meta.url), { type: 'module' })`
// transpiles the target on the fly in dev and bundles it standalone on
// build — no need for the published package's public/render-worker.js
// prebuild-and-indirect dance (that workaround exists only for consumers
// installing this as a dependency; this tool always runs from within this
// same repo/Vite project).
const RENDER_WORKER_URL = new URL('../../../src/render/worker/render-worker.ts', import.meta.url)
// Served from the real project's public/ dir (vite.patchbay-editor.config.ts
// points publicDir back out at it) — prebuilt by `npm run build:worklet`,
// which `npm run patchbay` runs first, same as the main app's dev script.
const WORKLET_URL = new URL('/worklets/feature-worklet.js', window.location.origin)
// Same value/reasoning as src/index.ts's RESIZE_DEBOUNCE_MS — a resize
// reallocates the whole render pipeline including MemoryFieldPass's
// ping-pong buffers (wiping the accumulated memory-field trail history), so
// an undebounced ResizeObserver firing on every intermediate size (e.g. a
// DevTools panel opening/closing, which fires multiple times as it
// animates open) reads as the view "vanishing"/getting reset repeatedly.
// This tool skipped that debounce originally — same bug, same fix.
const RESIZE_DEBOUNCE_MS = 150

export interface RuntimeBridgeCallbacks {
  onSignalBus?: (bus: SignalBus, dropDebug: DropDetectorDebug | null) => void
  onStats?: (fps: number) => void
  onError?: (message: string) => void
  onPatchbayResult?: (result: { ok: true } | { ok: false; message: string }) => void
}

export class RuntimeBridge {
  private worker: Worker
  private engine = new AudioEngine()
  private audioEl: HTMLAudioElement
  private ctx: AudioContext | null = null
  private resizeObserver: ResizeObserver
  private resizeDebounceHandle: ReturnType<typeof setTimeout> | null = null
  private objectUrl: string | null = null

  constructor(
    private canvas: HTMLCanvasElement,
    private callbacks: RuntimeBridgeCallbacks,
  ) {
    this.worker = new Worker(RENDER_WORKER_URL, { type: 'module' })
    this.worker.onmessage = (e: MessageEvent<RenderWorkerToMain>) => this.handleWorkerMessage(e.data)

    const offscreen = canvas.transferControlToOffscreen()
    const dpr = window.devicePixelRatio || 1
    this.post({ kind: 'init', canvas: offscreen, dpr, reducedMotion: false }, [offscreen])

    this.resizeObserver = new ResizeObserver(() => this.postResizeDebounced())
    this.resizeObserver.observe(canvas)
    this.postResize() // first size is real and immediate — nothing to coalesce against yet

    this.audioEl = new Audio()
    this.audioEl.crossOrigin = 'anonymous'

    this.engine.onStateFrame((frame: StateFrame) => this.post({ kind: 'state', frame }))
  }

  // Rewires which handlers get called, without touching the worker/canvas
  // at all. Exists for App.tsx's bridge cache (see its useRuntimeBridge): a
  // Fast-Refresh remount gets a fresh set of React state setters to call,
  // but must reuse the SAME RuntimeBridge instance, since its canvas was
  // already (irreversibly) transferred to the existing worker.
  setCallbacks(callbacks: RuntimeBridgeCallbacks): void {
    this.callbacks = callbacks
  }

  private post(msg: MainToRenderWorker, transfer?: Transferable[]): void {
    if (transfer) this.worker.postMessage(msg, transfer)
    else this.worker.postMessage(msg)
  }

  private postResize(): void {
    const rect = this.canvas.getBoundingClientRect()
    this.post({ kind: 'resize', cssWidth: rect.width, cssHeight: rect.height, dpr: window.devicePixelRatio || 1 })
  }

  private postResizeDebounced(): void {
    if (this.resizeDebounceHandle !== null) clearTimeout(this.resizeDebounceHandle)
    this.resizeDebounceHandle = setTimeout(() => {
      this.resizeDebounceHandle = null
      this.postResize()
    }, RESIZE_DEBOUNCE_MS)
  }

  private handleWorkerMessage(msg: RenderWorkerToMain): void {
    switch (msg.kind) {
      case 'error':
        this.callbacks.onError?.(msg.message)
        break
      case 'stats':
        this.callbacks.onStats?.(msg.fps)
        break
      case 'signalBus':
        this.callbacks.onSignalBus?.(msg.bus, msg.dropDebug)
        break
      case 'patchbayConfigResult':
        this.callbacks.onPatchbayResult?.(msg.ok ? { ok: true } : { ok: false, message: msg.message })
        break
    }
  }

  // Live-swaps the screen output's active routing — the whole point of the
  // editor. Fire-and-forget from the caller's perspective; the result comes
  // back async via onPatchbayResult (rejected edits leave the previous,
  // still-valid config running, per render-worker.ts's handler).
  setPatchbayConfig(config: PatchbayConfig): void {
    this.post({ kind: 'debugSetPatchbayConfig', config })
  }

  setSignalBusStream(on: boolean): void {
    this.post({ kind: 'debugSetSignalBusStream', value: on })
  }

  async loadFile(file: File): Promise<void> {
    if (!this.ctx) {
      this.ctx = new AudioContext()
      const source = this.ctx.createMediaElementSource(this.audioEl)
      const analyser = this.ctx.createAnalyser()
      analyser.fftSize = 256
      source.connect(analyser)
      analyser.connect(this.ctx.destination)
      await this.engine.attach(this.ctx, WORKLET_URL, analyser)
    }
    await this.ctx.resume() // suspended until a user gesture — loadFile is called from one (a file-picker change handler)

    if (this.objectUrl) URL.revokeObjectURL(this.objectUrl)
    this.objectUrl = URL.createObjectURL(file)
    this.audioEl.src = this.objectUrl
    await this.audioEl.play()
  }

  get playing(): boolean {
    return !this.audioEl.paused
  }

  togglePlayback(): void {
    if (this.audioEl.paused) void this.audioEl.play()
    else this.audioEl.pause()
  }

  dispose(): void {
    if (this.resizeDebounceHandle !== null) clearTimeout(this.resizeDebounceHandle)
    this.resizeObserver.disconnect()
    this.engine.detach()
    this.audioEl.pause()
    if (this.objectUrl) URL.revokeObjectURL(this.objectUrl)
    this.worker.terminate()
  }
}
