import type { TargetDecl } from '../../types'

// SPEC ONLY (SINTEZA_SIGNAL_BUS.md §6.3, §8) — no runtime ServoOutput exists
// and none should be built as part of this pass. This file exists solely so
// the patchbay's validation (§5.3) has a second, physically-constrained
// output shape to prove the interface generalizes against: a servo
// physically cannot follow a `transient`/`beat` signal without buzzing/
// overheating, so `acceptsTags` excludes both — a config routing
// `onsetImpulse` or `beatPulse` to one of these must be rejected at load.
// Imported only by tests/unit/patchbay.spec.ts. Do NOT wire this into the
// output registry, a ServoOutput class, or any transport — that's explicitly
// later work (§8 item 1).
const SERVO_AXIS_COUNT = 4
const SERVO_RANGE_DEGREES: [number, number] = [-45, 45] // safe mechanical sweep, placeholder until real hardware is tuned
const SERVO_REST_ANGLE = 0

export const SERVO_TARGETS: TargetDecl[] = Array.from({ length: SERVO_AXIS_COUNT }, (_, i) => ({
  id: `servo.axis${i}`,
  acceptsTags: ['continuous', 'bar', 'section'],
  defaultValue: SERVO_REST_ANGLE,
  range: SERVO_RANGE_DEGREES,
}))
