import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { RuntimeBridge } from './runtime-bridge'
import { fromConfig, toConfig, type PatchDocument } from '../../../src/render/conductor/patchbay/editor/patch-document'
import { RouteTable } from './RouteTable'
import { screenOnlyConfig } from '../../../src/render/conductor/patchbay/configs/screen-only'
import { PatchGraphEvaluator } from '../../../src/render/conductor/patchgraph/PatchGraphEvaluator'
import { addFixture, fixtureTargetCatalog, emptyFixtureDocument, type FixtureDocument } from '../../../src/render/conductor/patchgraph/fixture-document'
import { fixtureTargetId } from '../../../src/render/conductor/patchgraph/fixture-types'
import type { PatchGraph } from '../../../src/render/conductor/patchgraph/types'
import type { SignalBus } from '../../../src/render/conductor/types'
import type { DropDetectorDebug } from '../../../src/audio/worklet/brain/drop-detector'

// Vertical slice (task 3): proves the whole loop works end to end before
// the real editor UI (route table, graph canvas, meters) gets built on top
// — one live screen route (a gain slider on energy -> screen.energy) and
// one live physical-graph fixture (a simulated dimmer gated by a threshold
// on energy), both driven by the same real running visualizer.

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
  const energyRoute = screenDoc.routes.find((r) => r.from === 'energy' && r.to === 'screen.energy')

  function handleScreenDocChange(next: PatchDocument) {
    setScreenDoc(next)
    bridgeRef.current?.setPatchbayConfig(toConfig(next))
  }

  const [fixtureDoc, setFixtureDoc] = useState<FixtureDocument>(() => addFixture(emptyFixtureDocument(), 'Demo Dimmer', 'dimmer'))
  const dimmer = fixtureDoc.fixtures[0]
  const dimmerTargetId = fixtureTargetId(dimmer.id, 'brightness')

  const graph: PatchGraph = useMemo(
    () => ({
      id: 'demo',
      nodes: [
        { id: 'sig', kind: 'signal', inputs: [], signal: 'energy' },
        { id: 'th', kind: 'threshold', inputs: ['sig'], cut: 0.4, hysteresis: 0.05 },
        { id: 'tgt', kind: 'target', inputs: ['th'], targetId: dimmerTargetId },
      ],
    }),
    [dimmerTargetId],
  )
  const targetCatalog = useMemo(() => fixtureTargetCatalog(fixtureDoc), [fixtureDoc])
  const evaluator = useMemo(() => new PatchGraphEvaluator(graph, targetCatalog), [graph, targetCatalog])
  const [dimmerValue, setDimmerValue] = useState(0)

  useEffect(() => {
    if (!bus) return
    const resolved = evaluator.evaluate(bus, 1 / 20) // ~ the signalBus stream's own interval
    setDimmerValue(resolved[dimmerTargetId] ?? 0)
  }, [bus, evaluator, dimmerTargetId])

  async function onFileChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) await bridgeRef.current?.loadFile(file)
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
        <span className="mono" style={{ color: 'var(--text-1)', marginLeft: 'auto' }}>
          {fps > 0 ? `${fps.toFixed(0)} fps` : '—'}
        </span>
      </header>

      {error && (
        <div style={{ padding: '6px 16px', background: 'var(--error)', color: '#200' }}>
          Render worker error: {error}
        </div>
      )}
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
            width: 460,
            padding: 16,
            borderLeft: '1px solid var(--border)',
            background: 'var(--bg-1)',
            display: 'flex',
            flexDirection: 'column',
            gap: 20,
          }}
        >
          <section>
            <h3 style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--text-1)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
              Screen routes
            </h3>
            <p style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--text-2)' }}>
              Every route in the live config, editable — this is the actual palette-automation control surface (see the
              hueDrift/centroid → screen.hueShift and buildWindup → screen.paletteMix rows).
            </p>
            <RouteTable doc={screenDoc} onChange={handleScreenDocChange} />
          </section>

          <section>
            <h3 style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--text-1)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
              Fixture: {dimmer.name}
            </h3>
            <p style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--text-2)' }}>
              threshold(energy, cut 0.4, hysteresis 0.05) → brightness
            </p>
            <div
              style={{
                width: '100%',
                height: 48,
                borderRadius: 'var(--radius)',
                border: '1px solid var(--border)',
                background: dimmerValue > 0 ? 'rgba(94, 230, 200, 0.8)' : 'rgba(94, 230, 200, 0.04)',
                boxShadow: dimmerValue > 0 ? '0 0 32px rgba(94,230,200,0.5)' : 'none',
                transition: 'background 0.08s linear, box-shadow 0.08s linear',
              }}
            />
          </section>

          <section>
            <h3 style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--text-1)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
              Debug readout
            </h3>
            <div className="mono" style={{ fontSize: 12, color: 'var(--text-1)', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div>bus.energy: {bus ? bus.energy.toFixed(4) : '—'}</div>
              <div>bus.idle: {bus ? String(bus.idle) : '—'}</div>
              <div>energy gain (route): {(energyRoute?.gain ?? 1).toFixed(2)}</div>
              <div>energy * gain (pre-clamp): {bus ? (bus.energy * (energyRoute?.gain ?? 1)).toFixed(4) : '—'}</div>
              <div>dimmer threshold output: {dimmerValue.toFixed(0)}</div>
              <div>signalBus messages received: {busMessageCount}</div>
              <div>patchbay edits acknowledged by worker: {patchbayAckCount}</div>
            </div>
          </section>

          <section>
            <h3 style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--text-1)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
              Musical state (Layer 2 → bus)
            </h3>
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
            <h3 style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--text-1)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
              Drop detector internals
            </h3>
            <p style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--text-2)' }}>
              The detector's own live qualifying values, straight from inside it — not the bus. If dropImpulse never
              fires, this is what tells you WHICH condition is failing against real audio (thresholds below were tuned
              against synthetic test fixtures, which may not match real value ranges at all).
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
            <h3 style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--text-1)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
              Drop detector log
            </h3>
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
