# Emulator authoring-loop reliability — 2026-08-08

This page records the current failure reproduction and the fixes on
`task/dev-loop-reliability`. It covers isolated emulators only; no physical
Newton or shared emulator was used.

## Root cause 1: external worktrees lost the ROM setting

The requested authoring worktree had no `.env`, because `.env` is ignored and
Git does not copy ignored files into a linked worktree. The first blank
instance therefore used Compose's fallback `./secrets/717006`, which did not
exist in that worktree. Einstein's entrypoint exited 64 and the service restart
policy looped immediately: 549 restarts in three minutes, with every log line
saying `Missing Newton ROM: mount your 717006 dump at /rom/717006`
([failure log](../runtime/evidence/devloop-root1-fresh-boot.log)). The real ROM
was present and exactly 8,388,608 bytes in the same log, so this was mount
configuration, not a bad or missing ROM dump.

`scripts/emulator-instance.sh` now finds the main checkout through
`git rev-parse --git-common-dir` and passes its `.env` to Compose when the
current worktree has none. A second disposable blank instance mounted
`/home/jbfly/newton-dev/prefix/bin/717006`, reached healthy after 15 seconds,
and remained at zero restarts
([launch and mount evidence](../runtime/evidence/devloop-root2-up.txt),
[health JSON](../runtime/evidence/devloop-root2-health.json)). Its 320x480
[screenshot](../runtime/evidence/devloop-root2-fresh.png) shows the expected
first-run Welcome tour and card warning, proving this was fresh state rather
than the EF13 flash seed.

The fresh first-run UI is deterministic and does not need a seed: close the
card warning at `(247,271)`, tap Welcome's Continue at `(160,440)`, then tap
Enter at `(160,30)`. The resulting screen is stock Notes. The reliability
harness uses that sequence after each fresh boot.

## Root cause 2: tntk exits zero after an undefined helper

A real workspace build used generated source containing
`CellButton("Broken helper", ...)`, which is not a NewtonScript global. `tntk`
reported `kNErrUndefinedGlobalFunction` for `CellButton` but continued through
`Package buildcrash-0808.pkg created.` and `make` exited 0. The resulting file
was only 232 bytes
([complete MCP/toolchain transcript](../runtime/evidence/devloop-build-crash.json)).
This is the observed “core dump” class: the compiler emits an uncaught Newton
exception and a partial artifact while its process status still looks
successful.

The existing `build_pkg` defense from commit `8d933fd` holds: it forces a
rebuild, treats `Uncaught exception:` as failure even when make exits 0, and
publishes nothing to hardware staging. The reproduction found the 232-byte
workspace artifact but `staged_pkg=absent`
([publish check](../runtime/evidence/devloop-build-crash-publish-check.txt)).
The agent prompt now requires reading that exact error, replacing the complete
source, and rebuilding, with at most five attempts per stage.

## Root cause 3: the reliability harness violated the native handshake

The first three-app reliability attempt connected each test client but never
started Codex and never created an emulator container. Its three server logs
contain only `serving`, `connect`, and a disconnect 568 seconds later
([tic-tac-toe log](../runtime/evidence/devloop-reliability-round1/tic-tac-toe-run1.server.log));
the counter and hello logs are byte-for-byte equivalent apart from port and
address. A bounded fake-backend reproduction exposed the protocol error: the
harness sent its first `MSGP` before ACKing the server's `STAT READY`, so
`send_frame` answered `NAK BUSY` and consumed the prompt. The harness ignored
that NAK and waited forever for an ACK that could no longer arrive.

The harness now ACKs `STAT READY` before sending any prompt frame and applies
one absolute deadline to connection, every frame read, and the whole turn. The
same fake-backend probe completed all three prompt parts, `STAT THINKING`, the
reply, and `PROMPT` in 0.7 seconds (`runtime/evidence/devloop-fake-protocol/`;
ignored scratch evidence). Server and Codex run in one process group, so timeout
cleanup kills both rather than leaking the three `server.py` processes found
after the failed attempt.

## Fresh emulator recovery, timeouts, and progress

The new `emulator_boot` MCP tool recreates only a named isolated instance,
waits for health, and dismisses the deterministic Welcome UI. Its real-tool
proof returned healthy, zero-restart stock Notes from a blank volume
([tool result](../runtime/evidence/devloop-emulator-boot-final.json),
[screenshot](../runtime/evidence/devloop-emulator-boot-final.png),
[OCR](../runtime/evidence/devloop-emulator-boot-final-ocr.txt)). Calling it
again is the agent's bounded crash-recovery path; it never targets the shared
emulator.

`server.py` now relays every authoring MCP `item.started` event over the existing
native `TEXT` channel, including the stage and attempt number. Failed MCP items
relay the first error line as “failed; fixing”. It also writes a compact JSONL
MCP event log when `NEWTON_MCP_EVENT_LOG` is set; the reliability gate uses
completed events from that file rather than trusting the agent's prose. No
wire-format or client change was added.

All loop waits are bounded: the authoring turn defaults to 300 seconds, package
builds and emulator Compose commands to 60 seconds, fresh-emulator health to 90
seconds, and install/control/screenshot calls to at most 60 seconds. The harness
default is intentionally one tic-tac-toe run; multiple apps are opt-in only
after that gate passes. `scripts/emulator-instance.sh` also wraps Compose and
Podman themselves with `timeout -k 5`, so killing its caller cannot leave an
unbounded child behind.

## Root cause 4: Codex JSON events exceeded asyncio's line limit

The counter failure at 08:18:43 was not a build retry failure: immediately
after `create_project`, the whole backend turn ended with
`ValueError('Separator is not found, and chunk exceed the limit')`
([server log](../runtime/evidence/devloop-reliability/counter-run1.server.log)).
`CodexBackend.chat` created the subprocess without a stream limit and then read
one JSON event per line, so asyncio's 64 KiB default rejected any event carrying
a large generated source value (`server.py:575-586` before this fix). That
exception sits outside the MCP stage retry loop and therefore ended the turn.

The subprocess now uses a 16 MiB reader limit (`server.py:575-579`). The
regression test constructs the fake subprocess's real `asyncio.StreamReader`
from that argument, feeds it one valid JSON line larger than 64 KiB, and proves
the backend still returns the final message (`test_server.py:131-151`). The
full suite passed **128/128**
([pytest log](../runtime/evidence/devloop-streamlimit/pytest.log)).

## Root cause 5: recursive source crashes `tntk` and repeats unchanged

Deeply nested agent-generated NewtonScript can crash `tntk` inside its recursive
parser before it emits a diagnostic. A 500-array fixture reproduces SIGSEGV 139
with `NPSGenNode2 -> yyparse -> NPSParse`; increasing the process stack through
64 MiB and unlimited does not change the result. `build_pkg` already rejected
the nonzero make exit, but its generic error gave the authoring agent no direct
instruction to stop retrying the same source shape.

The build path now identifies the compiler crash text and explicitly requires a
non-identical rewrite with less nesting or a different source shape. The agent
prompt carries the same rule. The fixture, core trace, stack-limit results, and
sandboxed build-path proof are in [`docs/tntk-crash.md`](tntk-crash.md).

## Reliability results

Post-fix isolated-emulator validation passed **counter 5/5**. Every round
completed create, write, build, boot, install, launch, and screenshot, and each
OCR file contains the visible `Counter` title and `Increment` button
([summary and per-round evidence](../runtime/evidence/devloop-streamlimit/counter/)).

A deliberately large app also passed **1/1** with no human turn. Its Codex
stream carried single `write_source` event arguments of **88,766**, **88,727**,
and **88,870 bytes** without the former reader exception; after bounded
self-correction it built, installed, launched, and OCR found `Large Source`
([server log](../runtime/evidence/devloop-streamlimit/large-source/large-source-run1.server.log),
[result](../runtime/evidence/devloop-streamlimit/large-source/results.json),
[screenshot](../runtime/evidence/devloop-streamlimit/large-source/large-source-run1.png)).
The validation used named isolated instances only; its detached bounds and
artifact index are recorded in
[`runtime/evidence/devloop-streamlimit/README.md`](../runtime/evidence/devloop-streamlimit/README.md).
