# СИНТЕЗА — offline structure analysis: closing the SSM gap

Repo: `hysteresis` (formerly `sinteza-viz`)
Status: design spec, not yet implemented. Targets `scripts/structure.ts` and
`src/shared/sidecar.ts` precisely — both read in full before writing this.

Context this assumes: AGENTS.md §2 (architecture), §4 (Layer 2 understanding — this doc's
own thesis and taxonomy already live there, near-verbatim from the retired
`SINTEZA_UNDERSTANDING.md`). This spec does not restate that context; it closes one specific,
named gap in it.

---

## 0. The gap, precisely

AGENTS.md §4.4 already says it plainly: *"Repetition map... SIDECAR, not attempted (needs a
full offline SSM this plan doesn't build)."* Reading `scripts/structure.ts` confirms exactly
why, and confirms it's not just the repetition map:

- `analyzeMix()` is a single forward pass. `BeatTracker`/`BuildDetector`/`DropDetector`/
  `BreakDetector` run causally, per hop, in real time order — the *same* logic the live worklet
  runs, just replayed once offline. This is correct and sufficient for what it's used for
  (tempo, beats, drop/break events — genuinely one-shot phenomena a causal detector finds fine).
  It is not a look-ahead structural analysis, despite running "offline."
- `buildWindowsFromDrops()` does not look at the buildup's own features at all — it draws a
  fixed `BUILD_WINDOW_BARS = 8` box backward from each detected drop time. A build that's 4
  bars or 16 bars gets the same window regardless of what the audio actually does.
- There is no matrix anywhere in the file. No feature-vector buffer survives past the per-hop
  loop except as flattened, already-decimated envelopes (`downsample()`). Nothing is ever
  compared to anything outside a small causal window.
- Consequently: section *boundaries* are approximate/heuristic-derived from event replay, not
  real segmentation; the *repetition map* (this section = that earlier section) has no
  substrate to be built from at all.

**What is NOT the gap, so this spec doesn't touch it:** the live, per-frame `noveltyLocal`/
`noveltySection`/`familiarity` signals on the `SignalBus` (AGENTS.md §4.2) are real, implemented,
and verified against real audio via an online causal ring-buffer + half-kernel. That's the
correct design for the live/unknown-audio case and stays exactly as-is. This spec is entirely
about the **offline** sidecar-generation path, where the whole track is already sitting in
memory and there is no principled reason to stay causal.

---

## 0b. REVISION (post-research): use `allin1`, don't hand-roll most of this

Research into current MIR practice changed the plan for this doc substantially. **`allin1`
(All-In-One Music Structure Analyzer)** predicts BPM, beats, downbeats, segment boundaries, *and*
functional segment labels from audio in one tool, using neighborhood attentions on **demixed**
audio (Kim & Nam, WASPAA 2023; Python package `allin1`, plus a "Music Dissector" visualizer).

This matters because the pipeline **already runs Demucs offline** for stem presence (AGENTS.md
§4.3) — the demixing this model wants is already paid for. One packaged, learned model therefore
replaces three things this doc originally proposed hand-building:

| Originally planned here | Replaced by |
|---|---|
| Beat grid from causal `BeatTracker` replay | `allin1` beats + downbeats |
| §1.3/§1.4 checkerboard novelty → boundaries | `allin1` segment boundaries |
| Heuristic intro/outro labeler (`labelSections`) | `allin1` functional segment labels |

**What is still worth building ourselves: the repetition map (§1.5).** `allin1` does not output
"this section is a repeat of that earlier section," and that fact is precisely what the
choreography layer needs for phrase reuse (`SINTEZA_CHOREOGRAPHY.md` §4.2). Build the SSM
(§1.1–§1.2) over **`allin1`'s** beat grid rather than our own — cleaner input, same math, and the
novelty/peak-picking machinery (§1.3–§1.4) is no longer needed since boundaries come from the
model.

**Two cautions carried from the literature into the compiler:**
- Beat-tracking models tend to produce *confident-but-wrong* activations, and madmom's default
  55 BPM tempo floor forces double-tempo predictions on ~21% of slow tracks. **Do not blindly
  trust reported tempo** — sanity-check it (especially slow material) and make it
  hand-correctable in the sidecar, consistent with this project's existing "verify the handful
  of drops, takes a minute" discipline.
- `allin1` is Python/offline only. **The live path is unchanged** — the browser AudioWorklet PLL
  stays exactly as-is. (For reference, real-time SOTA is BeatNet — CRNN + particle filtering,
  joint beat/downbeat/tempo/meter — and BEAST, which reaches 80.04% beat / 52.73% downbeat F1
  under 50 ms latency, ~5 and ~13 points over prior SOTA. Both are Python, so neither is
  drop-in for a browser worklet; noted for completeness, not proposed.)

Sections §1.1–§1.5 below are retained as written, with §1.3/§1.4 now **optional/fallback** (a
no-Python-dependency path, or if `allin1` proves unsuitable on this material) rather than the
primary plan. §1.1/§1.2/§1.5 remain primary — they are what the repetition map needs.

---

## 1. What gets added

One new pass in `structure.ts`, run **after** the existing per-hop loop, operating on data the
loop already computes (or can compute for negligible extra cost). Nothing about the existing
loop's live-parity primitives (`BeatTracker`, `DropDetector`, etc.) changes.

### 1.1 Beat-synchronous feature vectors

The loop already has `beats: number[]` (timestamps) and per-hop `bandRaw`/`centroidRaw`/
`flatnessRaw` arrays (`Float32Array`, length `totalHops`, currently only consumed by
`downsample()`). Add: for each inter-beat interval `[beats[i], beats[i+1])`, average the hops
falling in it across `bandRaw.sub/low/mid/presence/air`, `centroidRaw`, `flatnessRaw` → one
7-dimensional feature vector per beat. This reuses data already computed; the only new cost is
the averaging pass, O(totalHops), negligible next to the FFT loop already run.

**Normalize each of the 7 dimensions independently across the whole track** (z-score: subtract
the track's mean, divide by its std, per dimension) before anything else. Skip this and the SSM
is dominated by whichever raw dimension has the largest scale — this is the standard MSA
practice (AGENTS.md §4.1) and it is not optional.

Call this sequence `beatFeatures: Float32Array[]`, length = `beats.length`.

### 1.2 The Self-Similarity Matrix

Build the full `N × N` matrix (`N = beats.length`), `SSM[i][j] = cosineSimilarity(beatFeatures[i],
beatFeatures[j])`, `0..1`. For a typical track (~120 BPM, 4 minutes → N ≈ 480), this is ~230k
cosine evaluations on 7-dim vectors — trivial, sub-millisecond-class cost for a one-time offline
script. No approximation needed; do not skip beats or downsample further. Symmetric, so only
compute the upper triangle and mirror.

### 1.3 Multi-scale checkerboard novelty

Standard Foote novelty (AGENTS.md §4.1): correlate a checkerboard kernel along the SSM's main
diagonal. Build **two kernels, two scales**, matching the live signals' own naming so the two
paths read as the same idea at two speeds:

- `noveltyLocalOffline` — small kernel (~4–8 beats radius). Phrase-scale: a fill, a new element
  entering, a small variation.
- `noveltySectionOffline` — large kernel (~16–32 beats radius, tune by ear against real tracks;
  start around 8 bars' worth of beats). Section-scale: verse→chorus, breakdown→drop.

At the diagonal's edges (first/last `kernelRadius` beats) the kernel doesn't fully overlap the
matrix — zero-pad the missing side (AGENTS.md §4.1's own noted EDM-research practice: padding
loudness novelty with zeros, not the trivial no-data value, is what makes intros behave). This
is a direct, non-causal counterpart to the live path's causal half-kernel — same kernel, full
window instead of half, because offline has both directions available.

### 1.4 Peak-picking → real section boundaries

Standard local-maximum peak-picking on `noveltySectionOffline` (a peak = a value that's the max
within a window of ± a few beats, above an adaptive threshold — e.g. the curve's own median plus
some multiple of its MAD, not a fixed constant, so it self-calibrates per track's dynamic range).
The resulting peak times **are** the section boundaries — this replaces relying on
`buildWindowsFromDrops`'s fixed-bar guess and on `breakSectionsFromEvents`'s break-event-pair
logic as the *only* source of structure. Concretely:

- **Real build-window derivation**: for each detected drop time (still found the existing way —
  `DropDetector` is unchanged), walk backward through `noveltySectionOffline`'s boundary peaks to
  find the nearest preceding one. *That* peak — not a fixed 8-bar count — is the real start of
  the build, because it's the point where the audio's own features actually changed character.
  Fall back to the fixed-bar heuristic only if no boundary peak exists before the drop within a
  generous outer limit (handles a drop with no real lead-in, e.g. right after the intro).
- **`noveltyLocalOffline` peaks** become a new, optional, lightweight event stream — phrase-level
  markers, useful later for choreography (a smaller gesture can key off these without being a
  full section change) — not required to consume this spec's core deliverable.

### 1.5 The repetition map (the one §4.4 explicitly flagged as blocked on this)

Once the full `SSM` exists, this is nearly free. A repetition = an off-diagonal region of
sustained high similarity (a path parallel to the main diagonal, not just a single high cell —
single high cells are noise, sustained diagonal runs are real repeated material). Algorithm:
for each pair of boundary-delimited sections (from §1.4) that aren't adjacent, compute the mean
`SSM` value over their cross-block (section A's beat-range × section B's beat-range); if it
exceeds a threshold (again, adaptive — track median/MAD), record a repeat link.

Output: `repeats: SidecarRepeat[]`, each `{ aStart, aEnd, bStart, bEnd, similarity }` (times in
seconds, matching every other sidecar field's units). This is genuinely new information nothing
in the current pipeline produces, and it's the natural authoring seam for choreography later —
"the dance for this chorus is the same as the dance for that earlier chorus" becomes a real,
computed fact instead of something a human has to notice by ear.

---

## 2. Sidecar schema change

Additive only, following the schema 2→3 precedent exactly (`AGENTS.md`'s own stated rule: never
break the live production path; a schema-2 sidecar already published must keep validating).
Bump to **schema 4**.

New fields on `Sidecar`, all optional so nothing currently depending on schema 3 breaks:
- `repeats?: SidecarRepeat[]` (§1.5).
- `noveltyLocalEnvelope?: number[]`, `noveltySectionEnvelope?: number[]` — the two offline
  novelty curves themselves, sampled at the existing `envelopeRate` (20 Hz) like every other
  envelope, via the same `downsample()` machinery already used for bands/centroid/flatness. Not
  strictly required to consume §1.4/§1.5's outputs, but cheap to include and directly useful:
  lets `StructureSource` expose a *precise, look-ahead* structural-novelty curve for own-tracks,
  distinct from (and more accurate than) the live causal approximation — same relationship as
  sidecar-primary drops vs. the live drop fallback.

`SidecarSection` gains one optional field:
- `boundaryConfidence?: number` — the novelty peak's own magnitude at that boundary (0..1,
  relative to the track's own novelty range). Lets a consumer (a future choreography timeline,
  or just tuning) distinguish a sharp, obvious boundary from a soft, ambiguous one, rather than
  treating every detected boundary as equally certain.

`SidecarRepeat` (new interface):
```
export interface SidecarRepeat {
  aStart: number
  aEnd: number
  bStart: number
  bEnd: number
  similarity: number // 0..1
}
```

No change to `buildWindowsFromDrops`'s signature or `breakSectionsFromEvents` — they still run,
still produce sections; §1.4's boundary-informed build-window derivation is a refinement *of*
`buildWindowsFromDrops`'s internals (a better backward-walk instead of a fixed count), not a
replacement of its call site or output shape.

---

## 3. What explicitly does not change

- The live worklet path (`src/audio/worklet/**`, `src/audio/worklet/brain/**`) — zero changes.
  This spec is entirely inside `scripts/structure.ts` (offline) plus `src/shared/sidecar.ts`
  (schema).
- `DropDetector`/`BreakDetector`/`BuildDetector` logic itself — unchanged. They still find the
  one-shot events they're good at finding; the SSM pass only refines what surrounds those
  events (build-window extent, section boundary times), not whether an event fired.
- `StructureSource.fuse()`/`synthesize()`'s existing behavior for schema-2/3 sidecars — a schema-4
  sidecar validates and plays back identically for any consumer that doesn't yet read the new
  optional fields, per the additive-schema rule.
- `hysteresisSignal`/`HYSTERESIS_SCRIPT`/the `.hyst` format — untouched; out of scope for this
  spec entirely.

---

## 4. Build order (REVISED per §0b)

0. **Integrate `allin1`** into the offline pipeline, alongside the existing Demucs shell-out
   (`scripts/demucs.ts` — same subprocess pattern): beats, downbeats, tempo, boundaries, labels.
   Add a tempo sanity-check + hand-correction path (§0b's caution). This replaces causal-replay
   structure as the source of the beat grid and section boundaries.
1. Beat-synchronous feature extraction + normalization (§1.1), **over `allin1`'s beat grid** — no visible output yet, just the
   `beatFeatures` array; verify by unit test on synthetic beats with known feature values.
2. Full SSM construction (§1.2) — unit test on a synthetic case with an obvious repeated block
   (e.g. two identical halves) and confirm the matrix shows it.
3. *(OPTIONAL/FALLBACK ONLY per §0b — skip unless `allin1` proves unsuitable)* Multi-scale checkerboard novelty + peak-picking (§1.3/§1.4) on a synthetic two-section signal
   with a known boundary; confirm the peak lands within a few beats of the true boundary.
4. Wire §1.4's boundary-informed build-window derivation into `buildWindowsFromDrops`, with the
   fixed-bar fallback retained. Verify against a real track headlessly (matching the project's
   own established verification discipline — AGENTS.md's "headless real-audio verification"
   entries) that build windows now vary in length rather than always being exactly 8 bars.
5. Repetition map (§1.5) — verify against a real track with an obvious repeated chorus.
6. Schema-4 additions to `sidecar.ts` (§2) — additive fields, existing schema-2/3 fixtures/tests
   must still pass unmodified.
7. `StructureSource` exposure of the new optional fields as bus signals (`noveltyLocalOffline`/
   `noveltySectionOffline`/`repeats` made available for own-tracks the same way existing
   sidecar-only fields are) — only after 1–6 are verified; this step is what makes the new data
   actually reachable by a consumer (e.g. the choreography-timeline work planned next).

Each step is independently testable and shippable; nothing here requires the physical/servo
path or blocks anything else in flight.

---

## 5. Why this specifically feeds what's next

The choreography-timeline layer (planned next, per current priority order) needs exactly two
things this spec produces and nothing currently in the codebase does: **precise, non-causal
section boundaries** (so an authored "move" can be anchored to a real structural change instead
of a heuristic replay) and **the repetition map** (so a choreographed sequence for one chorus can
be reused, not re-authored, for every later repeat of that chorus — "dance the same phrase again
here" becomes a lookup, not a manual re-annotation). Building this first is not a detour from the
dance vision; it's the specific piece of ground the dance vision needs to stand on.
