# Planner brief: movement rhythm vs beat, and event responses, in human data (7.81 item 4) (2026-11-18)

Rules `docs/RHYTHM_EVENTS_RULES.md`, pushed before results. Report `docs/RHYTHM_EVENTS_REPORT.md`, tables `docs/RHYTHM_EVENTS_TABLES.md`.
Merged into `body` (f7dc5cf), 8 tests pass. The overseer recomputed the pooled and per-dataset bin shares against shuffled chance from
`rhythm/windows_*.npz`; they match. One arm.

## What ran

- **Data:** human motion retargeted to the arm. 1,215 songs (682 song groups), 4 datasets, mirrors excluded; 310,065 windows of 3 s and 4 s.
- **Rhythm:** the dominant period of lamp speed (autocorrelation within 0.2-2.5 s), divided by the beat period from librosa or from pulse v2.
  - Bins: 1/2, 1, 2, other, none (strength < 0.2).
  - Chance 1: a similar-tempo song's beat (±10 %). Chance 2: beats shuffled within the dataset.
  - Bootstrap by song group.
- **Event responses:**
  - per token: hold (pause onset), change (gesture-family or posture change), burst (vigour jump);
  - locked to onsets, dropouts, novelty boundaries and cortex surprise at lags ±1 s;
  - against circular shifts.

## Results

- **Movement periods are long.** Median 1.24 s (q10 0.46, q90 2.12). The median ratio is 2.2-2.7 librosa beats and 1.9-2.4 pulse v2 beats.
  Of the rhythmic windows, 55-66 % fall outside the 1/2, 1, 2 bins, mostly above 2.5.
- **Clustering at 1/2, 1, 2:**

  | beat source | share | vs similar-tempo chance | vs shuffled |
  |---|---|---|---|
  | librosa | 0.398 | +0.001 [-0.001, +0.003] | +0.018 [+0.010, +0.027] |
  | pulse v2 | 0.435 | +0.000 [-0.003, +0.004] | +0.015 [+0.008, +0.022] |

  - The shuffled excess comes mainly from AIOZ: +0.026 librosa, +0.023 pulse v2. The other datasets give -0.001 to +0.014.
  - A narrow variant (tighter bins, strength ≥ 0.3) gives +0.017 vs similar tempo and +0.072 vs shuffled (librosa), mostly AIOZ.
- **Overseer recompute, full histogram against shuffled.** There is a weak but regular pattern:
  - density ratio 1.11-1.16 near r = 1/2, 1, 2 (also 1.06 at 4);
  - 0.81-0.94 near the in-between ratios 0.7, 1.4, 2.8.

  Movement tends slightly to whole multiples of the beat, but only by 10-15 %, and not beyond what the tempo class explains (similar-tempo
  chance excess ≈ 0).
- **Item 4's rule:** against the similar-tempo chance, the cluster excess is +0.001 / +0.000, which points to **clusters absent** beyond the
  tempo class, so the rule says the teacher shapes rhythm.
- **Event responses** (pooled, peak excess per second, with lag):
  - hold × novelty: +0.028/s at −0.65 s, ratio 1.78, p 0.005;
  - hold × cortex L2: +0.015 at −0.25 s, ratio 1.42, p 0.01; the only one with a ±0.3 s mean above 0 (+0.006 [+0.003, +0.010]);
  - burst × dropout end: +0.051 at −0.45 s, ratio 1.38, p 0.005;
  - change × cortex total: ratio 1.09;
  - **Peaks sit at negative lags,** partly because the detectors stamp an event late (a causal boundary; a dropout end stamped at the first
    frame of recovery).
- **Limits:**
  - "change" fires at nearly every token (1.95/s of a possible 2/s), so it is almost the token grid itself.
  - The posture threshold is dominated by AIOZ.
  - Events are counted per copy (V1/V2/AIOZ performers).

## Questions

1. **Rhythm control for A3.** Options:
   - (a) follow the rule: rhythm is shaped by the teacher, with no learned rhythm-ratio target in B;
   - (b) still add rhythm as an A control (the ratio as a continuous log2 value plus strength, not bins), so the teacher has a knob to set,
     with B not predicting it;
   - (c) drop rhythm as a control.

   **Recommendation: (b).** The teacher needs a knob to shape anything. The human data say the ratio is free (mostly 2-4 beats, weakly
   attracted to whole multiples), so a continuous control fits better than the bins.
2. **Event-response controls.** Options:
   - (a) keep hold and burst as A controls; redefine "change" sparsely (for example, posture change above the per-dataset p90, or family
     change across ≥ 2 tokens);
   - (b) keep all three as defined.

   **Recommendation: (a).** Hold and burst show the clearest relations to music (hold × novelty ratio 1.78; burst × dropout end 1.38).
3. **Event timing.** Should a causal-lag-corrected event time be used before the B-input stage (shift each detector by its measured mean lag)?
   **Recommendation: report only for now.** B learns lags from inputs anyway.
