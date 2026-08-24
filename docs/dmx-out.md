# DMX out (Art-Net / sACN / USB / WLED)

Sends the patchbay editor's fixture channel values out over real
[Art-Net](https://art-net.org.uk/resources/art-net-specification/),
[sACN/E1.31](https://tsp.esta.org/tsp/documents/published_docs.php), a
USB-DMX dongle, or a [WLED](https://kno.wled.ge/) LED controller's own
realtime protocol — to an actual DMX lighting rig, console, software
(TouchDesigner, QLC+, an Art-Net node), or LED strip, not just the editor's
own simulated visuals.

## Setup

1. **Patch your fixtures** — in the editor's **Fixtures** panel, each
   fixture instance now has a `DMX: [universe] @ [address]` field. Set a
   universe number and the DMX512 start address (1..512) its first channel
   should occupy. A fixture with no DMX patch set only drives the
   simulated preview, same as before this feature existed.
2. **Run the relay** — browsers can't send real Art-Net/sACN (UDP) directly
   (see `docs/osc.md`'s explanation, same underlying gap):
   ```sh
   npm run udp-relay
   ```
   Defaults to `ws://localhost:9090`. No `--udp-host`/`--udp-port` flags
   needed for Art-Net/sACN specifically — the **DMX out** panel tells the
   relay exactly where each universe's packet goes (broadcast for Art-Net,
   the standard per-universe multicast group for sACN), per-message.
3. **In the editor's DMX out panel**, pick one of four modes:
   - **Art-Net** or **sACN (E1.31)** — confirm the relay URL, hit
     **Connect**, then **Start sending**. Patched fixtures' live values
     (whatever the patch graph currently resolves them to) go out at ~25Hz.
   - **WLED (UDP realtime)** — the friendly, DMX-concept-free on-ramp for
     LED strip owners. Pick the universe your WLED-driven fixtures are
     patched into, enter the WLED device's own IP address, **Connect**,
     then **Start sending**. Under the hood this reuses the exact same
     universe buffer Art-Net/sACN send — patch your `rgb`-type fixtures at
     contiguous addresses starting from 1 in one universe and that buffer
     IS a plain sequential pixel stream, no DMX-specific concept needed on
     the WLED side at all. (You could also just point a WLED device at
     sACN with a matching universe — WLED speaks that natively too — this
     mode exists because *not needing to think about sACN/universes at
     all* is the actual "friendly on-ramp" master-prompt.md §5 asks for.)
   - **USB (Enttec-protocol dongle)** — no relay needed at all; this path
     is genuinely browser-native (Web Serial). Pick the universe to send
     (a USB dongle only ever drives one), click **Select serial port…**
     (the browser's own device picker), then **Start sending**. Chromium
     desktop only — Safari/Firefox and all mobile browsers don't implement
     Web Serial (see "What's not built yet" below).

## What's real here

- **Real, spec-shaped packet encoders**: `src/dmx/artnet.ts`
  (Art-Net ArtDMX), `src/dmx/sacn.ts` (sACN/E1.31 Data Packet — Root/
  Framing/DMP layers), `src/dmx/enttec-usb-pro.ts` (the Enttec DMX USB PRO
  Widget API framing most USB-DMX dongles either speak directly or clone),
  `src/dmx/wled.ts` (WLED's own "DRGB"/"WARLS" realtime UDP protocols) —
  actual protocol byte layouts, not simplified stand-ins.
- **Real universe rendering** (`src/dmx/render-dmx-universe.ts`) — every
  DMX-patched fixture's resolved channel values, scaled from that channel's
  declared range onto a real DMX byte (0..255), written at its patched
  address into a 512-byte universe buffer.
- **A real relay** (`scripts/udp-relay.ts`, `npm run udp-relay`) — the same
  process the OSC-out feature uses (see `docs/osc.md`), extended to also
  forward a small JSON envelope (`{ host, port, bytes }`) to a
  per-message UDP destination, since Art-Net/sACN/WLED each address a
  different destination per message rather than one fixed target. Only
  needed for Art-Net/sACN/WLED — USB doesn't use it at all.
- **Real Web Serial output** (`src/dmx/dmx-serial-output.ts`) — talks
  directly to a real USB-DMX dongle's serial connection from the browser,
  no relay process in the loop. Enttec's framed protocol is what makes this
  possible at all: the dongle's own firmware generates the real DMX
  signal/break, so the host only needs an ordinary serial write, which Web
  Serial can do — a raw "Open DMX USB"-style dongle (host generates the
  break itself) is NOT reachable this way, since Web Serial has no
  send-break API.

## What's not built yet

- **No 16-bit ("coarse/fine") channel support** — every channel is a
  single 8-bit DMX byte. A fixture profile needing fine pan/tilt resolution
  isn't modeled.
- **No fixture profile import** (e.g. GDTF/QLC+ fixture definition files) —
  fixture types are the small built-in set in `fixture-types.ts`.
- **USB requires Web Serial**, which only Chromium-based desktop browsers
  implement — Safari has an explicit stated position against it
  (fingerprinting concerns), and no mobile browser supports it at all.
  Un-supported browsers get a clear message in the panel rather than a
  silent failure.
- **Art-Net/sACN/WLED now have a real production path** (see AGENTS.md's
  "Wire the fixture patch graph into production" session):
  `VizInstance.setFixtureDocument()`/`setFixtureGraph()`/`setFixtureOut()`
  run a real `FixtureOutput` inside the shipped render worker
  (`src/render/conductor/outputs/FixtureOutput.ts`), evaluating the fixture
  patch graph every frame and sending real DMX universes out over the same
  WebSocket relay OSC uses — a host embedding this package (not just the
  patchbay editor) can now actually drive a lighting rig. **USB (Web
  Serial) is still editor-tool-only** — `DmxSerialOutput.connect()` needs a
  main-thread user-gesture `requestPort()` call, which a background render
  worker can never trigger, so that leg has no production counterpart and
  isn't expected to get one without a different mechanism (e.g. the host
  page obtaining the port itself and transferring it in).
