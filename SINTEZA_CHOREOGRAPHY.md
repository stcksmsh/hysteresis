# СИНТЕЗА — physical output: choreography, fields, and rig-agnosticism

Repo: `hysteresis`
Status: design spec, not yet implemented. Companion to `AGENTS.md` (architecture) and
`SINTEZA_OFFLINE_SSM.md` (the structural analysis this layer consumes). Targets a new
subsystem — nothing here modifies the screen/patchgraph/live-detector code that already
ships.

Read `AGENTS.md` §2/§4 and `SINTEZA_OFFLINE_SSM.md` first. This assumes: the conductor→bus→
patchgraph→output architecture, the schema-4 sidecar (structure, repetition map, per-stem
presence envelopes), and the live-vs-sidecar/LIVE-CAPABLE-vs-SIDECAR-ONLY discipline already
established throughout this project.

---

## 0. Scope: rig-agnosticism is the point

The deliverable is **not one installation** — it is a system configurable into many physical
shapes (a ring of expressive arms, a dense planar array, a line, a hanging grid), sharing one
audio-understanding stack. The first rig built gets the most polish because it shows first, but
rig-agnosticism is the project's throughline, not a later generalization. Every design choice
below is evaluated against that.

**Research (Rozin's mechanical mirrors; entertainment show-control practice) established that
there are two genuinely different physical control paradigms, and forcing one abstraction over
both is the mistake to avoid:**

| | **Sparse expressive agents** | **Dense element arrays** |
|---|---|---|
| Example | ring of multi-DOF arms | Rozin-style tile/pin array |
| Element count | few (1–12) | many (100s) |
| DOF per element | several | typically one |
| Authored unit | a *gesture* (move + formation) | a *field/image* mapped across elements |
| Relation between elements | explicit (unison/canon/mirror) | implicit — only via the field |
| Output | `ChoreographyOutput` (§4) | `FieldOutput` (§5.3) |

Rozin's mirrors work by reducing a camera image to a coarse bitmap and setting each tile's pivot
angle from the average brightness of its patch, refreshing ~15×/sec — every element is one DOF
driven by a scalar, with no inter-element relationship except through the image. Later works
(*Angles Mirror*) map to pin *orientation* forming contour rather than brightness — same
paradigm, different mapping. This is not choreography and must not be modelled as it: doing so
would mean authoring hundreds of near-identical "moves" whose entire content is one scalar.

**Both paradigms are `VizOutput` peers sharing the entire upstream stack** (bus, sidecar,
structural analysis) — exactly the pattern `ScreenOutput`/`FixtureOutput` already establish.
The payoff of separating them: a field is something the screen pipeline *already produces* (the
memory field, the Julia substrate), so **a dense array is literally a low-resolution physical
render target for the existing visual layer** rather than a new authoring burden.

§§1–4 below specify the choreography paradigm. §5.3 specifies the field paradigm. §§6–9 apply
to both.

---

## 1. What "dancing" means here, precisely

Not: reactive-to-BPM, energy-driven amplitude. Dancing requires, and this doc is organized
around delivering:

1. **Anticipation** — motion that begins before a known event and arrives at it, not motion
   triggered by the event.
2. **Salience-following** — attention (which agent is "featured," what it's doing) tracks the
   most prominent musical element right now, not just how loud things are.
3. **Ensemble relation** — agents relate to each other (unison, canon, mirror, shared breathing),
   not N independent reactors. Closer to synchronized swimming than solo dance.
4. **Structural memory** — a repeated section is recognized and can echo its own earlier
   choreography; a long section evolves rather than looping identically.

The organizing principle, carried directly from every other layer of this project:

> **Anticipation and salience-following require knowing the future. A live system cannot know
> the future. Therefore: for known tracks, choreography is compiled offline, once, with the
> whole song available, into a complete timeline. Live/unknown audio gets a much simpler,
> honestly-limited, reactive fallback.**

This is the sidecar-primary/live-fallback split (already used for drops, structure, and stem
presence) applied one layer up, and it is what makes genuine anticipation possible at all rather
than aspirational.

---

## 2. The move primitive

The atomic unit of authored/generated motion. Designed so a hand-posed gesture and a
procedurally-generated one are indistinguishable to everything downstream.

**Agent-local, count-agnostic.** A move is defined for *one* agent, in normalized local space.
It has no knowledge of how many agents exist or where they sit — that's the formation layer's
job entirely (§3). This is what makes "design for one arm, extend to many" literal rather than
aspirational: an N=1 rig is N=1 with no formation relation active, not a special case.

**DOF are named channel roles, not hardcoded servo axes** — e.g. `primaryElevation`,
`secondaryRotation`, `accentLightIntensity`, `accentLightHue`. Bound to real physical channels
at the output layer, the same target-declaration pattern `VizOutput` already uses. A move plays
identically on a one-DOF test rig (unused roles idle) and a full arm+head+LED rig; adding a
laser or second LED ring later never touches the move format.

**Every channel is a small parametric curve over local, normalized time (`t ∈ [0,1]`), with
duration as a separate outer parameter.** The curve doesn't know how long it takes; a move gets
stretched/compressed to whatever duration it's scheduled with (seconds or, for tempo-locked
moves, bars/beats). This is what makes hand-tuning *and* procedural generation both cheap: a
curve is a few numbers to turn, and perturbing one of those numbers yields a meaningfully
related variant rather than noise. Physical capture (posing an arm) means "record keyframes, fit
to this curve vocabulary," not "record and store a raw sample array."

### 2.1 The curve corpus

Merged from three converged traditions rather than invented: DAW automation (REAPER's
linear/square/slow-start-end/fast-start/fast-end/bezier+tension), the Penner/`easings.net`
animation-standard set (ten families × in/out/in-out), and industrial motion control's
jerk-limited S-curve (a physical-validity concern, not an aesthetic option — see §6).

- **Linear** — the null case; baseline reference, and for deliberately mechanical accents.
- **Sine, Quad, Cubic, Quart, Quint** (in/out/in-out each) — the graduated "how aggressive"
  ladder; the main organic-motion palette. 15 meaningfully distinct feels from one family.
- **Expo, Circ** (in/out/in-out) — sharper, punchier accents without full overshoot.
- **Back** (in/out/in-out) — deliberate overshoot-then-settle; gives a "reach" gesture weight
  and intent rather than a flat arrival.
- **Elastic, Bounce** (in/out/in-out) — springy/wobbling settle. Use deliberately and sparingly
  — overused on a physical arm reads as mechanical failure, not liveliness.
- **Square** — instant on/off. For light/LED channels specifically, where a hard snap is often
  *more* correct than any eased curve.
- **Bezier(tension)** — one general escape hatch (single tension knob, matching REAPER's own
  model) for anything that doesn't fit a named family, so the vocabulary never needs a new
  entry just to get a slightly different shape.

Represented as a small discriminated union, not a flat enum — `{ family: 'quad', flavor: 'out'
}`, `{ family: 'back', flavor: 'in', overshoot: 1.2 }`, `{ family: 'bezier', tension: 0.4 }` —
so a generator's job is "pick a family, pick a flavor, perturb the optional shape parameter,"
not "choose from 30 unrelated cases."

### 2.2 Other move fields

- **Entry/exit pose**: either a required starting pose (chains only from a compatible
  predecessor, or needs a transition inserted) or entry-agnostic (blends from wherever the
  agent currently is).
- **Future-arrival anchor**: a move's *end* can be pinned to a known future timestamp rather
  than a fixed offset from now — "wind up over the next 2 bars, land exactly on the drop." This
  is the literal anticipation mechanic, expressible as data, not a hack.
- **Timescale/role tag**: `hit` (bounded, keyed to a specific event), `groove` (sustained,
  looping-but-varied filler — keeps the ensemble visibly alive between hits, the physical
  analogue of the screen's continuous-signal fix), `windup` (spans toward a known future event),
  `hold` (deliberate stillness — a first-class choice, not an absence of movement; the physical
  analogue of the ninth-movement locked groove and the memory-field's post-drop ghost).
- **Effort vector — movement *quality*, the missing dimension** (added after research). Laban
  Movement Analysis (LMA) describes movement quality via four Motion Factors, each with two
  polarities: Time (sudden–sustained), Weight (strong–light), Space (direct–indirect), Flow
  (free–bound). Robotics research has already reduced this to a tractable form for **low-DOF,
  non-humanlike platforms** — exactly a servo arm — with computational definitions (Cui, Maguire
  & LaViers, *Robotics* 8(2):24, 2019), validated by a certified movement analyst plus lay-viewer
  studies (word accuracy up to 77%, context accuracy up to 83%):
  - **Time** → the number of local extrema in the velocity profile. More extrema = more "sudden";
    fewer = "sustained".
  - **Weight** → displacement of the path relative to a neutral reference (they bend waypoints
    toward/away from gravity; here: amplitude/extension bias).
  - **Space** → heading variation en route. Direct = few or no heading changes toward the target;
    Indirect = more heading changes while travelling there.
  - **Flow is deliberately dropped** — the source work excludes it because Flow has no spatial
    correlate and low-DOF platforms cannot express it. Do not attempt it.

  Model this as a **three-scalar modifier applied over any move**, not as separate moves. One
  "reach" gesture with a quality dial beats authoring gentle-reach and sharp-reach separately,
  and it is exactly the meaningful-variation axis a generator needs (§2's population strategy).
  The Director (§4) can then differentiate sections without new moves: a build ramps Time toward
  sudden; a breakdown goes light and indirect.

  **At ensemble scale, prioritise Space and Time.** A user study mapping Effort onto swarm
  behaviour found Space and Time were recognised significantly better than Weight and Flow
  (*The Dancing Swarm*, HRI '25 companion). Treat Weight as a per-agent refinement.

  **Caution from the same work**: a CMA observing constant-parameter motion perceived *three*
  Effort configurations where one was authored — quality reads as changing over time even when
  held constant. Do not over-author quality changes; the observer supplies some.

- **Applicability tags**: which salience role a move suits (vocal-lead, bass-anchor,
  ambient-fill), whether it only makes sense inside a specific formation (a "canon-source" move
  only as a wave's origin). This is what lets the Director (§4) search the library
  algorithmically rather than needing a hand-written lookup table. **Use descriptive, not
  emotive, tags** — the LMA robotics work argues explicitly that emotive models are limited and
  soon outmoded, since movement is inherently expressive with subjective, contextual
  interpretation; it uses descriptive words ("clear", "puffy") instead. So tag moves as
  sharp//floating/coiled, never angry/joyful. This also fits the project's machine-native,
  non-sentimental aesthetic.
- **Intensity**: one scalar amplitude/tempo-scale multiplier — "the same reach, bigger, because
  the piece has built" — without authoring N duplicate moves. Same variance-serves-the-line
  principle as production velocity/timing work.
- **Provenance**: authored / generated / generated-then-edited. Pure workflow bookkeeping — the
  taste-gate record, same role played on the AI-generated album, for gestures instead of
  arrangement.

**Population strategy (per user decision): systemic generation is primary.** The library is
machine-produced (procedurally varying curve families/parameters within the schema above); hand
authoring is for injecting or correcting a specific gesture, not the default path. You curate,
the same relationship as the AI-album project.

---

## 3. The formation / relational grammar

A **Formation** is a pure function: `(topology, chosen base move, timing anchor) → per-agent
instructions`. It never references a literal agent — only topology positions and roles — so it
generalizes to any agent count without re-authoring, and grounds directly in swarm-robotics
formation control (leader-follower, virtual-structure/affine formation) rather than being
invented from nothing.

### 3.1 Ensemble Topology

The one new piece of shared data, defined once per physical rig:
```
Topology {
  agents: AgentId[]
  order: AgentId[]                       // propagation sequence for wave/canon
  neighbors: Record<AgentId, AgentId[]>  // adjacency (ring: ±1)
  axisPairs?: [AgentId, AgentId][]       // mirror pairing, if a symmetry axis exists
}
```
Kept generic on purpose. If the physical layout changes (ring → line → cluster), only this
descriptor changes; no formation logic touches a literal position.

### 3.2 Formation modes

**Timing-synchrony** (same move, offset in time): **Unison** (zero offset). **Canon/wave**
(offset by a fraction of move duration, propagating along `order`). **Call-and-response** (a
leader plays first; everyone answers after a full move-length delay).

**Parameter-synchrony** (different, independent moves, one shared modulated parameter):
**Breathe/converge-diverge** (amplitude scales together from one shared envelope — the ring
visibly inhales/exhales even though each arm's actual gesture differs). **Affine/reference-shape**
(the ensemble maps onto a shared target shape — lean toward center, flatten, expand — the direct
analogue of swarm robotics' affine formation control).

**Mirror** — a spatial transform (reflect spatial move parameters across a topology axis),
layerable on top of either category above.

**Scatter/independent** — the null formation, and it must be first-class, not a fallback: each
agent runs its own move selection with zero shared transform. This is what most of a groove
section actually looks like; a ring locked in unison/canon constantly reads as gimmicky fast —
independent variation is what makes a *return* to unison land as a moment.

**Ordering source — spatial vs. salience-anchored.** A canon's propagation sequence can follow
fixed `order` (deterministic, position-based) or originate from whichever agent's role
assignment currently holds the highest-priority signal, propagating outward by topology
distance. Same fixed-vs-dynamic duality as role assignment itself (§4) — one parameter on the
formation, not two formation types. Default: salience-anchored.

**Explicitly deferred, not designed now**: nested sub-formations (groups within groups, real
corps-de-ballet practice) — the topology-based design makes this a natural later extension (a
group is a sub-topology), not a redesign, but it isn't needed at current arm counts.

**What does NOT live here**: which formation is active when, and how transitions sequence —
that's the Director's job (§4). This layer only guarantees formations are clean, composable,
swappable states.

---

## 4. The Director

### 4.1 The core split

**Compiled** (own tracks, sidecar available) vs. **live** (unknown audio, no lookahead). Not two
implementations of the same thing — genuinely different scope, matching every other
LIVE-CAPABLE/SIDECAR-ONLY split in this project.

### 4.2 Compiled mode — an offline compiler, not a runtime system

Given the full schema-4 sidecar (structure, repetition map, presence envelopes) plus the move
library (§2) and formation grammar (§3), runs **once**, offline, with the whole song known, and
emits a complete **Choreography Score** — every agent's move/formation/role resolved for the
entire track, before playback ever starts. This is the only way real anticipation happens; it
cannot be done live. Same review discipline as sidecar structure: watch it once, hand-correct
the few spots that read wrong, ship.

**Decision cadence, nested with the structural layers already computed:**
- **Section-level** (SSM boundaries): overall character — intro→scatter/idle, build→canon with
  rising intensity, drop→unison hit, breakdown→hold or slow breathe.
- **Phrase-level** (local novelty peaks, bar boundaries): rotate the specific move within a
  section every few bars — the physical form of "break section loops so each bar is its own
  copy," applied to gesture instead of MIDI. **Acceptance test, matching the screen work's own
  brutal check: strip every hit/windup special case — does the groove still look alive?** If
  scatter mode goes inert between events, this section of the compiler has failed exactly the
  way the pre-fix screen failed.
- **Hit-level** (exact drop/downbeat times): windup moves anchored to arrive precisely at a
  known future timestamp via §2.2's future-arrival mechanic.
- **Role/salience layer** (cross-cutting): since presence envelopes exist for the whole track,
  role assignment is *also* fully compiled — computed once from the full envelope, baked into
  the score. Dynamic assignment with zero runtime cost.

**Repetition-map reuse-vs-vary**: when a section is flagged as a repeat, the compiler chooses
(a compiler parameter, not a hardcoded default) to replay the earlier section's exact
choreography (reinforces "this was rehearsed") or deliberately vary it (evolution).

**Generation, not hand-authorship, is the primary path here too** — the compiler is itself the
generative system; you're the taste gate on its output, the same relationship as §2's library
population and the AI-album project generally.

### 4.3 Live mode — deliberately much simpler

No presence signals exist live (no separation is possible — an established, honest limitation,
not a bug). Therefore genuine salience-based role assignment **cannot** happen live, full stop.
The fallback is a handful of simple reactive formulas — each agent's target as a function of its
own phase offset plus shared live bus signals (`energy`, `dropImpulse`, `bandTilt`) — no move
library, no formation grammar, no compiler involved. "Good enough to look alive" is the honest
bar, matching every other live fallback in this project (the drop detector, the screen's live
novelty).

---

## 5. Execution — where this plugs into the existing architecture

### 5.1 The good news: no new patch-graph node family is required

An earlier status-report concern was that the reactive, per-frame bus/patchgraph stack
fundamentally fights a lookahead choreography model. That concern is correct *if* choreography
stayed live-reactive — but §4.2's choice (fully resolve everything offline) sidesteps it: a
compiled path never evaluates a formation or picks a move at runtime, it only **samples a
precomputed timeline at the current playback position**. This is exactly the pattern
`StructureSource.synthesize()` already proves in production (a complete frame from sidecar data
alone, at an arbitrary position) — extending it, not inventing a new mechanism.

### 5.2 The pieces

- **Choreography Score** (new artifact, sidecar-sibling): produced by a new offline script
  (`choreograph.ts`, same shape as `structure.ts`/`analyze.ts`), consuming the schema-4 sidecar
  + move/formation libraries. A sorted timeline of `{ agentId, moveId, startTime, duration,
  curveParams }` per channel, formations and roles already resolved into concrete per-agent
  instructions — the grammar in §3 does not need runtime evaluation.
- **`ChoreographyOutput`** (new `VizOutput`, peer to `ScreenOutput`/`FixtureOutput`): given
  current playback position, looks up active instructions per agent, samples each channel's
  curve at local progress. For the compiled path this bypasses the patchgraph entirely —
  everything is already resolved. This is, concretely, the same idea as AGENTS.md's own
  already-backlogged, unbuilt "presentation/export mode: fixed showfile vs. live-reactive
  playback" item — just not previously connected to servos. Building this finishes existing
  scope, not new scope.
- **Live path**: routes through the existing reactive patchgraph exactly like any other live
  signal — no new mechanism.
- **One physical-safety layer, unconditional, after ALL paths** (choreography, field, live):
  rate-limiting, thermal duty-cycle, graceful single-axis failure — the `ServoOutput` spec
  already deferred in `SINTEZA_SIGNAL_BUS.md` §6.3. Every path's final values pass through the
  same clamp before touching hardware. This is the one place physical safety is enforced;
  no output may bypass it.

**Adopt show-control vocabulary, not a bespoke one.** In the established terms of the field
(Huntington, *Introduction to Show Control* — the standard text), the Choreography Score is a
**cue list**: cues with timeline triggers. Use `cue` / `cueList` / `trigger` / `go` rather than
inventing names. Two reasons beyond consistency: it maps onto existing protocols (MIDI Show
Control) if external triggering is ever wanted, and it gives an established mental model instead
of a private one. Note also that modern show control uses a **distributed model with independent
nodes**, not one central computer executing a sequential instruction list — which is an
independent endorsement of the `VizOutput`-peers architecture already in place over any
monolithic sequencer design.

### 5.3 `FieldOutput` — the dense-array paradigm (§0)

A peer `VizOutput` for rigs of many single-DOF elements (Rozin-style tile/pin arrays). Entirely
separate from §§2–4's move/formation/compiler machinery — it shares the audio stack, not the
choreography model.

- **Input is a field, not a score**: a 2D scalar (or small-vector) buffer, sampled per element.
  The natural sources are what the screen pipeline already renders — the memory field, the Julia
  substrate, any `.hyst` shader's output — plus live bus signals for procedural fields. **A dense
  array is a low-resolution physical render target for the existing visual layer.** No new
  authoring surface is required for the common case.
- **`ArrayTopology`** (distinct from §3.1's `Topology`): a grid/packing descriptor mapping each
  element to a normalized (u,v) sample position in the field, plus its channel binding. Changing
  the physical array's shape or resolution changes only this descriptor.
- **Per-element mapping function**: field value → element DOF, with the same named-channel-role
  indirection §2 uses. Rozin's own two mappings are the reference cases: brightness → tilt angle
  (*Wooden Mirror*), and value → pin *orientation* forming contour rather than shading
  (*Angles Mirror*). Expose the mapping as a parameter; it is the array's entire aesthetic.
- **Refresh rate is low and that is correct**: Rozin's mirrors refresh ~15×/sec and read as
  smooth. Do not drive a mechanical array at frame rate; the safety layer's rate limiting and the
  elements' own travel time dominate. Send only changed elements (Rozin's own optimization —
  compare current state to target, transmit the diff) rather than a full frame every tick.
- **Prior art note**: "convert an image to grayscale, derive a per-element motion profile, drive
  automation from it" is a recognized industrial pattern, not a Rozin-specific trick — it appears
  in entertainment-automation patent literature (e.g. US 20140277623, graphics-driven motion
  control). Relevant as validation of the approach; scope/applicability of any patent is a
  question for a lawyer, not this document, though for a non-commercial installation using a
  decades-old widely-replicated technique the practical concern is low.

---

## 6. Kinematics & latency compensation (found during review — a real gap, not deferred)

A compiled score's timestamps assume the physical channel can reach the target instantly. Real
servos have travel time and settling behavior; "arrive exactly on the drop" as authored will
arrive *late* by however long the arm actually takes to move, unless compensated. This needs:

- A **per-DOF kinematics profile** — max angular velocity, acceleration, and jerk — supplied
  once per physical channel type (a servo spec, effectively).
- The compiler uses this profile to **back-calculate** a move's actual start time: if a windup's
  end must land at drop time T and the channel's kinematics say the required travel takes X
  seconds beyond what the curve's own duration implies, the compiler starts the move X seconds
  earlier, not at the naively-authored offset.
- The same profile constrains the S-curve/jerk-limiting applied at the safety layer (§5.2's
  unconditional clamp) — motion-planning practice, not an aesthetic curve choice (see §2.1's own
  note distinguishing S-curve from the aesthetic corpus).

Without this, "land exactly on the beat" is a documented lie the system tells itself. This must
be designed before real hardware timing is trusted for anything performative.

---

## 7. Degradation & robustness (found during review)

- **Topology mismatch**: a compiled score assumes N working agents; a show day may have fewer
  (a failed unit). The compiler/score format needs a defined collapse strategy — redistribute or
  skip a missing agent's assigned instructions rather than the whole formation breaking. Related
  to, but distinct from, the single-axis graceful-failure already specced for `ServoOutput`;
  this is ensemble-level, that's channel-level.
- **Element-level failure in dense arrays (§5.3) is a *when*, not an *if*.** Field reports from
  repairing a Rozin mirror describe a burned-out servo controller board, several seized servos,
  and a controller model no longer manufactured; visible "stuck pixels" appear in documentation
  of working pieces. An array of hundreds of elements has hundreds of failure points, each one
  visible. Requirements that follow: elements must be individually replaceable without
  disassembling the array; the driver must tolerate and route around a dead element rather than
  stalling a bus; prefer a controller built from currently-manufactured, replaceable parts over
  anything bespoke or single-sourced (the Rozin repair was blocked precisely by an obsolete
  controller); and the field mapping should degrade gracefully — a dead element should read as
  one wrong tile, never as a stalled or corrupted region.
- **Thermal interaction with `hold`**: a long authored `hold` (§2.2) may conflict with a hobby
  servo's continuous-holding-torque thermal limits (already a named concern in the deferred
  `ServoOutput` safety spec). A compiled long hold needs the safety layer's thermal model
  available at compile time too, not just at runtime — either the compiler avoids authoring
  holds longer than the thermal budget, or the safety layer is allowed to insert imperceptible
  micro-releases during an overlong hold. Decide which before holds longer than a few seconds
  are authored.

---

## 8. Cohesion with the screen/visual layer (found during review)

Both the screen (`SINTEZA_SIGNAL_BUS.md`) and this layer consume the *same* sidecar and
structural analysis, so baseline synchrony (both react to the same drop, the same section) is
free — no explicit cross-wiring needed. Left open, not required now: whether a climactic moment
should have the compiled choreography *also* directly inform a screen parameter (or vice versa)
for a single, unified "the whole room moves as one" instant, versus the two mediums staying
independently-synced-by-shared-source. Worth a real decision once both exist and can be watched
together — not decidable on paper.

---

## 9. Versioning & tooling (found during review)

- **Choreography Score schema** should follow the sidecar's own additive-versioning precedent
  (schema 2→3→4) exactly — never a breaking bump, optional fields only, so refining the
  compiler later doesn't invalidate an already-reviewed, already-approved score.
- **A preview/simulation tool is REQUIRED, not optional** (upgraded from "flagged" after
  research). Previsualization is standard practice in entertainment automation, not a nicety:
  dedicated previz systems exist specifically to simulate rigs against real automation data
  (e.g. Stage Precision ingesting live Kinesys winch positions to drive a simulated object), and
  the industry does not move real machinery without simulating first. The same reasoning applies
  with more force here, since §6's kinematics gap and §7's failure modes are exactly the class of
  problem that only becomes visible when watched.

  A cheap first version suffices: a top-down 2D animation of the topology executing a score, no
  hardware required — analogous to how the screen path is already dev-reviewable without a
  gallery. It must cover both paradigms: agent poses over time for `ChoreographyOutput`, and a
  rendered element grid for `FieldOutput`. Treat "never send an unpreviewed score to hardware" as
  a working rule.

---

## 10. What is explicitly deferred

- Nested sub-formations (§3.2's closing note).
- Any decision on whether one global move/formation library serves every track/project, or
  libraries are scoped per-song/per-exhibition — worth deciding before the library grows large,
  not designed here.
- The screen/servo cross-link (§8).
- `ArrayTopology` calibration for a physical array (§5.3) — mapping real element positions to
  field (u,v) once a rig physically exists.
- Detailed design of the preview tool (§9) — it is REQUIRED before hardware, but its own UI/
  implementation is not specced here.
- Real hardware kinematics profiles (§6) — the *mechanism* is specced; the actual numbers depend
  on whichever servos get sourced, still last in the priority order per earlier discussion.
