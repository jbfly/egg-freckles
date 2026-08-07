# Mars package-authoring deployment

Deployed 2026-08-07 (UTC). Live host-side "write me a program" feature on mars.
Checkout: `5599e7b9b1684ae73bf4cb1434e5ae792e710780` on `master`.

## What runs on mars now
- **Chat server**: `~/.config/systemd/user/egg-freckles-chat.service` → `/usr/bin/python3 -u server.py`, listening on **6801** (lingering user service). Codex reachable via the service PATH (`/home/jbfly/.local/bin/codex`).
- **Emulator image**: `localhost/newton-harness-dev:local`, built from this checkout with rootless podman.
- **Download server untouched**: `dual-send.service` still active on **18081**, still serving EF21 `6652fb0b2e28412cf63caf9cd692359ecee0388206d0bb4131fc1cb9a96a8ebb`.

## Host setup that was required (not in git — host state)
1. `sudo pacman -S --needed podman` (podman 6.0.2) + rootless subuid/subgid + `podman system migrate`.
2. `systemctl --user enable --now podman.socket` — the docker-compose provider mars's `podman compose` shells out to needs the rootless API socket, else builds fail with `dial unix .../podman.sock: no such file`.
3. `codex` CLI installed + authenticated on mars.
4. **Newton ROM**: real 8 MB `717006` dump (sha256 `2f2ce27d59203d0ce48165b20d6b5787`) installed at `/home/jbfly/newton-dev/prefix/bin/717006` (was an empty placeholder dir). `.env` `NEWTON_ROM_PATH` already pointed there.

## Two bugs found and fixed
- **Compose v2 container naming.** mars's `podman compose` → docker-compose plugin names containers with hyphens (`newton-harness-<inst>-emulator-1`), but all repo tooling assumes underscores (`emulator/client.py:19`, `runtime/ns_eval.py`, `scripts/emulator-instance.sh`, `scripts/newton-round.sh`). Fix: `~/.local/bin/podman-compose` wrapper and the chat service unit both export `COMPOSE_COMPATIBILITY=1`, restoring legacy underscore names. Drop only after every hardcoded name is migrated.
- **EF13 seed flash wedges an isolated instance.** The EF13 proof flash carries a live hardware TCP session (`dst=18081`); restored into an isolated emulator the Newton loops in `TCPDIAG` and `/health` never comes up. A fresh (un-seeded) emulator boots healthy and is sufficient to prove authoring. Don't seed EF13 into isolated package-authoring instances.

## Smoke proof (PASS, recovery_used=0)
A real native `~NEWTONCLI 1` / `MSG` turn on 6801 asked for tic-tac-toe. The agent itself chose `create_project → write_source → build_pkg → emulator_install → emulator_screen` and wrote valid NewtonScript.
- Project: `mars-ttt-0807-r3`, identity `MarsTTT0807R3:nwtn`, `protoFloatNGo` view.
- Built pkg sha256 `dff3f7bc4bcb5c5a7ad198bd84b4da0356882f7b348772cbba54c2fa0dc606ac`.
- Screenshot sha256 `38c7e620c6d31273765388ac3bdd2383fdacc706a593f627480c0573685ad536`.
- Evidence: `runtime/evidence/marssmoke-20260807T164030Z-*` (wire transcript, codex rollout, Main.newt, pkg, png).
- Isolated instance torn down; no physical Newton write.

## Operate
- Start/stop/restart: `systemctl --user {start,stop,restart} egg-freckles-chat.service`
- Status/logs: `systemctl --user status egg-freckles-chat.service --no-pager`; `journalctl --user -u egg-freckles-chat.service -n 100 --no-pager`; `ss -ltnp | grep ':6801 '`
