export interface Vec2 {
  x: number
  y: number
}

// Shared idle path (SINTEZA_VIZ.md §4a/§4b): a slowly-drifting 3:2 Lissajous
// figure. The substrate's idle `c`-drift and the beam's idle trace both walk
// this same curve so the two layers read as one stationary dynamic, not two
// unrelated animations, when nothing is playing.
export function lissajousPoint(theta: number, phase: number, ax = 3, by = 2): Vec2 {
  return {
    x: Math.sin(ax * theta + phase),
    y: Math.sin(by * theta + phase * 0.5),
  }
}
