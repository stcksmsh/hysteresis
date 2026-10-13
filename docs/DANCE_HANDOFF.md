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

### Version 47: the user's review of three songs — 2026-10-06

The user on version 46:
- "Five years is generally OK, its a difficult song for this and for dancing
  in general so its OK"
- Instant Crush: "at 3:52 has a strange jerk also at 4:08-4:09, the 4:36
  flourish is also sortof jerky"
- Presence: "a really strange moment at ~0:24-0:26 and again at ~0:41 and
  ~0:49 and ~1:00 (its also all labeled as percussive open, the only
  percussive is kick drum on a simple slower pattern)"; "similar strange stuff"
  at 1:13; after the "quasi drop/start" at 1:32 "really slow and low-energy"
  until ~1:50, "label is bass-led now (the most prominent instrument there for
  me is keys ...)"; "a jerk at 2:03/2:04"; "at 2:24 theyre too fast (but in the
  like 10secs before/after it they actually look like theyre following the
  flute being played)"; the next bass-led "low energy even though the main
  instrument (some high keys/pluc/synth thing) is really nice and emotional
  and has energy and could be followed"; at 2:55–3:00 "the spins fit it
  nicely"; "3:06 is quite a rough stop/slowdown at once"; "3:17 is too fast,
  most of the music dropped out so we should be slower right (and we know a
  buildup and a drop is coming soon due to sidecar)"; "at ~3:29 it says vocal
  led but no vocals exist"; "the buildup until ~3:52 is 'danced' well but it
  doesnt pay off (they could RISE HIGH for it or smth, now they just continue
  like nothing happened)"; after it "again `bass-led` even though an electric
  guitar is the MAIN item"; "the ending is nice but at 4:26 they jitter into a
  stop and then turn quickly again".

Measured causes (`jolts.py`, `spans.py`, `look5.py`):
- Instant Crush 3:52, 4:09, 4:36 and Presence 0:41, 0:49, 1:00, 1:13: sharp
  flourishes; hand 1.5–2.3 m/s, 14–22 m/s². The 0.8 m/s cap is on the figure
  clock; a moment's blend rode on top of it, and a surge under it added more.
  The Instant Crush ones were in version 44 too.
- Presence 0:24, 2:03, 2:24, 3:06, 3:17, low energy 1:32–1:50 and 2:31–2:55:
  the stab surge. Its decay (0.35 beat) suits notes about a beat apart; with
  sparse lead notes the pace sat at 0.3 for seconds, the clock fell behind,
  then caught up at the cap (1.2 m/s, base at 160–185°/s).
- 4:26: an arrival at a point where the music falls away, then catch-up.
- 3:52: an arrival existed, with the same pose as any other.

Changes:
1. **Moment speed limit.** After the clock is built each moment's `span` is
   widened so its blend adds at most 0.6 m/s (travel from the prepared pose to
   the arrival, 1.5 × mean for a smooth blend). The arrival time stays exact;
   the preparation starts earlier. No surge within two beats of a moment.
2. **Surge stretched to the note spacing**: decay 0.35 beat × gap/0.9 for gaps
   of 0.9 to 4 beats (average pace about 1 at any spacing), even pace where
   the leader's notes are more than four beats apart. Because the clock never
   runs ahead of the music, a stretched surge is partly clipped, so sparse
   notes surge less than dense ones; letting the clock lead by half a beat
   restored it but brought back 1.9 m/s flourishes on Instant Crush and was
   reverted. The surge test now measures close either side of each hit with a
   1.1 threshold (was 1.3 over windows a quarter second out, which fell where
   the fixture's figure changes pace tenfold).
3. **Arrivals have a direction**: level over the eight beats before against
   the four after. Lift (rise of 50 % or more is full): pose elevation 0.72 →
   1.0, hold 1.5 → 2.5 beats, strength at least the lift. Falling away:
   strength × the ratio (floor 0.3). An entry from near silence is not a lift.
4. **Calmer without drums**: the clock's rate × 0.65 where drum activity over
   ±2 beats is nil (full from 0.08). The clock then lags and catches up at
   15 % over the next section.
5. **Class names** (same dances): `melody-led` = bass-led rule with the "other"
   stem over 1.5 × the bass's power (motif BASS); `kick-led` = drums over 40 %
   of the power but under the activity mark (motif PERC, formation as
   percussive-open). The voice counts by activity only with 15 % of the "other"
   stem's power beside it. **Not done:** the dance does not yet follow keys or
   guitar any differently than before; the leader lane already drives surge
   and swell in every class. The user's "could be followed" is open.
6. **Abort fixed**: "cannot fit tangents" came from the tangent pass treating
   a joint change under 0.05° between knots as a hold. The last knot sits at
   the song's end, milliseconds after the grid's last, so a moving arm looked
   held, its velocity was zeroed and no fit existed. Now 0.05° per regular
   knot interval. It needed arms still moving at the last instant (Presence;
   Five Years on its first, wrong grid). The error message now prints knot
   times and velocities.

Measured, version 46 → 47:

| | Instant Crush | Five Years | Presence |
|---|---|---|---|
| jolts (any arm over 9 m/s²) | 7 → 5 | 5 → 2 | 13 → 15 |
| kicks (per arm) | 36 → 26 | 25 → 10 | 66 → 76 |
| top hand speed | 2.30 → 1.49 m/s | 1.26 → 1.22 | 2.60 → 1.73 |
| peak hand acceleration | 20.0 → 19.1 m/s² | 22.7 → 10.4 | 21.7 → 21.4 |
| closest implement gap | 11.2 → 13.0 cm | 14.1 → 17.5 | 13.2 → 12.9 |

The user's moments (hand speed m/s, peak acceleration m/s², top base turn °/s):
- Instant Crush 3:50–3:54: top 2.02, 20.0 → 1.2–1.5, 11; 4:07–4:11: top 2.30,
  17.5 → 0.98, 4.4; 4:34–4:38: top 1.32, 14.3 → 1.04, 6.4.
- Presence 0:23–0:27 turn 185 → 144, acceleration 8.5 → 4.2; 0:40–0:42 14.7 →
  6.8; 1:00–1:02 21.7 → 7.8; 1:12–1:15 13.7 → 4.4; 1:32–1:50 mean speed 0.19
  → 0.46, slow share 20 % → 6 %; 2:02–2:06 acceleration 6.2 → 2.9 (still
  0.93 m/s mean: fast arcs); 2:22–2:26 top 1.73 → 0.65 (acceleration still 11);
  2:31–2:55 mean 0.30 → 0.39, slow share 16 % → 6 %; 3:04–3:08 slow share 27 %
  → 0; 3:15–3:20 mean 0.62 → 0.35, top 1.22 → 0.81; 4:24–4:29 top 1.68, 19.9,
  turn 188 → 0.51, 1.7, 106.
- Drops: hand height at 1:32 and 3:52 reaches 0.70 m (the top of the reach),
  2:31 0.67 m. Instant Crush's chorus entries 0.61 → 0.66 m.

Still jolting: Presence 0:48 (a flourish passed round as a ripple in the
mirrored intro, 1.73 m/s), 1:56, 3:11 (flourishes passed round), and one
four-arm event near 3:43 on Instant Crush (19 m/s², inter-arm braking). The
jolt count moves by several with any change of heading: arms in unison brake
for each other at geometry-dependent moments, and no change here addressed
that mechanism.

Presence classes now: kick-led 0:00–1:10 (Mirrored), textural to 1:32,
melody-led and bass-led alternating 1:32–2:16 and 2:31–3:15 (the bass's share
crosses the 1.5 mark; same dance), textural breaks, a 4 s vocal-led at 3:26
(share 0.09 beside a lone synth: passes the 15 % test), kick-led 3:30–3:49,
melody-led and bass-led to 4:23.

Files: `hexagon-47.html`, `hexagon-47-full.mp4`, `five-years-hexagon(.html,
-full.mp4)`, `presence-hexagon(.html, -full.mp4)`. New scratch: `jolts.py`,
`spans.py`, `lv.py`. 139 CPU tests, clippy, fmt. Not reviewed.


### B workspace, round 1 — 2026-10-12

Round 1 of `docs/B_WORKSPACE.md` is built and measured. Mode `Off` is still the
default and reproduces version 47 byte for byte. Nothing here is judged by eye:
**Not verified on any song by eye.** Version 47 itself still has no verdict.

#### What each commit did

| Commit | What |
|---|---|
| `6c1caa8` | Golden digests of `compile_ensemble` before any workspace code (the `Off` ablation baseline). |
| `f2075d7` | `Foresight`: arrivals, repeats, cuts and phrase ends lifted out of the moments code into `workspace.rs`. Golden unchanged. |
| `b38916f` | The workspace itself, not wired: beat observations, levels L1/L2/L4 (leaky mean and variance), L3 (phrase rhythm against the best earlier phrase), surprise, the five-field `Field`, basins, `run()`. 9 tests. |
| `7a06695` | Approach from the lift; timescales from the song's own phrase gap; build start and afterglow length per lift. 4 tests. |
| `310c758` | Wired into figure size, figure clock, moments, voice height, contrast phrase and accents (Ripple/Canon) and the Unison basins. The four ensemble tests now run in all three modes. 5 tests added, 2 replaced. |
| `e6949d0` | This step's code: `EnsembleScore.workspace` debug lane (`FieldSample` per beat; absent in `Off`; old score JSON loads), `ensemble_preview --workspace off|rehearsed|schematic`, stderr summary. `compile_ensemble_with_workspace` returns the `Workspace` beside the score so the example can print basins (the score lane has no basin list). 1 test. |

Tests: 156 green before this step (CPU workspace, `hyst-render` excluded), 157
after. Clippy, fmt, `ensemble.cjs` and the 15 Python tests green before and after.
The three `Off` exports are byte-identical to `hexagon-47.html`,
`five-years-hexagon.html` and `presence-hexagon.html`.

#### Constants and where each came from

Spec = `docs/B_WORKSPACE.md` gave the value. The rest are mine and unjudged.

| Constant | Value | Origin |
|---|---|---|
| Gain attack / afterglow decay | 0.5 beats / per lift | attack: spec. Decay: spec said a fixed 16; `7a06695` replaced it with the lift's own loud stretch. |
| Tension release | 1 beat | spec |
| Precision recovery / approach decay / habituation decay | 8 / 8 / 64 beats | spec |
| Gain from surprise, payoff, novelty and recognition kicks | 0.6·s, 0.5+0.5·T, 0.3·s, 0.2 | spec |
| Level weights L1, L2, L3, L4 | 0.5, 0.3, 0.3, 0.2 | spec said "fixed constants" and gave none; `b38916f` chose them |
| `Z_KNEE`, `Z_SPAN` | 1.5, 4.0 | `b38916f`. Not in spec. A steady loop has a z-score near 1, so raw z cannot be an error; below the knee is no error, knee + span is full error. |
| `VAR_FLOOR` | 0.0025 (sd 0.05) | `b38916f`. Not in spec. A flat signal would make the first wiggle an infinite z. |
| `PEAK_DECAY` | 256 beats | `b38916f`. Not in spec. The running peak that stands in for `intensity(t)` (see below). |
| L3 spread time constant | 2 phrases | `b38916f`. Not in spec. |
| Leader dimensions in the observation | lane/8, brightness/128 | `b38916f`. Scaling not in spec. |
| Timescales L1, L2, L4 | phrase/4, phrase, 4·phrase | spec said 4, 16, 64 beats; `7a06695` derives them from the song's median phrase gap |
| Measured sign (Schematic only) | level now vs mean of last 8 beats: >1.1 up, <0.9 down, none if before <0.15·peak | `b38916f`/`7a06695`. Not in spec. |
| Figure size | ×(0.85+0.3·g)×(1−0.25·T), then min 1.0 | factors: spec. The cap at 1.0: `310c758`. |
| Figure clock | ×(1−0.35·T); floor 1.0 while `since_lift` < afterglow, else 0.65 | spec |
| Moment strength and hold | ×(0.7+0.6·T one beat before it); strength capped at 1.0 | factor: spec. The cap at 1.0: `310c758`, because strength is a 0..1 blend. |
| Moment preparation | `lead` = max(2·span, T one beat before × beats since build start) | spec idea; formula is `310c758`'s |
| Voice lift | +0.15·a, where a is the lift's sign smoothed over 4 beats (k = 1−e^−0.25) | factor: spec. The 4-beat smoothing: `310c758`, because a step in the lift carried the hand 0.2 to 0.5 m/s past the speed cap. |
| Contrast phrase | after 128·(1−0.4·h) beats | spec |

#### What the spec did not settle

- **Gain loudness is causal.** `intensity(t)` looks ahead and behind. Gain uses
  the beat's level against a running peak that decays over 256 beats.
- **Timescales from the median phrase gap.** A bar is phrase/4. That is a guess:
  the sidecar has no downbeats.
- **Build start** is the quietest bar within 2 phrases before a lift (the
  earliest on a tie). A build longer than that starts its held breath late.
- **Afterglow** is the loud stretch after a lift (bars until a bar falls under
  half the first), clamped to [bar, 4 phrases].
- **Approach** is the lift's sign (up +1, falling away −1, entry 0). In
  Schematic it is the measured sign when a surprise crosses 0.5.

#### Measured (release builds, `--ring 6,0.8`)

Guardrails from "Acceptance". Jolts = moments any arm passes 9 m/s². Gap =
closest implement gap.

| Song · mode | Jolts (limit) | Top hand speed (≤ 1.73) | Gap (≥ 10 cm) | Shown? |
|---|---|---|---|---|
| Instant Crush · off (v47) | 5 (≤ 8) | 1.49 | 13.0 | baseline |
| Instant Crush · rehearsed | **9** (≤ 8) | **2.24** | 10.3 | **not shown** |
| Instant Crush · schematic | 7 | 1.64 | 12.8 | ok |
| Five Years · off (v47) | 2 (≤ 5) | 1.22 | 17.5 | baseline |
| Five Years · rehearsed | **7** (≤ 5) | 1.17 | 12.4 | **not shown** |
| Five Years · schematic | 2 | 1.59 | 13.0 | ok |
| Presence · off (v47) | 15 (≤ 18) | 1.73 | 12.9 | baseline |
| Presence · rehearsed | 16 | **2.06** | 12.2 | **not shown** |
| Presence · schematic | 17 | **1.78** | 12.8 | **not shown** |

`Rehearsed`, the mode that has to win, breaks a guardrail on all three songs.
By the rule in "Acceptance" it goes to the tuning round, not to the user.
`Schematic` breaks one (Presence top speed, 1.78 against 1.73).

Jolts in a mode that are more than 0.5 s from every `Off` jolt (Five Years times
are video clock). "No moment" means the jolt is inside a plain move.

- Instant Crush, rehearsed: 8 new
  - 0:15.4 · 6 arms · 10.5 m/s² · move eight (percussive-open) · flourish moment at 12.60s
  - 1:34.8 · 6 arms · 10.4 m/s² · move rise (interlocked) · no moment
  - 1:57.0 · 6 arms · 17.4 m/s² · move gather (interlocked) · no moment
  - 2:03.0 · 6 arms · 12.8 m/s² · move reach (vocal-led) · no moment
  - 3:45.7 · 5 arms · 21.5 m/s² · move circle (interlocked) · flourish moment at 221.35s
  - 4:08.8 · 6 arms · 15.5 m/s² · move gather (interlocked) · flourish moment at 249.05s
  - 4:18.0 · 2 arms · 9.0 m/s² · move gather (interlocked) · no moment
  - 4:57.6 · 6 arms · 27.1 m/s² · move arc (bass-led) · no moment
- Instant Crush, schematic: 7 new
  - 0:15.4 · 6 arms · 10.5 m/s² · move eight (percussive-open) · flourish moment at 12.60s
  - 1:42.3 · 6 arms · 24.6 m/s² · move circle (interlocked) · no moment
  - 2:15.6 · 4 arms · 10.2 m/s² · move reach (vocal-led) · arrival moment at 134.25s
  - 3:42.9 · 2 arms · 13.9 m/s² · move circle (interlocked) · flourish moment at 221.35s
  - 4:08.8 · 4 arms · 20.2 m/s² · move circle (interlocked) · flourish moment at 249.05s
  - 4:46.3 · 1 arms · 9.6 m/s² · move rise (interlocked) · no moment
  - 4:55.3 · 6 arms · 21.7 m/s² · move gather (interlocked) · no moment
- Five Years, rehearsed: 7 new
  - 2:30.9 · 6 arms · 9.7 m/s² · move reach (vocal-led) · arrival moment at 149.60s
  - 2:57.0 · 6 arms · 10.9 m/s² · move open (interlocked) · no moment
  - 3:33.6 · 6 arms · 10.2 m/s² · move gather (interlocked) · arrival moment at 213.00s
  - 3:43.5 · 6 arms · 27.1 m/s² · move circle (interlocked) · no moment
  - 3:50.6 · 6 arms · 10.2 m/s² · move open (interlocked) · no moment
  - 3:52.0 · 6 arms · 10.6 m/s² · move circle (interlocked) · arrival moment at 236.10s
  - 3:59.0 · 6 arms · 11.0 m/s² · move arc (interlocked) · no moment
- Five Years, schematic: 2 new
  - 2:44.4 · 6 arms · 19.0 m/s² · move circle (interlocked) · flourish moment at 162.20s
  - 4:17.3 · 3 arms · 9.3 m/s² · move gather (interlocked) · no moment
- Presence, rehearsed: 12 new
  - 0:14.2 · 1 arms · 9.9 m/s² · move sway (kick-led) · no moment
  - 0:40.6 · 6 arms · 18.2 m/s² · move eight (kick-led) · no moment
  - 0:46.8 · 2 arms · 10.1 m/s² · move eight (kick-led) · no moment
  - 0:49.0 · 1 arms · 9.6 m/s² · move sway (kick-led) · flourish moment at 48.05s, passed round as Ripple
  - 1:57.2 · 1 arms · 11.1 m/s² · move rise (melody-led) · flourish moment at 117.05s, passed round as Canon
  - 2:18.1 · 2 arms · 11.8 m/s² · move sway (textural) · arrival moment at 136.57s, passed round as Canon
  - 2:55.8 · 4 arms · 12.1 m/s² · move rise (melody-led) · passed round as Ripple
  - 2:57.1 · 2 arms · 9.9 m/s² · move rise (melody-led) · passed round as Ripple
  - 3:16.9 · 1 arms · 14.1 m/s² · move sway (textural) · arrival moment at 195.77s, passed round as Canon
  - 3:21.8 · 1 arms · 15.2 m/s² · move sway (textural) · arrival moment at 195.77s, passed round as Canon
  - 3:29.5 · 4 arms · 9.5 m/s² · move reach (vocal-led) · passed round as Canon
  - 4:12.9 · 6 arms · 29.5 m/s² · move arc (melody-led) · no moment
- Presence, schematic: 10 new
  - 0:28.2 · 3 arms · 10.9 m/s² · move sway (kick-led) · no moment
  - 0:54.0 · 6 arms · 10.6 m/s² · move eight (kick-led) · no moment
  - 1:00.9 · 1 arms · 9.1 m/s² · move reach (kick-led) · flourish moment at 60.95s
  - 1:20.7 · 1 arms · 10.8 m/s² · move sway (textural) · passed round as Canon
  - 1:24.3 · 1 arms · 10.9 m/s² · move sway (textural) · passed round as Canon
  - 1:55.8 · 1 arms · 10.1 m/s² · move rise (melody-led) · flourish moment at 117.05s, passed round as Canon
  - 1:57.2 · 2 arms · 10.5 m/s² · move rise (melody-led) · flourish moment at 117.05s, passed round as Canon
  - 2:18.0 · 2 arms · 15.1 m/s² · move sway (textural) · arrival moment at 136.57s, passed round as Canon
  - 3:16.3 · 2 arms · 20.0 m/s² · move sway (textural) · arrival moment at 195.77s, passed round as Canon
  - 4:16.5 · 6 arms · 15.6 m/s² · move arc (melody-led) · no moment

Per the "Acceptance" rule, a jolt that also exists in `Off` belongs to the
braking problem. These do not exist in `Off`. The list shows additions only;
it does not show `Off` jolts that a mode removed.

#### Presence 1:15–1:50, the build into the 1:32 drop (Rehearsed)

There is **no held breath**. Tension is 0.00 on every beat from 1:15 to 1:50.
Its three highest peaks in the whole song are 1:09.8 (0.92), 2:53.2 (0.92) and 3:52.2
(0.94). Gain is already near its 1.5 clamp: the lift at 1:10.2 (gain 1.50) left a
64-beat afterglow, so gain only decays from 1.38 at 1:15.8 to 1.20 at 1:30.5, and
the lift at 1:32.4 pushes it from 1.20 to 1.50, a rise of 0.30 where the payoff
rule asked for 0.5. Basins in the window: novelty 1:28.7 (0.95); lift 0.60 and
novelty 0.95 together at 1:32.4; Schematic (no foresight) has novelty basins at
1:36.1, 1:43.5 and 1:50.8 and no lift. Surprise 0.74 at 1:32.4 (the second
largest in the song; the largest, 0.89, is at 3:24.5), so the drop does break
the groove. Why the 1:32 build has no tension is not diagnosed. The cause is
somewhere in the build start or the ramp for that lift; it was not traced.

#### Instant Crush

First Recognition basin: **0:46.2** (similarity 0.95), then 0:50.5 and 0:52.7.
Recognition basins also fire nine times between 3:25 and 3:50 (every 2.2 s).

#### What is not known

Everything about how it looks. The measurements above are guardrails; they are
not a verdict. `Off` is unchanged. No video was made.

#### Next steps for the user

1. Rehearsed breaks a guardrail on all three songs, so the rule says tune
   before showing. Say if you would rather look at it anyway; that is your call
   and it is outside the fixed acceptance rule.
2. If you want the blind clips: they are three exports shuffled per clip as
   A | B | C (left, middle, right), key in a file you leave unread until the
   verdict. `hexreview.sh` cannot make them (whole song only, hard-coded to
   Instant Crush's audio, and it reuses a cached `hexrev-all.mp4`), so this
   script calls the recorder directly (`record-ensemble.cjs`, max 40 s per
   call, honours `HYST_TEMPO_MAP`). Not run. Save and run with `bash`:

```
#!/bin/bash
set -e
D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
O=$D/b1-blind; mkdir -p $O; : > $O/b1-blind-key.txt
# name song-tag audio-stem start-seconds length-seconds
clips=("presence-build pr presence 75 35" "presence-emotional pr presence 151 24" "crush-return ic instant-crush 38.2 32" "years-climb fy five-years 133 27")
for c in "${clips[@]}"; do
  read name s audio start secs <<< "$c"
  perm=$(python3 -c "import random;m=['off','rehearsed','schematic'];random.shuffle(m);print(*m)")
  echo "$name left-to-right: $perm" >> $O/b1-blind-key.txt
  i=0
  for m in $perm; do
    if [ $s = fy ]; then export HYST_TEMPO_MAP=$D/five-years.tempomap.json; else unset HYST_TEMPO_MAP; fi
    node $D/record-ensemble.cjs $D/b1-$m-$s.html $D/$audio.m4a $O/$name-$i.mp4 $start $secs > /dev/null
    i=$((i+1))
  done
  ffmpeg -y -v error -i $O/$name-0.mp4 -i $O/$name-1.mp4 -i $O/$name-2.mp4 -ss $start -t $secs -i $D/$audio.m4a \
    -filter_complex "[0:v]scale=640:-2[a];[1:v]scale=640:-2[b];[2:v]scale=640:-2[c];[a][b][c]hstack=inputs=3[v]" \
    -map "[v]" -map 3:a -c:v libx264 -crf 28 -pix_fmt yuv420p -c:a aac -shortest $O/$name.mp4
  rm $O/$name-0.mp4 $O/$name-1.mp4 $O/$name-2.mp4
done
echo "clips in $O; do not open b1-blind-key.txt until you have chosen"
```

3. The four clips (audio clock; the exports are `$D/b1-{off,rehearsed,schematic}-{ic,fy,pr}.html`):
   "Presence" 1:15–1:50 and 2:31–2:55; "Instant Crush" 8 s before its first
   Recognition basin to 24 s after (0:38.2–1:10.2); "Five Years" 2:13–2:40.
4. What to look for: the held breath before 1:32 in Presence (this run shows
   none, see above), and the arms gathering into one body at the Instant Crush
   chorus return.
5. The rule, fixed before any result: `Rehearsed` must beat `Off` in at least 3
   of the 4 clips. A tie is a loss. `Schematic` cannot win alone. A mode over a
   guardrail is not shown (all `Rehearsed` exports are over one).

Files in `$D`: `b1-{off,rehearsed,schematic}-{ic,fy,pr}.{html,summary.txt,jolts.txt,look5.txt,gap.txt}`.
Scratch: `/tmp/b1/` (export, measure and field scripts; not kept).

### B workspace, round 2 — 2026-10-12

The user's round-1 verdicts stand: `Rehearsed` won only Presence 2:31–2:55 (1 of
4), so the rule sent it to round 2. The user allowed constants plus two
definition fixes and nothing else. Commit `b20e7f6`. `Off` is still byte-
identical to version 47 (the three exports compared with `cmp`), golden digests
unchanged, 159 CPU tests, clippy, fmt, `ensemble.cjs` and the Python tests green.
**Not verified on any song by eye.**

#### What the user measured on round 1 (Presence, Rehearsed), confirmed

Gain above 1.0 on 93 % of beats (median 1.28), so figure size was ×1.15–1.3
nearly all the time and clamped at 1.0. Tension built before the 1:10 lift but
started at 1:31.9 for the 1:32 drop. Instant Crush fired Recognition every 2.2 s
at 3:25–3:50.

#### Changes

Two definition fixes (`workspace.rs`):

1. **`build_start` skips the last two bars before the arrival** when it looks
   for the quietest bar (bars 3 to 8 back instead of 1 to 8). Test: a riser from
   beat 52 to 76, a quiet bar at 76–80, the drop at 80: build start 52, tension
   starts within 4 beats of it.
2. **At most one Recognition basin per phrase**: a minimum gap of the phrase
   length (`taus[1]` beats) between recognitions. It gates the whole basin (the
   precision reset, habituation, gain kick and the Unison). Test: repeats every
   4 beats in a 16-beat-phrase song give gaps of at least 16 beats.

Constants:

| Constant | Round 1 | Round 2 | Why |
|---|---|---|---|
| `GAIN_STEADY` (new): gain target = this × level/peak | 1 (implicit) | 0.5 | a steady passage sits near 0.5; the spec's surprise term, lifts and recognitions push above |
| Figure size gain factor, `figures.rs` | 0.85 + 0.3·g | 0.9 + 0.2·g | still ×1.0 at g = 0.5; a smaller swing |
| Figure clock tension factor | 1 − 0.35·T | 1 − 0.17·T | |
| Everything else | | unchanged | size ×(1−0.25·T), moment ×(0.7+0.6·T), voice +0.15·a, all `workspace.rs` time constants |

**How the last two were chosen: a search, not a derivation.** With only the gain
centre and the two fixes (rehearsed: Instant Crush 11 jolts, Five Years 9; both
over), I swept 48 combinations of the five wiring factors (size gain 0 / 0.1 /
0.2, size tension 0.12 / 0.25, clock tension 0.17 / 0.35, moment 0.3 / 0.6, voice
0.075 / 0.15) against the three songs' guardrails. Two passed all nine checks;
I took the one that moves the fewest constants. The other: size gain 0.1 and
clock 0.35, which sits at exactly 18 jolts on Presence. Jolt counts move by
several with any change (the known braking mechanism), so the margin is thin:
Five Years sits at its limit of 5. These constants are tuned against these three
songs and the guardrail numbers, not against how it looks.

#### Gain distribution (Rehearsed, per beat)

| Song | Median | p10 | p90 | Share above 1 |
|---|---|---|---|---|
| Instant Crush before → after | 1.23 → 0.98 | 0.99 → 0.61 | 1.47 → 1.38 | 88 % → 48 % |
| Five Years before → after | 1.33 → 1.22 | 0.93 → 0.56 | 1.47 → 1.45 | 86 % → 76 % |
| Presence before → after | 1.28 → 1.02 | 1.03 → 0.73 | 1.47 → 1.36 | 93 % → 54 % |

Steady passages now sit near 0.6 (p10). The medians stay near or above 1 because
a lift's afterglow keeps gain above 1 for 40 or more beats (decay 16 to 64 beats
from 1.5) and these songs lift often; Five Years stays loud for minutes. Not
reduced further: the afterglow clamp is a definition, not a constant.

#### Guardrails, Rehearsed now passes on all three songs

| Song · mode | Jolts (limit) | Top hand speed (≤ 1.73) | Gap (≥ 10 cm) |
|---|---|---|---|
| Instant Crush · off (v47) | 5 (≤ 8) | 1.49 | 13.0 |
| Instant Crush · rehearsed | 7 | 1.56 | 13.7 |
| Instant Crush · schematic | 4 | 1.56 | 15.1 |
| Five Years · off (v47) | 2 (≤ 5) | 1.22 | 17.5 |
| Five Years · rehearsed | 5 | 1.26 | 15.5 |
| Five Years · schematic | 2 | 1.28 | 16.9 |
| Presence · off (v47) | 15 (≤ 18) | 1.73 | 12.9 |
| Presence · rehearsed | 17 | 1.57 | 12.8 |
| Presence · schematic | 15 | 1.55 | 11.5 |

New jolts (more than 0.5 s from every `Off` jolt; Five Years in video clock):

- Instant Crush, rehearsed: 6 new
  - 1:57.2 · 1 arms · 12.4 m/s² · move gather (interlocked) · no moment
  - 4:08.8 · 4 arms · 20.7 m/s² · move circle (interlocked) · flourish moment at 249.05s
  - 4:47.4 · 6 arms · 10.6 m/s² · move open (interlocked) · no moment
  - 4:56.7 · 5 arms · 18.2 m/s² · move gather (interlocked) · no moment
  - 5:09.1 · 1 arms · 9.3 m/s² · move gather (bass-led) · no moment
  - 5:10.7 · 1 arms · 10.7 m/s² · move rise (bass-led) · flourish moment at 312.75s, passed round as Canon
- Instant Crush, schematic: 4 new
  - 1:42.3 · 3 arms · 15.1 m/s² · move circle (interlocked) · no moment
  - 2:15.6 · 4 arms · 11.5 m/s² · move reach (vocal-led) · arrival moment at 134.25s
  - 3:34.5 · 6 arms · 15.2 m/s² · move gather (interlocked) · arrival moment at 212.65s
  - 3:59.6 · 5 arms · 12.0 m/s² · move gather (interlocked) · flourish moment at 240.30s
- Five Years, rehearsed: 5 new
  - 2:54.7 · 6 arms · 9.7 m/s² · move rise (interlocked) · no moment
  - 3:31.9 · 2 arms · 9.2 m/s² · move gather (interlocked) · arrival moment at 213.00s
  - 3:50.6 · 6 arms · 11.1 m/s² · move open (interlocked) · no moment
  - 4:02.5 · 6 arms · 9.4 m/s² · move arc (interlocked) · no moment
  - 4:43.7 · 3 arms · 12.9 m/s² · move still (silence) · passed round as Ripple
- Five Years, schematic: 2 new
  - 3:10.9 · 6 arms · 9.7 m/s² · move circle (interlocked) · arrival moment at 189.80s
  - 3:38.0 · 2 arms · 9.1 m/s² · move circle (interlocked) · no moment
- Presence, rehearsed: 9 new
  - 0:40.7 · 6 arms · 12.8 m/s² · move sway (kick-led) · flourish moment at 40.65s
  - 1:11.5 · 6 arms · 12.1 m/s² · move sway (textural) · arrival moment at 70.35s, flourish moment at 77.35s, passed round as Ripple
  - 1:57.6 · 2 arms · 10.7 m/s² · move rise (melody-led) · flourish moment at 117.05s, passed round as Canon
  - 3:13.0 · 1 arms · 11.3 m/s² · move arc (melody-led) · no moment
  - 3:16.4 · 3 arms · 19.0 m/s² · move sway (textural) · arrival moment at 195.77s, passed round as Canon
  - 3:19.8 · 2 arms · 11.7 m/s² · move sway (textural) · arrival moment at 195.77s, passed round as Canon
  - 3:29.9 · 3 arms · 10.7 m/s² · move reach (vocal-led) · passed round as Canon
  - 3:40.9 · 4 arms · 11.6 m/s² · move eight (kick-led) · flourish moment at 220.45s, passed round as Canon
  - 4:13.6 · 4 arms · 10.2 m/s² · move arc (melody-led) · no moment
- Presence, schematic: 9 new
  - 1:20.2 · 1 arms · 10.5 m/s² · move sway (textural) · passed round as Canon
  - 1:24.3 · 1 arms · 13.5 m/s² · move sway (textural) · passed round as Canon
  - 1:57.2 · 3 arms · 10.5 m/s² · move rise (melody-led) · flourish moment at 117.05s, passed round as Canon
  - 2:19.4 · 3 arms · 11.5 m/s² · move sway (textural) · arrival moment at 136.57s, passed round as Canon
  - 2:59.8 · 6 arms · 10.7 m/s² · move arc (melody-led) · no moment
  - 3:14.3 · 1 arms · 11.6 m/s² · move arc (melody-led) · no moment
  - 3:16.1 · 2 arms · 17.9 m/s² · move sway (textural) · arrival moment at 195.77s, passed round as Canon
  - 3:19.5 · 1 arms · 12.2 m/s² · move sway (textural) · arrival moment at 195.77s, passed round as Canon
  - 3:21.6 · 1 arms · 9.3 m/s² · move sway (textural) · arrival moment at 195.77s, passed round as Canon

#### Presence 1:15–1:50 and Instant Crush, Rehearsed

- Tension now starts at 1:23.6, not 1:31.9: 0.12 at 1:24.5, 0.42 at 1:27.3, 0.72
  at 1:30.1, 0.87 at 1:31.5, then 0 at the 1:32.4 lift. Gain falls from 1.19 to
  0.97 over the build, then jumps to 1.48 at the drop and decays to 1.01 by 1:50.8.
  Surprise at the drop is 0.74 as before.
- Presence has 6 Recognition basins (12 before); Instant Crush has 4 (12 before).
  Instant Crush's first is still 0:46.2; at 3:25–3:50 they are 3:25.5, 3:36.4
  and 3:47.3, one per phrase.

#### The blind test, round 2

Same four clips as round 1, fresh shuffle, key in
`$D/b1-blind-r2/b1-blind-key.txt`, which I did not open. Clips:
`presence-build.mp4`, `presence-emotional.mp4`, `crush-return.mp4`,
`years-climb.mp4` in `$D/b1-blind-r2/`, left to right A, B, C. The round-1 clips
and key stay in `$D/b1-blind/`. Same rule: `Rehearsed` must beat `Off` in at
least 3 of 4, a tie is a loss, `Schematic` cannot win alone. A loss here is
"Remove": delete `workspace.rs` and its wiring (`Foresight` stays only if the
moments code reads cleaner with it). There is no round 3.

To remake them: `/tmp/b1/blind2.sh` is the round-1 script with the output
directory changed to `b1-blind-r2`; the script text is in the round-1 entry.

### Emotion stage 1: encoder — 2026-10-12

Spec: `docs/EMOTION.md`. No planner behaviour changed (version 47 and the `Off`
golden digests untouched). All code is in `scripts/emotion/`; data, caches and
models are outside git. **The final check 1 uses the stems baseline** (Demucs on all
2,144 clips); an earlier run against mix-only features came first and is kept below
for comparison. **Not judged by ear or eye; the report page is for you to read and
mark wrong.**

#### Datasets and licences (`/secondary/hyst-data/emotion/SOURCES.md` has URLs, hashes, text)

| Data | Used | Licence |
|---|---|---|
| DEAM, 2013/2014 label release, songs 1..2000 (1,744 clips; the 58 full songs of the 2015 release are left out so one release is used) | timing | manual §3: Non-Commercial Creative Commons (BY-NC), non-profit work |
| Emotify, 400 one-minute clips, 8,407 rater rows | feelings | no licence stated; "cite the paper" |
| PMEmo | **not used** | data licence unstated (the repo's MIT covers code), audio only on Google Drive |

Emotify track ids 1..400 are assumed to run classical, rock, electronic, pop
with file `n` in each genre folder numbered 1..100. The package does not say so.
Models: MERT-v1-95M (cc-by-nc-4.0), `laion/larger_clap_music` (apache-2.0),
Essentia Discogs-EffNet and the mtg_jamendo_moodtheme head (CC BY-NC-SA 4.0). The
DEAM- and emoMusic-trained Essentia heads were not used: they were trained on the
labels this check scores. All of these are non-commercial: check before exhibition.

#### Candidates

Windows 4 s, step 0.5 s, cached as `.npy` with a manifest per candidate.
- Baseline: the sidecar's mix signals (energy, five bands, centroid, flatness, flux,
  onset density, periodicity: mean, std, max over the window; 29 numbers) from audio
  with the sidecar's constants, plus the stems (Demucs htdemucs 4.1.0, per-stem level,
  flux, power share, leader: 20 more, 49 in all). The stems baseline is **the** baseline;
  the 29-number mix-only version is the earlier reference.
- B expectation signals: **not computed.** They need beat grids, phrase memory and
  Foresight events; a 45 s clip has none worth the name. Said here, not faked.
- MERT-v1-95M: run over the whole clip, hidden states pooled per window. All 13 layers
  kept; "average" = mean of layers, "best" = layer chosen by inner CV on training songs.
- CLAP: `larger_clap_music`, 4 s windows hop 2 s (a 0.5 s hop would have taken about 8 h).
- Essentia: Discogs-EffNet embedding (1,280) and the mood/theme head (56).
- Combined: baseline + each model, and baseline + all.

#### Final check 1: stems baseline (rules as written in `check1.py`, committed before any result)

Same folds, seeds, rows and rules as the earlier run below. Output: `/secondary/hyst-data/emotion/check1_stems/`.

| candidate | dims | timing R² | rank corr ρ | NN agreement | geometry | gates timing/ρ/NN | result |
|---|---|---|---|---|---|---|---|
| baseline (stems + mix) | 49 | 0.449 [0.423, 0.473] | 0.524 [0.490, 0.558] | 0.215 [0.175, 0.255] | 1.082 [1.035, 1.143] | – | reference |
| mert_avg | 768 | 0.603 [0.582, 0.622] | 0.597 [0.569, 0.626] | 0.260 [0.217, 0.302] | 1.041 [1.025, 1.061] | y/y/n | fail |
| mert_best | 768 | 0.605 [0.584, 0.622] | 0.616 [0.588, 0.644] | 0.273 [0.230, 0.318] | 1.050 [1.032, 1.072] | y/y/n | fail |
| clap | 512 | 0.229 [0.206, 0.251] | 0.366 [0.329, 0.400] | 0.177 [0.140, 0.215] | 1.065 [1.028, 1.115] | n/n/n | fail |
| essentia | 1,336 | 0.531 [0.508, 0.550] | 0.614 [0.586, 0.641] | 0.295 [0.253, 0.340] | 1.042 [1.028, 1.060] | y/y/n | fail |
| baseline+mert_avg | 817 | 0.610 [0.590, 0.629] | 0.596 [0.568, 0.626] | 0.260 [0.217, 0.303] | 1.044 [1.026, 1.065] | y/y/n | fail |
| baseline+clap | 561 | 0.454 [0.429, 0.477] | 0.467 [0.430, 0.503] | 0.215 [0.175, 0.255] | 1.067 [1.031, 1.114] | n/n/n | fail |
| baseline+essentia | 1,385 | 0.559 [0.537, 0.578] | 0.616 [0.588, 0.643] | 0.295 [0.253, 0.340] | 1.043 [1.029, 1.062] | y/y/n | fail |
| baseline+all | 2,665 | 0.617 [0.596, 0.635] | 0.616 [0.588, 0.643] | 0.318 [0.273, 0.362] | 1.043 [1.027, 1.063] | y/y/y | **pass, pick** |

**Pick: baseline+all** (stems + mix baseline, MERT average, CLAP, Essentia embedding,
Essentia mood). It is the only passer. Against the stems baseline, Essentia and
baseline+Essentia no longer pass: their NN-agreement intervals now overlap the
baseline's (0.253 vs 0.255). Valence R² 0.54 / arousal 0.70 for the pick (baseline 0.33 / 0.57).
Within-song R² is still negative for every candidate (baseline -1.37, pick -0.96).
Everything said under "What the numbers do and do not say" below still holds.

#### Earlier run: mix-only baseline (rules as written in `check1.py`, committed before any result)

Seeds: folds 20261012, bootstrap 20261013 (2,000 resamples over songs), inner CV
20261014. Five folds by song, same folds for every candidate (Emotify balanced by genre).
Ridge penalty by inner 3-fold on training songs only. Scored on the same rows: 4 s
windows on a 2 s grid (DEAM labels at 15, 17, … s: 26,155 rows from 1,744 songs;
Emotify clip means). Intervals are 95 % bootstrap over songs.

| candidate | dims | timing R² | rank corr ρ | NN agreement | geometry | gates timing/ρ/NN | result |
|---|---|---|---|---|---|---|---|
| baseline (mix only) | 29 | 0.426 [0.402, 0.449] | 0.509 [0.474, 0.543] | 0.190 [0.152, 0.230] | 1.082 [1.031, 1.151] | – | reference |
| mert_avg | 768 | 0.603 [0.582, 0.622] | 0.597 [0.569, 0.626] | 0.260 [0.217, 0.302] | 1.041 [1.025, 1.061] | y/y/n | fail |
| mert_best | 768 | 0.605 [0.584, 0.622] | 0.616 [0.588, 0.644] | 0.273 [0.230, 0.318] | 1.050 [1.032, 1.072] | y/y/n | fail |
| clap | 512 | 0.229 [0.206, 0.251] | 0.366 [0.329, 0.400] | 0.177 [0.140, 0.215] | 1.065 [1.028, 1.115] | n/n/n | fail |
| essentia | 1,336 | 0.531 [0.508, 0.550] | 0.614 [0.586, 0.641] | 0.295 [0.253, 0.340] | 1.042 [1.028, 1.060] | y/y/y | **pass** |
| baseline+mert_avg | 797 | 0.609 [0.589, 0.628] | 0.595 [0.566, 0.625] | 0.255 [0.212, 0.300] | 1.043 [1.026, 1.064] | y/y/n | fail |
| baseline+clap | 541 | 0.432 [0.407, 0.456] | 0.430 [0.393, 0.464] | 0.193 [0.155, 0.230] | 1.066 [1.030, 1.114] | n/n/n | fail |
| baseline+essentia | 1,365 | 0.553 [0.530, 0.572] | 0.612 [0.584, 0.639] | 0.295 [0.253, 0.340] | 1.043 [1.028, 1.061] | y/y/y | **pass** |
| baseline+all | 2,645 | 0.614 [0.593, 0.632] | 0.614 [0.586, 0.641] | 0.310 [0.265, 0.355] | 1.043 [1.027, 1.062] | y/y/y | **pass, pick** |

**Pick: baseline+all** (mix baseline + MERT average + CLAP + Essentia embedding + Essentia
mood), best mean rank among the three passers (mean ranks 1.50, baseline+essentia 1.92,
essentia 2.58; the three differ by under 0.002 on geometry and by 0.003 on ρ).
Pass rule: beats the baseline's point value on timing, rank correlation and nearest-
neighbour agreement, each with an interval that does not overlap the baseline's;
geometry is ranked, not a gate. Pick = best mean rank over timing, feelings (mean of
ρ rank and agreement rank) and geometry among passers.

What the numbers do and do not say:
- **Within-song timing is not captured.** The diagnostic R² with song means removed
  is negative for every candidate (baseline -1.31, MERT -0.37…-0.41, Essentia -1.90,
  baseline+all -0.96). The pooled timing score is mostly between-song mood.
  The spec's measure is the pooled one and that is what gates. Nothing here shows the
  encoding follows change inside a song.
- **Geometry is weak** for everything (1.04–1.08), and the baseline is highest.
- MERT misses only on nearest-neighbour agreement; its interval touches the baseline's.
- CLAP (music checkpoint, 4 s windows padded to its 10 s input) is below the baseline.
- Rank correlation includes the common mode (every clip has high tenderness and
  low tension); the centred variant is in `results.json` and the table: baseline
  0.46, baseline+all 0.59.
- DEAM valence is the weaker label (its manual says so): R² 0.31 vs arousal 0.54 for
  the baseline, 0.53 vs 0.69 for baseline+all.

#### Deviations from the spec, and why

1. **Stems baseline took a long run.** Demucs on 2,144 clips was ~13-20 s per clip here
   (8.5 s in a quiet machine; three parallel shards were slower, not faster), roughly
   11 h with interruptions. I first ran check 1 against the mix-only baseline (the table
   below), then reran when stems finished (the table above, which is final). Demucs is
   4.1.0, the songs' own stems were made with 4.0.1 (same htdemucs weights).
2. **Evaluation grid 2 s**, not 0.5 s, for every candidate (CLAP cost). Caches for the
   other candidates are at 0.5 s.
3. B expectation signals not computed (above).
4. MERT is pooled from whole-clip hidden states, not run per window: windows see context.
5. Nearest-neighbour is among the other held-out clips of the same fold (pools of 80);
   cosine distance on training-standardised vectors. The spec said "closest held-out
   neighbour"; the pool choice is mine. NN bootstrap resamples clips, not pools.
6. DEAM: 2013/2014 labels only, chosen to use one release.

#### Output and report

- `scripts/emotion/encode.py IN AUDIO OUT --components …` writes a new sidecar with
  `emotionEncoding` (`model`, `version`, `dims`, `hopSeconds`, `windowSeconds`,
  per-step `steps`, per-beat `perBeat`, `components`, `provenance`). Refuses to
  overwrite the input, refuses audio more than 100 ms off the sidecar duration.
- Run on the three danced songs, outputs next to the inputs, with the final pick's components:
  `instant-crush.emotion.sidecar.json` (680 steps), `five-years-steady.emotion.sidecar.json` (568),
  `presence.emotion.sidecar.json` (542), 2,665 dims each, 62–77 MB each. The songs' stems are
  the existing Demucs outputs. Five Years uses its steady-grid analysis WAV, as the sidecar does.
- Report: `$D/emotion-report.html` (D = music-arm directory): the check-1 table, and for
  each song every 10 s the predicted GEMS profile and the nearest 3 Emotify and 3 DEAM clips.
  **I have not read it for sense.** Library clips are 45–60 s means; a 10 s query is noisier.

#### Cost

Run times (this machine, 20 threads): mix features under 15 min; Essentia 1.2 s/clip (~45 min);
MERT 4.5 s/clip (~2.7 h); CLAP 3.3–4.6 s/clip (~2.2 h incl. a restart); Demucs 13 s/clip;
check 1 for all nine candidates ~6 min (~4 min in the final run). Disk: data and caches 7.8 GB, env 2.1 GB, HF cache
1.6 GB, uv cache 2.2 GB (~14 GB of the 30 GB; encoded sidecars 195 MB outside the repo).

#### Tests and checks

`scripts/emotion/test_*.py`: 19 tests. Splits never share a song; ridge recovers a known
linear signal and scores noise near zero; the inner choice does not see the test fold
(wrecked test labels change nothing); layer selection finds the informative layer; pass
rule needs clear intervals; `encode.py` leaves the input byte-identical and adds only
`emotionEncoding`. Run: `cd scripts/emotion && /secondary/hyst-env/emotion/bin/python -m unittest`.
The five repository checks passed before the first edit and again after the last.

#### To rerun

Caches are complete, so: `python extract.py baseline && python check1.py` (stems baseline is the
default; `--baseline mix` for the mix-only one), then `encode.py` / `report.py` with the pick's
components (`/secondary/hyst-env/encode_songs.sh`, `make_report.sh`). A pick containing
`baseline_stems` needs `--stems-dir` for each song.
Nothing here says the arm will look emotional: stage 4 is the only test of that.

### B workspace parked — verdict of 2026-10-12 (written 2026-10-13)

Round 2's blind test did not separate the modes: the user could not tell
`Off`, `Rehearsed` and `Schematic` apart ("all 3 are mostly good"). Under the
round-2 rule a tie is a loss, but the user chose to **park** B rather than
delete it: `workspace.rs` and its wiring stay in the tree, `Off` stays the
default and still reproduces version 47 byte for byte.

Measured cause, from the user's own look at the exports (Presence, Rehearsed):

- **The hand shell caps elevation at 79°.** Presence's median hand elevation
  is 49°, and the hand sits pinned at the lid 8–10 % of the time. Every "rise"
  B asks for (lift, gain, voice) saturates against that lid, so the fields
  move little that can be seen. Stage 2 of `docs/EMOTION.md` (open shell)
  removes the lid.
- **The held breath reads as low energy.** Tension shrinks figures and slows
  the figure clock before a drop; on screen that is a smaller, slower dance,
  not suspense.

B is not part of the emotion pipeline. Its expectation signals were not
computed for check 1 (no beat grids or phrase memory on 45 s clips). Revisit
only if a later stage needs expectation as an input.

### Body study, step 1: generator and 2a sweep (stop 1) — 2026-10-13

Rules: `docs/BODY_STUDY.md`, unchanged. Code: `crates/hyst-compile/src/body.rs`
(generator, check 2a, 37 descriptors), `crates/hyst-previz/examples/body_study.rs`
(`sweep`, `fill`, `html`), `scripts/body_study/regions.py`. Planner, `ensemble_preview.rs`
and `figures.rs` untouched: `three.sh` exports compared with `cmp` against
`hexagon-47.html`, `five-years-hexagon.html`, `presence-hexagon.html`, identical before and
after. Data in `/secondary/hyst-data/bodystudy/` (outside git). **Not verified by eye.**

Generator: phrase of moves in joint space; the ranges and why are in the doc comments.
Constants the builder chose: knots every 0.05 s, moves 1.0–1.8 s apart, depth 0.3–1.0,
arrival skew 0.75–1.4, bursts 1–3, follow-through 0–15 % at 0.8–1.4 Hz, wander yaw ±15°
and roll ±30° (capped to 0.35 of the speed limit per move), breath 8°/12°, period
3.3–12 s. Each move's size is capped by the acceleration and speed budget of its duration.

Sweep (seed 20261013): first draft (no cap) passed 2000 of 48,939 (4 %), nearly all
sustained, light, bound, direct. Cap added, then wander cap: 2000 of 3,457 (58 %).
Remaining rejections: floor 1357, joint range 5, kinematic 95. Low height and deep curl
fail the floor (pass rate 7 % at height decile 0, 97 % at decile 9). Stretch used,
1.1^0..1.1^7: 162, 41, 98, 337, 581, 459, 256, 66; median 1.46.

Regions (37 descriptors, z-score, farthest-point): r = 4.52, centre distance min 12.56,
mean 17.50. Seven of 8 centres are single outlier clips (z up to 8.6 on shoulder, elbow or
wrist speed and acceleration, heavy right tails). After `fill`: region 4 has 24 members,
regions 0, 2, 6 reach 9 (clones of one body vector, new seeds), regions 1, 3, 5, 7 stay at
2, 2, 1, 1. By the study's rule, the study stops here. Triplets not built.

### Body study, step 1 rerun under the addendum (stop 1 again) — 2026-10-13

Rules: `docs/BODY_STUDY.md` with its 2026-10-13 addendum (unchanged). Data in
`/secondary/hyst-data/bodystudy/r2/` (`sweep.json`, `regions.json`, `fill.json`,
`first/{a,b,c}.{html,mp4}`), outside git. `scripts/body_study/report.py` prints the sweep
numbers below. **Not verified by eye.** The study stops at the region rule (below): no
triplets, no `answer.html`.

Code (`hyst-compile` and `hyst-previz` only):
- `body.rs`: `LIMITS` (one table: yaw 120/600, shoulder 90/300, elbow 150/1000, wrist bend
  200/2000, roll 250/3000 deg/s, deg/s2). `violations()` samples the score's own quintic
  curve at 1 kHz (speed by first difference, acceleration by second difference), runs
  `validate` on the rig's own envelope (240 deg/s, 8000 deg/s2, unchanged), then hand speed,
  jolt and floor at 60 fps; every broken rule is named. `check_2a` returns the first.
  `feasible_traced` also returns the rules broken at stretch 1.
- **Score format, additive**: `JointKnot.acceleration_degrees_per_second2` (serde default,
  omitted when empty, so every older score and export is unchanged). Reason: with zero
  acceleration at every knot the quintic renders 1.3-1.5x the acceleration of the curve it
  samples, at any knot spacing (tested 0.05, 0.02, 0.01 s: 1.32, -, 1.48). The generator now
  writes the true acceleration; `channel_bounds` (the `validate` proof) uses it too. Motion
  before the change: the move itself peaked at 299.97 of 300 deg/s2 on a probe, the rendered
  curve at 1.3-1.5x.
- Move-size cap per joint from that joint's own limits, no factor on them. Exact numeric peaks
  of the skewed burst profile (`profile_peaks`) and of the follow-through ring with its 0.15 s
  ramp (`ring_peaks`) replace the old 5.77, 1.875, 1.5 and 0.45/0.8 constants. Taken off the
  limit before the move gets it: breath on shoulder and elbow (exact peak), wander on yaw and
  roll. The ring starts after the move ends, so it is a separate bound, not a sum.
  Remaining factors: **0.5 on wander** (it shares yaw/roll with the move and the two can
  peak together; the move gets the other half). Wander shape bounds 2 pi w/dur and
  6 pi^2 w/dur^2 are upper bounds from the shape's components. Nothing else.
- Knots every 0.05 s as before. Tests: 7 body tests (rendered-curve check names joint and
  limit; wrist range > shoulder range for a sudden strong clip); workspace CPU tests (165,
  `hyst-render` excluded) pass; clippy -D warnings clean on compile/previz/output/cli.

Sweep (seed 20261013): **3,516 attempts, 2,000 passed.** Rejected 1,516: at the top of the
ladder (1.95) the first rule broken is floor 1,510, joint range 6, nothing else. Rules broken
at stretch 1 over all rejected clips (a clip can break several): floor 1,514, shoulder accel
841, elbow accel 465, hand jolt 149, wrist bend accel 127, hand speed 75, roll `validate`
72, base yaw accel 59, roll speed 11, yaw speed 2, roll accel 17, joint range 7. Rejection by
decile is in `report.py` output: height decile 0 rejects 322/338, decile 9 rejects 3/342;
curl_extension decile 0 250/345, decile 9 57/370; every other parameter 120-190 per ~350 in
every decile (no other parameter matters). Stretch histogram (1.1^0..7): 501, 1308, 78, 27,
15, 20, 30, 21. Clips clean at stretch 1: 501 of 2,000. Rules broken at stretch 1 among the
2,000 that pass: shoulder accel 1,256, elbow accel 762, hand jolt 240, wrist bend accel 174,
floor 138, base yaw accel 84, roll `validate` 65, roll accel 30, hand speed 29, roll speed 8,
shoulder/elbow/yaw speed 1-2. These are mostly about 10 % over (probe: rendered 1.14 at worst
on the shoulder, caused by consecutive moves overlapping through joint delays and the
previous move's ring); the ladder's first step (1.1) takes them. Roll `validate` failures:
the roll's limit (250 deg/s) is above the rig's envelope (240).

Low (<0.2) against high (>0.8) medians; p90 joint speed deg/s (yaw / shoulder / elbow / wrist
bend / roll) and total joint motion deg (same order; sum), motion of the rendered 8 s:
- time: n 358 / 436. p90 low 44.0 / 17.0 / 26.7 / 13.5 / 93.4; high 15.9 / 8.8 / 22.7 / 18.2 /
  68.5. Total low 143 / 62 / 93 / 42 / 319 (683); high 39 / 29 / 63 / 42 / 171 (351).
- weight: n 411 / 403. p90 low 27.4 / 11.8 / 19.6 / 10.4 / 73.2; high 28.1 / 14.7 / 31.7 /
  22.8 / 93.3. Total low 85 / 40 / 66 / 27 / 206 (425); high 80 / 47 / 92 / 56 / 271 (579).
- flow: n 389 / 375. p90 low 30.4 / 14.7 / 28.3 / 16.8 / 85.0; high 26.9 / 12.7 / 26.4 / 16.2 /
  82.5. Total low 85 / 45 / 82 / 40 / 234 (514); high 86 / 44 / 81 / 47 / 246 (522).
- space: n 390 / 412. p90 low 31.3 / 13.9 / 27.3 / 16.2 / 52.9; high 30.3 / 14.6 / 26.5 /
  16.6 / 109.3. Total low 88 / 45 / 82 / 45 / 136 (414); high 93 / 46 / 80 / 42 / 340 (621).
Sudden clips (time > 0.8) still move less than sustained ones at yaw, shoulder, roll (total
351 against 683). It is the acceleration budget: a burst of 0.1 s at 600 deg/s2 is about 1
degree on yaw. The wrist moves the same total and faster in sudden clips. "Weight" now
differs at the elbow, wrist and roll (p90 22.8 against 10.4 on the wrist). Flow differs by
under 10 % in either measure (follow-through is small: 0.15 of the move at most).

Regions (rank-normalised descriptors, 1,000 candidate centres with d9 at or under the median
1.091; centres clips 785, 1627, 497, 815, 1383, 897, 1972, 1506): **r = 0.691**.
Centre-to-centre distance min 2.228, mean 2.991 (a quarter: 0.748). Mean within-region
pairwise distance 0.679 / 0 / 0.678 / 0.676 / 0 / 0 / 0 / 0 (regions with one member have 0).
Members before fill: 2, 1, 2, 3, 1, 1, 1, 1. After fill (clones of members' body vectors,
fresh seeds, kept inside the ball, 200 tries): **9, 9, 9, 6, 9, 7, 9, 9**. Regions 3 and 5
stay short (200 tries each). **The rule stops the study here.** The 9th-nearest neighbour of
a median clip is 1.09 away, farther than r, so the 2,000 clips alone never fill a ball: the
filled members are clones of one or two body vectors with other content seeds. Whether that
counts as a region is a decision for you; I did not change r, the fill or the rule.
Stretch (median / max) of region members before fill: 1.0/1.0, 1.1/1.1, 1.1/1.1, 1.61/1.77,
1.0/1.0, 1.1/1.1, 1.1/1.1, 1.0/1.0.

Single clips for a first look (not test clips, silent, 8 s) in `r2/first/`: a (body 1238:
time 0.00, weight 0.13, flow 0.08, stretch 1.0), b (1071: time 0.90, weight 0.87, flow 0.94,
stretch 1.1), c (1792: space 0.98, extension 0.88, time 0.04, stretch 1.1). `SendUserFile`
could not deliver (not a project thread); paths above. Body vectors and seeds are in
`sweep.json`.

Unchanged: `three.sh` exports compared with `cmp` against `hexagon-47.html`,
`five-years-hexagon.html`, `presence-hexagon.html`: all three identical. The three tmp files
it made were deleted; older `tmp-45-*`, `tmp-46-*` files from earlier sessions were not mine
and are left. Frozen `src/` and `tools/`, no hardware.

### Body study, step 1 under addendum 2: new generator, sweep, regions (stop 1) — 2026-10-13

Rules: `docs/BODY_STUDY.md` with both addenda (unchanged). Data in
`/secondary/hyst-data/bodystudy/r3/` (`sweep.json`, `report.txt`, `regions.json`,
`fill.json`, `first/{a,b,c}.{html,mp4}`, `first/silence.m4a`), outside git. **Not verified
by eye.** Stopped at ★ 1: no triplets, no `answer.html`.

Why: the user saw three 8 s first-look clips as hardly moving, and the sudden/strong/free one
as jittery. The old generator sized every move from body weight ("depth") and the
acceleration budget of a short slot, and its sudden and free settings made several bursts
and a ring on every joint.

Generator changes (`crates/hyst-compile/src/body.rs`, `Motion` rewritten; ranges in its doc
comment):
1. Travel. Each move goes to a new posture. Base yaw alternates sides of a span drawn per
   clip from 220 to 320 degrees, with each target in the outer 35 % of its side. The shoulder
   alternates between the lowest and highest 35 % of its draw. Shape parameters set 0.25 of
   the posture draw, so they bias where the targets fall, never whether they spread. Weight no
   longer sets move size. Reason: the brief's item 1 and the floors below.
2. Time. Velocity ramps cover 100 % of the move (sustained, a bell) to 45 % (sudden, quick
   cruise). Duration is the shortest legal one times 1.7 (sustained, no hold) to 1.0
   (sudden), then a hold of time x 0.6..1.4 s. Breath runs through the hold. The multi-burst
   profile is deleted. Reason: item 2.
3. Weight sets the deceleration ramp's share of the ramps: 65 % (light, floats in) to 30 %
   (strong, firm stop).
4. Flow. Elbow and wrist bend overshoot by 25 % x flow of their move, then settle once over
   0.4 x sqrt(flow) of the move's duration. Other joints get no overshoot. The ring and its
   frequency/decay are deleted. Reason: item 3.
5. Limits. Each move's duration comes from one sampled pass of the move at unit duration.
   Joint speed scales as 1/T and acceleration and jolt as 1/T^2, so this gives the exact
   shortest T for each joint's own `LIMITS`, hand speed 1.2 m/s and jolt 9 m/s^2. The roll's
   speed is capped at the rig's 240 deg/s envelope so `validate` can pass. Breath's exact peak
   is taken off the shoulder and elbow limits. The 0.5 wander factor and the per-joint
   move-size caps are deleted. The one common duration is set by whichever joint or hand rule
   binds, usually yaw at 120 deg/s or hand speed. Joint delays and breath are left out of
   this pass, and the stretch ladder covers them. Reason: item 4. **Open question for you:**
   the elbow and wrist share that duration, so they move far under their own limits. If
   "uses its own limits" means each joint at its own pace, say so.
6. A target whose path or pose breaks the floor (breath at either extreme) is drawn again,
   up to 30 times.

Check 2a (addendum 2): 16 s clips, stretch about 8 s. Floors use `movement()`: hand path
3.67 m, box side 0.74 m, base turn 161 deg. Tests (8 body tests): 321 knots, centre at knot
160, sudden has a hold of at least 0.6 s and overshoot only on elbow/wrist, sustained/bound
has no hold or overshoot, the profile is monotone from 0 to 1, and a mid body passes the
floors. Workspace CPU tests (hyst-render excluded) pass. Clippy -D warnings is clean on
compile/previz/output/cli, and fmt is clean.

Sweep (seed 20261013): **2,082 attempts, 2,000 passed.** First rule broken among the 82
rejected at stretch 1.95: floor 69, hand path 13. Rules broken at stretch 1 by the rejected
clips: floor 75, hand path 7, hand speed 6. Rejections by decile, of about 200 per decile:
height 31, 26, 12, 5, 0, 1, 4, 1, 1, 1; curl_extension 19, 17, 8, 12, 9, 3, 8, 3, 2, 1;
breath_depth 2, 4, 3, 2, 3, 4, 9, 14, 14, 27; every other parameter 1-15 per decile. Stretch
histogram (1.1^0..7): 1904, 73, 4, 7, 5, 3, 1, 3. Rules broken at stretch 1 among the 2,000
that passed: hand speed 69, floor 27; 1,904 were clean at stretch 1.

Low (<0.2) against high (>0.8) medians. p90 joint speed is deg/s and total joint motion is
degrees, both in the order yaw / shoulder / elbow / wrist bend / roll. Movement is hand path
m / box m / base turn deg:
- time (n 380 / 411): p90 low 69.5 / 13.6 / 12.3 / 6.2 / 23.7, high 103.0 / 20.1 / 17.9 /
  10.6 / 40.4. Total low 468 / 98 / 93 / 34 / 144 (sum 842), high 751 / 148 / 126 / 56 /
  212 (1301). Movement low 4.84 / 1.12 / 230, high 7.56 / 1.14 / 239.
- weight (373 / 416): p90 low 85.9 / 17.0 / 15.5 / 8.1 / 29.6, high 80.3 / 16.2 / 14.4 / 7.7
  / 29.7. Total low 630 / 127 / 115 / 45 / 165 (1111), high 575 / 120 / 106 / 43 / 167
  (1028). Movement low 6.43 / 1.13 / 235, high 5.94 / 1.13 / 236.
- flow (419 / 380): p90 low 83.6 / 16.7 / 14.1 / 7.9 / 32.1, high 84.3 / 16.9 / 16.0 / 8.3 /
  28.2. Total low 664 / 130 / 106 / 44 / 191 (1158), high 573 / 121 / 118 / 46 / 160 (1034).
  Movement low 6.67 / 1.14 / 235, high 5.97 / 1.13 / 234.
- space (423 / 389): p90 low 85.8 / 16.9 / 15.3 / 8.5 / 15.7, high 80.0 / 15.4 / 14.8 / 7.1 /
  46.8. Total low 637 / 128 / 111 / 50 / 91 (1020), high 563 / 115 / 111 / 41 / 260 (1117).
  Movement low 6.49 / 1.14 / 236, high 5.86 / 1.13 / 234.
Weight and flow move these medians by under 10 %, so their effect is in profile shape, which
these measures do not separate. Yaw carries most of the motion, and the wrist bend totals
34-56 degrees over 16 s.

Histograms over all 2,000 clips, as range:count:
- Hand path, m: 3.69-4.37:83 4.37-5.04:312 5.04-5.72:349 5.72-6.40:400 6.40-7.08:350
  7.08-7.75:278 7.75-8.43:164 8.43-9.11:47 9.11-9.78:14 9.78-10.46:3.
- Box, m: 0.81-0.85:1 0.85-0.90:4 0.90-0.95:14 0.95-0.99:64 0.99-1.04:138 1.04-1.09:271
  1.09-1.13:507 1.13-1.18:547 1.18-1.23:394 1.23-1.27:60.
- Base turn, deg: 164-179:25 179-194:111 194-209:270 209-224:360 224-239:326 239-253:339
  253-268:281 268-283:186 283-298:72 298-313:30.

Regions (rank space; candidate centres are the 1,000 clips with d9 at or under the median,
0.999): **r = 0.794**. Centre-to-centre distance min 2.205, mean 3.099 (a quarter: 0.775).
Initial centres 1739, 926, 194, 1663, 935, 386, 1267, 1048. Within-region mean distances
0.703, 0.689, 0.768, 0, 0.729, 0.677, 0, 0. Members before fill: 12, 4, 2, 1, 4, 2, 1, 1.
Replacement (`body_study fill`, which now holds r, recomputes every region's membership after
each replacement, and never reuses a dropped centre; `regions.py` now writes `candidates`).
Each step is old > new, with the members after the failed fill:
- region 3: 1663>1491 (5), 1491>320 (3), 320>136 (2), 136>1715 (4), 1715>1694 (4),
  1694>675 (7), 675>1464 (4), 1464>1336 (3), 1336>1740 (5), 1740>118 (1), 118>97 (5);
- region 5: 386>829 (8), 829>277 (5), 277>192 (6), 192>797 (8), 797>1210 (7), 1210>193 (7),
  193>1695 (3), 1695>1815 (5), 1815>219 (3), 219>936 (6), 936>1977 (6), 1977>1478 (7),
  1478>1055 (2), 1055>772 (8);
- region 6: 1267>334 (4).
26 replacements. Final centres 1739, 926, 194, 97, 935, 772, 334, 1048. Members after fill:
12, 9, 9, 9, 9, 9, 9, 9. Of these, 12, 4, 2, 4, 4, 4, 2, 1 are sweep clips and 0, 5, 7, 5,
5, 5, 7, 8 are made (clones of members' body vectors with new seeds). Within-region
distances after replacement were not recomputed.

Single first-look clips (16 s, silent, stretch 1.0, not test clips) in `r3/first/`.
Reversals count frames where the hand's velocity points against its velocity at the
previous frame faster than 0.05 m/s:
- a: sweep clip 491, time 0.03, weight 0.09, flow 0.06. Hand path 4.98 m, box 1.07 m, base
  turn 210 deg, top hand speed 0.69 m/s, 1 reversal.
- b: clip 665, time 0.99, weight 0.96, flow 0.94. 7.14 m, 1.11 m, 212 deg, 1.19 m/s, 3
  reversals. At 10 s the disc rises out of the top of the frame (camera unchanged).
- c: clip 994, space 0.98, curl_extension 0.99. 5.92 m, 1.24 m, 257 deg, 0.87 m/s, 3
  reversals.
Body vectors and seeds are in `sweep.json`.

Unchanged: `three.sh` exports compared with `cmp` against `hexagon-47.html`,
`five-years-hexagon.html` and `presence-hexagon.html`: all three are identical. Its three tmp
files were deleted; older `tmp-*` files from earlier sessions are left. Frozen `src/` and
`tools/` were not touched. No hardware was driven.

### Body study, step 1 under addendum 3: per-joint generator, sweep, regions (stopped at the region rule) — 2026-10-13

Rules: `docs/BODY_STUDY.md` with all three addenda (unchanged). Data in
`/secondary/hyst-data/bodystudy/r4/` (`sweep.json`, `sweep.log`, `report.txt`, `regions.json`,
`regions.txt`, `fill.json`, `fill.txt`, `first/{a,b,c}.{html,mp4}`, `first/silence.m4a`),
outside git. **Not verified by eye.** The final region check fails (below), so the study
stops at ★ 1: no triplets, no `answer.html`.

Why: the user on the three r3 clips: a "almost all is base moving, the elbow joint not at
all and almost no disc spin"; b "spin, stop, reposition ... mechanical looking, like an
assembly line machine"; c "somewhere in between". Cause in the generator: one move duration
for all joints, set by the slowest (usually the base); all joints starting and stopping
together; "sudden" as move then dead stop.

Generator changes (`crates/hyst-compile/src/body.rs`, `Motion` rewritten; ranges and reasons
in its doc comment):
1. Own pace per joint. Each joint has its own list of moves, with lengths drawn from its own
   range: base 1.8-3.0 s, shoulder 1.5-2.6, elbow 0.8-1.3, wrist bend 0.6-1.1, roll 0.7-1.3.
   Initiation picks the leading joint (base, shoulder, elbow or wrist bend), which runs its own
   moves. Every other joint starts a move at one of the leader's move starts plus its
   succession delay (0.12 s, plus 0-0.3 s along the chain, its direction set by succession
   direction). It picks the leader starts nearest its own pace and splits a long gap into its
   own shorter moves (each 0.75-1.25 of an equal split). If a joint's own limits need longer
   than the gap, the move takes the following gaps too, so it still reaches its target.
   Reason: item 1, no shared duration.
2. No dead stops. Each move lasts its gap times 1 + overlap (0.3 sustained to 0.12 sudden), so
   the next move of the same joint starts before the previous ends and the two add up. Only
   base and shoulder hold, and only when sudden (their moves last the gap times 1.3 down to
   0.8). Elbow, wrist and roll never hold. Breath runs throughout. Time sets the accelerating
   ramp, 50 % (a bell) down to 12 % (a sharp start) of every move. Weight sets how much of the
   rest decelerates. On base and shoulder that is 100 % down to 35 % (cruise, then a firm
   arrival). On elbow, wrist and roll it is 100 % down to 75 %, so they keep settling when the
   heavy joints arrive. Reason: item 2.
3. Flow. Elbow, wrist bend and roll pass their target by 25 % x flow of the move and settle
   back once, monotonically, over 0.4 x sqrt(flow) of its duration. Base and shoulder never
   overshoot. Reason: item 3.
4. Every joint travels. Base yaw alternates sides of a 240-330 degree span, with targets in
   the outer 25 % of each side, so two targets are at least 180 degrees apart; the r3 span
   allowed 143, under the 161 turn floor. The shoulder alternates between its lowest and
   highest 35 % of 10 + breath .. 95 degrees of elevation. The elbow alternates between the
   most curled and most straight 35 % of -30 (bent up, new) .. 95 degrees. The wrist bend
   alternates sides by 20-70 degrees about the arch's centre. The roll turns 30-110 x 0.6-1
   degrees per move (space). Shape parameters set 0.25 of each draw. Sizes were chosen on a
   200-clip probe so that the joints' shares come near version 47's. Reason: item 4, every
   joint clears its floor.
5. Floor during generation. Joints are drawn shoulder, elbow, wrist, then base, then roll.
   While a joint is drawn, the points placed by the joints drawn so far must stay above the
   floor, and the last of them above the floor plus the disc radius, with breath at either
   extreme; the wrist checks the whole floor rule. Elbow and wrist bends are also capped so
   their link end stays 5 mm over floor plus disc. A draw is rejected if it fails these
   checks or lands under 15 degrees from the current angle. After 30 rejected draws the joint
   lifts 25 degrees (shoulder 15); if that fails too, it stays put for that move.
6. Limits. Each move lasts at least what its joint's own `LIMITS` need. The roll's speed is
   capped at the rig's 240 deg/s envelope, and breath's peak is taken off the shoulder and
   elbow limits. Elbow, wrist and roll moves are sized against 0.6 of their speed limit,
   because overlapping moves add up (first probe: wrist at 1.1-1.55x its limit). The base's
   speed is capped so the hand's largest horizontal radius over the move gives at most 0.75
   of the hand speed rule (first probe: hand at 1.1-1.6x). Then the whole motion, but not
   breath, is slowed by one factor, if needed, to keep every joint under 0.98 of its limits
   and the hand under 0.95 of its speed and jolt rules over the clip. The 0.98 covers the
   gap between this pass's 240 Hz sampling and the 1 kHz check.
7. Clips open mid-motion: moves start at -3 s.

Check 2a, addendum 3 (`violations`):
- Per-joint motion floors: `MIN_JOINT_DEG` = 386 / 148 / 299 / 454 / 370 degrees per 16 s,
  measured with `joint_motion` at 60 fps.
- In frame: `frame_margin` projects every world point exactly as `ensemble.html`'s `project`
  does, plus the disc's radius around the hand point; it must stay ≥ 20 px inside the
  1280 x 720 frame.
- Study camera: the template's solo camera with the same yaw (-0.6), pitch (0.35) and focal
  length, moved from 2.1 m to 3.05 m and aimed at z 0.35 instead of 0.3. That is the smallest
  distance, in 0.05 m steps, at which every point within the arm's reach plus the disc stays
  20 px inside the frame (sampled sphere).
- `body_study html` writes these two numbers into its own copy of the template and fails if
  the template's camera strings change. `ensemble.html` is unchanged.
- `body_study fill` now rechecks the quarter rule and r on the final centres and members.

Tests (12 body tests):
- the camera matches the template's centre, and a point out of frame is caught;
- a typical clip clears every floor and stays in frame;
- elbow and wrist move more often and on shorter moves than base and shoulder, starting at
  other times;
- sudden and sustained clips: no 60 fps frame where every joint is under 2 deg/s, and elbow,
  wrist and roll never still for 0.5 s or more;
- free overshoots elbow, wrist and roll only, settling once and monotonically; bound never
  overshoots;
- sudden plus strong gives a sharp start, a firm heavy arrival and a long light settle.

Other checks: workspace CPU tests (171, `hyst-render` excluded) pass; clippy -D warnings is
clean on compile/previz/output/cli; fmt is clean.

Sweep (seed 20261013): **2,068 attempts, 2,000 passed.** Rejected 68.
- First rule broken at stretch 1.95: joint range (`validate`, joint not named) 26, base yaw
  motion 20, hand path 19, floor 2, shoulder motion 1.
- Rules broken at stretch 1 by the rejected clips: joint range 34, base yaw motion 23, hand
  speed 8, shoulder motion 4, floor 2.
- Rejections by decile (about 200 attempts per decile):
  - time 3, 5, 5, 4, 2, 4, 6, 12, 13, 14;
  - weight 12, 19, 6, 9, 8, 2, 6, 3, 1, 2;
  - flow 4, 3, 3, 3, 7, 6, 12, 7, 9, 14;
  - arch 14, 12, 9, 1, 3, 2, 5, 10, 4, 8;
  - curl_extension 10, 11, 2, 9, 7, 6, 5, 6, 5, 7;
  - every other parameter 2-11 per decile.
  Full table in `report.txt`.
- Stretch histogram (1.1^0..7): 1773, 195, 26, 2, 2, 2, 0, 0.
- Rules broken at stretch 1 among the 2,000 that passed: hand speed 213, joint range 15;
  1,773 were clean at stretch 1.

Per joint over the 2,000 clips, total motion histogram (degrees, range:count) and share of
the summed motion (median, p10, p90):
- base yaw: 387-443:80 443-499:264 499-555:445 555-611:447 611-666:307 666-722:211
  722-778:145 778-834:60 834-890:36 890-946:5. Share 0.196 (0.170, 0.231).
- shoulder: 151-182:51 182-213:151 213-244:312 244-275:452 275-307:478 307-338:341
  338-369:153 369-400:49 400-431:10 431-462:3. Share 0.094 (0.074, 0.114).
- elbow: 309-361:7 361-413:24 413-465:78 465-517:209 517-569:405 569-621:529 621-673:397
  673-725:235 725-777:83 777-829:33. Share 0.201 (0.172, 0.230).
- wrist bend: 464-544:9 544-623:37 623-703:107 703-782:304 782-862:504 862-941:530
  941-1021:336 1021-1100:130 1100-1179:38 1179-1259:5. Share 0.292 (0.257, 0.322).
- roll: 390-453:19 453-516:92 516-580:307 580-643:602 643-707:573 707-770:269 770-834:99
  834-897:30 897-961:7 961-1024:2. Share 0.216 (0.191, 0.244).

For comparison, from the brief: v47's shares are base 26 %, wrist bend 24, roll 24, elbow 17;
the r3 sweep's were base about 60 %.

Low (< 0.2) against high (> 0.8) medians. Joint values are given as yaw / shoulder / elbow /
wrist bend / roll. Movement is hand path m / box m / base turn deg.
- time (n 388 / 403): p90 speed low 65.9 / 30.4 / 68.6 / 98.8 / 82.4, high 69.6 / 30.5 /
  70.3 / 101.3 / 84.2. Total low 653 / 282 / 618 / 892 / 655 (sum 3115), high 527 / 233 /
  583 / 852 / 643 (2844). Movement low 7.96 / 1.14 / 252, high 7.27 / 1.13 / 255.
- weight (355 / 425): p90 low 67.6 / 34.3 / 68.1 / 97.7 / 83.3, high 66.5 / 30.3 / 70.1 /
  99.4 / 82.9. Total low 532 / 273 / 578 / 827 / 632 (2849), high 645 / 278 / 618 / 902 /
  647 (3110). Movement low 7.32 / 1.13 / 256, high 8.00 / 1.14 / 253.
- flow (428 / 370): p90 low 67.6 / 32.8 / 63.0 / 92.7 / 80.7, high 67.4 / 31.5 / 74.9 /
  104.7 / 86.3. Total low 588 / 280 / 559 / 834 / 625 (2900), high 569 / 267 / 640 / 892 /
  659 (3054). Movement low 7.67 / 1.15 / 252, high 7.78 / 1.11 / 256.
- space (423 / 386): p90 low 71.8 / 31.7 / 68.6 / 98.1 / 85.8, high 62.9 / 32.2 / 68.7 /
  99.3 / 86.6. Total low 623 / 274 / 594 / 850 / 704 (3080), high 544 / 279 / 603 / 878 /
  642 (2940). Movement low 7.88 / 1.14 / 253, high 7.37 / 1.13 / 255.
These medians move by under 20 % across any of the four parameters. The parameters now
change profile shape, holds, overshoot and wander; p90 speed and total motion do not
separate these.

Histograms over the 2,000 clips:
- Hand path, m: 4.49-5.11:4 5.11-5.72:19 5.72-6.34:88 6.34-6.95:309 6.95-7.57:494
  7.57-8.18:523 8.18-8.80:353 8.80-9.41:169 9.41-10.03:34 10.03-10.64:7.
- Box, m: 0.83-0.88:3 0.88-0.93:19 0.93-0.98:68 0.98-1.03:168 1.03-1.08:308 1.08-1.13:430
  1.13-1.18:480 1.18-1.23:349 1.23-1.28:148 1.28-1.33:27.
- Base turn, deg: 186-200:11 200-214:76 214-228:260 228-242:355 242-256:358 256-270:370
  270-284:292 284-298:187 298-312:81 312-326:10.

Regions (rank space; candidate centres are the 1,000 clips with d9 at or under the median,
1.374):
- **r = 0.903.** Initial centre-to-centre distance min 2.287, mean 2.977 (a quarter: 0.744).
- Initial centres 1706, 1966, 357, 1016, 1582, 365, 1434, 1017. Members before fill: 1 in
  every region (only the centre; its within-region distance is 0).
- Fill and replacement: **814 replacements**, each with the reason "under 9 members after
  fill". Per region: 7, 29, 2, 108, 145, 260, 212, 51. Every replacement (old > new, members
  after the failed fill) is in `r4/fill.txt` and `fill.json`.
- Final centres 1919, 644, 1264, 1074, 1102, 1457, 1277, 1025. Members after fill: 11, 9, 9,
  9, 9, 9, 9, 9. Of these, 9, 1, 1, 1, 2, 1, 1, 1 are sweep clips; the rest are made from
  members' body vectors with fresh seeds.
- **Final check (addendum 3): broken.** Final centre-to-centre min 1.484, mean 2.531, a
  quarter 0.633. Mean within-region distances 0.996, 0.935, 0.848, 1.006, 1.012, 0.901,
  0.944, 1.018: all eight are over the quarter. r = 0.903 is under the final minimum centre
  distance 1.484. **The study stops here.**
- What the numbers say: the new clips spread more evenly in descriptor space (d9 median 1.374
  against r3's 0.999). No clip but the centre falls inside r of any initial centre. Clones of
  one body vector with fresh seeds sit about 0.85-1.0 apart. So a ball holding 9 clips cannot
  have a within-distance under a quarter of the centre spacing. Changing r, the fill or the
  rule is your decision; I did not.

Single first-look clips (16 s, silent, stretch 1.0, not test clips) in `r4/first/`, recorded
with `record-ensemble.cjs` from the study-camera pages. Units: hand path m, box m, base turn
deg, top hand speed m/s. Per joint, in the order yaw / shoulder / elbow / wrist bend / roll:
total motion in degrees, then the longest time under 2 deg/s in seconds.
- a, sustained/light/bound: sweep clip 494 (time 0.03, weight 0.09, flow 0.06). Movement 6.60
  / 1.05 / 213 / 0.90. Motion 637 / 197 / 583 / 981 / 650. Still 0.13 / 1.17 / 0.07 / 0.03 /
  0.03. Frame margin 53 px.
- b, sudden/strong/free: clip 670 (time 0.99, weight 0.96, flow 0.94). Movement 8.25 / 1.10 /
  304 / 1.14. Motion 613 / 227 / 695 / 770 / 597. Still 1.93 / 1.15 / 0.08 / 0.05 / 0.05.
  Frame margin 39 px.
- c, indirect/extended: clip 53 (space 0.97, curl_extension 0.98). Movement 6.04 / 1.06 /
  252 / 1.13. Motion 561 / 208 / 652 / 943 / 609. Still 0.80 / 0.13 / 0.05 / 0.05 / 0.13.
  Frame margin 35 px.
The longest still time over any joint is base 1.93 s (b, its sudden hold) and shoulder 1.17
s (a, where breath alone moves it between moves).
Body vectors and seeds are in `sweep.json`.

Unchanged: `three.sh` exports compared with `cmp` against `hexagon-47.html`,
`five-years-hexagon.html` and `presence-hexagon.html`: all three are identical. Its three
tmp files were deleted. Frozen `src/` and `tools/` were not touched. No hardware was driven.

### Body study, step 1 under addendum 4: regions as one body vector (stopped at the separation rule) — 2026-10-13

Rules: `docs/BODY_STUDY.md` with all four addenda (unchanged). Data in
`/secondary/hyst-data/bodystudy/r5/` (`regions.json`, `regions.log`, `report.txt`), outside
git. Reused, not regenerated: `r4/sweep.json` and `r4/regions.json` (sorted columns,
candidates). Generator (`body.rs`) and check 2a untouched. **Not verified by eye.** The
separation rule fails with the candidates exhausted, so the study stops before ★ 2: no
triplets, no clips rendered, no answer page in the repo.

Built:
- `crates/hyst-compile/src/body_regions.rs` (new): rank against the sweep's sorted columns
  ((values below + 0.5) / 2,000), seed spread w (mean pairwise distance of a region's 9
  rank vectors), position m (their mean), all pairs and their ratio |m_i - m_j| / max(w_i,
  w_j), the worst pair, farthest-point order, and `select`, the addendum-4 loop: build the 8
  initial centres; a region short of 9 clips is replaced; while a pair has a ratio under
  1.5, the later-chosen centre of the pair with the smallest ratio is replaced by the
  candidate farthest from the 7 kept centres (never a centre used before); stop when the
  rule holds or no candidate is left. On a stop the last full set of 8 is kept for the
  report. 7 tests on small synthetic sets: the rule takes the larger spread, ranks, spread
  and position, farthest-point order, replacement of the later-chosen centre of the worst
  pair until the rule holds, a short region replaced, exhaustion stops.
- `body_study regions SWEEP REGIONS OUT` (`crates/hyst-previz/examples/body_study.rs`):
  recomputes the 8 initial centres and fails unless they equal `r4/regions.json`'s (they
  do: 1706, 1966, 357, 1016, 1582, 365, 1434, 1017). A region = the centre sweep clip + the
  first 8 seeds that pass check 2a (`body::feasible`, the stretch ladder, floors, frame).
  A failing seed is counted by the first rule it breaks at stretch 1.95.
- `scripts/body_study/report4.py REGIONS.json REGIONS.log`: the step-6 report.

Constants and origin:
- factor 1.5, 9 clips per region, 200 seeds per region, seed 20261015: addendum 4.
- Seed order (mine): a splitmix64 stream started at 20261015 + (centre + 1) x
  0x2545F4914F6CDD1D, 53-bit seeds as `body::draw` gives. It depends only on the centre, so
  a region is the same whenever it is built. Seeds run in batches of the thread count; the
  first 8 passing in seed order are kept, and "tried" counts up to the 8th pass.
- Mean for the first centre: the mean of the 2,000 sweep rank vectors.

Run (twice; the second run only added w to the log; the event lists are identical):
- **992 replacements, candidates exhausted (all 1,000 used). Rule broken.**
- Replacements by reason: 992 separation rule, 0 short regions (every region reached 9
  clips). By slot: 0, 0, 26, 189, 0, 0, 666, 111.
- Worst-pair ratio at each replacement: max 0.860, median 0.581, p90 0.704. None reached
  1.0.
- Seed spread w over all 1,000 regions built: min 1.327, p10 1.674, median 1.925, p90
  2.199, max 2.721. Addendum 4 quoted 0.85-1.0 for clones of one body vector. Those were
  the r4 fill's clips, kept only if they fell inside r = 0.90 of the centre, so that number
  was biased low.
- For scale: two random sweep clips are a median 2.416 apart (p10 1.856, p90 3.066; 20,000
  random pairs). Per descriptor, the variance inside a final region is a median 0.52 of the
  sweep's variance (min 0.13, max 1.08). The seed accounts for about half of what the
  descriptors show.
- Seeds over all builds: 8,252 tried, 252 skipped: joint range (`validate`) 101, hand path
  75, base yaw motion 66, floor 3, base turn 3, hand box 2, shoulder motion 1, wrist bend
  motion 1.

Final set (the last full set of 8 before exhaustion), centres 1706, 1966, 529, 786, 1582,
365, 1919, 183:
- w: 2.225, 1.667, 1.553, 1.679, 1.386, 1.984, 1.944, 1.519.
- Seeds tried (skipped): 8; 8; 8; 10 (hand path 2); 13 (base yaw motion 2, joint range 3);
  8; 8; 8.
- Pairs, i j |m_i - m_j| ratio, smallest ratio first: 0 6 1.376 0.618; 6 7 1.512 0.778;
  5 6 1.607 0.810; 2 5 1.733 0.874; 2 3 1.510 0.899; 5 7 1.786 0.900; 0 7 2.011 0.904;
  0 2 2.029 0.912; 0 5 2.045 0.919; 0 3 2.152 0.967; 1 3 1.656 0.986; 4 5 2.044 1.030;
  1 5 2.062 1.039; 2 6 2.029 1.044; 0 4 2.376 1.068; 3 5 2.183 1.100; 2 4 1.764 1.136;
  1 2 1.908 1.144; 3 6 2.339 1.203; 4 6 2.433 1.252; 0 1 2.856 1.284; 2 7 2.094 1.349;
  1 4 2.302 1.381; 1 6 2.797 1.439; 4 7 2.270 1.494; 1 7 2.503 1.502; 3 4 2.550 1.518;
  3 7 2.567 1.529.
- **Smallest ratio 0.618. 25 of 28 pairs under 1.5.** |m_i - m_j| ranges 1.376-2.856;
  1.5 x the largest w needs 3.337.
- Stretches of the 72 clips (centre first per region):
  - 0: 1.331, then 1.000 x 8;
  - 1: 1.000 x 7, 1.100, 1.000;
  - 2: 1.000 x 9;
  - 3: 1.000 x 9;
  - 4: 1.000 x 9;
  - 5: 1.000 x 4, 1.100, 1.000 x 4;
  - 6: 1.100, 1.000 x 4, 1.100, 1.100, 1.000 x 2;
  - 7: 1.000 x 9.
  Histogram 1.1^0..7: 66, 5, 0, 1, 0, 0, 0, 0.

What the numbers say: a region's position is a mean of 9 clips, so positions sit nearer
the middle of rank space than single clips do. The rule asks for about 1.5 x 1.9 = 2.9
between positions. No pair of positions in any set reached that, and no worst pair got
over 0.86. Changing the factor, the descriptors or the region definition is your decision;
I did not.

Drafts written for ★ 2 but not run, not tested and not committed (rule broken):
`r5/drafts/{triplets.py,render.sh,answer.html,score.py}` (triplet assignment, shuffle with
`random.Random(20261014)`, 72 clip recordings and A | B | C stacks at 3840 x 720, the
answer page, the 2b scorer).

Checks: `cargo test -p hyst-compile -p hyst-output -p hyst-previz -p hyst-cli` passes
(hyst-compile 53, with the 7 new); clippy -D warnings on the same crates with
--all-targets is clean; fmt is clean. `three.sh` exports compared with `cmp` against
`hexagon-47.html`, `five-years-hexagon.html` and `presence-hexagon.html`: all three are
identical; the tmp files were deleted. Frozen `src/` and `tools/` untouched. No hardware
driven.

### Body study, step 1 under addendum 5: triplets, clips and the answer page (★ 2) — 2026-10-13

Rules: `docs/BODY_STUDY.md` with all five addenda (unchanged). Regions: the final set of
`r5/regions.json` of `90cbec8` as stored (centres 1706, 1966, 529, 786, 1582, 365, 1919, 183;
9 clips each; smallest ratio 0.618 against addendum 5's factor 0.6). Nothing rebuilt. Data
in `/secondary/hyst-data/bodystudy/r5/`, outside git. **Not verified by eye.** The study
waits at ★ 2: the user takes the test.

Built:
- `scripts/body_study/triplets.py REGIONS.json R5DIR`: checks the centres and the 0.6
  factor, then builds the 24 triplets. Triplet i: pair from p = i mod 8, odd from
  (p + k) mod 8, k = 1, 3, 5 for i in 0-7, 8-15, 16-23. Each region gives its 9 clips in
  stored order (centre first): clips 0-5 to its 3 pairs in triplet order, clips 6-8 to its
  3 odd appearances (my choice; the documents do not order clips within a region). Order
  and odd position shuffled with Python's `random.Random(20261014)` (shuffle, then
  `randrange(3)` per triplet). Writes `key.json` (per shown triplet: odd position, pair
  and odd region, k, and region, centre, sweep index, body vector, seed, stretch of A, B,
  C; plus m, w, centres), `clips.tsv` and `triplets.tsv`. Checked: 72 distinct clips, each
  region odd 3 times and pair 3 times, every triplet's regions match its key.
- `body_study ladder b SEED S` (new subcommand): fails unless S is the first passing
  stretch on the ladder.
- `scripts/body_study/render.sh R5DIR`: per clip, `body_study ladder`, then `body_study
  html` (study camera, check 2a with the frame rule), then `record-ensemble.cjs` (start 0,
  16 s, `r5/silence.m4a`, which is r4's 16 s of silence). Any failure is listed and nothing
  is stacked. Stacks: ffmpeg `hstack` of the three 1280 x 720 clips at full size, 3840 x
  720, libx264 crf 20, yuv420p, faststart, no audio track, `-map_metadata -1`, named
  `test/t01.mp4`..`t24.mp4` by shown order.
- `scripts/body_study/answer.html`: one triplet at a time, progress "n / 24". Play plays
  once: there are no controls, no pointer events on the video, no context menu or
  picture-in-picture, and any later play or seek is undone. A / B / C and the optional
  text box ("What did the odd one look like?") unlock when the video ends. At the end,
  "Save answers" downloads `answers.json`: `{finished, answers: [{shown, choice, text,
  time}]}`. Videos come from `test/` next to the page, or from `?dir=`. The page has no
  reference to `key.json`. A copy of the page is in `r5/answer.html`.
- `scripts/body_study/test_answer.sh` (+ `test_answer.cjs`): the page in headless Chrome
  at 1366 x 768 on 24 gray dummy videos. Checked: page width 1366 = viewport (no
  horizontal scroll), video 250 px tall, buttons locked until the end, no replay, progress
  text, 24 answers saved with shown/choice/text/time, no request outside `test/`. Passes
  from `file://` and from `python3 -m http.server`.
- `scripts/body_study/score.py ANSWERS KEY`: correct of 24, pass at >= 16, per region found
  as the odd one (of 3) and as the pair of a correct triplet, per k, and the 8 descriptors
  with the largest found-minus-missed difference (the odd region's position m, and |m_odd
  - m_pair|), then the free text. `test_score.py` runs it on a synthetic key and answers:
  16 correct gives PASS, 15 FAIL, 24 "all found". Not run on real answers.
- `r5/HOWTO.txt`: the server command, the URL, and where `answers.json` goes.

Clips (automated checks only):
- All 72 match their stored stretch on the ladder and pass check 2a. The smallest frame
  margin is 27 px (rule 20). Stretches: 66 at 1.0, 5 at 1.1, 1 at 1.331. No clip problems.
- Each clip: 1280 x 720, 480 frames. Each stack: 3840 x 720, 480 frames, 16.000 s, video
  only.
- Stack tags: encoder strings only. The only id-like byte string in the files is "key"
  from x264's `keyint` option, the same in every file.
- Sizes: `test/` 77,341,453 bytes (2,980,505-3,515,610 per stack); `clips/` 112 MB,
  intermediates the page never loads.
- First stacking attempt: ffmpeg read the loop's stdin and skipped lines. It was fixed
  with `-nostdin` and the stacks were remade. The clips were not re-recorded.
- Disclosure: one run of `triplets.py` printed the 24 odd positions to my terminal before I
  removed that print. I have not watched any test clip.

Checks: `cargo test -p hyst-compile -p hyst-output -p hyst-previz -p hyst-cli` passes; clippy
-D warnings with --all-targets is clean on the same crates; fmt is clean. `three.sh` exports
compared with `cmp` against `hexagon-47.html`, `five-years-hexagon.html` and
`presence-hexagon.html`: all three are identical; the tmp files were deleted. Frozen `src/`
and `tools/` untouched. No hardware driven.

### Body study, step 1 under addendum 7: one clip at a time, the counted answer (★ 2) — 2026-10-13

Rules: `docs/BODY_STUDY.md` with all seven addenda (unchanged). Addendum 6 was never built.
The 72 clips, the 24 triplets, the shuffle and `r5/key.json` of `9337b00` are unchanged.
Data in `/secondary/hyst-data/bodystudy/r5/`, outside git. **Not verified by eye.** The study
waits at ★ 2: the user takes the test as `r5/HOWTO.txt` says.

Why: the user, on the A | B | C stack: "This sort of comparison doesnt work without
seek/pause etc, there are 3 videos running simultaneously, I cant keep up with all 3 and
compare all of them". The overseer then wrote addenda 6 and 7; 7 replaces 6.

Built:
- `scripts/body_study/crops.sh R5DIR`: cuts A, B and C out of each stack `test/tNN.mp4`
  into `test/tNN-{a,b,c}.mp4`. Settings: `crop=1280:720:{0,1280,2560}:0`, libx264 `-qp 0`
  (lossless; the profile is High 4:4:4 Predictive), yuv420p, faststart, no audio,
  `-map_metadata -1`. Then every crop's decoded frames (`framemd5`) are compared with its
  third of the stack: **72 crops, 0 mismatches.** Each is 1280 x 720, 480 frames, 16.0 s,
  with encoder tags only. Sizes 8,205,478-10,896,646 bytes, 657 MB in all. Headless Chrome
  plays them (one test crop: 50 frames, 0 dropped in 1.5 s). The stacks are no longer shown
  and stay on disk.
- `scripts/body_study/answer.html` (rewritten to addendum 7):
  - First pass: Start, then A, B, C alone at 1280 x 720 (scaled to fit), with 1 s of black
    between. The letter is beside the video, left. A Pause/Resume button; no controls, no
    pointer events, no context menu. A seek is undone (snaps back to the last played time).
    One video element only, so two clips never play at once.
  - After C: the counted answer A / B / C, final, saved at once.
  - Then replays of any clip one at a time, with native controls (seek), an optional second
    answer (toggle) and the free text. Next triplet; no way back.
  - State is in `localStorage` (`hyst-bodystudy-answers-v1`), saved at Start, at every
    pause, at the counted answer, on every replay, second answer and text change, and at
    Next. A reload during the first pass restarts that triplet from A and keeps its counts.
    A reload after the counted answer returns to the replays with the answer locked.
  - "Download answers so far" (any time) and "Download answers" (end) save `answers.json`.
    "Load a saved file" resumes from it; a file with fewer answers than the browser has is
    refused.
  - Per triplet it records: shown, counted, second, text, timeToCountedS (Start to counted
    answer, across reloads), totalS (Start to Next), pausesFirstPass, replays {A, B, C}
    (each open and each play after a clip ended), firstPassStarts, started, countedAt,
    finishedAt.
  - Videos come from `test/` next to the page or `?dir=`. The page has no reference to
    `key.json`.
- `scripts/body_study/serve.cjs [DIR] [PORT]`: a loopback server with byte ranges (Python's
  `http.server` has none, and replay seeking needs them). Defaults: its own folder, port
  8777. It serves only `answer.html` and `test/tNN-{a,b,c}.mp4`. `key.json`, `clips.tsv`,
  the stacks and `../` paths answer 404 (checked with curl on r5). A copy of it and of the
  page are in `r5/`.
- `scripts/body_study/test_answer.sh` (+ `test_answer.cjs`): headless Chrome at 1366 x 768
  on gray 3 s lossless dummy clips. It runs once from `file://` and once over `serve.cjs`,
  31 checks each, all passing:
  - no horizontal scroll; the controls fit in 768 px (the video is 956 px wide);
  - A, black, B, black, C in order; no controls in the first pass; seeks back and forward
    refused; pause holds the clip;
  - replays locked until the counted answer; the counted answer is saved and cannot change,
    also after a reload; no way back to the first pass;
  - replays have controls and seek;
  - the records' fields, replay counts and times;
  - a reload mid first pass restarts it (2 starts recorded);
  - download mid test; cleared storage, then resume from the file;
  - 24 / 24 ends the test with a final download;
  - no request for the key; only the page and the single clips are requested (Chrome's
    built-in `data:` icons and favicon excepted); `serve.cjs` refuses `key.json` and
    serves byte ranges.
- `scripts/body_study/score.py`: scores only `counted`. Second answers (given, correct,
  changed), times, pauses and replays are printed as data only. `test_score.py`
  (synthetic key and answers, where the second answer is always right): 16 gives PASS, 15
  and 0 give FAIL, 24 all found, and the data lines are checked. Not run on real answers.
- `r5/HOWTO.txt`: the server command `node /secondary/hyst-data/bodystudy/r5/serve.cjs`,
  the URL `http://127.0.0.1:8777/answer.html`, Chrome required, how to resume, where
  `answers.json` goes.

Checks: `cargo test -p hyst-compile -p hyst-output -p hyst-previz -p hyst-cli` passes;
clippy -D warnings with --all-targets is clean on the same crates; fmt is clean. `three.sh`
exports compared with `cmp` against `hexagon-47.html`, `five-years-hexagon.html` and
`presence-hexagon.html`: all three are identical; the tmp files were deleted. Nothing was
watched or answered. Frozen `src/` and `tools/` untouched. No hardware driven.

### Body study, check 2b scored (★ 3) — 2026-10-13

The user's answers: `answers.json` (24 of 24, finished, no pending triplet), copied to
`/secondary/hyst-data/bodystudy/r5/answers.json`; the score output is in `r5/score.txt`.
Scored with `scripts/body_study/score.py` against `r5/key.json`: counted answers only, as
addendum 7 says.

- **13 of 24 correct. Check 2b fails** (pass at ≥ 16; chance 8).
- Under guessing, 13 or more has p = 0.028 (binomial, 1/3 per triplet); 16 or more 0.00086.
  Wilson 95 % interval for the hit rate: 0.35-0.72 (chance 0.33).
- Per region, found as the odd one (of 3) / as the pair of a correct triplet (of 3):
  0 (centre 1706) 2/2, 1 (1966) 1/0, 2 (529) 2/1, 3 (786) 2/2, 4 (1582) 1/2,
  5 (365) 2/3, 6 (1919) 1/2, 7 (183) 2/1.
- Per k (odd region = pair + k mod 8): k 1: 3/8, k 3: 5/8, k 5: 5/8.
- Descriptors with the largest found-minus-missed difference, rank units:
  - odd region's position: wrist roll jerk p90 -0.101, roll jerk mean -0.092, roll accel
    p90 -0.081, lag elbow>wrist +0.078, wrist bend speed p90 -0.074, extension +0.067;
  - |m_odd - m_pair|: shoulder accel p90 -0.140, shoulder speed mean -0.133, roll jerk
    mean +0.125, shoulder accel mean -0.109, roll jerk p90 +0.105, shoulder jerk p90 -0.100.
  With 13 hits and 11 misses, each difference rests on a few triplets.
- Data, not scored: no second answers, no replays, no free text. Time to the counted
  answer: median 51.1 s (min 50.6, max 55.7). The first pass alone takes 50 s, so every
  answer came right after C. One pause in the first pass at most.

Per `NEXT_BODY_THEN_MIND.md` step 1, "If it fails": round 2, once, widens what the misses
point at. Addendum 5 says a failing 2b points at the generator (how much the seed decides
against the body vector). Round 2 is not started. That decision, and its addendum, belong to
the user and the overseer. Answers file also left where the user put it:
`/secondary/Programming/Github/Hysteresis/answers.json` (untracked, main checkout).

### Body study, round 2 under addendum 8: generator and sweep (★ 1) — 2026-10-14

Rules: `docs/BODY_STUDY.md` with all eight addenda (unchanged). Data in
`/secondary/hyst-data/bodystudy/r6/` (`sweep.json`, `sweep.log`, `report.txt`, `first.tsv`,
`first/{calm,middle,energetic}.{html,mp4,txt}`, `first/silence.m4a`), outside git. **Not
verified by eye.** The study waits at ★ 1: the user judges the range from the three clips.
Nothing of round 1's clips is reused.

Generator (`crates/hyst-compile/src/body.rs`, `Motion::new` rewritten; every range and its
reason in its doc comment):
- **15 body dimensions** (was 12): round 1's twelve plus `size`, `energy` and `rhythm`.
- **The body decides.** Pattern: every joint alternates between two poles, one move each
  way (base yaw ±span/2 about straight ahead, roll back and forth, shoulder and elbow about
  centres set by height and curl_extension, wrist about the arch's centre). Pace: energy sets
  the leader's move length. Rhythm sets how many moves elbow (1 + round(rhythm)), wrist bend
  and roll (1 + round(2 rhythm)) make per base and shoulder move. Initiation, succession,
  time, weight, flow, space and breath act as in round 1.
- **The seed only varies:** the start phase (anywhere in one leader cycle of two moves),
  ±8 % on each gap, ±10 % of the joint's travel on each target, breath's phase. Round 1's
  random target draws, random side flips, random paces and the 15-degree minimum move are
  gone.
- **Floor:** a target that breaks the floor rule is lifted in steps (shoulder 8, elbow and
  wrist 10 degrees) up to 6 times, then the joint stays for that move (round 1: 30 random
  redraws).
- Limits, the base's hand-speed cap, overlap, holds, overshoot and the final slow-down
  factor are round 1's.

Constants and origin:
- `PACE_FAST` 0.7 s per leader move (energy 1): under round 1's shortest wrist move, so the
  fast end meets the joint limits and hand rules, not a cap of its own. Geometric between.
- `PACE_SLOW` 5.0 s (energy 0) and `SIZE_MIN` 0.06 (size 0, scale 1 at size 1, geometric):
  the slowest and smallest point of a probe ladder (size scale / pace 0.12 / 3.2, 0.06 / 4.0,
  0.06 / 5.0, 0.04 / 6.0, 0.03 / 8.0) at which at least 90 % of the calmest bodies (size and
  energy ≤ 0.05, 60 draws) pass the stillness cap: 56 of 60 here, 53 at 0.04 / 6.0, 47 at
  0.03 / 8.0. 200-clip sweeps on the same ladder gave mean joint speed p90/p10 2.28, 4.01,
  4.53, 5.97, 7.66.
- `AMP`, full-size travel per move: base 330 and roll 110 degrees (round 1's upper ranges),
  shoulder 85 and elbow 125 (their whole ranges, 10..95 and -30..95), wrist bend 140 (twice
  round 1's 70 per side). Wander (base 15, roll 30 degrees x space) is scaled by size too.
- `TIME_JITTER` 0.08, `TARGET_JITTER` 0.1: mine, small next to pace (7.1x) and size (16.7x).
- `BEGIN` -12 s (minus the start phase): two slowest moves plus overlap, so the clip opens
  inside the pattern. `END` 12 s.
- Stillness cap (addendum 8): `STILL_DEG_S` 2, `STILL_RUN_S` 2, `STILL_SHARE` 0.25. A frame
  step is still when all five joints move under 2 deg/s.
- Clip 8 s, stretch about 4 s (addendum 8). Sample seed 20261016.
- Removed: the movement floors (`MIN_PATH_M`, `MIN_BOX_M`, `MIN_TURN_DEG`) and per-joint
  floors (`MIN_JOINT_DEG`). `body_study fill` (addendum 3's region fill) was deleted.

Tests (13 body tests): same inputs give the same clip; stretching keeps the centre pose and
slows the clip; one body over 6 seeds stays within 1.35x in mean joint speed (three bodies);
size and energy at 0 and 1 give mean joint speed calm < big-slow / 3, < small-fast / 2,
< both-high / 4; hardware limits and `validate` hold on feasible clips from calm to sudden,
big and fast; the rendered-curve check names the joint; a 2.5 s freeze fails "still run",
alternating 1 s still / 1 s moving fails the share; rhythm 1 gives the wrist at least twice
rhythm 0's moves; overshoot only on distal joints and only with free flow; the study
camera; descriptors finite.

Sweep (seed 20261016): **2,002 attempts, 2,000 passed**, 2 rejected (floor at stretch 1.95;
one also out of frame at stretch 1). No parameter decile has more than 2 rejections; the
full table is in `report.txt`. Stretch histogram 1.1^0..7: 1913, 79, 8, 0, 0, 0, 0, 0.

Reports (addendum 8, never gates). Mean joint speed = mean over the five joints of each
joint's mean speed on the shown 8 s, deg/s:
- **min 2.8, p10 8.5, median 28.3, p90 45.6, max 63.7; p90/p10 5.35.** Round 1's 72 test
  clips: 24-45.
- Histogram: 2.8-7.9:178 7.9-13.0:217 13.0-18.0:204 18.0-23.1:212 23.1-28.2:182
  28.2-33.2:223 33.2-38.3:249 38.3-43.4:255 43.4-48.5:160 48.5-53.5:90 53.5-58.6:27
  58.6-63.7:3.
- Per joint, mean speed p10 / median / p90: yaw 10.9 / 29.8 / 47.7, shoulder 3.9 / 11.1 /
  26.2, elbow 8.1 / 24.2 / 43.7, wrist bend 8.4 / 37.3 / 64.8, roll 7.5 / 31.4 / 58.0.
- Spearman rho of each parameter with mean joint speed: size +0.78, energy +0.46, rhythm
  +0.21, flow +0.13, every other |rho| ≤ 0.06. Median by size decile 8.0 to 41.9; by
  energy decile 15.3 to 37.5. Energy flattens above its 7th decile: big, fast bodies meet
  the hand-speed rule and are slowed as a whole.
- Share of total joint motion, median (p10, p90): yaw 0.216 (0.162, 0.342), shoulder 0.091
  (0.058, 0.145), elbow 0.186 (0.124, 0.251), wrist bend 0.270 (0.166, 0.327), roll 0.223
  (0.155, 0.284).
- Still time (all joints under 2 deg/s): 145 of 2,000 clips have any still frame; longest
  run max 1.05 s; share median 0, p90 0, max 0.242.
- Hand path p10 / median / p90 1.09 / 2.97 / 4.50 m; box 0.26 / 0.66 / 1.06 m; base turn
  28 / 90 / 228 degrees.
- Seed against body (probe, not a rule): 100 sweep bodies, 6 seeds each. Coefficient of
  variation of mean joint speed within one body: median 0.046, p90 0.083; max/min over the
  6 seeds median 1.14, p90 1.30, max 2.01. Ranks and regions are not built yet.

First-look clips (8 s, silent, study camera, `record-ensemble.cjs`, 1280 x 720, not test
clips): the sweep clip nearest the 5th, 50th and 95th percentile of mean joint speed.
Per joint in the order yaw / shoulder / elbow / wrist bend / roll, mean speed deg/s.
- calm, sweep clip 1982 (size 0.14, energy 0.15, stretch 1.0): mean joint speed 6.2;
  per joint 7.7 / 4.2 / 6.9 / 6.6 / 5.8. Hand path 0.99 m, box 0.25 m, base turn 29
  degrees, top hand speed 0.18 m/s. All joints still: 0 s. Frame margin 218 px.
- middle, clip 561 (size 0.59, energy 0.11, stretch 1.0): 28.3; per joint 24.9 / 8.8 /
  24.7 / 42.5 / 40.7. Hand path 2.82 m, box 0.76 m, base turn 95 degrees, top hand speed
  0.67 m/s. Still 0 s. Frame margin 86 px.
- energetic, clip 1466 (size 0.76, energy 0.76, stretch 1.0): 49.3; per joint 45.1 / 38.5
  / 28.1 / 72.9 / 61.6. Hand path 3.48 m, box 0.77 m, base turn 168 degrees, top hand
  speed 0.70 m/s. Still 0 s. Frame margin 46 px.
Body vectors and seeds: `r6/first.tsv`; per-clip printout in `first/*.txt`.

Report script: `scripts/body_study/report6.py SWEEP.json`.

Not done (after the go-ahead): ranks with half-ties, regions of 12 with the gate, practice
and scored triplets, the page with capped replays and practice feedback, scorer, HOWTO,
page tests.

Checks: `cargo test -p hyst-compile -p hyst-output -p hyst-previz -p hyst-cli` passes
(hyst-compile 54); clippy -D warnings on the same crates with --all-targets is clean; fmt is
clean. `three.sh` exports compared with `cmp` against `hexagon-47.html`,
`five-years-hexagon.html` and `presence-hexagon.html`: all three identical; tmp files
deleted. Frozen `src/` and `tools/` untouched. No hardware driven.
