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
   `runtime/evidence/mars-agent-pkg-download-20260807.txt:4-6,37-47`.

## Implemented publication fix

`tool_build_pkg` forces a rebuild and treats `tntk`'s misleading zero-exit
`Uncaught exception:` output as failure. After a genuinely successful sandboxed
build, it copies the selected `.pkg`
under the same basename to `runtime/staging/hardware/` and returns
`Loader filename: <name>.pkg` (`newton_mcp.py`, `tool_build_pkg`). The copy uses
a temporary sibling followed by `Path.replace`, so `dual_send.py` cannot read a
partially copied package. A failed `make` or compiler exception returns before publication. The
focused test pins both the returned name and copied bytes
(`test_newton_mcp.py`, `test_build_pkg_allows_only_sandboxed_agent_workspace`).

This is host publication, not a physical-Newton write. The existing Loader still
requires the human to type the returned filename and tap **Install**.

The specific 240-byte `tic-tac-toe-r1.pkg` was a partial compiler artifact:
forced compilation reports undefined `CellButton`, and opening it in the
isolated emulator produced `-48809`
(`runtime/evidence/mars-agent-pkg-download-20260807.txt:8-20`). It was not left
published. For the filename the user had already entered, the bytes of the
successful, emulator-proven Mars chat tic-tac-toe build were atomically staged
as `tic-tac-toe-r1.pkg`. Live curl returned HTTP 200, 1,952 bytes, `package0`,
and SHA-256 `898a6a3b...`, byte-identical to the emulator-tested package
(`runtime/evidence/mars-agent-pkg-download-20260807.txt:22-47`). EF21 remained
`6652fb0b...`; no ZC40 or backup path was selected (`:49-54`).

## Direct physical install: wired, hardware validation still gated

Implemented 2026-08-08. `hardware_install` now accepts only one `.pkg` basename
already published by `build_pkg`, refuses unless the service inherited
`NEWTON_ALLOW_HARDWARE_INSTALL=1`, and shells out to
`runtime/install-newton-tcp` for that staged file (`newton_mcp.py:370-391`). The
tool overrides only its child process with `NEWTON_DOCK_TIMEOUT=180` and allows
a 195-second subprocess ceiling, so the listener survives while a human
navigates Dock (`newton_mcp.py:382-386`; pinned by
`test_newton_mcp.py:162-183`). The normal installer remains the mechanism: it
listens on `10.42.0.1:3679`, then sends `lpkg` as soon as the Newton connects
(`runtime/install-newton-tcp:57-91`).

The exact chat flow is:

1. The agent creates, writes, and builds the project; `build_pkg` atomically
   stages the successful package and returns its basename.
2. The agent validates the same package in an isolated emulator and inspects a
   screenshot.
3. The agent says the package is ready and calls `hardware_install`. The system
   prompt requires this order and the plain Dock wording
   (`agent_prompt.txt:25-39`); the public tool schema repeats that it must listen
   first (`newton_mcp.py:579-594`).
4. When Codex emits the `hardware_install` start event, the chat server relays
   `Package ready. Open Dock, choose connect via TCP/IP, then tap Connect.` over
   the existing Newton frame channel while the tool is still blocked listening
   (`server.py:516-520,557-568,774-781`). Tapping Connect is the physical-write
   confirmation; no package bytes move before it.
5. `runtime/install-newton-tcp` automatically sends the staged package on that
   connection. The agent's final message reports `Package installed; Dock
   session closed`, the exact Dock error, or the 180-second no-connection
   timeout.

No physical install was attempted in this change. Emulator-provable evidence is
`runtime/evidence/agent-hardware-install-20260808.txt`: the full suite passed
124 tests, the Dock packet self-test passed, and a real sandboxed agent build
produced byte-identical 1,112-byte workspace/staged packages with `package0`
magic. A real gate-off `codex exec --json` probe also emitted the exact
`item.started` MCP event pinned by `test_server.py:71-107`, then returned the
out-of-band-gate refusal without starting the installer. The two focused tests also prove the subprocess cannot run without the
out-of-band gate and receives the 180/195-second bounds when enabled
(`test_newton_mcp.py:145-183`). The former prepared patch was deleted because
keeping an applyable copy after wiring the feature would be stale and unsafe.

The observed `tntk` core dump was secondary and recoverable: the preserved
rollouts show syntax errors followed by `Segmentation fault (core dumped)`, then
a corrected source built and emulator-installed successfully
(`runtime/evidence/pkgchat0807b-codex-rollout.jsonl`, events 60, 69, 74;
`runtime/evidence/marssmoke-20260807T164030Z-codex-rollout.jsonl`, events 34,
43, 48). No new `-60037` was observed in this download failure; it remains a
known Dock/NIE link-selection error, not the cause of the HTTP 404.

## Mars deployment prepared, not applied

Mars was verified read-only on 2026-08-08 at `179f91a` on
`fix/agent-pkg-download`. Its MCP registration already names
`/home/jbfly/git/newton-harness/newton_mcp.py` with approval mode `approve`, and
`egg-freckles-chat.service` already has `NEWTON_CODEX_TIMEOUT=300`. The checkout
has preserved EF package backups and a modified live EF21 package, so the sync
must fast-forward without requiring or cleaning an otherwise-pristine tree.
The orchestrator can apply exactly:

```sh
# alpha: package the committed branch without pushing a shared branch
cd /home/jbfly/git/newton-harness-pkg-download
test "$(git branch --show-current)" = fix/agent-pkg-download
test -z "$(git status --porcelain)"
git bundle create /tmp/agent-dock-install.bundle fix/agent-pkg-download
sha256sum /tmp/agent-dock-install.bundle
scp /tmp/agent-dock-install.bundle mars:/tmp/

# mars: preserve its unrelated EF21/backups, fast-forward only, enable the gate
ssh mars <<'MARS'
set -eu
export PATH=/home/jbfly/.local/bin:/home/jbfly/newton-dev/prefix/bin:/usr/local/bin:/usr/bin
cd ~/git/newton-harness
test "$(git branch --show-current)" = fix/agent-pkg-download
test "$(git rev-parse HEAD)" = 179f91ac1da9a1a5dafbb48a01ffd7fb801885a6
git diff --quiet -- agent_prompt.txt newton_mcp.py server.py test_newton_mcp.py test_server.py docs
git bundle verify /tmp/agent-dock-install.bundle
! ss -ltn | grep -q ':3679 '
git show-ref --verify --quiet refs/heads/backup/mars-before-agent-dock-install || \
  git branch backup/mars-before-agent-dock-install HEAD
git fetch /tmp/agent-dock-install.bundle fix/agent-pkg-download
git merge --ff-only FETCH_HEAD
uv run --with pytest pytest -q
python3 - <<'PY'
import newton_mcp
assert "hardware_install" in newton_mcp.HANDLERS
assert newton_mcp.DOCK_WAIT_SECONDS == 180
assert "open Dock, choose connect via TCP/IP" in open("agent_prompt.txt").read()
PY
mkdir -p ~/.config/systemd/user/egg-freckles-chat.service.d
cat > ~/.config/systemd/user/egg-freckles-chat.service.d/hardware-install.conf <<'UNIT'
[Service]
Environment=NEWTON_ALLOW_HARDWARE_INSTALL=1
UNIT
systemctl --user daemon-reload
systemctl --user restart egg-freckles-chat.service
systemctl --user is-active --quiet egg-freckles-chat.service
systemctl --user show egg-freckles-chat.service -p Environment | grep 'NEWTON_ALLOW_HARDWARE_INSTALL=1'
ss -ltnp | grep ':6801 '
codex mcp get newton | grep '/home/jbfly/git/newton-harness/newton_mcp.py'
MARS
```

After the restart, enter `/new dock-install` once in Egg Freckles before the
first package-authoring request; resumed Codex threads retain their old system
prompt. Do not pre-start an installer or touch port 18081: `hardware_install`
opens `10.42.0.1:3679` only during the gated turn.
