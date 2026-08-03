# Parallel emulators — one Einstein per worker

Written for an agent worker. If you are about to install a package, restore a
backup, or evaluate NewtonScript, and another worker might be doing the same
thing, claim your own emulator first. Sharing one emulator does not fail
loudly: it fails as somebody else's answer showing up in your result file, and
that reads like a protocol bug.

## Claim your own emulator

One command. Pick a short lowercase name for yourself (`dock`, `pkg`, `w3`):

```sh
make emulator-instance-up INSTANCE=dock
```

It prints everything you need:

```
instance   dock
container  newton-harness-dock_emulator_1
control    http://127.0.0.1:43157
novnc      http://127.0.0.1:51183/vnc.html?autoconnect=1
```

Then export the name once and every tool follows it:

```sh
export NEWTON_INSTANCE=dock

python3 -m emulator.client status
runtime/ns_eval.py '2+2'
```

Or pass `--instance dock` per call. Both tools resolve the instance the same
way — the container is `newton-harness-<INSTANCE>_emulator_1`, and
`emulator.client` asks `podman port` for the published control port, so you
never have to remember or hardcode the number.

Booting to `healthy` takes about 20-40 seconds. Wait for it:

```sh
until [ "$(podman inspect -f '{{.State.Health.Status}}' newton-harness-dock_emulator_1)" = healthy ]; do sleep 5; done
```

## Seed an instance from a saved flash (do this if you need the network)

A fresh instance is a **blank Newton**: it boots into the first-run Welcome
tour, which suppresses floating windows until you click all the way through it,
and it has none of the `runtime/nie2/` stack, so there is no Ethernet driver and
no saved Internet Setup for `InetGrabLink`. Anything that talks to
`10.42.0.1:18081` — the tools long-poll, the loader — will not work on it.

Do not rebuild that by hand. Copy a flash that already has it:

```sh
make emulator-instance-up INSTANCE=c2round
until [ "$(podman inspect -f '{{.State.Health.Status}}' newton-harness-c2round_emulator_1)" = healthy ]; do sleep 5; done

podman stop -t 20 newton-harness-c2round_emulator_1
podman cp ~/newton-archive/newton-harness/flash-backups/internal-before-round9-loader-20260725-195622.flash \
          newton-harness-c2round_emulator_1:/state/internal.flash
podman start newton-harness-c2round_emulator_1
until [ "$(podman inspect -f '{{.State.Health.Status}}' newton-harness-c2round_emulator_1)" = healthy ]; do sleep 5; done
```

The instance must be brought up once first so the `emulator-state` volume
exists; you are overwriting `internal.flash` inside it, not creating it. Total
cost is about 90 seconds. It boots straight into the Notepad with a `PCMCIA
Ethernet` card-inserted slip to dismiss (tap its close box at roughly `247,178`),
and that slip reappearing after a container restart is the sign the NE2K driver
is live. Verified 2026-08-03 for the Track C1–C3 wire round.

It may also boot with one or more `Sorry, a problem has occurred` alerts stacked
*on top of* that slip — `-48807` and `-48601` were both seen in the Track C4
round, before any broker was listening. Tap the alert's close box (roughly
`247,271`) repeatedly until they are all gone, then dismiss the card slip. The
NIE link came up normally afterwards; they are not worth debugging.

The Notepad on this seed holds three entries whose `data` is `nil` — the failed
writes `docs/notes-bridge.md` diagnosed in N2/N3. They read back as empty text.
If you need notes with content, create them
(`local notes := GetRoot().paperroll; notes:NewNote(notes:MakeTextNote(text, nil), nil, nil);`).

**Picking a seed flash.** It has to contain both the driver and a saved setup:

```sh
strings -a  "$f" | grep -c NE2K              # want >0
strings -el "$f" | grep -ci 'Untitled Ethernet'   # want >0
```

| Flash | NE2K | Ethernet Setup | Use it? |
| --- | ---: | ---: | --- |
| `runtime/emulators/mp2000-core-20260803/internal.flash` | 0 | 0 | **No** — core packages restored onto a blank flash over Dock; the NIE install onto it failed with `-48807` (`docs/installed-package-inventory.md:167-171`) |
| `~/newton-archive/newton-harness/flash-backups/internal-before-round9-loader-20260725-195622.flash` | 4 | 3 | **Yes** — newest working snapshot; carries `HarnessLoaderR3O`/`R7B` and no HarnessTools, so nothing competes for the broker |
| `runtime/backups/internal-before-*.flash` (Jul 24) | 4 | 3 | Workable older fallbacks |

Prefer a seed with **no HarnessTools package installed**. Two tools clients on
one broker fight over the single long-poll slot, and a client whose window you
closed keeps retrying its endpoint and raises modal `Communications — Sorry, a
problem has occurred` alerts over whatever you are doing. If you do end up with
a stale one, `podman restart` the container clears it.

## What is actually isolated

Each instance is its own `podman-compose` project (`-p newton-harness-<name>`),
which is what gives you separation for free:

| Resource | Default emulator | Instance `dock` |
| --- | --- | --- |
| Container | `newton-harness_emulator_1` | `newton-harness-dock_emulator_1` |
| State volume | `newton-harness_emulator-state` | `newton-harness-dock_emulator-state` |
| Control port | `127.0.0.1:18080` | kernel-assigned, ask `podman port` |
| noVNC port | `127.0.0.1:6080` | kernel-assigned, ask `podman port` |

The state volume is the one that matters. `/state` holds `internal.flash` (the
Newton store, so installed packages live there), `einstein-control.sock`, and
`einstein-ns-result` — the file `runtime/ns_eval.py` polls for your answer. Two
containers on one volume means one worker reads another worker's result.

The ROM, `/packages`, and `/nie2` stay shared read-only mounts. Nothing writes
to them, so they are not a collision source.

## Avoiding port collisions

There is nothing to avoid — do not assign ports by hand. `make
emulator-instance-up` binds port 0, lets the kernel pick a free port, and hands
it to podman, so N workers can start at the same time without coordinating.
Discover a running instance's port with `podman port <container> 8080`, which is
exactly what `emulator.client --instance` does for you.

## See what is running

```sh
make emulator-instances
```

```
INSTANCE                 STATUS     PORTS
(default)                Up         127.0.0.1:6080->6080/tcp, 127.0.0.1:18080->8080/tcp
alpha                    Up         127.0.0.1:43157->8080/tcp, 127.0.0.1:51183->6080/tcp
beta                     Up         127.0.0.1:35999->8080/tcp, 127.0.0.1:40033->6080/tcp
```

`(default)` is the shared long-lived emulator. Treat it as somebody else's:
never stop, restart, or reconfigure it, and never install into it while other
workers are attached.

## Release it when you are done

```sh
make emulator-instance-down INSTANCE=dock
```

This is `down -v` — it deletes the instance's state volume, including the
Newton flash you installed into. That is the point: an instance is disposable,
so the next worker to claim that name gets a clean Newton. If you need the flash
afterwards, copy it out first:

```sh
podman cp newton-harness-dock_emulator_1:/state/internal.flash ./internal.flash
```

## Defaults are unchanged

With no `NEWTON_INSTANCE` and no `--instance`, everything behaves exactly as it
did before this document existed: `make emulator-up` manages
`newton-harness_emulator_1`, `emulator.client` talks to `127.0.0.1:18080`, and
`ns_eval.py` targets `newton-scratch2_emulator_1` unless `--container` says
otherwise. An explicit `--url` or `--container` always wins over `--instance`.
