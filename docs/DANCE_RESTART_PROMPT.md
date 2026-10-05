# Fresh-agent prompt — continue the arm ensemble

Continue on branch `keys-decide` (draft pull request open; do not push to
`master`). Communicate terse and exact. Frozen `src/` and `tools/` are
read-only. Never drive hardware.

First, before any code: read this file, then the `DANCE_HANDOFF.md` entries
from "Version 33" to the end (the ensemble), and "Versions 28–30" to
"Version 32" for the single arm ("Version 13" onward only if you need the
earlier blind-test history). Read `crates/hyst-compile/src/director/figures.rs`
in full (`compile_ensemble` is the entry; `compile_figures` is its one-arm
case) and skim `director.rs`, `ensemble.rs`, `crates/hyst-previz/src/ensemble.html`.
Run the checks under "Commands" and export the hexagon: it must be
byte-identical to `hexagon-42.html`. Report in a few lines what you understand
and what you will do first, then start; do not wait for approval unless you
asked a blocking question.

## The task for this session (the user's words, 2026-10-05)

Asked what comes next, the user chose overlap outside unison: "1. is most
important, we want to be able to make red zones so that it doesn't hit
equipment or whatever, it's supposed to be generalized right?"

Two parts:

1. **Arms working inside each other's space.** Version 40 lifted the "own
   sector" limit except where arms posed alone would come within the
   clearance (`apart` in `compile_ensemble`). The user then changed the
   formations (see the ensemble record below), so today the arms overlap in
   Unison only by choice of formation: Mirrored cannot overlap (mirror
   neighbours meet in the plane between them at the same moment) and the
   flourishes are danced in line with the centre. Version 42 is **not yet
   reviewed** (`hexagon-42-full.mp4` sent). Whether more overlap is still
   wanted is the user's call. Arms that are stopped or stutter are a defect
   the user spots at once (see version 38).
2. **Red zones as a general tool**: the arms must be kept off equipment or
   anything else in the room. What exists: fixed zones are axis-aligned boxes
   in the world (`Zone`, `--zone x0,y0,z0,x1,y1,z1`, repeatable); every arm of
   an ensemble respects them through `Obstacles`; the implement counts by its
   bounding radius; other arms count as moving zones with a tunable
   `--clearance`. Tests cover one arm and two arms against a box. Not known:
   which shapes the user needs (boxes only, or cylinders, tilted boxes, a
   wall), and whether zones may change over time. The user was asked what
   equipment they have in mind; do not invent shapes before they answer.

## What the user wants (their words, settled)

- A viewer should think "beautiful", then "impressive", then "how did they do
  this". Idea source: OK Go "Love" (robot arms with mirrors).
- **The whole project:** several arms holding "something with mirrors", and a
  projector that fires the visualizer (the Julia and Mandelbulb fractals, the
  other half of the project) onto them and the surface they stand on. The
  projector faces the mounting surface head-on: ceiling for a floor arm,
  perpendicular to the wall for a wall arm.
- **Six arms, concentric, symmetric, like a hexagon.** In a ring the arms'
  forward is the centre; they still turn all the way round.
- **Synchronized dancing is "a different game"** from the single arm: all
  together, inverses, one by one, drop-outs, pairs, complements. It should
  "decide itself" from the music. Low energy and resting arms were rejected
  ("not synchronized enough, too low energy"). Arms too far apart were
  rejected. Canon: each arm starts a fraction of the move late, circular
  (1-2-3-4-5-6) or spreading both ways and back.
- Interpretation must be automatic. Human timestamps
  (`scripts/instant_crush.acceptance.json`) and published notes (the Songsterr
  tab) are validation only, never planner input.
- Dance works from offline sidecars only. No live audio.
- **Real hardware is the end goal.** Motion no servo arm could execute is a defect.
- **Rig, settled:** five servos: base yaw (continuous 360°), shoulder, elbow,
  wrist bend, wrist roll. Lengths, limits and speeds are invented until measured.
- **Hand, settled as a direction:** a reflective, non-spherical object. The
  user prefers the lumpy mirror ball ("like a disco ball, but not quite, not
  spherical, irregular", "non-convex sort of") over the disc. Different
  implements must stay possible ("generalization is always good").
- A lifelike render comes much later. Do not polish the canvas preview unless asked.
- The note data is for the whole installation, lives in the sidecar and must
  work for other songs. The voice is not an instrument but a fluid
  up/down/stop/loudness. The dominant instrument leads the arm.
- A hold is almost never a dead stop. This song has no sharp passages; flicks
  are wrong here. Jitter is a defect; purposeless constant motion is also a defect.
- Keep scope finite. Test song stays Instant Crush until the user supplies another.

## How the user reviews (keep this loop)

The user judges by eye, fast and precise, and is usually on remote control:
**send every file with SendUserFile** (30 MiB limit; re-encode larger videos).
Do not claim to have watched or heard anything. Tell the user what to look for
with each clip; they asked. They answer best to a concrete clock time and what
should happen there.

- **Single-arm motion decisions:** one shuffled, synced side-by-side (A | B | C,
  30–40 s, with audio); the key goes to a file and stays unread until the
  verdict. Winners become constants; losers and their flags are deleted the
  same turn. "No difference" means delete. Variants must keep the same
  choreography or the user cannot judge them. Measure variants before sending.
- **Ensemble:** the user has reviewed whole-song videos with a clock in the
  corner (5:40, 30 fps, about 28 MiB) and reported by clock time. Give a table
  of what happens when.

Blind-test record, single arm. Kept: hand-path low-pass, figure clock with
0.8 m/s cap, wrist drag 240, disc roll = travel + flips, spin 280°/m, surge
after each stab of the leading lane, hand size and height follow the leader's
swell, hand rises with a high voice (0.65), soft flourishes in a steady stream,
sections travel round the base in alternating directions. Kept without a
visible difference, for the hardware: figure clock smoothed over two knots.
Died: beat pulse, keys pacing, figure carry, melody contour, plain joint lag,
wrist whip, suspension at peaks, three roll drivers, figures snapping to the
leader's phrase starts, figures picked by the leader's pitch step, accents from
the second lane, arriving on the stab. Lesson: small posture pulses and small
timing shifts are invisible; structural changes read.

Ensemble record. Accepted at version 39 ("It's good now"); version 42 awaits
review. After version 40 the user said: a long canon is "too unsynchronized";
"the best looking one is sync. I also like mirror"; canon and ripple are
"more of a flurish move" and "work well especially with 'linear' movements
(where the joints are co-linear with the centerpoint)". Version 42 is built
on that. Rejected on the
way: resting formations (one by one, long pairs), a 1.1 m hexagon, a ripple
whose end arms stalled and raced, a draw-order bug. "Doesn't follow music
enough, needs to be more on point" was said of version 38 and not explained;
version 39 (delays on the beat) was then accepted. Do not build for it unless
the user raises it again.

## What exists

- Sidecar pipeline: `scripts/dance_memory.py`, `dance_stems.py`,
  `dance_structure.py`, `dance_notes.py` (`noteTrack.lanes`: per stem, onsets
  `[time, rough pitch, strength]`, phrases, `levelPerBeat`, `brightnessPerBeat`).
- `crates/hyst-compile/src/director/figures.rs`: the planner. `director.rs`:
  sidecar parsing. `ensemble.rs`: rig, implement, kinematics, score.
- `crates/hyst-previz`: `examples/ensemble_preview.rs` + `src/ensemble.html`.

Single arm in one paragraph: the song is cut at measured transitions and phrase
edges; each stretch gets a class from stem levels; each class plays a sequence
of hand figures, mirrored on each repeat, travelling round the base (direction
alternates per section). The hand path is low-passed. A figure clock stops
during holds, caps path speed at 0.8 m/s, surges after each stab of the leading
instrument lane, and is smoothed over two knots. Where the leader plays no
stabs, figure size follows its loudness and hand height its brightness. The
hand rises while the voice sings high. Moments: section arrivals and
flourishes. Joints are solved per knot; the wrist roll is driven outside the
solver; a follower limits speed and acceleration and brakes near end stops and
zones.

Ensemble in one paragraph: `compile_ensemble(json, config, rig, zones, arms,
clearance_m)`. Each run of the song gets a `Formation` from its class and how
often that class has come round (interlocked, bass-led, silence: Unison;
vocal-led: Mirrored, Unison in turn; percussive-open: Unison, Mirrored;
sparse: DropOut; else Pairs). The move holding a melodic flourish is passed
round the ring (`accents`: ripple and canon in turn; six beats or longer,
under 120° of sweep) while each arm turns in line with the centre. `Formation::part` gives each arm a side, a delay
in beats and dancing or resting; the arm's path is the single-arm path at its
own delayed time, bearing times its side, eased toward a rest pose when it
sits out. Delays run evenly across each move. `shared` then applies two
limits that are the same for every arm: no hand enters a circle at the
layout's centre; and each hand stays in its own sector where out-of-step arms,
posed alone, would come within the clearance (`apart`).
Arms are solved in order at each knot; `Obstacles` makes fixed zones and the
other arms' current poses things to keep clear of, in the solver, the
follower's braking and a hard check. One arm alone bypasses all of it.

## Commands

```
D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
cargo run --release -p hyst-previz --example ensemble_preview -- \
  $D/OUT.html instant-crush.m4a $D/instant-crush.notes.sidecar.json \
  [--ring 6,0.8] [--clearance 0.1] [--implement ball|disc] [--zone x0,y0,z0,x1,y1,z1] \
  [--score OUT.json] [--rig RIG.json] [--groove-only] [--no-reuse] [--drag GAIN]
node $D/record-ensemble.cjs $D/OUT.html $D/instant-crush.m4a $D/clip.mp4 START SECONDS
```
Without `--ring` it plans one arm (`song-figures-34.html` holds the same
planned motion; the page script has changed since, so compare the data, not
the file). With `--ring 6,0.8` it must reproduce `hexagon-42.html` exactly.

Checks: `cargo test --workspace --exclude hyst-render` (138 pass; the six-arm
tests take about 15 s each), clippy `-D warnings` on hyst-compile/-output/-previz/
-cli, `cargo fmt --all --check`, `node crates/hyst-previz/tests/ensemble.cjs`,
`cd scripts && python3 -m unittest test_dance_notes`. No hyst-render tests (GPU).
The recorder draws the canvas only, max 40 s per call, 30 fps. `$D` is outside
git; never commit media. Shell note: the worktree guard refuses commands that
mix the `$D` path (it contains "github") with pipes, `&&`, loops or heredocs;
put such steps in a script file and run that.

Helpers outside git:
- `$D/tracker-scratch/`: single-arm review (`variants.sh`, `sbs.sh`,
  `measure.py`, `diff.py`) and the note-tracker tools.
- `$D/tracker-scratch/ensemble/`: `ens.sh RADIUS` exports a hexagon and prints
  closest approach and per-section hand speeds per arm; `pairs.py` (closest
  approach between arms), `ensstat.py` (formation and speed per section),
  `kicks.py` (sharp accelerations and standstills per arm), `stut.py FILE T0 T1`
  and `peak.py FILE T0 T1 ARM` (one window in detail), `overlap.py` (how much
  arms share space), `byform.py` (the same per formation, with stalls and
  kicks), `when.py` (clock times of out-of-step overlap), `runs.py`, `accents.py`,
  `still.py`, `who.py FILE T…` (which parts are closest), `hexreview.sh
  SOURCE.html OUT.mp4 [CRF]` (whole song with a clock), `mirror2.py` (where the
  implement throws the projector's light). Paths inside point at that folder.
Environments under `/secondary/hyst-env`; root disk is nearly full.

## Known weak points

- Ensemble: no overlap in Mirrored (135 s of the song). No test covers a
  flourish. A linear reach pauses 0.3 s where it turns round (0:49). Arms
  drift out of step over the move before a flourish. Six arms compile in about 16 s. Right of way between
  arms is by arm index. The formation table is an agent's guess; the unison
  from 3:33 to 5:23 is long; "complements" is undefined. Version 40 removed the 187.9 s kick and the
  short standstills of version 39 (arm 5 keeps one). A ring under about 0.7 m fails
  (`fit_tangents` or the start poses). The implement is a bounding sphere and
  is not checked against its own arm. Hexagon radius 0.8 m, projector height
  2.5 m and the ball's 8 cm radius are assumptions.
- The preview's light: plain patches, no image content, no shading of one tile
  by another, no arm blocking the beam.
- Single arm: stab surges exceed the speed cap by up to half. The swell has no
  gate for "single flowing line". The break's leader change is found at
  188.8 s; the user hears it at 185. The disc roll chatters (the user saw no
  jitter at 60 fps). Flourish and arrival poses are two or three fixed shapes.
  Follower limits are guesses for hobby servos; no load or gravity model.
  `fit_tangents` can cascade when an arm is stopped within one knot.
- Lanes come from six-stem Demucs; all tracker numbers are one song against one
  fan-made tab. The lanes pipeline for the rest of the machine is paused.
- `AGENTS.md` is long; trimming it was proposed, not done.

## Rules of engagement

Ask the user before artistic choices they have not made. Measure before you
send. Keep code small: delete what loses. Append an honest entry to
`docs/DANCE_HANDOFF.md` and `AGENTS.md` when you stop.
