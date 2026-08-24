# Hysteresis docs

User-facing documentation for the patchbay editor tool and the concepts
behind it — separate from `AGENTS.md` (the single AI-facing reference:
architecture, target spec/backlog, and session-by-session engineering notes
for future contributors).

- [Patchbay editor](./patchbay-editor.md) — running the tool, the signal
  bus / patch graph / targets / fixtures mental model.
- [ISF shaders](./isf-shaders.md) — loading a real ISF (`.fs`) shader as
  the screen scene and patching signals into its inputs.
- [OSC out](./osc.md) — streaming the signal bus to external tools
  (TouchDesigner, VCV Rack, Ableton, ...) as real OSC.
- [DMX out (Art-Net / sACN / USB)](./dmx-out.md) — sending patched
  fixtures out to a real lighting rig, console, or USB dongle.
- [MIDI in](./midi.md) — real MIDI CC input and clock/beat sync via Web
  MIDI.
- [ILDA / laser DAC support](./ilda.md) — the real ILDA file format and
  the Ether Dream live laser DAC protocol.

This folder is versioned with the code: docs and the feature they describe
should never drift out of sync across a rename or a PR. If it ever needs to
also live on the GitHub Wiki tab, these files can be pushed there verbatim —
nothing here assumes an in-repo-only home.
