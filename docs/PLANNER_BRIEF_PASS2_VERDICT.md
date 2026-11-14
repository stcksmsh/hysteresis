# Planner brief — user verdict on K5-pass2: one shape repeated (2026-11-08)

Follows `docs/PLANNER_BRIEF_PASS2_RESULTS.md` and your rulings (BRAIN_SPEC 7.33). ONE arm. ARGMAX for every claim.

## The verdict (user, verbatim; recorded as 7.33.7)

> "The third video isn't good, it's the same exact shape of movement, just repeated at different speeds/accelerations/etc, it's not
> conveying anything to me."

The user watched the three-panel videos (v47 one arm | fallback | pass2), full songs. Instant Crush and Five Years were sent; Presence was
rendering.

## Measurement (overseer, from the song joint CSVs at 50 Hz; bending joints shoulder / elbow / wrist bend)

| Song | Policy | Distinct 5-deg postures | sd shoulder / elbow / wrist (deg) | Range (deg) | PC1 share |
|---|---|---|---|---|---|
| Instant Crush | pass2 | **214** | 3.0 / 14.4 / 10.4 | 41 / 132 / 86 | 0.78 |
| | v47 one arm | 2,321 | 16.7 / 19.5 / 26.9 | 86 / 96 / 161 | 0.57 |
| | K5 try 1 | 3,682 | 36.7 / 29.7 / 31.5 | 183 / 158 / 156 | 0.48 |
| Five Years | pass2 | **239** | 3.3 / 15.2 / 10.7 | 45 / 133 / 86 | 0.79 |
| | v47 one arm | 1,734 | 14.1 / 21.1 / 25.7 | 90 / 99 / 143 | 0.55 |
| | K5 try 1 | 2,968 | 31.9 / 27.9 / 38.6 | 154 / 121 / 163 | 0.57 |
| Presence | pass2 | **237** | 3.3 / 15.2 / 10.3 | 44 / 132 / 86 | 0.79 |
| | v47 one arm | 2,094 | 14.0 / 20.7 / 32.9 | 66 / 95 / 214 | 0.67 |
| | K5 try 1 | 2,320 | 26.7 / 36.5 / 33.7 | 170 / 184 / 148 | 0.56 |

What the numbers say:

- Pass2 visits 7-10x fewer postures than v47 one arm.
- The shoulder barely moves: sd 3 deg, against 14-17 deg for v47.
- The bend statistics are the same across the three songs to about 1 deg. The shape is song-independent; only timing and speed vary.

This is consistent with the earlier findings:

- a single basal-ganglia program 100 % of the time ((c) MI 0);
- peak hand speed 0.741 m/s, identical in all songs;
- hand acceleration p99 about 2.1 m/s² vs v47 4.1-6.0.

The readability bar (a) (ext 0.943) is met by timing and speed modulation of one fixed shape. The bar has no measure of shape variety
or of song-dependence of the shape, so it could not catch this.

Not checked: which pass2 ingredient narrows the shape (the smooth-u map with c = 0.5 and amplitude cap, the hand-acc / floor /
limit-proximity hinges, jerk and switch weights, or the collapse to one program).

## Questions

**Q1. Diagnose before any new training?**
Options:
- (a) Report-only diagnosis on the M3f toy (about 2-4 h, no new long run). Measure distinct postures, shoulder sd and program count for
  the WO17 seed-0/1 policies and the two saved pass2 policies (round 600 best.pkl and round 977 ckpt; no others were kept). Then run
  single-ingredient toy ablations (one
  epoch budget each): smooth-u off (clip back), amplitude cap raised, hand-acc hinge off, limit-proximity off, switch weight 0.
  Name the ingredient(s) that shrink the posture set.
- (b) Go straight to a round-3 run with a variety term.

Recommend (a). WO17's clips had the same "2 programs, top share 84-98 %" signature before pass2, so the cause may already be visible on
the toy.

**Q2. Add variety to the bar, pre-registered before any new run?**
Proposed gate per danced song:
- (i) distinct 5-deg postures of the bending joints >= 50 % of v47 one arm's;
- (ii) shoulder sd >= 8 deg;
- (iii) song-dependence: the bending-joint posture distributions of two different songs differ more than the two halves of one song do
  (e.g. Jensen-Shannon distance between songs > within-song).

Options:
- (a) adopt (i)-(iii);
- (b) adopt (i)+(ii) only;
- (c) no numeric gate, the user's eye only.

Recommend (a). The user's verdict is about shape conveying the music, and (iii) is the only one of the three measures that tests that.
Thresholds to be confirmed on the toy diagnosis before any run.

**Q3. Program diversity.**
7.33.3 allows a diversity term if the verdict asks for variety. It does. Options:
- (a) an entropy bonus on the basal-ganglia program choice;
- (b) a gate: (c) MI > 0 and top-program share <= 60 %;
- (c) both;
- (d) defer until Q1 shows whether one program is the cause.

Recommend (d), then (c) if the diagnosis points at the program collapse.

**Q4. Status of pass2.**
Options:
- (a) keep pass2 recorded as passing the numeric bar (7.33.1), with no public wording, and mark it "rejected by the user's eye";
- (b) withdraw the numeric pass.

Recommend (a): the numbers are correct; the bar was incomplete.

**Q5. Fallback for the demo.**
Until a learned policy passes the user's eye, the installation demo uses:
- (a) the fallback (authored mapping on the brain lanes, middle panel), or
- (b) v47 one arm.

The user's choice; no recommendation from the overseer.

## Paths

- Song CSVs: `/secondary/hyst-data/body/k5p2/check/songs/<song>.pass2.csv`. References: `/secondary/hyst-data/body/hf/v47/<song>-arm0.csv`
  and `/secondary/hyst-data/body/k5/danced/<song>.k5.csv`.
- Videos: `/secondary/hyst-data/body/k5p2/video/<song>-three-panel-720p.mp4`.
- Pass2 checkpoints: `/secondary/hyst-data/body/k5p2/run/` (best.pkl = round 600, ckpt = round 977).
