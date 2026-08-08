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

## Fresh emulator recovery and progress

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
relay the first error line as “failed; fixing”. No wire-format or client change
was added.

## Reliability results

Pending in this cycle.
