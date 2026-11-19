# B: the workspace that makes the dance feel (design, not built)

Status: design only, 2026-10-11. Nothing here is implemented or verified.
Branch: `keys-decide`. Read `docs/DANCE_RESTART_PROMPT.md` first.

## Names

- **Hysteresis**: the engine. It listens, remembers and decides.
- **АФЕКТ** (`afekt`): the body. The arms, and any later physical piece.
- **СИНТЕЗА** (`sinteza`): the visuals.

The engine has three parts, from the user's own model of a mind:

| Part | What it is | In this repo today |
|---|---|---|
| **A**, perception | a stack of embeddings: raw sound reduced to features, beats, phrases, sections | the sidecar: stems, `musicalMemory`, `musicalStructure`, `noteTrack` |
| **B**, workspace | recurrent state at several timescales; it predicts, holds and is surprised | **missing** |
| **C**, selection | picks the action | `character()` in `director.rs`, `motif()` and the moments in `figures.rs` |

Emotion, in that model, is not a module. It is a **field-state**: a few global
parameters (gain, precision, learning rate, approach) that bend A, B and C at once.

## Why the dance reacts instead of feels

Today A feeds C directly. `character()` labels each stretch of the song, and
each label picks a motif. Loudness scales the figures (`intensity`, `sized`).
Moments prepare for an event over a few beats. All of it maps the music *now*
onto motion *now*.

What a viewer reads as feeling is state that has its own time:

- **Held breath**: it gathers *bars* before a drop, not beats.
- **Payoff**: the release at the drop is as big as the tension built before it.
- **Afterglow**: after a climax it stays large and settles slowly.
- **Recognition**: a returning chorus pulls the ensemble into one body.
- **Startle and composure**: a surprise breaks the ensemble's unity briefly,
  then it regathers.
- **Familiarity**: the fourth chorus is not danced like the first.

The user's measured lesson from 47 versions: small posture and timing changes are
invisible; structural changes read. Every effect below must be structural:
held breath across at least 4 bars, contraction of at least 20 %, afterglow
across at least 8 bars.

## Two expectation streams

The arm **knows the dance**, like a dancer who has rehearsed the song. But if B
knew everything its surprise would be zero, and with zero surprise there is
nothing to feel. A rehearsed dancer still performs the drop. So B listens with
two streams, the split music psychology uses (Huron, *Sweet Anticipation*):

| Stream | Knows | Gives |
|---|---|---|
| **Veridical** | the whole song, from the sidecar, weighted by precision ρ | timing: when to gather, when to land, what is coming back |
| **Schematic** | only what *this song* has done *so far* | surprise: the drop breaks the groove, the cut breaks the pulse, a new element breaks the texture |

The field is driven by **schematic surprise, timed by veridical knowledge**. The
drop at 1:32 in "Presence" is known exactly (veridical), and it still breaks the
groove (schematic), so the body shows the impact exactly on time.

**Hard rule: the schematic stream is causal.** At beat *n* it reads only beats
0..=n. The only route to the future is an explicit `Foresight` input that the
veridical stream builds from the sidecar. This keeps the schematic stream
usable live later (unknown audio has no sidecar).

## Modes

One workspace, four settings:

| Mode | ρ (veridical) | Use |
|---|---|---|
| `Off` | — | version 47, byte for byte. The ablation baseline. |
| `Rehearsed` | 1 | **the dance.** Deterministic: the same dance every play. |
| `Schematic` | 0 | ablation of foresight; also what live mode would be |
| `Learning { play, kappa }` | 1 − e^(−κ·play) | optional installation that learns the song across plays. Build last, or not at all. |

## The levels (schematic stream)

The model the user wrote down: each level i holds state at timescale τᵢ,
τ₁ ≪ τ₂ ≪ … ≪ τₙ, and each level predicts the level below it.

Input per beat (the beat grid is `beat_zero + k · beat_period`), observation
vector **x**:
- stem activity for bass, drums, vocals, other (`wholeTrackActivity`, mean over the beat)
- overall level (the `level` series in `compile_ensemble`)
- drum transient density
- the leader lane's index and brightness (`ranks`, `brightness_per_beat`)

| Level | τ (beats) | Expects | Error |
|---|---|---|---|
| L0 beat | 1 | — (the observation) | — |
| L1 bar | 4 | leaky mean and variance of **x** | per-dimension z-score of **x**, a Mahalanobis distance on the diagonal |
| L2 phrase | 16 | L1's mean and variance, slower | same, against the slower context |
| L3 phrase identity | per phrase | the 32-step `rhythm` of the most similar **earlier** phrase | 1 − correlation of the actual rhythm with it, checked at each phrase start |
| L4 section | 64 | L2's statistics, slower | same |

L3 is the one genuinely predictive level in version 1: at a phrase's start it
predicts the phrase from the past and measures how wrong that was. It uses only
earlier phrases, which keeps it causal. L1, L2 and L4 are leaky integrators, a
deliberate simplification of "predicts the level below". Version 2 may predict
slopes as well as levels. Leave that out until version 1 has been judged.

**Surprise** s(n) = Σᵢ wᵢ · πᵢ · eᵢ(n), clipped to 0..1. Each level's precision
πᵢ is the inverse of its running variance; the weights wᵢ are fixed constants.
In a steady loop, after two phrases s must sit near 0.

## The veridical stream

`Foresight` is built once from the sidecar. It lists the known future events,
each with a time and a sign:
- arrivals (the measured transitions `compile_ensemble` already ranks), with
  their lift direction, computed exactly as the moments' code does now (level 8
  beats before against 4 beats after; `+` lift, `−` falling away, an entry from
  near silence is neither)
- repeats (`phrase.repeat_of`, `repeatedMaterial`)
- cuts (the near-silence detection already in the moments code)
- phrase ends

Lifting that logic out of the moments code into `Foresight` is a refactor: the
moments must keep their exact current behaviour (see the golden test).

## The field

Five values per beat, each a first-order system with its own attack and decay
(in beats). Constants are starting points; the user tunes them by eye.

| Field | Driven by | Attack / decay | Meaning |
|---|---|---|---|
| **gain** g | `intensity(t)` + 0.6 · s | 0.5 / 16 | arousal. The slow decay is the afterglow. |
| **tension** T | ρ · ramp toward the next `+` arrival within 32 beats, × (1 − s) | ramp / release in 1 beat | held breath. Builds only while the groove is predictable. At the arrival it is released into gain. |
| **precision** π | drops by s when s > 0.5; reset to 1 by recognition | step / recovers in 8 | composure. Low = the ensemble briefly loses unity. |
| **approach** a | prediction error on valence at an arrival: expected sign vs measured lift | step / 8 | −1..1. Lift = extend and rise; falling away = pull in. |
| **habituation** h | count of recognised repeats of the current material | step / 64 | familiarity within the song |

The payoff rule: at a `+` arrival, gain jumps by `0.5 + 0.5 · T_before`. A drop
after a long held breath lands bigger than one with no build.

## Basins: one event, three consequences

The user's model: an evoked basin sets the field-state and produces the
emotion, the capture of attention and a reorientation *as one consequence*. B
emits a `Basin` at:
- **recognition**: a phrase start whose `repeat_of` is set with similarity ≥ 0.8,
  or the start of a `repeatedMaterial` span
- **lift**: a `+` arrival
- **novelty**: a novelty candidate (scale ≥ 8, percentile ≥ 0.94) with no repeat

Each basin does three things at the same instant, and only through these code paths:

| Basin | Field | Attention (ensemble) | Reorientation |
|---|---|---|---|
| recognition | π → 1, h += 1, g += 0.2 | Unison for the first bar of the phrase; the existing `recall_from` path (same figures, same side, larger) | none: it is coming home |
| lift | tension released into g; a from the measured lift | Unison through the arrival | base travel flips (the `way` flip) |
| novelty | π −= s, g += 0.3 · s | the next move passes round the ring (the existing `accents`: Ripple, then Canon), then back | base travel flips |

These reuse mechanisms that are already accepted (formations, accents,
`recall_from`, the `way` flip). B adds no new move shapes and no new formations.
User rules that still bind: every arm always dances; sync and mirror are the
favoured looks; canon and ripple are only flourishes; no arm rests.

## What the field drives (existing knobs only)

| Knob (in `figures.rs`) | Modulation |
|---|---|
| `sized()` figure size | × (0.85 + 0.3 · g) × (1 − 0.25 · T) |
| figure clock rate (`drive`) | × (1 − 0.35 · T); the afterglow allows full rate sooner after a lift |
| moment `strength` and `hold` | × (0.7 + 0.6 · T released at that moment) |
| moment preparation | lengthened by T: the gather starts where tension starts, up to 16 beats before, not 1 to 2 |
| voice `lift` and brightness height | + 0.15 · a |
| contrast phrase after 128 beats | after 128 · (1 − 0.4 · h) beats |
| `accents` (Ripple/Canon) | also triggered by a novelty basin (see above) |

**Caps are not negotiable.** `HAND_SPEED_CAP` (0.8 m/s), the 0.6 m/s that a
moment may add, the collision clearance and the follower's limits all stay as
they are. If the field asks for more, the cap wins and the effect shrinks. The
field never touches the follower or the collision check.

## Where it goes in the code

- New file `crates/hyst-compile/src/director/workspace.rs`. Stay inside
  `hyst-compile` (and `hyst-previz` only for printing). Later the workspace
  moves into the engine so СИНТЕЗА can read the same field. Not now.
- Shape:
  - `Foresight::from(&Evidence, …)`: the veridical events
  - `struct State` with `fn step(&mut self, obs: &BeatObs, foresight: Option<&Foresight>, n: usize) -> Field`:
    one beat. It must be a pure step, so it can run live later.
  - `Workspace { field: Vec<Field>, basins: Vec<Basin> }` and `field_at(t)`, interpolated
- `CompileConfig` gets `workspace: WorkspaceMode`, default `Off` until the
  user's verdict. When the user picks a winner it becomes the constant and the
  losing modes and switches are deleted in the same turn (the project's rule).
- `EnsembleScore` gets an optional debug lane, `workspace: Option<Vec<FieldSample>>`
  (`#[serde(skip_serializing_if = "Option::is_none")]`), so a field can be
  plotted against a song. The `ensemble_preview` example prints a summary:
  basins with their clock times, tension peaks, and the two largest surprises.
  Do not polish the canvas preview.

## Tests (all on synthetic evidence, no real songs)

1. **Golden**: before any code change, record a digest of `compile_ensemble`
   output for the existing fixtures. `Off` must reproduce it exactly, forever.
2. **Causality**: change the evidence after beat n; the schematic field up to n
   is unchanged.
3. **Steady loop**: after two phrases of the same material, s < 0.1.
4. **Groove break**: an activity jump after a steady loop makes s spike above 0.5.
5. **Held breath**: in `Rehearsed`, T rises steadily over 16 beats before a
   known `+` arrival and releases within 2 beats after it. In `Schematic` T stays 0.
6. **Payoff**: the same drop after a 16-beat build lands with more gain than
   with no build.
7. **Afterglow**: after a lift, g decays with the stated τ.
8. **Recognition**: at a repeating phrase start the first bar is Unison, π = 1, h rises.
9. **Caps**: the existing speed, acceleration and clearance tests pass in every mode.
10. **Determinism**: two compiles in the same mode are identical.

## Acceptance (only the user can do this)

Nothing improves until it is exported and judged on the user's machine. The
rules below are fixed **before** anyone looks at a result. Do not renegotiate
them after seeing one.

**Guardrails** (measured with `jolts.py`, `spans.py`, per song, against version 47):

| Song | v47 jolts | allowed | v47 top hand speed | allowed |
|---|---|---|---|---|
| Instant Crush | 5 | ≤ 8 | 1.49 m/s | ≤ 1.73 m/s |
| Five Years | 2 | ≤ 5 | 1.22 m/s | ≤ 1.73 m/s |
| Presence | 15 | ≤ 18 | 1.73 m/s | ≤ 1.73 m/s |

Also: no new jolt inside any judged clip; closest implement gap ≥ 10 cm.
A mode that breaks a guardrail is not shown to the user; it goes straight to
the tuning round.

**The blind test.** Shuffled, synced A | B | C (`Off`, `Rehearsed`,
`Schematic`), the key in a file left unread until the verdict:
1. "Presence" 1:15–1:50 (build into the 1:32 drop)
2. "Presence" 2:31–2:55 (the user's "emotional, could be followed")
3. "Instant Crush" the first chorus return (recognition)
4. "Five Years" the climb to the climax (tension over minutes)

**Decision rule.** `Rehearsed` wins only if the user prefers it over `Off` in
at least 3 of the 4 clips. A tie counts as a loss. `Schematic` exists only to
show whether foresight matters; it cannot win on its own.

The project's own rule of evidence: a system that runs proves nothing; forced
choice and ablation do. `Off` is the ablation.

## Rounds and stop rules

The work is bounded. There is no round 3.

| Round | What happens | Then |
|---|---|---|
| **1. Build** | Implement v1 as specced. Export, measure, blind test. | Win → step "Freeze". Lose → round 2. |
| **2. Tune** | Constants only: time constants, gains, the modulation factors. **No new mechanisms, no new fields, no new basins.** The user names what read wrong by clock time; only those constants move. Re-export, re-test with the same four clips. | Win → "Freeze". Lose → "Remove". |
| **Freeze** | The winning constants become constants. Delete `Schematic`, the mode switch and any losing code in the same turn. Handoff entry. | Done. v2 only through its gate (below). |
| **Remove** | Delete `workspace.rs` and its wiring. Keep `Foresight` only if the moments code reads cleaner with it; otherwise revert to version 47. Handoff entry says why it lost. | Done. Move to the next piece the user picks. |

**Frozen during all of this** (no changes, even if bugs show up there; note
them in the handoff instead): the follower, inter-arm braking and the collision
check, the speed caps, motifs and figure shapes, formations, `character()`
classes, the moments' timing logic.

A jolt the user reports in a judged clip is first checked with `jolts.py`: if
the same jolt exists in `Off`, it belongs to the braking problem, not to B, and
it does not count against B.

## The v2 gate (latent workspace)

v2 replaces the five hand-built fields with a latent state: a learned music
embedding (MERT or CLAP) as A's top layer, a multi-timescale recurrent network
as B, and the five names kept only as readouts. It is **not part of this
plan**. It gets its own spec only if both are true:
1. v1 won and was frozen, and
2. the user, after watching the frozen v1, says it still lacks feeling and
   names clock times where it does.

Without both, v2 does not start. v1 is its baseline; v2 must beat v1 blind by
the same 3-of-4 rule.

## Out of scope for version 1

- `Learning` mode (build only after `Rehearsed` wins, if ever)
- Per-arm temperament (six arms with slightly different π and τ): it changes
  relative timing and risks the braking problem. Version 2, after the braking
  work.
- Following the lead instrument's melody, and arms braking for each other: the
  other two open pieces. B only modulates.
- Live audio. СИНТЕЗА reading the field.
