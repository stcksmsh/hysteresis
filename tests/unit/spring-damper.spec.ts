import { describe, it, expect } from 'vitest'
import { SpringDamper } from '../../src/render/choreography/spring-damper'

function simulate(spring: SpringDamper, seconds: number, dt = 1 / 120): number[] {
  const steps = Math.round(seconds / dt)
  const values: number[] = []
  for (let i = 0; i < steps; i++) values.push(spring.update(dt))
  return values
}

describe('SpringDamper', () => {
  it('converges to its target over time', () => {
    const spring = new SpringDamper(90, 20, 0)
    spring.setTarget(1)
    const values = simulate(spring, 2)
    const last = values[values.length - 1]
    expect(last).toBeGreaterThan(0.95)
    expect(last).toBeLessThan(1.05)
  })

  it('overshoots when underdamped — the "punch" the design thesis calls for', () => {
    // Low damping relative to stiffness: critically damped would be damping = 2*sqrt(stiffness) ~= 19.
    const spring = new SpringDamper(90, 4, 0)
    spring.setTarget(1)
    const values = simulate(spring, 2)
    const max = Math.max(...values)
    expect(max).toBeGreaterThan(1.05) // genuinely overshoots past the target
  })

  it('does not overshoot when overdamped', () => {
    const spring = new SpringDamper(90, 60, 0)
    spring.setTarget(1)
    const values = simulate(spring, 2)
    const max = Math.max(...values)
    expect(max).toBeLessThanOrEqual(1.001)
  })

  it('an impulse produces a visible kick away from a settled value', () => {
    const spring = new SpringDamper(90, 10, 0)
    spring.setTarget(0)
    simulate(spring, 1) // settle at 0
    spring.addImpulse(20)
    const afterImpulse = spring.update(1 / 120)
    expect(afterImpulse).toBeGreaterThan(0)
  })
})
