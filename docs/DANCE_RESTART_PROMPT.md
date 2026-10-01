# Fresh-agent prompt — musical memory → convincing dance

Work in `/secondary/Programming/Github/Hysteresis`. Fresh diagnosis required.
User rejected both full-song demos. Current motion is technically valid but does
not look like dancing. Larger gestures, fewer cues and generic energy thresholds
missed the root problem. Treat current output as a rejected baseline.

User intent: HYSTERESIS = memory. Offline mode has the whole song available and
should anticipate musical events, develop/revisit movement ideas and dance to
what music is doing. Arm should follow meaningful bass/drum/vocal phrasing and
become recognizably more energetic when music does. Occasional coincidental hits,
beat-synchronized flailing and repetitive template playback fail acceptance.
User does not know which algorithm will solve this; choose foundation from evidence.

Read first: git status, git log -3 --oneline, AGENTS.md, docs/DANCE_HANDOFF.md,
crates/hyst-previz/README.md. Then relevant SINTEZA_IMPLEMENTATION_PLAN.md R4/R7/R8/R9
and SINTEZA_CHOREOGRAPHY.md sections4/6. Plan is authoritative; older companion
specs are directional. Latest user correction overrides earlier priorities:
convincing musical dance comes before native-window or hardware integration.

Start bottom-up. Trace real audio → actual available analysis → musical memory /
future context → movement generation → constrained joints → playback. Identify
where musical information is absent, discarded or flattened. Watch/listen to
rejected demos and contrasting real song passages before choosing implementation.
Explain root failure briefly, then implement a coherent working improvement.
Do not spend session renaming gestures, widening angles or randomly rotating
existing templates. Reconsider compiler/movement representation if evidence says
it is wrong. Do not assume one scalar energy envelope is a musical interpretation.

Verified gaps to investigate, not a prescribed solution:
- Supplied Instant Crush analysis has only one early break section,0–2.554s;
  it is not a whole-song structure map. Current motion sidecar has no stemPresence,
  repeats or novelty envelopes. Inspect actual assets before assuming otherwise.
- hyst-core has optional stem/repetition/novelty types; scripts/ contains active
  analysis, SSM/repetition and Demucs paths. Determine what actually works and
  what is connected. Low frequency band energy is not an isolated bass stem;
  brightness is not vocals. Never label proxies as verified instrument sources.
- Current hyst-compile mainly averages envelopes over short spans and anchors a
  few strongest onsets. It does not meaningfully use drop events, repetition maps
  or vocal/bass phrase structure. Prior joint displacement is motion history,
  not sufficient musical memory. All quintic legs stop at knots; evaluate whether
  this prevents believable sustained groove.
- Offline anticipation should use verified future musical timestamps and enough
  preparation time. Live path currently provides limited causal analysis/PLL;
  equivalent predictive live dance director is not implemented. Keep capabilities
  separate; do not pretend unavailable structure is known.

Deliver musical evidence, not only software checks:
1. Identify several contrasting timestamps: sustained groove, vocal/bass change,
   louder passage, transition/drop if actually present, quiet passage/rest.
   Show which signals/events justify decisions. Do not invent a drop for this song.
2. Demonstrate recognizable groove with hit/windup special cases disabled. Dance
   needs phrasing, continuation, preparation, arrival and recovery—not continuous
   random motion or a scalar amplitude dial. Musical recurrence should inform
   related movement; different content at matched tempo should change behavior.
3. Demonstrate anticipation of an annotated future event, with arrival at its
   actual timestamp. Use a suitable real-track excerpt if supplied song lacks
   reliable events; do not redownload media already provided or fabricate analysis.
4. Use acceptance checks for musical decisions, memory/recurrence, anticipation,
   energetic contrast, continuity, limits, rests and deterministic seek. Numeric
   workspace coverage alone does not prove dance quality. Compare before/after
   with audible short excerpts before spending time on another full-song render.
5. Deliver runnable preview and, after review of representative excerpts, updated
   full-song arm recording with original audio. User is perceptual acceptance gate.
   Report what improved and what remains unresolved without claiming human-quality
   dance from passing tests.

Current usable infrastructure: deterministic compiler score; shared native/browser
absolute-time sampler; exact onset anchors; simulated joint speed/acceleration
validation; audio-master seek/pause; autoplay-safe remote mode; recording script.
Reuse it where useful. Preserve additive score/sidecar compatibility or provide
explicit backwards-compatible migration. Compiled musical memory may be resolved
into score offline; runtime hidden state must not break seek reconstruction.

Assets, all outside git:
`/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm/`
- instant-crush.m4a / instant-crush-analysis.wav (339.824s)
- instant-crush.sidecar.json / instant-crush.motion.sidecar.json
- instant-crush.score.json / instant-crush.audit.json / song.html
- arm-dance-instant-crush-current.mp4 (tiny repeated motion, rejected)
- arm-dance-instant-crush-phrases.mp4 (larger heuristic motion, also rejected)
- record-demo.cjs (1080p/30fps, original AAC copied)
- serve.cjs (loopback8766, byte ranges)
Preview: http://127.0.0.1:8766/song.html?remote=1&fix=4
If offline: node serve.cjs in asset directory. Recording commands in script/previz
README; use a new output filename and preserve rejected comparisons.

Work directly in saved checkout. No reset/clean. Frozen src/ and tools/ remain
read-only; active scripts/ may change. Native rewrite must survive. Cross-crate
integration for this dance slice is authorized; give cheaper coding workers bounded
file ownership per AGENTS.md. Keep coordinator focused on diagnosis/integration
and perceptual review. Do not recursively delegate. Communicate smart caveman.
Do not install allin1/natten, run expensive GPU experiments, drive hardware or
commit generated media. Check existing dependencies before adding/installing any.
Research technical options from primary sources if needed. Flag genuine expensive
or missing-data decisions; do useful independent work before asking questions.

Checkpoint validation: CPU workspace tests excluding hyst-render, workspace check,
targeted compiler/output/previz/CLI clippy and JS timing/media tests pass. Strict
workspace clippy has pre-existing manual_is_multiple_of warnings in
hyst-render/src/passes/julia.rs:308,1574. GPU unavailable; do not repeat expensive
probe or claim full GPU suite passed. Current 92-cue score/43 onset anchors is a
technical checkpoint, not accepted choreography. .codex/config.toml is local and
untracked. No remote push requested. Append honest checkpoint when done.
