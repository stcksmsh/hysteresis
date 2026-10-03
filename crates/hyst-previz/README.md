# Song-driven arm preview

Rust compiles sidecar content into absolute-time cues, samples joint trajectories,
then exports a standalone browser preview. Audio playback position owns time;
pause and seek reconstruct arm, trace and simple visual panel from identical score.
Browser canvas remains disposable previz, not replacement for native renderer.

## Corrected target — automatic interpretation and 3D ensemble

The project must infer musical structure and phrasing from audio, then compile
shared choreography for multiple synchronized 3D robot arms. The current planar
three-joint score is a diagnostic rig, not the target architecture. A provisional
arm has five servos: base rotation, three bending joints, and another rotation at
the second joint. Local axes and the optional final link remain unconfirmed.
Projected visuals should follow the same musical interpretation and shared clock.

The authored solo director has been removed from the compiler. Its source and
recordings survive outside the repository as rejected diagnostic material in the
media directory. `scripts/instant_crush.acceptance.json` stores only the user's
listening references for evaluating automatic inference; it must never drive
inference or choreography. `?solo=1` hides auxiliary graphics for motion inspection.

The musical-memory candidate below was also rejected: it does not provide adequate
section interpretation or convincing dance. Passing trajectory limits is not
perceptual acceptance.

## Automatic analysis evidence

`dance_structure.py` adds mixed-audio novelty and repeated-material candidates.
`dance_stems.py` adds estimated source activity from four separated WAVs. Neither
module accepts choreography roles or human section timestamps. Source-separation
producer metadata comes from an optional `separation.json` manifest; arbitrary
WAVs must not be attributed to a model that did not produce them. Activity uses
whole-track calibration and preserves absolute RMS. Candidate confidence is
heuristic evidence strength, not a calibrated probability or semantic label.

```sh
media=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
python3 scripts/dance_stems.py "$media/instant-crush.memory.sidecar.json" "$media/stem-analysis/htdemucs/instant-crush-stereo-analysis" "$media/instant-crush.stems.sidecar.json" "$media/instant-crush.stems.evidence.json"
python3 scripts/dance_structure.py "$media/instant-crush-stereo-analysis.wav" "$media/instant-crush.stems.sidecar.json" "$media/instant-crush.interpreted.sidecar.json" "$media/instant-crush.interpreted.evidence.json" scripts/instant_crush.acceptance.json
python3 -m unittest discover -s scripts -p 'test_dance_*.py'
```

The optional final reference file is evaluated after inference and appears only
in the evidence report. It does not change the enriched sidecar or inferred data.
Current source WAVs came from CPU htdemucs4.0.1 / torch2.5.1+cpu in isolated
`/tmp/hyst-dance-cpu`, using original stereo audio, shifts0, float32 and clamp mode.
No GPU, allin1 or natten was used. Stem estimates expose bass/vocal contrast hidden
by total mix loudness; leakage and clamped peaks remain limitations.

The compiler does not yet consume `musicalStructure` or `stemInterpretation`.
These are automatic evidence for the next director integration, not a new
accepted dance recording. The three-joint score remains a diagnostic format.

## Musical-memory candidate — 2026-10-01

Both previous recordings are rejected baselines. The new offline path analyzes the
provided WAV with existing NumPy/SciPy/SoundFile, preserving the input sidecar.
It adds versioned `musicalMemory` evidence: provisional regularized pulse,
ordered 16-beat mix-transient profiles, harmonic recurrence comparisons, absolute
level, and measured transient timestamps. These metrical windows are not inferred
verse/chorus sections. Low/bright mix features are not isolated bass/vocal stems.

```sh
media=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
python3 scripts/dance_memory.py "$media/instant-crush-analysis.wav" "$media/instant-crush.motion.sidecar.json" "$media/instant-crush.memory.sidecar.json" "$media/instant-crush.memory.evidence.json"
cargo run -p hyst-previz --example arm_preview -- "$media/song-memory.html" instant-crush.m4a "$media/instant-crush.memory.sidecar.json" "$media/instant-crush.memory.score.json"
cargo run -p hyst-previz --example arm_preview -- "$media/song-memory-groove.html" instant-crush.m4a "$media/instant-crush.memory.sidecar.json" "$media/instant-crush.memory.groove.score.json" --groove-only
```

`--groove-only` removes event preparation/arrival overlays. `--no-reuse` resolves
current phrase coefficients instead of recalling the matching earlier phrase.
Both options affect compilation, not playback. Old sidecars without
`musicalMemory` retain the previous planner; old scores deserialize unchanged.
Invalid extension data fails explicitly rather than silently falling back.

The planner projects ordered profiles onto phrase/four-beat/two-beat harmonics,
with physical timing preserved. Whole-track calibration makes actual content
variation visible. Phrase coefficients crossfade, absolute level shapes motion,
and validated recurrence recalls the source signature. All decisions resolve
into the score offline. Runtime sampling has no hidden musical state.

Knots optionally carry velocity and acceleration. Quintic Hermite interpolation
preserves C2 continuation; omitted derivatives retain legacy zero-stop quintics.
Shared Bezier hull bounds conservatively prove continuous joint range, speed,
and acceleration. Floor clearance remains a sampled geometry check. Jerk,
actuator dynamics, calibration, self-collision and hardware safety remain open.

Measured transients use 50Hz frame centers (20ms quantization), not sample-accurate
acoustic onsets. Preparation targets the stored estimate exactly. No drop is
invented for Instant Crush. Beat fit remains provisional; supplied detector
residuals and independent waveform pulse evidence are reported separately.
Preview readout uses the compiled pulse when this extension is present.

```sh
python3 -m unittest discover -s scripts -p test_dance_memory.py
cargo test -p hyst-compile -p hyst-output -p hyst-previz -p hyst-cli
cargo run -p hyst-previz --example audit_score -- "$media/instant-crush.memory.score.json"
python3 scripts/dance_acceptance.py "$media/instant-crush.memory.score.json" "$media/instant-crush.memory.groove.score.json" "$media/instant-crush.memory.sidecar.json" "$media/instant-crush.rejected-phrases.score.json" "$media/instant-crush.memory.acceptance.json"
```

Listening comparison: <http://127.0.0.1:8766/dance-memory-review.html>.
Candidate: <http://127.0.0.1:8766/song-memory.html>.
No-accent candidate: <http://127.0.0.1:8766/song-memory-groove.html>.

External `record-memory.cjs` preserves the existing recorder and adds `--start`
for short excerpts. Full recordings copy original AAC; excerpts decode/re-encode
AAC for sample-aligned trimming. Generated media stays outside git. Human
listening/visual acceptance is still required; software checks do not establish
convincing dance or verified instrument following.

## Supplied track

Media and generated files stay outside git. From repository root:

```sh
media=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
python3 scripts/arm_features.py "$media/instant-crush-analysis.wav" "$media/instant-crush.sidecar.json" "$media/instant-crush.motion.sidecar.json"
cargo run -p hyst-previz --example arm_preview -- "$media/song.html" instant-crush.m4a "$media/instant-crush.motion.sidecar.json" "$media/instant-crush.score.json"
node "$media/serve.cjs"
```

If port 8766 already serves existing preview, reuse it. Open
<http://127.0.0.1:8766/song.html>. Range-capable server required for reliable seeking.
For remote review, open <http://127.0.0.1:8766/song.html?remote=1&fix=4>.
Silent motion advances before browser permits audio. Press **Play** or **Enable audio**
to start sound at current preview position. Pause and seek then follow audio time;
clicking unrelated controls does not start sound.

Original sidecar and media remain unchanged. Score JSON exposes cue decisions and
joint knots for inspection. Invalid sidecar stops generation with error.

Song score is default. Reference studies remain selectable for comparison.
Grid selector/manual BPM/beat-zero correct beat readout and reference studies;
they do not recompile song decisions. Positive offset delays score and grid.
Compiled cue times remain inspectable in JSON.

Absolute RMS enrichment uses standard-library Python + PCM16 WAV, checks duration
match, and adds `rmsEnvelope` without changing published sidecar fields. Necessary
because adaptive normalized energy may remain high during an almost silent fade.
Compiler also accepts original sidecar without RMS, with less reliable silence detection.

## Synthetic reference

```sh
cargo run -p hyst-previz --example arm_preview -- /tmp/hysteresis-arm.html
```

Self-contained authored 16-beat studies, optional click track. These remain
reference motions, distinct from song-conditioned score.

## Verification

```sh
cargo test -p hyst-compile -p hyst-previz
cargo clippy -p hyst-compile -p hyst-previz --all-targets -- -D warnings
node crates/hyst-previz/tests/timing.cjs crates/hyst-previz/src/viewer.html
node crates/hyst-previz/tests/media.cjs crates/hyst-previz/src/viewer.html
```

Geometry assumes planar 32/26/12 cm links. Joint constraints are illustrative,
not measured actuators. No torque, dynamics, thermal model, self-collision solver,
hardware output or physical-safety guarantee. Song interpretation uses heuristics;
watching/listening remains taste gate. Full ensemble R7/R9 remains separate scope.

## Exact arrivals and audit

Hit/coil cues carry optional `arrivalAnchor` seconds. Their arrival knot lands on
that onset exactly; if preparation/recovery cannot fit, planner emits groove with
explicit reason. No midpoint substitution under an accent label. Boundaries come
from envelope changes and valid supplied section edges; known onsets are searched
inside cues. Section kinds influence recovery posture. Ordinary content changes form 3.6–6.8 second planning spans, with fewer stops for
groove sweeps. Declared and rest edges remain exact. Absolute RMS changes gesture
and posture: quiet passages fold, sustained loud passages extend. Timbre adjusts
height/wrist, onset pan and prior displacement choose continuation direction.
Each phrase carries its endpoint rather than resetting to one home pose. Internal
planning margins avoid hard-limit pinning. Unlabeled spans use a bounded content
neighborhood, not inferred verse/chorus labels. No random or cue-index cycling.
This remains heuristic phrasing, not verified semantic dance analysis.

`Next accent` seeks to next anchored arrival. Visual halo peaks on that same
arrival; brightness blends across cue boundaries. Both use audio time + score delay.

```sh
cargo run -p hyst-previz --example audit_score -- "$media/instant-crush.score.json"
```

Audit checks complete coverage, shared boundary poses, exact arrival knots, joint
ranges and analytic quintic speed/acceleration extrema. Floor clearance is sampled
at 120Hz, not proven collision-free. Holds and deterministic random-access sampling
are checked. Exported `instant-crush.audit.json` records supplied-track results.

Current supplied track: 92 cues, 43 anchored arrivals, 4 hold cues. Maximum joint
speeds 55.00/47.28/56.39 degrees/s, minimum sampled floor clearance 22.63 cm.
Human-quality dance remains unproven; the preview is ready for listening review.

## Native score inspection

Native output samples the same compiled score at absolute time. Browser export and
native SVG use this shared output path. No browser, GPU or audio device is needed
for these commands; SVG is a still inspection view, not a native animation window.

```sh
cargo run -p hyst-cli -- score-sample "$media/instant-crush.score.json" 60 "$media/native-arm-60.svg"
cargo run -p hyst-cli -- score-trace "$media/instant-crush.score.json" "$media/instant-crush-analysis.wav" 30 50 > "$media/native-arm-trace.ndjson"
```

`score-sample` prints one JSON frame and optionally writes SVG. Finite times outside
score range clamp to endpoints; NaN/infinity fail. SVG uses existing planar arm
geometry and labels simulated dimensions.

`score-trace` decodes supplied WAV and advances `AudioClock` by sample counts, then
samples its audible position. Optional arguments are FPS (default 30, range 1–240)
and output latency in milliseconds (default 0, range 0–5000). Trace includes initial
and final frames, draining latency after source ends. It writes NDJSON to stdout.
This is offline clock simulation; it neither plays audio nor drives hardware.
Duration mismatch fails before trace output. Native window, wgpu integration and
live hardware transport remain separate work.
