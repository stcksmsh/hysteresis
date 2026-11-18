# Planner brief: overseer questions and pushbacks (2026-11-18)

These are not results. The overseer raises them for the planner. Numbers come from merged reports. One arm.

## 1. Is the human data musical enough to learn timing from? (pushback on 7.81, before A3)

7.81 makes timing learned from human motion. The measurements so far:
- beat-phase locking at chance in FineDance, and small in AIST++ (+0.016 to +0.067);
- movement rhythm not clustered at 1/2, 1, 2 beyond the tempo class;
- event responses weak (ratios 1.4-1.8 on rare holds).

If the data carry little timing, A3 and B learn little timing, and the result may look unmusical to Kosta. Nothing so far tests whether
Kosta can see the musical fit in the human data at all.

**Proposal (cheap, before A3):** a **mismatch test**.
- Human clips retargeted to the arm, each shown with its own music and with the same music shifted by a random 2-6 s, or a different song of
  similar tempo.
- Paired, blind: "which fits the music better?"
- About 20 pairs plus 4 repeats.

If Kosta picks the real pairing well above chance, the data carry visible timing, and learning it is sound. If not, the timing should come
from the teacher or the planner, not the data, and A3's timing controls matter less.

**Recommendation:** run it before A3. It is a standard check in dance-generation research ("does the dance match its own music better than
other music"). It needs only existing retarget and render tools.

## 2. Make viewings robust to rater noise (pushback on viewing design, including WO50)

- Kosta's "right speed" answers changed on 10 of 35 items with identical tempo between sessions (`docs/PULSE2_VIEW_RESULT.md`). The pulse v2
  decision turned on a 3-item margin.
- WO50 (factorial T × P × E) uses absolute 1-5 ratings: 48 items, 4 repeats.

**Proposal:**
- Use paired forced choice (same excerpt, two versions, "which fits better?") wherever versions are compared. It is more reliable than
  absolute ratings.
- Put at least 20 % repeats in every session, and state a minimum effect size in advance (larger than the measured test-retest flip rate).
- For WO50: the main effects T, P and E as 3 paired comparisons per excerpt (factor on vs off, the others at a fixed level), 6 excerpts × 3 ×
  2 orders = 36 pairs + 8 repeats, in place of 48 absolute ratings.

**Recommendation:** adopt it; WO50 is not sent yet, so changing it now costs nothing.

## 3. Measure rhythm on raw human joints too (question on WO52)

WO52 measured the movement period on lamp speed after retargeting to the arm: median 1.24 s, 2.2-2.7 beats. Retargeting and the arm's limits
may smooth out faster movement.

**Proposal:** a report-only rerun of WO52's rhythm part on the raw human joints (wrists, feet, pelvis) before retargeting. If the raw data
show beat-level periods that the arm loses, the arm's limits rather than the dancers explain "no clustering".

**Recommendation:** run it with the mismatch test; it is a small subagent job.

## 4. Consolidate open briefs

Three briefs are open (A2, CORTEX_EVENTS, RHYTHM_EVENTS); the TEMPO_SOURCE brief was answered by 7.81. Several questions overlap:
- A2 Q1 pause/stillness overlaps RHYTHM_EVENTS Q2 (hold as a control);
- CORTEX_EVENTS Q1 (event source) overlaps 7.81 (all trackers become senses).

**Proposal:** one combined answer, "A3 controls and B senses", ruling these together.
