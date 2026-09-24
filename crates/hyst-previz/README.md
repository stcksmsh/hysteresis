# Song-driven arm preview

Rust compiles sidecar content into absolute-time cues, samples joint trajectories,
then exports a standalone browser preview. Audio playback position owns time;
pause and seek reconstruct arm, trace and simple visual panel from identical score.
Browser canvas remains disposable previz, not replacement for native renderer.

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

From a video instead (any ffmpeg with AAC decode; Playwright's bundled one lacks it):

```sh
ffmpeg -i song.mp4 -vn -c:a copy "$media/instant-crush.m4a"
ffmpeg -i song.mp4 -vn -ac 2 -ar 44100 -c:a pcm_s16le "$media/instant-crush-analysis.wav"
node --import tsx "$PWD/scripts/analyze.ts" "$media/instant-crush-analysis.wav" "$media/instant-crush.sidecar.json"
```

## Sections, phrases, key poses

Compiler splits song into sections (z-scored loudness/5 bands/centroid/flatness,
4s before/after novelty, peaks above median+2·MAD, >=8s apart). Level class
(`quiet`/`mid`/`peak` song-relative, `rest` from absolute RMS) sets phrasing:

| level | new pose every | move | sustain |
|---|---|---|---|
| peak | 1 bar | 0.45s lead, anticipation, 10% overshoot | bounce every beat, onset hits |
| mid | 2 bars | 0.8s lead, 7% overshoot | half-depth bounce, hits |
| quiet | 4 bars | 1.8s sweep | one slow breath |
| rest | section | fold to rest pose | frozen |

Poses come from 8 full-range key poses (rise, reach, arc, fold, sweep, hook,
coil, open) + mirrors; section motif = 4 poses alternating sides, chosen by
timbre family. Similar later sections replay the motif mirrored. Moves arrive
exactly on bar lines (downbeat phase = beat parity with most onset strength;
provisional) or on a strong onset within 0.3s of the bar. Lead time is reserved
before each arrival; if a bar is too short, the move shrinks rather than
smearing past the beat. Strong onsets during a held bar become hits; accents
inside a big move's wind-up are not hit separately (known gap). Every knot pose
keeps >=8 cm floor clearance.

## Remote mode

`song.html?remote=1` starts muted and free-runs a wall clock while browser
blocks playback. First Play press or tap anywhere carries free-run position
into audio, unmutes and plays; after that media time owns transport (pause
freezes, seek moves). Seek/Next accent work before first gesture too.

## Synthetic reference

```sh
cargo run -p hyst-previz --example arm_preview -- /tmp/hysteresis-arm.html
```

Self-contained authored 16-beat studies, optional click track. These remain
reference motions, distinct from song-conditioned score.

## Verification

```sh
cargo test -p hyst-compile -p hyst-previz   # includes tests/acceptance.rs
cargo clippy -p hyst-compile -p hyst-previz --all-targets -- -D warnings
node crates/hyst-previz/tests/timing.cjs crates/hyst-previz/src/viewer.html
```

Geometry assumes planar 32/26/12 cm links. Joint limits assume servo-class
actuators (±75/±150/±90°, 240/300/360°/s, 1500/1800/2400°/s²), derated guesses,
not measured hardware. No torque, dynamics, thermal model, self-collision solver,
hardware output or physical-safety guarantee. Song interpretation uses heuristics;
watching/listening remains taste gate. Full ensemble R7/R9 remains separate scope.

## Exact arrivals and audit

Hit/coil cues carry optional `arrivalAnchor` seconds. Their arrival knot lands on
that onset exactly; if preparation/recovery cannot fit, planner emits groove with
explicit reason. No midpoint substitution under an accent label. Boundaries come
from envelope changes; known onsets are searched inside cues. This is heuristic
phrasing, not verified verse/chorus or semantic dance analysis.

`Next accent` seeks to next anchored arrival. Visual halo peaks on that same
arrival; brightness blends across cue boundaries. Both use audio time + score delay.

```sh
cargo run -p hyst-previz --example audit_score -- "$media/instant-crush.score.json"
```

Audit checks complete coverage, shared boundary poses, exact arrival knots, joint
ranges and analytic quintic speed/acceleration extrema. Floor clearance is sampled
at 120Hz, not proven collision-free. Holds and deterministic random-access sampling
are checked. Exported `instant-crush.audit.json` records supplied-track results.

Current supplied track: 19 sections, 98 cues, 97 exact arrivals. Max joint
speeds 240/300/338 degrees/s, minimum sampled floor clearance 8.08 cm. Audit logic lives in
`hyst_previz::audit_score`, shared by CLI and acceptance tests.
Human-quality dance remains unproven; the preview is ready for listening review.
