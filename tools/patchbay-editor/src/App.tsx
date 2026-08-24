import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { RuntimeBridge, type PlaybackState } from './runtime-bridge'
import { TransportBar } from './TransportBar'
import { FixtureManager } from './FixtureManager'
import { PatchGraphCanvas } from './PatchGraphCanvas'
import { FixtureVisuals } from './FixtureVisuals'
import { SectionCard } from './SectionCard'
import { serializeGraphAndFixtures, saveToFile } from './serialize-config'
import { toPatchGraph, fromPatchGraphNode, type DraftNode } from './graph-draft'
import { seedNodes } from './seed-graph'
import { screenGraph } from '../../../src/render/conductor/patchgraph/configs/screen-graph'
import { SCREEN_TARGETS } from '../../../src/render/conductor/outputs/screen-targets'
import { validatePatchGraph } from '../../../src/render/conductor/patchgraph/validate'
import { PatchGraphEvaluator } from '../../../src/render/conductor/patchgraph/PatchGraphEvaluator'
import { pruneGraphToTargets } from '../../../src/render/conductor/patchgraph/prune'
import { addFixture, fixtureTargetCatalog, emptyFixtureDocument, type FixtureDocument } from '../../../src/render/conductor/patchgraph/fixture-document'
import { fixtureTargetId } from '../../../src/render/conductor/patchgraph/fixture-types'
import type { SignalBus } from '../../../src/render/conductor/types'
import type { DropDetectorDebug } from '../../../src/audio/worklet/brain/drop-detector'
import type { PatchTargetDecl } from '../../../src/render/conductor/patchgraph/types'
import { IsfPanel } from './IsfPanel'
import { DmxOutPanel } from './DmxOutPanel'
import { MidiPanel } from './MidiPanel'

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
  onSignalBus: (bus: SignalBus, dropDebug: DropDetectorDebug | null) => void,
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

  return { bridgeRef, fps, error, patchbayError, patchbayAckCount, playback }
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

interface DropLogEntry {
  atMs: number // performance.now() when observed — wall-clock since page load, not track position (this tool doesn't track playback position)
  strength: number
}

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
  // 'demo' = canvas fills the viewport, no panels — for actually watching
  // it. 'edit' = canvas shrinks to a small corner preview, panels take the
  // rest — for wiring the graph. Never both at full size at once (that
  // squeezed-sidebar layout was the thing an earlier pass already replaced
  // once, see AGENTS.md's layout-overhaul note — this is the same lesson
  // applied one level up: a *tool-wide* mode split, not just a canvas-size
  // knob within one cramped layout).
  const [viewMode, setViewMode] = useState<'demo' | 'edit'>('edit')
  const [showDebug, setShowDebug] = useState(false)
  const [bus, setBus] = useState<SignalBus | null>(null)
  const [busMessageCount, setBusMessageCount] = useState(0)
  const [dropDebug, setDropDebug] = useState<DropDetectorDebug | null>(null)
  const handleSignalBus = useCallback((b: SignalBus, dbg: DropDetectorDebug | null) => {
    setBus(b)
    setBusMessageCount((n) => n + 1)
    setDropDebug(dbg)
  }, [])
  // ISF import (master-prompt.md §6): the loaded shader's own declared
  // inputs, as real patch targets — merged into mergedCatalog below so the
  // graph canvas's target dropdown offers them exactly like a screen/
  // fixture target. `pendingIsfFileName` bridges the load call to the
  // async onIsfResult callback, which carries no filename of its own.
  const [isfStatus, setIsfStatus] = useState<
    { state: 'empty' } | { state: 'loaded'; fileName: string; targets: PatchTargetDecl[] } | { state: 'error'; fileName: string; message: string }
  >({ state: 'empty' })
  const pendingIsfFileName = useRef('shader.fs')
  const isfTargets = isfStatus.state === 'loaded' ? isfStatus.targets : []
  const handleIsfResult = useCallback((r: { ok: true; targets: PatchTargetDecl[] } | { ok: false; message: string }) => {
    setIsfStatus(r.ok ? { state: 'loaded', fileName: pendingIsfFileName.current, targets: r.targets } : { state: 'error', fileName: pendingIsfFileName.current, message: r.message })
  }, [])

  const { bridgeRef, fps, error, patchbayError, patchbayAckCount, playback } = useRuntimeBridge(canvasRef, handleSignalBus, handleIsfResult)
  const dropLog = useDropLog(bus)

  function handleIsfLoad(source: string, fileName: string) {
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
  // same graph. See AGENTS.md's "unify screen + physical patch graphs" note.
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
  // graph (see prune.ts) — it has no idea a fixture half exists, exactly
  // like it never knew about Patchbay's screen-only.ts before this session.
  useEffect(() => {
    if (graphErrors.length > 0) return // don't even try — the worker's own construction-time validation would just reject it anyway, and this way patchbayError reflects THIS specific rejection reason if the worker path itself has a narrower issue
    bridgeRef.current?.setScreenGraph(pruneGraphToTargets(graph, screenTargetIds))
  }, [graph, graphErrors.length, screenTargetIds, bridgeRef])

  const fixtureEvaluator = useMemo(() => {
    if (graphErrors.length > 0) return null
    try {
      return new PatchGraphEvaluator(pruneGraphToTargets(graph, fixtureTargetIds), targetCatalog)
    } catch {
      return null
    }
  }, [graph, targetCatalog, fixtureTargetIds, graphErrors.length])
  const [resolvedValues, setResolvedValues] = useState<Record<string, number>>({})

  useEffect(() => {
    if (!bus || !fixtureEvaluator) return
    setResolvedValues(fixtureEvaluator.evaluate(bus, 1 / 20)) // ~ the signalBus stream's own interval
  }, [bus, fixtureEvaluator])

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

  // Diagnostic-only readouts — never the main workspace, always behind the
  // 🐞 Debug drawer (see the return statement below). Nothing here shapes
  // the graph; it's all read-only observation of live state.
  const debugPanels: { id: string; title: string; hint?: string; content: React.ReactNode }[] = [
    {
      id: 'debug',
      title: 'Debug readout',
      content: (
        <div className="mono readout">
          <div>bus.energy: {bus ? bus.energy.toFixed(4) : '—'}</div>
          <div>bus.idle: {bus ? String(bus.idle) : '—'}</div>
          <div>graph: {graphErrors.length === 0 ? 'valid' : `invalid (${graphErrors.length} error(s) — see patch graph)`}</div>
          <div>fixture evaluator: {fixtureEvaluator ? 'valid' : 'invalid/not constructed'}</div>
        </div>
      ),
    },
    {
      id: 'musical',
      title: 'Musical state (Layer 2 → bus)',
      content: (
        <div className="mono readout">
          <div>tension: {bus ? bus.tension.toFixed(4) : '—'}</div>
          <div>buildProgress: {bus ? bus.buildProgress.toFixed(4) : '—'}</div>
          <div>suspension: {bus ? bus.suspension.toFixed(4) : '—'}</div>
          <div>dropImpulse: {bus ? bus.dropImpulse.toFixed(4) : '—'}</div>
          <div>familiarity: {bus ? bus.familiarity.toFixed(4) : '—'}</div>
          <div>flatness: {bus ? bus.flatness.toFixed(4) : '—'}</div>
          <div>tempoBpm / confidence: {bus ? `${bus.tempoBpm.toFixed(1)} / ${bus.tempoConfidence.toFixed(2)}` : '—'}</div>
        </div>
      ),
    },
    {
      id: 'dropInternals',
      title: 'Drop detector internals',
      hint: "The detector's own live qualifying values, straight from inside it — not the bus. If dropImpulse never fires, this is what tells you WHICH condition is failing against real audio.",
      content: (
        <div className="mono readout">
          <div>fullness: {dropDebug ? dropDebug.fullness.toFixed(4) : '—'} (needs &gt; 0.5)</div>
          <div>onsetJump: {dropDebug ? dropDebug.onsetJump.toFixed(4) : '—'} (needs &gt; 0.06 for the rhythmic path)</div>
          <div>noveltyPeak: {dropDebug ? dropDebug.noveltyPeak.toFixed(4) : '—'} (needs &gt; 0.3)</div>
          <div>armed: {dropDebug ? String(dropDebug.armed) : '—'}</div>
          {dropDebug === null && bus !== null && (
            <div style={{ color: 'var(--warn)' }}>
              null — either no track is loaded, or detectors are disabled (sidecar/position-only mode has no live
              detector to read from at all).
            </div>
          )}
        </div>
      ),
    },
    {
      id: 'dropLog',
      title: 'Drop detector log',
      hint: `Rising edges of bus.dropImpulse (>${DROP_EDGE_EPS} in one tick), most recent first. Time is seconds since this page loaded, not track position.`,
      content:
        dropLog.length === 0 ? (
          <div className="empty-hint">No drops observed yet.</div>
        ) : (
          <div className="mono readout">
            {dropLog.map((entry, i) => (
              <div key={i}>
                +{(entry.atMs / 1000).toFixed(1)}s — strength {entry.strength.toFixed(2)}
              </div>
            ))}
          </div>
        ),
    },
    {
      id: 'midi',
      title: 'MIDI in',
      hint: 'Real Web MIDI device input — control-change activity and clock/beat sync, if a device sends it. See docs/midi.md.',
      content: <MidiPanel />,
    },
  ]

  const handleTogglePlay = useCallback(() => bridgeRef.current?.togglePlayback(), [bridgeRef])
  const handleSeek = useCallback((sec: number) => bridgeRef.current?.seek(sec), [bridgeRef])

  // Escape closes the debug drawer when it's open — takes priority over the
  // demo-mode Escape handler above since the drawer only ever shows in edit
  // mode (no conflict: at most one of the two effects is listening at a time).
  useEffect(() => {
    if (!showDebug) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setShowDebug(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [showDebug])

  // Rendered exactly once, at exactly one place in the tree, regardless of
  // viewMode — canvas.transferControlToOffscreen() is a genuine one-shot
  // browser API (see the bridgesByCanvas comment above), so this element's
  // identity must never change. Its size/position is purely a CSS class
  // swap (fixed-position full-viewport vs. a small fixed corner box) —
  // exactly the lesson AGENTS.md's "fullscreen toggle unmounting the
  // canvas" bug already taught once, applied here to a bigger mode switch
  // instead of a boolean.
  const canvasBlock = (
    <div className={`canvas-block ${viewMode === 'demo' ? 'canvas-block-demo' : 'canvas-block-corner'}`}>
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
      <button className="canvas-mode-toggle" onClick={() => setViewMode(viewMode === 'demo' ? 'edit' : 'demo')} title={viewMode === 'demo' ? 'Back to editing (Esc)' : 'Fullscreen demo'}>
        {viewMode === 'demo' ? '✕ Edit' : '⤢'}
      </button>
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
            {saveStatus && <span className="status-pill">{saveStatus}</span>}
            <button className={showDebug ? 'debug-toggle active' : 'debug-toggle'} onClick={() => setShowDebug((v) => !v)} title="Show/hide diagnostic panels">
              🐞 Debug ({debugPanels.length})
            </button>
            <span className="status-pill" style={{ marginLeft: 'auto' }}>
              signalBus msgs: {busMessageCount} · acks: {patchbayAckCount}
            </span>
          </header>

          {error && <div className="banner banner-error">Render worker error: {error}</div>}
          {patchbayError && <div className="banner banner-warn">Config rejected (previous graph still running): {patchbayError}</div>}

          <div className="workspace">
            <div className="workspace-main">
              <div className="workspace-main-header">
                <h2 className="workspace-main-title">Patch graph — screen + fixtures</h2>
                <span className="section-hint" style={{ margin: 0 }}>
                  One unified graph: signal → operator → target chains, driving both the live screen and the fixtures
                  on the right from the same wiring.
                </span>
                <button onClick={handleSaveGraph} style={{ marginLeft: 'auto' }}>
                  Save to file
                </button>
              </div>
              <PatchGraphCanvas nodes={graphNodes} onChange={setGraphNodes} targets={mergedCatalog} />
            </div>

            <aside className="workspace-rail">
              <SectionCard title="ISF shader" hint="Load a real single-pass ISF (.fs) generator/filter as the screen scene — its inputs become routable targets below.">
                <IsfPanel onLoad={handleIsfLoad} onClear={handleIsfClear} status={isfStatus} />
              </SectionCard>
              <SectionCard title="DMX out" hint="Send patched fixtures out over real Art-Net/sACN via a local relay (npm run udp-relay) — see docs/dmx-out.md.">
                <DmxOutPanel fixtureDoc={fixtureDoc} resolvedValues={resolvedValues} />
              </SectionCard>
              <SectionCard title="Fixtures">
                <FixtureManager doc={fixtureDoc} onChange={handleFixtureDocChange} />
              </SectionCard>
              <SectionCard title="Fixture visuals">
                <FixtureVisuals doc={fixtureDoc} resolved={resolvedValues} />
              </SectionCard>
            </aside>
          </div>
        </>
      )}

      {showDebug && viewMode === 'edit' && (
        <>
          <div className="debug-drawer-backdrop" onClick={() => setShowDebug(false)} />
          <div className="debug-drawer">
            <div className="debug-drawer-header">
              <strong>Debug</strong>
              <button className="debug-drawer-close" onClick={() => setShowDebug(false)} title="Close (Esc)">
                ✕
              </button>
            </div>
            <div className="debug-drawer-body">
              {debugPanels.map((p) => (
                <SectionCard key={p.id} title={p.title} hint={p.hint}>
                  {p.content}
                </SectionCard>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
