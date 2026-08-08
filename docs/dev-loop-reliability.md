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

## Build crash investigation

Pending in this cycle.

## Reliability results

Pending in this cycle.
