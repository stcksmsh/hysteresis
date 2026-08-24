import type { MainToRenderWorker, RenderWorkerToMain, StateFrame } from '../../src/shared/types'
import type { SignalBus } from '../../src/render/conductor/types'
import type { DropDetectorDebug } from '../../src/audio/worklet/brain/drop-detector'
import type { PatchGraph } from '../../src/render/conductor/patchgraph/types'
import { StructureSource } from '../../src/audio/StructureSource'
import { isSidecar, type Sidecar } from '../../src/shared/sidecar'
import { screenGraph } from '../../src/render/conductor/patchgraph/configs/screen-graph'
import { emptyFixtureDocument, addFixture, fixtureTargetCatalog, type FixtureDocument } from '../../src/render/conductor/patchgraph/fixture-document'
import { seedNodes } from '../patchbay-editor/src/seed-graph'
import { toPatchGraph, makeDefaultDraft } from '../patchbay-editor/src/graph-draft'
import type { RoutableSignalName } from '../../src/render/conductor/types'
import { drawDebugOverlay } from './overlay-debug'
import { drawFixtureOverlay } from './overlay-fixtures'

// The offline video-render harness (AGENTS.md's "render-video" tool):
// exposes window.__render* functions a Puppeteer driver (scripts/
// render-video.ts) calls via page.evaluate(). No UI, no HMR-dependent
// behavior — this page's only job is orchestration. Reuses the exact same
// render-worker.ts the shipped package uses (imported by relative path,
// same pattern tools/patchbay-editor/src/runtime-bridge.ts already
// established) so the rendered output is the real production pipeline, not
// a mock of it.
const RENDER_WORKER_URL = new URL('../../src/render/worker/render-worker.ts', import.meta.url)

let worker: Worker | null = null
let canvas: OffscreenCanvas | null = null
let structureSource: StructureSource | null = null
let outputCanvas: OffscreenCanvas | null = null
let outputCtx: OffscreenCanvasRenderingContext2D | null = null
let fixtureDoc: FixtureDocument | null = null

// Layout (SINTEZA_UNDERSTANDING... no — AGENTS.md's render-video session):
// left debug panel / center visualizer / right fixture panel, both side
// panels drawn at reduced alpha so the center stays the dominant visual —
// the user's explicit ask.
const SIDE_FRACTION = 0.18
const OVERLAY_ALPHA = 0.55

function post(msg: MainToRenderWorker, transfer?: Transferable[]): void {
  if (!worker) throw new Error('worker not initialized — call __init first')
  if (transfer) worker.postMessage(msg, transfer)
  else worker.postMessage(msg)
}

function waitFor<T extends RenderWorkerToMain['kind']>(kind: T): Promise<Extract<RenderWorkerToMain, { kind: T }>> {
  return new Promise((resolve) => {
    const handler = (e: MessageEvent<RenderWorkerToMain>) => {
      if (e.data.kind === kind) {
        worker?.removeEventListener('message', handler)
        resolve(e.data as Extract<RenderWorkerToMain, { kind: T }>)
      }
    }
    worker?.addEventListener('message', handler)
  })
}

async function init(renderWidth: number, renderHeight: number, outWidth: number, outHeight: number): Promise<void> {
  worker = new Worker(RENDER_WORKER_URL, { type: 'module' })
  worker.onmessage = (e) => {
    if (e.data.kind === 'error') console.error('[render-video worker]', e.data.message)
  }
  // The visualizer's own canvas is rendered at renderWidth/renderHeight
  // (the center column's real pixel size) — separate from outWidth/
  // outHeight, the FINAL composited video frame including both side
  // panels. No DOM <canvas> needed anywhere: OffscreenCanvas is itself
  // transferable via postMessage.
  canvas = new OffscreenCanvas(renderWidth, renderHeight)
  post({ kind: 'init', canvas, dpr: 1, reducedMotion: false, startLoop: false }, [canvas])

  outputCanvas = new OffscreenCanvas(outWidth, outHeight)
  const ctx = outputCanvas.getContext('2d')
  if (!ctx) throw new Error('2D context unavailable on output canvas')
  outputCtx = ctx
}

// Takes the already-parsed sidecar object directly (Puppeteer's
// page.evaluate() structured-clones a plain JS argument straight into the
// page) rather than fetching a URL — sidesteps needing to serve the
// sidecar file over the dev server at all, which would otherwise need
// either copying it under tools/render-video/'s root or a second CORS-
// enabled static server just for this one file.
async function loadSidecar(raw: unknown): Promise<void> {
  if (!isSidecar(raw)) throw new Error('not a valid sidecar')
  structureSource = new StructureSource()
  structureSource.load(raw as Sidecar)
}

async function loadIsfShader(source: string): Promise<{ ok: boolean; message?: string }> {
  const donePromise = waitFor('isfShaderResult')
  post({ kind: 'setIsfShader', source })
  const result = await donePromise
  return result.ok ? { ok: true } : { ok: false, message: result.message }
}

export interface HysteresisRoute {
  signal: string
  target: string // e.g. "isf.drive"
}

// Adds one `signal:<signalName> -> target:isf.<isfInputName>` route per
// entry in `routes`, on TOP OF the real default screen graph, not
// replacing it: the memory-field/bloom pipeline's own required routes
// (buildWindup/tension/energy/...) still need to be live under a loaded
// ISF scene too (docs/isf-shaders.md: "a loaded shader still gets the
// memory-field/bloom pipeline applied on top"). Plural (not a single
// hardcoded signal->drive pair) so a shader that declares several
// hysteresisSignal inputs — this tool's whole point is testing that a
// shader can be driven by many signals at once, not just one — gets every
// one of them wired, not just the first.
function setScreenGraphWithHysteresisRoutes(routes: HysteresisRoute[]): void {
  const extraNodes = routes.flatMap(({ signal, target }) => {
    const sig = makeDefaultDraft('signal')
    sig.signal = signal as RoutableSignalName
    const tgt = makeDefaultDraft('target')
    tgt.targetId = target
    tgt.inputs = [sig.id]
    return [sig, tgt]
  })
  const extra = toPatchGraph('render-video-extra', extraNodes).nodes
  const graph: PatchGraph = { id: 'render-video-screen', nodes: [...screenGraph.nodes, ...extra] }
  post({ kind: 'debugSetScreenGraph', graph })
}

// Seeds the same 4 demo fixture types (Demo Dimmer/RGB/Servo/Laser) the
// patchbay editor already seeds (tools/patchbay-editor/src/App.tsx), wired
// to rotating real bus signals via seed-graph.ts's seedNodes() — reused
// directly, not reimplemented, per the plan's own "reuse the wiring logic,
// only the draw routines needed reimplementing" design.
function setupDemoFixtures(): FixtureDocument {
  let doc = emptyFixtureDocument()
  doc = addFixture(doc, 'Demo Dimmer', 'dimmer')
  doc = addFixture(doc, 'Demo RGB', 'rgb')
  doc = addFixture(doc, 'Demo Servo', 'servo')
  doc = addFixture(doc, 'Demo Laser', 'mover')
  fixtureDoc = doc
  post({ kind: 'setFixtureDocument', doc })
  const catalog = fixtureTargetCatalog(doc)
  const graph = toPatchGraph('render-video-fixtures', seedNodes(catalog))
  post({ kind: 'setFixtureGraph', graph })
  return doc
}

interface RenderedFrameResult {
  jpeg: string // base64 data URL
}

// Real, precise readiness signal for the render-video driver's crash-
// recovery path (scripts/render-video.ts): distinct from window.__ready
// (which only means "this harness script executed at all" — true again
// moments after ANY page reload, even one that just wiped every other
// piece of state below). A driver that only checked __ready would see
// "ready" on a freshly-reloaded, otherwise-uninitialized page and keep
// calling __renderFrame into a null structureSource — exactly the failure
// this session's real full-render attempt hit (frame 6748: "no sidecar
// loaded" on every retry, because nothing re-called __init/__loadSidecar
// after Chrome silently reloaded the page mid-run).
function renderReady(): boolean {
  return structureSource !== null
}

// JPEG, not PNG: measured directly (AGENTS.md's own note on this) that
// PNG's DEFLATE compression was the dominant per-frame cost, not the GL
// rendering itself — live rendering hits 45-60fps with neither an encode
// nor a base64/CDP round-trip step at all, which is exactly the gap
// between it and this offline path. JPEG's DCT encode is far cheaper, and
// since the frame sequence gets muxed straight into lossy H.264 anyway, a
// JPEG intermediate costs no additional real quality.
const JPEG_QUALITY = 0.92

async function renderFrame(positionSec: number, dt: number, showDebugOverlay: boolean, showFixtureOverlay: boolean): Promise<RenderedFrameResult> {
  if (!structureSource) throw new Error('no sidecar loaded — call __loadSidecar first')
  if (!canvas || !outputCanvas || !outputCtx) throw new Error('__init not called')

  const frame: StateFrame = structureSource.synthesize(positionSec)
  const donePromise = waitFor('frameRendered')
  post({ kind: 'renderFrame', frame, dt })
  const result = await donePromise

  compositeFrame(result.bitmap, result.bus, result.dropDebug, result.fixtureValues, showDebugOverlay, showFixtureOverlay)
  result.bitmap.close()

  const blob = await outputCanvas.convertToBlob({ type: 'image/jpeg', quality: JPEG_QUALITY })
  const buf = await blob.arrayBuffer()
  const base64 = arrayBufferToBase64(buf)
  return { jpeg: `data:image/jpeg;base64,${base64}` }
}

function compositeFrame(
  bitmap: ImageBitmap,
  bus: SignalBus,
  dropDebug: DropDetectorDebug | null,
  fixtureValues: Record<string, number>,
  showDebugOverlay: boolean,
  showFixtureOverlay: boolean,
): void {
  if (!outputCtx || !outputCanvas) return
  const w = outputCanvas.width
  const h = outputCanvas.height
  const sideWidth = Math.round(w * SIDE_FRACTION)
  const centerWidth = w - sideWidth * 2

  outputCtx.fillStyle = '#05050a'
  outputCtx.fillRect(0, 0, w, h)
  outputCtx.drawImage(bitmap, sideWidth, 0, centerWidth, h)

  if (showDebugOverlay) {
    drawDebugOverlay(outputCtx, 0, 0, sideWidth, h, bus, dropDebug, OVERLAY_ALPHA)
  }
  if (showFixtureOverlay && fixtureDoc) {
    drawFixtureOverlay(outputCtx, w - sideWidth, 0, sideWidth, h, fixtureDoc, fixtureValues, OVERLAY_ALPHA)
  }
}

function arrayBufferToBase64(buf: ArrayBuffer): string {
  let binary = ''
  const bytes = new Uint8Array(buf)
  const chunkSize = 0x8000
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize))
  }
  return btoa(binary)
}

declare global {
  interface Window {
    __init: typeof init
    __loadSidecar: typeof loadSidecar
    __loadIsfShader: typeof loadIsfShader
    __setScreenGraphWithHysteresisRoutes: typeof setScreenGraphWithHysteresisRoutes
    __setupDemoFixtures: typeof setupDemoFixtures
    __renderFrame: typeof renderFrame
    __renderReady: typeof renderReady
    __ready: boolean
  }
}

window.__init = init
window.__loadSidecar = loadSidecar
window.__loadIsfShader = loadIsfShader
window.__setScreenGraphWithHysteresisRoutes = setScreenGraphWithHysteresisRoutes
window.__setupDemoFixtures = setupDemoFixtures
window.__renderReady = renderReady
window.__renderFrame = renderFrame
window.__ready = true
