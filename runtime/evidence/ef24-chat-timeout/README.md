# EF24 chat-connect timeout evidence

Date: 2026-08-11. This prepared the smallest M4 follow-up hypothesis directly
atop historical master milestone `4c834a9a04231403beb15d5e155ae4d629090bdc`. This file
records Linux Einstein evidence only; the later physical result is separately
curated in `../ef24-ipad-physical-20260811/README.md`.

## Exact change

M2 commit `3b2be4f5c44aafde7d981352a9d87105a6c4c721` changed the primary Egg
Freckles chat `endpoint:connect` request timeout from 45,000 ms to 10,000 ms
while integrating EF23. EF24 restores only that value to 45,000 ms. The
12,000 ms post-connect handshake watchdog and the marker output's 10,000 ms
request timeout are unchanged. No polling, tickets, delayed calls, Loader,
shared abstraction, server, protocol, ink, tools, or package-download behavior
changed.

Fresh package identity/version had zero matches across all refs and history
before editing: `EggFrecklesEF24:jbfly`, `1.0-ef24`, package version 38.

## Verification

| Check | Result |
|---|---|
| Focused source tests | 45 passed |
| Full suite | 140 passed |
| Normalized build 1 | 114,704 bytes; SHA-256 `5147937cd38086aa2b5ac258630f7f51f03e04d246d41fe3c440cd8a735981ba` |
| Normalized build 2 | Byte-identical; same size and SHA-256 |
| Package header | Newton NOS 1.x, NoCompression, version 38 |
| Embedded identity/title | `EggFrecklesEF24:jbfly`; `Egg Freckles 1.0-ef24` |
| Disposable emulator install | `GetPkgRefInfo` returned version 38 |
| Isolated local handshake | marker received; `HELLO NEWTON1 1.0-ef24` received; client ACKed `STAT READY` |
| Teardown | Disposable emulator and its state volume removed |

The first disposable attempt installed version 38, but its listener timed out because `OpenSession()` reloaded the active persisted favorite and overwrote the temporary view-slot port. That instance was removed. A fresh rerun set the favorite through the existing activation path and produced `install_version=38`, `marker=ok`, `hello_version=1.0-ef24`, `ready_ack=ok`, and `isolated_instance=removed`. This was a test-setup failure, not a product failure.

The emulator check used the established seeded isolated-instance path and a
throwaway local listener for the handshake only. It sent no prompt and used no
shared emulator, Mars host, iPad, physical Newton, shared service, or remote.
A later human-gated iOS run visibly ended at `Connect error -16013`, rather than
EF23's `-16005`, but reached no HS-A/B/C stage or reply. That result does not
identify a root cause; see `../ef24-ipad-physical-20260811/README.md:9-38`.
