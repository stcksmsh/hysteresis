# Hysteresis dance handoff — 2026-09-24

## Latest user priority — 2026-10-01 bottom-up dance restart

User rejected both recordings and amplitude/template fixes. Musical memory,
whole-song analysis, anticipation and recognizable dance are primary goal.
Read `docs/DANCE_RESTART_PROMPT.md` for fresh-agent task. Current score/recordings
are rejected baselines, not perceptually accepted work. Native window/hardware
integration must not displace this priority. User requested checkpoint commit
and fresh prompt; no further dance implementation in this handoff session.


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

### Phrase context + remote transport — 2026-09-28

Continued in canonical `/secondary/Programming/Github/Hysteresis`, baseline
`a4afbda`, with only pre-existing `.codex/` untracked. Two bounded Terra workers
owned compiler and remote transport; coordinator reviewed, integrated and verified.

Compiler uses valid supplied section edges and section-specific recovery posture.
Unlabeled spans use a bounded ±4s content neighborhood clipped at declared edges;
energy/timbre departure selects related motif variation. Cue index no longer picks
gesture or direction. Invalid/overlapping section spans are ignored deterministically;
nearby declared edges remain exact. This is heuristic context, not inferred verse/
chorus recognition. Existing single early break is not stretched over whole song.

Remote preview advances before autoplay permission; explicit Play/Enable audio
hands off at current preview position. Pause/seek/end no longer resume fallback.
Removed global pointerdown play race; pending play rejection cannot overwrite
intentional pause status. Normal music/synthetic paths retained. Added full-viewer
mock media regression tests, plus section/posture/anchor/continuity compiler tests.

Verified: compiler12 + previz4 tests; workspace check; workspace CPU tests excluding
hyst-render; targeted compiler/previz clippy; JS timing + media suites; diff-check.
Chrome real media: blocked autoplay, first Play, handoff, quick pause, seeks15/105/
335/60s, mobile width, allowed muted autoplay/unmute, normal playback. Screenshot
inspected. No GPU rerun; existing renderer clippy debt remains outside this slice.

Regenerated external song.html/score/audit:221 cues,56 exact onset anchors,5 holds;
max speed33.85/40.35/47.47deg/s, acceleration150/170/200deg/s², minimum floor
clearance26.33cm sampled120Hz. Browser preview server on loopback8766. Review:
http://127.0.0.1:8766/song.html?remote=1&fix=3. Existing MP4s were not regenerated.
No commit/push, generated media outside repo, frozen src/tools untouched.
Native score/output integration and perceptual dance acceptance remain open.

### Native score output + CPU inspection checkpoint — 2026-09-30

Implemented bounded single-arm native score playback/inspection slice. Two Terra
workers owned hyst-output and CLI/previz; coordinator integrated and reviewed.
Existing September28 dirty changes preserved. HEAD remains a4afbda; no commit/push.

hyst-output now exports ChoreographyOutput, ChoreographyFrame and ClockPosition.
Constructor validates finite limits, exact contiguous score/knot coverage, shared
boundary poses, immutable holds, exact arrival anchors and analytic quintic speed/
acceleration bounds. Sampling uses absolute time with explicit Logical/Audible
AudioClock domain; no dt integration or patchgraph evaluation. Nonfinite sample
time fails; finite out-of-range time clamps. Cue metadata selects next cue at
shared boundary; phase selects first knot at/after time, including exact arrivals.

CLI commands:
  cargo run -p hyst-cli -- score-sample SCORE_JSON SECONDS [SVG_PATH]
  cargo run -p hyst-cli -- score-trace SCORE_JSON WAV_PATH [FPS] [LATENCY_MS]
Trace is offline WAV sample-clock simulation, no audio device. FPS integer1..240,
latency0..5000ms. Duration mismatch fails before frames; tolerated one-sample skew
and latency tail drain to exact score endpoint. JSON/NDJSON stdout, --help, path
errors and broken-pipe handling implemented. Native SVG uses existing Arm FK,
32/26/12cm assumed links, escaped metadata, joint/energy/accent readouts.
Browser song_preview_data now validates/samples same ChoreographyOutput.

Verified: workspace cargo check; CPU workspace tests excluding hyst-render;
targeted compiler/output/previz/CLI clippy -D warnings; JS timing/media tests;
git diff --check. Output23 tests; CLI4 unit+2 integration tests; previz5 tests.
Final CLI integration extension tests both9/10 and10/10 WAVframes against1s score
with200ms latency: endpoint exactly once, monotonic time, bounded cadence.
No GPU rerun; existing renderer clippy warnings remain baseline limitation.

Real supplied WAV44100Hz mono14986240frames, duration339.82403628117913s.
Native30fps/50ms trace10198frames: exact final time, single terminal frame,
bounded cadence, max pose difference5.97e-13degrees vs independent score sampler,
sampled minimum floor clearance26.3254cm. Actual onset anchors retained.
Browser20391 exported FK/joint frames byte-identical numerically to prior export;
216 phase labels changed at exact knots to shared sampler semantics. Chrome
play/pause and seeks15/60/105/335s pass; no page errors. Native SVG gallery inspected.

External generated artifacts remain outside git in music-arm output directory:
  native-arm-trace.ndjson
  native-arm-60.svg / native-arm-60.png
  native-inspection.html / native-inspection.png
  native-arm-15.svg, native-arm-60.337052154195014.svg,
  native-arm-105.svg, native-arm-335.svg
song.html regenerated from shared sampler; existing score/media/MP4 unchanged.
Loopback server started via exec session97793. If offline, run node serve.cjs
in external asset directory. Gallery: http://127.0.0.1:8766/native-inspection.html
Motion preview: http://127.0.0.1:8766/song.html?remote=1&fix=3
Logs: /tmp/hyst-native-check.log, /tmp/hyst-native-tests.log,
/tmp/hyst-native-clippy.log. Independent comparator /tmp/hysteresis-native-acceptance.py.
Launch/limits documented in crates/hyst-previz/README.md.

User requested state saved and work stopped. This delivers native sampling +
static inspection/offline trace, not a native animated window or live audio loop.
Next: wire score output to native live playback/animated previz; retain explicit
clock domain and seek/pause semantics. Native wgpu connection, hardware transport,
ensemble preview and perceptual dance acceptance remain open. Frozen src/tools
untouched; pre-existing .codex/ untracked preserved. No reset/clean/commit/push.

### Full-song arm recording — 2026-09-30

User requested full song + dancing arm demo after saved native checkpoint.
Recorded current score-driven browser preview deterministically at 30fps; reused
existing arm/shared visual canvases and cue captions. Bounded Terra worker owned
external recording script; coordinator reviewed framing and verified final media.

External output (no generated media in git):
/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm/arm-dance-instant-crush-current.mp4
Reusable record-demo.cjs lives beside video; defaults record full current song.
H.264 1920x1080, 10195 frames, 339.833333s; original AAC copied unchanged,
339.824036s, both streams start at zero. File size29612368bytes.
Verified source/final audio payload SHA256 identical:
339393e808e01509aef2cacafea29abe59f610ae036210680415ce3e02cdace4
Final encoded frames inspected at60.333333s and335s. Chrome decoded video,
sought60/335s, played forward and paused without error. Capture muted browser;
no GPU probe, Rust changes or new dependencies. Existing dirty rewrite preserved.
Native live animation/audio loop and hardware output remain open. No commit/push.

### Tiny repeated gesture fix — 2026-10-01

User rejected full-song recording: same little move repeated. Measured old score:
221 cues, 133 nods; median active duration1.5s; median joint excursions5.40/7.41/
10.43degrees. Five quintic stops per short cue + home recovery suppressed travel;
normalized energy obscured broad loudness changes and fade.

Bounded Sol worker changed only hyst-compile/src/lib.rs; coordinator reviewed
full-song paths and integrated export. Ordinary fluctuations now coalesce into
3.6–6.8s planning spans; groove uses three quintic legs. Rest/declared edges remain
exact. RMS controls gesture, numeric recovery posture and amplitude; content,
onset pan and prior displacement guide continuation, with workspace reversal.
No random or cue-index cycling. Planning margins prevent hard-limit pinning.
Quiet fade damps amplitude/history before immutable holds. Exact accent arrivals,
C2 joins, published schema and deterministic seek preserved.

Real score:92 cues,43 exact anchors,4 holds; sway29/reach13/nod3/coil17/
flick-high16/strike-low10. Median active duration3.8s; median per-cue joint ranges
24.68/20.75/24.30degrees. Max speed55/47.28/56.39deg/s; accel150/170/200deg/s²;
120Hz sampled floor clearance22.63cm. Broad-workspace and normalized-path repetition
acceptance checks added; matched-tempo loudness/timbre/rest fixtures contrast motion.

Verified targeted compiler/output/previz/CLI Rust tests + clippy, workspacecheck,
JS timing/media tests, real-score audit. Browser seeks15/60/105/200/285/335s,
play/pause and selected song source pass with no page errors. Representative
whole-arm path plots reviewed. Cargo logs /tmp/hyst-phrase-integration-tests.log,
/tmp/hyst-phrase-check.log and /tmp/hyst-phrase-clippy.log. No GPU rerun.
Canonical external song.html, score/audit regenerated. Score SHA256:
dc09962813dadc2f102730ca16d82827c9e4a5410cb9c5e95d01bf305c3a0fe8
Preview http://127.0.0.1:8766/song.html?remote=1&fix=4
Older recording preserved. Generated media remains outside repo. Frozen src/tools
untouched, dirty native work preserved. No commit/push. Dance quality still needs
user listening review; no native live window or hardware added.

Replacement full-song recording verified:
/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm/arm-dance-instant-crush-phrases.mp4
H.264 1920x1080/30fps,10195frames,339.833333s. Original AAC preserved;
packet payload SHA256 still339393e808e01509aef2cacafea29abe59f610ae036210680415ce3e02cdace4.
Encoded frames15/105/200/320s inspected; intact canvas and contrasting silhouettes.
Chrome MP4 playback/seeks/pause pass. Prior tiny-motion recording preserved.
State saved; no active encode remains.

### Rejected choreography + fresh diagnosis handoff — 2026-10-01

User rejected larger-phrase recording too: looks like movement/flailing, weak
energetic contrast, no clear bass/vocal following, rare hits seem coincidental.
User requires bottom-up musical memory/anticipation and dance generation;
previous geometric/amplitude fixes missed root problem. Neither recording is
perceptually accepted. Saved self-contained docs/DANCE_RESTART_PROMPT.md.
Current infrastructure remains useful; no further behavior edits this session.

Checkpoint verification: CPU workspace tests excluding hyst-render and workspace
check pass. Strict workspace clippy reconfirmed baseline manual_is_multiple_of
warnings julia.rs308/1574. Targeted dance-crate clippy and JS tests pass. GPU
unavailable; no rerun. Commit includes accumulated related compiler/remote/native
output/CLI work + tests/docs. Local .codex/config.toml excluded; external assets
excluded. User requested local commit, not push or new chat creation.

### Whole-song memory + continuous groove candidate — 2026-10-01

Fresh diagnosis: original sidecar contains no usable whole-song sections, stem
presence, recurrence or novelty. Normalized energy falsely stays high in silence;
onset pan is synthetic. Old compiler averages short spans into template choices,
then zeroes velocity/acceleration at every knot. Prior recordings remain rejected.
Current user restart authorizes implementation; previous handoff-only pause ended.

Added scripts/dance_memory.py using already-installed NumPy/SciPy/SoundFile.
Original input stays immutable. Additive musicalMemory v1 contains ordered
16-beat mixed-spectral rhythm profiles, low/high flux, chroma comparisons,
absolute level, provisional pulse and measured future transient estimates.
No isolated bass/drum/vocal claims; no inferred verse/chorus/downbeat/drop labels.
Grid =109.94744 BPM, beatZero0.323700s. Supplied beats have15.4ms median/88.2ms
p90 residual; fit explicitly provisional. Independent233 strong WAV flux peaks
have5.4ms median/11.9ms p90 residual against grid. Flux event timing uses50Hz
frame-center estimates, not sample-accurate acoustic ground truth.

One conservative real recurrence:87.638–96.370s →209.878–218.610s,
similarity0.9633, matching ordered rhythm + harmonic profiles. Truncated edge
phrases cannot become recall sources. Weak legacy SSM candidates discarded.
Planner preserves phrase/four-beat/two-beat timing, calibrates rhythm projection
across whole song, crossfades phrase coefficients, recalls earlier motif and
uses absolute level/rest state. Accent overlays prepare before stored estimates;
--groove-only removes all overlays, --no-reuse disables earlier-motif recall.
Compilation resolves every choice; seek needs no hidden musical state.

Knot velocity/acceleration fields additive, default zero for old JSON. Shared
quintic Hermite sampler and Bezier hull bounds retain old zero-stop behavior,
allow C2 continuation and prove continuous range/speed/acceleration bounds.
Output validation + audit consume same bounds. Changes cross crates only inside
user-authorized integration scope; CLI literals updated for additive fields.
Workers owned analysis/tests and trajectory/memory modules; coordinator owned
integration, exports, independent numeric evidence and representative media review.

Real candidate =86cues,23 exact stored arrival anchors,2 absolute-RMS HOME holds.
Continuous bound maxima speed[35.01,31.14,33.77]deg/s,
acceleration[149.84,169.77,199.93]deg/s². Sampled120Hz minimum floor
clearance21.94cm; geometry still illustrative, no physical safety claim.
Independent scripts/dance_acceptance.py reports98.8% active internal knots carry
speed>2deg/s, recalled centered motion cosine1.0, immutable rests and local
anticipation. At66.906s, >0.5deg preparation difference starts0.733s early.
60–68s groove median joint-vector speed6.40deg/s;96–104s7.49deg/s;
264–272s dense transients19.27deg/s;336–339.8s completely still. This does
not prove recognizable dance. Content/density matters; motion level is not a
monotonic meter of mix RMS across different phrases.

External outputs in existing music-arm directory: song-memory.html,
song-memory-groove.html, instant-crush.memory.{sidecar,score,evidence,audit,
acceptance}.json, instant-crush.memory.groove.score.json, dance-memory-review.html.
Original song.html/score/media preserved. Audible before/after clips60–72,
96–108,64–70s; no-accent60–72s; source/recall87.64/209.88s; dense264–276s;
fade326–339.824s. Encoded frame grids inspected at60/96/264/326s. No assistant
audio-perception facility available; human listening gate remains open.
Full candidate recording currently encoding; final verification appended below.

Verification: cargo check --workspace; cargo test --workspace --exclude
hyst-render =165 tests; targeted compile/output/previz/CLI clippy -D warnings;
5 Python analysis tests; JS timing/media tests; git diff --check all pass.
GPU suite not run. Strict workspace clippy has previously verified unrelated
manual_is_multiple_of warnings in Julia renderer; no renderer edits/probes.
Browser UI control rejected supplied HTTP preview URL by security policy;
no workaround attempted. Current browser play/pause/seek review unverified;
JS media/timing tests and deterministic offline recording remain verified.
Frozen src/tools unchanged. No dependencies installed, hardware driven,
media committed or remote push. Local .codex/ stays untracked.

Unresolved: isolated instrument phrasing, genuine semantic song structure,
confirmed downbeats, live predictive director, human dance acceptance. Harmonic
projection may still read as mechanical. Candidate is working foundation and
review artifact, not completed perceptual goal.

Full candidate recording completed + verified:
arm-dance-instant-crush-memory.mp4, H.2641920×1080/30fps,
10195frames,339.833333s video /339.824036s original AAC. Copied AAC packet
payload SHA256339393e808e01509aef2cacafea29abe59f610ae036210680415ce3e02cdace4
matches source exactly. Evidence saved instant-crush.memory.recording.json.
No active encode remains; loopback8766 server stays running for review.
Encoded full-song frames60/96/210/264/336s inspected: intact canvas, varying
pose, final HOME rest. Proof saved memory-recording-proof.jpg outside git.

### Rejected memory candidate → annotated solo-arm choreography — 2026-10-01

User rejected third recording too: same one-sided sway, missing musical pickup,
break and repeated high passage. Perceptual acceptance negative; prior numeric
checks did not establish dance. User supplies human structure: high≈90–126s,
break185–203s, vocals return203s while break continues until212s, then related
high212–246s. Working demo must impress through servo-arm movement alone.

Root failure confirmed: memory score hand mean remains x≈24–25cm across
pickup/break/reprise, near same HOME bubble. Break RMS≈.220 vs high≈.260/.263;
one loudness scalar cannot represent semantic break. Mix ratios change at185
and212s;203s vocal meaning comes only from user.246s shows almost no RMS/flux
change; human phrase annotation remains authoritative. Earlier memory repetition
covers only8.7s, not full36/34s high regions. Automatic semantic MIR still unsolved.

Added scripts/instant_crush.dance.json storing explicit user annotations;
unmarked regions use generic groove, fade uses measured RMS. Additive dancePlan
selects new hyst-compile/dance.rs before prior musicalMemory path. This is authored
demo choreography, not claimed automatic vocal/bass/section recognition.
32-beat phrase develops eight coordinated whole-arm silhouettes: coil, left
reach, cross-right, recoil, rise, fold, low reach, recover. Neighbor-derived
joint tangents + shared quintic Hermite preserve flowing C2 travel. Break has
separate bow/wrist-turn path with exact held reposes. Vocal-return uses restrained
wrist-led unfold within break character. Reprise recalls first high sequence at
same beat rate, with3% amplitude variation; no34→36s time stretching.
Three-beat blends prepare across human section markers. No claimed exact acoustic
arrival anchors. Core choreography stays identical with hit/windup switches off;
--no-reuse changes reprise pose by7.89deg mean across214–244s. Cue energy reports
authored motion intensity, not mix loudness. RMS HOME holds and2s entry/exit gates
retained. Invalid annotation contract fails explicitly; old sidecars still work.

Annotated viewer renders arm alone, centered and larger: no auxiliary visual,
grid or tip trails. External song-solo.html embeds original AAC bytes into one
portable HTML file; JavaScript parses, embedded AAC byte identity checked.
Existing recorder preserved; external record-dance.cjs renders solo1080p/30fps.
Before/after audible excerpts:88–106s pickup,183–215s break/vocalreturn/high entry,
210–228s reprise. Encoded frame grids inspected for all3: clear opposite-side
travel and varying folded/extended/low-reaching silhouettes; no clipping.
No assistant audio-perception facility; no human dance acceptance claimed.

Final real score=10cues (8roles +2RMS holds), continuousC2 boundaries.
Conservative speed bounds[39.08,49.39,61.36]deg/s;
acceleration[68.78,87.92,100.08]deg/s²; sampled120Hz floorclearance22.74cm.
Independent Python FK sampler: firsthigh handx−34.06→44.99cm, y27.70→68.80cm,
9bilateralcrossings, endpointpath20.28cm/s; break1.41cm/s with2.86s longestdwell;
reprise x−32.33→44.37cm,8crossings,path18.80cm/s. Recalled centered trajectory
cosine≈1 across30s. These are motion evidence, not perceptual dance proof.
Independent circular-arc fixture also verified path units + hysteretic side
crossing count; earlier sampler’s legacy-memory results preserved.

Verification: workspace check,168CPU tests excluding hyst-render, targeted
compile/output/previz/CLI clippy -D warnings,5Python analysis tests, JS media/timing,
cargo fmt --check and git diff --check pass. No renderer/GPU probes; previously
verified workspace-wide Julia clippy warnings remain baseline. Browser interactions
not rechecked after earlier URL-policy rejection; no alternate UI route attempted.
Workers owned dance.rs and independent acceptance script; coordinator integrated
schema dispatch, solo viewer, human annotation data, exports and media review.
Frozen src/tools untouched, pre-existing native work preserved. No dependency
installation, hardware driving, media commit, local commit or remote push.
Local .codex/ remains untracked. Full solo recording currently encoding;
final verification appended below.

External artifacts in existing music-arm directory: instant-crush.dance.sidecar.json,
instant-crush.dance.{score,audit,acceptance}.json, instant-crush.dance.groove.score.json,
song-dance.html, song-dance-groove.html, portable song-solo.html,
dance-solo-review.html, solo-{pickup,break,reprise}.mp4. Rejected files preserved.
Human acceptance still pending. Automatic semantic director and instrument
following remain unfinished; this authored demo tests movement foundation.

Full solo recording completed + verified: arm-dance-instant-crush-solo.mp4,
H.2641920×1080/30fps,10195frames,339.833333s video /339.824036s AAC.
Original AAC packet payload unchanged:
SHA256339393e808e01509aef2cacafea29abe59f610ae036210680415ce3e02cdace4.
Recording evidence saved instant-crush.dance.recording.json. No active encode
remains; loopback8766 server stays available. Single-file song-solo.html includes
original audio bytes. All6 before/after excerpt files contain AAC and matched
video/audio durations. Human review question pending; no positive acceptance
inferred from silence. This is authored demo, not automatic semantic solution.

### User correction — automatic interpretation and 3D ensemble (2026-10-01)

The user rejected the authored-demo direction. Automatic musical interpretation
is the project requirement, not an optional later feature. Human section times
are validation references only. The installation uses multiple synchronized 3D
robot arms, with a provisional five-servo layout: base rotation, three bending
joints, and an additional rotation at the second joint. Local axes and the final
distal link remain unsettled. Projected visuals share musical interpretation
and timing with the ensemble. A single planar arm is only a diagnostic rig.

Removed the authored dancePlan compiler dispatch and dance.rs from production.
Archived their source outside git alongside the rejected solo recordings.
Converted the song annotations to scripts/instant_crush.acceptance.json, which
must not enter inference or choreography. The optional bare-arm view is now
selected explicitly with ?solo=1, independent of analysis. The earlier authored
checkpoint does not meet user acceptance. Musical-memory output also remains
rejected. Resume at audio interpretation, not another pose/template adjustment.

Architecture audit after correction: hyst-choreo already has normalized channel
maps, agent topology and unison/canon/wave/mirror formations. They are disconnected
from hyst-compile, which does not depend on hyst-choreo and emits fixed three-joint
single-arm scores. ChoreographyOutput returns the same three-joint frame. The
previz arm is planar; hyst-hw is a stub. Five-axis kinematics, rig calibration,
3D agent placement, multi-agent resolved tracks and projection are not implemented.
Do not duplicate ensemble primitives or turn the current arrays into five unrelated
oscillators. Required integration is shared evidence -> coordinated motion intent
-> formation scheduling -> calibrated rig/channel tracks -> one absolute-time
playback clock for arms and visuals. Exact physical geometry remains provisional.

### Automatic source/structure evidence checkpoint — 2026-10-02

Installed Demucs4.0.1 with torch/torchaudio2.5.1+cpu in isolated
/tmp/hyst-dance-cpu after checking dependencies and official CPU instructions.
No global package changes, GPU, allin1 or natten. Decoded the supplied original
AAC as stereo44100Hz float WAV and separated the entire track with htdemucs,
shifts0, float32, clamp mode. Four matched stereo WAVs contain14,986,240 frames.
Producer metadata, input and model hashes, and environment requirements are saved
outside git in the existing media directory. Estimated sources remain uncertain,
with leakage; drums have approximately0.00335% samples at/above0.99FS.

Added scripts/dance_stems.py and tests: absolute RMS, globally calibrated source
activity, flux/density and local activity-entry/exit/change evidence. Optional
separation.json identifies the actual producer; absent manifest means unspecified.
Added scripts/dance_structure.py and tests: mixed descriptors plus optional
validated source RMS, multiscale4/8/16/32-beat novelty and longer recurrent-material
candidates. No authored song roles enter inference. Outputs are additive
stemInterpretation/musicalStructure evidence, not a semantic dance director.

Post-inference listening-reference check: high90–126s estimated vocalsRMS0.1086,
bass0.1661; break185–203s vocals0.0078, bass0.0440 while drums remain strong;
203–212s vocals0.0752 but bass0.0294; reprise212–246s vocals0.1115, bass0.1692.
Source estimates expose structural contrast that total mix level hid. Local vocal
exit185.15s and entry203.60s are waveform-derived estimates, not supplied labels.
Sparse novelty candidates approach126/185/203s but miss90/212/246s; broad recurring
material appears roughly122.24s apart. These are uncalibrated hypotheses, not
confirmed semantic sections or downbeats. Full semantic interpretation remains
unresolved. Do not claim all user reference boundaries were automatically found.

External files: instant-crush-stereo-analysis.wav; stem-analysis/htdemucs/
instant-crush-stereo-analysis/{vocals,drums,bass,other}.wav and separation.json;
instant-crush.stems.{sidecar,evidence}.json; instant-crush.structure.{sidecar,evidence}.json;
instant-crush.interpreted.{sidecar,evidence}.json; source-reference evidence.
Both annotated-reference and no-reference CLI runs on identical stereo input
produce identical enriched sidecars. All original memory-sidecar fields survive.
The first equality comparison used different mono/stereo inputs and failed;
matching inputs resolved it. Evidence now records the actual input WAV path.

Verified:165CPU workspace tests excluding hyst-render, workspace check, targeted
compile/output/previz/CLI clippy-Dwarnings,15Python analysis tests, JS timing/media,
fmt and diff checks. No hardware, new motion video, commit or push. Frozen src/tools
and local .codex preserved. Earlier authored-demo review request is obsolete.

Still unfinished: compiler integration of this richer automatic evidence,
coordinated musical movement, generic rig retargeting, five-axis3D ensemble
playback and projection. Compiler currently consumes musicalMemory only.
All existing dance recordings remain rejected; numeric/source evidence does not
prove dance quality. Continue here, not with manual section labels or amplitude
tuning of the old single-arm score.

### Fresh-context handoff requested — 2026-10-02

User requested a fresh-context agent. Rewrote docs/DANCE_RESTART_PROMPT.md around
the corrected automatic-interpretation/3D-ensemble target, current source evidence,
uncommitted code, validation, assets and missing compiler/rig integration.
No further dance implementation in this handoff turn. No commit or push requested.
The saved project path resolves to this same checkout; the new chat must reuse
its working tree and preserve all modified/untracked work.

### Automatic director + 3D ensemble integration checkpoint — 2026-10-02

Found prior uncommitted slice (undocumented): `hyst-compile/src/director.rs`
(sidecar with musicalMemory + stemInterpretation + musicalStructure → `Interpretation`
cues: character, formation, calibrated source activity, confidence, recall_from,
anticipation, 3-axis sweep/lift/fold profile), `ensemble.rs` (`Rig` of
`RigChannel` with local axes, N-agent ring placement, hyst-choreo canon/unison/
mirror offsets, per-agent quintic score with C2 tangents, FK in carried local
frames, absolute-time `sample`), `hyst-output/ensemble.rs` (`EnsembleOutput`,
audio-clock sampling), `hyst-previz` `ensemble_preview` example + `ensemble.html`
+ `tests/ensemble.cjs`, `scripts/ensemble_acceptance.py`. No authored times enter it.

This session: acceptance script self-test had wrong analytic constant (accel
1.40625, not 1.0546875) — fixed. Acceptance then exposed a real bug: illustrative
rig tip went 0.138 m below floor at 316.67 s (agent 5). Added `floor_safe` in
`compile_ensemble` (bisect from prior feasible pose; 0.02 m margin; base joint
points skipped) + test `links_stay_above_floor_under_extreme_intent`. Regenerated
external song-ensemble{,-groove,-no-reuse}.html and instant-crush.ensemble.*.json
(6 arms, 55 cues). Acceptance: 0 blockers, seek deterministic, limits within rig.

Automatic decision evidence (reference windows used only after inference): break
185–203 s → percussive-open/wave, vocal activity 0.03; vocal return 203–212 s →
vocal-led/canon with recall; reprise 212–246 s → interlocked/mirror, 32.8 s recalled,
reuse-off changes pose by 5.07° mean (49° max); high 90–126 s no recall (earlier
material absent). Specials off changes ≤0.33° mean, so core groove carries motion.
Anticipated arrivals include 185.15, 203.6, 211.0 s.

Verified: workspace CPU tests excl. hyst-render (173), clippy -D warnings on
compile/output/previz/cli, previz JS (ensemble/timing/media), 15 Python tests, fmt.
Not done: perceptual review (human gate; no audio perception here), audible
excerpts of ensemble motion, five-axis real geometry/calibration, projection
shared-visual wiring, live native loop, hardware. Misses 90/212/246 s boundaries
by design of evidence; formation vocabulary is small (mirror/canon/wave).
Preview: http://127.0.0.1:8766/song-ensemble.html (server must be running).
No commit/push. Frozen src/tools untouched.

### User rejection of ensemble preview + rework — 2026-10-02 (evening)

User review of song-ensemble.html: arms fully stationary until 0:29, low-energy
and unresponsive until the high section, then "worms", arms clip each other, no
emotion — "matching beat and RMS" is not dancing.

Diagnosis (measured): (1) stillness 0–29 s was MY regression: floor clamp added
earlier bisected every move back because the neutral wrist sat 2.4 cm above the
floor margin. (2) Old director summed stem activity *levels* into 3 scalar axes —
exactly beat/RMS matching; rate clamp (rest-to-rest bound) capped tip speed ~0.3 m/s;
knots one per beat made everything a smooth worm. (3) Ring radius 0.70 m with
0.74 m reach, arms facing inward: constant overlap, no collision check.

Rework: director motion is now event-driven. Per-stem flux peaks become impulses
with windup (opposite-direction anticipation before the measured onset), accent at
it, follow-through: drums → alternating sweep snaps + wrist, bass → weighted
drop/crouch, vocals → sustained lift/open swell + small flicks, other → bar-locked
sway; lookahead trend (rise = tension lift, fall = release fold). Knots every
beat/4; second-order follower bounds slope and slope change; knot tangents are the
follower slopes (not harmonic means). Rig: higher neutral, illustrative servo limits
raised to 400 deg/s / 6000 deg/s² (INVENTED, must be measured), larger mixes.
Placement radius scales with N (min 0.6 m), arms face outward. New hard constraints
in compile: floor margin 7 cm and inter-arm clearance 14 cm, both checked at
interpolated sub-knot poses and resolved by bisection toward the prior pose.

Evidence (numeric only): tip speed 0.6–1.1 m/s from the first seconds (was 0);
sampled 5 Hz min inter-arm distance 6.7 cm in one second (117 s), none else <8 cm;
acceptance 0 blockers; recall still differs 4° mean in 203–246 s; specials-off
still ≤0.6° so groove carries motion. 173 CPU tests, clippy -D warnings, ensemble.cjs pass.
Matplotlib pose sheet inspected: small ring of thin arms, still modest silhouettes.
NOT established: that it reads as emotional dance. Likely still weak: only 3-axis
intent, no per-phrase motif development, no emotion model beyond brightness-free
trend/vocal proxies, formation vocabulary mirror/canon/wave. Human gate open.

### Unaccepted ensemble integration; clarification-first handoff — 2026-10-03

The user stopped the implementation direction and requested a prompt for a new
agent: investigate the repo first, then ask what they actually want from the
project and clarify uncertainties before further implementation. Rewrote
DANCE_RESTART_PROMPT.md accordingly. New code is an unaccepted prototype, not an
agreed artistic direction. No new full render or dance-quality approval.

This session added uncommitted director.rs (source/structure/memory to intent),
ensemble.rs (configurable local-axis 3D rig, offline formation/track resolution),
EnsembleOutput, and a new standalone ensemble preview/exporter. Legacy planar
score APIs remain. Existing hyst-choreo helpers are reused via a path dependency.
Three bounded workers owned director, ensemble/output, and preview. All earlier
modified/untracked work was preserved; frozen src/tools untouched.

Real interpreted sidecar compiles to 55 cues/339.824s, with source-derived local
vocal exit185.15s and entry203.60s. Core source-specific contour, recurrence and
anticipation are prototype heuristics. Source estimates and provisional pulse
are not semantic truth; movement/formation mappings were not approved by user.
Shared interior tangents and quintic interpolation support C2 continuation;
Bezier subdivision bounds constrain position/speed/acceleration. Physical jerk,
collision clearance and calibration remain unresolved.

Exported song-ensemble.html, instant-crush.ensemble.score.json and .intent.json
outside git. Groove/no-reuse exports were also started. A static96s screenshot
was inspected; no motion listening judgment was made. Important numeric finding:
exported sampled joint endpoints reach z=-0.1377m below the floor. Do not call this
rig valid or hide the issue with an arbitrary pedestal. The latest silence-hold
and display-label fixes can postdate exports; verify provenance on resume.

15 Python analysis tests, legacy JS timing/media checks, new JS seek/offset checks,
CPU workspace tests excluding hyst-render, and workspace check passed during
integration. Workers reported targeted clippy clean. Final verification receipts
were interrupted by the handoff request; rerun affected checks after resumed edits.
No new GPU/hardware checks. scripts/ensemble_acceptance.py was drafted by worker;
its final status is recorded separately if available. scripts/__pycache__/ is
transient output from this session. No commit/push/reset/clean. External
record-ensemble.cjs exists as a draft; no new ensemble video was generated.

Next action: read restart prompt, inspect current code/data, ask focused creative
intent questions, wait for answers, agree next acceptance slice. Do not resume
implementation simply because remaining technical tasks are obvious.

### Clarified intent + figure-based single-arm slice — 2026-10-04

User answers (authoritative, replacing earlier agents' artistic assumptions):
viewer should think "beautiful", then "impressive", then "how did they do this".
Idea source: OK Go "Love" (industrial arms with mirrors). One convincing arm is
the higher goal; many arms, mirrors and projection come after. Hand leads, but
all joints must stay fluid and every link must avoid red zones and other arms.
Dance must reuse and alter motifs with the music and match its imagery/emotion.
User wants structured critique, not typed timestamps. Preview tool kept; planar
path dropped; formations fine but maybe limiting. Rig-agnostic; renders only;
hardware far later. Instant Crush stays. User described the first high section
as "spiral inward, then up and out, then in pairs".

Branches: previous dirty tree committed as `dance-checkpoint` (725127a). New work
on `dance-figures` in `.claude/worktrees/dance-figures`. Nothing pushed.

Added `crates/hyst-compile/src/director/figures.rs` (`compile_figures`): hand
figures in arm-relative shell coordinates (gather = inward spiral, rise, open,
arc, sway, reach, eight, still). Spans come from phrase edges plus measured
transitions; each span's class reuses the director's stem thresholds. Each class
has two figure sequences, played A, A mirrored, B, A mirrored. Returning
material copies the source span's sequence and side, 12% larger. Progress eases
into beats by drum activity. Joints: damped least squares toward the hand
target, weighted to stay near the prior pose, with zone penalties; then a hard
clearance check (three joint-space blends, bisect toward prior). Per-knot travel
is capped at the rest-to-rest quintic limit so tangent fitting always succeeds.
Output is the existing `EnsembleScore` (one agent); sampling and preview reused.

Preview: `ensemble_preview --figures [--zone x0,y0,z0,x1,y1,z1]`. `ensemble.html`
draws the hand trail (1.5 s behind/ahead) and red zones, moves the camera closer
for one arm, adds a speed select and a critique panel: hold M to mark a range
(tap = last 2 s), keys 1–9 toggle tags, optional note, click a mark to replay,
Export writes JSON with overlapping figures, planner reasons and hand positions.
Marks persist in localStorage when available.

Real track: 126 figure cues. 90.4s starts gather, rise, open, arc; 212.7s
recalls 90.4s; 203.6s recalls 78.9s. Tip speed median 0.14 m/s in verse,
0.50–0.55 m/s in high sections (max 2.9 m/s), still in final silence. Lowest
sampled joint 8.9 cm above floor. Hand-path plot and two headless-Chrome
screenshots inspected: spiral and arcs are legible; no console errors.

Verified: 174 CPU workspace tests excluding hyst-render, targeted clippy
-D warnings (compile/output/previz/cli), fmt, `tests/ensemble.cjs`. New test
proves no link sample enters a red zone that the unobstructed path crosses.
Not run: `tests/timing.cjs` (needs an exported legacy viewer path), GPU suite.

Not established: that this reads as dance. No human review yet. Figure shapes,
class table and A/A'/B/A' development are assumptions. Known weak points: class
still comes from stem-level thresholds; no emotion layer; gather does 1.5 turns
in about 2.2 s and may read as rushed; hand tracking error is not measured; the
zone variant shows the hand jittering against the box face; arm-vs-arm clearance
is not in this path (ensemble path has it); servo limits remain invented.
Emotion model: small arousal/valence regressors exist (Essentia heads on
MusiCNN embeddings); `essentia-tensorflow` has no Python 3.12 wheel here,
`onnxruntime` does. Not installed, not verified. `/tmp/hyst-dance-cpu` is gone.

External (outside git): song-figures.html, song-figures-zone.html and
instant-crush.figures.score.json in the music-arm directory. Open the HTML
directly from disk; audio is `instant-crush.m4a` beside it.
Next: user watches 80–110s and 205–235s, exports critique JSON, iterate from it.

### First human critique + second figure iteration — 2026-10-04

User reviewed song-figures.html through the critique tool (7 marks,
`~/Downloads/critique-2026-10-04T09-26-14-789Z.json`). Verdict: "night and day"
better than every earlier version; "this path may be the way to go"; not yet
good. Specific notes:
- Intro (7–10s) good, but looked janky; user suspects the render.
- 33s and 136–144s: flicks too hard/quick. This song has no sharp passages.
- High sections: too busy, stiff, does not follow the music; uses only about a
  quarter of the half-dome (front/left).
- Break 186–203s: should follow the guitar solo, which truly leads there.
- User's own model of dancing the high section: percussion is the floor
  (keeps rhythm), keys are the decision-maker (their flourishes cue movement
  from state to state), vocals give the emotion.
- User decision: drop live audio for dance; work only from offline sidecars.

Changes:
- `scripts/dance_melody.py`: additive `melodyContour` (height and salience per
  pitched stem, `other` and `vocals`) from the strongest spectral peak in
  110–2500 Hz. Proxy, not a real f0 tracker. Built-in `--self-check`.
- `figures.rs`: one figure sequence per class that runs for the whole stretch
  of that class, mirrored each repeat (no restart per 16-beat phrase); figures
  twice as long; gather is one turn. Figure progress is paced by `other`-stem
  spectral flux (faster through flourishes, lingering on sustains). Lead
  contour raises/lowers the hand; voice contour and salience extend the arm.
  Hand path low-passed (sigma 0.3 s); beat pulse capped at 0.3; previous-figure
  carry spread over half a figure. Azimuth range ±140° (was ±80°).
- Illustrative rig base yaw limit ±170° (was ±110°). Still invented.
- Preview exports 60 fps in figures mode.

Measured, old → new: hand acceleration p95 in high sections 10–12 → 1.3–1.6
m/s², at the 33s flick 5.1 → 1.1 m/s²; azimuth used in high sections about
150° → 240–260°; figure cues 126 → 87; lowest sampled joint 14 cm above floor.
212.7s still recalls 90.4s. These are motion numbers, not dance approval.

Verified: 174 CPU workspace tests, targeted clippy, fmt, ensemble.cjs, melody
self-check. Not verified: that the contour tracks the audible keys or guitar
line (the break reads mostly low, which may be chords under the solo); that the
result reads as following the music. Joint "stiffness" was not addressed
directly: only the hand path changed; posture still comes from a neutral bias.
Keys-as-decision-maker is only approximated by pacing, not by choosing figures.

External: instant-crush.melody.sidecar.json, song-figures-2.html (first export
song-figures.html kept for comparison).

### Depth cues, orbit camera, full 360° — 2026-10-04

User thought the render was broken because the arm never seemed to go behind
its base. Measured: hand was behind 28–34% of the high sections; the fixed
camera with no depth cues hid it. Preview now draws a floor shadow and a drop
line under the hand, and the stage can be dragged to orbit.

User then asked for 360° in the floor plane and rejected the agent's
servo-seam objection ("that's how dancing should work"), then confirmed the
base will rotate a full continuous 360°: settled rig fact. Implemented:
unbounded azimuth with per-figure winding offsets (no unwinding), a `circle`
figure replacing the two arcs in the high-section sequence, illustrative base
yaw unbounded, no neutral-angle bias on free joints.

Measured (song-figures-4.html): hand azimuth spans the full ±180° in both high
sections; five circles, base travel 270–350° each; base speed max 142°/s; hand
acceleration p95 about 2 m/s²; base ends about 1000° from start. 174 CPU tests
pass. Not reviewed by eye yet. Only `circle` crosses the back; other classes
keep their narrower figures. song-figures-3.html is the ±170° intermediate.

### Travel, untwist, and step 1 "moments" — 2026-10-04

User on version 4: only a chunk of the 360° is used; a joint looks stuck near
2:40; and overall "not really wow". Measured and confirmed: 69% of the song
sat within ±60° of a fixed front; the second-joint yaw had parked near 90°.

Version 5: figures are relative to the hand's current facing and travel
steadily around the base (per-class turns per 32 beats); the free base is
biased to face the hand, other joints pulled harder to neutral. Azimuth use is
now 6–11% in each 30° sector; twist joint stays within −7°..23°.

Agreed order for "wow" (user): 1 moments, 2 body (motion travelling through the
joints), 3 stillness and suspension, 4 many arms. Step 4 needs dynamic red
zones (each arm a moving zone for the others); not started.

Version 6 = step 1. Moments are measured events the arm prepares for (sink and
pull in over two beats), arrives at over two beats, stops exactly on, holds one
beat with the whole arm frozen, and releases over two. Sources: stem/novelty
transitions (strongest first, eight beats apart; pose high and fully extended)
and the strongest `other`-stem onset per sixteen beats (alternating high and
low-out poses). Transitions now take priority over phrase edges when cutting
spans, so runs start on measured changes (90.4, 185.2, 203.6, 212.7s).
`--groove-only` disables moments for before/after comparison.

Measured: 36 moments (13 arrivals, 23 flourishes), all on exact knots; joint
change during holds median 0.00°, worst 0.94°; hand acceleration p95 3.4 m/s²
(2.0 with moments off). Illustrative joint acceleration limit raised to
12000°/s² (still invented) so arrivals are not rate-capped; that exposed a
gap in the red-zone check, now six blends per knot at full margin with the
solver aiming for 1.6× margin. Shoulder at its limit 10.7% of the song.
174 CPU tests pass. No human review of version 5 or 6 yet.

### Versions 7–8: fewer holds, faster highs, hardware follower — 2026-10-04

User on version 6: better; energetic parts too slow in places; holds too many
and too long ("they have uses, just not like this"). Version 7: only the 13
section arrivals stop, for half a beat; the 23 flourishes are reached and passed
through; energetic figures three quarters as long; shorter moment windows in
energetic classes; less lingering on sustained notes.

User on version 7: good, but strange flicks remain (0:23) that real hardware
could not execute. **Hardware execution is the end goal** — treat joint
dynamics as a real constraint, not preview polish. Version 8:
- Joint follower in `figures.rs`: each joint chases its solved angle with a
  trapezoid profile at design limits (0.75 × rig speed, 0.1 × rig acceleration:
  180°/s and 800°/s² on the illustrative rig), braking before targets and
  before end stops. Rig limits (240°/s, 8000°/s²) are the hard validation
  envelope. All four numbers are assumptions until measured on real servos;
  `--rig` JSON is the calibration knob.
- Knots uniform at beat/8 (68 ms), no inserted exact knots: uneven knot
  spacing made the quintic ill-conditioned. Moments land within 34 ms.
- Flourishes no longer freeze azimuth (that caused the sideways swing at 0:23).
- Found on the way: the earlier "cannot fit tangents" failures were quintic
  overshoot past the shoulder end stop, not acceleration.

Measured v7 → v8: joint acceleration max about 3000–3300 → 1600–1800°/s² (one
shoulder segment 3042); at 0:21–0:25 base 559 → 237, elbow 1817 → 903°/s²;
hand acceleration max 22.8 → 14.5 m/s². Arrivals now reach zero speed 0–80 ms
after the event (follower lag; was 0–20 ms). Shoulder within 1° of its end
stop 11.7% of the song, unresolved. 174 CPU tests pass.
