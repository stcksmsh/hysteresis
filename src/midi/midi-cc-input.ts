import type { ControlChangeMessage } from './midi-messages'

// Live MIDI CC values, keyed by channel+controller — the "control input:
// mapping a knob to a patch parameter" half of master-prompt.md §5's MIDI
// entry. Normalizes MIDI's 0..127 resolution to the same 0..1 range every
// other patchable value in this codebase uses (signal bus fields, ISF
// inputs, fixture channels) so a MIDI CC can be routed through the exact
// same curve/gain/threshold nodes without a special case anywhere else.
export function ccKey(channel: number, controller: number): string {
  return `${channel}:${controller}`
}

export class MidiCcInput {
  private values = new Map<string, number>()
  // Set by learnNext()/consumed by the next incoming CC — the standard
  // "MIDI learn" UX: a user clicks "learn" on a target, then wiggles the
  // physical knob they want mapped, and the assignment happens from
  // whichever CC arrives next rather than requiring them to know its
  // number in advance.
  private pendingLearn: ((key: string) => void) | null = null

  // Optional observability hook, fired on every real CC message — this
  // class's own `get()`/`has()` are pull-only (no notion of "what just
  // changed"), which is fine for a patch graph reading it once per frame
  // but not enough for a live UI list of recent activity (the editor's
  // MidiPanel). Purely additive: omit it and this behaves exactly as
  // before this parameter existed.
  constructor(private onChange?: (key: string, value: number) => void) {}

  onControlChange(msg: ControlChangeMessage): void {
    const key = ccKey(msg.channel, msg.controller)
    const value = msg.value / 127
    this.values.set(key, value)
    this.onChange?.(key, value)
    if (this.pendingLearn) {
      const learn = this.pendingLearn
      this.pendingLearn = null
      learn(key)
    }
  }

  get(key: string): number {
    return this.values.get(key) ?? 0
  }

  has(key: string): boolean {
    return this.values.has(key)
  }

  // Resolves with the key of whichever CC arrives next. Cancel by calling
  // again with a no-op, or just ignore the eventual resolution.
  learnNext(onLearned: (key: string) => void): void {
    this.pendingLearn = onLearned
  }

  cancelLearn(): void {
    this.pendingLearn = null
  }
}
