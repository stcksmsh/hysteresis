# OSC in/out

Streams the live signal bus out as real [OSC](https://opensoundcontrol.stanford.edu/spec-1_0.html)
(Open Sound Control) messages, so an external tool that understands OSC —
TouchDesigner, VCV Rack, Ableton (via Max for Live or an OSC-in device),
Resolume, etc. — can react to the same signals driving Hysteresis's own
visual, without a bespoke translation layer.

## Why a relay is involved

Real OSC almost always travels over UDP, and **browsers have no raw UDP
API at all** — the same underlying gap that makes Art-Net/sACN/DMX
inaccessible directly from a webapp (see `hysteresis-master-prompt.md` §3).
So the browser side speaks OSC over a WebSocket connection instead, and a
tiny local relay (shipped in this repo) forwards those bytes on to real UDP:

```
Hysteresis (browser) --WebSocket--> udp-relay (local Node process) --UDP--> your OSC-receiving tool
```

The relay does no encoding/decoding of its own — Hysteresis already sends
complete, valid OSC packets over the WebSocket, so the relay just forwards
each message as one UDP datagram, unchanged.

## Running it

```sh
npm run udp-relay -- --ws-port 9090 --udp-host 127.0.0.1 --udp-port 9000
```

Defaults: `--ws-port 9090`, `--udp-host 127.0.0.1`, `--udp-port 9000` — point
`--udp-port` at whatever port your receiving tool listens for OSC on (e.g.
TouchDesigner's OSC In DAT, VCV Rack's OSC module).

Then, from a page using the package:

```ts
const instance = init(canvas, opts)
instance.setOscOut('ws://localhost:9090', (status) => {
  console.log(status.connected ? 'OSC connected' : `OSC disconnected: ${status.message ?? ''}`)
})
// ...later
instance.setOscOut(null) // disconnect
```

The local dev harness (`npm run dev`) has a small "OSC connect"/"OSC
disconnect" control wired to this exact API, for trying it out without
writing any code.

## What gets sent

Every routable signal bus value (the same set a patch graph `signal` node
can read — loudness bands, spectral centroid, beat/bar phase, build/drop/
break structure, and more), each as its own OSC message, all bundled
together once per send:

```
/hysteresis/bus/energy       f 0.62
/hysteresis/bus/centroid     f 0.41
/hysteresis/bus/tension      f 0.0
/hysteresis/bus/dropImpulse  f 0.0
...
```

Sent at 20Hz (throttled independently of render frame rate — fast enough to
feel live, far below the cost of doing this every rendered frame). `scope`
(the oscilloscope beam's raw waveform buffer) and `idle` (a meta flag, not
a signal) are not included — same exclusion the patch graph itself applies.

## OSC in

An incoming OSC message from an external tool is now routable into the
patch graph with an `oscIn` node (`patchgraph/types.ts`), the same way a
`signal` or `midiCc` node is — wire a `curve`/`threshold`/`envelope` chain
into it exactly like any other source, addressed by the message's own OSC
address string (e.g. `/1/fader1`). Only a message's first numeric-ish
argument (float/int/bool) is stored; a string-typed argument is dropped
rather than coerced (see `src/osc/osc-in-bridge.ts`'s own doc comment).

This direction needs the relay to also listen for inbound UDP and forward
it back over the WebSocket — pass `--osc-in-port`:

```sh
npm run udp-relay -- --ws-port 9090 --udp-host 127.0.0.1 --udp-port 9000 --osc-in-port 9001
```

Point your OSC-sending tool at `udp://<this machine>:9001`. Then, from a
page using the package:

```ts
const instance = init(canvas, opts)
instance.setOscIn('ws://localhost:9090', (status) => {
  console.log(status.connected ? 'OSC in connected' : `OSC in disconnected: ${status.message ?? ''}`)
})
// ...later
instance.setOscIn(null) // disconnect
```

`--osc-in-port` is optional (omit it, or pass `0`, and the relay behaves
exactly as it did before this option existed — no inbound listening at
all) since a relay only ever used for `setOscOut`/DMX has nothing to gain
from an extra open port.

## Status today

Both directions are real. Not built: OSC address pattern matching (an
`oscIn` node matches one exact address, not a wildcard), and there's no
UI in the patchbay editor showing which addresses have actually arrived
(the OSC in panel shows connection status only, not a live value log —
unlike the MIDI panel's CC activity list).
