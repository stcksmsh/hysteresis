import { useEffect, useMemo, useRef, useState } from 'react'
import { DmxSerialOutput, isWebSerialSupported, type DmxSerialStatus } from '../../../src/dmx/dmx-serial-output'
import { renderDmxUniverses, DMX_UNIVERSE_SIZE } from '../../../src/dmx/render-dmx-universe'
import type { FixtureDocument } from '../../../src/render/conductor/patchgraph/fixture-document'
import type { DmxProtocol } from '../../../src/dmx/dmx-out-bridge'
import type { FixtureOutConfig } from '../../../src/shared/types'
import { Button } from './ui/Button'
import { Select } from './ui/Select'
import { TextInput } from './ui/TextInput'
import { Badge } from './ui/Badge'

export interface DmxOutPanelProps {
  fixtureDoc: FixtureDocument
  resolvedValues: Record<string, number>
  // Art-Net/sACN/WLED delegate to the real production path (FixtureOutput,
  // running inside the render worker — see AGENTS.md's "wire the fixture
  // patch graph into production" then "dogfood the fixture API in the
  // patchbay editor" sessions) via these two, instead of this panel owning
  // its own DmxOutBridge/send-loop the way it used to. USB stays local
  // (below) since Web Serial can't run inside a worker.
  onConnect: (config: FixtureOutConfig) => void
  onDisconnect: () => void
  status: { connected: boolean; message?: string }
}

const DMX_SEND_INTERVAL_MS = 40 // ~25Hz — plenty for a reactive lighting look, matches FixtureOutput's own worker-side throttle
type OutMode = DmxProtocol | 'usb'
// USB and WLED both target exactly ONE universe per send (a dongle drives
// one universe; a WLED device is one specific IP, not a broadcast/
// multicast group) — Art-Net/sACN send every patched universe at once.
const SINGLE_UNIVERSE_MODES: OutMode[] = ['usb', 'wled-drgb']

// Sends the editor's already-live fixture values out over real Art-Net,
// sACN, a USB DMX dongle, or a WLED LED controller (docs/dmx-out.md) — the
// "runnable, not just simulated" half of the DMX-patched fixtures
// FixtureManager now supports. Art-Net/sACN/WLED reuse `npm run udp-relay`
// (browsers have no raw UDP); USB is the one leg that's genuinely
// browser-native (Web Serial), no relay needed, but Chromium-desktop-only
// AND main-thread-only (a requestPort() user gesture can't run inside a
// worker), so it's the one mode this panel still drives itself rather than
// delegating to the worker-resident FixtureOutput.
export function DmxOutPanel({ fixtureDoc, resolvedValues, onConnect, onDisconnect, status }: DmxOutPanelProps) {
  const [mode, setMode] = useState<OutMode>('artnet')
  const [wsUrl, setWsUrl] = useState('ws://localhost:9090')
  const [wledHost, setWledHost] = useState('')
  const [serialStatus, setSerialStatus] = useState<DmxSerialStatus>({ connected: false })
  const [sending, setSending] = useState(false)
  const serialRef = useRef<DmxSerialOutput | null>(null)
  // Kept live across renders without retriggering the USB send-loop effect
  // — same "read through a ref" shape as before.
  const latest = useRef({ fixtureDoc, resolvedValues })
  latest.current = { fixtureDoc, resolvedValues }

  const patchedUniverses = useMemo(() => [...new Set(fixtureDoc.fixtures.map((f) => f.dmxPatch?.universe).filter((u): u is number => u !== undefined))].sort((a, b) => a - b), [fixtureDoc])
  const [singleUniverse, setSingleUniverse] = useState<number | null>(null)
  const isSingleUniverseMode = SINGLE_UNIVERSE_MODES.includes(mode)
  const isConnected = mode === 'usb' ? serialStatus.connected : status.connected

  function connect() {
    if (mode === 'usb') {
      const serial = new DmxSerialOutput(setSerialStatus)
      serialRef.current = serial
      void serial.connect() // user-gesture click, per Web Serial's own requirement
      return
    }
    onConnect({ protocol: mode, wsUrl, universeHost: mode === 'wled-drgb' ? wledHost : undefined })
  }

  function disconnect() {
    void serialRef.current?.disconnect()
    serialRef.current = null
    setSerialStatus({ connected: false })
    setSending(false)
    onDisconnect()
  }

  // USB's own send loop — the worker drives Art-Net/sACN/WLED itself now
  // (FixtureOutput's own throttled send, see render-worker.ts), so this
  // effect only still exists for the one mode that can't run there.
  useEffect(() => {
    if (!sending || mode !== 'usb') return
    const handle = setInterval(() => {
      if (!serialRef.current) return
      const universes = renderDmxUniverses(latest.current.fixtureDoc, latest.current.resolvedValues)
      if (singleUniverse !== null) void serialRef.current.send(universes.get(singleUniverse) ?? new Uint8Array(DMX_UNIVERSE_SIZE))
    }, DMX_SEND_INTERVAL_MS)
    return () => clearInterval(handle)
  }, [sending, singleUniverse, mode])

  useEffect(() => {
    return () => {
      void serialRef.current?.disconnect()
    }
  }, [])

  const patchedCount = fixtureDoc.fixtures.filter((f) => f.dmxPatch).length
  const canConnect = mode !== 'usb' || isWebSerialSupported()
  const canSend = mode !== 'usb' || !isSingleUniverseMode || singleUniverse !== null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
      <p className="section-hint" style={{ margin: 0 }}>
        {patchedCount === 0 ? 'No fixtures have a DMX address yet — set one in Fixtures below.' : `${patchedCount} fixture(s) patched.`}
      </p>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <Select uiSize="sm" value={mode} onChange={(e) => setMode(e.target.value as OutMode)} disabled={isConnected}>
          <option value="artnet">Art-Net</option>
          <option value="sacn">sACN (E1.31)</option>
          <option value="wled-drgb">WLED (UDP realtime)</option>
          <option value="usb">USB (Enttec-protocol dongle)</option>
        </Select>
        {mode === 'usb' ? null : mode === 'wled-drgb' ? (
          <TextInput placeholder="192.168.1.50" value={wledHost} onChange={(e) => setWledHost(e.target.value)} disabled={isConnected} style={{ flex: 1, fontSize: 12 }} />
        ) : (
          <TextInput value={wsUrl} onChange={(e) => setWsUrl(e.target.value)} disabled={isConnected} style={{ flex: 1, fontSize: 12 }} />
        )}
      </div>
      {isSingleUniverseMode && (
        <Select uiSize="sm" value={singleUniverse ?? ''} onChange={(e) => setSingleUniverse(e.target.value ? Number(e.target.value) : null)}>
          <option value="">select universe…</option>
          {patchedUniverses.map((u) => (
            <option key={u} value={u}>
              universe {u}
            </option>
          ))}
        </Select>
      )}
      {mode === 'usb' && !isWebSerialSupported() && <div className="banner banner-warn">Web Serial isn't supported in this browser (Chromium desktop only).</div>}
      <div style={{ display: 'flex', gap: 6 }}>
        {!isConnected ? (
          <Button onClick={connect} disabled={!canConnect}>
            {mode === 'usb' ? 'Select serial port…' : 'Connect'}
          </Button>
        ) : (
          <>
            {mode === 'usb' && (
              <Button onClick={() => setSending((v) => !v)} disabled={!canSend}>
                {sending ? 'Stop sending' : 'Start sending'}
              </Button>
            )}
            <Button onClick={disconnect}>Disconnect</Button>
          </>
        )}
      </div>
      <div className="mono readout">
        {(mode === 'usb' ? serialStatus.connected : status.connected) && <Badge tone="ok">connected</Badge>}{' '}
        {mode === 'usb'
          ? serialStatus.connected
            ? sending
              ? 'sending'
              : ''
            : (serialStatus.message ?? 'disconnected')
          : status.connected
            ? 'the render worker sends automatically'
            : (status.message ?? 'disconnected')}
      </div>
    </div>
  )
}
