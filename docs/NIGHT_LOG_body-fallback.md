# Night log: body-fallback (work order 3, builder 2), 2026-11-04

## MORNING SUMMARY

Branch `body-fallback` (from `origin/body`). No claims; mechanism names only.

- **Phase 1, fallback arm.** `scripts/author/build.py` already read the B7 lanes (`mindState.brain`, work order 2); rebuilt the page
  (`/secondary/hyst-data/brain/author/index.html`). Exported a phrase bodyTrack per danced song with `mappings/example-sketch.json` (a starting
  sketch, not a claim; the user tunes it by eye) and compiled the arm previews with `attach.py --preview` (`--body layered --clock music`).
  Files in `/secondary/hyst-data/brain/author/fallback/`: `instant-crush.html`, `five-years.html`, `presence.html` (audio URL `../audio/<song>.m4a`,
  serve `/secondary/hyst-data/brain/author` with `scripts/author/serve.py`), plus `<song>.bodytrack.phrase.json`, `<song>.sidecar.json`, `<song>.log`.
  Spans: 40 / 32 / 38.
- **Phase 2, self-surprisal lane.** "cerebellum: prediction error of its own arm", no claim (K1 failed). `scripts/body/selfsurprisal.py`;
  files `/secondary/hyst-data/body/selfsurprisal/{instant-crush,five-years,presence}.npz` + `schema.json` (sizes below).
- **Phase 3, `mindState` version 2.** `hyst-compile/src/mind_state.rs` reads version 1 unchanged and version 2 (`bands` / `surprise` / `neuromod`
  as objects of 0.1 s lanes, `brainHopSeconds`); writer `brain_mindstate.py --v2` (`to_v2`). Files `/secondary/hyst-data/brain/mindstate/mind2-<song>.json`.
- **Phase 4.** `scripts/compute/manifest.py` skips `dataset-metadata.json` in `build` and `verify`; test added.
- **brainDump.** Crossing marks dropped (array, meta, viewer ticks and threshold lines, mindState `brain.crossing`); the four coherence traces stay.
  Regenerated the three danced dumps and viewers in `/secondary/hyst-data/brain/braindump/`.
- **v47 check** after every Rust change: `ensemble_preview ... --ring 6,0.8` for the three songs, `cmp` against `hexagon-47.html`,
  `five-years-hexagon.html`, `presence-hexagon.html`: identical (3/3).

FOR USER: see the end of this file.

## Phase log

### Phase 1 (fallback arm)
Nothing to change in the page code: B7 lanes were already the source (commit e6ab2b8). Ran `build.py`, `export_cli.cjs` and `attach.py --preview`
via a script; all three compiled (86 / 67 / 67 cues). Author tests: node 9 pass, `test_attach` 5 OK.

### Phase 2 (self-surprisal)
K1 round-2 bundle `m1_r2.pt`; each of the 6 v47 arms per song replayed in physics (`build_v47.replay`, whole song, not the 60 s segments), cerebellum run
in 200-step chunks with stride 180 (the training layout, 20 warm-up steps per chunk), Gaussian NLL of the actual change at +10/+50/+100 ms (mean over
the 15 dims), 30 Hz bins. Run time 97 s. Sizes (npz, compressed) and statistics: see `schema.json` `sizes`.

| song | bytes | seconds | median NLL | p99 NLL |
|---|---|---|---|---|
| instant-crush | 654,398 | 339.8 | -0.936 | 29.88 |
| five-years | 530,107 | 283.7 | -1.228 | 10.50 |
| presence | 536,201 | 270.7 | 1.669 | 91.67 |

The heavy tail follows the K1 record (§7.14 point 1): the v47 targets include moves the M0 servos cannot follow, so large NLL there is the limiter, not a finding.

### Phase 3 (mindState v2)
Lane names: bands `power.L1..L4`, `coherence.L1..L4`, `selfSimilarity`; surprise `L1..L4`, `total`, `smoothed`, `slope30s`, `l4PredictedVariance`;
neuromod `arousalSignal`, `gain.L1..L4`, `exponent.L1..L4`. `mood.*` unchanged (energy from core-2b). `pulse` and `events` stay empty. Version 1
still requires the reserved arrays empty. `MindState::On(Mood)` gained `brain: Option<Box<Brain>>` (None for version 1). Rust: 15 mind_state tests
(6 new), including a fixture written by the Python writer from the real presence lanes (12 bins).

## FOR USER

1. The mapping in the previews is `example-sketch.json`; tune by eye in the authoring page.
2. Lane grouping in version 2 (which B7 lane sits under `bands`, `surprise` or `neuromod`) is my choice; the planner does not read them yet.
3. Previz videos (below). Same example-sketch mapping, single arm; no claim about how they look.

## Previz videos (7.15 addition)

`scripts/author/record_ensemble.cjs PREVIEW.html AUDIO OUT.mp4` (drawn frame by frame with `window.__ENSEMBLE_PREVIEW__.draw`, no real time; derived
from the music-arm `record-ensemble.cjs`, whole song, 1080p). Five Years uses `HYST_TEMPO_MAP=five-years.tempomap.json` (steady-grid score drawn at the audio's time).
H.264 1920x1080 30 fps, original AAC copied unchanged (packet payload sha256 equal to the source m4a, checked for all three).

| file (in `/secondary/hyst-data/brain/author/fallback/`) | frames | video s | audio s | bytes |
|---|---|---|---|---|
| `instant-crush-fallback.mp4` | 10195 | 339.833 | 339.824 | 143,364,351 |
| `five-years-fallback.mp4` | 8513 | 283.767 | 283.753 | 126,692,844 |
| `presence-fallback.mp4` | 8122 | 270.733 | 270.733 | 122,904,044 |

Frame checked at 3 s of a 6 s test clip (arm, disc, floor, trail all drawn). Whole-song frames not inspected by eye.
