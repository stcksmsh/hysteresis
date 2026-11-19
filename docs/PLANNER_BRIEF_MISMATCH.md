# Planner brief: mismatch test result (BRAIN_SPEC 7.84 item 1), 2026-11-19

TO: planner. FROM: overseer (via Kosta). Material `docs/MISMATCH_RULES.md`, scorer `scripts/body/mismatch_score.py` (merged in `body`).
Session `/secondary/hyst-data/body/mismatch/session_2026-11-19` (20 pairs + 5 repeats, 10 shifted + 10 different-song pairs, 21.5 s clips,
one viewer: Kosta, 2026-11-19 12:18-12:50, answered all 25 in one pass). Overseer recomputed every number below from `answers.csv`
and the keys, and checked the keys independently from the clips' audio.

## Result against the rule stated in advance

Rule (7.84 item 1): real-pick share >= 0.70 AND its lower 95 % bound above 0.5 + flip rate / 2. **Rule NOT met** (both parts).

| group | real picks | foil picks | ties | real-pick share (non-tie) | 95 % CI |
|---|---|---|---|---|---|
| all 20 pairs | 5 | 13 | 2 | 0.278 | 0.097-0.535 |
| shifted (10) | 0 | 8 | 2 | 0.000 | 0.000-0.369 |
| different song (10) | 5 | 5 | 0 | 0.500 | 0.187-0.813 |

- Repeat-flip rate 3/5 = 0.60. Two of the three flips are the two repeats of pairs P19 and P17, which Kosta answered "same" at items 2
  and 3 while still believing the shifted pairs were a bug (he did not yet understand that a shifted pair is the same song 2-6 s apart).
  Without them: 1 flip in 3 repeats.
- **Sensitivity to those first items (Kosta's own caveat, items 1-4):** dropping them changes nothing in the outcome: all 5/11 real picks
  (0.31 on 16 non-tie), shifted 0/7, different song 5/9.
- Confidence split: low 1/2, medium 1/9, high 3/7 real (n tiny).

## What stands out (observations, not a ruling)

- **Shifted pairs: Kosta picked the foil in 8 of 8 non-tie answers** (two-sided binomial p = 0.008; 0/7 without items 1-4, p = 0.016; no
  multiple-comparison correction, n small). His notes: both halves "seem the same" in the first items; three consecutive shifted
  PhantomDance pairs looked identical to him.
- The key is correct: in all 13 shifted clips the second half is the first half's music exactly at the stated shift (linear correlation
  1.00 at the stated lag, about 0 at the opposite sign), so "real" and "foil" are not swapped.
- Foil offsets that were picked: 6 positive (foil music later than the movement's own), 2 negative. Too few to say if the direction matters.
- Different-song pairs: 5/5, chance level. The real-pick share does not distinguish the songs.
- Test-retest: 0.60 with the confused items, about 0.33 without (earlier viewing sessions: 10 of 35 speed answers flipped, 0.29).

## Possible reading (not verified)

A consistent preference for the shifted foil, with no preference on different songs, would be expected if the retargeted movement sits a
constant lag away from the music's own timing (so a shifted copy of the music can line up better), or if the music in the clips is
loop-based and a 2-6 s shift hides the difference. The numbers cannot separate these. WO52's lag question was parked as report-only.

## Questions

**Q1. Reading of the outcome.**
- (a) Record the rule outcome as stated: not met, so per 7.84 item 1 the fit is treated as teacher- and planner-shaped and data-learned
  timing is deprioritised; AND record the shifted-pair foil preference as an unexplained finding that blocks reading "no fit" as "no
  signal". **[recommended]**
- (b) Treat the test as inconclusive (one viewer, first items confused, 20 pairs) and rerun it before ruling.
- (c) Apply the rule outcome only.

**Q2. Report-only lag diagnostic (cheap, existing data, no viewing).** Measure the lag between the realised movement (lamp speed, and the
raw joints of WO53 part B) and the music's onset/energy envelope: cross-correlation per song, lag distribution per dataset, bootstrap by
song, against shifted-song chance. If a stable lag of about 0.2-1 s exists, it explains the foil preference. **[recommended]**
- (a) Yes, report-only before the combined ruling. (b) No.

**Q3. Round 2 of the viewing (only if Q1 is (b), or after Q2).** Two rounds at most per check; this is round 1. If a round 2 runs:
- the instruction page explains shifted pairs (same song, moved in time) before item 1;
- shifted offsets of 4-6 s only, and a different-song foil from a different dataset when tempo allows;
- the same 20 pairs with fresh excerpts, 5 repeats, no item skipped.
Order of events: Q2 first, then the decision on round 2. **[recommended]**
