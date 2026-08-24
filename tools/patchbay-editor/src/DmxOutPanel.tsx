import { useEffect, useMemo, useRef, useState } from 'react'
import { DmxOutBridge, type DmxProtocol, type DmxOutStatus } from '../../../src/dmx/dmx-out-bridge'
import { DmxSerialOutput, isWebSerialSupported, type DmxSerialStatus } from '../../../src/dmx/dmx-serial-output'
import { renderDmxUniverses, DMX_UNIVERSE_SIZE } from '../../../src/dmx/render-dmx-universe'
import type { FixtureDocument } from '../../../src/render/conductor/patchgraph/fixture-document'

export interface DmxOutPanelProps {
  fixtureDoc: FixtureDocument
  resolvedValues: Record<string, number>
}

// Sends the editor's already-live fixture values out over real Art-Net,
// sACN, a USB DMX dongle, or a WLED LED controller (docs/dmx-out.md) — the
// "runnable, not just simulated" half of the DMX-patched fixtures
// FixtureManager now supports. Art-Net/sACN/WLED reuse `npm run udp-relay`
// (browsers have no raw UDP); USB is the one leg that's genuinely
// browser-native (Web Serial), no relay needed, but Chromium-desktop-only.
const DMX_SEND_INTERVAL_MS = 40 // ~25Hz — plenty for a reactive lighting look, well clear of either transport as a bottleneck
type OutMode = DmxProtocol | 'usb'
// USB and WLED both target exactly ONE universe per send (a dongle drives
// one universe; a WLED device is one specific IP, not a broadcast/
// multicast group) — Art-Net/sACN send every patched universe at once.
const SINGLE_UNIVERSE_MODES: OutMode[] = ['usb', 'wled-drgb']

export function DmxOutPanel({ fixtureDoc, resolvedValues }: DmxOutPanelProps) {
  const [mode, setMode] = useState<OutMode>('artnet')
  const [wsUrl, setWsUrl] = useState('ws://localhost:9090')
  const [wledHost, setWledHost] = useState('')
  const [status, setStatus] = useState<DmxOutStatus | DmxSerialStatus>({ connected: false })
  const [sending, setSending] = useState(false)
  const bridgeRef = useRef<DmxOutBridge | null>(null)
  const serialRef = useRef<DmxSerialOutput | null>(null)
  // Kept live across renders without retriggering the send-loop effect —
  // the interval below reads through this ref so it always sends the
  // CURRENT fixture doc/resolved values without needing to be torn down
  // and recreated every time either changes (which happens on every
  // signalBus tick, i.e. constantly).
  const latest = useRef({ fixtureDoc, resolvedValues })
  latest.current = { fixtureDoc, resolvedValues }

  const patchedUniverses = useMemo(() => [...new Set(fixtureDoc.fixtures.map((f) => f.dmxPatch?.universe).filter((u): u is number => u !== undefined))].sort((a, b) => a - b), [fixtureDoc])
  const [singleUniverse, setSingleUniverse] = useState<number | null>(null)
  const isSingleUniverseMode = SINGLE_UNIVERSE_MODES.includes(mode)

  function disconnectAll() {
    bridgeRef.current?.disconnect()
    bridgeRef.current = null
    void serialRef.current?.disconnect()
    serialRef.current = null
  }

  function connect() {
    disconnectAll()
    if (mode === 'usb') {
      const serial = new DmxSerialOutput(setStatus)
      serialRef.current = serial
      void serial.connect() // user-gesture click, per Web Serial's own requirement
    } else {
      const bridge = new DmxOutBridge({ protocol: mode, sacnSourceName: 'Hysteresis' }, setStatus)
      bridge.connect(wsUrl)
      bridgeRef.current = bridge
    }
  }

  function disconnect() {
    disconnectAll()
    setSending(false)
    setStatus({ connected: false })
  }

  useEffect(() => {
    if (!sending) return
    const handle = setInterval(() => {
      const universes = renderDmxUniverses(latest.current.fixtureDoc, latest.current.resolvedValues)
      if (serialRef.current) {
        if (singleUniverse !== null) void serialRef.current.send(universes.get(singleUniverse) ?? new Uint8Array(DMX_UNIVERSE_SIZE))
        return
      }
      if (!bridgeRef.current) return
      if (mode === 'wled-drgb') {
        if (singleUniverse === null || !wledHost) return
        const buf = universes.get(singleUniverse)
        if (buf) bridgeRef.current.send(new Map([[singleUniverse, buf]]), wledHost)
        return
      }
      if (universes.size > 0) bridgeRef.current.send(universes)
    }, DMX_SEND_INTERVAL_MS)
    return () => clearInterval(handle)
  }, [sending, singleUniverse, mode, wledHost])

  useEffect(() => disconnectAll, [])

  const patchedCount = fixtureDoc.fixtures.filter((f) => f.dmxPatch).length
  const canConnect = mode !== 'usb' || isWebSerialSupported()
  const canSend = !isSingleUniverseMode || (singleUniverse !== null && (mode !== 'wled-drgb' || wledHost.trim().length > 0))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
      <p className="section-hint" style={{ margin: 0 }}>
        {patchedCount === 0 ? 'No fixtures have a DMX address yet — set one in Fixtures below.' : `${patchedCount} fixture(s) patched.`}
      </p>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <select value={mode} onChange={(e) => setMode(e.target.value as OutMode)} disabled={status.connected} style={{ fontSize: 12 }}>
          <option value="artnet">Art-Net</option>
          <option value="sacn">sACN (E1.31)</option>
          <option value="wled-drgb">WLED (UDP realtime)</option>
          <option value="usb">USB (Enttec-protocol dongle)</option>
        </select>
        {mode === 'usb' ? null : mode === 'wled-drgb' ? (
          <input type="text" placeholder="192.168.1.50" value={wledHost} onChange={(e) => setWledHost(e.target.value)} disabled={status.connected} style={{ flex: 1, fontSize: 12 }} />
        ) : (
          <input type="text" value={wsUrl} onChange={(e) => setWsUrl(e.target.value)} disabled={status.connected} style={{ flex: 1, fontSize: 12 }} />
        )}
      </div>
      {isSingleUniverseMode && (
        <select value={singleUniverse ?? ''} onChange={(e) => setSingleUniverse(e.target.value ? Number(e.target.value) : null)} style={{ fontSize: 12 }}>
          <option value="">select universe…</option>
          {patchedUniverses.map((u) => (
            <option key={u} value={u}>
              universe {u}
            </option>
          ))}
        </select>
      )}
      {mode === 'usb' && !isWebSerialSupported() && <div className="banner banner-warn">Web Serial isn't supported in this browser (Chromium desktop only).</div>}
      <div style={{ display: 'flex', gap: 6 }}>
        {!status.connected ? (
          <button onClick={connect} disabled={!canConnect}>
            {mode === 'usb' ? 'Select serial port…' : 'Connect'}
          </button>
        ) : (
          <>
            <button onClick={() => setSending((v) => !v)} disabled={!canSend}>
              {sending ? 'Stop sending' : 'Start sending'}
            </button>
            <button onClick={disconnect}>Disconnect</button>
          </>
        )}
      </div>
      <div className="mono readout">{status.connected ? `connected${sending ? ' — sending' : ''}` : (status.message ?? 'disconnected')}</div>
    </div>
  )
}
