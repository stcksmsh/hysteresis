# Fresh-agent prompt — continue the single-arm dance

Start from current `master` on a new branch; open a pull request when a slice is
done. Do not push to `master` directly. Communicate terse and exact. Frozen
`src/` and `tools/` are read-only. Never drive hardware.

First, before any code: read this file, then every `DANCE_HANDOFF.md` entry dated
2026-10-04 from "Version 13" onward (the last, "Version 27", holds the note tracker and leading-lane work) (older entries and most of `AGENTS.md` §5
describe deleted code; skip them). Read `crates/hyst-compile/src/director/figures.rs`
in full and skim `director.rs`, `ensemble.rs`, `crates/hyst-previz/src/ensemble.html`
and `examples/ensemble_preview.rs`. Run the checks under "Commands" and export one
preview to confirm the tree works (it should be byte-identical to
`song-figures-27.html`). Then report to the user in a few lines: what you
understand the goal and state to be, what you will do first, and any question
that blocks it. Start work after that report; do not wait for approval unless
you asked a blocking question.

## What the user wants (their words, settled)

- A viewer should think "beautiful", then "impressive", then "how did they do
  this". Idea source: OK Go "Love" (robot arms with mirrors).
- One arm that truly dances is the goal now. Many arms and projection come
  after, and need "dynamic red zones" (each arm a moving zone for the others).
- Interpretation must be automatic. Human timestamps in
  `scripts/instant_crush.acceptance.json` are validation only, never input.
- Dance works from offline sidecars only. No live audio.
- **Real hardware is the end goal.** Motion no servo arm could execute is a defect.
- **Rig, settled:** five servos: base yaw (continuous 360°), shoulder, elbow,
  wrist bend, wrist roll. No more axes for now. Lengths, limits and speeds are
  invented until measured.
- **Hand, settled:** a reflective, non-spherical object, for the first demo a
  mirror disc held by its edge in line with the arm ("---0"). Never a ball.
  Its orientation matters. What exactly it is remains open, so checks that need
  its shape (disc rim against floor and zones) wait.
- A lifelike render (Blender or similar) comes much later. Do not polish the
  canvas preview unless asked.
- The user's own model of dancing this song: percussion is the floor, the
  keys/guitar are the decision-maker (their flourishes cue movement from state to
  state), vocals give the emotion. In the break the guitar solo leads.
- A hold is almost never a dead stop: small slow movement. A true freeze only
  on a cut (dense, nothing, dense). This song has none.
- This song has no sharp passages; flicks are wrong here. Jitter is a defect;
  purposeless constant motion is also a defect.
- Keep scope finite: "we want this to actually work and be finished".
- Test song stays Instant Crush.

## How the user reviews (keep this loop)

The user judges by eye and is fast and precise. For every decision, send a
**shuffled side-by-side**: three variants of the same 30–40 s passage in one
synced video (A | B | C), key written to a file and left unread until the
verdict. Winners become constants; losers and their flags are deleted the same
turn. `$CLAUDE_JOB_DIR`-style scratch scripts did this in the last session; the
recipe is: export three HTMLs with a temporary flag, record each with
`record-ensemble.cjs`, `ffmpeg hstack` with `drawtext` labels.
Numbers are evidence about motion, never proof of dance. Do not claim to have
watched or heard anything. Measure before sending: twice a variant turned out
to be broken or a no-op, which a quick measurement caught.

Blind-test record so far. Kept: hand-path low-pass, figure clock with 0.8 m/s
cap, wrist drag (strong), disc roll = travel + flips, spin 280°/m. Died: beat
pulse, keys pacing, figure carry, melody contour, plain joint lag, wrist whip
on moments, suspension at figure peaks, three other roll drivers (lead, spin
one-way, twirl). Lesson: small posture pulses and small timing shifts are
invisible; structural changes and changes to the hand object read.

## What exists

- `scripts/dance_memory.py`, `dance_stems.py`, `dance_structure.py` build the
  sidecar (`musicalMemory`, `stemInterpretation`, `musicalStructure`) from audio
  and Demucs stems.
- `crates/hyst-compile/src/director.rs`: sidecar parsing and evidence helpers.
- `crates/hyst-compile/src/director/figures.rs` (about 990 lines):
  `compile_figures`, the planner.
- `crates/hyst-compile/src/ensemble.rs`: rig, forward kinematics, score type,
  quintic sampling and validation.
- `crates/hyst-previz/examples/ensemble_preview.rs` + `src/ensemble.html`:
  browser preview at 60 fps, canvas 2D, one offline file: shaded capsule links,
  pedestal with marks that turn with the base, mirror disc on a stem (two
  distinct faces), cast shadow, depth-sorted hand trail, drag-to-orbit, red
  zones, critique panel.

Planner in one paragraph: the song is cut at measured transitions and phrase
edges; each stretch gets a class from stem levels; each class has a sequence of
hand figures in arm-relative coordinates, mirrored on each repeat, travelling
round the base. The hand path is low-passed. A **figure clock** stops during
holds, caps path speed at 0.8 m/s and makes lost time up at 15% extra pace.
Moments: section arrivals (prepare, arrive, living hold, release) and
keys/guitar flourishes (passed through); a true freeze only on a cut. Joints
are solved per knot (damped least squares, base faces the hand, zone
penalties) with a **wrist drag** posture preference (wrist trails the hand's
rise and fall; the other joints compensate, so the hand path is unchanged).
The **wrist roll** is driven outside the solver: 280° per metre of hand travel
in fast sweeps only, direction from the sweep relative to the figure's steady
travel, plus a half turn across each moment in alternating directions. A
follower then limits each joint's speed and acceleration, brakes before end
stops and **near zones** in proportion to clearance; a hard zone check
bisects back if still needed. The roll is exempt from zone braking.

## Commands

```
D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
cargo run --release -p hyst-previz --example ensemble_preview -- \
  $D/song-figures-N.html instant-crush.m4a $D/instant-crush.notes.sidecar.json \
  [--score OUT.json] [--zone x0,y0,z0,x1,y1,z1] [--groove-only] [--no-reuse] [--drag GAIN]
node $D/record-ensemble.cjs $D/song-figures-N.html $D/instant-crush.m4a $D/clip.mp4 START SECONDS
```
Open the HTML from disk (audio sits beside it). The recorder draws the canvas
only, max 40 s, fixed camera. `$D` is outside git; never commit media. Stems are
in `$D/stem-analysis/`; the Demucs environment is gone, do not regenerate.
Checks: `cargo test --workspace --exclude hyst-render`, clippy `-D warnings` on
hyst-compile/-output/-previz/-cli, `cargo fmt --all --check`,
`node crates/hyst-previz/tests/ensemble.cjs`. Do not run hyst-render tests (GPU).
Shell note: commands that contain the `$D` path together with pipes or `&&`
chains may be refused by the worktree guard; put such steps in a script file.

## Next work, in the user's order

1. **Keys decide** (the main job, for this fresh iteration). The user: "follows
   music OK, could be a tad better". Nothing follows keys/guitar/voice directly.
   Two earlier attempts (pace from keys activity, hand height from a pitch
   proxy) were invisible and deleted. The next attempt must be structural:
   build a note tracker on the `other` stem (onsets, rough pitch contour,
   phrase starts and ends), then let it choose **when figures change** and
   which figure follows, instead of fixed beat counts. Judge by side-by-side
   against the current version.
2. **Hand object.** Decide what the hand holds (disc, faceted mirror), then
   include its shape in floor and zone checks, and decide whether the roll
   should aim it (at a light or the viewer) on moments.
3. **Many arms** with dynamic red zones, as moving zones inside the figure
   planner. Zone braking exists; untested with several or moving zones.

## Known weak points

- Follower limits (design 180°/s, 800°/s²; envelope 240°/s, 8000°/s²) are
  guesses for hobby-class servos; no load, gravity or inertia model. Wrist drag
  about triples wrist travel and runs the wrist near the acceleration cap;
  `--drag` is the knob if a real wrist servo cannot keep up.
- The disc rim (6 cm past its centre) is not in the floor/zone check.
- The roll's travel part nets about one direction over the song.
- `fit_tangents` still cascades: one infeasible segment zeroes neighbouring
  tangents until fast segments fail. The last two triggers were fixed at their
  source (zone braking of the roll; zero tangent on the last knot). Its error
  now prints the neighbouring knots.
- Shoulder reaches −109.5° of a −110° limit; within 1° of it about 3% of the song.
- Stretch class comes from fixed thresholds on stem levels.
- Arrival and flourish poses are two or three fixed shapes.
- Cut detector is tested only on a synthetic fixture.
- Arrivals stop 0–80 ms late (follower lag); knots are 68 ms apart.
- Only 1:24–2:04 of the song has been reviewed by eye in the last session.
- `AGENTS.md` is long; trimming it into a history file was proposed, not done.

## Rules of engagement

Ask the user before artistic choices they have not made. Do not stack layers
without a side-by-side. Keep code small: delete what loses. Append an honest
entry to `docs/DANCE_HANDOFF.md` and `AGENTS.md` when you stop.
