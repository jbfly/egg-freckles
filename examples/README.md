# examples/ — Newton-side packages

Six package source dirs. Each holds a NewtonScript project built into a
`.pkg` checked into the same directory.

| dir | identity | status |
|---|---|---|
| `harness-client` | `HarnessClientA3:jbfly` ("Chat A3", v2.3-a3) | CURRENT chat client; installed on physical MP2000; built by `make newton-packages` |
| `harness-loader` | `-HarnessLoaderZC40:jbfly` (v2.4) | CURRENT WiFi package loader; installed on physical MP2000 (ZC39 fallback also installed); built by `make newton-packages` |
| `harness-tools` | `HarnessToolsR10P:jbfly` | fixed-op tools client (ping/front_app/get_note/note_list/note_probe/battery/store_info/pkg_list), all proven over the `POST /tools` link on Einstein, not yet on hardware; ROADMAP Track C |
| `hello` | `HarnessHello:jbfly` | toolchain smoke test (`make toolchain-hello`) |
| `ink-capture` | `InkPad2:jbfly` (v2) | ink capture → `/ink` → vision model, emulator-proven only; ink now stays visible after pen-up with Clear/Undo (ROADMAP Track E1, `docs/ink-client-design.md` "Stage 5"); not on hardware yet (Track E2) |
| `note-export` | `NoteExportN13:jbfly` | newest-note → `/note` → reply-as-native-note, proven on emulator and physical MAIN store; folds into Chat A4 (ROADMAP Track F2) |

Package identities are never reused — see `docs/phase3-chat-round.md`
"Package identity" for why, and use `scripts/newton-round.sh` to bump one
correctly. The `.pkg` files checked into each dir above are the built
artifacts; the emulator is served them read-only via the `compose.yaml:41`
mount.
