# Fresh-agent prompt — continue the single-arm dance

This work was merged into `master` (pull request 12). Start from current
`master` on a new branch; open a pull request when a slice is done. Do not push
to `master` directly. Communicate terse and exact. Frozen `src/` and `tools/`
are read-only. Never drive hardware.

First, before any code: read this file, then the last four entries of
`docs/DANCE_HANDOFF.md` (older entries and most of `AGENTS.md` §5 describe
deleted code; skip them). Read `crates/hyst-compile/src/director/figures.rs` in
full and skim `director.rs`, `ensemble.rs`, `crates/hyst-previz/src/ensemble.html`
and `examples/ensemble_preview.rs`. Run the checks under "Commands" and export one
preview to confirm the tree works. Then report to the user in a few lines: what
you understand the goal and state to be, what you will do first, and any
question that blocks it. Start work after that report; do not wait for approval
unless you asked a blocking question.

## What the user wants (their words, settled)

- A viewer should think "beautiful", then "impressive", then "how did they do
  this". Idea source: OK Go "Love" (robot arms with mirrors).
- One arm that truly dances is the goal now. Many arms, mirrors and projection
  come after, and need "dynamic red zones" (each arm a moving zone for the others).
- Interpretation must be automatic. Human timestamps in
  `scripts/instant_crush.acceptance.json` are validation only, never input.
- Dance works from offline sidecars only. No live audio.
- **Real hardware is the end goal.** Motion no servo arm could execute is a defect.
- The base rotates a full continuous 360°. Settled rig fact. Everything else
  about the rig (lengths, limits, speeds) is invented until measured.
- The user's own model of dancing this song: percussion is the floor, the
  keys/guitar are the decision-maker (their flourishes cue movement from state to
  state), vocals give the emotion. In the break the guitar solo leads.
- A hold is almost never a dead stop: small slow movement. A true freeze only
  on a cut (dense, nothing, dense). This song has none.
- This song has no sharp passages; flicks are wrong here.
- Test song stays Instant Crush.

## How the user reviews (keep this loop)

The user judges by eye and is fast and precise. Send a short clip (30–40 s, with
audio) of a stated passage after each change; one change per version. The preview
has a critique panel (hold M to mark, 1–9 tags, Export JSON to `~/Downloads`).
When a layer's value is in doubt, run a **blind ablation**: same passage with and
without it, shuffled labels, key kept unread until the verdict. Four of five
layers died that way. Numbers are evidence about motion, never proof of dance.
Do not claim to have watched or heard anything.

## What exists

Live path only (older planners were deleted on purpose; they are in git at
`dance-checkpoint`, 725127a):
- `scripts/dance_memory.py`, `dance_stems.py`, `dance_structure.py` build the
  sidecar (`musicalMemory`, `stemInterpretation`, `musicalStructure`) from audio
  and Demucs stems.
- `crates/hyst-compile/src/director.rs`: sidecar parsing and evidence helpers
  (stretch class from stem levels, transitions, onsets, recurrence).
- `crates/hyst-compile/src/director/figures.rs`: `compile_figures`, the planner.
- `crates/hyst-compile/src/ensemble.rs`: rig, forward kinematics, score type,
  quintic sampling and validation.
- `crates/hyst-previz/examples/ensemble_preview.rs` + `src/ensemble.html`:
  browser preview at 60 fps with hand trail, floor shadow, drag-to-orbit, red
  zones, speed select, critique panel.

Planner in one paragraph: the song is cut at measured transitions and phrase
edges; each stretch gets a class from stem levels; each class has a sequence of
hand figures (gather = inward spiral, rise, open, circle, arc, sway, reach,
eight) in arm-relative coordinates, mirrored on each repeat, relative to the
hand's current facing and travelling around the base, so the full 360° is used.
Returning material reuses the same sequence, larger. The hand path is low-passed.
Moments: section arrivals (prepare, arrive, living hold, release) and keys/guitar
flourishes (reached and passed through); a true freeze only on a cut. Joints are
solved per knot (damped least squares, base faces the hand, zone penalties), then
a follower limits each joint's speed and acceleration and brakes before end
stops, then a hard red-zone clearance check bisects back if needed.

## Commands

```
D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
cargo run --release -p hyst-previz --example ensemble_preview -- \
  $D/song-figures-N.html instant-crush.m4a $D/instant-crush.interpreted.sidecar.json \
  [--score OUT.json] [--zone x0,y0,z0,x1,y1,z1] [--groove-only] [--no-reuse]
node $D/record-ensemble.cjs $D/song-figures-N.html $D/instant-crush.m4a $D/clip.mp4 START SECONDS
```
Open the HTML from disk (audio sits beside it). The recorder draws the canvas
only, max 40 s, fixed camera. `$D` is outside git; never commit media. Stems are
in `$D/stem-analysis/`; the Demucs environment is gone, do not regenerate.
Checks: `cargo test --workspace --exclude hyst-render`, clippy `-D warnings` on
hyst-compile/-output/-previz/-cli, `cargo fmt --all --check`,
`node crates/hyst-previz/tests/ensemble.cjs`. Do not run hyst-render tests (GPU).

## Next work, in the user's order

0. **Better render (done as version 13, awaiting user review).** The user called the arm render
   "too shitty". It is a 2D canvas of thick lines and dots. Ask one question
   about the look they want if unclear; otherwise make the arm read as a solid
   3D object: shaded links with thickness, joint housings, a base, a visible
   hand/end effector, ground shadow, sensible lighting and depth ordering. Keep
   it one portable HTML file, keep the critique panel, trail, zones and orbit.
   Decide between improving the canvas and a small embedded WebGL renderer by
   what stays a single offline file. The same dance must look better, so the
   user can judge motion more fairly. The recorder must keep working.
1. **Body.** Motion should travel through the arm: base to wrist (wave, whip)
   or wrist leading and arm following; wrist and elbow lag or counter-move.
   Now the arm is a stick that follows its hand and the posture comes from one
   neutral bias. The user called it "stiff" early on; never addressed.
2. **Speed smoothing** (user's guess): hand speed is whatever each figure's
   shape gives (median 0.32 m/s, peaks 2.1). Re-time along path length while
   keeping arrivals on time.
3. **Stillness and suspension**, beyond the living holds.
4. **Keys decide.** Still open and important: nothing follows keys/guitar/voice
   directly. Two attempts (pace from keys activity, hand height from a pitch
   proxy) were invisible in blind tests and deleted. A next attempt must be
   structural (keys choose figures and their timing), probably needs a real
   pitch/onset tracker on the `other` stem, and must pass a blind test.
5. **Many arms** with dynamic red zones. Old arm-vs-arm code was deleted; build
   it as moving zones inside the figure planner.

## Known weak points

- **Planner can fail to compile a score.** `--groove-only --no-reuse --zone
  0.15,0.3,0.25,0.6,0.6,0.7` together ends with "cannot fit tangents ... accel
  13856/8000" (each flag alone works). When the red-zone bisect stops a joint
  abruptly, `fit_tangents` halves neighbouring tangents and the failure cascades
  into rest-to-rest segments that exceed the envelope. Dynamic red zones (many
  arms) will hit this constantly; fix it before step 5, ideally by making the
  follower zone-aware instead of bisecting after it.
- Shoulder sits within 1° of its end stop about 11% of the song.
- Follower limits (design 180°/s, 800°/s²; envelope 240°/s, 8000°/s²) are
  guesses for hobby-class servos; no load, gravity or inertia model.
- Stretch class comes from fixed thresholds on stem levels.
- Arrival and flourish poses are two or three fixed shapes; likely repetitive.
- Cut detector is tested only on a synthetic fixture.
- Arrivals stop 0–80 ms late (follower lag); knots are 68 ms apart.
- `AGENTS.md` is long (about 38k tokens of history); trimming it into a history
  file was proposed and not done.

## Rules of engagement

Ask the user before artistic choices they have not made. Do not stack layers
without a blind test. Keep code small: the planner is about 840 lines and every
surviving part was either requested or verified by eye. Append an honest entry
to `docs/DANCE_HANDOFF.md` and `AGENTS.md` when you stop.
