// Generic damped harmonic oscillator: drives a value toward a target with
// mass/stiffness/damping dynamics instead of snapping directly to it.
// Underdamped (damping low relative to stiffness) produces overshoot — the
// "punch" the core thesis calls for. Every choreographed visual parameter
// should be driven through something like this, never read directly.
export class SpringDamper {
  private value: number
  private velocity = 0
  private target: number

  constructor(
    private stiffness = 120,
    private damping = 14,
    initial = 0,
  ) {
    this.value = initial
    this.target = initial
  }

  setTarget(target: number): void {
    this.target = target
  }

  // One-shot velocity kick — e.g. a drop's release burst.
  addImpulse(amount: number): void {
    this.velocity += amount
  }

  update(dt: number): number {
    const accel = (this.target - this.value) * this.stiffness - this.velocity * this.damping
    this.velocity += accel * dt
    this.value += this.velocity * dt
    return this.value
  }

  get current(): number {
    return this.value
  }
}
