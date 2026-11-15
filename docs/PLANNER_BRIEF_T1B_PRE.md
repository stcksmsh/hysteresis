# Planner brief: open points in 7.63-7.67 before the E1 baseline trains (2026-11-15)

TO: planner. FROM: overseer, via Kosta. Recorded so far on branch `body`: BRAIN_SPEC 7.63 (with the categorical-heads amendment), 7.64,
7.65, 7.66, 7.67, verbatim, plus overseer notes. Work order WO41 (E1 baseline, then T2) is written and not yet sent. Nothing has run.

## Facts

- **T1b was not running when 7.66 arrived.** 7.66.1 says "do not stop the running T1b". The overseer recorded E1 as T1b exactly as
  specified in 7.63-7.65 (listener split rhythm 192 / affect 64) plus the 7.66.3 T2 additions.
- **The cortex input is not causal today.** B7 (epoch 6) was trained, and T0 lanes were built, with beat phase from the offline
  whole-song beat grid (as in all earlier rounds). T0 also recorded per-column lookahead: ear features 0.023 s, ear energy 1.0 s.
- **The project plays from offline sidecars only** (Kosta, 2026-10-04: "dance works from offline sidecars only, no live audio").
- **FineDance split** (T0, seed 33001, by song): train 133 song groups, validation 20, test 19 (154 / 26 / 23 sequences).
- **7.56.11 (Kosta):** V1 and V2 pooled with no variant label ("a dance is freedom"); 7.63.8 repeats it ("must not learn one right
  answer").

## Questions

**Q1. Causality: required, and which kind?** 7.67.3 asks to fix every non-causal feature. The cortex's beat input comes from a whole-song
grid, and the cortex is frozen, so a strict fix means retraining B7. Playback is offline, so lookahead is available at run time.
- (a) Causal only in the token sense: the planner sees music only up to decision time; inputs may contain offline whole-song facts (beat
  grid, 1.0 s ear energy) as long as they are listed. No cortex retrain. **[recommended]** E1 can start now, and the lookahead is
  disclosed.
- (b) Strictly causal: fix ear features and ear energy; replace the beat grid with a causal tracker, which means retraining the cortex
  (days, and it reopens B7's checks).
- (c) Deliberate lookahead: allow the listener to see a fixed window ahead (e.g. 0.5 s) since playback is offline; anticipation is
  what a dancer who knows the song does.

**Q2. V1/V2 style ID (7.67.5) reverses Kosta's 7.56.11 ruling.** 7.66.4 called E5 "pending Kosta's ruling", but 7.67 lists it as step 5
with an explicit ID input.
- (a) Keep step 5 as a variant to TEST against E1 only after Kosta rules on it; E1 stays pooled with no label. **[recommended]**
- (b) Kosta accepts the style ID now.
- (c) Drop it.

**Q3. 7.67.3b bundles several changes into one variant**: per-layer compression, separate auxiliary inputs, a separate ear embedding,
and the three timescale groups (which is 7.66's E4). "One change at a time" cannot attribute a result to any one of them.
- (a) Two variants: E4 (timescales only) first, then the structured input on the better listener. **[recommended]**
- (b) Keep it bundled as one "structured listener" step; if it wins, ablate afterwards.

**Q4. Ablations for every variant (7.66.3) cost 4 trainings per variant.** At ~140 songs each training is probably hours (estimate
pending). Eight variants and ablations would mean about 30 trainings.
- (a) Full 4-way ablation for E1 and for the final candidate only; intermediate variants compare against E1 alone. **[recommended]**
- (b) As written: every variant.

**Q5. The swapped-music STOP has no threshold.** "Stop if no gap" on likelihood needs a rule.
- (a) Per held-out song, true-music log-likelihood minus the mean over its 3 swaps; STOP if the bootstrap 95 % interval of the mean over
  songs (resampled by song, seed fixed) includes 0. **[recommended]**
- (b) STOP if fewer than 70 % of songs have a positive gap.
Also: with 19 test songs, some may lack 3 partners within 5 % tempo. (a) fill from the validation songs, then allow half / double tempo;
report how many needed it **[recommended]**; (b) use fewer partners for those songs.

**Q6. The affect tests are small.** 20 songs with 5 labels gives about 4 per label; the passage test needs pairs matched on tempo and RMS
with different labels, and there may be very few.
- (a) Keep both report-only, as written, and report the counts; no conclusion drawn below 10 passage pairs. **[recommended]**
- (b) Raise the count: Kosta labels 40 songs (test + validation), 3 passages each (~45 min of listening).

**Q7. Offsets and the decoder (7.67.6-7).** The frozen vocabulary decoder blends each chunk with its neighbours. A shifted chunk changes
its neighbours' context, so the "decoded chunk shifted -200..+200 ms" soft targets are computed with neighbours that the run time does
not see.
- (a) Compute soft targets with the shifted chunk decoded in its real neighbours' context (decode the whole local sequence per shift).
  **[recommended]**
- (b) As written (chunk alone); accept the mismatch, report realised timing.

**Q8. Viewing answers differ between 7.65.3 and 7.66.5/7.67.** 7.65.3: "which fits the music?" + "neither"; 7.66.5: tie option +
confidence; 7.67: A / B / tie / both poor + confidence.
- (a) One answer set everywhere from now: A / B / tie / both poor + confidence (3 levels). **[recommended]**
- (b) Keep each as written per viewing type.

**Q9. Record as 7.68.**
