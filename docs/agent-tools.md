# Agent tools — the MCP server (`newton_mcp.py`)

ROADMAP Track D1, with D2's rails folded in. This is the file that closes the
gap named in `docs/ROADMAP.md`: "the agent has no tools". `server.py` still
only relays chat; the *agent* behind that chat (`codex exec`,
`server.py:227-260`) now gets the host's Newton surfaces as MCP tools.

**Status 2026-08-03: LIVE-PROVEN (Track D3).** A prompt typed into Chat on an
emulated Newton made the agent call `newton_tool` three times and answer with
the device's real numbers, on screen, in 19 seconds. The transcript, the three
tool calls and the screenshot are at the bottom of this page under "The live
demo (D3)". Since Track G2 the same is true of the build-and-test surface:
`build_pkg`, `emulator_install`, `emulator_newtonscript`, `emulator_screen` and
`emulator_tap` were driven by an agent to build a new app and prove it works on
screen (`docs/agent-dev-loop.md`, "Proven 2026-08-03"). That historical build
used `examples/`; the confined writable-workspace path is now emulator-proven
too (`docs/agent-dev-loop.md`, "Workspace plumbing proven 2026-08-07"). `emulator_boot` was added and blank-volume proven on 2026-08-08; it removes
   the old EF13-seed dependency for authoring and provides crash recovery. Only
`emulator_text` and `emulator_key` are still exercised by tests alone. Track C5's
`pkg_install`, `pkg_remove`, and `emulator_remove` are isolated-emulator proven; the
physical no-Dock turn remains pending
(`runtime/evidence/pkg-install-delete/README.md`).
The old agent-facing `stage_hw` tool was removed when writes were confined to
the dedicated workspace; physical staging remains a human host procedure.

`newton_mcp.py` is one stdlib-only file at the repo root. It speaks MCP over
stdio as newline-delimited JSON-RPC 2.0 and implements exactly `initialize`,
`ping`, `tools/list`, `tools/call`; notifications are read and dropped
(`newton_mcp.py:handle`). There is no SDK dependency, which matters because the
server image is `node:22-bookworm-slim` + `python3` and nothing else
(`containers/server.Dockerfile:5-8`).

## What it exposes

| Tool | Arguments | Goes to | Notes |
|---|---|---|---|
| `pkg_install` | `basename` | `POST {NEWTON_TOOLS_URL}/tools` → staged package GET on port 18081 | Accepts only a regular staged ASCII `.pkg` basename. Egg Freckles downloads it into a VBO and calls `SuckPackageFromBinary`; call immediately after `build_pkg` in the same user-requested active send. |
| `pkg_remove` | `identity` | `POST {NEWTON_TOOLS_URL}/tools` | Removes the exact identity returned by `pkg_list`; host and Newton both refuse Egg Freckles, loader/recovery, NIE, and network-driver identities. |
| `emulator_remove` | `identity`, `instance` | isolated emulator `/newtonscript` | Emits the proven close + two-argument `GetPkgRef(identity, store)` + `SafeRemovePackage` sequence and refuses the shared emulator/protected identities. |
| `newton_tool` | `op` (required), `args` (object), `timeout` (s, ≤120, default 20) | `POST {NEWTON_TOOLS_URL}/tools`, default `http://10.42.0.1:18081` | Generic pass-through to the `ToolBroker`. Reply JSON is returned verbatim; mutating op names remain gated here so callers use the validated dedicated tools. Read-only ops: `ping`, `front_app`, `get_note`, `note_probe`, `battery`, `store_info`, `pkg_list`. |
| `emulator_boot` | `instance` | `scripts/emulator-instance.sh` + control API | Recreates a fresh isolated instance, waits at most 90 seconds for health, and dismisses Welcome; call again after a crash. Compose/Podman children are capped at 60 seconds. |
| `emulator_screen` | `instance` | `GET /screen.png` | Returns MCP `image` content (base64 PNG) plus one line of text. **Always allowed**, shared emulator included. |
| `emulator_tap` | `x`, `y`, `instance` | `POST /tap` | 320×480 Newton coordinates. |
| `emulator_text` | `value`, `instance` | `POST /text` | xdotool typing. |
| `emulator_key` | `key`, `instance` | `POST /key` | One xdotool key name. |
| `emulator_newtonscript` | `source`, `instance` | `POST /newtonscript` | One line, raw text body. |
| `create_project` | `project`, `identity`, `title`, `version` | `runtime/agent-workspace/<project>` | Copies the trusted `examples/hello` scaffold, renames its project/build targets, and sets a fresh package identity. Refuses nested paths and existing projects. |
| `write_source` | `project`, `source` | `runtime/agent-workspace/<project>/Main.newt` | Replaces only `Main.newt` in a direct workspace project; refuses path and symlink escapes and source over 256 KiB. |
| `emulator_install` | `pkg_path`, `instance` | `POST /install` | Accepts container paths under read-only `/packages/` or read-only `/agent-workspace/`; the endpoint takes a path inside the container, **not** an upload (`docs/install-paths.md` row 1). |
| `build_pkg` | `dir` | sandboxed `make -C <dir>` | Accepts only a direct project under `runtime/agent-workspace/`; the build is capped at 60 seconds. A successful build is copied under the same basename to `runtime/staging/hardware/`; the result returns both the Loader filename and emulator-visible path. |

Instance resolution reuses `emulator.client.instance_url`
(`emulator/client.py:17-30`) — `podman port newton-harness-<instance>_emulator_1
8080` — rather than reimplementing port lookup. Omitting `instance` means the
shared emulator at `NEWTON_CONTROL_URL` (default `http://127.0.0.1:18080`).

## The safety rails (in code, not in a prompt)

Track D2's point is that a prompt is not a rail. All four of these are
enforced in `newton_mcp.py` and covered by tests:

1. **The shared emulator is read-only.** `emulator_tap`, `_text`, `_key`,
   `_newtonscript` and `_install` refuse when no `instance` was passed, unless
   the server's environment carries `NEWTON_ALLOW_SHARED=1`
   (`newton_mcp.py:guard_shared`). The refusal text tells the agent to run
   `make emulator-instance-up INSTANCE=<name>` and pass `instance`.
   `emulator_screen` is exempt — looking is free.
2. **Package mutation has a narrow, user-confirmed path.** Generic `newton_tool`
   still refuses every name in `HUMAN_GATED_OPS`. Dedicated `pkg_install` and
   `pkg_remove` are available only for the user's explicit install/remove request:
   install accepts one regular file already published by `build_pkg`; removal
   accepts one exact printable identity and blocks the running Egg Freckles package,
   loader/recovery packages, and NIE/network drivers in both Python and NewtonScript
   (`newton_mcp.py:258-295`, `examples/harness-client/Main.newt:2837-2890`). On
   hardware the active chat send is the confirmation and timing gate: EF14 closes
   `/tools` about five seconds after idle, so the call must follow the build in the
   same turn. No background keepalive was added.
3. **Agent writes are confined to one ignored runtime directory.** Codex keeps
   its global `--sandbox read-only` setting (`server.py:524`).
   `create_project` can create only one direct child of
   `runtime/agent-workspace/` (`newton_mcp.py:146-190`);
   `write_source` can replace only that child's
   `Main.newt` (`newton_mcp.py:296-350`); both resolve paths and
   reject symlink escapes. `build_pkg` accepts only a direct workspace project;
   its Makefile runs under bubblewrap with `/` read-only and only
   `runtime/agent-workspace/`
   rebound writable, and networking unshared (`newton_mcp.py:364-391`).
   The repository and `examples/` therefore remain read-only to the chat agent.
   The emulator sees the same host directory at `/agent-workspace:ro`
   (`compose.yaml:41`), so it can read a built package but
   cannot alter source or build output. No host directory outside this dedicated
   workspace is granted write access.
4. **Physical install has two human gates.** `build_pkg` stages only its own
   successful output under `runtime/staging/hardware/`. `hardware_install`
   accepts only that staged basename, refuses unless the service inherited
   `NEWTON_ALLOW_HARDWARE_INSTALL=1`, and invokes `runtime/install-newton-tcp`
   with a 180-second Dock wait (`newton_mcp.py:370-391`). The package is not sent
   until the human opens Dock, chooses connect via TCP/IP, and taps Connect.

## How it is registered with codex

`codex exec` reads `$CODEX_HOME/config.toml`, and in the server container
`CODEX_HOME` is `/home/node/.codex` — which `compose.yaml:21` mounts as the
named volume `codex-home`. That volume is also where `make server-login` puts
`auth.json`, so registration follows the same one-shot-per-volume pattern:

```sh
make server-mcp
```

`containers/server.Dockerfile` copies `newton_mcp.py` and
`emulator/{__init__,client}.py` into `/app`. Nothing in `server.py` changes —
the chat wire protocol is untouched, and if the backend is ever swapped for
Claude the same MCP server plugs in.

**On the host** — the recommended shape for tool work, see the networking
section below — the registration used for the live demo was exactly:

```sh
codex mcp add newton -- python3 /home/jbfly/git/newton-harness/newton_mcp.py
```

which appended this to `~/.codex/config.toml` (a symlink to
`~/git/ai-ops/moon/config.toml` on this machine), plus one line that has to be
added by hand:

```toml
[mcp_servers.newton]
command = "python3"
args = ["/home/jbfly/git/newton-harness/newton_mcp.py"]
default_tools_approval_mode = "approve"   # added by hand -- see below
```

Confirm with `codex mcp get newton`, which prints the approval mode as its own
line. This registration is meant to stay: leave it in place. Two side effects
worth knowing — `codex mcp add` rewrites the *whole* config file, so it
reflowed an unrelated `disabled_tools` array onto one line, and it does not
touch anything else.

### The two `[verify]` items, settled 2026-08-03

Full transcripts: `runtime/evidence/d3demo-mcp-verify.txt`.

1. **Does `codex exec` auto-approve MCP tool calls non-interactively? No.**
   With the plain two-line registration the call is *attempted and then
   fails*: the JSONL carries
   `"error": {"message": "user cancelled MCP tool call"}, "status": "failed"`.
   Nobody is there to answer the approval request, so it is auto-declined —
   which reads like a broken tool, not like a missing permission.
   The fix is `default_tools_approval_mode = "approve"` on the server entry.
   `codex mcp add` has **no flag** for it (`codex mcp add --help`), so it must
   be written into the TOML; `make server-mcp` now does that step for the
   container. The valid values, from codex's own rejection message, are
   `auto`, `prompt`, `writes`, `approve` — and the default (`auto`) is what
   fails above. With `approve` the identical prompt returned
   `{"request_id":"5","status":"result","result":"Notepad (paperroll)"}`.
2. **Is the MCP server subprocess inside `--sandbox read-only`? No.**
   `--sandbox` governs the commands the *model* runs, not the MCP server
   process. Proof: `examples/hello/hello.pkg` was deleted, then a
   `codex exec --sandbox read-only` run called `build_pkg(dir="examples/hello")`
   and the tool wrote the file (1104 bytes). That historical behavior is why
   `build_pkg` is now workspace-only and bubblewrapped. The flip side is a
   security note:
   **the sandbox flag is not a rail for this tool surface.** The only rails on
   these tools are the ones coded into `newton_mcp.py` (Track D2), and
   `approve` means the agent uses them without asking.

## Container networking — measured, 2026-08-03

Tested with a throwaway host listener on port 18099 (bound to both `10.42.0.1`
and `127.0.0.1`) and a one-shot container on the server's compose network:
`podman run --rm --network newton-harness_default
localhost/newton-harness-server:local python3 -c ...`. Podman 6.0.1, rootless,
netavark.

| From the server container to | Result |
|---|---|
| `http://10.42.0.1:18099/` (host `lo` alias) | **OK 200** |
| `http://127.0.0.1:18099/` (host loopback) | `URLError [Errno 111] Connection refused` |
| `http://host.containers.internal:18099/` | resolves to `169.254.1.2`, then `Connection refused` |

What that means:

- **`newton_tool` works from inside the container as shipped.** The broker
  address `10.42.0.1:18081` is a global-scope alias on the host's `lo`
  (`ip -4 addr show lo` → `inet 10.42.0.1/24 scope global lo`), and container
  traffic to it leaves via the default route and lands on the host. This is
  the tool the D3 demo needs.
- **The `emulator_*` tools do not work from inside the container.** Two
  independent reasons: every emulator instance publishes its control port on
  `127.0.0.1` only (`compose.yaml:35`, `scripts/emulator-instance.sh:33-38`),
  which the table above shows is unreachable; and `instance_url` shells out to
  `podman`, which is not installed in the server image and has no socket there.
- **`build_pkg` does not work from inside the container either** — the image
  has no `make`, no `tntk`, and no repo checkout.

**Recommended fix — and what the D3 demo did: run `server.py` on the host for
agent-tool work**, where
`codex`, `podman`, `make` and `127.0.0.1` all already exist (`python3
server.py` needs only stdlib; `codex` is at `~/.local/bin/codex`). Keep the
container for the chat-only deployment. The alternatives, for the record and
not recommended here: `network_mode: host` for the server service (loses the
port isolation the compose file deliberately keeps), or republishing every
emulator control port on `10.42.0.1` (that address is also the AP address the
Newton itself sees, so it would expose the control API to the device network),
or mounting the podman socket plus a repo bind mount into the server
container. Do not restructure the containers without a session that owns them.

## Tests

`test_newton_mcp.py`, 8 tests, no network and no containers: the JSON-RPC round
trips run against a real subprocess over a pipe (`initialize` →
`tools/list` → `tools/call`, notification silence, unknown method → -32601),
the shared-emulator refusal is asserted for all five mutating tools and shown
to lift under `NEWTON_ALLOW_SHARED=1`, and `newton_mcp.http_request` is
monkeypatched for the `newton_tool` URL/body assertion and the
`emulator_screen` image encoding. Suite total: 45 passed.

## Writable-workspace package plumbing — emulator-proven 2026-08-07

The package-authoring tools were called directly over MCP JSON-RPC against an
isolated `pkgproof0807b` emulator restored from the known-good EF13 proof flash
(SHA-256 `8f37d609d46711ea2ce1d748ed52fbd4b3f4f88fd86e6c90b654fb21fdb1508a`).
The instance used the emulator image rebuilt from this checkout and mounted
this checkout's `runtime/agent-workspace` read-only at `/agent-workspace`.

`create_project` made `hello-agent-0807b` with never-used identity
`HelloAgent0807B:jbfly`; `write_source` wrote a complete 579-byte `Main.newt`;
and `build_pkg` returned
`/agent-workspace/hello-agent-0807b/hello-agent-0807b.pkg`. The host package was
1,120 bytes (SHA-256
`4887dd0e565746cc185e89d442ca5bb6c09c9a88c70fc8a36d2cca27fb2a3c03`), existed
only below `runtime/agent-workspace`, and before/after hashes showed no change
to `examples/` or any repository file outside the workspace and evidence
directory. `emulator_install` returned `queued`, launching
`GetRoot().|HelloAgent0807B:jbfly|:Open();` returned `queued`, and
`emulator_screen` showed the **HelloAgent** window with “HelloAgent is alive!”
visible.

Evidence: [`pkgproof0807b-mcp-transcript.jsonl`](../runtime/evidence/pkgproof0807b-mcp-transcript.jsonl)
contains every MCP request and response;
[`pkgproof0807b-identity-build.txt`](../runtime/evidence/pkgproof0807b-identity-build.txt)
records identity, package path, size, checksum, and containment checks; and
[`pkgproof0807b-07-launched.png`](../runtime/evidence/pkgproof0807b-07-launched.png)
is the screenshot returned by `emulator_screen`. This proves the plumbing; the
real chat-agent selection proof is the `pkgchat0807b` round below.

## Real Egg Freckles turn attempt — stopped before the agent, 2026-08-07

A host-path validation attempt used `release/pkg-write-fix @ 4fc2fb34`, isolated
instance `pkgchat0807a`, the known-good EF13 seed flash (SHA-256
`8f37d609d46711ea2ce1d748ed52fbd4b3f4f88fd86e6c90b654fb21fdb1508a`),
and a real host `server.py` with a temporary Codex home whose `newton` MCP entry
pointed at this worktree's `newton_mcp.py`. The branch-paired Egg Freckles EF20
package launched and displayed its normal prompt window
([`pkgchat0807a-04-egg-recovery.png`](../runtime/evidence/pkgchat0807a-04-egg-recovery.png)).

The turn itself did **not** start. `emulator_text` returned `{"ok":true}`, but
the NewtonScript prompt field remained empty; tapping **Send** displayed
"Type a prompt first", and the complete server log contains only its startup
line — no Newton connection
([`pkgchat0807a-06-sent.png`](../runtime/evidence/pkgchat0807a-06-sent.png),
[`pkgchat0807a-server.log`](../runtime/evidence/pkgchat0807a-server.log)). The
status log records every bounded step, the one recovery (installing the client;
the EF13 flash is a seed, not a client-package snapshot), and teardown
([`pkgchat0807a-status.log`](../runtime/evidence/pkgchat0807a-status.log)). No
workspace project was created, so none of `create_project`, `write_source`,
`build_pkg`, or `emulator_install` was selected by the chat agent. This remains
the evidence for why Newton glass text injection is not a reliable automation
path; the next round bypassed only that input obstacle.

## Real host chat-agent package turn — proven 2026-08-07

`pkgchat0807b` sent the short tic-tac-toe request through the exact native
`~NEWTONCLI 1` / `MSG` channel on host `server.py:6801`, not through direct MCP
calls ([wire transcript, lines 1–8](../runtime/evidence/pkgchat0807b-wire-transcript.txt#L1-L8)).
The server launched the normal `codex exec` backend with this worktree's
`newton_mcp.py`; the full preserved rollout is
[`pkgchat0807b-codex-rollout.jsonl`](../runtime/evidence/pkgchat0807b-codex-rollout.jsonl).

The agent itself chose the complete confined path. The concise transcript shows
`create_project` and `write_source`, including its generated NewtonScript
([lines 1–2](../runtime/evidence/pkgchat0807b-agent-tool-transcript.txt#L1-L2));
it hit a real NewtonScript syntax error, corrected `|` to `+`, and rebuilt a
valid package ([lines 3–29](../runtime/evidence/pkgchat0807b-agent-tool-transcript.txt#L3-L29));
then it selected `emulator_install`, launch, and repeated `emulator_screen`
verification against isolated instance `pkgchat0807b`
([lines 30–39](../runtime/evidence/pkgchat0807b-agent-tool-transcript.txt#L30-L39)).
The source's title and 3x3 board are preserved at
[`pkgchat0807b-agent-Main.newt:1-34`](../runtime/evidence/pkgchat0807b-agent-Main.newt#L1-L34),
and the exact image returned by the agent's final `emulator_screen` call is
[`pkgchat0807b-agent-screen.png`](../runtime/evidence/pkgchat0807b-agent-screen.png).

The never-used identity was `TTTGridP0807bR1:nwtn`; prior git history had zero
matches. The built package is 1,784 bytes, SHA-256
`40fdc2e6157cc2afd2f2e075166cad475f4b479be9e55c98f9dc1c257c79f898`, and
its live build stayed under `runtime/agent-workspace`
([identity/build evidence, lines 1–9](../runtime/evidence/pkgchat0807b-identity-build.txt#L1-L9)).
The committed evidence copy is
[`pkgchat0807b-tic-tac-toe.pkg`](../runtime/evidence/pkgchat0807b-tic-tac-toe.pkg).
The branch-paired Egg Freckles package and `pkg_publisher.py` hashes are recorded
in [`pkgchat0807b-egg-pair-sha256.txt`](../runtime/evidence/pkgchat0807b-egg-pair-sha256.txt).

One bounded recovery was needed after the work, not during package authoring:
the agent had completed the required tool chain but continued visually checking
until `server.py`'s 170-second deadline killed its final text
([wire transcript, lines 8–14](../runtime/evidence/pkgchat0807b-wire-transcript.txt#L8-L14)).
The preserved Codex thread was resumed once through the same port-6801 channel
and returned the normal completion `TEXT` and `PROMPT` frames
([recovery transcript, lines 6–14](../runtime/evidence/pkgchat0807b-recovery-wire-transcript.txt#L6-L14)).
Focused tests passed 65/65 and the full suite passed 120/120
([focused lines 1–3](../runtime/evidence/pkgchat0807b-focused-tests.txt#L1-L3),
[full lines 1–3](../runtime/evidence/pkgchat0807b-full-tests.txt#L1-L3)). The
shared emulator was healthy before and after; the status log records every
bounded step and the single recovery
([`pkgchat0807b-status.log`](../runtime/evidence/pkgchat0807b-status.log)).

## Mars deployment prepared — not applied, 2026-08-07

Mars was reported at `590b6ab`; live SSH verification failed with
`ssh: connect to host 10.13.13.12 port 22: Connection timed out`. Do not call
Mars deployed until the following preflight runs there. `tntk` does **not**
need to be on `PATH`: `build_pkg` resolves `bwrap` with `shutil.which`, invokes
`make`, and the copied project Makefile calls
`$HOME/newton-dev/prefix/bin/tntk` while setting `LD_LIBRARY_PATH` itself
(`newton_mcp.py:364-377`; `examples/hello/Makefile:1-11`). Podman is
separate and still required for `emulator_*` instance resolution.

Prepare the release bundle on the validated host, then let the human copy and
apply it:

```sh
# alpha / validated host
cd ~/git/newton-harness-worktrees/rel-pkgwrite
test "$(git rev-parse HEAD)" = 4fc2fb34cce2b1f5b092318c2d1207a6cca9ac0d
git bundle create /tmp/pkg-write-fix-4fc2fb34.bundle release/pkg-write-fix
sha256sum /tmp/pkg-write-fix-4fc2fb34.bundle
scp /tmp/pkg-write-fix-4fc2fb34.bundle mars:/tmp/

# mars — human-gated; abort on any failed assertion
cd ~/git/newton-harness
test -z "$(git status --porcelain)"
test "$(git rev-parse HEAD)" = 590b6ab
{
  git rev-parse HEAD
  sha256sum examples/harness-client/egg-freckles.pkg pkg_publisher.py
  pgrep -af '^python3( -u)? runtime/raw_pkg_server.py$'
  ss -ltnp | grep ':18081 '
} | tee /tmp/mars-pkg-write-predeploy.txt
test "$(pgrep -fc '^python3( -u)? runtime/raw_pkg_server.py$')" = 1
git bundle verify /tmp/pkg-write-fix-4fc2fb34.bundle
git branch backup/mars-before-pkg-write-590b6ab 590b6ab
git fetch /tmp/pkg-write-fix-4fc2fb34.bundle \
  release/pkg-write-fix:refs/heads/release/pkg-write-fix
git switch --detach 4fc2fb34cce2b1f5b092318c2d1207a6cca9ac0d
mkdir -p runtime/agent-workspace

command -v bwrap
command -v make
test -x "$HOME/newton-dev/prefix/bin/tntk"
test -f "$HOME/newton-dev/ntk-platform-files/Newton 2.1"
command -v podman                    # required for install/launch/screenshot
podman info --format '{{.Host.Security.Rootless}}' | grep -x true
codex mcp get newton                 # must name ~/git/newton-harness/newton_mcp.py
                                    # and approval mode "approve"
uv run --with pytest pytest -q
```

The checkout update changes **both** `examples/harness-client/egg-freckles.pkg`
and `pkg_publisher.py` relative to `590b6ab`; keep them paired. At `4fc2fb34`
their SHA-256 values are `91381832725a2563…` and `538d6fa41b65373c…`.
`runtime/raw_pkg_server.py` imports the publisher at process start, so restart
that one listener after the tests and verify the served package before any
human uses Egg Freckles:

```sh
cd ~/git/newton-harness
old_pid=$(pgrep -f '^python3( -u)? runtime/raw_pkg_server.py$')
test -n "$old_pid" && test "$(printf '%s\n' "$old_pid" | wc -l)" = 1
kill "$old_pid"
for _ in $(seq 1 20); do
  kill -0 "$old_pid" 2>/dev/null || break
  sleep 1
done
! kill -0 "$old_pid" 2>/dev/null
mkdir -p runtime/logs
nohup python3 -u runtime/raw_pkg_server.py \
  >runtime/logs/raw-pkg-server.log 2>&1 &
echo $! >/tmp/mars-raw-pkg-server.pid
for _ in $(seq 1 20); do
  curl -fsS http://10.42.0.1:18081/status && break
  sleep 1
done
curl -fsS http://10.42.0.1:18081/egg-freckles.pkg | sha256sum | \
  grep '^91381832725a2563dcf6c635c3f7f98306a5d1214d1bdafd183757d5c5d4e0bd '
sha256sum pkg_publisher.py | \
  grep '^538d6fa41b65373c4cb3040ff3e7512078e93e7f4d6914e8a18e7b583f6ec566 '
```

This section records the older package-authoring rollout. The direct Dock tool
was wired later on 2026-08-08: `docs/agent-package-download.md` records the
current build, emulator-validation, listen, Connect, and result flow. That live
change requires restarting `egg-freckles-chat.service` so its long-running
`server.py` reads the new prompt and can relay the Dock instruction during the
Codex turn.

Rollback restores the saved checkout and restarts the same publisher process.
It deliberately leaves the confined workspace in place so generated source and
packages are not destroyed:

```sh
cd ~/git/newton-harness
git switch --detach backup/mars-before-pkg-write-590b6ab
old_pid=$(cat /tmp/mars-raw-pkg-server.pid)
kill "$old_pid" 2>/dev/null || true
for _ in $(seq 1 20); do
  kill -0 "$old_pid" 2>/dev/null || break
  sleep 1
done
nohup python3 -u runtime/raw_pkg_server.py \
  >runtime/logs/raw-pkg-server.log 2>&1 &
sha256sum examples/harness-client/egg-freckles.pkg pkg_publisher.py
cat /tmp/mars-pkg-write-predeploy.txt
```

This procedure does not merge `master`, install on the MessagePad, or touch
ZC40. The publisher restart is host-only but hardware-facing, which is why the
entire apply sequence remains human-gated.

## The live demo (D3) — 2026-08-03

Isolated emulator instance `d3demo`, flash seeded from
`internal-before-round9-loader-20260725-195622.flash`
(`docs/parallel-emulators.md`), `HarnessToolsR10N:jbfly` and
`HarnessClientA3:jbfly` both installed on it. Everything host-side:

| Piece | Where | Note |
|---|---|---|
| `runtime/raw_pkg_server.py` | `10.42.0.1:18081` | tools broker |
| `server.py` | `0.0.0.0:6801` | host python3, `NEWTON_CODEX_TIMEOUT=300` |
| `codex` | `~/.local/bin/codex` 0.146.0 | picked up from `PATH` by `server.py:235` |

The chat client needed **no change and no rebuild**: `HarnessClientA3`'s
hardcoded `serverAddress: [10, 42, 0, 1]` / `serverPort: 6801`
(`examples/harness-client/Main.newt:42-43`) reaches a host process on the `lo`
alias exactly the way the tools long-poll does. `server.py` logged
`connect ('10.42.0.1', 40642)`.

**The prompt, typed on the Newton with the on-screen keyboard:**

> use your newton tools. what app is in front, how much free space, and how
> many packages are installed.

**The reply, rendered in the Newton's chat transcript 19 seconds later:**

```
Front app: Notepad (paperroll)
Free space: 6,758,976 bytes (6.45 MiB)
Installed packages: 39
```

Screenshot: [`d3demo-screen.png`](../runtime/evidence/d3demo-screen.png).
Full chain: [`d3demo-chat-turn.txt`](../runtime/evidence/d3demo-chat-turn.txt).

Three `newton_tool` calls happened inside that one turn, and the codex rollout
records each with its own duration:

| call | broker reply | duration |
|---|---|---:|
| `newton_tool(op="front_app", timeout=30)` | `{"request_id":"6","status":"result","result":"Notepad (paperroll)"}` | 0.127 s |
| `newton_tool(op="store_info", timeout=30)` | `…"result":"Internal total=7638048 used=879072 free=6758976 ro=n"` | 0.805 s |
| `newton_tool(op="pkg_list", timeout=30)` | `…"result":"count=39"` | 0.796 s |

That is the same warm-link profile as the C1–C3 wire round, so essentially all
of the 19 seconds is the model, not the Newton.

**Why the answer could only have come from the device.** `free=6758976` and
`count=39` are the numbers the reply quotes verbatim. A pre-flight `curl`
against the same broker minutes earlier — before `HarnessClientA3` was
installed onto this instance — read `free=6778912` and `count=38`. The pair
moved by exactly one package.

Three things learned running it:

- **The model batched the three calls through code mode.** Rather than three
  separate tool-call turns it emitted one `exec` script,
  `await Promise.all([tools.mcp__newton__newton_tool({op:"front_app", …}), …])`.
  The tools are re-exported into that sandbox as `mcp__<server>__<tool>`, and
  the parallel calls serialised correctly on the broker's single poll slot.
- **The tools client and the chat client coexist on one Newton, noisily.**
  Both hold NIE endpoints. During the turn the broker logged one
  `Newton tools disconnected` / `Newton tools connected 10.42.0.1:52144`, and
  the Newton raised the familiar modal `Communications — Sorry, a problem has
  occurred` slip *over the chat window*. The turn completed correctly anyway;
  the slip has a close box and is cosmetic. Expect it, do not chase it.
  (Track L1 removed the cause going forward: the tools client and the chat
  client are now one package, `EggFrecklesEF1:jbfly`, sharing one app. Two
  separate packages is what the physical MP2000 still has installed, so expect
  the slip there until Egg Freckles replaces them.)
- **`xdotool` typing drops the first characters and mangles shifted keys.**
  The first attempt lost the leading `Use ` and turned `:` into `;` and `?`
  into `/`. Tap the field, wait ~3 s, then type in short chunks with a pause
  between them (`runtime/evidence/d3demo-prompt-typed.png` is the good one).

Not yet demonstrated: any of this against the **physical** MessagePad — the
tools client has still never run on hardware (ROADMAP "Where we are").
