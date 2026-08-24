import { parseMidiMessage } from './midi-messages'
import { MidiClockTracker, type MidiClockState } from './midi-clock'
import { MidiCcInput } from './midi-cc-input'

export interface MidiInputStatus {
  connected: boolean
  message?: string
  deviceNames: string[]
}

export function isWebMidiSupported(): boolean {
  return typeof navigator !== 'undefined' && 'requestMIDIAccess' in navigator
}

// The Web MIDI half of this — genuinely browser-native, no relay/Bridge
// daemon needed (same story as Web Serial for DMX-serial), and with
// meaningfully broader support than Web Serial (Chrome/Edge on desktop AND
// Android; Safari added Web MIDI in 17+, unlike its explicit anti-Web-
// Serial stance — see docs/midi.md). Attaches to EVERY currently-connected
// input port rather than making the caller pick one — a "knob to map" or
// "DAW sending clock" use case almost always means "listen to whatever's
// plugged in," not a specific named device.
export class MidiInput {
  readonly clock = new MidiClockTracker()
  readonly cc: MidiCcInput
  private access: MIDIAccess | null = null

  constructor(
    private onStatus?: (status: MidiInputStatus) => void,
    onCcChange?: (key: string, value: number) => void,
  ) {
    this.cc = new MidiCcInput(onCcChange)
  }

  // Requesting MIDI access can itself prompt for permission in some
  // browsers — call from a user gesture handler to be safe, same posture
  // as Web Serial's requestPort() (DmxSerialOutput) even though Web MIDI's
  // own spec doesn't mandate it as strictly.
  async connect(): Promise<void> {
    if (!isWebMidiSupported()) {
      this.onStatus?.({ connected: false, message: 'Web MIDI is not supported in this browser', deviceNames: [] })
      return
    }
    try {
      const access = await navigator.requestMIDIAccess()
      this.access = access
      this.attachToInputs()
      access.onstatechange = () => this.attachToInputs()
    } catch (err) {
      this.onStatus?.({ connected: false, message: err instanceof Error ? err.message : String(err), deviceNames: [] })
    }
  }

  disconnect(): void {
    if (this.access) {
      this.access.onstatechange = null
      for (const input of this.access.inputs.values()) input.onmidimessage = null
    }
    this.access = null
    this.onStatus?.({ connected: false, deviceNames: [] })
  }

  private attachToInputs(): void {
    if (!this.access) return
    const names: string[] = []
    for (const input of this.access.inputs.values()) {
      names.push(input.name ?? input.id)
      input.onmidimessage = (e: MIDIMessageEvent) => this.handleMessage(e)
    }
    this.onStatus?.({ connected: true, deviceNames: names })
  }

  private handleMessage(e: MIDIMessageEvent): void {
    if (!e.data) return
    const msg = parseMidiMessage(e.data)
    const timeSec = e.timeStamp / 1000
    switch (msg.type) {
      case 'clock':
        this.clock.onClockTick(timeSec)
        break
      case 'start':
        this.clock.onStart()
        break
      case 'continue':
        this.clock.onContinue()
        break
      case 'stop':
        this.clock.onStop()
        break
      case 'controlChange':
        this.cc.onControlChange(msg)
        break
    }
  }

  getClockState(): MidiClockState {
    return this.clock.getState()
  }
}
