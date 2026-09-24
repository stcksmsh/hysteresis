# Hysteresis dance handoff — 2026-09-24

## Task prompt

Work directly in `/home/stcksmsh/Programming/Github/Hysteresis` (canonical `/secondary/Programming/Github/Hysteresis`). Coordinator: GPT-6 Astra, medium. User authorizes completing this cross-crate vertical slice and explicitly requests cheaper-agent coding delegation. Preserve existing unrelated/uncommitted work; do not reset, clean, commit everything, or start from HEAD-only worktree. Native rewrite is largely untracked.

Goal: usable music-driven arm simulation, then coherent visualizer interaction from shared musical/choreographic state. User's objection: arm follows its own anchored 16-beat motif, not song. Synchronizing that motif to audio is insufficient. Deliver functioning implementation, launch command, visible preview, and honest evidence; no plan-only finish.

Read AGENTS.md, this file, then relevant plan/source sections. Older session claims are historical; verify current flow. Coordinator may integrate across Rust crates and active `scripts/` for this goal; workers receive explicit file ownership. Frozen `src/` and `tools/` remain read-only. Browser canvas is disposable previz, Rust remains choreography source. Hardware geometry, mirrors, wall/floor layout and projector placement remain undecided; simulated dimensions must be labeled assumptions. Do not drive hardware.

First trace audio → features/grid → score/planner → joints → preview. Implement smallest complete song-conditioned planner: musical accents, energy changes, rests and usable phrase boundaries influence gesture selection, timing, size and continuation. Use preparation, arrival, follow-through, recovery, holds and recurrent motifs with variation. Avoid raw spectrum-to-joint jitter and fixed modulo-16 planning. Repeated music may repeat motion; score decisions must depend on musical content. Prefer deterministic offline planning with known future audio. Keep beat correction controls: detector output is provisional.

Milestones:
1. Reproduce current preview; verify writes and assets; establish one inspectable score/gesture contract using existing types where sensible.
2. Compile song-conditioned motion for supplied track; preview follows audio time across pause/seek. Expose concise reasons/events so user can see what motion responds to. Establish believable continuous transitions and explicit simulated joint/speed/acceleration constraints.
3. Show arm + simple visual output consuming same timeline/score, reusing existing renderer where practical. Prioritize convincing arm behavior over renderer redesign. Finish full-track usable path; document limitations instead of implying human-quality dance proven.
4. Test, watch representative contrasting sections, provide reproducible launch and checkpoint. If allowance gets tight, finish coherent current milestone and identify remaining acceptance gaps.

Acceptance: matched-tempo fixtures with different accent/rest/section structure produce different gesture decisions, not merely faster/slower loop or amplitude scaling. Silence/rest permits stillness. Seek reconstructs deterministic state; no accumulated clock drift. Transition and constraint checks cover actual planned motion. Real-track browser smoke covers play/pause/seek and contrasting song sections. Report musical interpretation heuristics and uncertainty; perceptual dance quality requires watching/listening. Run targeted tests during work; required workspace check/test/clippy before any commit, document baseline failures separately. No repeated broad checks absent changes.

Delegation + allowance: Astra owns architecture, contracts, integration and review. Delegate bounded coding to gpt-5.6-sol low/medium or gpt-5.6-terra medium; gpt-5.6-luna low for trivial docs/data tasks. Use available model IDs, never invent substitutes. Usually one worker, maximum two when truly independent. Fresh short context, exact files, inputs, done criteria, test command. Workers do not recursively delegate. After one failed attempt diagnose/escalate; no cheap-model retry loop. Coordinator does useful independent work while worker runs. Avoid duplicate audits, broad repo dumps and polling.

Check account usage initially and between milestones. Five-hour window is shared allowance, not promised token budget or runtime. Reserve roughly final 20% of remaining allowance for integration/testing/report; checkpoint before limit. No credit purchases or reset redemption. Do not promise hard spending cap: tools may lack enforcement. No expensive model/dependency installation experiments such as allin1/natten compilation during this pass.

Communication: smart caveman. Short direct sentences, no filler, exact technical names, brief progress. Never omit material failures or evidence for brevity. Adapted from Caveman guide: keep user docs understandable, claims tied to shipped behavior, no invented savings metrics. Adapted from Ponytail: trace real callers first; reuse repo/stdlib/platform/existing dependencies before new code; fix shared root cause; skip speculative abstractions; retain validation, calibration and meaningful checks. Simplicity must still fulfill requested behavior. These are selected principles, not instructions to install Claude hooks or import upstream project-maintenance rules.

Sources:
- https://github.com/JuliusBrussee/caveman/blob/main/CLAUDE.md
- https://github.com/DietrichGebert/ponytail/blob/main/skills/ponytail/SKILL.md

## Verified starting point

`crates/hyst-previz/src/lib.rs`: FK + three authored studies, `sample(beat)`, HTML generation. `src/viewer.html`: audio master clock, detected/manual grid, offset, seek, canvas. `examples/arm_preview.rs`: CLI generator. `tests/timing.cjs`: grid/clock regression checks. README documents limitations. Current motion remains 16-beat authored study, NOT autonomous dance. `hyst-compile` remains integration gap; audit existing choreo types before inventing new ones.

Prior verification: three previz Rust tests passed (geometry/clearance, reach/hold, continuity), targeted check/clippy passed; JS timing regression passed; headless browser exercised play/pause, seek to 60s, study switch, manual offset, synthetic mode and mobile layout without JS errors. These do not prove musical interpretation or hardware feasibility.

Assets already available, do not redownload or commit copyrighted media:
`/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm/`
contains `instant-crush.m4a`, `instant-crush-analysis.wav`, `instant-crush.sidecar.json`, `index.html`, `synthetic.html`, `serve.cjs`, `preview.png`.
Original user MP4 is in ~/Downloads with Instant Crush in filename.

Track duration 339.824s; reported tempo 109.95678; 617 beats, 880 onsets. Beat startup suspicious: .3483 → 3.5178 → 4.0403; interval extremes .15093–3.16952. Current sidecar has only one early break section (0–2.554), so cannot treat it as useful full-song section analysis. Do not fabricate sections. Extract/use available features or improve modestly within budget.

Existing preview: http://127.0.0.1:8766/ . If offline, run `node serve.cjs` inside asset folder. Server supports byte ranges; plain server lacking ranges caused broken seeking despite buffered audio. Keep loopback binding. For new artifacts prefer repo-local ignored output directory; existing assets readable without modifying Downloads.

Commands from repo root:
```sh
cargo run -p hyst-previz --example arm_preview -- /tmp/arm.html
cargo test -p hyst-previz
cargo clippy -p hyst-previz --all-targets -- -D warnings
node crates/hyst-previz/tests/timing.cjs crates/hyst-previz/src/viewer.html
```
Music generation accepts output HTML path, track URL, sidecar JSON path. Put generated HTML beside matching media or use correct URL. Analyzer must use canonical absolute script path: `node --import tsx /secondary/Programming/Github/Hysteresis/scripts/analyze.ts WAV SIDECAR`; symlink invocation previously silently skipped main.

## Permissions / handoff record

New task must use saved project locally, not isolated HEAD worktree. Project .codex/config.toml requests workspace-write, network access for dependencies/local preview, on-request with auto-review, plus existing preview asset directory as extra writable root. App/enforced policy may override configuration: verify inherited environment and ordinary temporary file write before workers start. Report actual blocker rather than repeatedly requesting same escalation. Global settings unchanged. Prompt itself cannot grant permissions.

No implementation edits made during this handoff. No commits created: baseline includes substantial pre-existing modified/untracked native work. Current handoff adds this document, review background, scoped Codex config and AGENTS note. Detailed previous audit copied to docs/DANCE_REVIEW.md; optional background, not mandatory full-context load.

## Checkpoint — 2026-09-24 song-conditioned slice

Implemented `hyst-compile` single-arm deterministic cue compiler, RMS enrichment
`scripts/arm_features.py`, full-track previz export + score JSON, shared score visual
panel, absolute audio-time sampling, reference studies and correction controls.
Launch instructions: `crates/hyst-previz/README.md`. Review URL:
http://127.0.0.1:8766/song.html (existing loopback range server). Media/output remain
external in original music-arm directory; original sidecar unchanged.

Real track: 339.824s, 219 cues: coil49/sway47/reach42/nod40/flick-high22/strike-low13/hold6.
RMS enables opening/outro holds despite adaptive envelope remaining high. Decisions
use envelope changes, relative accent salience, tone and low/high balance; phrase
boundaries heuristic, not verified verse/chorus analysis. 1.5s minimum cue spacing
prevents tiny constrained gestures. Quintic knot transitions share boundary poses,
zero velocity/acceleration at knots; amplitude reduced to fit simulated limits.
Geometry corrected to shoulder105/elbow-65/wrist-20 degrees, relative planar joints.

Verified: 8 targeted Rust tests; JS timing/score boundary checks; workspace cargo
check. Full-track analytic per-segment speed/acceleration audit passes; sampled
clearance minimum26.80cm (not collision certification). Observed max speed
42.29/42.44/56.10deg/s, acceleration150/170/200deg/s². Browser play/pause and seeks
15/105/335s inspected: active groove vs fade hold, shared visual changes, paused
preview left for user. Perceptual quality remains user taste gate.

Remaining limits: full workspace test was still running GPU suite at checkpoint
(`/tmp/hyst-test.log`, exec session10799); chained workspace clippy follows only if
it passes. GPU log includes MESA/EGL warnings. Do not claim full suite green without
checking completion. Targeted clippy run separately. No commit made; preserve all
baseline untracked rewrite. Frozen src/tools unchanged.

Further improvements: accent arrivals can fall back to cue midpoint when onset too
close to boundary; coil reason names upcoming accent but does not guarantee exact
arrival there. No calibrated jerk/torque/thermal/self-collision constraints, native
renderer integration or full ensemble R7/R9. Simple canvas visual proves shared
score path only. Motif variation uses content signature + cue index, not semantic
repetition recognition. Manual BPM changes readout/reference grid, not recompilation.
Shared five-hour allowance reached100% at checkpoint; no purchase/reset requested.

## Continuation — 2026-09-24 exact arrival + verified shared visuals

Supersedes earlier accent-arrival limitation. Bounded Terra worker fixed compiler:
Cue optional `arrivalAnchor`, exact onset arrival knots, >=0.38s preparation and
>=0.30s recovery window, truthful groove fallback when no anchor fits. Strong
onsets no longer cut cue boundaries at the arrival itself. Malformed/short RMS
arrays fail instead of compressing sample time. Geometry/limits remain unchanged.
Coordinator added `audit_score` CLI, visual arrival pulse and smooth cue brightness,
Next accent navigation, disabled when exhausted, human-readable phase labels.

Regenerated external song.html and score JSON: 222 cues, 56 anchors, 6 holds.
56 anchors match sidecar onsets within <=2.85e-14s JSON roundoff. Exported audit
`instant-crush.audit.json`: exact arrival knots, C2 joins, analytic max speed
33.85/40.35/47.47deg/s, max accel150/170/200deg/s², 120Hz sampled floor clearance
29.26cm. Audit rejects deliberately invalid pose. No hardware or frozen-tree edits.

Verified: compiler8 + previz4 tests; targeted clippy clean; JS timing, cue-boundary,
partial final frame, delay and visual pulse/brightness checks pass. Workspace CPU
tests (`--exclude hyst-render`) pass. Full clippy has pre-existing
manual_is_multiple_of warnings in hyst-render/src/passes/julia.rs:308,1574.
GPU bootstrap test timed out after45s with MESA/EGL errors; /dev/dri absent in this
session. Previous full GPU run never completed; no longer describe it as pending.
No renderer changes or commit made. Logs /tmp/hyst-cpu-tests.log,
/tmp/hyst-all-clippy.log, /tmp/hyst-gpu-probe.log.

Browser verified updated build: exact Next accent jump6.861496s, play/pause,
335s hold, 100s→next anchor126.374603s with0.5s delay giving media126.874603s,
zero warning/error logs. Final preview paused60s. Old tab was stale; fresh tab2
marked deliverable. Loopback range server restarted via exec session55303.
URL remains http://127.0.0.1:8766/song.html. Launch/audit commands in previz README.

Interpretation still heuristic, shared visual simple canvas proof; native renderer,
ensemble choreography, semantic repetition matching, physical actuator constraints
remain outside this single-arm slice. No claim of perceptually finished dance.

## Continuation — 2026-09-24 sections, motifs, remote clock

Cloud session (no local asset dir). User uploaded MP4; audio re-extracted,
analyzed (`scripts/analyze.ts`: 110.0 BPM, 612 beats, 956 onsets) + RMS enriched.
Compiler gained section layer (multi-feature novelty), motif recurrence,
gather/settle transitions, section posture register. Supplied track: 19 sections,
9–37s; loud `D` blocks at 98–135, 218–265, 290–299s; verse-like `C` recurs 8×.
Workstream A SSM repeats tried: similarity 0.23 only → not used as recurrence
source (compiler accepts schema-4 repeats >=0.5 if later present).

Remote viewer bugs fixed: pause jumped back to wall clock; first Play press
started then paused audio; pre-gesture seek ignored. Playwright smoke with
simulated blocked autoplay: free-run, seek 20s, Play joins at 21.1s unmuted,
pause freezes, sections at 20/110/250/336s show B/D/D3/rest. Playwright
Chromium lacks AAC → smoke used WAV; m4a unchecked in-container.

Tests: compile 8, previz 4 + acceptance 6 (audit, recurrence+mirroring,
transitions/posture, matched-tempo structure swap, exact anchors, short clip),
JS timing incl. remote clock. Mutation check: disabling mirroring or gather
fails tests. Workspace CPU tests green; clippy fails only on known julia.rs.
Not done: native previz/output wiring of score (item 2); perceptual review.

## Continuation — 2026-09-24 expressive phrase planner

User on sections build video: "still doesn't look any good" (v1: tip box 31×20 cm,
218 small cues returning to one home pose, limits 55–70°/s). Planner core
replaced: bar-based phrases (peak 1 bar, mid 2, quiet 4), 8 full-range key poses
+ mirrors, anticipation → arrival on bar (or strong onset ±0.3s) → overshoot/
settle → beat bounce/onset hits; quiet = slow sweep + breath; rest = frozen fold.
Limits loosened to assumed servo class. Found + fixed smear bug: truncated lead
let the limiter spread each move across the following beats (arrival was not the
pose); lead now reserved, move shrinks if bar too short. Regression test proven
by mutation. Real track: tip −65..63 cm × 8..70 cm, 98 cues, 97 exact arrivals,
8.08 cm clearance, still ~16% of time. Videos rendered offline from score (PIL +
ffmpeg, scratchpad render.py, not in repo). Perceptual verdict pending user.
