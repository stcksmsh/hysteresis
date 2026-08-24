import { encodeEnttecDmxPacket, ENTTEC_BAUD_RATE } from './enttec-usb-pro'

export interface DmxSerialStatus {
  connected: boolean
  message?: string
}

// The ONE genuinely browser-native leg of this whole DMX arc — no relay
// process needed, unlike Art-Net/sACN/OSC (dmx-out-bridge.ts,
// osc-out-bridge.ts), because the Web Serial API gives real serial port
// access straight from the browser. The real cost lives in support
// breadth, not architecture: Web Serial is Chromium-desktop-only (no
// Safari — an explicit position over fingerprinting concerns per
// master-prompt.md §3 — and no mobile at all), so `isSupported()` exists
// specifically so a caller can show a clear message instead of a silent
// failure on every other browser.
export function isWebSerialSupported(): boolean {
  return typeof navigator !== 'undefined' && 'serial' in navigator
}

export class DmxSerialOutput {
  private port: SerialPort | null = null
  private writer: WritableStreamDefaultWriter<Uint8Array> | null = null

  constructor(private onStatus?: (status: DmxSerialStatus) => void) {}

  // Must be called from within a user gesture handler (a click) — the
  // browser's own requirement for navigator.serial.requestPort(), not
  // something this class can work around.
  async connect(): Promise<void> {
    if (!isWebSerialSupported()) {
      this.onStatus?.({ connected: false, message: 'Web Serial is not supported in this browser (Chromium desktop only)' })
      return
    }
    try {
      const port = await navigator.serial.requestPort()
      await port.open({ baudRate: ENTTEC_BAUD_RATE })
      this.port = port
      this.writer = port.writable?.getWriter() ?? null
      this.onStatus?.({ connected: true })
    } catch (err) {
      this.onStatus?.({ connected: false, message: err instanceof Error ? err.message : String(err) })
    }
  }

  async disconnect(): Promise<void> {
    try {
      this.writer?.releaseLock()
      await this.port?.close()
    } catch {
      // best-effort — a port already gone (device unplugged) throws here,
      // nothing further to clean up either way
    }
    this.port = null
    this.writer = null
    this.onStatus?.({ connected: false })
  }

  // No-op (not an error) when not connected yet/anymore — same posture as
  // OscOutBridge/DmxOutBridge's own send(), called from a render-loop-style
  // interval that shouldn't need to know connection state itself.
  async send(universe: Uint8Array): Promise<void> {
    if (!this.writer) return
    try {
      await this.writer.write(encodeEnttecDmxPacket(universe))
    } catch (err) {
      this.onStatus?.({ connected: false, message: err instanceof Error ? err.message : String(err) })
      this.port = null
      this.writer = null
    }
  }
}
