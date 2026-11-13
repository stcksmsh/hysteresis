# Planner brief: retarget look test on v2p: the speed/acceleration gate leaves only slow dance (BRAIN_SPEC 7.51), 2026-11-13

TO: planner. FROM: overseer. The clips are rendered, but the overseer HELD Kosta's session: the 10 passing clips would mostly show one slow
opera sequence. Nothing has been shown to Kosta.

## What ran

- **v2p, as 7.51:**
  - square column 0.14 m, top at the old table plane, floor 1.0 m below;
  - clearance 0.05 m from the column and floor;
  - backstop guard (hold the last safe command; a clip with more than 10 % of frames held fails);
  - V1/V2 mapping, the 80 % share and the scale unchanged;
  - the seeded stream restarted from candidate 1.
- **Gating (145 candidates, both variants):** 10 passed in both at candidate 145 (V1 13, V2 43). Contact with the column 2; guard engagement
  median 0 %. Clips rendered (body-retarget d0644f0).
- **Report-only breakdown afterwards** (`/secondary/hyst-data/body/retarget_look/limits_breakdown.json`, agent 1): the same 145 candidates
  re-simulated; nothing adopted. The overseer recomputed the genre spread from it and from the gating log.

## Results

**The 10 clips that passed:**
- 7 are windows of the same Kunqu opera sequence (FineDance seq 028, the only "kun" sequence). Three of them nearly overlap: windows start at
  40.5, 41.2 and 43.3 s.
- One each from Hantang, Dai and Shenyun.
- 12 of 16 genres, every street style included (hip-hop, popping, locking, breaking, urban, Korean, jazz), passed 0 of 9 windows.

**Why they fail:**
- Discards: V1 "limits" 132, end stop 19; V2 "limits" 100, end stop 32, contact 2, clearance 2, guard 1.
- The limits failures are almost all **shoulder acceleration** (V1 132, V2 97). The other joints stay at or under about 1.0 of their limits.
- Median realised shoulder acceleration / limit: V1 1.24, V2 1.14. Servo overshoot over the limiter output on the shoulder: median +0.23 (V1),
  +0.05 (V2).
- The human command asks far more: median commanded shoulder acceleration 22x (V1) and 9x (V2) the limit. The limiter brings it down to the
  limit.
- **Not yet explained:** in 6 % (V1) and 19 % (V2) of candidates, the limiter's own shoulder output exceeds the acceleration limit, up to 5.5x.
  The cause is not checked.

**How many would pass at a looser speed/acceleration tolerance** (all other gates unchanged; counts only, nothing adopted):

| Tolerance (realised / limit) | Pass in both variants | Genres | Sequences |
|---|---|---|---|
| 1.05 (current) | 10 | 4 | 4 |
| 1.25 | 43 | 15 | 30 |
| 1.5 | 93 | 16 | 63 |

## Questions

1. **What to do about the speed/acceleration gate for this look test** (simulation only; no hardware is driven).
   - (a) **Raise the speed and acceleration tolerance to 1.25** for this look test only, record it, and re-pick from the same stream.
     **[recommended]** At 1.25, 15 genres and 30 sequences pass, so 10 different sequences across genres are reachable. The look test asks
     whether human dance looks like dancing on this arm; hardware limits come later. The simulated shoulder then runs up to 25 % over the
     servo's rated acceleration.
   - (b) Keep the gate at 1.05 and give the command limiter headroom on the shoulder (e.g. accelerate the command to at most 0.8 of the limit),
     then re-gate. This keeps the hardware margin but smooths the shoulder further; the yield is unknown until it is re-run.
   - (c) Show the current 10 as they are. Not recommended: 7 clips of one opera sequence cannot answer the question.
2. **Pick rule:** at most one window per sequence and at most two per genre, in the same seeded stream order. **Recommended**, so the 10 clips
   cover different dances.
3. **Unexplained limiter overshoot:** agent 1 reports the cause, report-only, before the next render. **Recommended.**
4. **Record** as BRAIN_SPEC 7.52.
