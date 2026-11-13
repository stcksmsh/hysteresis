# Planner brief: motor-network toy test Part 3 (music pairs), Kosta's blind picks (2026-11-13)

From the overseer, for the planning agent. Paste-ready. One arm only. Rules: BRAIN_SPEC 7.44-7.46. Report: `docs/MOTORNET_REPORT.md` on
body; the report script printed Part 3 twice, a fix is pending with builder 2, and this brief does not depend on it.

## What ran

- **Network and body:** unchanged from Parts 1, 2 and 4.
- **Input:** each song's cortex lanes (B7 epoch 6, frozen): beat-band phase and arousal.
- **Excerpts:** 12 s at Kosta's start times, with the song's preceding 10 s as warm-up.
- **Settings:** two per song, drawn with seed 29031 from the shown S01-S10.
- **Gate failures with music:** 3 of the 10 first renders failed the gates, although the same settings had passed silent:

  | Song | Setting | Contact substeps | Acceleration |
  |---|---|---|---|
  | Blue Lagoon | S04 | 13 | 1.18x limit |
  | Epitaph | S02 | 339 | 7.32x |
  | One of These Days | S06 | 180 | 1.96x |

  They were replaced by the next draws per 7.44.3.4 (overseer note 7.46.7): S06, S03, S08. The overseer reproduced the draws.
- **Overseer checks:** all 10 renders pass the gates (recomputed); each audio window starts at the excerpt time (offset 0.0 s); frames
  looked at.
- **Session:** 5 pairs, blind, in seeded order (29061). Kosta answered all 5 and wrote a note on each.

## Results

Hand speed was recomputed by the overseer from the CSVs. Arousal is the builder's number: the mean `arousal_b7` over the 12 s, standardised
as the network input.

| Song (start) | Pair (first / second) | Mean hand speed m/s | Base yaw range deg | Cortex arousal (std) | Pick |
|---|---|---|---|---|---|
| Blue Lagoon (0:20) | S03 / S06 | 0.365 / 0.473 | 27 / 58 | -0.23 | first (S03) |
| Breathe (1:17) | S05 / S03 | 0.797 / 0.281 | 52 / 29 | +0.43 | second (S03) |
| Epitaph (5:45) | S08 / S03 | 0.184 / 0.273 | 19 / 22 | -0.59 | second (S03) |
| One of These Days (3:57) | S01 / S08 | 0.163 / 0.063 | 15 / 14 | **-1.40** | neither |
| 21st Century Schizoid Man (0:58) | S01 / S07 | 0.297 / 0.292 | 45 / 39 | +0.66 | neither |

Base yaw range is p5-p95.

Kosta's notes, condensed (full text in the report):
- Blue Lagoon: first is more "on the music", less janky, mostly on beat. Both are "too simple/repetitive loops facing the same direction
  always". The guitar melody is more than loops.
- Breathe: the first "swings wildly"; the second is better but still "too loopy/swingy/fast".
- Epitaph: the second is better but "too stationary ... almost no if any rotation of the base, little movement in the shoulder".
- One of These Days: neither. Both "too small/boring", "they don't match the music's energy at all, it's not a ballad so they shouldn't be
  this droopy/sad".
- Schizoid Man: neither. "Not energetic enough on the drop ... an angrier/more energetic song ... little to no shoulder/base movement, too
  small".

Facts:
- **Picks:** S03 was picked in all 3 pairs it was in (Blue Lagoon, Breathe, Epitaph). The two "neither" songs are the two Kosta describes
  as energetic or angry.
- **Cortex arousal disagrees with Kosta's hearing.** One of These Days has the lowest cortex arousal of the five (-1.40), while Kosta hears it
  as energetic. Breathe (+0.43) is above Epitaph (-0.59).
- **Arousal input and movement on One of These Days:** the excerpt moved S01 at 0.163 m/s, against 0.526 silent, and S08 at 0.063 m/s,
  against 0.247 silent. Low arousal input went with much smaller movement here.
- **Repeated themes in the notes:** repetitive loops; a fixed facing direction; little base and shoulder movement; too small on energetic
  music.
- **Activity:** still one cycle, PR 2.2-3.0 in these renders, matching the PR-about-2 risk recorded in 7.46.2.

## Questions

**Q1. Next step** (7.46.3: decided after Part 3). Options:
- (a) Close the toy test. The next design question is the one 7.46.2 named: richer motor-network dynamics (not one low-dimensional cycle),
  with more use of base and shoulder. The planner specifies which change to test in a second toy round (e.g. more control units, a higher
  spectral radius, slower or multiple input timescales, a readout weighted towards base and shoulder), blind-judged as before.
- (b) Go to the proposal of 7.44.2: limbic gains trained by Kosta's labels.
- (c) A second silent round with a new seed, network unchanged.

*Recommendation: (a).* Kosta's notes name the limits of this network (loops, fixed direction, small proximal motion) more than the choice
of gain setting. (b) would train gains over a repertoire Kosta judged too small for energetic music. (c) adds labels without addressing the
notes.

**Q2. Cortex arousal against Kosta's hearing.** Options:
- (a) Report only. Compare `arousal_b7` with Kosta's whole-song dial recordings where they exist (`scripts/emotion/dial.html` sessions, 3
  songs), and with these 5 excerpts. No change to the cortex (frozen).
- (b) Nothing now.

*Recommendation: (a).* It is cheap, and a later limbic part depends on whether this signal tracks what Kosta hears.

**Q3. Record** these results and answers as BRAIN_SPEC 7.47. *Recommendation: yes.*

## State

- **Merged:** body-mnet3 and body-mnettool3 into body (e5f3ac9).
- **Running:** nothing. The session is stopped.
- **Builders:** builder 2 is fixing the report's duplicate Part 3 table and adding the list of settings that failed with music. Builder 1 is
  idle.
- **Data:** `/secondary/hyst-data/body/motornet_toy/` (clips, `session_2026-11-13_part3`, `part3_numbers.json`). Audio stays outside git.
