# EF25 synchronous primary-connect diagnostic evidence

Date: 2026-08-11. Parent: branch-base commit
`25c2cc56e4caf5b5083d3546b6e228a61e987548`. This is a diagnostic build, not
a transport redesign and not physical proof.

## Hypothesis and exact change

EF24's first physical iPad run ended at visible `Connect error -16013` before
HS-A/B/C; its packet capture missed the Send and cannot identify a cause
(`../ef24-ipad-physical-20260811/README.md:9-38`). EF25 tests only whether the
iOS NIE async connect completion path is the blocker:

- `handshake-source.txt:2-21` preserves the EF25 address-options array and
  endpoint call, synchronous `{async: nil, reqTimeout: 10000}` request, and
  direct `:Connected()` continuation.
- The captured chat connect block has no `CompletionScript`
  (`handshake-source.txt:2-21`). Bind remains async in immutable commit
  `338e3662`, `examples/harness-client/Main.newt:1400-1409`.
- `handshake-source.txt:23-95` preserves HS-A/B/C, the 12 s post-connect
  watchdog, the marker's async 10 s output timeout, input arming, and framed
  HELLO.
- No server, Loader, protocol, polling, retry, ticket, tools, ink,
  package-download, ownership, or cleanup code changed.

Fresh identity/version had no match in any committed history or other branch:
`EggFrecklesEF25:jbfly`, title `Egg Freckles 1.0-ef25`, package version 39
(`identity-proof.txt`).

## Verification

| Check | Result |
|---|---|
| Focused client + server | 83 passed (`focused-tests.txt`) |
| Full suite | 140 passed (`full-tests.txt`) |
| Normalized builds | Two byte-identical 114,480-byte packages |
| Package SHA-256 | `edf439e9a7bf6ec8051fcc1fb03d24ae5bae8368acb3c54655b78092190b3a0e` |
| Package metadata | Newton NOS 1.x, NoCompression, version 39; identity/title each embedded once (`package-proof.txt`) |
| Emulator install | `GetPkgRefInfo(...).version` returned 39 (`emulator-state.txt`) |
| Isolated local gate | Exactly one accept; marker; `HELLO NEWTON1 1.0-ef25`; server `ACK 00`; server `STAT READY`; client `ACK 00`; clean EOF; no second accept (`emulator-gate.txt`) |
| Teardown | Listener exited; disposable container and state volume removed (`emulator-state.txt`) |

Einstein did not expose the transient painted HS-A/B/C labels long enough for a
screenshot. No visual claim is made. The nearest exact evidence is the single
source path in `handshake-source.txt`: `Connected()` paints HS-A before calling
`Hello`; `Hello` paints HS-B before marker output; only the marker completion
callback paints HS-C and emits framed HELLO. The gate received both marker and
HELLO, so that path traversed all three instrumentation points, but this does
not prove what an iOS screen will paint.

## Disclosed setup failures

The first disposable instance was poisoned by an invalid diagnostic `ns_eval`
expression. Its clean recreation then used a blank flash with no recognized
Ethernet card, so the listener saw no accept. Both attempts were removed. The
successful run followed `docs/parallel-emulators.md` and seeded a fresh private
volume from the archived NIE-configured flash before reinstalling EF25. Exact
sanitized errors are in `setup-failures.txt`; neither failure is product
evidence.

No Mars/iPad/physical Newton, shared emulator, shared service, remote, Loader,
or server source was touched. The remaining question is exclusively physical:
does synchronous primary connect advance iOS beyond EF24's pre-HS failure?
