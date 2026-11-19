# Planner brief: AIOZ prune and weight cap (BRAIN_SPEC 7.59.2.4, 7.59.2.6), 2026-11-14

TO: planner. FROM: overseer, for Kosta. T0 is running on FineDance. Two rules in 7.59 do not work as worded on AIOZ. The errors are the
overseer's (the prune thresholds were the overseer's default in 7.56.10). Numbers recomputed by the overseer from
`/secondary/hyst-data/body/t0/aioz_measures.json`.

## 1. Prune rule (7.59.2.4)

- AIOZ: 1,624 clips, 6,011 dancers, 60.77 dancer-hours, all at 30 fps.
- **As worded:** 168 dancers kept (2.8 %, 1.52 h) -> the 30 % stop rule drops AIOZ.
- **Why it is wrong:** rule (2), "> 1 % of frames where ANY joint's speed is above FineDance's p99.9 for that joint", takes a union over
  20 joints. The median FineDance dancer is already at 1.36 %. Applied to FineDance itself, the rule drops 58 % of it.
- **Calibrated variant** (written before any AIOZ number was computed): thresholds of (2) and (3) = max(1 %, FineDance's p95 of the same
  share), i.e. 5.78 % for joint speed, 1 % for root jumps (FineDance p95 0.43 %). Same logic as rule (1), which already uses FineDance's
  p95. Rules (1) and (4) unchanged. **Kept: 1,852 dancers (30.8 %, 19.28 h).** Just above the 30 % stop.
- Two dead joints (feet, never move in FineDance) excluded from (2).

## 2. Weight cap (7.59.2.6)

- Worded: cap each song's / **YouTube id's** total weight at its single longest dancer.
- An AIOZ YouTube id holds several clips from different moments of the video, not only dancers dancing at the same time. Per id, the
  calibrated AIOZ keeps **2.72 h** effective (231 ids). Capping per **clip** (only dancers on screen together share weight): **8.36 h**
  (804 clips).
- FineDance: one sequence = one whole song, so no change (its 22 songs danced twice are still capped per song).
- The split stays by YouTube id either way (no song in two splits).

## Context

FineDance public part: 7.66 h, 203 sequences. Each dancer gives 4 training copies (V1, V2, mirrored); the hours above are human-motion
hours before copies and before the 1.25 gates.

## Questions

1. Prune: (a) calibrated variant **[recommended]** / (b) as worded (AIOZ dropped) / (c) other.
2. Weight cap: (a) per clip **[recommended: matches the stated purpose "so multi-dancer group songs do not dominate"]** / (b) per
   YouTube id as worded.
3. Record as 7.60.
