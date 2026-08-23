import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { RuntimeBridge } from './runtime-bridge'
import { fromConfig, toConfig, updateRoute, type PatchDocument } from '../../../src/render/conductor/patchbay/editor/patch-document'
import { screenOnlyConfig } from '../../../src/render/conductor/patchbay/configs/screen-only'
import { PatchGraphEvaluator } from '../../../src/render/conductor/patchgraph/PatchGraphEvaluator'
import { addFixture, fixtureTargetCatalog, emptyFixtureDocument, type FixtureDocument } from '../../../src/render/conductor/patchgraph/fixture-document'
import { fixtureTargetId } from '../../../src/render/conductor/patchgraph/fixture-types'
import type { PatchGraph } from '../../../src/render/conductor/patchgraph/types'
import type { SignalBus } from '../../../src/render/conductor/types'

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

function useRuntimeBridge(canvasRef: React.RefObject<HTMLCanvasElement | null>, onSignalBus: (bus: SignalBus) => void) {
  const bridgeRef = useRef<RuntimeBridge | null>(null)
  const [fps, setFps] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [patchbayError, setPatchbayError] = useState<string | null>(null)

  useEffect(() => {
    if (!canvasRef.current) return
    const callbacks = {
      onStats: (v: number) => setFps(v),
      onError: (m: string) => setError(m),
      onSignalBus,
      onPatchbayResult: (r: { ok: true } | { ok: false; message: string }) => setPatchbayError(r.ok ? null : r.message),
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

  return { bridgeRef, fps, error, patchbayError }
}

export function App() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [bus, setBus] = useState<SignalBus | null>(null)
  const [busMessageCount, setBusMessageCount] = useState(0)
  const handleSignalBus = useCallback((b: SignalBus) => {
    setBus(b)
    setBusMessageCount((n) => n + 1)
  }, [])
  const { bridgeRef, fps, error, patchbayError } = useRuntimeBridge(canvasRef, handleSignalBus)

  const [screenDoc, setScreenDoc] = useState<PatchDocument>(() => fromConfig(screenOnlyConfig))
  const energyRoute = screenDoc.routes.find((r) => r.from === 'energy' && r.to === 'screen.energy')

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

  function setEnergyGain(gain: number) {
    if (!energyRoute) return
    const next = updateRoute(screenDoc, energyRoute.id, { gain })
    setScreenDoc(next)
    bridgeRef.current?.setPatchbayConfig(toConfig(next))
  }

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
            width: 320,
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
              Screen route
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 12 }}>
                energy → screen.energy — gain ({(energyRoute?.gain ?? 1).toFixed(2)})
              </label>
              <input
                type="range"
                min={0}
                max={3}
                step={0.05}
                value={energyRoute?.gain ?? 1}
                onChange={(e) => setEnergyGain(Number(e.target.value))}
              />
            </div>
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
            </div>
          </section>
        </aside>
      </div>
    </div>
  )
}
