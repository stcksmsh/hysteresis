import './styles.css'
import { init } from './index'

// Local dev harness ONLY — exercises the public init() API exactly as the
// IO page does (see IO_PAGE_CHANGESET.md §6 / stcksmsh.github.io's
// src/lib/{viz-bus,player-bus,audio-bus}.ts). Not shipped: the actual
// package entry point is src/index.ts (built via `npm run build:lib`).
//
// Mirrors the site's real lazy-audio-bus pattern: no AudioContext exists
// until the first play click (autoplay policy), so init() is called
// immediately with getAudioContext()/getAnalyser() closures that return
// null until then — exactly what a real host does — and transport is
// dispatched on the same `window` "player:transport" CustomEvent the site
// uses, not called directly on the returned handle (init() doesn't expose
// transport methods at all; it listens for this bus itself).
const canvas = document.querySelector<HTMLCanvasElement>('#scene')!
const ui = document.querySelector<HTMLDivElement>('#ui')!

const audio = new Audio()
audio.crossOrigin = 'anonymous'

let bus: { ctx: AudioContext; analyser: AnalyserNode } | null = null
function ensureAudioBus(): { ctx: AudioContext; analyser: AnalyserNode } {
  if (bus) return bus
  const ctx = new AudioContext()
  const source = ctx.createMediaElementSource(audio)
  const analyser = ctx.createAnalyser()
  analyser.fftSize = 256
  source.connect(analyser)
  analyser.connect(ctx.destination)
  bus = { ctx, analyser }
  return bus
}

const workletUrl = new URL(`${import.meta.env.BASE_URL}worklets/feature-worklet.js`, window.location.href)
// index.ts's own renderWorkerUrl default is relative to wherever its
// MODULE's own chunk ends up (import.meta.url) — fine when that's dist/
// root (the lib build), but this dev harness's own app-mode build hashes
// src/index.ts into dist/assets/, which breaks that default the same way
// it broke for stcksmsh.github.io (see VizOpts.renderWorkerUrl's doc
// comment). BASE_URL + the known public/ filename sidesteps it entirely.
const renderWorkerUrl = new URL(`${import.meta.env.BASE_URL}render-worker.js`, window.location.href)
init(canvas, {
  accent: [0.68, 0.2, 33], // vermilion, matching SINTEZA_VIZ.md's default
  tier: 'full',
  getAudioContext: () => bus?.ctx ?? null,
  getAnalyser: () => bus?.analyser ?? null,
  workletUrl,
  renderWorkerUrl,
})

function emitTransport(detail: object): void {
  window.dispatchEvent(new CustomEvent('player:transport', { detail }))
}

let objectUrl: string | null = null
let sidecarObjectUrl: string | null = null
let posRafHandle: number | null = null

function trackPosition(): void {
  if (posRafHandle !== null) cancelAnimationFrame(posRafHandle)
  const tick = () => {
    emitTransport({ type: 'position', positionSec: audio.currentTime })
    posRafHandle = requestAnimationFrame(tick)
  }
  tick()
}

async function loadAndPlay(file: File, sidecarFile: File | null): Promise<void> {
  const { ctx } = ensureAudioBus()
  await ctx.resume() // suspended until a user gesture — this handler is one

  if (objectUrl) URL.revokeObjectURL(objectUrl)
  objectUrl = URL.createObjectURL(file)
  if (sidecarObjectUrl) URL.revokeObjectURL(sidecarObjectUrl)
  sidecarObjectUrl = sidecarFile ? URL.createObjectURL(sidecarFile) : null

  emitTransport({
    type: 'trackchange',
    track: { slug: file.name, title: file.name, envelope: sidecarObjectUrl ?? undefined },
  })
  audio.src = objectUrl
  await audio.play()
  emitTransport({ type: 'play' })
  trackPosition()
}

const wrap = document.createElement('div')
wrap.style.cssText = 'position:fixed;left:16px;bottom:16px;display:flex;gap:8px;align-items:center'

const fileInput = document.createElement('input')
fileInput.type = 'file'
fileInput.accept = 'audio/*'
fileInput.style.color = '#eee'

const sidecarInput = document.createElement('input')
sidecarInput.type = 'file'
sidecarInput.accept = '.json'
sidecarInput.title = 'Optional precomputed sidecar.json for the selected track'
sidecarInput.style.color = '#eee'

fileInput.addEventListener('change', () => {
  const file = fileInput.files?.[0]
  if (file) void loadAndPlay(file, sidecarInput.files?.[0] ?? null)
})
wrap.appendChild(fileInput)
wrap.appendChild(sidecarInput)

const playPause = document.createElement('button')
playPause.textContent = 'Pause'
playPause.addEventListener('click', async () => {
  if (audio.paused) {
    await audio.play()
    emitTransport({ type: 'play' })
    playPause.textContent = 'Pause'
  } else {
    audio.pause()
    emitTransport({ type: 'pause' })
    playPause.textContent = 'Resume'
  }
})
wrap.appendChild(playPause)

ui.appendChild(wrap)
