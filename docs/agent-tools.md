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
screen (`docs/agent-dev-loop.md`, "Proven 2026-08-03"). Only
`emulator_text`, `emulator_key` and `stage_hw` are still exercised by tests
alone.

`newton_mcp.py` is one stdlib-only file at the repo root. It speaks MCP over
stdio as newline-delimited JSON-RPC 2.0 and implements exactly `initialize`,
`ping`, `tools/list`, `tools/call`; notifications are read and dropped
(`newton_mcp.py:handle`). There is no SDK dependency, which matters because the
server image is `node:22-bookworm-slim` + `python3` and nothing else
(`containers/server.Dockerfile:5-8`).

## What it exposes

| Tool | Arguments | Goes to | Notes |
|---|---|---|---|
| `newton_tool` | `op` (required), `args` (object), `timeout` (s, ≤120, default 20) | `POST {NEWTON_TOOLS_URL}/tools`, default `http://10.42.0.1:18081` | Generic pass-through to the `ToolBroker` (`pkg_publisher.py:354-385`). Reply JSON is returned verbatim; a 4xx/5xx body (`unknown_op`, `timeout`) comes back as `isError` text rather than being swallowed. Ops today: `ping`, `front_app`, `get_note`, `note_probe`, `battery`, `store_info`, `pkg_list`. |
| `emulator_screen` | `instance` | `GET /screen.png` | Returns MCP `image` content (base64 PNG) plus one line of text. **Always allowed**, shared emulator included. |
| `emulator_tap` | `x`, `y`, `instance` | `POST /tap` | 320×480 Newton coordinates. |
| `emulator_text` | `value`, `instance` | `POST /text` | xdotool typing. |
| `emulator_key` | `key`, `instance` | `POST /key` | One xdotool key name. |
| `emulator_newtonscript` | `source`, `instance` | `POST /newtonscript` | One line, raw text body. |
| `emulator_install` | `pkg_path`, `instance` | `POST /install` | `pkg_path` must start with `/packages/` — the endpoint takes a path inside the container, **not** an upload (`docs/install-paths.md` row 1). |
| `build_pkg` | `dir` | `make -C <dir>` | `dir` must resolve under `examples/`. Returns the built `.pkg` path, or the tail of the compiler output when the build fails. |
| `stage_hw` | `pkg_dir` | `make stage-hw PKG=<dir>` | Stages into `runtime/staging/hardware/` and returns the short filename. Installs nothing. |

Instance resolution reuses `emulator.client.instance_url`
(`emulator/client.py:17-30`) — `podman port newton-harness-<instance>_emulator_1
8080` — rather than reimplementing port lookup. Omitting `instance` means the
shared emulator at `NEWTON_CONTROL_URL` (default `http://127.0.0.1:18080`).

## The safety rails (in code, not in a prompt)

Track D2's point is that a prompt is not a rail. All three of these are
enforced in `newton_mcp.py` and covered by tests:

1. **The shared emulator is read-only.** `emulator_tap`, `_text`, `_key`,
   `_newtonscript` and `_install` refuse when no `instance` was passed, unless
   the server's environment carries `NEWTON_ALLOW_SHARED=1`
   (`newton_mcp.py:guard_shared`). The refusal text tells the agent to run
   `make emulator-instance-up INSTANCE=<name>` and pass `instance`.
   `emulator_screen` is exempt — looking is free.
2. **Device-mutating tool ops need a human.** `newton_tool` refuses op names in
   `HUMAN_GATED_OPS` (`pkg_install`, `pkg_remove`, `note_write`, `note_delete`,
   `note_create`, `reset`, `restart`) and returns the exact `curl` for the human
   instead. None of those ops exist on the Newton client yet (ROADMAP C5); the
   rail is in place so they cannot arrive without the gate
   (`docs/notes-bridge.md:16`).
3. **There is no physical-install tool at all.** The tool surface has no path
   that puts a package on the MessagePad. `stage_hw` stages and stops; a human
   opens the ZC40 Loader, types the filename, taps Install
   (`docs/install-paths.md` row 2). `build_pkg`/`stage_hw` also refuse any
   `dir` that does not resolve under `examples/`.

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
   and the tool wrote the file (1104 bytes). So `build_pkg`/`stage_hw` need no
   `--add-dir` and no sandbox change. The flip side is a security note:
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
- **`build_pkg` / `stage_hw` do not work from inside the container either** —
  the image has no `make`, no `tntk`, and no repo checkout.

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
- **`xdotool` typing drops the first characters and mangles shifted keys.**
  The first attempt lost the leading `Use ` and turned `:` into `;` and `?`
  into `/`. Tap the field, wait ~3 s, then type in short chunks with a pause
  between them (`runtime/evidence/d3demo-prompt-typed.png` is the good one).

Not yet demonstrated: any of this against the **physical** MessagePad — the
tools client has still never run on hardware (ROADMAP "Where we are").
