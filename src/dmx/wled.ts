// WLED's native realtime UDP protocol — master-prompt.md §5's #7 priority
// ("a friendly on-ramp for hobbyist LED strip users before they touch raw
// DMX... it rides on sACN"). WLED devices already speak real sACN/Art-Net
// natively (so `src/dmx/sacn.ts`/`artnet.ts` already reach them), but this
// is the genuinely simpler alternative the "friendly on-ramp" framing is
// actually about: no universe/DMX-address concepts at all, just "here are
// N pixels' worth of RGB bytes" straight to the device's own IP.
// Reference: https://kno.wled.ge/interfaces/udp-realtime/
export const WLED_DEFAULT_PORT = 21324

const PROTOCOL_WARLS = 1
const PROTOCOL_DRGB = 2

// DRGB: the simplest variant — sequential RGB triplets for LED 0, 1, 2, ...
// in order, no addressing at all. `rgb` is expected to already be a real
// multiple of 3 (typically the exact byte layout render-dmx-universe.ts
// already produces for a contiguous run of `rgb`-type fixture instances —
// this is why WLED output reuses that same renderer rather than needing
// its own pixel model).
export function encodeWledDrgb(rgb: Uint8Array, timeoutSec = 1): Uint8Array {
  const buf = new Uint8Array(2 + rgb.length)
  buf[0] = PROTOCOL_DRGB
  buf[1] = timeoutSec & 0xff
  buf.set(rgb, 2)
  return buf
}

export interface WledPixel {
  index: number // 0..255 — WARLS's single-byte index caps a run at 256 LEDs per packet
  r: number
  g: number
  b: number
}

// WARLS: explicit per-LED addressing — lets a caller update a sparse
// subset of pixels (or reorder them) without resending the whole strip,
// unlike DRGB's fixed sequential layout. Real use in this codebase is
// modest (nothing here currently produces sparse LED updates), but it's a
// real, spec-correct encoder in case a future fixture model wants it.
export function encodeWledWarls(pixels: WledPixel[], timeoutSec = 1): Uint8Array {
  const buf = new Uint8Array(2 + pixels.length * 4)
  buf[0] = PROTOCOL_WARLS
  buf[1] = timeoutSec & 0xff
  pixels.forEach((p, i) => {
    const offset = 2 + i * 4
    buf[offset] = p.index & 0xff
    buf[offset + 1] = p.r & 0xff
    buf[offset + 2] = p.g & 0xff
    buf[offset + 3] = p.b & 0xff
  })
  return buf
}
