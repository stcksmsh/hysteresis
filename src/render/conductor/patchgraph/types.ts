import type { RoutableSignalName, TimescaleTag } from '../types'

// The patch graph: a small, general dataflow model for PHYSICAL outputs
// (servos, LEDs, lasers, movers, ...) — deliberately separate from the
// screen's Patchbay/Route (SINTEZA_SIGNAL_BUS.md §5), which stays exactly
// as-is. That system is a flat 1-signal-in/1-target-out route model by
// design ("no logic beyond eval", §5) and the live visualizer depends on
// it working unchanged. Physical fixtures need real composability — "turn
// this LED on only when energy is high AND the low end is present" is an
// AND of two thresholded signals, which a flat route can't express at all.
// Rather than bend Route into something it isn't, this is a second,
// independent system built for that need from scratch.
//
// A graph is nodes + edges: `signal` nodes read the live SignalBus, chains
// of operator nodes combine/shape/gate values, and `target` nodes write the
// result to a fixture channel. Every node kind takes 0 or more named inputs
// (an ordered list of node ids to read from) and produces exactly one
// scalar output per frame — that's what makes arbitrary chaining possible
// without a bigger type system: every node is `(inputs: number[]) => number`
// plus its own params, only `signal`/`const` ignore inputs entirely.

export type NodeId = string

export interface NodeBase {
  readonly id: NodeId
  readonly inputs: readonly NodeId[]
  // Human-readable, freely renameable — `id` is the stable wiring key (an
  // edge/route persists across a rename since it references `id`, never
  // `label`) and stays opaque/auto-generated. A saved graph with no labels
  // (anything from before this field existed) still loads fine; a node
  // without one just displays its kind/id instead — see node-fields.tsx's
  // nodeSummary()/displayName() on the editor side.
  readonly label?: string
}

export interface SignalNode extends NodeBase {
  kind: 'signal'
  inputs: readonly []
  signal: RoutableSignalName
}

// A tunable constant — most operator params (a threshold cut, a gain) live
// inline on the node that uses them (kept as plain numbers, not their own
// nodes, so a simple threshold stays a single node to place/wire — "minimal
// patches" from the ask). `const` exists for the rarer case where a bare
// number needs to flow as a real graph edge (e.g. into a `combine` alongside
// real signals).
export interface ConstNode extends NodeBase {
  kind: 'const'
  inputs: readonly []
  value: number
}

// A live external MIDI CC value — the "control input: mapping a knob to a
// patch parameter" half of master-prompt.md §5's MIDI entry, finally
// routable the same way a bus signal is (see SignalNode above). `ccKey` is
// MidiCcInput's own "channel:controller" key format (src/midi/midi-cc-
// input.ts's ccKey()) — already normalized to 0..1, so it flows through the
// exact same curve/threshold/envelope/map chain a signal node would. Reads
// external per-frame state (PatchGraphEvaluator.evaluate's midiCc map, kept
// live by setMidiCc messages — src/index.ts's VizInstance.connectMidiIn and
// the patchbay editor's own MIDI panel both feed it), so this has zero
// inputs of its own, same shape as SignalNode.
export interface MidiCcNode extends NodeBase {
  kind: 'midiCc'
  inputs: readonly []
  ccKey: string
}

// A live incoming OSC message's value, addressed by its OSC address string
// (e.g. "/1/fader1") — the "OSC in" half of master-prompt.md §5's OSC
// entry (out has existed since the ISF/OSC session; in was explicitly
// deferred). Same external-state shape as MidiCcNode above: zero inputs,
// resolved from PatchGraphEvaluator.evaluate's oscIn map every frame,
// fed live by an OscInBridge (src/osc/osc-in-bridge.ts) decoding real OSC
// packets a relay forwards from the network. Only a message's first
// numeric-ish argument (float/int/bool) is ever stored — see
// OscInBridge's own doc comment for why a string-typed argument is
// dropped rather than coerced.
export interface OscInNode extends NodeBase {
  kind: 'oscIn'
  inputs: readonly []
  address: string
}

// Outputs 1 when input >= cut, else 0. `hysteresis` (if set) requires the
// input to fall to `cut - hysteresis` before it releases back to 0 — a
// dead-band around the cut point, essential for anything physical (an LED
// or servo chattering right at a threshold looks/sounds broken; a hair of
// hysteresis fixes it for free). This is real per-node state across frames
// (see PatchGraphEvaluator), unlike the stateless nodes below.
export interface ThresholdNode extends NodeBase {
  kind: 'threshold'
  inputs: readonly [NodeId]
  cut: number
  hysteresis?: number
}

// Attack/release envelope follower — same shape as the screen side's
// DtSmoother, reimplemented here rather than shared so this system has zero
// dependency on conductor-internal helpers (keeps the "separate layer"
// promise literal, not just organizational).
//
// inputs[0] is the value to smooth (required). inputs[1]/inputs[2]
// (optional — '' means "not connected", never a dangling reference) are a
// live override for attackSec/releaseSec respectively: wire a midiCc/oscIn
// node (through a `map` node to rescale its 0..1 into a real seconds
// range, same as any other target) in and a physical knob controls ease
// timing directly, instead of a knob only ever being able to drive a
// target's VALUE. Kept as extra input SLOTS rather than separate fields so
// topo-sort/PatchGraphEvaluator's existing generic dependency walk
// (`for (const inputId of node.inputs)`) already picks them up correctly
// — no evaluator-specific-casing needed for "this node kind has more than
// one dependency", the same mechanism combine/logic's N-input case already
// relies on. Always exactly 3 slots (not variable-length) specifically
// because slot POSITION is meaningful here (slot 1 is always "attack",
// slot 2 is always "release") — unlike combine/logic, where slot order
// never mattered.
export interface EnvelopeNode extends NodeBase {
  kind: 'envelope'
  inputs: readonly [NodeId, NodeId, NodeId]
  attackSec: number
  releaseSec: number
}

// Fuzzy logic over already-0..1-ish values (thresholded or not — and/or/not
// work on continuous inputs too, which is the point: "and" of two envelopes
// is exactly the kind of soft gating a real lighting rig wants, not just
// hard boolean logic). and = min(inputs), or = max(inputs), not = 1 - input
// (single input only).
export interface LogicNode extends NodeBase {
  kind: 'logic'
  op: 'and' | 'or' | 'not'
  inputs: readonly NodeId[]
}

// General numeric combine over 2+ inputs — separate from LogicNode because
// "sum these three band energies" and "gate this LED" are different intents
// even though `max`/`min` overlap; keeping them as distinct node kinds makes
// a saved graph read as what it means, not just what it computes.
export interface CombineNode extends NodeBase {
  kind: 'combine'
  op: 'add' | 'multiply' | 'max' | 'min'
  inputs: readonly NodeId[]
}

export type CurveKind = 'linear' | 'exp' | 'log' | 'smoothstep'

export interface CurveNode extends NodeBase {
  kind: 'curve'
  inputs: readonly [NodeId]
  curve: CurveKind
}

// General range remap (replaces gain/offset/invert as three separate knobs
// with one that reads as what it does: "this signal's 0..1 becomes the
// servo's 40..140 degrees", inversion is just outMin > outMax).
export interface MapNode extends NodeBase {
  kind: 'map'
  inputs: readonly [NodeId]
  inRange: readonly [number, number]
  outRange: readonly [number, number]
  clamp: boolean
}

// Writes to one fixture channel (SINTEZA_SIGNAL_BUS.md §6.1's TargetDecl,
// reused as-is — a physical channel is still "an id, accepted tags, a
// default, a range", the same concept the screen's targets already use).
export interface TargetNode extends NodeBase {
  kind: 'target'
  inputs: readonly [NodeId]
  targetId: string
}

export type PatchGraphNode =
  | SignalNode
  | ConstNode
  | MidiCcNode
  | OscInNode
  | ThresholdNode
  | EnvelopeNode
  | LogicNode
  | CombineNode
  | CurveNode
  | MapNode
  | TargetNode

export interface PatchGraph {
  readonly id: string
  readonly nodes: readonly PatchGraphNode[]
}

// A physical fixture's one channel — same shape/intent as the screen side's
// TargetDecl (SINTEZA_SIGNAL_BUS.md §6.1) so §5.3's servo-safety principle
// (a target declares which timescale tags it can safely follow) applies
// here too. `acceptsTags` is advisory in this graph (validated as a
// warning, not a hard construction-time throw like the screen Patchbay) —
// there's no real hardware yet to protect against buzzing/overheating, and
// a simulated preview shouldn't refuse to render just because a signal
// upstream hasn't been smoothed yet.
export interface PatchTargetDecl {
  readonly id: string
  // Optional, not required: this same type now also describes the screen's
  // own targets (SCREEN_TARGETS, conductor/types.ts's plain TargetDecl —
  // structurally compatible with this interface once `label` can be
  // absent), which never had a separate display label — screen target ids
  // already read fine on their own (`screen.hueShift`). Display code should
  // fall back to `.id` when this is absent (see node-fields.tsx's target
  // dropdown).
  readonly label?: string
  readonly acceptsTags: readonly TimescaleTag[]
  readonly defaultValue: number
  readonly range: readonly [number, number]
}
