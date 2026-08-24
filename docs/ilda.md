# ILDA / laser DAC support

Two related but distinct capabilities, both implemented against real,
researched specifications rather than guessed:

1. **ILDA file format** (`src/ilda/ilda-format.ts`) — export/import the
   actual `.ild` file format real laser show software (Pangolin Beyond,
   LaserOS, QuickShow) and hardware read.
2. **Ether Dream protocol** (`src/ilda/ether-dream.ts`) — the live,
   real-time streaming protocol for [Ether Dream](https://ether-dream.com/)
   laser DACs, the most widely used *open* laser DAC protocol (the
   hardware/firmware behind many open-source laser projects).

## Sourcing and confidence

Both were implemented from real, published references, not memory — the
master-prompt backlog originally flagged ILDA as the one protocol in this
whole arc *not* to guess at, since a wrong binary format looks done but
silently fails to load. What was actually used:

- **ILDA file format**: the ILDA Technical Committee's own IDTF spec
  (Revision 011, [PDF](https://www.ilda.com/resources/StandardsDocs/ILDA_IDTF14_rev011.pdf)),
  cross-checked against [nannou-org/ilda-idtf](https://github.com/nannou-org/ilda-idtf),
  a real, maintained Rust implementation of the same spec. Both agree on
  every byte offset used here.
- **Ether Dream**: the official [protocol page](https://ether-dream.com/protocol.html),
  cross-checked against **two** independent real implementations —
  [tgreiser/etherdream](https://github.com/tgreiser/etherdream) (Go) and
  [echelon/etherdream.rs](https://github.com/echelon/etherdream.rs) (Rust).
  This cross-check actually caught a real error: an initial AI-summarized
  read of the protocol page said the DAC status struct was 18 bytes; both
  real implementations agree it's actually 20 bytes (and the response/
  broadcast packet sizes that include it are 22/36 bytes, not 20/34). The
  final code here matches both real implementations exactly.
- **One remaining lower-confidence detail**: Ether Dream's "queue rate
  change" ('q') command is described on the protocol page, but **neither**
  reference implementation actually implements it — the Go library has an
  `Update` method using byte `'u'` instead, with its own author's comment
  "Maybe this is the 'q' command now," i.e. genuinely unsure. `encodeQueueRateChangeCommand()`
  is implemented per the spec page, but flagged in its own doc comment as
  the one command here not cross-verified against a second source. Confirm
  against a real DAC before depending on it.

## What's real and tested

- **`ilda-format.ts`**: encode/decode a real ILDA section header (32 bytes,
  every field's byte offset verified against both sources above), point
  records for all defined formats (0/1/4/5 — 3D/2D × indexed/true color),
  the format-2 color palette, and `encodeIldaFile()`/`decodeIldaFile()` for
  a complete multi-frame file with the mandatory end-of-file marker
  (`numRecords === 0`) and automatic `LAST_POINT` status-bit placement.
- **`ether-dream.ts`**: `DacStatus`/`DacBroadcast`/`DacResponse` decoders,
  `DacPoint` encode/decode (the real 18-byte point layout, little-endian —
  a real, confirmed difference from ILDA's big-endian file format), and
  encoders for every real command (Prepare, Begin, Data, Stop, Emergency
  Stop, Clear E-Stop, Ping, plus the lower-confidence Queue Rate Change).
- **`scripts/tcp-relay.ts`** (`npm run tcp-relay`) — Ether Dream's TCP
  connection (port 7765, one persistent bidirectional session per DAC,
  unlike Art-Net/sACN/OSC/WLED's fire-and-forget UDP) needs a different
  relay shape than `udp-relay.ts`: this one duplexes a WebSocket connection
  with one TCP connection, forwarding bytes both ways, doing no protocol
  interpretation itself (same "dumb forwarder" philosophy). **Real,
  end-to-end tested**: `tests/unit/tcp-relay.spec.ts` uses a real TCP
  server standing in for the DAC and a real `ws` client, confirming bytes
  cross the relay correctly in both directions and that the WebSocket
  closes when the TCP connection does.

## What's not built yet

- **No browser-side `EtherDreamClient`** implementing the actual
  prepare→data→begin command sequence and ACK-tracking state machine over
  the relay — the protocol byte layer above is real and tested, but
  nothing yet drives it end-to-end from the patchbay editor.
- **No laser "point source" in the patch graph** — there's no fixture/
  target concept yet for "a stream of XY+RGB laser points," the way a
  dimmer/RGB/servo fixture exists for DMX. Building one (and deciding what
  drives the actual beam path — an ISF-shader-like scripted path? signal-
  bus-modulated geometric shapes?) is real, separate design work.
- **Not verified against real hardware** — no Ether Dream DAC or ILDA-
  reading software available in this environment. The encoders are
  verified for internal correctness and cross-checked against independent
  real implementations (see above), which is a meaningfully higher bar
  than "typechecks," but isn't the same as a real device confirming it.
