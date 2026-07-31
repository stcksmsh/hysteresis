import type { MainToRenderWorker, StateFrame } from '../shared/types'
import { BAND_NAMES } from '../audio/worklet/bands'
import { Choreographer } from '../render/choreography/Choreographer'

const NUMERIC_FIELDS = ['tempo', 'tempoConfidence', 'beatPhase', 'barPhase', 'buildProgress', 'tension', 'energy', 'centroid', 'flatness'] as const
const BAR_FIELDS = ['buildProgress', 'tension'] as const
const MAX_LOG_ENTRIES = 10

export function isDebugEnabled(): boolean {
  return new URLSearchParams(window.location.search).get('debug') === '1'
}

export class DebugOverlay {
  private bars = new Map<string, HTMLDivElement>()
  private numbers = new Map<string, HTMLSpanElement>()
  private beatDot: HTMLDivElement
  private barSegments: HTMLDivElement[] = []
  private eventLog: HTMLDivElement
  private pending: StateFrame | null = null
  private rafHandle: number | null = null
  private lastTime: number | null = null

  // Phase-3.5 thesis-proof gate: a bare circle whose radius is driven by
  // the Choreographer's `windup` output (build -> wind up, drop -> release).
  // If this doesn't visibly wind up and release against a real track, the
  // rest of the build (a whole reaction-diffusion scene on top) is premature
  // — fix Layer 2/choreography first. Lives behind ?debug=1 alongside the
  // rest of this panel; not a production visual.
  private choreographer = new Choreographer()
  private thesisCanvas: HTMLCanvasElement
  private thesisCtx: CanvasRenderingContext2D

  constructor(container: HTMLElement, onSceneDebugMessage?: (msg: MainToRenderWorker) => void) {
    if (onSceneDebugMessage) {
      container.appendChild(this.makeSceneTuningPanel(onSceneDebugMessage))
    }

    this.thesisCanvas = document.createElement('canvas')
    this.thesisCanvas.width = 160
    this.thesisCanvas.height = 160
    this.thesisCanvas.style.cssText = 'position:fixed;left:16px;top:16px;background:rgba(0,0,0,0.55);border-radius:6px'
    container.appendChild(this.thesisCanvas)
    this.thesisCtx = this.thesisCanvas.getContext('2d')!

    const panel = document.createElement('div')
    panel.style.cssText =
      'position:fixed;right:16px;top:16px;font:12px/1.4 monospace;color:#eee;background:rgba(0,0,0,0.55);padding:12px;border-radius:6px;min-width:240px'

    const beatRow = document.createElement('div')
    beatRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:8px'
    this.beatDot = document.createElement('div')
    this.beatDot.style.cssText = 'width:14px;height:14px;border-radius:50%;background:#7fd0ff'
    beatRow.appendChild(this.beatDot)
    const barWrap = document.createElement('div')
    barWrap.style.cssText = 'display:flex;gap:3px'
    for (let i = 0; i < 4; i++) {
      const seg = document.createElement('div')
      seg.style.cssText = 'width:14px;height:8px;background:#333;border-radius:2px'
      barWrap.appendChild(seg)
      this.barSegments.push(seg)
    }
    beatRow.appendChild(barWrap)
    panel.appendChild(beatRow)

    const bandsWrap = document.createElement('div')
    for (const name of BAND_NAMES) {
      bandsWrap.appendChild(this.makeBarRow(name, '#7fd0ff'))
    }
    panel.appendChild(bandsWrap)

    const namedBarsWrap = document.createElement('div')
    namedBarsWrap.style.marginTop = '4px'
    for (const field of BAR_FIELDS) {
      namedBarsWrap.appendChild(this.makeBarRow(field, '#ff9d7f'))
    }
    panel.appendChild(namedBarsWrap)

    const numbersWrap = document.createElement('div')
    numbersWrap.style.marginTop = '8px'
    for (const field of NUMERIC_FIELDS) {
      numbersWrap.appendChild(this.makeNumberRow(field))
    }
    panel.appendChild(numbersWrap)

    this.eventLog = document.createElement('div')
    this.eventLog.style.cssText = 'margin-top:8px;max-height:120px;overflow:hidden;font-size:11px;color:#9ad'
    panel.appendChild(this.eventLog)

    container.appendChild(panel)

    const loop = (now: number) => {
      const dt = this.lastTime === null ? 0 : Math.min(0.1, (now - this.lastTime) / 1000)
      this.lastTime = now
      if (this.pending) {
        this.render(this.pending)
        const { windup } = this.choreographer.update(this.pending, dt)
        this.drawThesisCircle(windup)
      }
      this.rafHandle = requestAnimationFrame(loop)
    }
    this.rafHandle = requestAnimationFrame(loop)
  }

  update(frame: StateFrame): void {
    this.pending = frame
    if (frame.events.length > 0) this.logEvents(frame.events, frame.t)
  }

  dispose(): void {
    if (this.rafHandle !== null) cancelAnimationFrame(this.rafHandle)
  }

  private makeSceneTuningPanel(onSceneDebugMessage: (msg: MainToRenderWorker) => void): HTMLDivElement {
    const panel = document.createElement('div')
    panel.style.cssText =
      'position:fixed;left:16px;bottom:56px;font:12px/1.4 monospace;color:#eee;background:rgba(0,0,0,0.55);padding:10px;border-radius:6px;min-width:200px;display:flex;flex-direction:column;gap:6px'

    const makeSlider = (label: string, key: 'buildProgress' | 'tension') => {
      const row = document.createElement('label')
      row.style.cssText = 'display:flex;flex-direction:column;gap:2px'
      const span = document.createElement('span')
      span.textContent = label
      const input = document.createElement('input')
      input.type = 'range'
      input.min = '0'
      input.max = '1'
      input.step = '0.01'
      input.value = '0'
      input.addEventListener('input', () => {
        onSceneDebugMessage({ kind: 'debugSetParam', key, value: parseFloat(input.value) })
      })
      row.appendChild(span)
      row.appendChild(input)
      return row
    }

    panel.appendChild(makeSlider('scene: buildProgress', 'buildProgress'))
    panel.appendChild(makeSlider('scene: tension', 'tension'))

    const dropButton = document.createElement('button')
    dropButton.textContent = 'Trigger drop'
    dropButton.addEventListener('click', () => onSceneDebugMessage({ kind: 'debugTriggerDrop' }))
    panel.appendChild(dropButton)

    return panel
  }

  private makeBarRow(label: string, color: string): HTMLDivElement {
    const row = document.createElement('div')
    row.style.cssText = 'display:flex;align-items:center;gap:6px;margin:2px 0'
    const name = document.createElement('span')
    name.textContent = label.slice(0, 9).padEnd(9, ' ')
    name.style.cssText = 'width:64px;white-space:pre'
    const track = document.createElement('div')
    track.style.cssText = 'flex:1;height:8px;background:#333;border-radius:2px;overflow:hidden'
    const fill = document.createElement('div')
    fill.dataset.band = label
    fill.style.cssText = `height:100%;width:0%;background:${color}`
    track.appendChild(fill)
    row.appendChild(name)
    row.appendChild(track)
    this.bars.set(label, fill)
    return row
  }

  private makeNumberRow(label: string): HTMLDivElement {
    const row = document.createElement('div')
    row.style.cssText = 'display:flex;justify-content:space-between;gap:12px'
    const name = document.createElement('span')
    name.textContent = label
    const value = document.createElement('span')
    value.dataset.field = label
    value.textContent = '0'
    row.appendChild(name)
    row.appendChild(value)
    this.numbers.set(label, value)
    return row
  }

  private logEvents(events: StateFrame['events'], t: number): void {
    for (const ev of events) {
      const line = document.createElement('div')
      line.textContent = `${t.toFixed(2)}s ${ev.type} (${ev.strength.toFixed(2)})`
      this.eventLog.prepend(line)
    }
    while (this.eventLog.childElementCount > MAX_LOG_ENTRIES) {
      this.eventLog.lastElementChild?.remove()
    }
  }

  private drawThesisCircle(windup: number): void {
    const ctx = this.thesisCtx
    const w = this.thesisCanvas.width
    const h = this.thesisCanvas.height
    ctx.clearRect(0, 0, w, h)
    const radius = Math.max(4, Math.min(75, 12 + windup * 60))
    ctx.beginPath()
    ctx.arc(w / 2, h / 2, radius, 0, Math.PI * 2)
    ctx.fillStyle = '#ff9d7f'
    ctx.fill()
    ctx.font = '11px monospace'
    ctx.fillStyle = '#eee'
    ctx.fillText(`windup ${windup.toFixed(2)}`, 8, h - 8)
  }

  private render(frame: StateFrame): void {
    for (const name of BAND_NAMES) {
      const bar = this.bars.get(name)
      if (bar) bar.style.width = `${Math.round(frame.bandsRaw[name] * 100)}%`
    }
    for (const field of BAR_FIELDS) {
      const bar = this.bars.get(field)
      if (bar) bar.style.width = `${Math.round(frame[field] * 100)}%`
    }
    for (const field of NUMERIC_FIELDS) {
      const el = this.numbers.get(field)
      if (el) el.textContent = frame[field].toFixed(3)
    }

    // beat dot: brightest right on the beat, fading over the rest of the cycle
    const beatGlow = Math.max(0, 1 - frame.beatPhase * 2.5)
    const lightness = 55 + beatGlow * 40
    this.beatDot.style.background = `hsl(200, 80%, ${lightness}%)`

    const beatInBar = Math.floor(frame.barPhase * 4)
    for (let i = 0; i < 4; i++) {
      this.barSegments[i].style.background = i === beatInBar ? '#ff9d7f' : '#333'
    }
  }
}
