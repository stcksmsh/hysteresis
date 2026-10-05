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

### Versions 9–12: living holds, blind ablation, cleanup — 2026-10-04

User on version 8: "really good now", but holds too mechanical. A dancer's hold
is almost never a stop: small slow movement. A true hold only when the music
really cuts (dense, nothing, dense). Version 9–10: arrival holds drift steadily
(slow turn, slow rise, slight give) from before the arrival until after the
release, 1.5 beats, lower arrival pose; a `cut` detector on the RMS envelope
gives a true freeze. Instant Crush has no cuts; a synthetic-fixture test covers
the detector. Slowest hand speed around arrivals 0.036–0.18 m/s.

User asked whether the loop had over-engineered the code. Blind ablation over
1:24–2:04 (six shuffled clips, key unread until the verdict): with the hand-path
low-pass off the arm was "extremely jittery"; with beat pulse, keys pacing,
figure carry, or melody contour off the user saw no difference. A second blind
pair over the break rated the no-contour version same or slightly better. All
four were deleted, with `scripts/dance_melody.py`. Consequence: nothing follows
keys, guitar or voice directly any more; that request is fully open.

A clean-context reviewer found no bugs in `figures.rs` (its two "needs changes"
claims were checked and were wrong). On the user's decision ("option A") a
clean-context worker then deleted every older dance planner and the features
holding them in place: `memory.rs`, the planar score planner in `lib.rs`,
`compile_interpretation`, `compile_ensemble` with formations and arm-vs-arm
clearance, `hyst-output` choreography/ensemble outputs, the old single-arm
preview and viewer, `hyst` CLI `score-sample`/`score-trace` (the CLI now only
prints usage), two old acceptance scripts and `arm_features.py`. About 6300
lines removed. `ensemble_preview` is figures-only (`--figures` is a no-op).
The planner's score and HTML output are byte-identical before and after
(checked by the worker and again by the coordinator). 130 CPU workspace tests,
clippy, fmt, `ensemble.cjs` and 15 Python tests pass. Older entries in this file
and in `AGENTS.md` §5 describe deleted code.

Found during verification, not fixed: `--groove-only --no-reuse --zone ...`
together fails with "cannot fit tangents" (see restart prompt, weak points).

User's last requests: better render of the arm ("too shitty"), then continue
with body, speed smoothing, stillness, keys-decide, many arms with dynamic red
zones. Hand off to a fresh agent via `docs/DANCE_RESTART_PROMPT.md`.
Latest export: `song-figures-12.html` (outside git).

### Version 13: solid arm render — 2026-10-04

User called the arm render "too shitty" (thick 2D lines and dots). Rewrote the
arm drawing in `ensemble.html`, still canvas 2D: the recorder runs headless
Chrome with `--disable-gpu` and reads the canvas with `toDataURL`, so WebGL was
the riskier choice and the file stays one offline page. Links are tapered
cylinders shaded from one world light (gradient across the silhouette from real
cylinder normals), joints are lit spheres, the base is a turntable with a marker
toward the shoulder, the hand is a glowing ball, and the arm casts a soft floor
shadow along the light direction. Depth-sorted. Trail fades with age; stem rings
dimmed. Critique panel, zones, orbit, drop line and the `draw(t)` hook unchanged.

Planner untouched: before the change a fresh export was byte-identical to
`song-figures-12.html`. Look is an agent assumption (matte light arm, dark
stage), not a user choice. Joint housings are spheres because preview frames
carry joint positions only, not axes. Link radii are invented (15–31 mm).
Checked: stills at 95, 104, 150, 222 s inspected, no page errors; recorder ran
unmodified. Clips of 1:24–1:54: `render-12-old.mp4`, `render-13-new.mp4`
(outside git). No user review yet. Next: step 1 "body".

### Version 14: figure clock (hold wait + speed cap), look 1 — 2026-10-04

User on version 13: 1:31–1:33 too fast for the music, "especially the second
flick"; follows the music OK, could be a tad better; likes look 1 (dark stage,
light painting) and look 2 (studio product shot) most.

Measured cause at 1:31: the arrival at 90.4 s holds the hand 1.5 beats while
the figure path kept running underneath; on release the hand chased it, 185°
round the base in 1.25 s at 1.4 m/s (the same `gather` elsewhere: 0.9), then
reversed at 1.0 m/s (elsewhere 0.5). First attempt (figures only wait out the
hold) made it worse, 1.8 m/s: the full wide low start of `gather` then played
at its raw speed. Kept: a figure clock in `figures.rs`. It stops during any
hold, never carries the hand faster than `HAND_SPEED_CAP` (0.8 m/s, a guess),
and makes lost time up at 15% extra pace. This is restart-prompt step 2
(speed smoothing) done ahead of step 1. Moments are not capped.

Measured after: 91.5–93.5 s 0.8–1.0 m/s, reversal 0.55; song median 0.35, p95
0.83 (was 0.94), max 2.22 (a moment). Not measured: how far figures lag phrase
edges. The 2 s plateau at exactly the cap may read as mechanical.

Render look 1: glossy gunmetal links with a highlight strip, dark housings,
hand light pooling on the floor, 4 s additive ribbon trail, vignette; stem
rings removed from the stage (numbers stay in the Evidence panel). An arm
reflection in the floor was tried and dropped (read as detached clutter).
Look 2 not built. 130 CPU tests, clippy, fmt, `ensemble.cjs` pass. Clip:
`render-14.mp4`, export `song-figures-14.html`. Awaiting user review.

### Version 15: shoulder on the base axis, capsule links, zone-aware follower — 2026-10-04

User on version 14 (render only; no verdict yet on the speed change): the base
joint rotates around something that is not the centre of the base plate, and
the joints look bad and clip through the cylinders.

- Base: true to the rig, which put the shoulder 8 cm sideways from the yaw
  axis. The illustrative rig now puts it on the axis, 8 cm up
  (`base_yaw` link `[0, 0, 0.08]`). Still invented geometry. This changes the
  solved joint angles slightly; hand targets are unchanged.
- Joints: links were flat-cut quads drawn over larger joint balls. Links are
  now capsules whose round ends share the body shading; joint balls are gone.
  The base is a pedestal plus a column to the shoulder.
- The rig change made `hand_travels_and_no_link_enters_a_red_zone` fail with
  the known "cannot fit tangents" weak point. Fixed at the root: the follower
  now limits each link sample's travel per knot to what it could brake within
  its remaining clearance to any zone (floor included), so the hard bisect no
  longer stops the arm abruptly. The documented failing combination
  (`--groove-only --no-reuse --zone 0.15,0.3,0.25,0.6,0.6,0.7`) now compiles.
  Not tested with more zones or moving zones. Side effect: links skimming the
  floor are slowed; song hand speed median and p95 unchanged (0.35, 0.83).

130 CPU tests, clippy, fmt, `ensemble.cjs` pass. Stills inspected at 92.5 and
150 s. Clip `render-15.mp4`, export `song-figures-15.html`. Awaiting review.

### Version 16: trail sorted with the arm; render parked — 2026-10-04

User on version 15: speed OK now, look much better, "looks and feels better";
but the hand trail was always behind the arm. It was drawn as one layer before
the arm. Trail segments are now depth-sorted together with the arm, links cut
in four pieces so long links sort correctly; plain blending instead of additive
(additive burned to white where the trail crossed a lit link); gloss lowered.
Planner unchanged from version 15.

User decision: a lifelike "wow" render (Blender or similar) comes much later.
Do not polish the canvas preview further unless asked. Speed cap 0.8 m/s
accepted by eye on 1:24–1:54 only. Next: restart-prompt step 1 "body".
Export `song-figures-16.html`, clip `render-16.mp4`.

### Versions 17–18: visible base turn, chain lag killed, mirror-disc hand — 2026-10-04

- Version 17: the base seemed never to rotate (shoulder on the yaw axis, plain
  disc). Preview frames now carry each arm's first joint angle; the pedestal
  draws three marks that turn with it.
- Body step A (chain lag: each joint aims at the pose solved slightly earlier,
  more toward the wrist) was built and blind-tested at 0, 0.5 and 1 beat. User:
  all three the same quality, one "really shitty" near 1:46. Key: the bad one
  was 1 beat; 0.5 was indistinguishable from none. Deleted (commit reverted).
  Do not retry plain delay as "body".
- Found: `second_local_yaw` is effectively unused (−6°..11° over the song;
  the version 5 fix pulls it to neutral), so the arm always lies in one
  vertical plane. Shoulder reaches −109.5° of a −110° limit.
- **User decision: the hand is a reflective, non-spherical object** (a disc
  like OK Go, or mirrors on some faces), so its orientation matters. The ball
  was only a placeholder. Version 18 draws the hand as a mirror disc square to
  the last link, flashing when it throws the light at the camera
  (`render-18.mp4`). The planner does not plan orientation yet.
- Rig research for the user (references use 6-axis arms; flair comes from the
  held object and timing): for a disc with its normal along the last link,
  roll about that normal is invisible, so position (3) + aim (2) needs five
  axes. The same five servos suffice if the unused twist becomes a forearm
  roll (base, shoulder, elbow, forearm roll, wrist bend). A sixth (tool roll)
  is needed only for a hand that is not rotationally symmetric. Not decided.
- Open artistic question: what the mirror aims at. Next work depends on it.
- Version 19, user correction: the disc is **held by its edge, in line with
  the arm** ("---0", like a hand mirror), not square to the last link. So its
  normal is perpendicular to the last link and a roll about that link turns the
  disc visibly. This supersedes the "forearm roll" reasoning above: the natural
  fifth axis is a **wrist roll about the last link** (base, shoulder, elbow,
  wrist bend, wrist roll), which can be continuous because the mirror is
  passive. Not yet confirmed by the user; the rig still has the unused elbow
  twist and no roll. The preview draws the disc in the arm's vertical plane
  (`render-19.mp4`).

### Version 20: wrist roll replaces the elbow twist — 2026-10-04

**User decision, settled:** five servos; the rotation besides the base is a
**wrist roll** (mechanically simplest); more axes "definitely not now".

- Rig (`Rig::illustrative_five_axis`): base yaw, shoulder, elbow, wrist bend,
  wrist roll. `second_local_yaw` removed. The wrist link is 0.10 m plus a
  0.06 m roll link ending at the disc centre, so reach and every solved bend
  are unchanged from version 19. Roll is unbounded (passive mirror).
- Planner: a last joint that turns about its own link is detected as a tool
  roll and driven outside the position solver. First driver, **an agent
  default the user has not chosen**: the disc's face leads the hand, i.e. its
  normal turns toward the hand's travel across the wrist link; both faces are
  equal, so the nearer half turn is taken; below 0.1 m/s across, the roll is
  kept. The servo follower then limits its speed and acceleration.
- Preview frames carry `[base turn, hand roll]` per arm; the disc rolls.
- Measured: roll spans −824°..656° over the song; other joints as before.
  Not measured: roll rate, how often it reverses. The disc rim (6 cm past its
  centre) is not in the zone check; the 5 cm margin does not fully cover it.
- 130 CPU tests, clippy, fmt, `ensemble.cjs` pass. Stills at 92.5 and 101 s
  inspected. Clip `render-20.mp4`, export `song-figures-20.html`. No review yet.
- Alternatives offered for the roll: steady spin scaled by energy; flash toward
  the viewer on arrivals and flourishes. Body step B (whip on moments) not built.

### Wrist roll: jitter, then too little; three drivers under blind review — 2026-10-04

User on version 20: a lot better, wrist "a tad jittery". Measured: 41 roll
reversals a minute, speed pinned at the 180°/s cap. Version 21 smoothed the
aim (half-second travel window, easing by travel): 22 reversals a minute, p95
77°/s. User on version 21: now "not rolling enough; it should move, flourish,
but not jitter, big difference". So the target is much roll with no reversals.

`CompileConfig::roll` / `--roll` now selects one of three candidates. The
losers must be deleted after the verdict:
- `lead` (default for now): face leads the hand's travel, livelier gain.
  28 reversals a minute, acceleration p95 at the 800°/s² design cap.
- `spin`: 150° per metre of hand travel, one direction. 0 reversals, speed
  median 52, p95 123°/s.
- `twirl`: spin plus an extra half turn eased over three beats across each
  moment. 1 reversal a minute, speed p95 at the 180°/s cap.
A fourth idea (turn the face to throw the light at the viewer on moments) was
written and dropped before review: it needs viewer and light positions.

Blind side-by-side prepared, not yet judged: `blind-roll-side-by-side.mp4`
(1:24–1:54, A | B | C shuffled), key `blind-roll-key.json` unread by the agent.
130 CPU tests, clippy, fmt, `ensemble.cjs` pass.

**Verdict and version 22.** User: B best, "a tight race", minus: always turns
the same way. Key: A twirl, B spin, C lead. `lead`, `twirl`, `RollMode` and
`--roll` deleted. Kept: the disc turns 150° per metre of hand travel. Its
direction is now the figure's own left/right sense averaged over two beats, so
a mirrored figure turns the other way and the roll eases through rest at the
change. Measured: 5 reversals a minute, speed median 48, p95 123°/s. The zone
test then failed ("cannot fit tangents", channel 4): zone braking was scaling
the roll too; the roll is now exempt from zone braking, since it moves no link.
130 CPU tests, clippy, fmt, `ensemble.cjs` pass. Clip `render-22.mp4`
(1:24–2:04), export `song-figures-22.html`. Not reviewed yet.
Agreed next: side-by-side tests of the next decisions, starting with body B
(whip or wave on arrivals and flourishes), then spin rate, then keys-decide.

### Version 23: disc on a stem, distinct faces; roll candidates again — 2026-10-04

Pull request 13 was merged by accident mid-work; this continues on branch
`wrist-roll` (pull request 14). `master` still carries the earlier three roll
drivers until 14 merges.

User on version 22: the disc should sit further out and overlap the arm less
(it clipped); its two sides are hard to tell apart; it "seems to always rotate,
even when not needed", and always the same way. Then: "I liked the disc being
tied to travel, but it needs some in-between solution".

- Rig: wrist link 0.08 m, roll link 0.11 m (5 cm stem + 6 cm disc radius);
  reach 0.74 → 0.77 m. Preview draws a thin stem to the disc's edge.
- Disc faces differ: one warm, one cool with a dark bar.
- Measured why spin looked one-way: the figure-sense direction still netted a
  large one-way drift, and tying direction to the hand's sweep round the base
  drifted too (+5300°), because figures travel steadily one way round the base.
- Three candidates, `CompileConfig::roll` / `--roll` (default `both`); the
  losers must be deleted after the verdict:
  - `flip`: still; turns over (180°, 3 beats) across each moment, alternating
    direction. 0 reversals.
  - `travel`: turns 150° per metre only in fast sweeps (fades in from 0.25 to
    0.6 m/s); direction is the hand's sweep round the base relative to its
    steady travel over the surrounding four beats. 5 reversals a minute, speed
    median 2, p95 111°/s; still nets +2000° over the song.
  - `both`: sum of the two.
- Side-by-side prepared, shuffled, not yet judged:
  `blind-roll-side-by-side.mp4` (1:24–2:04), key `blind-roll-key.json` unread.
130 CPU tests, clippy, fmt, `ensemble.cjs` pass.

**Verdict, version 24.** User: "I think C looks best?" Key: A travel, B flip,
C both. `both` is now the only roll driver; `RollMode` and `--roll` deleted.
Export `song-figures-24.html` is byte-identical to clip C's export. The
one-way net drift of the travel part (about 5.5 turns over the song) was not
raised again; unresolved, low priority. 130 CPU tests, clippy, fmt,
`ensemble.cjs` pass. Next: body B (whip or wave on moments), with/without
side by side.

### Body, second attempt: wrist drag, side-by-side pending — 2026-10-04

Plain joint delay died in its blind test. New mechanism: the wrist's preferred
bend trails the hand's vertical speed (bends back as the hand rises, forward
as it falls). It is a posture preference inside the solver (`lean` argument of
`solve`), so shoulder and elbow compensate and the hand keeps its target.
Knob `CompileConfig::wrist_drag_degrees_per_mps`, flag `--drag`, default 0
(off) until judged; lean clamped to ±45°.

Measured against drag 0, whole song: hand moves 0.0 cm median at every gain
(p95 0.4 / 1.0 / 2.0 cm at gain 60 / 120 / 240); the wrist point moves 0.4 /
0.8 / 1.4 cm median, 1.7 / 3.3 / 5.1 cm p95; wrist bend range −3..74° becomes
−18..82°, −33..87°, −41..90°. Small in position; whether the changed tool angle
reads is the question for the eye.

Side-by-side prepared, shuffled, not yet judged: `blind-drag-side-by-side.mp4`
(1:24–2:04) with gains 0, 120, 240; key `blind-drag-key.json` unread. If no
difference is seen, delete the knob and `lean`. Body B (whip on moments) still
unbuilt. 130 CPU tests, clippy, fmt, `ensemble.cjs` pass.

**Verdict, version 25.** User: B and C best, C "stronger, more complex, wow",
generally nicer though sometimes B is better; worried about hardware. Key: A 0,
B 120, C 240. Wrist drag is the first "body" layer to pass a blind test.
Default is now 240 (export `song-figures-25.html` identical to clip C); the
knob stays as a hardware calibration knob.

Servo cost, whole song, drag 0 → 120 → 240 (speed p95 °/s, acceleration p95
°/s², travel in thousands of degrees): elbow 60 → 101 → 110, 216 → 380 → 439,
4.7 → 8.6 → 10.9; wrist 52 → 99 → 125, 186 → 481 → 687, 4.3 → 9.3 → 13.6. Base
and shoulder unchanged. All stay inside the follower's design limits (180°/s,
800°/s²), which are themselves guesses; the wrist's acceleration p95 is close
to that cap, so the follower is already clipping some of it. Wrist travel
about triples: more heat and wear on the smallest servo.

Body B built as a knob, off by default: `wrist_whip_degrees` / `--whip`. At
each moment the wrist cocks back by that angle over the prepare window, snaps
through to 0.6 of it just after the event, and settles over one beat; again a
posture preference, hand target unchanged. Side-by-side prepared, shuffled,
not yet judged: `blind-whip-side-by-side.mp4` (1:24–2:04), 0 / 35 / 60°, key
`blind-whip-key.json` unread. Not measured. Delete the knob if invisible.

**Whip verdict.** User: "They all seem identical." Checked it was a fair test:
at 60° the wrist point moved at most 3.5 cm in the clip and over 1 cm in only
144 of 2400 frames, so the whip acted but too little and too briefly. Deleted
(`wrist_whip_degrees`, `--whip`); planner output again equals version 25.
Lesson: a short posture pulse around a moment is too small to read. A whip
that reads would have to move the hand's own path or timing around the moment
(the arrival already does prepare/arrive), or use the roll (the disc flip
already fires on moments). Not retried.

State of "body": wrist drag at 240 kept; plain lag and whip dead.
Remaining queue: spin rate of the disc, then keys-decide (largest open item).

### Spin rate and suspension: two side-by-sides pending — 2026-10-04

User plan: do these two quickly, then hand off to a fresh agent; keys-decide in
a fresh iteration; disc-aware zone checks wait until the hand object is defined
("it needs to know what it's holding").

Two knobs added for review, both to be reduced to a constant or deleted after
the verdicts:
- `spin_degrees_per_metre` / `--spin` (default 150): side-by-side
  `blind-spin-side-by-side.mp4`, values 80 / 150 / 280, key
  `blind-spin-key.json`.
- `suspension` / `--suspend` (default 0 = off): at a high peak of a figure
  (hand higher than a quarter beat before and after, elevation above mid) the
  figure clock slows by this fraction, so the hand hangs before coming down;
  the clock makes the time up after. Side-by-side
  `blind-suspend-side-by-side.mp4`, values 0 / 0.5 / 0.75, key
  `blind-suspend-key.json`. First version slowed all high level travel and
  threw figures up to 90 cm out of place; narrowed to true peaks: median shift
  0 cm, in the clip the hand departs over 5 cm for 3.4 s (0.5) or 6.6 s (0.75)
  of 40 s.
Both clips 1:24–2:04, shuffled, keys unread. 130 CPU tests, clippy, fmt,
`ensemble.cjs` pass.

**Verdicts, version 26, session end.** Spin: user "a toss-up between A and C,
leaning A". Key: A 280, B 80, C 150. `SPIN_DEGREES_PER_METRE` is now 280 and
the knob is gone. Suspension: "they seem too similar". Key: A 0.75, B 0, C 0.5.
Deleted. `song-figures-26.html` is byte-identical to the chosen spin clip.

Found on the way: with the faster spin the fixture test
`only_a_cut_freezes_the_arm` failed in `fit_tangents`. Cause: the last knot of
a score always had zero velocity, and the fixture ends with the disc still
turning at full speed. The last knot now keeps its backward slope. The
`fit_tangents` error now prints the neighbouring knots, which is how this was
found.

Whole song, version 26: hand speed median 0.37, p95 0.83, max 2.02 m/s; wrist
bend −41°..90°, elbow 10°..110° (limit 110°), shoulder −109.5°..−21°.
130 CPU tests, clippy, fmt, `ensemble.cjs` pass. Only 1:24–2:04 was reviewed by
eye this session.

`docs/DANCE_RESTART_PROMPT.md` rewritten for a fresh agent. Next: keys-decide.

### Version 27: instrument lanes, leading lane, pulsed travel on stabs — 2026-10-04

Branch `keys-decide`. User intent stated this session: the note data is for the
whole installation ("the machine behind it"), lives in the sidecar, and must
work for other songs (e.g. twin guitars left and right). Target per instrument:
timing, relative pitch, some loudness. The voice is not an instrument but a
fluid up/down/stop/loudness.

**Tracker.** `scripts/dance_notes.py INPUT_SIDECAR STEM_DIR OUTPUT_SIDECAR` adds
`noteTrack.lanes`: one lane per WAV in `STEM_DIR` (any separation), each with
onsets `[time, rough pitch, strength]`, phrases, and `levelPerBeat` (A-weighted
dB). Onsets are spectral flux; pitch is a harmonic sum (often the chord root).
The song's sidecar is now `$D/instant-crush.notes.sidecar.json`, built from
six-stem Demucs stems (`/secondary/hyst-env/stems6/`). An older sidecar without
`noteTrack` still compiles and gives version 26 byte for byte.

**References found (validation only, never planner input).** A Songsterr tab
(14 tracks, full length) aligned to the recording; a midifind MIDI that turned
out to be derived from the same tab with a simplified chorus. Guitar and piano
tab tracks have capo 1. Assets and scratch scripts: `$D/tracker-scratch/`, see
the memory note `reference_dance_tracker_assets.md`.

**Measured against the tab** (note start within 50 ms): flux onsets on the
six-stem guitar stem 0.94; guitar and keys as one lane 0.92; keys via a stereo
"wide" split of `other` 0.85; voice (basic-pitch, filtered) 0.73; bass 0.67.
MuScriptor small (July 2026, CC BY-NC, gated): bass 0.95 and 0.93 right note;
guitar and keys on the `other` stem 0.95 and 0.67 right note; voice 0.84 with an
instrument hint; it gives no separate keys lane and constant velocity. Voice as
a pYIN curve: up/down 0.90, singing or silent 0.88, phrase stops weak. Not
solved: up/down of chord lines (0.3 to 0.6 by every method), the break solo's
line (under half its notes found), separate keys lane. Lane discovery by stereo
position separates simulated twin guitars at 35 % pan or more (0.91 to 0.97),
fails at 15 %. None of the MuScriptor, pYIN or stereo work is in the repo.

**Planner.** `compile_figures` ranks the instrument lanes per beat by level
(voice and drums do not compete; a challenger needs 3 dB for four beats,
backdated). On this song: guitar leads to 90.4 s, synths to 125.3, guitar to
188.8, the lead line to 212.7, synths after. Blind tests:
- Figures snapping to the leader's phrase starts, figures picked by its pitch
  step, accents from the second lane: lost. User: they follow the stabs but
  wobble up and down across the travel line. Deleted.
- Pulsed travel while the leader plays stabs (empty beats between its hits):
  user chose "surge just after each stab" over even travel and over "arrive on
  the stab". Now constant: pace 0.3 to 2.2 times even, decay 0.35 beat, the
  speed cap may be exceeded by half during a surge. Active only in the two
  choruses and the end; verses and break are unchanged.
`song-figures-27.html` is byte-identical to the chosen clip. Whole song: hand
speed median 0.34, p95 1.03, max 1.88 m/s; acceleration outside moments p95 5.6
m/s² (version 26: 1.4). That is a hardware and jitter risk the user has seen
only at 3:32 to 4:12.

**Open.** The `--flourish` knob (0 as before, 1 none, 2 soft) is still in the
code: user said all three have a part, per moment; the cause of the flick at
2:19 is a flourish placed on an arbitrary guitar note. Next agreed step: the
fluid half, for when the leader is a single flowing line (the break): size and
height follow its swell. User's unanswered point: the arm "over-focuses on
centre"; measured that verses sway about one fixed direction and the hand stays
0.31 to 0.55 m from the base axis. 131 CPU tests, clippy, fmt, `ensemble.cjs`,
tracker test pass.

### Versions 28–30: leader's swell, smoothed figure clock, voice lift — 2026-10-04

Branch `keys-decide`. All three were settled by side-by-sides with the user.

**Sidecar.** `scripts/dance_notes.py` now also writes `brightnessPerBeat` per
lane: the A-weighted spectral centroid as a MIDI pitch, 0 for a silent beat.
Old fields are unchanged; `$D/instant-crush.notes.sidecar.json` was regenerated.
A sidecar without the field compiles, without the swell.

**Version 28, swell of the leading lane (the "fluid half").** Measured on the
break: the solo's loudness is nearly flat (−27 to −23.5 dB over 187–204 s, then
fading to −38 dB by 212 s); its brightness carries the contour (89–98). Rule:
per beat, the leader's level and brightness about their medians over the
stretch that lane leads (3 dB and 4 semitones are full scale), faded out where
it plays stabs, smoothed with a bell one beat wide. Level scales the figure by
up to 35 %; brightness shifts hand elevation by up to 0.3. The user chose full
strength over half and none, blind on the break (3:00–3:40) and open on a verse
(2:05–2:45). There is no gate for "single flowing line": the rule runs wherever
the leader plays no stabs, verses included.

**Version 29, smoothed figure clock.** The user reported possible jitter or
micro-stutter. Measured: clips are 30 fps with no dropped or duplicate frames.
The motion did chatter: when the leader plays quick notes the surge retriggers
every second knot, so the hand's step alternated about 26 and 35 mm per knot
and the base and disc followed (163 knot-to-knot acceleration reversals of the
base over the song, mostly in the choruses). The joint follower was not the
cause; it reproduces its targets. Two first candidates (a run of quick notes
surges once; eased surge) shifted figure timing by 35–65 cm of hand position,
so the user could not compare them; deleted. Kept: a bell of two knots over the
figure clock. Hand within 1 cm of version 28; base reversals 163 → 1; hand
acceleration outside moments 5.8 → 1.7 m/s² p95. **The user saw no difference
by eye**; it is kept for the hardware only, against the "no difference means
delete" rule, and the user was told. So the jitter the user sees is something
else: candidates are the disc roll (still 81 reversals; its spin target is
faster than the roll limit, so it chases at full acceleration) and the 30 fps
recording. Smoothing the roll's direction signal changed almost nothing and was
deleted.

**Version 30, voice lift.** The user, on 4:07: the vocals are high and
important there, the arm should go a lot higher. Measured: the vocal lane's
rough pitch jumps from about 65 to 73 at 247.5 s and stays until about 262 s,
at the song's loudest vocal level; its brightness does not show it. Rule: per
beat, the median pitch of the vocal lane's notes above the song's median note
(2 semitones start it, 8 are full), smoothed with a bell two beats wide, adds
up to 0.65 to both elevation and extension. The user put the strength between
0.45 and 0.9 in a blind side-by-side on 3:52–4:32. Median hand height in
247–262 s: 0.39 → 0.61 m. It also lifts other high vocal stretches (165–185 s:
0.37 → 0.50 m), which the user has not reviewed.

**State.** `song-figures-30.html`. Whole song: hand speed median 0.34, p95 0.97,
max 2.25 m/s. 133 CPU tests, clippy, fmt, `ensemble.cjs`, tracker test pass.
An old sidecar no longer reproduces version 26 (the clock smoothing applies to
every sidecar). Still open: the `--flourish` knob, the roll chatter, the leader
change found at 188.8 s (the user hears 185), "over-focuses on centre".

### Version 31: flourishes soft where the leader plays a steady stream — 2026-10-04

Measured cause of the flick at 2:19: a flourish is the strongest onset of the
melodic stem per ~16 beats. In the choruses that is a stab of the leading
synth, a hit that stands out (9 of 23). In the verses, the break and the end
the leader plays a steady stream, every strum has the same strength, and the
flourish lands on an arbitrary one (14 of 23). Rule: where the stab weight of
the leading lane is under 0.5 at the flourish's beat, the flourish is slow and
soft (half strength, twice the window); among stabs it is as before. Blind
side-by-side on 2:05–2:45: the user called the sharp one "a bit too much" and
the soft one "ok"; "none" was not chosen. Peak hand acceleration at 2:19 falls
from 11.3 to 1.5 m/s². The `--flourish` knob and its config field are deleted.
`song-figures-31.html`; the choruses are unchanged from version 30. No test
covers the soft/sharp choice (the fixture has no flourish). Flourish poses are
still two fixed shapes alternating high and low.

### Version 32: sections travel round the base in alternating directions — 2026-10-04

The user's "over-focuses on centre" means: the rotation goes mostly one way.
Measured on version 31: the base netted 12.5 turns in one direction over the
song (turning that way 56 % of the time, the other 42 %), and every long
section turned the same way. Two candidates: the steady travel reverses each
section (3.6 net turns, 51 % / 47 %), or the whole section is mirrored, figures
included (1.0 net turn, 46 % / 50 %). On a blind 40 s clip (1:10–1:50) the user
was "genuinely unsure", declined a longer clip and asked for a middle ground.
Kept: the steady travel reverses each section, figures keep their own side.
This is the user's instruction, not a blind-test win. The choruses still all
turn the same way as each other (the sections between them reverse); that falls
out of the alternation on this song, it is not a rule. The `--travel` knob is
deleted. `song-figures-32.html`; 133 CPU tests, clippy, fmt, `ensemble.cjs`
pass. No review knobs remain in the code.

### Version 32 approved on a whole-song review — 2026-10-04

The user watched the whole song at version 32 (60 fps, on-screen clock,
`review-32-full-60fps.mp4`) and said: "I think it's all good". No jitter was
reported. The single-arm motion is accepted for now. Agreed order from here:
the hand object, then several arms with red zones. Open before the hand object
can be built: what the object is in numbers, and what the mirror aims at.

### Hand object, first step: where the disc throws the projector's light — 2026-10-04

The user restated the whole-project concept: several arms with "something with
mirrors" on the end, and a projector fires the visualizer (the Julia and
Mandelbulb fractals) onto them and the wall. So the light is the projector's
image. The object, the room layout and whether the mirrors aim are not decided.

Measured on version 32 with an **assumed** room (projector 3 m in front of the
arm at 1.2 m height, screen wall 1.5 m behind it, both mirror faces): the
reflection lands on the screen wall 43 % of the song, the floor 36 %, the
ceiling 12 %, side walls 8 %, back at the audience 1 %. The disc is nearly
edge-on to the beam 25 % of the time. A spot on the wall moves at 2.1 m/s
median, 14 m/s p95, and stays there 0.5 s median at a stretch. With the hand
where the dance puts it, some roll angle would put a usable spot on the screen
wall in 93 % of the song: the roll alone could steer it.

The preview (`ensemble.html`) now draws that room: a screen wall, a projector
mark, and the reflected patch on the wall or floor. Constants `PROJECTOR` and
`WALL` are assumptions. The planner is unchanged (still version 32). Clip
`mirror-light-32.mp4` (3:32–4:12) sent to the user. The disc rim is still not
in the zone check.

**Correction, same day: the projector is above the arm.** User: if the arm is
on the floor the projector is on the ceiling; if the arm is on a wall the
projector is perpendicular to that wall. So the projector faces the mounting
surface head-on and that surface is also the screen. The front projector and
back wall above were a wrong assumption and are gone from the preview.
Re-measured on version 32, projector 2.5 m straight above the base (4 m gives
the same shares): the disc faces the beam with 62 % of its area (median) and is
nearly edge-on 17 % of the song; the reflection falls back on the mounting
surface 60 % (within 1.5 m of the base 45 %), leaves sideways 18 %, upward
23 %; the beam's direction turns at 54°/s median, 373°/s p95. The roll alone
could always keep the disc facing the beam (never under 20 %, median 95 %).
The preview now puts the projector overhead, casts the arm's shadow from it,
and draws the reflection as a patch where it falls back on the surface and as a
beam where it leaves for the room. Height 2.5 m is assumed. Clip
`mirror-light-32b.mp4`. Not decided by the user: the object, the projector's
distance, where the audience is, whether the mirrors aim.

### Hand object "shards": a cluster of small mirrors — 2026-10-04

User on the overhead-projector clip: "a ray from mirror to reflection sometimes
appears"; after that is fixed "I think it's OK". Then asked for a new
implement: "a strange shape with mirrors all over, scattered".

- Ray: it was drawn only when the reflection left for the room. Now every lit
  mirror always has one thin ray, to its patch or 1.2 m out into the room.
- New hand object in the preview, the default: `SHARDS`, sixteen small round
  mirrors (1.6–3 cm radius) at 3.5–7 cm from the hand point, each tilted off
  the radial direction, one-sided. The layout is a fixed invented stand-in. It
  turns with the wrist roll like the disc did. Each mirror that faces the
  projector throws its own patch or ray. The disc remains as `?hand=disc` on
  the preview URL.
- Not modelled: one shard shading another, the arm blocking the beam, the
  image content. The planner and the rig are unchanged (version 32): the rig's
  last link still ends at a 6 cm disc radius and nothing of the hand object is
  in the zone check. Clips `shards-32.mp4` and `disc-32.mp4` (3:32–4:12).

**Shards, second form, same day.** User: "Shards is better, make it more like
a discoball, but not quite, not spherical, irregular a tad", then "non-convex
sort of". The preview's default hand is now a lumpy ball tiled with 84 small
square mirrors (about 1.5 to 1.9 cm across, each a little crooked): two unequal
lobes with a waist between them, one deep dent and one shallow, 3 to 7 cm from
the hand point (`radius`, `DENTS`, `SHARDS` in `ensemble.html`). Tiles follow
the surface, so the dents hold mirrors that face each other. About half the
tiles face the overhead projector at any time; each throws a small square
patch on the floor or a faint ray into the room. Not modelled: tiles shading
each other inside the dents, reflections between tiles. Clip
`mirrorball-32.mp4` (3:32–4:12). Planner and rig unchanged.

### Version 33: the implement is rig data and is in the zone check — 2026-10-04

User: the ball is good, make it lumpier; next "red-zones for the 3D shape of
the implement"; "want differing implements to be possible, generalization is
always good".

- `ensemble.rs`: `Rig` has an `implement` (`Implement { name, radius_m,
  mirrors }`, `Mirror { centre_m, normal, u, half_size_m, sides, both_faces }`,
  all in the tool frame: axis 0 along the last link, axis 1 the tool's facing
  at zero roll). Any set of flat mirrors is an implement; a `--rig` JSON file
  can carry its own. Built in: `Implement::mirror_ball()` (default) and
  `Implement::disc()`; the preview example takes `--implement ball|disc`. A rig
  file without the field loads with the default. `validate` refuses mirrors
  that are not unit, or that reach past `radius_m`.
- Zone and floor checks (`figures.rs`, `link_samples`): the hand point keeps
  the usual margin plus `radius_m` from every zone and the floor, in the
  solver, the follower's braking and the hard check. It is a bounding sphere,
  so it holds for any shape and any roll (the roll is driven outside the
  solver); it wastes room for a flat implement. Marked `ponytail:`.
- The ball is lumpier: 110 square tiles of 1.1 to 2 cm across, two lobes,
  ripples, four dents; bounding radius 8.0 cm.
- The preview draws whatever mirrors the rig carries (`data.rig.implement`);
  the hard-coded shapes and the `?hand=disc` switch are gone from
  `ensemble.html`.
- Effect on the dance: the hand used to dip to 7.9 cm above the floor (the old
  disc's rim would have been 1.9 cm off it). Now the lowest hand point is
  15.2 cm with the ball. The hand differs from version 32 by more than 2 cm
  for 0.8 s of the song, 7.3 cm at most; elsewhere it is the same.
`song-figures-33.html`, clip `mirrorball-33.mp4` (3:32–4:12). 134 CPU tests,
clippy, fmt, `ensemble.cjs` pass. Not done: implement against the arm's own
links, and anything between two arms.

### Version 34: several arms that keep clear of each other — 2026-10-04

User: "we need crosscheck with arms, red zone is a zone around arms to avoid
collision (tunable radius)"; six arms, concentric, symmetric, like a hexagon;
and the synchronized dancing itself (together, inverses, one by one, drop-outs,
pairs, complements) is "a different game", not this step.

- `figures.rs`: `compile_ensemble(json, config, rig, zones, arms, clearance_m)`
  with `ArmPlan { placement, mirrored }`; `compile_figures` is the one-arm case
  and its output is unchanged from version 33 (preview data identical). Every
  arm dances the same figures in its own frame (rotated by its yaw, optionally
  left-right mirrored).
- Cross-check (`Obstacles`): at each knot the arms are solved in order. Each
  sees the others' current poses as points (`body_samples`: the checked link
  points plus the base column) and keeps `clearance_m` plus the implements'
  radii from them, in the solver (which aims 3 cm wider), in the follower's
  braking (half the gap, since the other arm may be closing too) and in the
  hard check. Earlier arms have right of way. Fixed zones work as before.
- Preview example: `--ring N,R` (N arms on a circle of radius R, facing
  outward), `--mirror-odd` (every second arm mirrored), `--clearance M`
  (default 0.1). The camera backs off to hold the layout.
- Measured, hexagon of radius 0.9 m, on dense points along the played curves:
  unison never needs the check (closest implement surface 11.3 cm). With every
  second arm mirrored and clearance 0.10 m the closest is 9.5 cm; with 0.25 m,
  24.0 cm; with 0 m the implements overlap by 1.1 cm. So the played curve cuts
  up to about 1 cm inside the checked knots. Six arms compile in 12 s.
- Limits: a ring of 0.6 m (bases closer than one reach) fails with "cannot fit
  tangents": a blocked arm is stopped within one knot and the quintic fit
  cannot honour the rig limits (the known `fit_tangents` cascade). 0.7 m and up
  work. The implement is not checked against its own arm. Priority by arm order
  is arbitrary. A test covers two arms side by side.
- Not done, by the user's decision: any ensemble choreography. `--mirror-odd`
  exists only to make arms meet so the check can be seen.
`song-figures-34.html` (one arm), `hexagon-34-unison.{html,mp4}` and
`hexagon-34-mirrored.{html,mp4}` (3:32–4:12). 135 CPU tests, clippy, fmt,
`ensemble.cjs` pass.

### Version 35: the ensemble picks its own formations; forward is the centre — 2026-10-05

User: the ensemble "should be able to do both mirrored and unison and all of
the others, should decide itself (canon for instance)"; and in a ring "there is
a rough forward for the arms, towards the center ... it should be 360 but
center is the center".

- Forward: `--ring N,R` now faces every arm toward the ring's centre (yaw =
  its angle + 180°). Bearings are in the arm's frame, 0 = forward. Figures
  still travel all the way round the base.
- `Formation` (`figures.rs`): Unison, Mirrored (every second arm the mirror
  image about its forward line), Canon (each arm one beat after the last),
  Pairs (opposite arms pair up, pairs take turns of eight beats), OneByOne
  (four beats each round the ring), DropOut (every second arm rests).
  `Formation::part` gives each arm a side, a delay and dancing or resting.
- Chosen per run from its class and how often that class has come round:
  interlocked: Unison, Mirrored alternating; vocal-led: Canon, Mirrored, Pairs
  in turn; percussive-open: OneByOne, Canon; bass-led: Mirrored; silence:
  Unison; anything else: DropOut. A run under eight beats keeps the formation
  before it. **This table is an agent's first guess, not reviewed.** The
  choice is appended to each cue's reason (" · ensemble Canon").
- Each arm's hand path is built from the single-arm path: sampled at its own
  delayed time, bearing times its side, blended toward a rest pose (drawn in,
  low, facing forward) when it sits out. Delay and rest weights are eased with
  bells (16 and 6 knots) and the bearing with one of 5 knots, counted from the
  last bearing so a change of side swings the nearer way. One arm alone skips
  all of this and is identical to version 34.
- Cells: at 1.1 m a mirrored chorus had neighbours reach for the same spot and
  the cross-check stopped them (median hand speed 0.25 against 0.48 m/s when
  they cannot meet). Now each hand stays within its own cell of floor: radius
  = half the distance to the nearest arm, less the clearance and the implement
  (0.42 m on a 1.1 m hexagon), easing into the edge. The mirrored chorus runs
  at 0.41 m/s. A ring too tight for an arm to rest in its cell is refused
  (0.9 m hexagon: 0.32 m cell, needs 0.37 m). The cross-check stays as the
  safety net; closest approach on the song is 9.8 cm at 10 cm clearance.
- `--mirror-odd` is gone (the Mirrored formation covers it); `ArmPlan.mirrored`
  remains as a per-arm fixed flip.
On this song (hexagon 1.1 m): intro OneByOne, verse 1 Canon, chorus 1 Unison,
verse 2 Pairs, break OneByOne, vocal return Mirrored, chorus 2 Mirrored, then
Unison, Canon, Mirrored, Mirrored (bass-led), DropOut, still. Weak points seen
in the numbers: OneByOne and Pairs leave most arms resting for long (26 s in
the intro, 40 s in verse 2); hand speed peaks at 2.7 m/s at some formation
changes; arms still have right of way by index. `hexagon-35.html`,
`hexagon-35-full.mp4`. 136 CPU tests, clippy, fmt, `ensemble.cjs` pass.

### Version 36: arms share the floor; everyone dances — 2026-10-05

User on the whole-song video of version 35: "Not synchronized enough, too low
energy maybe? They are also too far apart, dynamic red zones overlapping is
what makes it WOW level of technical difficulty."

- Closer: the review hexagon is 0.8 m (was 1.1 m), so each arm reaches its
  neighbours' bases. The per-arm floor cells of version 35 are deleted.
  Measured on the song: a hand is inside a neighbour's reach 77 % of arm-time
  and nearer a neighbour's base than its own 14 %; closest approach of an
  implement to another arm or implement 10.0 cm at 10 cm clearance; every arm
  at full speed, the six alike (nothing blocked).
- Why it does not collide: formations that are the same for every arm, turned
  by the ring's angle, let each arm move through the space its neighbour just
  left. Two limits, the same for every arm so the picture stays symmetric
  (`shared` in `compile_ensemble`): no hand enters a circle at the layout's
  centre where all hands would meet (radius (clearance/2 + implement + 2 cm) /
  sin(π/N), 30 cm for six); and while the formation is Mirrored each hand stays
  on its own side of the line half way to its neighbours. The cross-check is
  the safety net under both.
- Arms no longer start at the rig's neutral pose in an ensemble (six neutral
  hands meet in the middle of a tight ring): each starts at its first target,
  solved on its own. One arm alone still starts at neutral, output unchanged.
- More together: OneByOne is deleted. Table now: interlocked, bass-led,
  silence: Unison; vocal-led: Canon, Mirrored alternating; percussive-open:
  Canon, Unison alternating; sparse: DropOut; anything else: Pairs. Canon is
  half a beat per arm (a ripple of three beats round six arms). **Still an
  agent's table, not reviewed.**
- On this song: intro Canon, verse 1 Canon, chorus 1 Unison, link Mirrored
  then Unison, verse 2 Canon, pre-break Mirrored, break Canon, vocal return
  Canon, chorus 2 Unison to the end section, fade DropOut.
- Open: hexagon size is still the agent's choice; "complements" undefined;
  right of way by arm index; canon breaks the symmetry, so its safety rests on
  the cross-check (it held on this song).
`hexagon-36.html`, `hexagon-36-full.mp4`. 136 CPU tests, clippy, fmt,
`ensemble.cjs` pass; one arm alone is identical to version 34.

### Version 37: canon by a fraction of the move; ripple out and back — 2026-10-05

User: a different one-by-one, a canon where arms "just start delayed, not for
the duration of the whole move, but a fraction of it" (a 3 s move delayed
0.5–1 s); circular (1-2-3-4-5-6-1-2-3…) or both directions (one starts, then
the two next to it, then the next two, then the last one, then backwards).

- `Formation::part` now gets the current move (figure) index and its length.
  Step = move length / max(6, arms): a sixth of the move, 0.5 s for a 3 s move.
  - Canon: delay = arm index × step; the next move starts again on arm 1.
  - Ripple (new): delay = (steps round the ring from arm 1, either way) ×
    step; on every second move the order is reversed, so it starts on the
    opposite arm and comes back.
- Table: vocal-led: Canon, Ripple, Mirrored in turn; percussive-open: Ripple,
  Canon; the rest as in version 36. On this song: intro Ripple, verse 1 Canon,
  chorus 1 Unison, link Ripple then Canon, verse 2 Mirrored, pre-break Canon,
  break Ripple, vocal return Ripple, chorus 2 Unison onward, fade DropOut.
- Two defects the larger delays exposed, both fixed:
  1. The follower's braking near another arm limited motion in every
     direction, so two arms that had met could only creep apart. It now limits
     only motion that shrinks the gap (`arm_room` before and after); zones are
     as before, so one arm alone is unchanged.
  2. Neighbours out of step reach for the same place at different times; the
     cross-check then held them (four arms stood still for 8 s in one canon).
     The "own side of the line half way to the neighbours" limit, which
     version 36 applied only to Mirrored, now applies to every formation but
     Unison, from two beats before to two after, with 5 cm of room beyond the
     clearance so the solver is not leaning on the hard check.
- Consequence, told to the user: reaches overlap in space only in Unison. A
  hand is inside a neighbour's reach 77 % of arm-time as before, but nearer a
  neighbour's base than its own 6 % (14 % in version 36). Overlap during
  canon would need the timing planned so paths interleave.
- Measured, hexagon 0.8 m: no section with still or uneven arms; closest
  approach 10.0 cm at 10 cm clearance; hand speed p95 0.88 m/s per arm.
`hexagon-37.html`, `hexagon-37-full.mp4`. 136 CPU tests, clippy, fmt,
`ensemble.cjs` pass; one arm alone identical to version 34.

### Version 38: the ripple's stall and dash; two more ensemble defects — 2026-10-05

User on the version 37 video: at 3:08 to 3:16 the orange arm on the right
"stutters/breaks formation", maybe a wrong canon or a jitter bug.

Measured: that is the Ripple of the break (185–204 s). The orange arm is arm 0,
where the ripple starts; its delay flipped between none and three steps at
every move because the order reverses. Applied as a jump eased by a bell, that
made it stand still about a second (hand speed 0.00 at 193–194.5 s) and then
race (1.1 m/s at 190 s); the opposite arm did the reverse. No arm was within
30 cm; it was not the cross-check.

- Delays now run evenly from one move's value to the next across the move
  (`part` in `compile_ensemble`): an arm starts each move on its turn and plays
  it a little slower or faster. No stall.
- Ripple's step is half the canon's (a twelfth of the move): reversing the
  order then changes an end arm's pace by a quarter, not a half.
- The "own side of the line" limit squeezed the whole sector with a tanh, which
  bent hand paths over their own base, into the shoulder's limit and out with a
  kick. It now leaves the inner 70 % of the sector untouched.
- In the mirrored verse arms were stopped dead at the line (elbows reach past
  the hand). The margin there is 12 cm beyond clearance and implement; the
  centre circle keeps its 2 cm.
Hexagon 0.8 m, whole song: arm 0 has no stall in 186–198 s; accelerations over
9 m/s² across the six arms 74 → 57 (about five per arm are the single arm's
own chorus accents); standstills over 0.3 s inside the song 3–5 → 1–4 per arm;
closest approach 13.4 cm. Left: arm 0 still has one 11 m/s² kick at 187.9 s
(shoulder at its limit as the hand passes over the base; the single arm has a
4.9 m/s² version); arms 4 and 5 have three or four short standstills; cause
not looked for. `hexagon-38.html`, `hexagon-38-full.mp4`. 136 CPU tests,
clippy, fmt, `ensemble.cjs` pass; one arm alone identical to version 34.

### Version 39: draw order across arms; canon delays on the beat — 2026-10-05

User on the version 38 video: "the orange one is sometimes rendered below the
one above it, layering issue"; and "doesn't follow music enough, it's like an
abstraction, but it needs to be more on point to be better I think".

- Preview: each arm used to be painted whole, in arm order, so a far arm could
  cover a near one. Every arm's pieces (and its pedestal) now go into one list
  drawn far to near. Planner data for one arm is unchanged from version 34
  (the exported file differs only in the page's script).
- Canon step is a whole number of beats (the move's length / 6, rounded, at
  least 1); Ripple's is half a beat. A late arm now lands on the beat.
- "On point" is **not answered**. Four readings were put to the user (accents
  together; arms joining and leaving with how full the music is; one arm
  leading the solo or the voice; the single-arm figures themselves being too
  loose) with a request for two or three timestamps and what the six arms
  should do there, as the 4:07 note did for the voice. Do not build ensemble
  behaviour for this before the user answers.
`hexagon-39.html`, `hexagon-39-full.mp4`. 136 CPU tests, clippy, fmt,
`ensemble.cjs` pass.

### Version 39 accepted — 2026-10-05

The user watched the version 39 whole-song video and said: "It's good now".
That followed the layering fix and the beat-aligned delays. They did not say
which reading of "more on point" they had meant, so treat that question as
closed by this verdict but not as answered: do not add ensemble behaviour for
it unless they raise it again. The six-arm ensemble on a 0.8 m hexagon is
accepted for now as it stands in version 39.

### Handover — 2026-10-05

Asked what comes next, the user chose overlap outside unison ("1. is most
important, we want to be able to make red zones so that it doesn't hit
equipment or whatever, it's supposed to be generalized right?") and asked for
a handoff to a fresh session. `docs/DANCE_RESTART_PROMPT.md` is rewritten for
the ensemble and states that task in two parts: arms inside each other's reach
in every formation, and red zones as a general tool against equipment. Nothing
of either is started. The measuring and recording scripts of this session are
saved outside git in `$D/tracker-scratch/ensemble/`. A hexagon export from the
current tree is byte-identical to `hexagon-39.html`. Tree clean, branch pushed.

### Version 40: out-of-step arms share space — 2026-10-05

Task 1 of the restart prompt (overlap outside unison). Not yet reviewed by the
user; `hexagon-40-full.mp4` was sent.

Measured first, on the 0.8 m hexagon. With the "own sector" limit switched off
entirely, canon and ripple mostly work: hands go past half way to a neighbour
14.6 % (canon) and 6.7 % (ripple) of arm-time, against 15.8 % in unison. The
cost was local: arms stood still 9 % of the canon, and the mirrored verse
jammed (34 % still, then all six stopped from 175 to 185 s). So out-of-step
arms rarely want the same place; the version 37 limit was on all the time to
cover a few seconds.

- Rule (`apart` in `compile_ensemble`): before the real solve, each arm is
  posed alone along its unlimited path at every second knot. Where two arms'
  checked points come within the clearance (and the formation is not Unison),
  every hand keeps to its own sector from half a beat before to half a beat
  after, eased as before. Elsewhere no sector limit. The limit is still the
  same for all arms at once, so the picture stays symmetric. The centre circle
  is unchanged. `shared` now takes the limit's weight; the per-formation flag
  is gone.
- Margin and window were swept. Wider (10 cm, two beats): less shared space,
  no fewer stalls. Narrower than the clearance: the cross-check stops arms
  (1.1 % still in canon). Kept: the clearance itself, half a beat.
- Limit active, share of each run: ripples 0 %; canons 12 %, 1 %, 1 %, 14 %;
  mirrored 68 % and 97 %.

| per formation | past half way, v39 | v40 | still, v39 | v40 |
|---|---|---|---|---|
| Unison | 15.5 % | 15.7 % | 1.4 % | 1.4 % |
| Ripple | 0 % | 6.7 % | 0.1 % | 0.1 % |
| Canon | 0 % | 9.0 % | 1.4 % | 0.1 % |
| Mirrored | 0 % | 0 % | 0.2 % | 0.1 % |

Whole song: hands nearer a neighbour's base than their own 6 % → 10 % of
arm-time; kicks over 9 m/s² 59 → 44; standstills over 0.3 s per arm 1–2 → 0
(arm 5: 1); closest implement surface to another arm 13.4 → 13.0 cm at 10 cm
clearance; closest hand centres 34 → 29 cm. One arm alone is byte-identical to
the tree before. Six arms compile in about 16 s (was 12 s): the lone posing is
the extra.

**Mirrored cannot share space as it is.** Mirror neighbours are images of each
other in the plane between them, so two arms that cross it meet in it, at the
same moment. Overlap there needs a different formation (a mirror with a delay,
or one arm passing over the other); that is an artistic choice, put to the
user, not built.

**Not what the restart prompt asked for in one respect.** It said overlap
"needs paths whose timing interleaves, not a clamp". Version 40 does not
retime anything: it found that the existing canon and ripple timing already
interleaves most of the time, and keeps the old clamp for the seconds where it
does not. Canon is still limited 12–14 % of its two long runs. Retiming those
moments (a different step for that move) is not tried.

Tests: `arms_out_of_step_share_space_without_stopping` (a six-arm ripple:
hands cross half way, no arm stands, implements stay apart; it fails with the
limit always on) and `every_arm_of_an_ensemble_stays_out_of_a_red_zone` (two
arms against a box; this closes the test gap of task 2). 138 CPU tests, clippy,
fmt, `ensemble.cjs` pass.

Task 2 (red zones against equipment) is otherwise not started: the user has
not said what the equipment is. Question put to them: which things (projector
stand, speakers, a wall, people's walkway), so shapes are not invented.

New helpers in `$D/tracker-scratch/ensemble/`: `byform.py FILE` (per formation:
past half way, speed, still, kicks, closest), `when.py FILE` (clock times where
two or more out-of-step hands are past half way).

### Version 41: a canon only for short runs — 2026-10-05

User on version 40, after asking how long the canon sections are (61 s in
verse 1): "too long at times, too unsynchronized if cannon or whatever stays
too long, ripple is ok, I think its cuz it breaks symmetry?" They also asked
whether "inverse pairs" exist (arms 1, 3, 5 do X, arms 2, 4, 6 the inverse
positions). Answer given: Mirrored is that for left and right only (2:14 to
2:57); no formation inverts high and low or in and out.

- A run that would be a Canon and is longer than sixteen beats is a Ripple
  (`compile_ensemble`, formation choice). The threshold is the agent's guess.
  On this song: verse 1 (0:29–1:30) and 4:24–4:41 ripple; two canons remain,
  2:09–2:14 and 2:57–3:05, one and two moves long. Ripple now runs 0:03–1:30
  without a break (87 s), not reviewed.
- Measured: ripple hands past half way to a neighbour 12.0 % of arm-time (the
  limit of version 40 seldom fires in a ripple); whole song 11.4 %; kicks 44 →
  40; no standstill over 0.3 s on any arm; closest implement surface 13.4 cm.
  One arm alone identical.
`hexagon-41.html`, `hexagon-41-full.mp4` (sent, not yet reviewed). 138 CPU
tests, clippy, fmt, `ensemble.cjs` pass. Open with the user: whether an
"inverse" formation in two groups of three is wanted and what inverse means
(high/low, in/out, or a group one step late); Mirrored without overlap; red
zone equipment.

### Version 42: unison and mirror for sections; canon and ripple as flourishes — 2026-10-05

Version 41 was never reviewed (its video was not sent). The user, before
seeing it: "the best looking one is sync. I also like mirror, for me cannon
was more of a flurish move, same with ripple"; then: "Cannon and ripple work
well especially with 'linear' movements (where the joints are co-linear with
the centerpoint), but thats just an idea".

- Sections are Unison or Mirrored only. Table: interlocked, bass-led, silence:
  Unison; vocal-led: Mirrored, Unison in turn; percussive-open: Unison,
  Mirrored in turn; sparse: DropOut; else Pairs. Still an agent's table. The
  sixteen-beat canon rule of version 41 is deleted.
- Flourish (`accents` in `compile_ensemble`): the move that holds a melodic
  flourish moment is passed round the ring, as a ripple and a canon in turn.
  Only the delay changes; arms keep the run's sides. Conditions: the move is
  six beats or longer and sweeps under 120° round the base.
- Linear: while a move is passed round, each arm turns to face straight in or
  straight out (the nearer at the middle of the move) and keeps only the
  rise, fall, reach and draw-in. This is the agent's reading of the user's
  "co-linear with the centerpoint". Without the 120° condition the wide
  moves (circle, arc, eight) lurched: 64 kicks, arms 9.7 cm apart, so they
  are never passed round.
- The delay still runs evenly from one move's value to the next (version 38),
  so arms drift out of step over the move before a flourish and close up
  during it. Whether that reads as a flourish is for the user.
- The "would meet" limit of version 40 now applies in every formation; the
  Unison exemption is dropped (the choruses kept their kicks and closest
  approach, so the limit seems not to fire there; not checked directly).
- On this song: Unison 0:00–0:29, Mirrored 0:29–1:30, Unison 1:30–2:09,
  Mirrored 2:09–2:57, Unison 2:57–3:23, Mirrored 3:23–3:32, Unison 3:32–4:24,
  Mirrored 4:24–4:41, Unison 4:41–5:23, DropOut, still. Passed round: 0:20
  (eight, canon), 0:37, 0:46, 0:55 (reach; ripple, canon, ripple), 1:17 (sway,
  ripple), 2:27 and 3:09 (sway, canon), 4:33 (reach, ripple), 5:10 (rise,
  canon), 5:23 (sway in the drop-out). None in the two choruses' circles.
- Measured: kicks over 9 m/s² 47; closest implement surface 13.4 cm; hands
  past half way to a neighbour 12.2 % of arm-time in Unison, 0 % in Mirrored
  (now 135 s of the song), 7.0 % overall. Standstills: only 0:49–0:50, 0.3 to
  0.4 s on five arms, where the linear reach turns round. One arm alone
  identical.
- Tests: the out-of-step test of version 40 became
  `mirrored_arms_keep_apart_without_stopping`; the six-arm unison test now
  also requires a hand past half way. **No test covers a flourish or the
  linear turn** (the fixture has no flourish moment). 138 CPU tests, clippy,
  fmt, `ensemble.cjs` pass.
`hexagon-42.html`, `hexagon-42-full.mp4` (sent, not yet reviewed). New helpers
in `$D/tracker-scratch/ensemble/`: `runs.py` (formation runs and their moves),
`accents.py` (moves passed round), `still.py` (standstills by clock time).

### Version 43 and a verse side-by-side pending — 2026-10-05

User on version 42: "They have a lot of 'free time' now like 1:59-2:03, they
just sortof hang around doing nothing. They also have moments where they just
snap back to center, as if theyre 'resetting'. They follow music less now that
this is all here. We could maybe increase what we did for it to follow the
stabs?"

Measured:
- The choruses of version 42 are identical to version 39. At 1:59–2:03 the
  chorus ends on gather and rise (hands 27–29 cm from their bases, 0.2 m/s),
  as it did in version 39; then the verse followed as a ripple, now it is in
  step.
- The "linear" turn of version 42 (the agent's reading of the user's idea)
  held arms on the line to the centre for a whole move, nearly still. Deleted.
  Idle time (six-hand mean under 0.15 m/s for 1.5 s or more) 35 → 32 s only,
  so it was a small part.
- Likely main cause, not confirmed by the user: the verse vocabulary. "reach"
  goes out and tucks back in every eight beats and "sway" is slow; six arms in
  step or mirrored do that together, which reads as a reset and a wait. In
  version 39 the canon and ripple delays hid it. Hands slow at the centre
  circle: 2 s of the song, not the cause.
- A stronger surge after stabs (1.7 and 2.5 times) changed the chorus hand
  speed spread little (p90/p10 6.1 → 7.5; the speed cap and the clock's catch-up
  bound it) and brought stalls (0.9 % → 4 % in Unison) and kicks (44 → 67).
  Not adopted; knob removed.

Version 43 = version 42 without the linear turn (`hexagon-43.html`; its video
was recorded but not sent). Kicks 44, closest 13.1 cm, one pause of 0.3–0.7 s
at 0:49.

**Pending review, key unread:** `blind-verse-side-by-side.mp4` (0:29–1:09, A
and B on top, C below, clock) with key `blind-verse-key.json`. The verse
(vocal-led) as mirrored, ripple or unison; same single-arm dance in all three.
Measured, whole song with every vocal-led run in that formation:

| verse as | idle | hands past half way, verse formation | kicks |
|---|---|---|---|
| mirrored | 32 s | 0 % | 44 |
| ripple | 19 s | 16.1 % | 38 |
| unison | 21 s | 14.8 % | 43 |

**A review knob is in the tree until the verdict:** environment variable
`HYST_VERSE=mirrored|ripple|unison` in the formation table of
`compile_ensemble`. Unset, the table is version 43's. On the verdict: make the
winner the table's entry, delete the variable, re-export, and compare against
`hexagon-43.html` only if mirrored wins. Not answered either way by this test:
what "follow the music" should look like for six arms; the user was asked.
138 CPU tests, clippy, fmt, `ensemble.cjs` pass. New helpers in
`$D/tracker-scratch/ensemble/`: `idle.py`, `wall.py`, `turn.py`, `pulse.py`,
`cmp.py`, `verse.sh`.

### Version 44: verses in unison — 2026-10-05

Verdict on the verse side-by-side: "Genuinely dont know, I think B is the worst
maybe? Unsure." B was mirrored (key: A ripple, B mirrored, C unison); the user
asked whether B had the most idle time, so the key was read and the test is
over. It supports "mirrored is worst for verses" only weakly and does not
separate ripple from unison. The user accepted the agent's recommendation of
unison (numbers near equal; the user had said ripple is a flourish).

Changes to the formation table of `compile_ensemble`:
- vocal-led is Unison; the `HYST_VERSE` variable is deleted.
- percussive-open alternates starting with Mirrored (was Unison first). The
  agent's choice, not asked of the user: with unison verses the old order left
  4.6 s of mirror in the whole song, and the user likes the mirror. One token
  to revert.

Measured, whole song (`hexagon-44.html`, `hexagon-44-full.mp4`):

| | version 43 | version 44 |
|---|---|---|
| Unison / Mirrored | 196 s / 135 s | 286 s / 45 s (0:03–0:29, 3:05–3:23) |
| idle | 32 s | 20 s |
| hands past half way, all | 7.4 % | 13.3 % |
| stalled | 1.7 % | 1.4 % |
| kicks | 44 | 45 |
| closest implement gap | 13.1 cm | 13.0 cm |

The mirrored test's fixture is now drums without voice (`fixture(0.1, 0.2)`).
138 CPU tests, clippy, fmt pass. Not reviewed by the user. Not answered: the
"snap back to centre" (no clock times given) and whether the remaining 20 s of
idle needs the verse moves changed. `tmp-verse-*.html` and `tmp-surge-*.html`
in the output directory are spent and may be deleted.

### Second song: "Five Years" (Bowie) — 2026-10-05

The user accepted version 44 ("Its nice now") and asked for a totally
different song. Source `~/Downloads/Five_Years_2012_Remaster.wav` (4:44,
48 kHz). Nothing in the planner was changed for it. Not yet reviewed.

What broke, in order:
1. `dance_structure.py` crashed when the stem folder had no
   `separation.json`. Fixed (committed).
2. **The fixed beat grid does not hold for a live drummer.** The song is in a
   triple feel (pulse about 1.16 s, three subdivisions of about 0.386 s) and
   speeds up 6.5 % from start to end. `analyze.ts` reported 114 bpm;
   `dance_memory.py`'s single period and phase put measured onsets a median
   134 ms from the grid (chance level; Instant Crush 5 ms). A steady grid and
   the real beats differ by up to 2.3 s.
3. On that wrong grid the planner failed outright: "cannot fit tangents
   segment 4280 channel 0 … accel 71110/8000". **Not investigated**; reproduce
   with `five-years.notes.sidecar.json`.

Workaround, all outside the repo (`$D/tracker-scratch/newsong/`):
`beatmap.py` tracks the subdivisions on the drum stem with librosa (basic-pitch
environment), smooths them and finds the pulse phase (drum strength by
subdivision mod 3: 4.2 / 1.2 / 2.1, the same phase in every sixth of the song,
so no slips; strong drum onsets a median 26 ms from a subdivision). `warp.py`
resamples the mix and all stems so the subdivisions are steady (pitch moves
with tempo, under half a semitone) and writes `five-years.tempomap.json`.
`song2.sh` runs the usual pipeline on the warped audio (slug
`five-years-steady`), with the sidecar's beats replaced by the steady grid.
The dance beat is 1.5 subdivisions (0.58 s, 103.5 bpm): two beats per pulse, so
an eight-beat move is one bar of four pulses and the pace matches what the
planner was tuned on. The agent's choice. Mix onsets are then a median 42 ms
from the grid and the structure pass calls the grid reliable.
`record-ensemble.cjs` gained `HYST_TEMPO_MAP=file.json`: it draws the score at
the mapped time, so the video is on the real beats. **The interactive HTML has
no tempo map** and drifts up to 2.3 s against its audio; use the video.

Result (`five-years-hexagon.html`, `five-years-hexagon-full.mp4`, 283.7 s):

| formation | seconds | median hand speed | stalled |
|---|---|---|---|
| Unison | 193.5 | 0.18 m/s | 5.9 % |
| DropOut | 57.5 | 0.02 m/s | 49.6 % |
| Pairs | 22.2 | 0.04 m/s | 47.6 % |
| Mirrored | 10.5 | 0.18 m/s | 1.0 % |

Kicks 24, closest implement gap 13.9 cm. Runs: still to 0:09; sparse/textural
(DropOut, Pairs) for most of 0:09–2:13 with bass-led unison between; unison
2:13–4:19 (vocal-led, then interlocked); mirrored 4:19–4:29; drop-out and
still to the end. So for the first two minutes most arms rest or barely move:
the class thresholds were set on Instant Crush and read the quiet opening
(voice, piano, drums) as "sparse", and sparse → DropOut, textural → Pairs are
the two rest-heavy rows left in the table. Whether that reads as a build or as
the idleness the user dislikes is for the user. Hand speed overall is half of
Instant Crush's (0.15 against 0.29 m/s).

If songs with a live tempo are to be supported properly: the tempo map belongs
in the sidecar and in score playback (page, `ChoreographyOutput`), and the
beat tracker in `scripts/`. Not built; waits for the user's verdict.

### Version 45: the planner meets a quiet, dynamic song — 2026-10-05

The user on the first "Five Years" video (version 44 planner):
- "The arms only start moving at 0:15, then 3 of them flick, then they stop
  again for a little while"
- "0:45 is REALLY jerky, too too fast, as if it doesnt even know the
  tempo/energy/emotion of the song, like its raving"
- "1:31-1:34 is EXTREMELY jerky, especially the lowest arm at the end, the
  spin afterwards is also WAAAY to fast"
- "2:22 to 2:25 is almost no movement"
- "most of the song says `bass-led` even though it isnt, at least it catches
  `vocal led` well, but if its `vocal led` for long enough it seems to get a
  bit 'boring'?"

Measured causes (video clock; `look5.py`, `acts.py`, `classes.py` in
`tracker-scratch/newsong/`):
- 0:15, 0:45, 1:31: each a **flourish in its sharp form** (hand 0.7–1.1 m/s,
  acceleration 15–18 m/s²). The planner chose sharp wherever the lead lane
  plays separated notes, whatever the loudness. 0:15 was danced by three arms
  (DropOut); the "spin" at 1:34 was three arms swinging to their rest pose at
  187°/s as a DropOut run began.
- 2:22–2:25: hands at 0.04–0.07 m/s; partly the stab surge idling between
  sparse stabs. Now 0.09–0.23 m/s; still the slowest spot, cause not isolated.
- Labels: `wholeTrackActivity` is each stem against its own loudest. The voice
  goes from soft to screaming, so the verses read as voiceless and the steady
  bass won, though the voice carried 40–55 % of the power and the bass under
  20 %. The climax (2:36–4:18) was vocal-led (reach, sway for 107 s) because
  its bass is buried.

Changes (`figures.rs`, `director.rs`):
1. `intensity(t)`: stem power summed, mean over ±4 beats, against half the
   song's 90th percentile, capped at 1. Below 0.75 a flourish is soft; arrival
   strength and the surge's depth are multiplied by it. Instant Crush is at 1
   nearly throughout (verses 0.55–0.66 of the 90th percentile, choruses 0.8).
2. `character` takes the voice's share of power and the loudness: sung =
   activity over 0.3 or share over 0.14; sung and louder than 0.7 of the 90th
   percentile is "interlocked". **Fragile by construction:** a song with flat
   dynamics would make every sung passage interlocked; thresholds sit between
   Instant Crush's verse (0.66) and chorus (0.73).
3. `Formation::Pairs` and `DropOut` deleted; every class but percussive-open
   is Unison. `part` still returns a dancing flag, now always 1; the resting
   pose code behind it is unused and could go.
4. A vocal-led or interlocked run plays the percussive-open or bass-led phrase
   once after about 128 beats of its own, and again. At 64 beats it changed
   Instant Crush's verses, and the different heading into the first chorus
   brought whole-ensemble kicks (45 → 64), so 128, which leaves Instant Crush's
   verses and all but its last chorus alone. On "Five Years" this gives one
   contrast in the climax; the boredom fix there is mostly the class change.
5. A run under 24 beats (was 8) keeps the formation before it: the ten-second
   mirrored passage at 4:19 entered from a turning chorus, neighbours met,
   braked at 20 m/s² and stood for two seconds. **A dodge, not a fix:** entering
   Mirrored from a wide heading is still unsafe for longer runs.

Measured:

| | Five Years, 44 | Five Years, 45 | Instant Crush, 44 | Instant Crush, 45 |
|---|---|---|---|---|
| arms resting (DropOut, Pairs) | 80 s | 0 | 9 s | 0 |
| kicks | 24 | 14 | 45 | 41 |
| peak hand acceleration | 22.8 m/s² | 11.7 | 23.0 | 23.0 |
| fastest base turn | 199°/s | 150 | 190 | 188 |
| median hand speed | 0.15 m/s | 0.21 | 0.29 | 0.27 |
| idle | n/a | n/a | 20 s | 19 s |
| closest implement gap | 13.9 cm | 13.9 | 13.0 | 12.8 |

"Five Years" classes now: sparse 0:09–0:30, bass-led to 0:40, vocal-led
0:40–1:35, a patchwork of sparse, bass-led, vocal-led and textural 1:35–2:36
(runs of 3–15 s, each with an arrival; **not fixed**), interlocked 2:36–4:18.
Instant Crush's classes are the same but for one 3 s vocal-led blip inside the
last chorus that merged.

Files: `hexagon-45.html`, `hexagon-45-full.mp4`, `five-years-hexagon.html`,
`five-years-hexagon-full.mp4` (the version 44 video kept as
`five-years-hexagon-44-full.mp4`). 139 CPU tests (one new, for the class
rule; the test fixture's stem levels now follow their activity), clippy, fmt.
Not reviewed. Still open from before: the planner's "cannot fit tangents"
failure on a wrong beat grid; the tempo map outside the repo.

### Version 46: a third song, classes by share of the sound — 2026-10-05

Version 45 was never shown to the user (its videos were recording when the
third song arrived); 46 replaces it and its files were deleted.

Third song: `~/Downloads/Justice_-_Presence_Official_Audio.wav` (4:31,
instrumental, steady 130.0 bpm), slug `presence`, usual pipeline (`song.sh`).
- **Grid 45 ms late.** `analyze.ts`'s causal beat tracker lags and
  `dance_memory.py` fits its grid to those beats: strong drum onsets fell an
  eighth of a beat before the grid through the whole song. `regrid.py` (scratch,
  librosa) refits period and phase to strong drum onsets (0.46160 s, drum hits a
  median 2 ms from a beat, 99 % within 30 ms) and replaces the sidecar's beats;
  `songtail.sh` reruns the later steps. Mix onsets against the grid: median
  46 → 9 ms. Instant Crush was not rechecked this way (its mix onsets sit 5 ms
  from its grid). **Belongs in `dance_memory.py`**; not moved there.
- **Phantom voice.** The voice stem holds under 2 % of the power but peaks
  against itself, so two passages were vocal-led.
- **Drum-led intro missed.** Drums carry 40–75 % of the power for 70 s at an
  activity of 0.15–0.16, under the 0.17 mark: "textural", one slow sway.

Changes to version 45:
- `character` takes every stem's share of mean power (mean of squares; the
  mean level squared under-counts drums). Sung = activity over 0.3 with a
  share over 0.04, or a share over 0.14. Percussive-open = drum activity over
  0.17 or drum share over 0.4, with no voice by activity or by share.
- Contrast phrases for all four main classes (vocal-led ↔ percussive-open,
  interlocked ↔ bass-led), still after about 128 beats.

Classes now (video clock):
- Instant Crush: as version 44 but 2:54–2:57 is percussive-open (was
  textural) and the 3 s vocal-led blip in the last chorus merged.
- Five Years: still to 0:09, percussive-open (drums alone) to 0:19, vocal-led
  0:19–1:35 and 1:44–2:36 (sparse and bass-led for 9 s between), interlocked
  2:36–4:18, percussive-open (drums alone) to 4:38. The patchwork of version
  45 is gone.
- Presence: percussive-open 0:00–1:10 (Mirrored), textural to 1:32, bass-led
  1:32–2:16 and 2:31–3:15 with textural breaks, a 6 s "vocal-led" at 3:24 (share
  0.09 in a drumless break; may be a voice-like synth), percussive-open
  3:30–3:52, bass-led to 4:23.

Measured (version 46):

| | Instant Crush | Five Years | Presence |
|---|---|---|---|
| Unison / Mirrored | 314 s / 26 s | 284 s / 0 | 200 s / 70 s |
| median hand speed | 0.28 m/s | 0.22 | 0.27 |
| stalled | 2.7 % | 3.2 % | 1.0 % |
| kicks (per arm) | 36 | 25 | 66 |
| jolts (any arm over 9 m/s², `jolts.py`) | not counted | 5 | 13 |
| closest implement gap | 11.2 cm | 14.1 | 13.2 |

Five Years' largest jolt (22.7 m/s²) is the last frame of the song; the others
are in the climax. Presence's are flourishes and arrivals. Instant Crush's
mirror fell from 54 s to 26 s: the 18 s drum passage at 3:05 is the third
percussive-open run now and alternates to Unison. Closest gap on Instant Crush
fell from 12.8 to 11.2 cm (clearance 10).

Files: `hexagon-46.html`, `hexagon-46-full.mp4`, `five-years-hexagon(.html,
-full.mp4)`, `presence-hexagon(.html, -full.mp4)`; the version 44 "Five Years"
video is `five-years-hexagon-44-full.mp4`. Scratch in
`tracker-scratch/newsong/`: `song.sh`, `regrid.py`, `songtail.sh`, `phase.py`,
`three.sh`, `jolts.py`, `acts.py`, `classes.py`, `look5.py`, and the tempo-map
set (`beatmap.py`, `warp.py`, `song2.sh`, `songvideo.sh`). 139 CPU tests,
clippy, fmt. Not reviewed.

The user's four moments on "Five Years", version 44 → 46: 0:10–0:17 three
arms flick and stop → all six at 0.1–0.7 m/s, peak acceleration 1.4; 0:45
0.70 m/s at 15.5 m/s² → 0.04–0.23 at 1.0; 1:31–1:35 18.2 m/s² and a 187°/s
turn → 1.6 and 66°/s; 2:22–2:25 0.04–0.07 m/s → 0.14–0.35.

Open: the thresholds remain tuned on three
songs; beat tracking (tempo map, grid refit) is outside the repo; "cannot fit
tangents" on a wrong grid is uninvestigated; entering Mirrored from a wide
heading is unsafe (dodged for short runs only).
