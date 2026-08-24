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

## Operating mode

- **Gap-analysis first, every time you resume.** Don't assume where the
  last session left off. Diff the master prompt's §4 target shape and §6
  backlog against what's actually in the repo (grep for the relevant
  modules, check AGENTS.md). The repo already has a signal bus, a unified
  patch-graph engine (screen + fixture targets, see AGENTS.md's "unify
  screen + physical patch graphs" session), and a visual node canvas
  editor — treat these as foundations to extend, not things to rebuild.
- **One coherent slice per session, picked by §5's priority order**
  (ISF → OSC → Art-Net/sACN → DMX-serial → MIDI → ILDA → WLED/E1.31),
  cross-checked against §6's backlog checkboxes. Don't split effort across
  multiple backlog items in parallel unless one is genuinely trivial.
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
