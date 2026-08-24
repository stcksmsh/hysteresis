import { useEffect, useRef, useState } from 'react'
import { MidiInput, isWebMidiSupported, type MidiInputStatus } from '../../../src/midi/midi-input'
import type { MidiClockState } from '../../../src/midi/midi-clock'

const CC_LOG_MAX = 8
const CLOCK_POLL_MS = 100

// A live diagnostic for real MIDI input (master-prompt.md §5's MIDI
// entry) — shows exactly what's arriving from a real connected device
// (clock tempo/phase, recent CC activity) so "does the device path
// actually work" is directly observable, the same role the drop-detector
// internals panel plays for audio. Deliberately NOT wired into the patch
// graph as a routable target yet (see AGENTS.md) — this is the
// "the real thing works end to end" proof for the parsing/clock-tracking/
// CC-mapping logic before committing to how it should be exposed as a
// patchable input.
export function MidiPanel() {
  const midiRef = useRef<MidiInput | null>(null)
  const [status, setStatus] = useState<MidiInputStatus>({ connected: false, deviceNames: [] })
  const [clockState, setClockState] = useState<MidiClockState>({ bpm: 0, confidence: 0, beatPhase: 0, barPhase: 0, running: false })
  const [ccLog, setCcLog] = useState<{ key: string; value: number }[]>([])

  function ensureMidi(): MidiInput {
    if (!midiRef.current) {
      midiRef.current = new MidiInput(setStatus, (key, value) => {
        setCcLog((prev) => [{ key, value }, ...prev.filter((e) => e.key !== key)].slice(0, CC_LOG_MAX))
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
        {!status.connected ? <button onClick={connect}>Connect MIDI</button> : <button onClick={disconnect}>Disconnect</button>}
      </div>
      <div className="mono readout">
        <div>{status.connected ? `connected — ${status.deviceNames.length ? status.deviceNames.join(', ') : 'no input ports'}` : (status.message ?? 'disconnected')}</div>
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
