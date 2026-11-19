# Planner brief — hand-set dial study results (2026-11-12)

Overseer handover for the planning agent. Rules of record: `docs/BRAIN_SPEC.md` §7.42-7.43 on branch `body`.
- Full table: `docs/DIALSTUDY_REPORT.md`.
- Dial implementation: `docs/DIALSTUDY_DIALS.md`.
- Gates: `docs/DIALSTUDY_RULES.md`.

No verdict here from the overseer: Kosta decides what this means (7.43.4).

## 1. What ran

- **Work orders:** WO28A (agent 1, branch body-dial, merged into body edf3c35) and WO28B (agent 2, body-dialtool, merged into body ef0081c).
- **Simulation:** plain MuJoCo on CPU, v2f body, 6 threads on cores 6-11.
- **Movement:** one seeded random pose sequence (seed 28011, 12 poses), one move per two beats at 100 BPM, the same in every clip. No v47
  input.
- **Clips:** 22 silent clips of 12 s each:
  - A: 10 single-dial extremes + 1 all-neutral;
  - B: 5 presets with the ball;
  - C: heavy, angry and light with the lamp and with the gripper.
- **Set D was not run:** no audio in `/secondary/hyst-data/audio/checkset/`.
- **Overseer checks before Kosta saw anything:** gates recomputed by the overseer's own code from each clip's 50 Hz CSV. All 22 pass:
  - lowest link point 0.070 m above the floor, lowest hand point 0.144 m (gates 0.05 / 0.11);
  - end-stop dwell 0;
  - joint-velocity power above 8 Hz: 0.0000;
  - maximum speed <= 0.99 of the limits, maximum acceleration <= 0.99.

  Frames were looked at: same framing and a neutral on-screen label.
- **Blind session (2026-11-12 22:26-23:2x):** coded names, seeded random order, key not served. 22 answers, one each.
  Overseer joined `answers.csv` with the key independently; it matches the report on all 22.

## 2. Results (Kosta's labels)

**Single dials** (all-neutral clip = "calm"):

| dial | low | high |
|---|---|---|
| vigour | calm | tense |
| stiffness | light | light |
| roundness | light | calm |
| lag | tense | tense |
| posture | calm | light |

**Presets:**

| preset | ball | lamp | gripper |
|---|---|---|---|
| heavy | calm | calm | calm |
| angry | light | **angry** | something, can't name it |
| tense | light | — | — |
| calm | heavy | — | — |
| light | **light** | **light** | **light** |

Counts, for the planner's suggested reading in 7.43.4 (stated as facts, not a reading):
- Presets with the ball read as intended: 1 of 5 (light).
- Over all effectors: light 3/3, angry 1/3 (lamp), heavy 0/3.
- Single dials whose extreme changed the label from the neutral clip's "calm": vigour (high), stiffness (both), roundness (low), lag (both),
  posture (high): 5 of 5 dials at one end or more. Only three labels appear across all of Set A: calm, tense, light.

**Recurring words in Kosta's notes** (counted by the overseer):
- "sad": 6 notes (all-neutral, roundness high, stiffness low, vigour high, calm preset, heavy preset). "sad" was not a button.
- "choppy" / "move stop": 4 notes (angry ball, tense ball, angry lamp, angry gripper), e.g. "Again the choppy one isnt really emotional in
  the traditional sense"; "it could work with something like techno/energetic stuff".
- "idk" / "unsure" / "can't say": 10 notes.
- The light/lamp clip: "Def happier than most of the ones so far".
- Several notes describe a change within a clip ("near the end it seems to start mooving more"; "slow, then a bit faster, then slow
  again"). The random pose sequence has larger and smaller moves in it; every clip shares that structure.

## 3. Facts about how the dials were made that may bear on the labels (builder's notes, overseer-read)

1. **Roundness:** the two ends differ more in stopping vs flowing than in path curvature. Hand-path chord/arc per move is 0.949 angular vs
   0.877 round; 1.0 = straight.
2. **Stiffness:** high stiffness is near-critical (zeta 1.0, kp 2.5x). The loose end has zeta 0.3 and a 9 deg shoulder droop at neutral
   posture. The light preset forces zeta 0.2 ("bouncy").
3. **"Angry" and "tense" share** high stiffness, the angular end (stops at every pose) and short move shares. Kosta's notes call both
   "choppy".
4. **STS3215 (unverified, builder):** the stiffness range is plausible in P gain. A real geared servo is probably better damped than the
   loose end, because the model has no friction or backlash.
5. **One viewer, one pass, no repeats.** Order effects and consistency are unmeasured.

## 4. Questions

**Q1. The label set.** "sad" was volunteered in 6 of 22 notes but was not a button.
- (a) Add "sad" to the buttons in any repeat or later session. The feelings list itself stays as ruled.
- (b) Keep the five labels; Kosta's notes carry the rest.
- (c) Kosta's own list.

Recommendation: (a). It costs nothing, and it is Kosta's own word.

**Q2. Consistency check.** Is a reshuffled re-run of the same 22 clips wanted (about 15 min, new seed, Kosta only, with "sad" if Q1 a)?
It measures how stable one viewer's labels are before any conclusion is drawn from 22 single answers. Recommendation: yes, if Kosta
agrees; no new clips are needed.

**Q3. What the result means and the next step: Kosta's decision.** Options, none recommended by the overseer:
- (a) the base is viable as is: move to the 7.43.3 direction steps;
- (b) a second dial round that changes only what the notes name, e.g. the "choppy" stop pattern of angry/tense, or a pose sequence with
  phrase structure instead of independent random poses (needs a ruling: the sequence is part of the study design);
- (c) stop.

**Q4. End effector.** The only "angry" came with the lamp, and light read as light on all three. One answer per cell. Record it only, or
include the lamp in any second round? Recommendation: record it only, until Q2 shows how stable the labels are.

## 5. State

- Nothing is running. The session server `hyst-wo28-session` is stopped.
- Both builders are idle.
- Data: `/secondary/hyst-data/body/dialstudy/` (clips, manifest, session_2026-11-12 with key and answers).
- Branches: body b4efa26+ (report), keys-decide merged.
