# EF26 physical-MP2000 candidate evidence

**EF26 restores the final EF13 hardware-proven async primary connect and passes
the source, build, identity, and isolated-emulator gates. Physical MP2000
validation is still open.**

This curated record contains no raw provider logs, local paths, hostnames,
network addresses, ports, process/container/volume identifiers, PIDs, or
unnecessary timestamps. No shared or physical system changed.

## Exact behavior change — one transport reversal

- The branch base is EF25 milestone `338e3662`.
- The primary chat `Bound` method replaces EF25's synchronous
  `{async: nil, reqTimeout: 10000}` plus immediate `:Connected()` with
  `{async: true, reqTimeout: 45000, _parent: self}` and the existing-style
  completion callback. A nonzero result calls `HandshakeFailed`; success alone
  calls `Connected`.
- `async: nil` is absent from the client source. The source regression pins the
  primary block, callback, 45-second timeout, and removal of the direct
  synchronous continuation.
- No server picker, HS/progress, framing, package-tool, ink/Notes, scrolling,
  or UI code changed. The reviewed/current blob equality is independently
  recorded in `verification-summary.txt:11-14`.

The 45-second value is historical evidence, not a new choice: the final EF13
client landed in `c8b4148` with `async: true, reqTimeout: 45000`, and its
physical pass is recorded by `39aa963`. That spec remained until M2
`3b2be4f` shortened only the primary timeout; EF24 `629f20e` restored 45
seconds; EF25 `338e3662` introduced the synchronous diagnostic now removed.

## Verification — all required local gates pass

| Check | Result | Evidence |
|---|---:|---|
| Focused client + package-publisher tests | 61 passed | `verification-summary.txt:3-4` |
| Full suite | 140 passed | `verification-summary.txt:5-6` |
| Normalized builds | 2, byte-identical to tracked package | `verification-summary.txt:7` |
| Package size | 114,704 bytes | `verification-summary.txt:8` |
| Package SHA-256 | `bcc36db8db643a1e9e1825699a52ffad9bf705617a4af97bed59641f5736b14f` | `verification-summary.txt:9` |
| Project/package version | 40 | `verification-summary.txt:10`; `runtime-state.txt:3` |
| Front application | `EggFrecklesEF26:jbfly` | `runtime-state.txt:4` |
| Disposable chat accepts | exactly 1 | `protocol-transcript.txt:3,17` |
| Teardown | private resources absent | `runtime-state.txt:8` |

The package inspector reports `Newton package, NOS 1.x, NoCompression,
version 40` (`verification-summary.txt:10`). The tracked package and both fresh
normalized builds are byte-identical. Package/front-app runtime identity is
recorded at `runtime-state.txt:3-4`.

## Isolated emulator gate — handshake, progress, reply

A fresh disposable instance was seeded with the archived NIE-configured flash,
then installed and launched the tracked EF26 package. The unrelated tools poll
was disabled only in that disposable runtime view
(`runtime-state.txt:3-7`).

One chat connection completed this exact sequence:

1. one accept and client marker (`protocol-transcript.txt:3-4`);
2. framed `HELLO NEWTON1 1.0-ef26` (`protocol-transcript.txt:5`);
3. service `ACK 00` and `STAT READY`, client ACK
   (`protocol-transcript.txt:6-8`);
4. client `MSG EF26 GATE`, service ACK (`protocol-transcript.txt:9-10`);
5. service `STAT PROGRESS 1/1`, client ACK
   (`protocol-transcript.txt:11-12`), with runtime status `1/1`
   (`runtime-state.txt:5`);
6. service `TEXT EF26 GATE OK` and `PROMPT`, both ACKed
   (`protocol-transcript.txt:13-16`);
7. runtime status `Ready` and retained reply `EF26 GATE OK`
   (`runtime-state.txt:6`);
8. exactly one accept and private-resource teardown
   (`protocol-transcript.txt:17`; `runtime-state.txt:8`).

The causes of the three previously disclosed discarded setup/wrapper attempts
are preserved without raw logs in `setup-failures.txt:3-7`. None established a
product failure; the final fresh run used scalar assertions and passed every
gate above.

## Gap

No physical Newton was touched, so EF26 is a candidate, not a hardware pass.
The one-session physical order and operator rollback gate are in
`docs/ef26-physical-mp2000-runbook.md`.
