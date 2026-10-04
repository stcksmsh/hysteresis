# Fresh-agent prompt — continue the single-arm dance

Continue on branch `keys-decide` (draft pull request open; do not push to
`master`). Communicate terse and exact. Frozen `src/` and `tools/` are
read-only. Never drive hardware.

First, before any code: read this file, then the `DANCE_HANDOFF.md` entry
"Versions 28–30", "Version 31", "Version 32" and "Version 27" ("Version 13" onward only
if you need the earlier blind-test history). Read `crates/hyst-compile/src/director/figures.rs` in full and skim
`director.rs`, `ensemble.rs`, `scripts/dance_notes.py`. Run the checks under
"Commands" and export one preview: it must be byte-identical to
`song-figures-34.html`. Report in a few lines what you understand and what you
will do first, then start; do not wait for approval unless you asked a blocking
question.

## What the user wants (their words, settled)

- A viewer should think "beautiful", then "impressive", then "how did they do
  this". Idea source: OK Go "Love" (robot arms with mirrors).
- One arm that truly dances is the goal now. Many arms and projection come
  later and need "dynamic red zones".
- Interpretation must be automatic. Human timestamps
  (`scripts/instant_crush.acceptance.json`) and published notes (the Songsterr
  tab) are validation only, never planner input.
- Dance works from offline sidecars only. No live audio.
- **Real hardware is the end goal.** Motion no servo arm could execute is a defect.
- **Rig, settled:** five servos: base yaw (continuous 360°), shoulder, elbow,
  wrist bend, wrist roll. Lengths, limits and speeds are invented until measured.
- **Hand, settled:** a reflective, non-spherical object, for the first demo a
  mirror disc held by its edge in line with the arm. Never a ball.
- A lifelike render comes much later. Do not polish the canvas preview unless asked.
- **The note data is for the whole installation** ("the machine behind it"), not
  only the arm. It lives in the sidecar and must work for other songs (the
  user's example: twin guitars, one left, one right). Per instrument the target
  is timing, relative pitch (up/down) and some loudness, not perfect notes.
- **The voice is not an instrument** but a fluid up/down/stop/loudness.
- **The dominant instrument leads the arm; the second one drives sub-elements.**
  Which sub-elements is not settled (accents from the second lane lost a test).
- Nothing is one-size-fits-all: sections differ, and so should flourishes and style.
- A hold is almost never a dead stop. This song has no sharp passages; flicks
  are wrong here. Jitter is a defect; purposeless constant motion is also a defect.
- Keep scope finite. Test song stays Instant Crush until the user supplies another.

## How the user reviews (keep this loop)

The user judges by eye, fast and precise. For every motion or look decision
send **one shuffled, synced side-by-side** (A | B | C, 30–40 s, with audio); the
key goes to a file and stays unread until the verdict. Winners become
constants; losers and their flags are deleted the same turn. "No difference"
means delete. Measure variants before sending (twice a variant was a no-op, once
the effect was 15 % and had to be strengthened). Do not look at stills of a
blind clip. Do not claim to have watched or heard anything.
The user is often on remote control: **send every file with SendUserFile**
(30 MiB limit; re-encode larger videos). For tracker output the user wants a
scrolling piano-roll video with the song's audio, not plots.

Blind-test record. Kept: hand-path low-pass, figure clock with 0.8 m/s cap,
wrist drag 240, disc roll = travel + flips, spin 280°/m, **surge after each
stab of the leading lane**, **hand size and height follow the leader's swell**
(full strength; break and verse), **hand rises with a high voice** (0.65),
**soft flourishes in a steady stream** (sharp there was "too much").
Kept without a visible difference, for the hardware: figure clock smoothed over
two knots. Died: beat pulse, keys pacing, figure carry, melody
contour (from a poor pitch proxy), plain joint lag, wrist whip, suspension at
peaks, three roll drivers, figures snapping to the leader's phrase starts,
figures picked by the leader's pitch step, accents from the second lane,
arriving on the stab. Lesson: small posture pulses and small timing shifts are
invisible; structural changes read. A reaction that swaps in short up/down
figures wobbles across the travel line; the user wants the hit along it.
Variants in one side-by-side must keep the same choreography: when two
de-jitter candidates shifted figure timing the user could not judge them.
Tell the user what to look for with each clip; they asked.

## What exists

- Sidecar pipeline: `scripts/dance_memory.py`, `dance_stems.py`,
  `dance_structure.py`, and `dance_notes.py` (adds `noteTrack.lanes`: one lane
  per stem WAV with onsets `[time, rough pitch, strength]`, phrases,
  `levelPerBeat` and `brightnessPerBeat`).
- `crates/hyst-compile/src/director/figures.rs`: `compile_figures`, the planner.
  `director.rs`: sidecar parsing. `ensemble.rs`: rig, kinematics, score.
- `crates/hyst-previz`: `examples/ensemble_preview.rs` + `src/ensemble.html`.

Planner in one paragraph: the song is cut at measured transitions and phrase
edges; each stretch gets a class from stem levels; each class plays a sequence
of hand figures with fixed beat counts, mirrored on each repeat, travelling
round the base. The hand path is low-passed. A figure clock stops during holds,
caps path speed at 0.8 m/s and makes lost time up at 15 % extra pace. The
instrument lanes are ranked per beat by level (voice and drums excluded; 3 dB
for four beats to take over, backdated); while the leading lane plays stabs
(empty beats between its hits) the clock surges after each hit; where it does not, figure size follows
its loudness and hand height its brightness. The clock is smoothed over two
knots. The hand rises and extends while the vocal lane sings well above its
median pitch. Moments:
section arrivals and "flourishes" (strongest `other`-stem onset per ~16 beats;
slow and soft where the leader plays a steady stream).
Joints are solved per knot with a wrist-drag posture preference; the wrist roll
is driven outside the solver; a follower limits speed and acceleration and
brakes near end stops and zones.

## Commands

```
D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
cargo run --release -p hyst-previz --example ensemble_preview -- \
  $D/song-figures-N.html instant-crush.m4a $D/instant-crush.notes.sidecar.json \
  [--score OUT.json] [--zone x0,y0,z0,x1,y1,z1] [--groove-only] [--no-reuse] [--drag GAIN]
node $D/record-ensemble.cjs $D/song-figures-N.html $D/instant-crush.m4a $D/clip.mp4 START SECONDS
python3 scripts/dance_notes.py $D/instant-crush.interpreted.sidecar.json \
  /secondary/hyst-env/stems6/htdemucs_6s/instant-crush-stereo-analysis $D/instant-crush.notes.sidecar.json
```
Checks: `cargo test --workspace --exclude hyst-render` (136 pass), clippy
`-D warnings` on hyst-compile/-output/-previz/-cli, `cargo fmt --all --check`,
`node crates/hyst-previz/tests/ensemble.cjs`,
`cd scripts && python3 -m unittest test_dance_notes`. No hyst-render tests (GPU).
The recorder draws the canvas only, max 40 s. `$D` is outside git; never commit
media. Shell note: commands that mix the `$D` path with pipes, `&&` or
heredocs are refused by the worktree guard; put such steps in a script file.

Review helpers, outside git in `$D/tracker-scratch/` (paths inside point at
that folder): `variants.sh NAME FLAG V1 V2 V3` exports and measures three
variants; `sbs.sh NAME START SECONDS V1 V2 V3` records the shuffled
side-by-side and writes `$D/blind-NAME-key.json`; `measure.py`, `diff.py`,
`pulse.py` measure hand speed and how far variants differ; `evalkit.py` and
friends score tracker lanes against the tab; `scrub*.py` make the piano-roll
videos. Environments under `/secondary/hyst-env` (basic-pitch, demucs,
muscriptor with the user's HuggingFace token); root disk is nearly full.

## Where it stands (version 39)

The single arm was approved on a whole-song review at version 32. Since then:
the hand object is rig data (`Rig.implement`, default a lumpy mirror ball,
`--implement disc`); a projector faces the mounting surface from straight above
(user's layout) and the preview draws each mirror's reflection; several arms
are planned by `compile_ensemble` with a cross-check between them; in a ring
every arm faces the centre; the planner picks a formation per section (Unison,
Mirrored, Canon, Ripple, Pairs, DropOut). Read the handoff entries "Version 33"
to "Version 39". Export the hexagon with `--ring 6,0.8`; whole-song review
videos are made by `tracker-scratch`-style scripts outside git (record in 40 s
chunks, concatenate, add a clock, keep under 30 MiB).

The user's words on the ensemble: synchronized dancing is "a different game"
(all together, inverses, one by one, drop-outs, pairs, complements); it should
"decide itself"; version 35 was "not synchronized enough, too low energy" and
"too far apart, dynamic red zones overlapping is what makes it WOW"; canon
should delay each arm by a fraction of the move, circular or spreading both
ways and back. Version 37 was reviewed once: the user found a stutter in the ripple (fixed in 38). Version 38 was reviewed: a draw-order bug (fixed) and "does not follow the music enough, needs to be more on point" (open). Version 39 **has not been reviewed**.

## Next work

1. **The user's verdict on the version 39 video** (`hexagon-39-full.mp4`), and their answer to "what does on point mean" (four readings were offered; see the handoff).
   Do not build further ensemble choreography before it.
2. **Overlap outside unison.** Canon, Ripple and Mirrored keep each hand on its
   own side of the line to its neighbours, because out-of-step neighbours
   blocked each other. The user's "wow" is overlapping zones; getting it in
   canon needs timing planned so paths interleave. Not started.
3. **The formation table** is an agent's guess (class and occurrence only). The
   long unison from 3:33 to 5:23 may be too uniform. "Complements" is undefined.
4. **Hexagon size, projector height, the object's real size**: all assumed.
5. Paused or parked: sidecar lanes for the machine; the disc roll's chatter
   (the user saw no jitter at 60 fps); flourish poses are two fixed shapes.

## Known weak points

- Stab surges exceed the speed cap by up to half; approved by eye on 3:32–4:12
  only. Hand acceleration outside moments is 1.7 m/s² p95 since the clock
  smoothing. Constants in the clock loop of `figures.rs`.
- The swell has no gate for "single flowing line": it runs in the verses too
  (user approved one verse). The voice lift also raises 2:45–3:05 and other
  high vocal stretches the user has not reviewed.
- An old sidecar no longer reproduces version 26.
- The break's leader change is found at 188.8 s; the user hears it at 185.
- Lanes come from six-stem Demucs: the solo guitar lands in `other`, the
  `piano` stem is nearly empty, keys and synths share `other`.
- All tracker numbers are one song against one fan-made tab.
- Follower limits are guesses for hobby servos; no load or gravity model.
  Wrist drag about triples wrist travel.
- The disc rim is not in the floor/zone check. `fit_tangents` can still cascade.
- Stretch class comes from fixed thresholds on stem levels. Arrival and
  flourish poses are two or three fixed shapes.
- Reviewed by eye so far: 1:24–2:04 (version 26), the whole song once
  (version 26), 2:05–2:45, 3:00–3:40, 3:32–4:12 and 3:52–4:32 in side-by-sides.
- `AGENTS.md` is long; trimming it was proposed, not done.

## Rules of engagement

Ask the user before artistic choices they have not made. Do not stack layers
without a side-by-side. Keep code small: delete what loses. Append an honest
entry to `docs/DANCE_HANDOFF.md` and `AGENTS.md` when you stop.
