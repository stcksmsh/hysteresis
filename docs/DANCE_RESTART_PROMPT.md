# Fresh-agent prompt — investigate, clarify intent, then implement

Work in `/secondary/Programming/Github/Hysteresis`.
`/home/stcksmsh/Programming/Github/Hysteresis` resolves to the same checkout.
Preserve all modified/untracked work. Do not reset, clean, create a worktree,
commit, push, install models, or drive hardware. Frozen `src/` and `tools/` are
read-only; active offline analysis lives in `scripts/`.

## Latest user instruction — 2026-10-03

The user explicitly wants the next agent to investigate the repository FIRST,
then ask questions about unresolved intent — including **what they actually want
from this project** — BEFORE continuing implementation. The previous agents
moved too quickly from technical evidence into invented artistic decisions.
Do not treat the newest prototype, old plan, or this handoff as an approved
artistic brief. Do not assume that making arms move more, adding formations,
or exposing more analysis is the desired outcome.

## 1. Investigate without changing implementation

Read, in order:
1. `AGENTS.md`, then the latest entries of `docs/DANCE_HANDOFF.md`.
2. `crates/hyst-previz/README.md` and relevant R4/R7/R8/R9 sections of
   `SINTEZA_IMPLEMENTATION_PLAN.md`; choreography spec sections 4 and 6 are
   directional background, not a substitute for user clarification.
3. Git status/diff/log and actual Rust/Python code. Separate pre-existing work
   from the newest unaccepted integration. Check whether `.ai/state.json` exists
   and follow its workflow if present.

Trace audio -> source/structure evidence -> musical interpretation -> motion
intent -> ensemble scheduling -> rig retargeting -> playback and projection.
Inspect actual sidecar/score data and representative preview frames. Do not
claim to have watched motion or heard music without perceptual access.

Summarize briefly: what works, what is speculative, where current implementation
fails, and which decisions need the user. Reading and targeted checks are fine;
do not begin another implementation or render campaign before clarification.

## 2. Clarify what the user wants

Ask focused questions grounded in the investigation. Use plain language, not
crate names or generic product-planning questionnaires. Start with the intended
experience and acceptance bar. For example:

- What should someone watching the installation experience? What would make you
  say “yes, this is the project,” rather than “arms moving to music”?
- What does convincing musical interpretation mean to you: following particular
  musical voices, developing dance phrases, anticipating structure, dialogue
  between arms, or something else? Ask for a concrete positive reference or an
  explanation of a rejected passage; do not presume these choices are exhaustive.
- What should multiple arms contribute, and how should projected visuals relate
  to them? Is the next proof about choreography alone or the whole installation?
- What is the smallest next result you want to judge, and what would count as
  failure? Which parts of the current direction should be discarded?

After that, resolve only technical unknowns needed for the chosen next slice:
rig axes/geometry if relevant, desired agent arrangement, acceptable offline
preparation, and whether this supplied song is still the right test case.
Do not repeat facts already settled below. Do not ask the user to design the
algorithm or review a giant requirements list. Ask a few high-value questions,
wait for answers, restate the agreed objective and acceptance criteria, THEN
continue implementation. No answer means no artistic approval.

## 3. Established constraints, not open questions

- Automatic interpretation is mandatory. Offline analysis has the whole song
  available and must support musical memory, anticipation and coherent motion.
- Target is multiple synchronized 3D articulated robot arms plus projection.
  Provisional arm: base rotation + three bends + extra local rotation at second
  joint (five servos); distal link optional. Exact axes/calibration are unsettled.
  Local rotation axes must inherit upstream orientation.
- All earlier motion recordings were rejected. New ensemble prototype is also
  unreviewed; green tests are not dance approval.
- Human timestamps in `scripts/instant_crush.acceptance.json` are validation-only.
  Never feed them into inference, cue planning or choreography. Authored director
  was removed from production and survives only outside git as diagnostic material.
- No allin1/natten installation, expensive GPU experiments, hardware driving,
  commits or pushes. Preserve existing CPU-separated stems; do not regenerate.
- Follow repo worker ownership/delegation rules after scope is clarified.
  Communicate smart caveman: concise, exact, no filler.

## 4. Current implementation — inspect before trusting

Existing mixed-audio memory planner remains `crates/hyst-compile/src/memory.rs`.
Its planar motion was rejected. `scripts/dance_stems.py` and
`scripts/dance_structure.py` produce estimated source activity, local transitions,
multiscale novelty and recurring-material evidence. These are uncertain features,
not confirmed semantic song sections or downbeats.

Newest uncommitted integration adds:
- `crates/hyst-compile/src/director.rs`: `compile_interpretation` consumes
  musicalMemory + stemInterpretation + musicalStructure; emits rig-independent
  sweep/lift/fold profiles, source character, formation choices, recurrence and
  anticipation. Choices and thresholds are prototype assumptions, not user approval.
- `crates/hyst-compile/src/ensemble.rs`: configurable local-axis rig, illustrative
  five-servo geometry, existing hyst-choreo formation helpers, offline per-agent
  tracks, shared quintic sampling and 3D forward kinematics. Interior tangents
  support continuation; position/speed/acceleration use continuous Bezier bounds.
  No jerk, collision or hardware-safety proof. Inspect actual formation handling:
  some mappings remain simplified and must not be oversold.
- `crates/hyst-output/src/ensemble.rs`: absolute-time/AudioClock sampling.
- `crates/hyst-previz/examples/ensemble_preview.rs` + `src/ensemble.html`:
  independent new 3D canvas preview, audio-master transport, shared floor visuals,
  evidence readouts. Supports --agents, --groove-only, --no-reuse, --rig, --score,
  --interpretation. Old single-arm APIs/preview stay intact.
- `scripts/ensemble_acceptance.py`: independent numeric verifier drafted during
  this session. Check latest handoff for run status; do not assume completed audit.

Real track compiled to 55 cues over 339.824 seconds. Automatic local vocal exit
185.15s and return203.60s influence decisions. Source contrast distinguishes
percussive break from bass/vocal passages. This does not establish good dance,
correct semantic sections, or correct recurrence phrasing.

**Known geometry failure:** sampled exported world points reached z=-0.1377m,
below the displayed floor. This is unresolved. Investigate real rig intent and
retargeting; do not hide it by arbitrarily raising the whole installation.
Latest silence-hold and preview-label changes may postdate exported artifacts.
Regenerate only after clarification and necessary fixes.

## 5. Assets and verification

External media directory (never commit generated media):
`/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm/`

Useful files:
- `instant-crush.m4a`, `instant-crush-stereo-analysis.wav`.
- `instant-crush.interpreted.sidecar.json` plus earlier memory/stems evidence.
- `stem-analysis/htdemucs/instant-crush-stereo-analysis/` contains vocals, drums,
  bass, other WAVs + separation.json. CPU separation already complete.
- `song-ensemble.html`, `instant-crush.ensemble.score.json`,
  `instant-crush.ensemble.intent.json`; groove/no-reuse exports may also exist.
- Rejected full videos and old before/after excerpts remain as baselines.
- `record-ensemble.cjs` was drafted but no new ensemble excerpt/video was produced
  before the user redirected work to this handoff.

Loopback8766 server was unavailable when checked this session. Verify before
linking it. Preview can be inspected locally; source HTML contains placeholders
and must first be exported. Don't imply an old artifact matches newest code.

Recent checks: 15 Python analysis tests, legacy JS timing/media helpers, new
ensemble JS deterministic seek/offset helpers, CPU Rust workspace tests excluding
hyst-render and workspace check passed during integration. Workers reported
targeted clippy pass. These precede some final edits; inspect latest receipts and
rerun affected checks after changes. No new GPU or hardware checks.

## 6. Continue only after answers

Record agreed creative objective, explicit non-goals, and one concrete next
acceptance slice. Keep musical reasoning independent from rig DOF and agent count.
Prefer a small representative real-audio proof that tests the agreed intent.
Show before/after and core groove with specials disabled when relevant; verify
seek, continuity, limits, real rests, recurrence and uncertainty honestly.
Ask for human dance-quality judgment on short excerpts before any full-song
render. Do not call this installation complete because a pipeline compiles.
Append an honest checkpoint to docs/DANCE_HANDOFF.md and AGENTS.md.
