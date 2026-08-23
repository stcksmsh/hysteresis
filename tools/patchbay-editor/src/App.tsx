import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { RuntimeBridge } from './runtime-bridge'
import { fromConfig, toConfig, type PatchDocument } from '../../../src/render/conductor/patchbay/editor/patch-document'
import { RouteTable } from './RouteTable'
import { FixtureManager } from './FixtureManager'
import { GraphEditor } from './GraphEditor'
import { FixtureVisuals } from './FixtureVisuals'
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

function sectionTitle(text: string) {
  return (
    <h3 style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--text-1)', textTransform: 'uppercase', letterSpacing: 0.6 }}>{text}</h3>
  )
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

  const [fixtureDoc, setFixtureDoc] = useState<FixtureDocument>(() => addFixture(emptyFixtureDocument(), 'Demo Dimmer', 'dimmer'))
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          padding: '10px 16px',
          borderBottom: '1px solid var(--border)',
          background: 'var(--bg-1)',
        }}
      >
        <strong style={{ letterSpacing: 0.3 }}>Patchbay</strong>
        <input type="file" accept="audio/*" onChange={onFileChosen} />
        {saveStatus && (
          <span className="mono" style={{ fontSize: 11, color: 'var(--text-1)' }}>
            {saveStatus}
          </span>
        )}
        <span className="mono" style={{ color: 'var(--text-1)', marginLeft: 'auto' }}>
          {fps > 0 ? `${fps.toFixed(0)} fps` : '—'}
        </span>
      </header>

      {error && <div style={{ padding: '6px 16px', background: 'var(--error)', color: '#200' }}>Render worker error: {error}</div>}
      {patchbayError && (
        <div style={{ padding: '6px 16px', background: 'var(--warn)', color: '#200' }}>
          Config rejected (previous config still running): {patchbayError}
        </div>
      )}

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <div style={{ flex: 1, position: 'relative', background: '#000' }}>
          <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
        </div>

        <aside
          style={{
            width: 520,
            padding: 16,
            borderLeft: '1px solid var(--border)',
            background: 'var(--bg-1)',
            display: 'flex',
            flexDirection: 'column',
            gap: 20,
            overflowY: 'auto',
          }}
        >
          <section>
            {sectionTitle('Screen routes')}
            <p style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--text-2)' }}>
              Every route in the live config, editable — including the palette-automation rows (hueDrift/centroid →
              screen.hueShift, buildWindup → screen.paletteMix).
            </p>
            <RouteTable doc={screenDoc} onChange={handleScreenDocChange} />
            <button onClick={handleSaveScreenConfig} style={{ marginTop: 8, fontSize: 12 }}>
              Save screen config to file
            </button>
          </section>

          <section>
            {sectionTitle('Fixtures')}
            <FixtureManager doc={fixtureDoc} onChange={handleFixtureDocChange} />
          </section>

          <section>
            {sectionTitle('Physical patch graph')}
            <p style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--text-2)' }}>
              Signal → operator → target chains, evaluated live against the fixtures above. Structured editor, not a
              canvas — see graph-draft.ts if adding a node-graph view later.
            </p>
            <GraphEditor nodes={graphNodes} onChange={setGraphNodes} targets={targetCatalog} />
            <button onClick={handleSaveGraph} style={{ marginTop: 8, fontSize: 12 }}>
              Save graph + fixtures to file
            </button>
          </section>

          <section>
            {sectionTitle('Fixture visuals')}
            <FixtureVisuals doc={fixtureDoc} resolved={resolvedValues} />
          </section>

          <section>
            {sectionTitle('Debug readout')}
            <div className="mono" style={{ fontSize: 12, color: 'var(--text-1)', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div>bus.energy: {bus ? bus.energy.toFixed(4) : '—'}</div>
              <div>bus.idle: {bus ? String(bus.idle) : '—'}</div>
              <div>signalBus messages received: {busMessageCount}</div>
              <div>patchbay edits acknowledged by worker: {patchbayAckCount}</div>
              <div>graph evaluator: {evaluator ? 'valid' : `invalid (${graphErrors.length} error(s) — see graph editor)`}</div>
            </div>
          </section>

          <section>
            {sectionTitle('Musical state (Layer 2 → bus)')}
            <div className="mono" style={{ fontSize: 12, color: 'var(--text-1)', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div>tension: {bus ? bus.tension.toFixed(4) : '—'}</div>
              <div>buildProgress: {bus ? bus.buildProgress.toFixed(4) : '—'}</div>
              <div>suspension: {bus ? bus.suspension.toFixed(4) : '—'}</div>
              <div>dropImpulse: {bus ? bus.dropImpulse.toFixed(4) : '—'}</div>
              <div>familiarity: {bus ? bus.familiarity.toFixed(4) : '—'}</div>
              <div>flatness: {bus ? bus.flatness.toFixed(4) : '—'}</div>
              <div>tempoBpm / confidence: {bus ? `${bus.tempoBpm.toFixed(1)} / ${bus.tempoConfidence.toFixed(2)}` : '—'}</div>
            </div>
          </section>

          <section>
            {sectionTitle('Drop detector internals')}
            <p style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--text-2)' }}>
              The detector's own live qualifying values, straight from inside it — not the bus. If dropImpulse never
              fires, this is what tells you WHICH condition is failing against real audio.
            </p>
            <div className="mono" style={{ fontSize: 12, color: 'var(--text-1)', display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 12 }}>
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
          </section>

          <section>
            {sectionTitle('Drop detector log')}
            <p style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--text-2)' }}>
              Rising edges of bus.dropImpulse (&gt;{DROP_EDGE_EPS} in one tick), most recent first. Time is seconds since this
              page loaded, not track position.
            </p>
            {dropLog.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--text-2)' }}>No drops observed yet.</div>
            ) : (
              <div className="mono" style={{ fontSize: 12, color: 'var(--text-1)', display: 'flex', flexDirection: 'column', gap: 2 }}>
                {dropLog.map((entry, i) => (
                  <div key={i}>
                    +{(entry.atMs / 1000).toFixed(1)}s — strength {entry.strength.toFixed(2)}
                  </div>
                ))}
              </div>
            )}
          </section>
        </aside>
      </div>
    </div>
  )
}
