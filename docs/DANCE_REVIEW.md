# Hysteresis: from audio response to dancing

Review date: 2026-09-23. Target: `/home/stcksmsh/Programming/Github/Hysteresis`.

Status: proposal for discussion, not replacement for repo's authoritative plan. No target-repo files changed. Findings based on source inspection, existing session history, and research below; no new runtime, listening, hardware, or full-suite validation performed. One small numerical check reproduced repetition scorer's order invariance.

## Assessment

Project has useful foundations: audio clock, signal extraction, offline annotations, motion curves, ensemble topology, renderer. Missing central capability: composing coordinated movements into musical phrases. Completing plumbing alone will not establish dancing quality.

Working definition for first prototype: movement maintains an identifiable groove, selects musical accents, prepares for them, completes gestures, preserves continuity, and revisits recognizable motifs. Human judgment must validate this; no single numerical score proves dance quality.

## Findings against actual code

| Area | Evidence | Consequence |
| --- | --- | --- |
| Choreography execution | `crates/hyst-compile/src/lib.rs`, `hyst-previz/src/lib.rs`, `hyst-hw/src/lib.rs` are stubs; `hyst-cli/src/main.rs` prints unimplemented message. `hyst-output/src/lib.rs` exports field output, no choreography output. | Native physical dancing path does not exist end to end. |
| Move generation | `hyst-choreo/src/generator.rs:109` chooses independent curves per channel, then random role, Effort, tags, intensity. | Labels do not constrain movement. A generated Hold receives same curve-selection process as a Hit. No coordinated movement vocabulary yet. |
| Move representation | `hyst-choreo/src/moves.rs:82`: one curve per channel; entry/exit poses; end-of-move arrival timestamp. | Useful tween primitive. Missing explicit multi-stage gestures, internal accent markers, repeatable cycles, and endpoint velocity/acceleration constraints. |
| Expressiveness | `hyst-choreo/src/effort.rs` stores three values and checks bounds. Repository references show no trajectory transformation using them. | Effort currently metadata, not implemented movement quality. |
| Formations | `hyst-choreo/src/formation.rs` emits copies, offsets, mirrors, pose targets. | Useful ensemble foundation. Does not choose or connect musical gestures. More synchronized arbitrary movement remains arbitrary movement. |
| Musical annotations | `scripts/analyze.ts` calls schema-3 `analyzeMix`; schema-4 `computeSchema4Sidecar` exists separately in `scripts/repetition.ts`. | Repetition-aware path is not exposed through normal analysis CLI. Stem and schema-4 paths need deliberate integration. |
| Beat/downbeat assumptions | `scripts/structure.ts` collects causal tracker wraps; Rust `BarTracker` assumes four beats and strongest onset slot. | Beat and bar estimates need verification, confidence, and correction. Musical phrasing cannot depend on unreviewed bar guesses. |
| Repetition | `scripts/ssm.ts:172` averages all cross-section pair similarities; adjacent sections skipped. | This score ignores order within each section. Similar timbre/energy is insufficient evidence of same phrase. Immediate repeats are excluded. |
| Attention | Stem presence in `scripts/structure.ts` uses independently normalized RMS envelopes; lead estimate uses spectral heuristic. | Presence is useful evidence, not direct measurement of what listener attends to. Taking maximum normalized stem value is not reliable salience ranking. |
| Serialization | `hyst-core/src/sidecar.rs:66` lacks camelCase rename for optional `boundary_confidence`, while TS emits `boundaryConfidence`. | This field is silently ignored on TS→Rust input; Rust-only round-trip test misses cross-language contract gap. Other main sidecar fields do have camelCase mapping. |

Repetition check: for vectors `[(1,0),(0,1)]`, current cross-block averaging gives 0.5 both for exact repeat and reversed order. More generally, summing every pair is permutation-invariant. This does not make similarity useless; it means it should propose candidates, not certify phrase identity. Add aligned sequence comparison and shuffled-order controls before using repeats to reuse choreography.

Docs deserve reconciliation. `SINTEZA_CHOREOGRAPHY.md` already asks for anticipation, salience, ensemble relations, structural memory, and groove without hit effects. Current implementation plan nevertheless calls renderer/autopilot its critical path. For user's current goal, movement audition becomes critical path. Session history records renderer improvements beyond older status summaries; code remains strongest evidence of what exists.

## Proposed movement model

Preserve curve math as interpolation machinery. Compose curves into gestures with shared structure across joints:

`preparation → accent → follow-through → recovery / next gesture`

An accent may be an extension, reversal, passing motion, or deliberate stop. It need not coincide with gesture end. Replace end-only scheduling assumption with semantic markers: choose which moment aligns to musical event, while reserving space before and after it.

First vocabulary, proposed for simulated articulated arm:

- Pulse: compact repeating compression/extension around resting pose.
- Sway: slower lateral arc, coordinated with pulse.
- Reach/retract: preparation, directional extension, controlled recovery.
- Coil/release: compact accumulation then opening across joints.
- Sweep: traveling gesture with sustained direction.
- Suspend: intentional stillness with defined re-entry.

Generation remains primary: generate variations inside these families. Couple joints through common gesture phase and controlled lag; vary amplitude, direction, preparation length, accent placement, recovery, and rhythm. Derive tags from selected family/parameters. Curate a small useful vocabulary rather than randomizing labels independently of curves.

Use one simulated body initially. Abstract roles alone cannot guarantee identical perceptual gestures across geometries. Rig descriptor should include hierarchy, joint axes, segment lengths, neutral pose, ranges, dynamic limits, and supported gesture capabilities. First prototype can use joint-space coordinated motion and forward kinematics; general inverse kinematics need not block it. Missing axes require explicit gesture adaptation or rejection.

## Musical decisions

Separate three timescales:

1. Pulse: continuous phase, subdivision, half/double-time choices. Preserve groove between accents.
2. Motif: recognizable multi-beat movement pattern; repeat with bounded variation. Persist long enough to become legible.
3. Phrase/section: choose direction, effort, attention, motif development, rest, and occasional ensemble changes.

Choose sparse accents rather than assigning movement to every onset. A sustained melodic line can lead a reach while pulse continues quietly underneath. Attention should have minimum dwell time and switching hysteresis so tiny changes in stem estimates do not redirect body every frame. Avoid forcing one musical interpretation from amplitude alone.

Store music time as beat positions mapped through actual beat timestamps, not only beat counts multiplied by global average tempo. Preserve downbeats, phrase labels, confidence/provenance, and manual overrides. Short-term groove can use periodic phase; compiler must handle local tempo changes explicitly.

First annotated example may assume reviewed 4/4 track. Keep this assumption visible; do not claim arbitrary meter support.

Live prediction is possible even without exact future knowledge. Existing docs overstate impossibility. A live system can predict pulse, sustain motifs, and prepare likely accents with confidence-dependent commitment; it cannot guarantee an unforeseen fill or drop. Known-track compilation remains easiest first demonstration. Live separation is outside current scope, not universally impossible.

## Compiler and physical timing

Proposed flow:

`reviewed musical timeline → motif/gesture choices → continuity-aware transitions → feasible trajectories → deterministic playback + preview`

Start with explicit rules plus scored candidate selection. Reward chosen accent alignment, motif continuity, phrase fit, and readable contrast. Penalize transition cost, saturation, excessive change, and unsupported gestures. Seeded variation makes comparisons reproducible. Add more elaborate search only when a small rule system exposes specific limitations.

Carry position, velocity, and acceleration through joins. Ending every gesture at rest creates stop-start motion; blending incompatible directions can erase intended accents. Periodic grooves need matching boundary state. Springs can shape follow-through, but damping arbitrary joint signals cannot supply composition.

Plan within physical limits before playback. Simply starting infeasible curve earlier does not reduce required velocity/acceleration. Starting earlier helps only if trajectory gains travel time and compatible preparation is available. When deadline impossible, reduce excursion, change gesture, or omit accent. Keep runtime limits as final protection; do not depend on routine clamping for aesthetic motion.

Separate known transport delay from physical travel. Simulate resulting trajectories, then measure command-to-visible-motion timing on actual rig. Position limits, collision checks, torque/load limits, and actuator tracking remain separate from a velocity/acceleration/jerk planner.

## First deliverable and build sequence

First deliverable: synchronized 30–60 second preview of one simple articulated arm on one real track, containing ordinary groove, a transition, and motif recurrence. Hardware geometry remains provisional until user chooses form.

1. **Movement audition.** Small native preview drawing actual segment geometry. Display beat, gesture phase, accent markers, and timing. Compare direct audio mapping, uniform pulse, and coordinated motif under identical music/body/amplitude budget. This is proposed scope change from old simultaneous multi-paradigm previz milestone.
2. **Minimal motion vocabulary.** Implement gesture phases, coupled joints, internal accent anchors, stable groove cycle, and continuity. Start with three strong families; expand only after watching.
3. **Reviewed musical timeline.** Manually correct beats/downbeats and mark a few phrase boundaries/accents for selected excerpt. This gives trusted input while analysis improves. Integrate schema-4 CLI + cross-language fixture checks separately; installation of large MIR stack should not block first motion result.
4. **Small compiler + playback.** Produce deterministic score from reviewed timeline, motifs, transition rules, and provisional rig limits. Compile a baseline and a few constrained variations; preserve edits when regenerating unrelated phrases.
5. **Musicality review.** Watch complete phrase, not isolated impressive hit. Repeat on another excerpt with different groove. Update movement rules from observed failures.
6. **Ensemble, then measured hardware.** Add second arm for call/response and mirrors; then larger topology. Trial one actuator/arm to calibrate actual ranges and timing before scaling.

Implementation changes would cross `hyst-choreo`, `hyst-previz`, `hyst-compile`, `hyst-output`, plus shared score/rig types. Repo's existing crate-boundary rule means this proposal needs an agreed integration slice before implementation. Analysis itself required no edits or exception.

## Acceptance checks

- Without music: gestures still have coherent preparation, direction, completion, and transitions. This tests body coherence, not musicality.
- With music: chosen accents read intentional; arm sustains groove when large hit/windup effects disabled.
- Repetition: viewer recognizes returning motif; variation preserves identity.
- Restraint: holds and omitted accents feel deliberate; quiet sections need not become constant filler motion.
- Comparison: same body + audio + comparable movement range; randomize presentation order. Ask which version appears to listen and which motion belongs to which musical phrase.
- Timing control: shift soundtrack by fraction of beat and compare. Useful diagnostic for alignment, not proof of overall dance quality.
- Numeric checks: marked accent timing, boundary continuity, feasible joint range/velocity/acceleration/jerk, deterministic replay/seeking. Use timestamp tolerance tied to display/control resolution; hardware tolerance requires measurement.
- Analysis checks: same phrase vs reordered controls, double/half-tempo errors, corrected downbeats, TS-produced schema-4 fixture loaded by Rust including optional fields.

## Research informing proposal

[Gao et al., gesture-based musical synchronization with Shimon (2024)](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2024.1461615/full) uses coordinated head/neck movement, delayed follow-through, and preparatory communication. Study supports value of anticipatory gestures in musical interaction; it does not establish universal recipe for dancing arms. Inspiration here: coordinated timing across simple joints can carry readable intent.

[AI Choreographer / AIST++ (Google Research, 2021)](https://research.google/blog/music-conditioned-3d-dance-generation-with-aist/) conditions generated human dance on both music and seed motion, and evaluates motion quality, diversity, alignment, and human judgments. For this repo, mapping full-body output to sparse arm remains separate problem. Start with explicit controllable motifs; learned motion retrieval or generation can supply candidates later.

[The Dancing Swarm (Gobec et al., 2026)](https://doi.org/10.1145/3776734.3794497) reports study of 17 participants where Time/Space mappings were recognized better than Weight/Flow. Repo cites this as 2025; bibliographic record says 2026. Evidence supports testing perceptual mappings, not treating Effort scalars as solved expression controls or extending swarm findings automatically to articulated arms.

[Ruckig official documentation](https://github.com/pantor/ruckig) describes trajectories constrained by velocity, acceleration, jerk, and endpoint state. Its minimum-duration option is not exact musical deadline guarantee. Worth evaluating as trajectory backend once gesture requirements are clear; it cannot select choreography or establish physical feasibility beyond its model.
