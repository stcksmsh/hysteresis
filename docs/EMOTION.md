# Emotion: encode a song's feeling, keep it, and dance it

Status: spec, 2026-10-12. Nothing here is built. Branch `keys-decide`.
Supersedes the outlet table of `docs/B_WORKSPACE.md` (B is parked, not
removed: its round-2 verdict was "not enough differences, all 3 are mostly good").

## Why

Anyone can make an arm that goes up and down with the beat. What makes this an
art piece is that the arm conveys the feeling of the song. That is the hard
part, and the through line of the user's work.

Two lessons from 47 versions and the B rounds:

1. **Hand-written mappings cap the result.** Every attempt so far turned the
   feeling into a few named signals wired to a few named motions ("tension →
   coil"). That limits the dance to the author's vocabulary. The pipeline here
   learns its structure from data and is checked against it; no stage assigns
   an emotional meaning to a motion by hand.
2. **The whole body dances, not the fingertip.** Today motion is a hand target
   and the joints are solved to reach it. Shape, succession through the joints,
   effort quality, initiation and breath carry most of what a body expresses.
   The hand path becomes one ingredient among them.

## The pipeline

```
song ──A──▶ emotion encoding (per time step, high-dimensional) ──C──▶ whole-body motion
              │ check 1: does it hold emotion?                     │ check 2: is the structure kept?
              ▼                                                    ▼
          public labelled data                              check 3: does a person read it?
```

- **A, encode**: reduce the song, per time step, to an encoding that holds its
  feeling. It need not be human-readable.
- **C, decode**: expand the encoding back up into movement of the whole body,
  keeping the encoding's structure: songs that feel alike move alike, songs that
  feel different move differently.
- Every stage has a check fixed **before** results are seen. A stage that fails
  its check stops the work and is reported; nothing downstream is built on it.

## Rules

- One arm only until stage 4 passes. The ensemble inherits what wins.
- No stage hand-assigns meaning ("sad = low"). Meaning comes from labelled data
  and from the user's judgments.
- Version 47 stays reachable and byte-identical (golden digests, `Off`).
- Additive sidecar changes only. Generated data, models, audio and datasets stay
  outside git.
- Frozen `src/` and `tools/` stay read-only. Never drive hardware.
- Every result is reported with numbers and the held-out set it was measured on.
  Nothing is "better" until its check says so.

## Stage 1: the encoder (check 1)

**Goal**: per time step (beat, and a 0.5 s grid for checking), an encoding of
the song's feeling.

**Candidates**, each alone and combined:
1. The current sidecar features (stem activity and level, rhythm, leader lane,
   brightness), summarised per window. **This is the baseline.**
2. B's expectation signals (surprise per level, tension, gain) from
   `director/workspace.rs`. Expectation is part of musical emotion (Huron).
3. MERT (`m-a-p/MERT-v1-95M`), layer-averaged or best layer.
4. CLAP (LAION, music-capable checkpoint).
5. Essentia's pretrained music models (Discogs-EffNet embeddings and its mood
   heads), if they install cleanly.

Windows: about 3–5 s, hop 0.5 s, then pooled per beat for the planner.

**Labelled data** (outside git, under `/secondary/hyst-data/emotion/`):
- **DEAM**: 1,802 songs (58 full-length, the rest 45 s excerpts), valence and
  arousal at 2 Hz, Creative Commons audio. Timing.
- **Emotify**: 400 one-minute clips, 4 genres, GEMS feelings (amazement,
  solemnity, tenderness, nostalgia, calmness, power, joyful activation, tension,
  sadness). The shape of the space: longing must sit far from thrilled.
- **PMEmo** (794 choruses, 2 Hz valence and arousal), only if its licence and
  audio allow.
- Read each dataset's manual. DEAM's labels differ between its 2014 and 2015
  releases; use one release and say which.

**Check 1, fixed in advance.** All splits are by song (no song in both train
and test), 5-fold, same folds for every candidate. Readouts are linear (ridge
or logistic), so the check measures what the encoding holds, not a model's
power.
- **Timing**: R² of the readout for DEAM dynamic valence and arousal on
  held-out songs.
- **Feelings**: on Emotify, the rank correlation between predicted and rated
  GEMS profiles per held-out clip, and nearest-neighbour agreement: is a clip's
  closest held-out neighbour's dominant feeling the same as its own?
- **Geometry**: the ratio of mean distance between clips of different dominant
  feelings to the mean distance within the same feeling (above 1 means the
  feelings separate).
- **Pass**: a candidate passes if it beats the baseline on timing and on
  feelings, with 95 % bootstrap intervals (over songs) that do not overlap the
  baseline's. The pick is the passing candidate with the best mean rank across
  the three measures. If none passes, stop and report.

**Report for the user** (diagnostic, not pass/fail): the three danced songs
encoded, and for each 10 s of each song its nearest labelled clips with their
feelings. The user reads it and says where it is wrong.

**Output**: an additive sidecar field `emotionEncoding` with `model`, `version`,
`dims`, `hopSeconds` and the per-step vectors, written by a script in
`scripts/emotion/`. The planner reads nothing from it yet.

## Stage 2: the body (motion space)

**Goal**: one arm whose whole body can move in a wide range of ways. No
emotional meaning is assigned to any of it.

- **Open shell.** The hand's space is the continuous top of the sphere (a
  direction plus an extension), not azimuth and elevation with a lid at 80°.
  Base yaw follows the hand's horizontal direction. Near the top, the planner
  picks the branch that turns the base least (in front, or the shoulder past
  vertical); a path straight over the top turns no base. The figure clock caps
  the base rate and acceleration the path needs, as `HAND_SPEED_CAP` caps hand
  speed. Full extension: open question for the user.
- **Body parameters**, per time, continuous:
  - shape: whole-arm curl and extension, arch, height
  - effort: sudden or sustained, strong or light, bound or free (follow-through,
    overshoot)
  - succession: direction (base to tip or tip to base) and delay between joints
  - initiation: which joint leads a move
  - breath: depth and rate of a slow expansion and contraction under everything
  - hand path: existing figures, with a weight against the body terms
- **Motion descriptors** for distances: per segment, from joint and FK
  trajectories (speed, acceleration and jerk per joint, posture height,
  extension and curl, joint-to-joint lag, periodicity).

**Check 2a, feasible**: speed caps, follower limits, no jolts over the
existing 9 m/s² mark beyond what `Off` has, over a sweep of the parameter space.

**Check 2b, distinguishable (the body study)**: silent odd-one-out triplets
drawn from different regions of the parameter space (see stage 4 for the test).
The user must pick the odd one in at least 2 of 3 trials over 24 triplets
(chance is 1 in 3). If the body cannot show visibly different ways of moving,
no mapping will help; stop and widen the space.

## Stage 3: the decoder

**Goal**: a map from the emotion encoding to the body parameters that keeps
the encoding's structure.

- Fit on segments from many songs (DEAM and Emotify audio plus the user's
  songs): the distances between segments in emotion space should match the
  distances between the motions they produce (representational similarity:
  rank correlation of the two distance matrices), with smoothness over time and
  the feasibility caps as constraints.
- **Check 3, fixed in advance**: on held-out songs, the rank correlation of the
  two distance matrices beats 99 % of 1,000 shuffles of the segment pairing
  (permutation test), and beats the same map fitted to the baseline encoding.
- The user's judgments from stage 4 then correct the map.

## Stage 4: does a person read it (check 3)

No more A | B | C preference clips: those measured fluidity well and emotion
not at all.

1. **Odd one out, silent.** Three short arm-only clips; the encoder calls two of
   their source passages alike and one different. The user picks the odd one.
   No words, no memory load. **Pass**: at least 16 of 24 correct (chance 8).
2. **Match or mismatch, with audio.** One song's audio, played with its own
   dance and with a dance made from a different song or section. Which belongs?
   **Pass**: at least 10 of 12.
3. **Whole-song dial.** While watching a full song, the user moves a slider for
   "feels right" and taps where something lands or misses. Recorded against the
   clock, so nothing depends on memory. Not pass/fail on its own: it locates
   problems, and it also records the user's own feeling for the song, which
   checks whether the public-data encoder agrees with them.

The tests are web pages that save the answers to a file; the key of each test
is hidden until the answers are in.

## Where things live

- Python analysis and dataset work: `scripts/emotion/`, tests beside it.
- Environment: `/secondary/hyst-env/emotion` (uv). Model caches under
  `/secondary/hyst-env/hf`. Datasets: `/secondary/hyst-data/emotion/`. The root
  disk is nearly full; nothing goes there.
- Body and decoder: Rust, in the dance crate (`hyst-compile`, to be renamed
  `afekt-compile`).
- Each stage appends a dated entry to `docs/DANCE_HANDOFF.md` with its check's
  numbers.

## Licences

Several datasets are licensed for research only. That is fine for building and
checking. Before the piece is exhibited or sold, each dataset and model licence
is checked, and anything that does not allow it is replaced or dropped.

## Out of scope until stage 4 passes

The ensemble, the braking work, melody-following, B's outlets, live audio,
СИНТЕЗА reading the encoding.
