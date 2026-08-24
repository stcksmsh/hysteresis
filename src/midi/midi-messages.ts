// Real MIDI 1.0 message parsing (channel voice + system realtime) —
// master-prompt.md §5's #5 priority protocol: "control input — mapping a
// knob to a patch parameter — and MIDI clock/beat sync from a DAW." Parses
// the raw byte arrays Web MIDI's `MIDIMessageEvent.data` (or any other
// source of real MIDI bytes) hands over — pure and framework-agnostic, no
// dependency on the Web MIDI API itself, so it's fully testable without a
// browser or a real device.

export interface ControlChangeMessage {
  type: 'controlChange'
  channel: number // 0..15
  controller: number // 0..127
  value: number // 0..127 (raw MIDI resolution — normalization is the caller's job, see midi-cc-input.ts)
}

export interface NoteMessage {
  type: 'noteOn' | 'noteOff'
  channel: number
  note: number
  velocity: number
}

// System realtime messages (single status byte, no data bytes) — the
// subset MIDI clock sync actually needs (§5's second MIDI use case).
export type RealtimeMessage = { type: 'clock' } | { type: 'start' } | { type: 'continue' } | { type: 'stop' }

export type MidiMessage = ControlChangeMessage | NoteMessage | RealtimeMessage | { type: 'unknown' }

const STATUS_NOTE_OFF = 0x80
const STATUS_NOTE_ON = 0x90
const STATUS_CONTROL_CHANGE = 0xb0
const STATUS_CLOCK = 0xf8
const STATUS_START = 0xfa
const STATUS_CONTINUE = 0xfb
const STATUS_STOP = 0xfc

export function parseMidiMessage(data: Uint8Array): MidiMessage {
  const status = data[0]
  if (status === undefined) return { type: 'unknown' }

  switch (status) {
    case STATUS_CLOCK:
      return { type: 'clock' }
    case STATUS_START:
      return { type: 'start' }
    case STATUS_CONTINUE:
      return { type: 'continue' }
    case STATUS_STOP:
      return { type: 'stop' }
  }

  const messageType = status & 0xf0
  const channel = status & 0x0f
  switch (messageType) {
    case STATUS_NOTE_OFF:
      return { type: 'noteOff', channel, note: data[1] ?? 0, velocity: data[2] ?? 0 }
    case STATUS_NOTE_ON: {
      const velocity = data[2] ?? 0
      // A note-on with velocity 0 is a running-status note-off, per spec —
      // real hardware/DAWs send this constantly to save a status byte.
      return { type: velocity === 0 ? 'noteOff' : 'noteOn', channel, note: data[1] ?? 0, velocity }
    }
    case STATUS_CONTROL_CHANGE:
      return { type: 'controlChange', channel, controller: data[1] ?? 0, value: data[2] ?? 0 }
    default:
      return { type: 'unknown' }
  }
}
