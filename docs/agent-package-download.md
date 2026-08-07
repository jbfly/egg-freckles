# Agent package download and direct-install boundary

Verified 2026-08-07 against commit `1ae0bd035e01e00c1957b7d5530f4137d6fa53ba`
and Mars. This page records why an agent-built package returned HTTP 404, the
small publication fix, and the separate physical-install path that remains
human-gated.

## Why `tic-tac-toe-r1.pkg` returned 404

1. The Newton Loader accepts only a basename ending in `.pkg`, with characters
   from `-._0-9A-Za-z` (`examples/harness-loader/Main.newt:94-105`). It sends
   exactly `GET /<that basename> HTTP/1.0` to `10.42.0.1:18081`
   (`examples/harness-loader/Main.newt:318-326`) and requires HTTP 200 plus a
   positive `Content-Length` (`:250-272`) before it queues
   `SuckPackageFromBinary` (`:309-315`, `:190-218`).
2. `runtime/dual_send.py` maps that request basename only beneath
   `runtime/staging/hardware/` (`runtime/dual_send.py:19`, `:38-45`). A missing
   regular file receives HTTP 404 (`:41-44`); a hit is returned byte-for-byte
   with its length (`:45-52`). The word "dual" means raw NS Basic bootstrap and
   Loader HTTP share one port (`:84-99`), not emulator plus hardware install.
3. Before this fix, `build_pkg` left its output beneath
   `runtime/agent-workspace/<project>/` and returned only that host path and its
   `/agent-workspace/...` emulator path (`newton_mcp.py` at parent commit
   `1ae0bd0`, lines 364-387). Mars held
   `runtime/agent-workspace/tic-tac-toe-r1/tic-tac-toe-r1.pkg`, but no
   `runtime/staging/hardware/tic-tac-toe-r1.pkg`. The live service recorded:

   ```text
   2026-08-07T10:59:37 request 'GET /tic-tac-toe-r1.pkg HTTP/1.0'
   2026-08-07T10:59:37 HTTP 404 'tic-tac-toe-r1.pkg'
   ```

   Evidence and the post-fix curl are preserved in
   `runtime/evidence/mars-agent-pkg-download-20260807.txt`.

## Implemented publication fix

After a successful sandboxed build, `tool_build_pkg` copies the selected `.pkg`
under the same basename to `runtime/staging/hardware/` and returns
`Loader filename: <name>.pkg` (`newton_mcp.py`, `tool_build_pkg`). The copy uses
a temporary sibling followed by `Path.replace`, so `dual_send.py` cannot read a
partially copied package. A failed `make` returns before publication. The
focused test pins both the returned name and copied bytes
(`test_newton_mcp.py`, `test_build_pkg_allows_only_sandboxed_agent_workspace`).

This is host publication, not a physical-Newton write. The existing Loader still
requires the human to type the returned filename and tap **Install**. No EF21,
ZC40, bootstrap, or backup filename is selected or modified by this change.

## Direct physical install: feasible, but prepared only

**Yes, a host-side push implementation already exists.**
`runtime/install-newton-tcp:57-91` validates `package0`, listens on
`10.42.0.1:3679`, performs the ROM Dock session, sends the package in the
`lpkg` command, and waits for the Newton's `dres` result. The physical Newton
must already have Dock TCP, open Dock, choose TCP/IP, and tap Connect
(`docs/hardware-bench-runbook.md:295-316`). Error `-60037` means the selected
NIE link is inactive (`:324-332`). Serial fallback also exists at
`runtime/install-newton-serial:1-23`, but requires the cable and device access.
Neither sender is exposed by `newton_mcp.py`; `dual_send.py` itself never pushes.

The smallest safe MCP wiring is preserved, but **not applied**, in
`docs/prepared-hardware-install.patch`. It adds one `hardware_install` tool that:

- accepts only a basename already in `runtime/staging/hardware/`;
- refuses unless a human starts the MCP service with
  `NEWTON_ALLOW_HARDWARE_INSTALL=1`;
- runs `runtime/install-newton-tcp` and returns its bounded output;
- has a test proving the default refusal never starts a subprocess.

The environment gate must be set out-of-band by the human; an agent-supplied
`confirm: true` would not be a human gate. `git apply --check
 docs/prepared-hardware-install.patch` validates that the prepared diff applies,
but it must remain unapplied until the human approves a physical install.

### Human-gated test plan

1. Build the package and confirm `build_pkg` returns its Loader filename.
2. Install that same `/agent-workspace/...` path into an isolated emulator,
   launch its fresh symbol, inspect `emulator_screen`, and exercise one control.
3. Confirm the staged file has `package0` magic and the same SHA-256 as the
   emulator-tested workspace file.
4. Human only: confirm Newton store free space, open Dock TCP with the working
   Link selected, and tap Connect only after explicitly approving the install.
5. Human only: enable `NEWTON_ALLOW_HARDWARE_INSTALL=1` for one chat/MCP run and
   call `hardware_install` with the staged basename. Require the exact host text
   `Package installed; Dock session closed`; record any Newton Dock error
   verbatim. Remove the environment override immediately afterward.

The observed `tntk` core dump was secondary and recoverable: the preserved
rollouts show syntax errors followed by `Segmentation fault (core dumped)`, then
a corrected source built and emulator-installed successfully
(`runtime/evidence/pkgchat0807b-codex-rollout.jsonl`, events 60, 69, 74;
`runtime/evidence/marssmoke-20260807T164030Z-codex-rollout.jsonl`, events 34,
43, 48). No new `-60037` was observed in this download failure; it remains a
known Dock/NIE link-selection error, not the cause of the HTTP 404.
