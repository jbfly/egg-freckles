# Install paths — the one table

Three ways a `.pkg` gets onto a Newton (real or emulated), which listener
serves it, and where to send the human. Written for ROADMAP Track B: three
host listeners can serve packages today; this page says which one to use for
each situation. It does not rewrite any of them.

| Situation | Path | Command |
|---|---|---|
| Emulator install | `scripts/newton-round.sh` for a full round (identity bump, build, install, launch, screenshot); `scripts/install-and-launch.sh` against the instance's control port for a bare install | `scripts/newton-round.sh examples/harness-loader r16a` **or** `NEWTON_CONTROL_URL=http://127.0.0.1:<control-port> scripts/install-and-launch.sh /packages/<dir>/app.pkg 'AppSymbol:jbfly'` (control port from `make emulator-instance-up INSTANCE=<name>`, `docs/parallel-emulators.md`) |
| Physical Newton, normal operation | `runtime/dual_send.py` on Mars (`10.42.0.1:18081`) + the ZC40 loader on the device: human types the `.pkg` filename, taps Install | `python3 runtime/dual_send.py` (host), then on the Newton: open **ZC40 Loader**, type the filename, tap **Install** |
| Physical Newton, bare-metal recovery | NS Basic DEMO bootstrap → reinstall the loader → then the normal path above | Type `bootstrap/nsbasic-bootstrap.bas` into the NS Basic demo slot (see `docs/install-lifeline-plan.md` §7); alternatives Newt's Cape and Dock TCP are preserved in `downloads/recovery/` |

## Row 1 in detail — what `POST /install` actually takes

`POST /install` is **not** a multipart upload. The handler reads the raw request
body as a UTF-8 string and forwards it to the Einstein control socket as
`install <body>` (`emulator/control.py:343-353`), so the body must be a **path
inside the container**, 1 to 8184 bytes. The Einstein side rejects anything
that is not under `/packages/` or that contains `..`
(`containers/patches/einstein-control-socket.patch:119-124`), and `/packages`
is the read-only mount of the repo's `examples/` directory
(`compose.yaml:40`). A `curl -F pkg=@…` form upload returns HTTP 400; an
earlier version of this table showed that form and it never worked.

`scripts/install-and-launch.sh` is the blessed two-liner: it POSTs the path to
`/install`, then POSTs `GetRoot().|<symbol>|:Open();` to `/newtonscript`.

## Row 2 in detail — which listener, and why

**`dual_send.py` is *the* 18081 listener** — `docs/newton-networking-lessons.md`
§4.9: "Use `dual_send.py` on 18081 from day one (§2 footgun). The
NS-Basic-bootstrap vs HTTP-Loader port collision cost two hardware cycles
before the sniff-and-branch server removed it." It protocol-sniffs the first
bytes of every connection (`runtime/dual_send.py:84-99`): `GET ` is the ZC40
loader's HTTP fetch, served from `runtime/staging/hardware/` by filename
(`:38-52`); a bare `G` is the NS Basic bootstrap's raw socket read, which gets
exactly 15,000 zero-padded bytes of `harness-loader.pkg` (`:22-35`).

**`runtime/raw_pkg_server.py` is historical** — it wraps
`pkg_publisher.make_server` on the same host/port (`:6-10`), predates the
sniff-and-branch fix, and does not speak the NS Basic bootstrap protocol at
all. Kept because six other docs still cite it, not because it is the loader
path — do not start it for an install.

**`pkg_publisher.py`'s package serving is a different channel.** Its
`ToolBroker` + HTTP handler (`pkg_publisher.py:62`, `:281`) back `/tools`,
`/ink`, and `/note` for `examples/harness-client` — since Track L1 that one
package is both the chat client and the tools client, and `examples/harness-tools`
is deleted (`Ask` POSTs `/ink` for a drawing; nothing calls `/note` since Track F2
moved the note bridge onto the chat transport) — the agent-facing channel, not the
ZC40 loader's install flow. Do not point the loader at it. It also serves the
client package itself at `/egg-freckles.pkg`, still answering the old
`/harness-client.pkg` path as an alias (`pkg_publisher.py:482-487`), so a loader
with the old filename typed in keeps working.

Use `make stage-hw PKG=<examples-dir>` (below) to build, copy into
`runtime/staging/hardware/`, and get the exact short filename to type.

## Row 3 in detail

The NS Basic REPLACE DEMO bootstrap (`bootstrap/nsbasic-bootstrap.bas`) is
hardware-proven: "All 27 lines... were checked against device photos; the
saved target is Mars at `10.42.0.1:18081`" (`docs/START-HERE.md`, "Current
state"). It gets the loader itself back onto a bare-metal device with zero
prerequisites, after which row 2 applies again. Newt's Cape and Dock TCP are
preserved as alternative recovery layers in `downloads/recovery/` (file list
and checksums in `downloads/recovery/README.md`) and ranked in full in
`docs/install-lifeline-plan.md` — a plan, not verified state, except where it
cites a hardware run.

## `make stage-hw` — build and stage one package for hardware

```sh
make stage-hw PKG=examples/harness-loader
```

Builds `PKG` the same way `make newton-packages` does (forces a rebuild,
stamps the reproducible-build header per `NEWTON_SOURCE_DATE_EPOCH`), copies
the resulting `.pkg` into `runtime/staging/hardware/`, and refreshes that
directory's `SHA256SUMS` (only the one entry changes; every other staged
package's line is left untouched). It prints the exact short filename —
e.g. `harness-loader.pkg` — to type into the ZC40 loader.

Needs `~/newton-dev/prefix/bin/tntk` built with the vendored
`tools/tntk-project-version.patch` applied to that out-of-tree checkout;
without it every rebuild silently regresses to package version 1
(`docs/START-HERE.md:96-98`). This is a one-time host setup step, not
something `stage-hw` applies itself.

## `dual-send` as a systemd user unit (Track B3)

`runtime/dual-send.service` exists but is not yet enabled by default. Install
it so the package server survives logout/reboot instead of needing a manual
`nohup` (folded in from `docs/next-hardware-session.md:96-106`):

```sh
cp runtime/dual-send.service ~/.config/systemd/user/
systemctl --user enable --now dual-send
loginctl enable-linger jbfly
```

Confirm it is serving the current build, not something stale, with
`journalctl --user -u dual-send -f`. Expect a line naming the bootstrap
package and its sha256, e.g. `bootstrap harness-loader.pkg 15000 bytes
sha256=…`, then `serving runtime/staging/hardware on 0.0.0.0:18081`.

## The human gate — always, on physical hardware

`docs/notes-bridge.md:16`: "Destructive operations require an explicit human
confirmation gate on real hardware. Disposable emulators are exempt from that
confirmation requirement." Treat every row-2/row-3 install as something a
human confirms before and after, never something fired unattended. ROADMAP
Track C2 will add an automated free-space check (`store_info`) before
agent-driven installs; until then, confirm free space manually — row 2's
hardware install failures have been card-memory-full, not transport failures
(`docs/hardware-bench-runbook.md:172-176`).
