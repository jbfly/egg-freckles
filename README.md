# Newton harness

**The harness uses rootless Podman for an always-on Newton server and an optional headless Einstein development environment.**

*Prepared 2026-07-23 from the locally verified Einstein, `tntk`, cDCL, and NEWT/0 builds. Podman is daemonless: agents can operate these containers without access to a root-owned Docker socket.*

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

This host already has subordinate UID/GID ranges, unprivileged user namespaces,
cgroup v2, and systemd user lingering enabled. On another host, verify them
before relying on reboot-time startup:

```sh
podman info --format '{{.Host.Security.Rootless}}'
loginctl show-user "$USER" -p Linger
```

## What runs where

| Service | Purpose | Default host access | Persistent data |
| --- | --- | --- | --- |
| `server` | Telnet chat endpoint for a real or emulated Newton | TCP `6801` | Conversation state and Codex login |
| `emulator` | Einstein on a private Xvfb display | HTTP `127.0.0.1:18080`; noVNC `127.0.0.1:6080` | Newton internal flash |
| `toolchain` | Reproducible `tntk` package builds | None | Writes build output into the checked-out repo |

The emulator never connects to the host desktop. Xvfb owns its display, so automated taps and keystrokes cannot steal focus from normal windows.

## Required private files

Einstein and `tntk` need two Apple files that are not included in this repository:

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

Human access is available at `http://127.0.0.1:6080/vnc.html?autoconnect=1`. The noVNC and control ports are bound to loopback deliberately; use an SSH tunnel when the container runs on another machine.

Stop it without deleting the virtual Newton’s flash:

```sh
make emulator-stop
```

## Agent screen and input control

The control service uses Newton screen coordinates: `x=0..319`, `y=0..479`.

```sh
python3 -m emulator.client status
python3 -m emulator.client screen /tmp/newton-screen.png
python3 -m emulator.client tap 160 240
python3 -m emulator.client text "hello world"
python3 -m emulator.client key Return
```

Injected NewtonScript can return text without a screenshot. The TCP callback path is not used: live tests recorded payload timeouts, so Einstein's existing `Print(result)` primitive writes one disposable result file instead. Source must fit on one line.

```sh
runtime/ns_eval.py '2+2'
```

The equivalent NewtonScript result expression is simply `2+2`; strings are returned quoted, matching Einstein's existing `Print` format. Select another disposable emulator with `--container NAME`.

A second isolated NS Basic scratch emulator uses its own compose project, state volume, ports, and package bind:

```sh
NEWTON_IMAGE_TAG=ns-eval NEWTON_CONTROL_PORT=18091 NEWTON_NOVNC_PORT=6091 \
  podman-compose -p newton-scratch2 -f compose.yaml -f runtime/nsbasic-scratch.override.yaml \
  --profile emulator up -d emulator
```

Its noVNC URL is `http://127.0.0.1:6091/vnc.html?autoconnect=1`; its control socket is `/state/einstein-control.sock` inside `newton-scratch2_emulator_1` (host volume `newton-scratch2_emulator-state`).

Einstein dialogs and its package installer sit outside the Newton screen. Agents can inspect and control the complete window separately:

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
| `POST` | `/text` | Type `{"text": "..."}` into the active Einstein control |
| `POST` | `/key` | Send a key such as `{"key": "Return"}` |

## Build Newton packages reproducibly

Build and stage Harness Loader v1.1 and Harness Client v1.1 with one target:

```sh
make newton-packages
```

The install candidates and checksums are written to `runtime/staging/`. The target pins tntk's embedded package timestamp so repeated builds from unchanged source are byte-identical. See `docs/newton-client-notes.md` for toolchain overrides, package-format details, and the update flow.

The original smoke-test package remains available through `make toolchain-hello`; it writes `examples/hello/hello.pkg`.

## Current verification

- The local Einstein build boots the supplied ROM through Newton setup and into Notes.
- The rootless Podman image boots Einstein on Xvfb without opening a host window.
- The telnet server socket test passes.
- The container toolchain rebuilds the corrected sample, and Einstein installs
  and launches it without the previous activation error.
- Controller unit tests verify screen cropping, tap bounds, the 78-pixel Einstein toolbar offset, and command failures.
- The Compose model validates with the existing Docker Compose parser; a
  rootless guard prevents the project shortcuts from using rootful Podman.

## Gaps

- The server still needs its one-time Codex device login.
- Reboot-time startup is not enabled yet.
- Einstein guest networking and an end-to-end connection to `server:6801` are not wired up yet. That should follow the isolated emulator test, rather than being mixed into it.

The stated verification is deterministic; untested container and guest-network behavior is listed explicitly above.
