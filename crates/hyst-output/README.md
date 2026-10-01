# hyst-output

Physical-output plumbing: `VizOutput` implementations for dense fields plus direct-clock
compiled-score playback. See `SINTEZA_IMPLEMENTATION_PLAN.md` §4 R5/R8 and
`SINTEZA_CHOREOGRAPHY.md` §0/§5.2/§5.3/§7.

## What's here

Shared plumbing, generic, not field-specific:
- `cadence::TickAccumulator` — converts irregular per-frame `dt` into whole fixed-period ticks
  (any output needing a cadence slower than render frame rate).
- `diff::DiffTracker<T>` — tracks last-sent value per index, reports only changed indices.
- `failure::FailureMask` — flat "is element i dead" table, injectable at runtime.

`FieldOutput` (dense physical arrays — Rozin-style tile/pin arrays, §5.3):
- `field::FieldSource` — trait `FieldOutput` samples through: `sample(u, v) -> FieldValue` +
  `advance(dt)` for time-varying sources. No renderer dependency. Ships three synthetic sources
  for testing: `BilinearGradient`, `Checkerboard`, `MovingGaussianBlob`.
- `array_topology::ArrayTopology` — element -> normalized `(u, v)` + channel id. Distinct from
  `hyst-choreo::Topology` (sparse-agent formations); no dependency on that crate.
- `field_output::FieldOutput` — `VizOutput` impl. Ticks its `FieldSource` at ~15 Hz
  (`DEFAULT_REFRESH_HZ`, independent of render frame rate), applies a pluggable
  `ElementMapping: Fn(FieldValue) -> f32` (brightness->tilt, value->orientation, whatever the
  rig needs), tracks a diff (`last_diff()`), and supports `mark_element_failed(index)` — a
  failed element freezes at its last value and is excluded from all further resampling; every
  other element keeps updating normally.

`ChoreographyOutput` (compiled single-arm score — §5.2):
- Owns validated `hyst_compile::Score`; samples score directly at absolute time. It does not use
  `VizOutput::update(dt)` or patchgraph because cue decisions are resolved offline.
- `sample_at(seconds)` is deterministic random access. Nonfinite input errors; finite values clamp
  to `[0, duration]`. Shared cue boundaries choose next cue metadata, except final endpoint.
- `sample_clock(clock, ClockPosition::Logical|Audible)` makes latency domain explicit. Logical
  source time leads output audio; audible time follows heard audio. Zero-rate clock errors.
- Validation mirrors exported-score audit: contiguous coverage, shared poses, bounded quintic
  speed/acceleration, exact anchor knots, immutable holds. It is artifact validation, not hardware
  safety, torque, calibration, or collision certification.

## Remaining field-renderer integration

R2 (`hyst-render`) doesn't exist yet as a finished renderer. `FieldSource` is the seam: once R2
has a real render target, add a `FieldSource` impl that reads it back (the same `wgpu` readback
path `OffscreenTarget::read_pixels` already exercises) and bilinearly samples at `(u, v)`.
`FieldOutput` needs no changes — only a new `FieldSource`.

## Verify

```
cargo test -p hyst-output
```

`field_output::tests::n100_field_exact_values_then_failure_injection_degrades_only_failed_tiles`
is the plan's mandatory acceptance test: N=100 elements, exact expected value per element against
a known bilinear field, 8 scattered failures injected, field then changes — failed elements stay
frozen, every other element tracks the new field exactly, nothing panics.
`diff_reports_only_the_element_that_actually_changed` is the diff-only-transmission test (a naive
"resend everything" impl fails it).

## Current limitations

- No real transport (Art-Net/serial/USB) — out of scope this session, `last_diff()` is as far as
  it goes.
- `FieldOutput::targets()` is empty — synthetic/self-driven sources only; a future
  bus-driven procedural `FieldSource` would declare routable targets.
- Element failure freezes at last value (no injectable custom "dead" value) — matches §7's "one
  wrong tile" requirement but is the only degradation policy implemented.
