import './styles.css'
import { init } from './index'

// Local dev harness ONLY — exercises the public init() API exactly as a host
// (the IO page) would. Not shipped: the actual package entry point is
// src/index.ts (built via `npm run build:lib`), and everything below —
// file picking, AudioContext creation, transport — is the host's job per
// HYSTERESIS.md §7/§10, not this repo's.
//
// init() is called immediately, with one persistent <audio> element as the
// source (never swapped) — matching §7's "host mounts once, never destroys",
// and specifically so the idle Lissajous state (§8) is visible before any
// file is ever picked. Swapping tracks changes `audio.src`, not the graph.
const canvas = document.querySelector<HTMLCanvasElement>('#scene')!
const ui = document.querySelector<HTMLDivElement>('#ui')!

const audio = new Audio()
audio.crossOrigin = 'anonymous'

const ctx = new AudioContext()
const sourceNode = ctx.createMediaElementSource(audio)
sourceNode.connect(ctx.destination)

const workletUrl = new URL(`${import.meta.env.BASE_URL}worklets/feature-worklet.js`, window.location.href)
const handle = init(canvas, {
  analyser: ctx.createAnalyser(),
  audioContext: ctx,
  source: sourceNode,
  workletUrl,
})

let objectUrl: string | null = null
let posRafHandle: number | null = null

function trackPosition(): void {
  if (posRafHandle !== null) cancelAnimationFrame(posRafHandle)
  const tick = () => {
    handle.setPosition(audio.currentTime)
    posRafHandle = requestAnimationFrame(tick)
  }
  tick()
}

async function loadAndPlay(file: File): Promise<void> {
  await ctx.resume() // AudioContext starts suspended until a user gesture — this handler is one
  if (objectUrl) URL.revokeObjectURL(objectUrl)
  objectUrl = URL.createObjectURL(file)

  handle.setTransport({ type: 'trackchange' })
  audio.src = objectUrl
  await audio.play()
  handle.setTransport({ type: 'play' })
  trackPosition()
}

const wrap = document.createElement('div')
wrap.style.cssText = 'position:fixed;left:16px;bottom:16px;display:flex;gap:8px;align-items:center'

const fileInput = document.createElement('input')
fileInput.type = 'file'
fileInput.accept = 'audio/*'
fileInput.style.color = '#eee'
fileInput.addEventListener('change', () => {
  const file = fileInput.files?.[0]
  if (file) void loadAndPlay(file)
})
wrap.appendChild(fileInput)

const playPause = document.createElement('button')
playPause.textContent = 'Pause'
playPause.addEventListener('click', async () => {
  if (audio.paused) {
    await audio.play()
    handle.setTransport({ type: 'play' })
    playPause.textContent = 'Pause'
  } else {
    audio.pause()
    handle.setTransport({ type: 'pause' })
    playPause.textContent = 'Resume'
  }
})
wrap.appendChild(playPause)

ui.appendChild(wrap)
