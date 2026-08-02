import './styles.css'
import type { MainToRenderWorker, RenderWorkerToMain, StateFrame } from './shared/types'
import type { Timeline } from './shared/timeline'
import { HYST_FORMAT_VERSION } from './shared/timeline'
import { AudioEngine } from './audio/AudioEngine'
import { TimelineSource } from './audio/TimelineSource'
import { mountControls } from './ui/controls'
import { DebugOverlay, isDebugEnabled } from './ui/debug-overlay'

const canvas = document.querySelector<HTMLCanvasElement>('#scene')!
const ui = document.querySelector<HTMLDivElement>('#ui')!

const engine = new AudioEngine()

// Bound once the render worker exists; the picker is simply inert if the
// browser never got as far as creating one.
let postToWorker: ((msg: MainToRenderWorker) => void) | null = null
let overlay: DebugOverlay | null = null
let timelineSource: TimelineSource | null = null

// While a .hyst is loaded, it fully replaces the live worklet as the source
// of StateFrames — both would otherwise drive the scene at once and fight
// each other's choreography.
function dispatchFrame(frame: StateFrame): void {
  postToWorker?.({ kind: 'state', frame })
  overlay?.update(frame)
}

async function loadTimelineFile(file: File): Promise<void> {
  const text = await file.text()
  const timeline = JSON.parse(text) as Timeline
  if (timeline.version !== HYST_FORMAT_VERSION) {
    console.error(`[main] .hyst version ${timeline.version} does not match expected ${HYST_FORMAT_VERSION}`)
    return
  }
  timelineSource?.stop()
  timelineSource = new TimelineSource(timeline, () => engine.currentTime)
  timelineSource.onStateFrame(dispatchFrame)
  timelineSource.start()
}

mountControls(
  ui,
  engine,
  (sceneId) => postToWorker?.({ kind: 'setScene', sceneId }),
  (file) => void loadTimelineFile(file),
)

function showFallback(message: string) {
  canvas.style.display = 'none'
  const el = document.createElement('div')
  el.style.cssText = 'padding:24px;font-family:system-ui,sans-serif;color:#eee;max-width:480px'
  el.textContent = `HYSTERESIS couldn't start: ${message}. Try a recent version of Chrome, Firefox, or Safari.`
  ui.appendChild(el)
}

if (!('transferControlToOffscreen' in canvas)) {
  showFallback('OffscreenCanvas is not supported in this browser')
} else {
  const worker = new Worker(new URL('./render/worker/render-worker.ts', import.meta.url), {
    type: 'module',
  })

  worker.onmessage = (e: MessageEvent<RenderWorkerToMain>) => {
    if (e.data.kind === 'error') showFallback(e.data.message)
    else if (e.data.kind === 'stats') overlay?.setFps(e.data.fps)
  }

  const offscreen = canvas.transferControlToOffscreen()
  const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')

  const post = (msg: MainToRenderWorker, transfer?: Transferable[]) =>
    transfer ? worker.postMessage(msg, transfer) : worker.postMessage(msg)
  postToWorker = post

  post(
    {
      kind: 'init',
      canvas: offscreen,
      dpr: window.devicePixelRatio,
      reducedMotion: reducedMotionQuery.matches,
    },
    [offscreen],
  )

  const resizeObserver = new ResizeObserver((entries) => {
    const entry = entries[0]
    if (!entry) return
    const { width, height } = entry.contentRect
    post({ kind: 'resize', cssWidth: width, cssHeight: height, dpr: window.devicePixelRatio })
  })
  resizeObserver.observe(canvas)

  document.addEventListener('visibilitychange', () => {
    post({ kind: 'visibility', hidden: document.hidden })
  })

  reducedMotionQuery.addEventListener('change', (e) => {
    post({ kind: 'setReducedMotion', value: e.matches })
  })

  // Live worklet frames drive the scene directly; once a .hyst is loaded,
  // TimelineSource takes over via the same dispatchFrame path instead.
  engine.onStateFrame((frame) => {
    if (!timelineSource) dispatchFrame(frame)
  })

  if (isDebugEnabled()) {
    overlay = new DebugOverlay(ui, post)
  }
}
