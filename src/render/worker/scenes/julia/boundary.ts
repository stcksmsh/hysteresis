export interface Vec2 {
  x: number
  y: number
}

// Exact parametrization of the Mandelbrot main cardioid's boundary:
// c(θ) = e^{iθ}/2 - e^{2iθ}/4. Every c on this curve sits exactly at the
// transition between a stable fixed point (dull, quickly-repeating Julia
// sets) and chaotic escape — which is precisely the "maximally interesting"
// territory a hand-picked constant + a spring can only approximate and
// easily overshoot out of. Sweeping θ continuously visits genuinely
// different, famous, always-rich Julia constants (θ=0 → c=0.25, the
// cauliflower; θ=π → c=-0.75, San Marco) forever without repeating on any
// timescale a session actually runs for.
export function cardioidPoint(theta: number): Vec2 {
  return {
    x: Math.cos(theta) / 2 - Math.cos(2 * theta) / 4,
    y: Math.sin(theta) / 2 - Math.sin(2 * theta) / 4,
  }
}
