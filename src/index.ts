import type { MainToRenderWorker, PowerTier, RenderWorkerToMain, StateFrame } from './shared/types'
import type { TargetDecl } from './render/conductor/types'
import type { Sidecar } from './shared/sidecar'
import { isSidecar } from './shared/sidecar'
import { AudioEngine } from './audio/AudioEngine'
import { StructureSource } from './audio/StructureSource'

export type { PowerTier } from './shared/types'
export type { Sidecar } from './shared/sidecar'

// Matches the IO page's actual §6 contract (IO_PAGE_CHANGESET.md, and
// src/lib/{viz-bus,player-bus,audio-bus}.ts in stcksmsh.github.io) — not the
// original SINTEZA_VIZ.md draft, which predates real integration constraints
// (getAudioContext/getAnalyser can be null at init time; accent is OKLCH,
// not a CSS string; transport arrives on a window CustomEvent bus, not
// pushed through this API). Kept intentionally this small — see the "don't
// grow the surface" note in the IO page's viz-bus.ts.
export interface VizOpts {
  accent: [number, number, number] // OKLCH [L, C, H] — site's current --accent
  tier: PowerTier
  // Optional: a host with no live AnalyserNode at all (a cross-origin embed
  // like SoundCloud/Bandcamp — nothing to attach a Worklet to) can omit
  // these entirely rather than pass closures that always return null.
  // Position-only mode (a loaded sidecar + setPosition/seek transport
  // events, see StructureSource.synthesize()) drives the visual instead.
  getAudioContext?: () => AudioContext | null
  getAnalyser?: () => AnalyserNode | null
  // Where the compiled feature-worklet/render-worker modules live. Optional
  // — both default to a path relative to this module (`import.meta.url`),
  // which resolves correctly when this package's own dist/index.js is
  // loaded as-is. It does NOT survive every consumer's bundler: if the
  // consumer inlines/re-bundles dist/index.js into its own differently-
  // located chunk (confirmed with Astro/Vite — see stcksmsh.github.io's
  // SintezaBackground.tsx), the relative default resolves against the
  // WRONG final location and 404s. When that happens, resolve the asset
  // through the bundler's own mechanism instead of trusting the default —
  // e.g. Vite's `?url` suffix against this package's exported subpaths:
  //   import renderWorkerUrl from 'sinteza-viz/dist/render-worker.js?url'
  //   import workletUrl from 'sinteza-viz/dist/worklets/feature-worklet.js?url'
  // and pass them here explicitly.
  workletUrl?: string | URL
  renderWorkerUrl?: string | URL
  // Idle-state oscilloscope figure (SINTEZA_VIZ.md §4c's Lissajous beam,
  // shown when nothing is playing) can read as distracting motion against
  // the rest of a page — default true, opt out per-host. Toggle at runtime
  // via VizInstance.setShowIdleBeam.
  showIdleBeam?: boolean
}

export type IsfShaderResult = { ok: true; targets: TargetDecl[] } | { ok: false; message: string }
export interface OscOutStatus {
  connected: boolean
  message?: string
}

export interface VizInstance {
  resize(): void
  destroy(): void
  setAccent(accent: [number, number, number]): void
  setTier(tier: PowerTier): void
  setShowIdleBeam(value: boolean): void
  // Loads a real single-pass ISF shader (see docs/isf-shaders.md for the
  // supported subset) as the screen scene, replacing the built-in Julia
  // substrate. Opt-in and additive — a host that never calls this never
  // triggers it, so every existing integration (including the IO page's)
  // is unaffected by this method merely existing. `onResult` (optional,
  // fire-and-forget if omitted) reports parse/compile success — with the
  // shader's own declared inputs as patch targets, in case a host wants to
  // expose them as UI controls itself — or a specific rejection reason
  // (an unsupported input type, a GLSL compile error) rather than crashing
  // or silently mis-rendering.
  loadIsfShader(source: string, onResult?: (result: IsfShaderResult) => void): void
  // Reverts to the default julia scene.
  clearIsfShader(): void
  // Streams the signal bus out as real OSC (see docs/osc.md) over a
  // WebSocket connection to `wsUrl` (pass null to disconnect) — opt-in and
  // additive, same as loadIsfShader above. Browsers have no raw UDP API, so
  // reaching an actual OSC-speaking tool (TouchDesigner, VCV Rack, Ableton)
  // needs a small local relay on the far end of that WebSocket
  // (scripts/udp-relay.ts ships one) — this method only owns the
  // browser-reachable half. `onStatus` (optional) fires on every
  // connect/disconnect/error over the connection's life, not just once.
  setOscOut(wsUrl: string | null, onStatus?: (status: OscOutStatus) => void): void
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

// Deliberately NOT inlined as a literal `new URL('./render-worker.js', import.meta.url)`
// argument to `new Worker(...)` below — that exact literal-inline pattern is
// what Vite's build specially detects and bundles/rewrites (see
// vite.render-worker.config.ts's comment for why that breaks once this
// package is installed as a dependency elsewhere). Routing it through a
// variable first is what keeps this package's own lib build from doing that
// rewrite, so the reference stays a portable, relative, run-time-resolved
// URL — exactly like workletUrl's default above (audioWorklet.addModule()
// was never subject to this rewrite in the first place; this achieves the
// same portability for the Worker path by opting out of it deliberately).
const RENDER_WORKER_PATH = './render-worker.js'

// See the ResizeObserver callback below for why this needs to be debounced,
// not immediate. Long enough to bridge a mobile browser's address-bar
// collapse/expand animation (typically ~200-300ms), short enough that a
// genuine window resize still feels responsive.
const RESIZE_DEBOUNCE_MS = 150

export function init(canvas: HTMLCanvasElement, opts: VizOpts): VizInstance {
  const engine = new AudioEngine()
  const structureSource = new StructureSource()
  const workletUrl = opts.workletUrl ?? new URL('./worklets/feature-worklet.js', import.meta.url)
  const renderWorkerUrl = opts.renderWorkerUrl ?? new URL(RENDER_WORKER_PATH, import.meta.url)

  let positionSec = 0
  let tier: PowerTier = opts.tier
  let destroyed = false
  let worker: Worker | null = null
  let postToWorker: ((msg: MainToRenderWorker, transfer?: Transferable[]) => void) | null = null
  let resizeDebounceHandle: ReturnType<typeof setTimeout> | null = null
  // At most one loadIsfShader() call is ever "in flight" at a time (a
  // second call before the first's result arrives just replaces which
  // callback gets the eventual isfShaderResult — matches how the worker
  // itself only ever has one active scene, so an interleaved response
  // couldn't be attributed to the "wrong" call anyway).
  let pendingIsfResult: ((result: IsfShaderResult) => void) | null = null
  // Persistent, not one-shot like pendingIsfResult above — a WebSocket
  // connection legitimately fires status multiple times over its life
  // (open, later a drop, a reconnect), all of which a host may want to see.
  let oscOutStatusCallback: ((status: OscOutStatus) => void) | null = null

  const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  const onReducedMotionChange = (e: MediaQueryListEvent) => post({ kind: 'setReducedMotion', value: e.matches })
  const onVisibilityChange = () => post({ kind: 'visibility', hidden: document.hidden })

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
    worker = new Worker(renderWorkerUrl, { type: 'module' })
    postToWorker = post
    worker.onmessage = (e: MessageEvent<RenderWorkerToMain>) => {
      if (e.data.kind === 'error') console.error('[sinteza-viz]', e.data.message)
      if (e.data.kind === 'isfShaderResult') {
        const result: IsfShaderResult = e.data.ok ? { ok: true, targets: e.data.targets } : { ok: false, message: e.data.message }
        if (!result.ok) console.error('[sinteza-viz] loadIsfShader failed:', result.message)
        pendingIsfResult?.(result)
        pendingIsfResult = null
      }
      if (e.data.kind === 'oscOutStatus') {
        oscOutStatusCallback?.({ connected: e.data.connected, message: e.data.message })
      }
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
      // Debounced, not immediate: a resize reallocates the whole render
      // pipeline (every pass's FBOs, including MemoryFieldPass's ping-pong
      // buffers — deleted and recreated from scratch, wiping the
      // accumulated memory-field trail history). A `position:fixed;
      // inset:0` canvas shouldn't need to resize from scrolling at all,
      // but on mobile a scroll gesture that crosses the point where the
      // browser's address bar finishes collapsing/expanding changes the
      // *dynamic* viewport height mid-gesture, and the observer fires
      // repeatedly during that animation — each firing was a full,
      // expensive reallocation AND a visible field reset, exactly the
      // "stutter"/"resets" reported when scrolling past that point.
      // Coalescing rapid-fire observations into one call after the size
      // has actually settled fixes both.
      if (resizeDebounceHandle !== null) clearTimeout(resizeDebounceHandle)
      resizeDebounceHandle = setTimeout(() => {
        resizeDebounceHandle = null
        post({ kind: 'resize', cssWidth: width, cssHeight: height, dpr: window.devicePixelRatio })
      }, RESIZE_DEBOUNCE_MS)
    })
    resizeObserver.observe(canvas)
    reducedMotionQuery.addEventListener('change', onReducedMotionChange)

    // render-worker.ts already handles a 'visibility' message (stop()/start()
    // the render loop) — nothing ever sent it. This package runs 24/7 as a
    // site-wide background, so a backgrounded/minimized tab was rendering at
    // full tilt indefinitely: some browsers throttle rAF in hidden tabs,
    // some don't reliably, and none of that is something to depend on for
    // "must be fast, no room for errors" — an unattended tab left open
    // overnight in the background shouldn't burn GPU/battery the whole time.
    document.addEventListener('visibilitychange', onVisibilityChange)
    if (document.hidden) post({ kind: 'visibility', hidden: true }) // page can start out already backgrounded (e.g. opened in a background tab)
  } else {
    console.error('[sinteza-viz] OffscreenCanvas is not supported in this browser; the visual will not render')
  }

  post({ kind: 'setAccent', rgb: oklchToLinearSrgb(...opts.accent) })
  post({ kind: 'setTier', tier })
  post({ kind: 'setShowIdleBeam', value: opts.showIdleBeam ?? true })

  // opts.getAudioContext()/getAnalyser() are null (or absent entirely) until
  // the shared bus is created on the site's first play click (IO_PAGE_CHANGESET.md
  // §3) — this package mounts well before that's guaranteed to exist, so
  // poll rather than assume it's there at init time. Attaches downstream of
  // the AnalyserNode itself (not a separate "source" node — the site's
  // contract doesn't expose one) — an AnalyserNode taps the signal without
  // altering it, so it's an equally valid attach point for our own Worklet.
  // A host that never provides one at all (SoundCloud/Bandcamp — genuinely
  // no live signal to tap) just polls forever harmlessly; startSynthLoopIfNeeded
  // below is what actually drives the visual for those tracks.
  let audioPollHandle: ReturnType<typeof setInterval> | null = null
  function tryAttachAudio(): void {
    if (tier === 'idle-only' || engine.attached) return
    const ctx = opts.getAudioContext?.()
    const analyser = opts.getAnalyser?.()
    if (!ctx || !analyser) return
    // Was previously fire-and-forget with the poll-clearing/synth-stop code
    // running unconditionally right after the call, regardless of whether
    // attach() (async — addModule() fetches+compiles the worklet script)
    // actually succeeded. A transient failure (script fetch hiccup, ctx
    // closed mid-attach) meant the poll was already stopped by then, so
    // there was no live audio for the rest of the session and no fallback
    // resumed either — permanent, silent, and unattended-24/7-fatal for
    // that one page load. Only stop polling/fall back once attach()
    // actually resolves; on failure the still-running poll just retries.
    void engine
      .attach(ctx, workletUrl, analyser)
      .then(() => {
        stopSynthLoop() // live audio just proved available — it's richer and takes over for good
        if (audioPollHandle !== null) {
          clearInterval(audioPollHandle)
          audioPollHandle = null
        }
      })
      .catch((err: unknown) => {
        console.error('[sinteza-viz] failed to attach audio worklet, will retry:', err)
      })
  }
  tryAttachAudio()
  if (!engine.attached && tier !== 'idle-only') {
    audioPollHandle = setInterval(tryAttachAudio, AUDIO_POLL_INTERVAL_MS)
  }

  // Position-only mode (SINTEZA_VIZ.md §5): drives StateFrames purely from
  // a loaded sidecar + the live position clock, for tracks with no
  // AnalyserNode to attach to at all. Runs only while live audio hasn't
  // (yet) attached — the moment it does, tryAttachAudio's stopSynthLoop()
  // call above hands off to the richer live path for good, never both at
  // once.
  let synthRafHandle: number | null = null
  function synthLoopTick(): void {
    if (!structureSource.active || engine.attached || tier === 'idle-only') {
      synthRafHandle = null
      return
    }
    post({ kind: 'state', frame: structureSource.synthesize(positionSec) })
    synthRafHandle = requestAnimationFrame(synthLoopTick)
  }
  function startSynthLoopIfNeeded(): void {
    if (synthRafHandle !== null || engine.attached || tier === 'idle-only' || !structureSource.active) return
    synthRafHandle = requestAnimationFrame(synthLoopTick)
  }
  function stopSynthLoop(): void {
    if (synthRafHandle !== null) cancelAnimationFrame(synthRafHandle)
    synthRafHandle = null
  }

  async function loadSidecar(url: string): Promise<void> {
    // Callers do `void loadSidecar(...)` (onTransport can't await a DOM
    // event handler) — an uncaught rejection here would be a silent,
    // console-only unhandled-rejection with no visible symptom beyond "this
    // track just never got sidecar-driven structure". A network blip or a
    // malformed/missing file on one track must not do anything worse than
    // that: log and fall back to the live/idle path, never throw past this
    // function.
    let json: unknown
    try {
      const res = await fetch(url)
      if (!res.ok) {
        console.error(`[sinteza-viz] failed to fetch sidecar ${url}: HTTP ${res.status}`)
        return
      }
      json = await res.json()
    } catch (err) {
      console.error(`[sinteza-viz] failed to fetch/parse sidecar ${url}:`, err)
      return
    }
    if (!isSidecar(json)) {
      console.error(`[sinteza-viz] ${url} is not a recognised sidecar (schema mismatch)`)
      return
    }
    structureSource.load(json as Sidecar)
    structureSource.resyncTo(positionSec)
    startSynthLoopIfNeeded()
    // SINTEZA_SIGNAL_BUS.md §4b(1): once a sidecar is active, StructureSource
    // .fuse() already overwrites buildProgress/tension/structural events from
    // the sidecar timeline wholesale — the live build/drop/break detectors'
    // output would just be discarded downstream. Stop running them entirely
    // rather than computing and throwing it away every hop (also removes the
    // live DropDetector's known false-positive/miss risk for own tracks,
    // since the sidecar's offline analysis is authoritative for structure).
    engine.setDetectorsEnabled(false)
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
        // Re-enabled unconditionally; loadSidecar() below will disable again
        // if the new track has a sidecar of its own.
        engine.setDetectorsEnabled(true)
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

    setShowIdleBeam(value) {
      post({ kind: 'setShowIdleBeam', value })
    },

    loadIsfShader(source, onResult) {
      pendingIsfResult = onResult ?? null
      post({ kind: 'setIsfShader', source })
    },

    clearIsfShader() {
      pendingIsfResult = null
      post({ kind: 'setIsfShader', source: null })
    },

    setOscOut(wsUrl, onStatus) {
      oscOutStatusCallback = wsUrl === null ? null : (onStatus ?? null)
      post({ kind: 'setOscOut', wsUrl })
    },

    setTier(next) {
      if (tier === next) return
      tier = next
      post({ kind: 'setTier', tier })
      if (tier === 'idle-only') {
        engine.detach()
        stopSynthLoop()
        if (audioPollHandle !== null) {
          clearInterval(audioPollHandle)
          audioPollHandle = null
        }
      } else if (!engine.attached) {
        tryAttachAudio()
        if (!engine.attached && audioPollHandle === null) {
          audioPollHandle = setInterval(tryAttachAudio, AUDIO_POLL_INTERVAL_MS)
        }
        startSynthLoopIfNeeded()
      }
    },

    destroy() {
      if (destroyed) return
      destroyed = true
      window.removeEventListener(TRANSPORT_EVENT, onTransport)
      if (audioPollHandle !== null) clearInterval(audioPollHandle)
      if (resizeDebounceHandle !== null) clearTimeout(resizeDebounceHandle)
      stopSynthLoop()
      engine.detach()
      resizeObserver?.disconnect()
      reducedMotionQuery.removeEventListener('change', onReducedMotionChange)
      document.removeEventListener('visibilitychange', onVisibilityChange)
      worker?.terminate()
      worker = null
      postToWorker = null
      // Defense-in-depth, not currently load-bearing: terminate() above
      // already makes it impossible for a late isfShaderResult/oscOutStatus
      // message to arrive and invoke these, but clearing them anyway means
      // that stays true even if destroy() is ever changed to something
      // less final (e.g. a "pause" mode that keeps the worker alive).
      pendingIsfResult = null
      oscOutStatusCallback = null
    },
  }
}
