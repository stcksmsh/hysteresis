# Builder prompt: work order 32C, retarget look test on the pillar mount v2p (2026-11-13)

You are a builder for Hysteresis, continuing work order 32B on branch `body-retarget` in the same pinned worktree. Work alone and unattended. Where
this prompt leaves a choice open, take the named default and log "FOR USER" instead of waiting. If you start fresh, everything is named below.

**Binding:** `docs/BRAIN_SPEC.md` **§7.51** (Kosta's decision: change the mount, not the motion, with the overseer notes 7.51.6), then §7.50
and §7.49.5. All rules of `docs/BUILDER_PROMPT_WO32B_RETARGET_CLIPS.md` still hold: header, cores 6-11, mains-only polling, detached
memory-capped units `hyst-wo32c-<fresh-name>`, push within 30 minutes, plain commit messages with **no co-author or attribution lines**, no
training, no downloads, no SMPL model files, nothing uploaded, no clip chosen or shaped by eye, no verdict.

## Before you start

- `git fetch origin && git merge origin/body` into `body-retarget` (brings in 7.51).
- Read your own `docs/RETARGET_RULES.md` (incl. notes (h), (i)), `docs/RETARGET_SCALE.json`, `docs/NIGHT_LOG_body-retarget.md` and
  `scripts/body/retarget*.py`.

## The work

1. **Rules note first:** a dated note "(j) pillar mount v2p" in `docs/RETARGET_RULES.md`, pushed before any render. The overseer reviews it.
   It fixes:
   - **Body v2p:** the raised plane replaced by a vertical column whose top is the base footprint + 2 cm per side (state the shape: a disc
     gives a cylinder, a square a square column, and its exact size), from the floor to the old table plane, so the base sits exactly where it
     sat. The floor plane is 1.0 m below the column top. Everything else in v2f unchanged (servos, limits, end stops, self-collision).
     Contact with the column or the floor counts as contact. Where the plane lives in the code (model XML / sim), the change is a new
     variant `v2p` beside v2f; v2f stays byte-identical.
   - **Clearance gates on v2p (7.51.6):** no link point inside the column or within 0.05 m of it; hand >= 0.05 m from the column; all points
     >= 0.05 m above the floor. Every other gate as 7.44 (contact, end stops, >8 Hz share, speed/acceleration, minimum motion).
   - **Backstop guard (7.51 C):** state the mechanism. Default: when the commanded pose's FK breaks the margins above, hold the last safe
     command for that 100 Hz frame. Log per clip and variant the share of command frames held. **A clip whose guard engages in more than
     10 % of frames fails the gate.**
   - **Unchanged:** V1/V2 mappings, the 80 % share, round 1's centre, `RETARGET_SCALE.json`, the seeds (32011 stream restarted from candidate
     1, 32021, 32031, 32041), music, lamp head, the manifest format, 20 s clips.
   - **Camera:** same framing as round 1. The column is visible, and its top sits at the old table height in the frame. State any camera
     change (e.g. a lower look-at so the column shows) as a fixed number.
2. **Gate the stream on v2p:** both variants of the seeded 20 s windows, the first 10 that pass in both. Report pass counts and discards by
   gate (and guard share) in the night log and `numbers.json`.
   **If fewer than 10 pass in both within 200 candidates: write "HOLD <counts>" in the night log, push and stop.** No share ladder or other
   change without Kosta (7.51 E).
3. **Reference:** round-1 S03 (unchanged network, inputs, spinal layer) re-simulated and gated on v2p on the 2 seeded clips' music. A failing
   reference is logged, not replaced.
4. **Render** 20 singles + up to 2 references (1280x720 h264 + aac, 20 s, FineDance music), CSVs, `numbers.json` (per clip and variant:
   limiter share per joint, guard share, every gate value, joint p5-p95, mean hand speed), `manifest.json` in 32A's format. Check that the 5
   pairs have mixed order (V1 first in 2 or 3). Look at 3 frames per clip (never to select or reshape).
5. **Done when:** "CLIPS READY <commit>" with MORNING SUMMARY, pushed. Then stop. The overseer checks before Kosta sees anything.

**Out of scope (stop and ask; log FOR USER):** any other change to mapping, scale, share or centre; training; gain modulation; cortex changes;
hardware; uploads; using AIOZ-GDANCE, AIST++ or Motorica in this test.
