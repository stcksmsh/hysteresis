# Hysteresis — resume prompt

You're continuing work on Hysteresis (repo: `stcksmsh/hysteresis`, package
`sinteza-viz`). Read in this order before touching anything:

1. `hysteresis-master-prompt.md` — the target architecture/scope (§4 pipeline,
   §5 protocol priority order, §6 backlog checklist, §7 design principles).
   This is the spec of record for where the project is going.
2. `AGENTS.md` — session-by-session history of what's actually been built,
   what's verified vs. not, known gaps. Trust this over assumptions about
   current state.
3. `SINTEZA_SIGNAL_BUS.md` / `SINTEZA_VIZ.md` — the existing signal
   bus/patchbay/render architecture the master prompt is extending, not
   replacing.

## Non-negotiable constraints, in priority order

1. **Never break the live production path.** The current renderer runs
   24/7 unattended on a real site (`stcksmsh.github.io`). Every commit must
   leave `npm run typecheck`, `npm test`, `npm run build`, and
   `npm run build:lib` green. If a master-prompt feature can't be added
   without regressing this, stop and say so — don't silently trade
   reliability for scope.
2. **Legibility over feature count.** Every UI surface you touch or add
   must be as usable/readable as the patchbay editor's current state (dark
   theme, clear visual hierarchy, no dead/hidden controls, real labels not
   ids). If a new subsystem needs UI, it needs *good* UI in the same pass,
   not a bolted-on debug view.
3. **Ship working slices, not partial scaffolding.** A half-built ISF
   importer that can't actually load a real ISF file is worse than not
   starting it. Definition of done for any slice: it does the real thing
   end-to-end, is tested, and is verified (real browser check when it's
   visual/interactive — flag clearly if you lack browser access, same as
   prior sessions).
4. **Protect extensibility ("infinite possibilities").** Per §7 of the
   master prompt: prefabs/built-ins must be built *through* the same
   extension mechanism a user would use, never as a hardcoded special case
   sitting next to a thinner "real" plugin API. Before calling any new
   subsystem done, ask: could a user replace/extend this the same way I
   just built it? If no, it's not done.

## Where things actually stand (as of the last two sessions — verify against AGENTS.md's newest entries before trusting this, it will drift)

All seven §5 protocols have real, tested work landed, and the two biggest
recurring gaps flagged across those sessions are now closed too:
- Art-Net/sACN/WLED run for real in production (`FixtureOutput` inside the
  render worker, `VizInstance.setFixtureDocument/setFixtureGraph/
  setFixtureOut`) — not just the patchbay editor anymore.
- `midiCc` and `oscIn` patch-graph node kinds exist, so a live MIDI CC or
  an incoming OSC message routes into the graph exactly like a bus signal.
- The patchbay editor now dogfoods the production fixture API (no more
  separate ephemeral evaluator living only in `App.tsx`).

**§5's protocol priority order no longer dictates the next slice** — it's
fully covered. Do a fresh gap-analysis against the WHOLE master prompt
(§4's target pipeline shape + §6's backlog, not just §5) to pick what's
next. Candidates already identified but not started, in no particular
order: Feature Engine plugin interface, ISF superset (novelty/similarity/
section-confidence as shader inputs), macro/sub-patch blocks, live inline
node value preview on the graph canvas, fixture profile import (GDTF/
QLC+), presentation/export mode, MIDI clock → Conductor tempo sync, ILDA
production wiring (protocol layer is real; no live client, no patch-graph
"laser point stream" concept exists yet), content-hash-keyed sidecars,
graph versioning/undo. Don't assume this list is exhaustive or still
accurate — re-derive it from `hysteresis-master-prompt.md` §6's checkboxes.

**Standing caveat across ALL of the above**: none of it has been verified
against real hardware or a real browser (no MIDI controller, no external
OSC sender, no Art-Net/sACN receiver, no laser DAC, no browser access in
these sessions). Everything is typechecked and unit-tested at the logic
layer only. If you get real hardware/browser access, closing that loop for
any one protocol is higher-value than starting new scope.

## Operating mode

- **Gap-analysis first, every time you resume.** Don't assume where the
  last session left off. Diff the master prompt's §4 target shape and §6
  backlog against what's actually in the repo (grep for the relevant
  modules, check AGENTS.md's newest entries — trust those over this file,
  which is not updated every session and will drift). The repo already has
  a signal bus, a unified patch-graph engine (screen + fixture targets,
  now with midiCc/oscIn external-input node kinds too — see AGENTS.md's
  "unify screen + physical patch graphs" and "MIDI CC + OSC-in" sessions),
  a visual node canvas editor that dogfoods the production fixture API,
  and a worker-resident FixtureOutput driving real Art-Net/sACN/WLED —
  treat all of this as foundations to extend, not things to rebuild.
- **One coherent slice per session.** Pick it from a fresh read of §6's
  backlog checkboxes (see "Where things actually stand" above for
  candidates), not from §5's protocol order, which is exhausted. Don't
  split effort across multiple backlog items in parallel unless one is
  genuinely trivial.
- **Update the backlog as you go.** Check off `§6` items in
  `hysteresis-master-prompt.md` itself as they land, so it stays a living
  tracker across sessions, not a static wishlist.
- **Keep AGENTS.md's convention going**: append a dated/titled section per
  session summarizing what changed, what's verified vs. not, and what's
  explicitly deferred — this is how continuity survives repeated context
  clears.
- **Respect §2's non-goals as hard scope boundaries** (not a general
  compositor, not a full lighting console, not a DAW, not reinventing
  ISF/OSC/Art-Net) — if a design decision would blur one of these, don't
  make it without flagging it first.
- If a decision genuinely needs the user's input (licensing stance,
  Bridge daemon signing, sidecar compute location — §8's open questions),
  ask; don't guess and proceed on things that are expensive to reverse.

Start by doing the gap analysis and proposing the single next slice before
writing code.
