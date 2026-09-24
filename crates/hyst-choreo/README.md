# hyst-choreo

Choreography primitives: curves, `Move`, the procedural generator,
`Topology`, formation modes. Pure math/data — no sequencing, no hardware,
no rendering. Spec: `SINTEZA_CHOREOGRAPHY.md` §2-§3 (flagged in `AGENTS.md`
as directional, not verified-current — see Deviations below for what
needed judgment calls).

## Data model

- `curve.rs` — `Curve` enum (family + flavor + optional shape param), the
  standard Penner/easings.net set + `Square` + `Bezier(tension)`. `eval(t)`
  is the only op.
- `effort.rs` — `Effort { time, weight, space }`. No `Flow` field, per spec.
- `moves.rs` — `Move`: channels (`BTreeMap<ChannelRole, Curve>`), outer
  `Duration` (seconds or beats), entry/exit `PoseRequirement`,
  `arrival_anchor: Option<f64>` (future-arrival anticipation), `role`
  (Hit/Groove/Windup/Hold), `Effort`, free-form descriptive
  `applicability_tags`, `intensity`, `Provenance`.
- `generator.rs` — `generate_move`: primary population path. Own tiny
  xorshift64* `Rng` (deterministic, seeded) — no `rand` dependency added
  for this.
- `topology.rs` — `Topology { agents, order, neighbors, axis_pairs }`, plus
  a `Topology::ring(n)` convenience constructor used by tests.
- `formation.rs` — pure functions `(topology, base_move, anchor) -> Vec<AgentInstruction>`:
  `unison`, `canon`, `call_and_response`, `breathe`, `affine`, `scatter`,
  plus `apply_mirror` (composable, layered on top of any of the above) and
  `effective_order` (`OrderingSource::Spatial | SalienceAnchored` — one
  parameter, not two formation types).

`ChannelRole`: enum with named common roles (`PrimaryElevation`, etc.) plus
`Custom(String)` escape hatch — typed for the common path, open for
rig-specific/future channels.

## Verify

```
cargo test -p hyst-choreo
cargo clippy -p hyst-choreo --all-targets -- -D warnings
```

37 tests. Curve tests: every family's `f(0)=0`/`f(1)=1` (or, for
Back/Elastic/Bounce, the overshoot bound instead), monotonicity where
expected, one exact closed-form value per family. Generator tests: N=30
generated moves are structurally valid and span >1 curve family. Formation
tests: the R4 acceptance test — N=1/6/12 from identical inputs, N=1 is an
exact no-op for every mode (asserted equal to the unmodified base move,
not specially branched), N=6/12 canon offsets equal `i*(duration/n)`
exactly, call-and-response followers equal exactly one full duration.

## Deviations from spec (flagged, not guessed silently)

- `Square`'s "instant on/off" is implemented as a step at `t=0.5`
  (mid-duration snap), not at either edge — the spec doesn't pin down
  which; a step at t=0 or t=1 would make half the curve's domain
  meaningless.
- `Bezier(tension)`'s exact curve isn't specified beyond "single tension
  knob, matching REAPER's model." Implemented as a symmetric cubic Bezier
  in (t, v) with control points `(1/3, 1/3±tension)`/`(2/3, 2/3∓tension)`,
  solved via bisection. `tension=0.0` collapses exactly to `Linear`
  (verified, not incidental — this is the exact-value test for this
  family) and endpoints hold exactly for any tension in `[-0.5, 0.5]`.
- Mirror is modeled as data on `AgentInstruction` (`MirrorSpec`, which
  channels to value-invert) rather than mutating a `Move`'s curves —
  there's no evaluation/output engine in this crate to apply an inversion
  to, so "layerable, composable" is expressed as a post-processing
  function (`apply_mirror`) over already-computed instructions.
- `AgentInstruction` is one uniform struct across all formation modes
  (`mv`, `time_offset`, `mirror`, `target_pose`, `blend`) rather than a
  per-mode instruction type, so every mode is literally the same
  `(topology, base_move, anchor) -> Vec<AgentInstruction>` shape with
  unused fields left at their no-op default — this is what makes the N=1
  no-op fall out of one formula per mode instead of needing a match.

## Not here yet (by design, other workstreams)

- Sequencing / which formation is active when / transitions — R7 (Director).
- Nested sub-formations — explicitly deferred in spec §3.2.
- Hardware, serial, rendering, kinematics back-calculation — R7/R8/R10.
- Evaluating a `Move`'s curves into physical channel output (applying
  `MirrorSpec`, resolving `Pose`/`target_pose` blends into an actual
  value) — an output-layer concern (R5/R8), not this crate's.
