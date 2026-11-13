# Builder prompt: work order 32D, shoulder limiter overshoot, then re-gate at 1.25 and re-pick (2026-11-13)

You are a builder for Hysteresis, continuing work orders 32B/32C on branch `body-retarget` in the same pinned worktree. Work alone and
unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER" instead of waiting. If you start fresh,
everything is named below.

**Binding:** `docs/BRAIN_SPEC.md` **§7.52** (Kosta's ruling on `docs/PLANNER_BRIEF_RETARGET_LIMITS.md`, with the overseer notes 7.52.8), then
§7.51, §7.50 and §7.49.5. All rules of `docs/BUILDER_PROMPT_WO32C_PILLAR_MOUNT.md` still hold **except mains polling: run on battery, never
wait for mains** (Kosta's standing rule for short jobs). Cores 6-11, detached memory-capped units `hyst-wo32d-<fresh-name>`, push within 30
minutes, plain commit messages with **no co-author or attribution lines**, absolute paths, no new worktrees, no training, no downloads, no SMPL
model files, nothing uploaded, no clip chosen or shaped by eye, no verdict.

## Before you start

- `git fetch origin && git merge origin/body` into `body-retarget` (brings in 7.52).
- Read `docs/RETARGET_RULES.md` (notes (h)-(j)), your night log, `scripts/body/retarget*.py`, and the data in
  `/secondary/hyst-data/body/retarget_look/` (`gating.json`, `limits_breakdown.json`, `clips.log`, `numbers.json`).

## The work

1. **Step A, limiter overshoot (7.52.2), before anything else.** Find why the command limiter's own shoulder output exceeds the acceleration
   limit (6 % of V1, 19 % of V2 candidates, up to 5.5x). Measure the limiter output's acceleration exactly as the gate measures realised
   acceleration (7.52.8). Name the code lines. Show the worst candidate (5.5x) before and after.
   - **If it is a bug:** fix it, add a unit test that fails before the fix, record the fix in a dated rules note "(k) limiter fix" in
     `docs/RETARGET_RULES.md`, push, and write "LIMITER FIXED <commit>" in the night log. Continue with step B.
   - **If it is not a bug** (e.g. a deliberate behaviour or a measurement artefact): write the cause under "LIMITER NOT A BUG <commit>" in the
     night log, push, and **STOP**. No re-gate, no render.
2. **Step B, rules note "(l) look-test tolerance and pick rule"** (pushed before any render): speed and acceleration gate at **1.25 x limit**
   for this look test only, marked as a look-test exception, not a hardware margin; every other gate unchanged (contact, clearance, end stops,
   guard > 10 %, > 8 Hz share, minimum motion). Pick rule: at most one window per FineDance sequence and at most two per genre (16,
   case-insensitive), in the seeded stream order (seed 32011, restarted from candidate 1), both variants must pass. Seeds 32021/32031/32041
   as before.
3. **Step C, re-gate** on v2p with the fix, from candidate 1. Keep the old `gating.json`, `clips.log` and `clips/` (move them to
   `/secondary/hyst-data/body/retarget_look/v2p_1.05/`); do not overwrite. Report pass counts, discards by gate, and the candidates skipped by
   the pick rule. **If fewer than 10 picks within 200 candidates: "HOLD <counts>" in the night log, push, stop.**
4. **Step D, reference:** round-1 S03 re-gated on v2p at the same 1.25 tolerance on the 2 seeded songs; a failing reference is logged, not
   replaced.
5. **Step E, render** 20 singles + up to 2 references as in 32C (1280x720 h264 + aac, 20 s, FineDance music, lamp head, camera unchanged),
   CSVs, `manifest.json` in 32A's format, and `numbers.json` with everything 32C wrote **plus, per clip and variant (7.52.5, 7.52.8):**
   commanded and realised shoulder acceleration (p50, p95, max, as multiples of the limit), the limiter's share (share of 100 Hz frames where
   the limiter changed the shoulder command) and the shoulder RMS of (command - limiter output) in degrees. Check the 5 pairs: V1 first in
   exactly 2 or 3. Check the 10 picks have 10 distinct sequences and at most 2 per genre. Look at 3 frames per clip (never to select or
   reshape).
6. **Done when:** "CLIPS READY <commit>" with MORNING SUMMARY (incl. the per-clip shoulder table), pushed. Then stop. The overseer checks
   before Kosta sees anything.

**Out of scope (stop and ask; log FOR USER):** any other change to mapping, scale, share, centre or mount; any tolerance other than 1.25;
training; gain modulation; cortex changes; hardware; uploads; using AIOZ-GDANCE, AIST++ or Motorica in this test.
