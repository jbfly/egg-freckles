# EF25 physical iPad one-Send result — synchronous-connect diagnostic

Date: 2026-08-11. Parent: branch-base commit `338e3662` carrying the EF25
source and package. This curated record contains no raw pcap, local path,
hostname, network address, process/container identifier, or ephemeral port.
No photo was taken, so it makes no visual claim.

## Direct observation

- EF25 package version 39 (`EggFrecklesEF25:jbfly`) was installed and open in
  the iPad Einstein runtime with the chat service selected.
- The operator entered `/status`, tapped **Send once**, and did not retry.
- The visible sequence was `Connecting to active server; will send...` then
  `Connect exception`.
- No HS-A, HS-B, or HS-C status appeared, and no reply arrived.

EF25's synchronous `Bound` block is preserved at
`../ef25-sync-connect/handshake-source.txt:2-21`. Its direct `:Connected()`
continuation is at lines 17-18, followed by the `Connect exception` handler at
line 19; an exception therefore occurs before `:Connected()` can paint HS-A or
send the marker and `HELLO`.

## Curated packet and service evidence

The capture covered the single Send. Its sanitized derivative is
`packet-summary.txt`; the raw pcapng is deliberately not committed.

| Fact | Result | Evidence |
|---|---:|---|
| Packets captured | 15 | `packet-summary.txt:17` |
| Capture drops | no drops recorded; no pcapng drop counter | `packet-summary.txt:18-19` |
| TCP handshakes | 3 | `packet-summary.txt:20-26` |
| Service greetings | 3 × 48 bytes | `packet-summary.txt:20-29` |
| Client TCP payload | 0 frames / 0 bytes | `packet-summary.txt:30-31` |
| Harness strings | no matches | `packet-summary.txt:32-33` |
| Accepted connections | 3 | `service-journal-excerpt.txt:7-9` |

Each handshake was followed by one 48-byte service greeting and a client ACK.
The client sent no TCP payload. The normalized service-journal summary
corroborates only the three accepted connections: the service journal does not
record payload, so it cannot support a zero-byte claim and does not contradict
the packet-visible greetings.

## Interpretation and close-out

EF25's synchronous connect reached the service TCP stack but raised before
`:Connected()` and before any marker or `HELLO`. It did not fix or advance the
harness handshake.

The evidence is asymmetric: EF23 and EF25 packet captures prove zero iPad TCP
payload, while EF24's pcap missed the Send and its lifecycle journal proves
seven accepts with no harness protocol observed by the service, not a
transmitted byte count. All three failed to advance the harness handshake under
the tested async, timeout-restoration, and synchronous-connect changes. The
EF2x client-parameter series is therefore closed and parked as an external
Einstein-platform issue. These observations do not prove
that the failure is specific to iOS.

If resumed, the first controlled experiment is the stock Einstein network path
with the **same seeded flash** used by the successful isolated EF25 gate,
retaining only the build/automation patches required to run and observe it.
Changing the flash at the same time would confound that comparison.
