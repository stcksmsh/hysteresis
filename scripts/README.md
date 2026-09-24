# scripts/ — offline analysis pipeline

Node/TS + Python-subprocess offline tools. Independent of the Rust rewrite in `crates/`.

## What it does

One WAV master in, one `<slug>.sidecar.json` out.

- `wav.ts` — minimal RIFF/WAVE decoder.
- `structure.ts` — `analyzeMix()`: causal beat/tempo/section/event/onset analysis (same
  primitives the live worklet runs, replayed offline), schema-3 output. `analyzeMixDetailed()`
  is the same pass but also returns the per-hop raw band/centroid/flatness arrays and drop
  times the SSM pass needs.
- `demucs.ts` — shells out to Python Demucs for stem separation (`analyze.ts --stems`).
- `ssm.ts` — beat-synchronous features, self-similarity matrix, checkerboard novelty +
  peak-picking, the repetition map. Pure functions, no I/O.
- `repetition.ts` — `computeSchema4Sidecar(wav)`: orchestrates `analyzeMixDetailed` + `ssm.ts`
  into a schema-4 sidecar (repeats, novelty envelopes, boundary-refined build windows).
- `schema4.ts` — the additive schema-4 TypeScript type (`SidecarRepeat`, `Schema4Sidecar`),
  layered on top of the frozen `src/shared/sidecar.ts` without editing it.
- `analyze.ts` — CLI: `npm run analyze -- track.wav [out.json] [--stems]`.

## Running it

```
npm run analyze -- master.wav out.sidecar.json          # schema 3
npm run analyze -- master.wav out.sidecar.json --stems   # + Demucs stem presence
```

Schema-4 (SSM/repetition map) isn't wired into `analyze.ts`'s CLI yet — call
`computeSchema4Sidecar(decodeWavFile(path))` from `scripts/repetition.ts` directly (or add a
`--repeats` flag following the `--stems` pattern) until it's promoted to a CLI flag.

## Schema 4 — what it adds and why

Per `SINTEZA_OFFLINE_SSM.md` §1.5, the one thing nothing else in the pipeline produces: **the
repetition map** — "this section is a repeat of that earlier section," needed for choreography
phrase reuse. Adds, all additive/optional, matching `crates/hyst-core/src/sidecar.rs`'s
schema-4 fields field-for-field:

- `repeats: {aStart,aEnd,bStart,bEnd,similarity}[]`
- `noveltyLocalEnvelope` / `noveltySectionEnvelope: number[]` (20Hz, like every other envelope)
- `SidecarSection.boundaryConfidence?: number`

Pipeline: beat-synchronous 7-dim feature vectors (5 bands + centroid + flatness), z-score
normalized per-dim → full N×N cosine-similarity SSM → Foote checkerboard novelty (two kernel
radii: local/phrase-scale, section-scale) → adaptive (median + 1.5×MAD) peak-picking for section
boundaries → boundary-informed build-window backward-walk (replaces `buildWindowsFromDrops`'s
fixed 8-bar guess where a real boundary precedes the drop) → repetition map (adaptive
median+1.5×MAD threshold over boundary-delimited, non-adjacent section-pair cross-block SSM
means).

`analyzeMix()` itself (schema 3, existing CLI default) is **unchanged** — schema 4 is a
separate opt-in pass (`computeSchema4Sidecar`), so no existing sidecar consumer or test is
affected.

## Known limitations (be honest)

- **`allin1` (the spec's preferred beat/boundary source) is still not usable here, but the
  blocker has moved.** Retried properly this time: `python3 -m venv` + `pip install torch
  --index-url https://download.pytorch.org/whl/cpu` first (pins the CPU wheel, avoids the
  resolver considering the CUDA matrix — this is what hung last time) — this part worked fine
  in a couple minutes. `pip install allin1` itself also installed cleanly and fast. The problems
  showed up at *import*, not install:
  - `allin1`'s hard dependency `madmom` isn't declared in its PyPI metadata, so `pip install
    allin1` silently leaves it missing (`ModuleNotFoundError: madmom`).
  - `madmom` 0.16.1 (latest on PyPI, last released years ago) doesn't build on Python 3.12 out
    of the box: its `setup.py` needs `Cython` pre-installed before it can even compute its build
    requirements (`pip install --no-build-isolation` after installing `Cython` fixes this), and
    its source still uses Python-2-era `collections.MutableSequence` (moved to
    `collections.abc` in 3.10+) and bare `np.float`/`np.int` aliases (removed in numpy 1.24+,
    and this stack pulls numpy 2.5.2). All three were mechanical, well-documented one-line/sed
    fixes applied directly to the installed package in the venv, and after that `madmom` imports
    fine.
  - The actual stopper: `allin1`'s model code (`allin1/models/dinat.py`) imports `natten`
    (Neighborhood Attention Extension) — also an undeclared dependency, also not on `allin1`'s
    metadata. `pip install natten` has no prebuilt CPU wheel for this torch/Python combo, so pip
    falls back to building from source, and that build's own isolated env re-installs a full
    copy of `torch` from source-dist just to read `natten`'s build requirements. This alone
    blew well past a 5-minute budget with no completion in sight (still sitting in "Installing
    build dependencies" when killed) — this is a real, likely multi-minute-to-multi-hour C++/
    CUDA-extension compile, not a resolver hang like the CUDA-matrix issue from before. Killed
    it rather than let it run unbounded; not retried further.
  - Net: torch and allin1's own PyPI package are no longer the blocker. `madmom` is fixable by
    hand (done, see above). `natten` needing a from-source build with no CPU wheel is the new,
    specific, harder blocker — worth revisiting with a real time budget (an hour+) or a prebuilt
    natten wheel/conda package, not attempted here.
  - This workstream still runs entirely over the **existing causal beat tracker's grid**
    (`structure.ts`'s `BeatTracker`, replayed offline) plus a from-scratch checkerboard-novelty/
    peak-picking fallback for boundaries (SSM spec §1.3/§1.4, originally scoped as fallback-only,
    still load-bearing). If `allin1` (or its `natten` dependency specifically) is stood up
    later, swap its beat grid and boundaries in — the SSM/repetition-map math (`ssm.ts`) doesn't
    care where the beat grid came from.
- The adaptive threshold multipliers (1.5×MAD for both peak-picking and the repetition map) are
  tuned against 3 real tracks (`hysteresis`, `panicspiral`, `afterimage` — all ~120 BPM in this
  artist's catalog), not against a broad corpus. Real-track results were mixed: a clear,
  plausible intro/outro-bookend repeat surfaced on 2 of 3 tracks (sim 0.72-0.76), but
  `panicspiral` also produced several low-similarity (0.17-0.3) pairs that read as marginal/
  possibly spurious on inspection, not confirmed against the actual audio by ear. Treat the
  repetition map as a real, useful signal that still needs a human sanity pass, not a fully
  trusted oracle yet.
- No resampling/tempo hand-correction path built (SSM spec §0b's "confident-but-wrong tempo"
  caution) — out of scope without allin1's tempo output to correct.
- `analyze.ts`'s CLI doesn't yet expose a `--repeats`/schema-4 flag; `computeSchema4Sidecar` is
  library-only for now (see above).

## Verifying it still works

```
npm run typecheck   # tsc across all 4 tsconfigs, must stay clean
npx vitest run       # full suite; scripts/ tests: analyze.spec.ts, ssm.spec.ts, schema4.spec.ts
```

`tests/unit/ssm.spec.ts` has the real bite: a synthetic two-identical-halves case asserts the
SSM's cross-block mean similarity is >0.95 and clearly beats a different-halves control (<0.3);
a synthetic two-section case asserts a boundary peak lands within 4 beats of the true boundary;
a 3-section (A/B/A) case asserts the repetition map finds the non-adjacent A-A repeat and not
the adjacent A-B/B-A pairs. `tests/unit/schema4.spec.ts` confirms `analyzeMix()`'s schema-3
output is untouched and that a schema-4 sidecar round-trips through JSON with all new fields
intact.

To re-verify against real audio, point `computeSchema4Sidecar(decodeWavFile(path))` (from
`scripts/repetition.ts`) at any real WAV and inspect `.repeats`/`.sections` by ear against the
track — no automated real-track assertion exists yet (see limitations above: results need a
human sanity pass per track before trusting a hard numeric assertion).
