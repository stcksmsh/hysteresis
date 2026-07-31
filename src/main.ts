import './styles.css'
import type { MainToRenderWorker, RenderWorkerToMain } from './shared/types'
import { AudioEngine } from './audio/AudioEngine'
import { mountControls } from './ui/controls'
import { DebugOverlay, isDebugEnabled } from './ui/debug-overlay'

const canvas = document.querySelector<HTMLCanvasElement>('#scene')!
const ui = document.querySelector<HTMLDivElement>('#ui')!

const engine = new AudioEngine()
mountControls(ui, engine)

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
  }

  const offscreen = canvas.transferControlToOffscreen()
  const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')

  const post = (msg: MainToRenderWorker, transfer?: Transferable[]) =>
    transfer ? worker.postMessage(msg, transfer) : worker.postMessage(msg)

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

  engine.onStateFrame((frame) => post({ kind: 'state', frame }))

  if (isDebugEnabled()) {
    const overlay = new DebugOverlay(ui, post)
    engine.onStateFrame((frame) => overlay.update(frame))
  }
}
