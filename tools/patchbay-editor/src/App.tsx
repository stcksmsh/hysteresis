import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { RuntimeBridge } from './runtime-bridge'
import { fromConfig, toConfig, type PatchDocument } from '../../../src/render/conductor/patchbay/editor/patch-document'
import { RouteTable } from './RouteTable'
import { FixtureManager } from './FixtureManager'
import { GraphEditor } from './GraphEditor'
import { FixtureVisuals } from './FixtureVisuals'
import { Panel } from './Panel'
import { usePanelOrder } from './use-panel-order'
import { serializeScreenConfig, serializeGraphAndFixtures, saveToFile } from './serialize-config'
import { makeDefaultDraft, makeNodeId, toPatchGraph, type DraftNode } from './graph-draft'
import { screenOnlyConfig } from '../../../src/render/conductor/patchbay/configs/screen-only'
import { validatePatchGraph } from '../../../src/render/conductor/patchgraph/validate'
import { PatchGraphEvaluator } from '../../../src/render/conductor/patchgraph/PatchGraphEvaluator'
import { addFixture, fixtureTargetCatalog, emptyFixtureDocument, type FixtureDocument } from '../../../src/render/conductor/patchgraph/fixture-document'
import { fixtureTargetId } from '../../../src/render/conductor/patchgraph/fixture-types'
import type { SignalBus } from '../../../src/render/conductor/types'
import type { DropDetectorDebug } from '../../../src/audio/worklet/brain/drop-detector'

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
) {
  const bridgeRef = useRef<RuntimeBridge | null>(null)
  const [fps, setFps] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [patchbayError, setPatchbayError] = useState<string | null>(null)
  // "No error banner" only proves a rejection didn't happen, not that an
  // edit was actually applied — this makes the round trip itself visible:
  // every debugSetPatchbayConfig gets an ack either way (see
  // render-worker.ts's handler), so a counter that keeps incrementing is
  // direct proof the hot-swap loop is alive end to end.
  const [patchbayAckCount, setPatchbayAckCount] = useState(0)

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

  return { bridgeRef, fps, error, patchbayError, patchbayAckCount }
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

// Seed graph: energy gated through a threshold into the first fixture's
// first channel — a working starting point to edit from, not a fixed demo.
function seedNodes(targetId: string): DraftNode[] {
  const sig = makeDefaultDraft('signal', makeNodeId())
  const th = makeDefaultDraft('threshold', makeNodeId())
  th.inputs = [sig.id]
  const tgt = makeDefaultDraft('target', makeNodeId())
  tgt.inputs = [th.id]
  tgt.targetId = targetId
  return [sig, th, tgt]
}

export function App() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [canvasFullscreen, setCanvasFullscreen] = useState(false)
  const [bus, setBus] = useState<SignalBus | null>(null)
  const [busMessageCount, setBusMessageCount] = useState(0)
  const [dropDebug, setDropDebug] = useState<DropDetectorDebug | null>(null)
  const handleSignalBus = useCallback((b: SignalBus, dbg: DropDetectorDebug | null) => {
    setBus(b)
    setBusMessageCount((n) => n + 1)
    setDropDebug(dbg)
  }, [])
  const { bridgeRef, fps, error, patchbayError, patchbayAckCount } = useRuntimeBridge(canvasRef, handleSignalBus)
  const dropLog = useDropLog(bus)

  const [screenDoc, setScreenDoc] = useState<PatchDocument>(() => fromConfig(screenOnlyConfig))

  function handleScreenDocChange(next: PatchDocument) {
    setScreenDoc(next)
    bridgeRef.current?.setPatchbayConfig(toConfig(next))
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

  const [graphNodes, setGraphNodes] = useState<DraftNode[]>(() => {
    const firstTarget = targetCatalog[0]
    return firstTarget ? seedNodes(firstTarget.id) : []
  })

  const graph = useMemo(() => toPatchGraph('editor', graphNodes), [graphNodes])
  const graphErrors = useMemo(() => validatePatchGraph(graph, targetCatalog).filter((i) => i.severity === 'error'), [graph, targetCatalog])
  const evaluator = useMemo(() => {
    if (graphErrors.length > 0) return null
    try {
      return new PatchGraphEvaluator(graph, targetCatalog)
    } catch {
      return null
    }
  }, [graph, targetCatalog, graphErrors.length])
  const [resolvedValues, setResolvedValues] = useState<Record<string, number>>({})

  useEffect(() => {
    if (!bus || !evaluator) return
    setResolvedValues(evaluator.evaluate(bus, 1 / 20)) // ~ the signalBus stream's own interval
  }, [bus, evaluator])

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
    if (!canvasFullscreen) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setCanvasFullscreen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [canvasFullscreen])

  const [saveStatus, setSaveStatus] = useState<string | null>(null)

  async function handleSaveScreenConfig() {
    const source = serializeScreenConfig(toConfig(screenDoc))
    const result = await saveToFile('screen-config.ts', source)
    setSaveStatus(result.ok ? `Saved to ${result.path}` : `Save failed: ${result.message}`)
  }

  async function handleSaveGraph() {
    const source = serializeGraphAndFixtures(graph, fixtureDoc)
    const result = await saveToFile('patch-graph.ts', source)
    setSaveStatus(result.ok ? `Saved to ${result.path}` : `Save failed: ${result.message}`)
  }

  const panels: { id: string; title: string; hint?: string; wide?: boolean; width?: number; height?: number; content: React.ReactNode }[] = [
    {
      id: 'routes',
      title: 'Screen routes',
      hint: 'Every route in the live config, editable — including the palette-automation rows (hueDrift/centroid → screen.hueShift, buildWindup → screen.paletteMix).',
      width: 560,
      height: 420,
      content: (
        <>
          <RouteTable doc={screenDoc} onChange={handleScreenDocChange} />
          <button onClick={handleSaveScreenConfig} style={{ marginTop: 8 }}>
            Save screen config to file
          </button>
        </>
      ),
    },
    {
      id: 'fixtures',
      title: 'Fixtures',
      width: 360,
      height: 260,
      content: <FixtureManager doc={fixtureDoc} onChange={handleFixtureDocChange} />,
    },
    {
      id: 'graph',
      title: 'Physical patch graph',
      hint: 'Signal → operator → target chains, evaluated live against the fixtures above. Structured editor, not a canvas — see graph-draft.ts if adding a node-graph view later.',
      wide: true,
      height: 480,
      content: (
        <>
          <GraphEditor nodes={graphNodes} onChange={setGraphNodes} targets={targetCatalog} />
          <button onClick={handleSaveGraph} style={{ marginTop: 8 }}>
            Save graph + fixtures to file
          </button>
        </>
      ),
    },
    {
      id: 'visuals',
      title: 'Fixture visuals',
      width: 360,
      height: 260,
      content: <FixtureVisuals doc={fixtureDoc} resolved={resolvedValues} />,
    },
    {
      id: 'debug',
      title: 'Debug readout',
      width: 340,
      height: 180,
      content: (
        <div className="mono readout">
          <div>bus.energy: {bus ? bus.energy.toFixed(4) : '—'}</div>
          <div>bus.idle: {bus ? String(bus.idle) : '—'}</div>
          <div>graph evaluator: {evaluator ? 'valid' : `invalid (${graphErrors.length} error(s) — see graph editor)`}</div>
        </div>
      ),
    },
    {
      id: 'musical',
      title: 'Musical state (Layer 2 → bus)',
      width: 340,
      height: 240,
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
      width: 380,
      height: 240,
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
      width: 320,
      height: 240,
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
  ]
  const panelsById = new Map(panels.map((p) => [p.id, p]))
  const defaultOrder = panels.map((p) => p.id)
  const { order, draggingId, dragOverId, onDragStart, onDragEnd, onDragOver, onDrop } = usePanelOrder(defaultOrder)

  const canvasBlock = (
    <div
      className={canvasFullscreen ? 'canvas-block canvas-block-fullscreen' : 'canvas-block'}
      style={{ background: '#000' }}
    >
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
      <button className="fullscreen-toggle" onClick={() => setCanvasFullscreen((v) => !v)}>
        {canvasFullscreen ? '✕ Exit fullscreen (Esc)' : '⤢ Fullscreen'}
      </button>
      <span className="status-pill canvas-fps-pill">{fps > 0 ? `${fps.toFixed(0)} fps` : '—'}</span>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <header className="app-header">
        <strong style={{ letterSpacing: 0.3, fontSize: 15 }}>Patchbay</strong>
        <input type="file" accept="audio/*" onChange={onFileChosen} />
        {saveStatus && <span className="status-pill">{saveStatus}</span>}
        <span className="status-pill" style={{ marginLeft: 'auto' }}>
          signalBus msgs: {busMessageCount} · acks: {patchbayAckCount}
        </span>
      </header>

      {error && <div className="banner banner-error">Render worker error: {error}</div>}
      {patchbayError && <div className="banner banner-warn">Config rejected (previous config still running): {patchbayError}</div>}

      <div className="app-body">
        {canvasBlock}

        <div className="panel-flow">
          {order.map((id) => {
            const panel = panelsById.get(id)
            if (!panel) return null
            return (
              <Panel
                key={panel.id}
                id={panel.id}
                title={panel.title}
                hint={panel.hint}
                wide={panel.wide}
                defaultWidth={panel.width}
                defaultHeight={panel.height}
                dragging={draggingId === panel.id}
                draggedOver={dragOverId === panel.id && draggingId !== panel.id}
                onDragStart={onDragStart}
                onDragEnd={onDragEnd}
                onDragOver={onDragOver}
                onDrop={onDrop}
              >
                {panel.content}
              </Panel>
            )
          })}
        </div>
      </div>
    </div>
  )
}
