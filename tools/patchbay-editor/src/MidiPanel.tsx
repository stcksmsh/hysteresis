import { useEffect, useRef, useState } from 'react'
import { MidiInput, isWebMidiSupported, type MidiInputStatus } from '../../../src/midi/midi-input'
import type { MidiClockState } from '../../../src/midi/midi-clock'
import { Button } from './ui/Button'
import { Badge } from './ui/Badge'

const CC_LOG_MAX = 8
const CLOCK_POLL_MS = 100

export interface MidiPanelProps {
  // Forwards every real CC message to the worker-resident patch graph
  // (a `midiCc` node reads it there — see patchgraph/types.ts's own doc
  // comment) — additive to this panel's own diagnostic ccLog below, not a
  // replacement for it. Optional so this panel still works standalone
  // (e.g. a future non-editor caller with nothing to route into).
  onCcChange?: (key: string, value: number) => void
}

// A live diagnostic AND the real routing source for MIDI input
// (master-prompt.md §5's MIDI entry): shows exactly what's arriving from a
// real connected device (clock tempo/phase, recent CC activity) so "does
// the device path actually work" is directly observable, the same role the
// drop-detector internals panel plays for audio — while `onCcChange`
// simultaneously feeds the same live values into the patch graph via
// App.tsx's bridge.setMidiCc, closing the "not yet routable" gap flagged
// in prior sessions.
export function MidiPanel({ onCcChange }: MidiPanelProps) {
  const midiRef = useRef<MidiInput | null>(null)
  const [status, setStatus] = useState<MidiInputStatus>({ connected: false, deviceNames: [] })
  const [clockState, setClockState] = useState<MidiClockState>({ bpm: 0, confidence: 0, beatPhase: 0, barPhase: 0, running: false })
  const [ccLog, setCcLog] = useState<{ key: string; value: number }[]>([])
  // Kept live without retriggering ensureMidi()/its MidiInput instance —
  // same "read through a ref so a changing prop doesn't need a re-wire"
  // shape as DmxOutPanel's own `latest` ref.
  const onCcChangeRef = useRef(onCcChange)
  onCcChangeRef.current = onCcChange

  function ensureMidi(): MidiInput {
    if (!midiRef.current) {
      midiRef.current = new MidiInput(setStatus, (key, value) => {
        setCcLog((prev) => [{ key, value }, ...prev.filter((e) => e.key !== key)].slice(0, CC_LOG_MAX))
        onCcChangeRef.current?.(key, value)
      })
    }
    return midiRef.current
  }

  function connect() {
    void ensureMidi().connect()
  }

  function disconnect() {
    midiRef.current?.disconnect()
    setCcLog([])
  }

  useEffect(() => {
    const handle = setInterval(() => {
      if (midiRef.current) setClockState(midiRef.current.getClockState())
    }, CLOCK_POLL_MS)
    return () => clearInterval(handle)
  }, [])

  useEffect(() => () => midiRef.current?.disconnect(), [])

  if (!isWebMidiSupported()) {
    return <div className="banner banner-warn">Web MIDI isn't supported in this browser.</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
      <div style={{ display: 'flex', gap: 6 }}>
        {!status.connected ? <Button onClick={connect}>Connect MIDI</Button> : <Button onClick={disconnect}>Disconnect</Button>}
      </div>
      <div className="mono readout">
        <div>
          {status.connected ? (
            <>
              <Badge tone="ok">connected</Badge> {status.deviceNames.length ? status.deviceNames.join(', ') : 'no input ports'}
            </>
          ) : (
            (status.message ?? 'disconnected')
          )}
        </div>
        <div>
          clock: {clockState.running ? `${clockState.bpm.toFixed(1)} bpm (confidence ${clockState.confidence.toFixed(2)})` : 'not running'} — beatPhase{' '}
          {clockState.beatPhase.toFixed(2)}, barPhase {clockState.barPhase.toFixed(2)}
        </div>
      </div>
      <div className="mono readout">
        {ccLog.length === 0 ? <div className="empty-hint">No CC activity yet.</div> : ccLog.map((e) => <div key={e.key}>CC {e.key}: {e.value.toFixed(2)}</div>)}
      </div>
    </div>
  )
}
