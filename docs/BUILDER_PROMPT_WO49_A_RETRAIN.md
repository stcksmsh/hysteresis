# Builder prompt: work order 49, A retrain to convergence with pause up-weighting; all checks rerun (7.78 section 4) (2026-11-17)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BRAIN_SPEC.md` **§7.78** (section 4: Q3, Q4, Q5, Q6; section 5 order), then `docs/A_RULES.md` with addenda 1-2 (branch
merged into `body`) and 7.73-7.77. No motor clock, no pulse, no B. No verdict. One arm. Another builder (WO48, internal pulse) works on cores
14-19: stay on cores 6-13.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-grammar2 origin/body`; absolute paths; no new
worktrees. Detached units `hyst-wo49-<fresh>`, `MemoryMax=10G`, `MemorySwapMax=0`, cores 6-13, `python -u`; read logs 1 min after start;
catch errors per item and log names. Run on battery. Commit and push before every run. Plain commit messages, no co-author or attribution
lines. No installs, downloads, uploads. Env `/secondary/hyst-env/brain`. In (read-only): `/secondary/hyst-data/body/grammar/` (WO45 data,
vocabularies, stats, first-run models). Out: `/secondary/hyst-data/body/grammar2/` (keep the first run untouched). Training resumable per
epoch. Night log `docs/NIGHT_LOG_body-grammar2.md`. Keep messages short.

## Read first

`docs/BRAIN_SPEC.md` 7.73-7.78; `docs/A_RULES.md` (with addenda 1-2), `docs/A_REPORT.md`, `docs/NIGHT_LOG_body-grammar.md`; code
`scripts/body/grammar_{data,model,train,checks,clips}.py`.

## The work

1. **Rules addendum 3 to `docs/A_RULES.md`, pushed before training:**
   - epoch cap 100, early stopping as ruled (patience 5 on the validation sum of the five head cross-entropies; learning rate halved after
     2 epochs without improvement), seeds 49101, 49102, 49103 (new, so the first run stays comparable);
   - pause up-weighting (7.78 Q4): windows containing any pause token (pause probability > 0) get a stated weight factor in the loss
     (default: the factor that makes pause-containing windows half of the effective training weight per dataset; state the numbers);
     the pause request gets exactly the same corruption and dropout treatment as the other controls (state how the current code treats it
     and what changes);
   - everything else identical to WO45 (architecture, data, vocabularies, controls version 2, auxiliary loss weight 1.0).
   Tests: weight factor applied as stated; pause treated like the other controls in corruption and dropout.
2. **Timing run + estimate** (3 seeds on cores 6-13); night log "A2 ESTIMATE"; if the worst case is <= 12 h, train without waiting.
3. **Train**; report per epoch per head as WO45B did.
4. **Rerun every A check** of `A_RULES.md` section 6 + addenda 1-2 on the new models (same starts, seeds of the checks unchanged, per-start
   values saved), including the pause intervention (low 0 / high 1.0 and p99) and the posture/gesture split. Report side by side with the
   first A (WO45B fix 1) and the first-run numbers.
5. **S-B clip candidates on the new A** as WO45B (same excerpts; human; A with own / other / shuffled / constant controls; V1 vs V2 matched
   on realised sharpness). The motor-clock pairs of 7.78 Q7 come later (they need the pulse and the motor clock); leave room in the
   manifest. Render, manifest only; do not serve.
6. **Done when:** `docs/A2_REPORT.md` and "A2 READY <commit>" in the night log, pushed; all tests pass. Then STOP.
