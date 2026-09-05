import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { RuntimeBridge, type PlaybackState } from './runtime-bridge'
import { TransportBar } from './TransportBar'
import { NavBar } from './NavBar'
import { GraphScreen } from './screens/GraphScreen'
import { ShaderScreen } from './shaders/ShaderScreen'
import { OutputScreen } from './screens/OutputScreen'
import { DiagnosticsScreen, type DropLogEntry } from './screens/DiagnosticsScreen'
import type { Screen } from './screens'
import { IconButton } from './ui/IconButton'
import { IconExpand, IconClose } from './ui/icons'
import { serializeGraphAndFixtures, saveToFile } from './serialize-config'
import { toPatchGraph, fromPatchGraphNode, type DraftNode } from './graph-draft'
import { seedNodes } from './seed-graph'
import { screenGraph } from '../../../src/render/conductor/patchgraph/configs/screen-graph'
import { SCREEN_TARGETS } from '../../../src/render/conductor/outputs/screen-targets'
import { validatePatchGraph } from '../../../src/render/conductor/patchgraph/validate'
import { pruneGraphToTargets } from '../../../src/render/conductor/patchgraph/prune'
import { addFixture, fixtureTargetCatalog, emptyFixtureDocument, type FixtureDocument } from '../../../src/render/conductor/patchgraph/fixture-document'
import type { SignalBus } from '../../../src/render/conductor/types'
import type { DropDetectorDebug } from '../../../src/audio/worklet/brain/drop-detector'
import type { PatchTargetDecl } from '../../../src/render/conductor/patchgraph/types'

// Keyed by canvas element, not component instance: canvas.transferControlToOffscreen()
// is a genuine one-shot browser API (confirmed: attempting it twice on the
// same canvas throws "Cannot transfer control from a canvas for more than
// one time"), so a Vite Fast-Refresh remount during development — which
// keeps the same DOM canvas node but re-runs this hook — MUST reuse the
// existing bridge instead of constructing a new one. Only callbacks get
// rewired (setCallbacks) so the reused bridge still calls into the current
// render's state setters. This is a dev tool that lives entirely within
// one page lifetime, so never disposing here (only the browser tearing
// down the page ever really ends it) is the right trade against fighting
// this exact one-shot API on every edit-triggered remount.
const bridgesByCanvas = new WeakMap<HTMLCanvasElement, RuntimeBridge>()

function useRuntimeBridge(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  onSignalBus: (bus: SignalBus, dropDebug: DropDetectorDebug | null, fixtureValues: Record<string, number>) => void,
  onIsfResult: (result: { ok: true; targets: PatchTargetDecl[] } | { ok: false; message: string }) => void,
) {
  const bridgeRef = useRef<RuntimeBridge | null>(null)
  const [fps, setFps] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [patchbayError, setPatchbayError] = useState<string | null>(null)
  // "No error banner" only proves a rejection didn't happen, not that an
  // edit was actually applied — this makes the round trip itself visible:
  // every debugSetScreenGraph gets an ack either way (see render-worker.ts's
  // handler), so a counter that keeps incrementing is direct proof the
  // hot-swap loop is alive end to end.
  const [patchbayAckCount, setPatchbayAckCount] = useState(0)
  const [playback, setPlayback] = useState<PlaybackState>({ currentTime: 0, duration: NaN, playing: false })
  const [fixtureOutStatus, setFixtureOutStatus] = useState<{ connected: boolean; message?: string }>({ connected: false })
  const [oscInStatus, setOscInStatus] = useState<{ connected: boolean; message?: string }>({ connected: false })

  useEffect(() => {
    if (!canvasRef.current) return
    const callbacks = {
      onStats: (v: number) => setFps(v),
      onError: (m: string) => setError(m),
      onSignalBus,
      onPatchbayResult: (r: { ok: true } | { ok: false; message: string }) => {
        setPatchbayError(r.ok ? null : r.message)
        setPatchbayAckCount((n) => n + 1)
      },
      onPlayback: (s: PlaybackState) => setPlayback(s),
      onIsfResult,
      onFixtureOutStatus: (s: { connected: boolean; message?: string }) => setFixtureOutStatus(s),
      onOscInStatus: (s: { connected: boolean; message?: string }) => setOscInStatus(s),
    }
    let bridge = bridgesByCanvas.get(canvasRef.current)
    if (bridge) {
      bridge.setCallbacks(callbacks)
    } else {
      bridge = new RuntimeBridge(canvasRef.current, callbacks)
      bridge.setSignalBusStream(true)
      bridgesByCanvas.set(canvasRef.current, bridge)
    }
    bridgeRef.current = bridge
    // eslint-disable-next-line react-hooks/exhaustive-deps -- bridge lifecycle is intentionally tied to mount only
  }, [])

  return { bridgeRef, fps, error, patchbayError, patchbayAckCount, playback, fixtureOutStatus, oscInStatus }
}

// Same rising-edge rule ScreenParamAssembler uses to reconstruct "a drop
// just happened" from the continuous dropImpulse pulse (see
// screen-composites.ts's DROP_EDGE_EPS) — mirrored here, not imported,
// since this hook's job is independent confirmation: if the real drop
// detector is firing too eagerly on quiet/ambient material, this needs to
// show it happening from the bus itself, not trust the same code path
// that's under suspicion.
const DROP_EDGE_EPS = 0.05
const DROP_LOG_MAX = 12

function useDropLog(bus: SignalBus | null) {
  const [log, setLog] = useState<DropLogEntry[]>([])
  const prevImpulse = useRef(0)
  const startedAt = useRef(performance.now())

  useEffect(() => {
    if (!bus) return
    if (bus.dropImpulse > prevImpulse.current + DROP_EDGE_EPS) {
      setLog((prev) => [{ atMs: performance.now() - startedAt.current, strength: bus.dropImpulse }, ...prev].slice(0, DROP_LOG_MAX))
    }
    prevImpulse.current = bus.dropImpulse
  }, [bus])

  return log
}

export function App() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  // 'demo' = canvas fills the viewport, no chrome — for actually watching
  // it. 'edit' = canvas shrinks to a small corner preview, the active
  // screen takes the rest — for wiring/authoring. Never both at full size
  // at once (a squeezed-sidebar layout was the thing an earlier pass
  // already replaced once).
  const [viewMode, setViewMode] = useState<'demo' | 'edit'>('edit')
  const [screen, setScreen] = useState<Screen>('graph')
  const [bus, setBus] = useState<SignalBus | null>(null)
  const [busMessageCount, setBusMessageCount] = useState(0)
  const [dropDebug, setDropDebug] = useState<DropDetectorDebug | null>(null)
  const handleSignalBus = useCallback((b: SignalBus, dbg: DropDetectorDebug | null, fixtureValues: Record<string, number>) => {
    setBus(b)
    setBusMessageCount((n) => n + 1)
    setDropDebug(dbg)
    setResolvedValues(fixtureValues)
  }, [])
  // ISF/.hyst import: the loaded shader's own declared inputs, as real
  // patch targets — merged into mergedCatalog below so the graph canvas's
  // target dropdown offers them exactly like a screen/fixture target.
  // `pendingIsfFileName` bridges the load call to the async onIsfResult
  // callback, which carries no filename of its own.
  const [isfStatus, setIsfStatus] = useState<
    { state: 'empty' } | { state: 'loaded'; fileName: string; targets: PatchTargetDecl[] } | { state: 'error'; fileName: string; message: string }
  >({ state: 'empty' })
  const pendingIsfFileName = useRef('shader.fs')
  const isfTargets = isfStatus.state === 'loaded' ? isfStatus.targets : []
  const handleIsfResult = useCallback((r: { ok: true; targets: PatchTargetDecl[] } | { ok: false; message: string }) => {
    setIsfStatus(r.ok ? { state: 'loaded', fileName: pendingIsfFileName.current, targets: r.targets } : { state: 'error', fileName: pendingIsfFileName.current, message: r.message })
  }, [])

  const { bridgeRef, fps, error, patchbayError, patchbayAckCount, playback, fixtureOutStatus, oscInStatus } = useRuntimeBridge(canvasRef, handleSignalBus, handleIsfResult)
  const dropLog = useDropLog(bus)

  function handleIsfApply(source: string, fileName: string) {
    pendingIsfFileName.current = fileName
    bridgeRef.current?.setIsfShader(source)
  }
  function handleIsfClear() {
    setIsfStatus({ state: 'empty' })
    bridgeRef.current?.setIsfShader(null)
  }

  const [fixtureDoc, setFixtureDoc] = useState<FixtureDocument>(() => {
    let doc = emptyFixtureDocument()
    doc = addFixture(doc, 'Demo Dimmer', 'dimmer')
    doc = addFixture(doc, 'Demo RGB', 'rgb')
    doc = addFixture(doc, 'Demo Servo', 'servo')
    doc = addFixture(doc, 'Demo Laser', 'mover')
    return doc
  })
  const targetCatalog = useMemo(() => fixtureTargetCatalog(fixtureDoc), [fixtureDoc])
  // Screen targets + every fixture channel, one list — this is what makes
  // "one signal drives both a screen effect and a servo" a real option in
  // the canvas: a target node can point at either, side by side, in the
  // same graph.
  const mergedCatalog = useMemo(() => [...SCREEN_TARGETS, ...isfTargets, ...targetCatalog], [isfTargets, targetCatalog])
  // isf.* targets are screen-side (they drive the loaded shader's own
  // uniforms via ScreenOutput, same as SCREEN_TARGETS) — included here so
  // pruneGraphToTargets keeps routes into them when carving out the slice
  // sent to the worker via setScreenGraph below.
  const screenTargetIds = useMemo(() => new Set([...SCREEN_TARGETS.map((t) => t.id), ...isfTargets.map((t) => t.id)]), [isfTargets])
  const fixtureTargetIds = useMemo(() => new Set(targetCatalog.map((t) => t.id)), [targetCatalog])

  // Seeded once from two independent sources: the production default screen
  // graph (screenGraph, converted node-for-node back into drafts) and the
  // fixture demo chains (seedNodes) — both live in ONE graph from the start,
  // not stitched together later. `fixtureTargetCatalog(fixtureDoc)` here is
  // a pure derivation (safe to call again) — unlike `fixtureDoc` itself,
  // which is already resolved above by the time this initializer runs.
  const [graphNodes, setGraphNodes] = useState<DraftNode[]>(() => [
    ...screenGraph.nodes.map(fromPatchGraphNode),
    ...seedNodes(fixtureTargetCatalog(fixtureDoc)),
  ])

  const graph = useMemo(() => toPatchGraph('editor', graphNodes), [graphNodes])
  const graphErrors = useMemo(() => validatePatchGraph(graph, mergedCatalog).filter((i) => i.severity === 'error'), [graph, mergedCatalog])

  // The worker only ever sees the screen-relevant slice of the unified
  // graph (see prune.ts) — it has no idea a fixture half exists.
  useEffect(() => {
    if (graphErrors.length > 0) return // don't even try — the worker's own construction-time validation would just reject it anyway
    bridgeRef.current?.setScreenGraph(pruneGraphToTargets(graph, screenTargetIds))
  }, [graph, graphErrors.length, screenTargetIds, bridgeRef])

  // Real production wiring, not a local copy: the worker-resident
  // FixtureOutput/PatchGraphEvaluator evaluates the fixture graph — this
  // editor dogfoods the exact same setFixtureDocument/setFixtureGraph
  // messages VizInstance's public API sends. `resolvedValues` (read by
  // DmxOutPanel/FixtureVisuals) comes back over the signalBus debug
  // stream's fixtureValues field, set directly from handleSignalBus.
  useEffect(() => {
    bridgeRef.current?.setFixtureDocument(fixtureDoc)
  }, [fixtureDoc, bridgeRef])

  useEffect(() => {
    if (graphErrors.length > 0) return
    bridgeRef.current?.setFixtureGraph(pruneGraphToTargets(graph, fixtureTargetIds))
  }, [graph, graphErrors.length, fixtureTargetIds, bridgeRef])
  const [resolvedValues, setResolvedValues] = useState<Record<string, number>>({})

  // Removing a fixture can leave graph target-nodes pointing at a channel
  // that no longer exists — harmless (validatePatchGraph flags it, the
  // evaluator just won't produce a value for it), not auto-cleaned-up here
  // so a fixture rename/re-add can still reconnect to the same wiring.
  function handleFixtureDocChange(next: FixtureDocument) {
    setFixtureDoc(next)
  }

  async function onFileChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) await bridgeRef.current?.loadFile(file)
  }

  useEffect(() => {
    if (viewMode !== 'demo') return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setViewMode('edit')
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [viewMode])

  const [saveStatus, setSaveStatus] = useState<string | null>(null)

  async function handleSaveGraph() {
    const source = serializeGraphAndFixtures(graph, fixtureDoc)
    const result = await saveToFile('patch-graph.ts', source)
    setSaveStatus(result.ok ? `Saved to ${result.path}` : `Save failed: ${result.message}`)
  }

  const handleTogglePlay = useCallback(() => bridgeRef.current?.togglePlayback(), [bridgeRef])
  const handleSeek = useCallback((sec: number) => bridgeRef.current?.seek(sec), [bridgeRef])
  const handleMidiCcChange = useCallback((key: string, value: number) => bridgeRef.current?.setMidiCc(key, value), [bridgeRef])

  // Rendered exactly once, at exactly one place in the tree, regardless of
  // viewMode or which screen is active — canvas.transferControlToOffscreen()
  // is a genuine one-shot browser API (see the bridgesByCanvas comment
  // above), so this element's identity must never change. Its size/position
  // is purely a CSS class swap (fixed-position full-viewport vs. a small
  // fixed corner box).
  const canvasBlock = (
    <div className={`canvas-block ${viewMode === 'demo' ? 'canvas-block-demo' : 'canvas-block-corner'}`}>
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
      <IconButton
        className="canvas-mode-toggle"
        icon={viewMode === 'demo' ? <IconClose size={14} /> : <IconExpand size={14} />}
        label={viewMode === 'demo' ? 'Back to editing (Esc)' : 'Fullscreen demo'}
        onClick={() => setViewMode(viewMode === 'demo' ? 'edit' : 'demo')}
      />
      <span className="status-pill canvas-fps-pill">{fps > 0 ? `${fps.toFixed(0)} fps` : '—'}</span>
    </div>
  )

  const transport = <TransportBar playback={playback} onTogglePlay={handleTogglePlay} onSeek={handleSeek} onFileChosen={onFileChosen} variant={viewMode === 'demo' ? 'demo' : 'corner'} />

  return (
    <div className={`app-root app-root-${viewMode}`}>
      {canvasBlock}
      {transport}

      {viewMode === 'edit' && (
        <>
          <header className="app-header">
            <strong className="app-title">Patchbay</strong>
            <NavBar active={screen} onSelect={setScreen} />
            {saveStatus && <span className="status-pill">{saveStatus}</span>}
            <span className="status-pill" style={{ marginLeft: 'auto' }}>
              signalBus msgs: {busMessageCount} · acks: {patchbayAckCount}
            </span>
          </header>

          {error && <div className="banner banner-error">Render worker error: {error}</div>}
          {patchbayError && <div className="banner banner-warn">Config rejected (previous graph still running): {patchbayError}</div>}

          <div className="screen-outlet">
            {screen === 'graph' && <GraphScreen nodes={graphNodes} onChange={setGraphNodes} targets={mergedCatalog} onSave={handleSaveGraph} />}
            {screen === 'shaders' && <ShaderScreen onApply={handleIsfApply} onClear={handleIsfClear} liveStatus={isfStatus} />}
            {screen === 'output' && (
              <OutputScreen
                fixtureDoc={fixtureDoc}
                onFixtureDocChange={handleFixtureDocChange}
                resolvedValues={resolvedValues}
                dmxProps={{ status: fixtureOutStatus, onConnect: (config) => bridgeRef.current?.setFixtureOut(config), onDisconnect: () => bridgeRef.current?.setFixtureOut(null) }}
                oscInProps={{ status: oscInStatus, onConnect: (url) => bridgeRef.current?.setOscIn(url), onDisconnect: () => bridgeRef.current?.setOscIn(null) }}
                onMidiCcChange={handleMidiCcChange}
              />
            )}
            {screen === 'diagnostics' && (
              <DiagnosticsScreen bus={bus} graphErrorCount={graphErrors.length} routedFixtureChannelCount={Object.keys(resolvedValues).length} dropDebug={dropDebug} dropLog={dropLog} />
            )}
          </div>
        </>
      )}
    </div>
  )
}
