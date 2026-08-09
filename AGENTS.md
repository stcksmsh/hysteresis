# AGENTS.md — sinteza-viz (published as `hysteresis` on GitHub, pending rename)

Working notes for future agent sessions on this repo. See `SINTEZA_VIZ.md` for the full design doc; this file is state/context, not spec.

## What this is

A WebGL2 music visualizer package (`the СИНТЕЗА visualizer` / "sinteza-viz") consumed by `stcksmsh/stcksmsh.github.io` as a persistent site-wide background. Three layers: Layer 1 (AudioWorklet feature extraction, live-audio only), Layer 2 (musical state — beat/build/drop/break via `StructureSource`/`Choreographer`), Layer 3 (`Choreographer` → `ParamBus` → `Scene` render). Signature visuals: curl-noise memory field (ping-pong feedback smear), onset particles, "earned symmetry" (folds only on drops/builds, never a constant filter), Julia scene (perpetual boundary-sweeping dive + oscilloscope beam foreground).

## Repo rename status

Not yet renamed on GitHub — still `stcksmsh/hysteresis`. The site's `projects.manifest.json` and this package's own `io-page` branch `meta.json` already declare the eventual slug `sinteza-viz`; the manifest's fetch-source `repo` field is deliberately still pointed at `stcksmsh/hysteresis` (the real, reachable name) until the actual rename happens. **When the rename happens: flip that one line back in the site repo, nothing else needs to change** (the resulting page path stays `/projects/sinteza-viz` either way, since that comes from `meta.json`'s `slug`, not the manifest's `repo` field).

## Position-only sync mode (the site's actual integration)

The site embeds SoundCloud via iframe — cross-origin, no AnalyserNode reachable, ever. `StructureSource.synthesize(positionSec)` builds a complete `StateFrame` purely from a schema-2 sidecar (`src/shared/sidecar.ts`), driven by an rAF loop in `src/index.ts` whenever a sidecar is loaded and no live audio has attached. `idle: true` is set *deliberately* in this mode even though music is genuinely playing — it's the existing lever (`JuliaScene.idleClockSec`) that keeps the beam animating its idle Lissajous figure, since there's no real waveform to trace offline. Every other field (`buildProgress`, `tension`, bands, onsets, energy, centroid, flatness) carries real per-track structure.

**Generating a sidecar**: `npm run analyze -- /path/to/master.wav output.sidecar.json` (wraps `scripts/analyze.ts`, needs the *original* WAV — the hand-rolled `scripts/wav.ts` reader only handles RIFF/WAVE PCM 16/24/32-bit or 32-bit float, no compressed formats). Output is schema-2 JSON: `bandEnvelope` (5 bands × ~20Hz samples), `centroidEnvelope`/`flatnessEnvelope`/`energyEnvelope`, `beats[]`, `sections[]` (build/break spans only — everything outside a matched section defaults to `buildProgress`/`tension` = 0), `events[]`, `onsets[]`. Runs fine on the *original* full-fidelity WAV directly — no need to downsample for this script's sake (downsampling only matters if you need to physically transfer the file somewhere with a size limit).

**Currently wired up** (as of this session): SIGSEGV, 0xC000021A, Hysteresis, Sampling Drift, Triple Pendulum — all five real tracks on the site now have real sidecars driving the visualizer (published to the site repo's `public/sidecars/`, referenced via each track's `sidecar` content field). Confirmed empirically (simulated `player:transport` sequences, diffed rendered output at a detected build-section position vs. a plain groove position) that this actually changes what renders, not placebo.

## Known/accepted limitations (don't "fix" these without reason to)

- The beam never shows a real waveform in position-only mode — always the idle Lissajous figure. Sidecar section detection is currently sparse for most tracks (e.g., SIGSEGV: 2 sections across ~6 minutes) — `buildProgress`/`tension` default to 0 for a large majority of most tracks' runtime, which is inherent to the offline section-detection heuristic in `scripts/structure.ts`, not a wiring bug.
- `ZOOM_MIN` (JuliaScene) is deliberately capped — going deeper needs actual perturbation-orbit rebasing (not implemented), and past attempts at a lower floor introduced visible blocky artifacts. Don't lower it without implementing rebasing.
- The Julia scene's perpetual zoom dive periodically resets when it hits `ZOOM_MIN` (a designed, not-a-bug beat) — happens roughly every 13-22 minutes at idle rate per the actual math (worst case ~2 min only under sustained `windup≈1`, which real short build sections never produce). If this ever gets reported as "too frequent," check `windup`'s actual behavior with real data before assuming the reset math is wrong — it likely isn't.

## Fixes landed this session

- **Flash pacing** (`JuliaScene.ts`, `POST_FLASH_SEC`): was 0.28s, now 1.6s. The zoom-floor reset's fade-to-black (`PRE_FLASH_LOG_WINDOW`) takes ~28s at idle rate — a near-instant 0.28s fade back in was a ~100x pacing mismatch that read as a stutter/glitch regardless of how rare the actual reset event is. This is very likely what "stutters/resets" reports are describing — the reset itself isn't frequent, its *pacing* was broken.

## Sandbox/environment notes (for whoever's running this next in a similar constrained environment)

- `w.soundcloud.com` and generic Google/Drive domains are blocked by egress policy in Claude Code's sandboxed sessions — can't test real SoundCloud playback or fetch from Drive links there. `raw.githubusercontent.com` and normal git push/fetch against `github.com` do work.
- `api.github.com` (plain REST, e.g. the `contents` listing endpoint the site's `federate.ts` script calls) also 403s in that sandbox even though `raw.githubusercontent.com` doesn't — this is a real, pre-existing limitation of `federate.ts`'s GitHub-API dependency in that specific sandbox, not a bug in the script; it works fine in real CI (GitHub Actions) which isn't behind the same egress policy.

## Outstanding

- No further known gaps as of this session's end — position-only sync is real end-to-end for all 5 live tracks, the reset pacing is fixed. Worth a real-browser sanity check (this session could only verify via simulated transport events + rendered-output diffing, never actual SoundCloud playback) once convenient.
