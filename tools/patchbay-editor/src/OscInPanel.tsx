import { useState } from 'react'
import { Button } from './ui/Button'
import { TextInput } from './ui/TextInput'
import { Badge } from './ui/Badge'

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
// production wiring, same as DmxOutPanel/ShaderScreen — src/index.ts's
// VizInstance.setOscIn sends the exact same message.
export function OscInPanel({ status, onConnect, onDisconnect }: OscInPanelProps) {
  const [wsUrl, setWsUrl] = useState('ws://localhost:9090')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <TextInput value={wsUrl} onChange={(e) => setWsUrl(e.target.value)} disabled={status.connected} style={{ flex: 1, fontSize: 12 }} />
        {!status.connected ? <Button onClick={() => onConnect(wsUrl)}>Connect</Button> : <Button onClick={onDisconnect}>Disconnect</Button>}
      </div>
      <p className="section-hint" style={{ margin: 0 }}>
        Route an incoming OSC message into the graph with an "osc in" node — see docs/osc.md. Requires `npm run udp-relay -- --osc-in-port 9001` (or your own port) so an external tool has somewhere real to send to.
      </p>
      <div className="mono readout">{status.connected ? <Badge tone="ok">connected</Badge> : (status.message ?? 'disconnected')}</div>
    </div>
  )
}
