# The development harness — containers, services, ports

This is the operational reference for running Egg Freckles on a host: what the
containers are, which ports they bind, and every command that drives the
emulator. It was the top half of `README.md` until the repo got a public front
door; the README now links here.

**The harness uses rootless Podman for an always-on Newton server and an
optional headless Einstein development environment.**

*Prepared 2026-07-23 from the locally verified Einstein, `tntk`, cDCL, and
NEWT/0 builds. Podman is daemonless: agents can operate these containers
without access to a root-owned Docker socket.*

## Security boundary

All services run in a rootless user namespace with `keep-id`. Container root maps
to an unprivileged host identity, not host root. The project deliberately does
not enable or mount the Podman API socket.

This protects the host from container-to-root escalation through a daemon
socket. It does not isolate an agent from files that the host user can already
read: agents run as that user. Keep bind mounts narrow, keep private mounts
read-only, and do not add host devices or broad home-directory mounts.

The emulator's noVNC and control ports bind only to loopback. Port `6801` binds
to the host network because a physical Newton must be able to reach the server.

## One-time host setup

On Arch Linux:

```sh
sudo pacman -S --needed podman podman-compose passt fuse-overlayfs
```

That is the only routine requiring root. Do not add the user to the `docker`
group, do not run `sudo podman`, and do not enable `podman.socket`.

The development host already has subordinate UID/GID ranges, unprivileged user
namespaces, cgroup v2, and systemd user lingering enabled. On another host,
verify them before relying on reboot-time startup:

```sh
podman info --format '{{.Host.Security.Rootless}}'
loginctl show-user "$USER" -p Linger
```

## What runs where

| Service | Purpose | Default host access | Persistent data |
| --- | --- | --- | --- |
| `server` | Chat endpoint for a real or emulated Newton | TCP `6801` | Conversation state and Codex login |
| `emulator` | Einstein on a private Xvfb display | HTTP `127.0.0.1:18080`; noVNC `127.0.0.1:6080` | Newton internal flash |
| `toolchain` | Reproducible `tntk` package builds | None | Writes build output into the checked-out repo |

The emulator never connects to the host desktop. Xvfb owns its display, so
automated taps and keystrokes cannot steal focus from normal windows.

## Required private files

Einstein and `tntk` need two Apple files that are not included in this
repository:

```text
secrets/
├── 717006
└── Newton 2.1
```

- `717006` is your own Newton ROM dump and must be exactly 8,388,608 bytes.
- `Newton 2.1` is the NTK platform file used when compiling packages.

Both `secrets/` and emulator runtime data are ignored by Git.

## Start the always-on server

Build the image, authenticate Codex once using the headless device flow, then
start the service:

```sh
podman-compose build server
make server-login
make server-up
```

To give the agent behind that chat actual tools — the Newton `/tools` ops, the
emulator control API, and the package build — register the MCP server once per
`codex-home` volume:

```sh
make server-mcp
```

That writes `[mcp_servers.newton]` into the same volume as the login, with the
`default_tools_approval_mode = "approve"` line without which every tool call in
a non-interactive run fails.

**For tool work, run the server on the host instead** — `python3 server.py`
needs only stdlib, and only there do `podman`, `make` and `127.0.0.1` exist for
the `emulator_*` and build tools:

```sh
codex mcp add newton -- python3 $PWD/newton_mcp.py   # once; then add the
                                                     # approval line by hand
python3 server.py                                    # 0.0.0.0:6801
```

Read `docs/agent-tools.md` first: the safety rails, the measured limits on what
these tools reach from inside the container, and the live demo that proved the
host shape.

The Codex login and Newton conversation state live in rootless named volumes. A
container replacement does not discard them.
Set `NEWTON_UPSTREAM_DNS` if the host network blocks the default `1.1.1.1` resolver.

For a backend-free connection test:

```sh
make server-test
```

## Start the headless emulator

```sh
make emulator-up
make status
```

Human access is available at `http://127.0.0.1:6080/vnc.html?autoconnect=1`. The
noVNC and control ports are bound to loopback deliberately; use an SSH tunnel
when the container runs on another machine.

Stop it without deleting the virtual Newton's flash:

```sh
make emulator-stop
```

## Agent screen and input control

The control service uses Newton screen coordinates: `x=0..319`, `y=0..479`.

```sh
python3 -m emulator.client status
python3 -m emulator.client screen /tmp/newton-screen.png
python3 -m emulator.client tap 160 240
python3 -m emulator.client drag 40 400 280 400 --duration 0.5 --steps 20
python3 -m emulator.client text "hello world"
python3 -m emulator.client key Return
python3 -m emulator.client install /packages/hello/hello.pkg
python3 -m emulator.client newtonscript 'GetRoot().|HarnessHello:jbfly|:Open();'
```

Injected NewtonScript can return text without a screenshot. The TCP callback path
is not used: live tests recorded payload timeouts, so Einstein's existing
`Print(result)` primitive writes one disposable result file instead. Source must
fit on one line.

```sh
runtime/ns_eval.py --container newton-harness_emulator_1 '2+2'
```

The equivalent NewtonScript result expression is simply `2+2`; strings are
returned quoted, matching Einstein's existing `Print` format. Pass
`--container NAME` to choose the emulator: the built-in default is the
`newton-scratch2` scratch instance, which is usually not running.

A second isolated NS Basic scratch emulator uses its own compose project, state
volume, ports, and package bind:

```sh
NEWTON_IMAGE_TAG=ns-eval NEWTON_CONTROL_PORT=18091 NEWTON_NOVNC_PORT=6091 \
  podman-compose -p newton-scratch2 -f compose.yaml -f runtime/nsbasic-scratch.override.yaml \
  --profile emulator up -d emulator
```

Its noVNC URL is `http://127.0.0.1:6091/vnc.html?autoconnect=1`; its control
socket is `/state/einstein-control.sock` inside `newton-scratch2_emulator_1`
(host volume `newton-scratch2_emulator-state`).

`make emulator-instance-up INSTANCE=name` generalises that recipe: it starts an
isolated emulator on a free port pair, and `--instance name` (or
`NEWTON_INSTANCE=name`) points `emulator.client` and `runtime/ns_eval.py` at it.
See [parallel-emulators.md](parallel-emulators.md).

Einstein dialogs and its package installer sit outside the Newton screen. Agents
can inspect and control the complete window separately:

```sh
python3 -m emulator.client window /tmp/einstein-window.png
python3 -m emulator.client window-tap 290 40
```

The raw HTTP endpoints are:

| Method | Path | Meaning |
| --- | --- | --- |
| `GET` | `/health` | Emulator readiness and window geometry |
| `GET` | `/screen.png` | Cropped 320×480 Newton display |
| `GET` | `/window.png` | Full Einstein window, including dialogs |
| `POST` | `/tap` | Tap Newton coordinates with `{"x": 160, "y": 240}` |
| `POST` | `/window/tap` | Click full-window coordinates |
| `POST` | `/drag` | Drag from `{"start_x", "start_y", "end_x", "end_y"}`, optional `duration`/`steps` |
| `POST` | `/text` | Type `{"text": "..."}` into the active Einstein control |
| `POST` | `/key` | Send a key such as `{"key": "Return"}` |
| `POST` | `/install` | Install the `.pkg` at the given path (raw text body, not JSON) |
| `POST` | `/newtonscript` | Run the given NewtonScript source (raw text body, not JSON) |

## Build Newton packages reproducibly

Build and stage the two Newton packages — Harness Loader and the client, **Egg
Freckles** (`egg-freckles.pkg`, which since Track L1 carries the chat client and
the fixed-op tools channel in one app) — with one target:

```sh
make newton-packages
```

The install candidates and checksums are written to `runtime/staging/`. The
target pins tntk's embedded package timestamp so repeated builds from unchanged
source are byte-identical. See `docs/newton-client-notes.md` for toolchain
overrides, package-format details, and the update flow, and
`docs/host-setup.md` if `~/newton-dev` (cDCL + `tntk` + the NTK platform
files) does not exist yet on this host — a from-zero recipe, verified to
reproduce byte-identical `.pkg` output on a second host.

The original smoke-test package remains available through `make toolchain-hello`;
it writes `examples/hello/hello.pkg`.

## Verification status

- The local Einstein build boots the supplied ROM through Newton setup and into Notes.
- The rootless Podman image boots Einstein on Xvfb without opening a host window.
- The chat server socket test passes.
- The container toolchain rebuilds the corrected sample, and Einstein installs
  and launches it without the previous activation error.
- Controller unit tests verify screen cropping, tap bounds, the 78-pixel Einstein
  toolbar offset, and command failures.
- The Compose model validates with the existing Docker Compose parser; a
  rootless guard prevents the project shortcuts from using rootful Podman.

Einstein guest networking and the end-to-end connection to `server:6801` are not
gaps: the native client completes a full framed round trip to a real backend,
wire-confirmed in `docs/phase3-chat-round.md` (2026-07-26). See
`docs/newton-networking-lessons.md` for how the transport actually works.

Still missing: the server needs its one-time Codex device login, and
reboot-time startup is not enabled for the server or emulator (a `dual-send`
systemd user unit does exist — `docs/install-paths.md`).
