# Fresh-agent prompt — the dancing arm ensemble (state at version 47, 2026-10-06)

Continue on branch `keys-decide` (draft pull request open; never push to
`master`). Frozen `src/` and `tools/` are read-only. Never drive hardware.
Write to the user in plain, short sentences with numbers; they judge by eye and
answer by clock time.

## Read this first: what you can and cannot do

**Everything the dance is made from lives outside git, on the user's machine:**
the audio, the sidecars the planner reads, the separated stems, the exported
previews, the videos, the video recorder and all measuring scripts. If you run
somewhere without that machine's disk (a web or cloud session), you have the
code and the tests and nothing else. Then:

- You **can** read and change the planner, run the tests, clippy and fmt, and
  reason from the measurements recorded in `docs/DANCE_HANDOFF.md`.
- You **cannot** plan a real song, reproduce `hexagon-47.html`, measure a
  change on a song, or make a video. Say so plainly; do not claim a change
  improved the dance. A change to the planner is unverified until someone
  exports and measures it on the user's machine.
- If the task needs real songs, ask the user to either run a local session or
  have the sidecars committed (about 12 MB of JSON for three songs; analysis
  data, not audio; not done so far because nothing outside code was ever
  committed).

On the user's machine the paths are under "Commands" below.

## What this is

Six servo arms on a hexagon, facing its centre, each holding an irregular
mirror ball, dancing to a song. The dance is planned offline from a "sidecar"
(a JSON analysis of the song) by one function,
`hyst_compile::director::figures::compile_ensemble` (`compile_figures` is its
one-arm case). `hyst-previz`'s `ensemble_preview` example turns the plan into a
self-contained HTML preview; a script outside git records that into a video.
A projector showing the visualizer (the other half of the project) will light
the arms. Real hardware is the end goal; nothing has been built or driven.

## Where we are

Three songs have been danced with the same planner:

| Song | Why it matters | User's verdict |
|---|---|---|
| Daft Punk, "Instant Crush" | the song everything was tuned on; steady tempo | version 44: "Its nice now"; version 46: jerks at 3:52, 4:08–4:09, 4:36 |
| Bowie, "Five Years" | live drummer, triple feel, tempo speeds up 6.5 %, soft opening to loud climax | version 46: "generally OK, its a difficult song for this and for dancing in general" |
| Justice, "Presence" | instrumental, steady 130 bpm, builds and drops | version 46: a long list of jerks, low-energy stretches, wrong labels, no payoff at the drop |

**Version 47 answers that review and has not been reviewed.** The three
whole-song videos were made and reported to the user; no verdict yet. Three
questions are open with the user:

1. Are Instant Crush's flourishes now too tame? (Their sharp form won a blind
   test; version 47 slowed them.)
2. Does the rise at the "Presence" drops read as a payoff, or does it need more?
3. What next: moves that follow the lead instrument's melody, or the remaining
   jolts?

Do not start either piece of work before the user answers; they are large and
the user chooses the order.

## What version 47 does that version 44 did not

All in `crates/hyst-compile/src/director/figures.rs` and `director.rs`; each
has its reason and numbers in the last five entries of `docs/DANCE_HANDOFF.md`
(second song, versions 45, 46, 47).

- **Intensity**: loudness round a time against the song's own loud passages.
  Gentle passages get the soft flourish, smaller arrivals, less surge.
- **Classes by share of the sound.** Each stretch of the song gets a class
  (`character` in `director.rs`) from the four stems (bass, drums, vocals,
  other): each stem's level against its own loudest, and now also its share of
  mean power and the overall loudness. Names: silence, interlocked (the song at
  full; chorus moves), vocal-led, bass-led, melody-led (bass rule, but the
  "other" stem outweighs the bass; same dance), percussive-open, kick-led (a
  sparse kick carries the power; same dance as percussive-open), textural,
  sparse. **The thresholds are tuned on three songs and are fragile**; a song
  with flat loudness would make every sung passage "interlocked".
- **No arm rests.** The drop-out and pairs formations are deleted. Every class
  is Unison except percussive-open and kick-led, which alternate Mirrored and
  Unison; a run under 24 beats keeps the formation before it.
- **Contrast phrase**: a run longer than about 128 beats plays another class's
  phrase once, then returns.
- **Moments limited in speed.** A flourish or arrival takes as long as its
  travel needs so that it adds at most 0.6 m/s to the hand; it still lands on
  time. No stab surge within two beats of a moment.
- **Surge stretched to the note spacing** of the lead instrument (it idled and
  burst where notes were sparse). The figure clock never runs ahead of the
  music, so sparse notes surge less than dense ones; that is known and kept.
- **Arrivals have a direction.** Where the music lifts (a drop), the arms rise
  to full height and hold longer; where it falls away, the arrival is small.
- **Calmer without drums**: the figure clock runs at 0.65 where the drum stem
  is silent.
- **Abort fixed**: "cannot fit tangents" when arms were still moving at the
  song's last instant.

## What the user wants (their words, settled)

- A viewer should think "beautiful", then "impressive", then "how did they do
  this". Idea source: OK Go "Love" (robot arms with mirrors).
- Six arms, concentric, symmetric. All dancing all the time: resting arms were
  rejected as low energy and not synchronized. "The best looking one is sync. I
  also like mirror"; canon and ripple are "more of a flurish move".
- The arms sharing each other's reach is the "wow"; they must never collide.
- Interpretation must be automatic, from offline sidecars only; no live audio.
  Human timestamps (`scripts/instant_crush.acceptance.json`) and published
  tabs are for checking, never planner input.
- The dominant instrument should lead the arm. The voice is not an instrument
  but a fluid up, down, stop and loudness.
- A hold is almost never a dead stop. Jitter and jerks are defects the user
  spots at once; so is purposeless constant motion, and so is hanging around.
- Motion no servo arm could execute is a defect.
- Rig, settled: five servos (base yaw continuous 360°, shoulder, elbow, wrist
  bend, wrist roll). Lengths, limits and speeds are invented until measured.
- Hand: a reflective, non-spherical object; the lumpy mirror ball is preferred
  over the disc. Other implements must stay possible.
- Do not polish the canvas preview unless asked.

## How the user reviews

By eye, on whole-song videos with a clock in the corner, reporting clock times.
For a single yes-or-no choice between variants: one shuffled, synced
side-by-side (A | B | C) with the key in a file left unread until the verdict;
the winner becomes a constant and the losers and their switches are deleted in
the same turn. Measure before you send, give a table of what changed, and tell
the user what to look for and when. Never claim to have watched or heard
anything. Ask before artistic choices the user has not made.

Lessons from the record: small posture or timing changes are invisible,
structural changes read; nearly every "jerk" the user has reported turned out
to be a flourish, an arrival or the stab surge, so measure the named clock time
before theorising (`jolts.py`, `spans.py`, `look5.py`).

## Known weak points (none of these is fixed)

- **Arms braking for each other.** In unison the arms brake for their
  neighbours at moments that depend on where the figures happen to point. Any
  change to the plan moves these jolts around by several per song. The
  mechanism (the follower's braking and the hard check in `compile_ensemble`)
  has not been touched.
- "Presence" still has hard jolts at 0:48, 1:56 and 3:11 (flourishes passed
  round the ring); Instant Crush one four-arm jolt near 3:43; 3:52 is softer,
  not gone.
- **Following the lead instrument.** Only the label says "melody-led". The
  lead lane drives the surge and the swell in every class, as before; it does
  not shape the moves. The user asked for exactly that on "Presence"
  (2:31–2:55: "really nice and emotional and has energy and could be followed").
- **Beat tracking is outside the repo.** "Five Years" needs a tempo map
  (tracked beats, audio warped to a steady grid for analysis, video played back
  through the map; the interactive page has no map and drifts up to 2.3 s).
  "Presence" needed its grid refitted to the drum hits (it was 45 ms late; the
  base analysis's beat tracker lags). Both are scratch scripts using librosa.
  They belong in `scripts/dance_memory.py` and in score playback.
- Entering Mirrored from a widely turned heading makes neighbours meet and
  stop; dodged for short runs only.
- Red zones for keeping arms off equipment: axis-aligned boxes exist
  (`--zone`), tested with one and two arms and with a ring. Which shapes the
  user needs is unanswered; do not invent shapes.
- The preview's light is plain patches. Follower limits are guesses for hobby
  servos; no load or gravity model. Six arms compile in about 16 s.
- `AGENTS.md` is very long; only its top section and its last few entries are
  current.

## Commands

Anywhere:
```
cargo test --workspace --exclude hyst-render      # 139 pass; six-arm tests take ~15 s each
cargo clippy -p hyst-compile -p hyst-output -p hyst-previz -p hyst-cli --all-targets -- -D warnings
cargo fmt --all --check
node crates/hyst-previz/tests/ensemble.cjs
cd scripts && python3 -m unittest discover -p "test_dance_*.py"
```
`hyst-render` needs a GPU; leave it out.

On the user's machine only:
```
D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
cargo run --release -p hyst-previz --example ensemble_preview -- \
  $D/OUT.html SONG.m4a $D/SONG.notes.sidecar.json --ring 6,0.8 \
  [--clearance 0.1] [--implement ball|disc] [--zone x0,y0,z0,x1,y1,z1] [--score OUT.json]
```
Sidecars: `instant-crush.notes.sidecar.json`, `five-years-steady.notes.sidecar.json`
(with `five-years.tempomap.json`), `presence.notes.sidecar.json`. The export
must reproduce `hexagon-47.html`, `five-years-hexagon.html`,
`presence-hexagon.html`.

Tools in `$D/tracker-scratch/newsong/`:
- A new song: `song.sh SOURCE SLUG` (resample, base sidecar, memory, Demucs
  four and six stems, stems, structure, notes, export). Check the printed grid
  support. Grid late or early: `regrid.py`, then `songtail.sh SLUG`. Tempo
  drifts: `beatmap.py`, then `song2.sh SLUG`.
- All three songs at once: `three.sh TAG` (exports and prints classes,
  formations, kicks, jolts).
- One song: `classes.py`, `acts.py` (stem activity and share per 10 s),
  `jolts.py` (every hard jolt with its move and moment), `spans.py A B T0 T1 …`
  (two versions over clock windows), `look5.py` (half-second detail).
- Videos: `songvideo.sh SLUG SECONDS` and `hexreview.sh SOURCE.html OUT.mp4`
  (whole song with a clock; about ten minutes each). The recorder
  `$D/record-ensemble.cjs` reads `HYST_TEMPO_MAP`.

Environments are under `/secondary/hyst-env` (Demucs; librosa is in the
`basic-pitch` one); the root disk is nearly full. A shell guard there refuses
commands that mix the `$D` path with pipes, `&&`, loops or heredocs: put such
steps in a script file and run that.

## Rules of engagement

Keep code small; delete what loses. Stay inside `hyst-compile` and
`hyst-previz` for dance work. Additive sidecar changes only. Append an honest
entry to `docs/DANCE_HANDOFF.md` (what changed, measured numbers, what is not
verified) and a short one to `AGENTS.md` when you stop, then commit and push
to `keys-decide`.
