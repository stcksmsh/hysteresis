import type { PatchTargetDecl } from './types'
import type { TimescaleTag } from '../types'

// A fixture TYPE describes the channel(s) any instance of it has — the
// static "shape" of a dimmer/servo/mover. Instances (fixture-document.ts)
// are the actual named things a user adds ("Stage Left Servo"), each
// contributing one PatchTargetDecl per channel to the graph's target
// catalog. New fixture types are additive: one entry here, no editor
// changes required to offer it.
export interface FixtureChannelSpec {
  readonly key: string
  readonly label: string
  readonly defaultValue: number
  readonly range: readonly [number, number]
  readonly acceptsTags: readonly TimescaleTag[]
  readonly unit?: string
}

export interface FixtureTypeSpec {
  readonly id: string
  readonly label: string
  readonly channels: readonly FixtureChannelSpec[]
}

// Servo-safety-style acceptance per channel kind (SINTEZA_SIGNAL_BUS.md
// §5.3's principle, applied to real moving/lighting hardware): a dimmer can
// safely flash on a transient (an LED has no inertia), a servo/mover
// physically cannot track a hi-hat and needs at least a threshold/envelope
// smoothing it first — the same distinction the spec draws for servos vs.
// screen targets, now actually enforced by fixture type instead of a single
// hardcoded example.
export const CONTINUOUS_ONLY: TimescaleTag[] = ['continuous', 'bar', 'section']
const ALL_TAGS: TimescaleTag[] = ['transient', 'beat', 'bar', 'section', 'continuous']

export const FIXTURE_TYPES: readonly FixtureTypeSpec[] = [
  {
    id: 'dimmer',
    label: 'Dimmer / LED',
    channels: [{ key: 'brightness', label: 'Brightness', defaultValue: 0, range: [0, 1], acceptsTags: ALL_TAGS, unit: '' }],
  },
  {
    id: 'rgb',
    label: 'RGB LED',
    channels: [
      { key: 'r', label: 'Red', defaultValue: 0, range: [0, 1], acceptsTags: ALL_TAGS },
      { key: 'g', label: 'Green', defaultValue: 0, range: [0, 1], acceptsTags: ALL_TAGS },
      { key: 'b', label: 'Blue', defaultValue: 0, range: [0, 1], acceptsTags: ALL_TAGS },
    ],
  },
  {
    id: 'servo',
    label: 'Servo',
    channels: [{ key: 'angle', label: 'Angle', defaultValue: 90, range: [0, 180], acceptsTags: CONTINUOUS_ONLY, unit: 'deg' }],
  },
  {
    id: 'mover',
    label: 'Moving light / laser',
    channels: [
      { key: 'pan', label: 'Pan', defaultValue: 0.5, range: [0, 1], acceptsTags: CONTINUOUS_ONLY },
      { key: 'tilt', label: 'Tilt', defaultValue: 0.5, range: [0, 1], acceptsTags: CONTINUOUS_ONLY },
      { key: 'intensity', label: 'Intensity', defaultValue: 0, range: [0, 1], acceptsTags: ALL_TAGS },
    ],
  },
]

export function getFixtureType(id: string): FixtureTypeSpec | undefined {
  return FIXTURE_TYPES.find((t) => t.id === id)
}

export function fixtureTargetId(instanceId: string, channelKey: string): string {
  return `fixture:${instanceId}.${channelKey}`
}

export function channelToTargetDecl(instanceId: string, instanceName: string, channel: FixtureChannelSpec): PatchTargetDecl {
  return {
    id: fixtureTargetId(instanceId, channel.key),
    label: `${instanceName} — ${channel.label}`,
    acceptsTags: channel.acceptsTags,
    defaultValue: channel.defaultValue,
    range: channel.range,
  }
}
