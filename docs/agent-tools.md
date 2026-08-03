# Agent tools — the MCP server (`newton_mcp.py`)

ROADMAP Track D1, with D2's rails folded in. This is the file that closes the
gap named in `docs/ROADMAP.md`: "the agent has no tools". `server.py` still
only relays chat; the *agent* behind that chat (`codex exec`,
`server.py:227-260`) now gets the host's Newton surfaces as MCP tools.

**Status 2026-08-03: code + registration + tests done, live demo pending.**
Nothing in this page has been exercised against a running broker or emulator
yet — see "What the live demo still has to do" at the bottom.

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
make server-mcp      # podman-compose run --rm server codex mcp add newton -- python3 /app/newton_mcp.py
```

which writes (verified by running the same `codex mcp add` against a scratch
`CODEX_HOME` on the host, codex-cli 0.146.0):

```toml
[mcp_servers.newton]
command = "python3"
args = ["/app/newton_mcp.py"]
```

`containers/server.Dockerfile` copies `newton_mcp.py` and
`emulator/{__init__,client}.py` into `/app`. Nothing in `server.py` changes —
the chat wire protocol is untouched, and if the backend is ever swapped for
Claude the same MCP server plugs in.

Running the server on the *host* instead (see the next section — this is the
recommended shape for the emulator tools), the same registration is:

```sh
codex mcp add newton -- python3 /home/jbfly/git/newton-harness/newton_mcp.py
```

Two things are **unverified** and are the first things the live-demo session
should check:

- **`[verify]` whether `codex exec` auto-approves MCP tool calls** in
  non-interactive mode, or whether `[mcp_servers.newton]` needs an approval
  setting (the host config uses `default_tools_approval_mode = "prompt"` for
  another server, `~/.codex/config.toml`). A prompt-mode tool in a
  non-interactive run has nobody to ask.
- **`[verify]` whether the MCP server subprocess is inside the
  `--sandbox read-only` policy** that `server.py:235` passes. If it is,
  `build_pkg`/`stage_hw` cannot write and would need `--add-dir` or a
  different sandbox mode; `newton_tool` and the emulator tools only need
  network and would be unaffected either way.

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

**Recommended fix: run `server.py` on the host for agent-tool work**, where
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

## What the live demo still has to do (D3)

1. Start the tools broker on the host (`pkg_publisher.py`, 18081) and get a
   Newton — physical or a network-ready emulator — polling it. Note the
   ROADMAP's blocker is gone: `10.42.0.1/24` **is** on `lo` as of 2026-08-03.
2. Register the server (`make server-mcp`, or the host `codex mcp add` above)
   and settle the two `[verify]` items in "How it is registered".
3. Prove D1's acceptance: from Chat on the Newton, ask *"what app is front on
   the newton?"*; the agent calls `newton_tool(op="front_app")` and the answer
   comes back as a chat reply.
4. Prove D3's gate: ask for free space and installed packages — `store_info`
   and `pkg_list`, the two C1–C3 ops that have returned real values under
   `ns_eval` but have never travelled the `/tools` link
   (`runtime/evidence/toolsround-r10m-nseval.txt`, ROADMAP status log).
5. Record the transcript and the timings under `runtime/evidence/` and update
   this page's status line.
