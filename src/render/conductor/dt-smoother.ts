// Attack/release smoothing driven by an explicit per-call dt (real elapsed
// frame time), rather than the AudioWorklet's EnvelopeFollower which bakes
// in a fixed hop period — the Conductor runs once per rendered frame, not
// once per fixed-size audio hop. Moved out of the old Choreographer.ts
// unchanged (SINTEZA_SIGNAL_BUS.md refactor) so both the Conductor and the
// patchbay's own route smoothing can share one implementation.
export class DtSmoother {
  private value = 0
  private initialized = false

  constructor(
    private attackSec: number,
    private releaseSec: number,
  ) {}

  update(input: number, dt: number): number {
    if (!this.initialized) {
      this.value = input
      this.initialized = true
      return this.value
    }
    const tau = input > this.value ? this.attackSec : this.releaseSec
    const coeff = Math.exp(-dt / tau)
    this.value = coeff * this.value + (1 - coeff) * input
    return this.value
  }
}
