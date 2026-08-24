import { useState } from 'react'

export interface OscInPanelProps {
  status: { connected: boolean; message?: string }
  onConnect: (wsUrl: string) => void
  onDisconnect: () => void
}

// The "OSC in" half of master-prompt.md §5's OSC entry (out has existed
// since the ISF/OSC session) — connects to a relay's inbound WebSocket
// feed (scripts/udp-relay.ts --osc-in-port) so an `oscIn` patch graph node
// (see the graph canvas's node kind dropdown) can route a live message
// from an external tool the same way a bus signal is routed. Real
// production wiring, same as DmxOutPanel/IsfPanel — src/index.ts's
// VizInstance.setOscIn sends the exact same message.
export function OscInPanel({ status, onConnect, onDisconnect }: OscInPanelProps) {
  const [wsUrl, setWsUrl] = useState('ws://localhost:9090')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <input type="text" value={wsUrl} onChange={(e) => setWsUrl(e.target.value)} disabled={status.connected} style={{ flex: 1, fontSize: 12 }} />
        {!status.connected ? <button onClick={() => onConnect(wsUrl)}>Connect</button> : <button onClick={onDisconnect}>Disconnect</button>}
      </div>
      <p className="section-hint" style={{ margin: 0 }}>
        Route an incoming OSC message into the graph with an "osc in" node — see docs/osc.md. Requires `npm run udp-relay -- --osc-in-port 9001` (or your own port) so an external tool has somewhere real to send to.
      </p>
      <div className="mono readout">{status.connected ? 'connected' : (status.message ?? 'disconnected')}</div>
    </div>
  )
}
