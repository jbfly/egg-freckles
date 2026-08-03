# examples/ — Newton-side packages

Five package source dirs. Each holds a NewtonScript project built into a
`.pkg` checked into the same directory.

| dir | identity | status |
|---|---|---|
| `dice` | `Dice1:jbfly` ("Newton Dice") | Track G2 proof artifact: the first app an **agent** built end to end (`docs/agent-dev-loop.md`, "Proven 2026-08-03"). Roll button → `Random(1, 6)`; emulator-proven on instance `gloop`, never on hardware. Also the smallest working example of a button + a live-updated text view |
| `harness-client` | `HarnessClientA8:jbfly` ("Chat A8", v2.4-a8) | CURRENT chat client and **the harness panel**: chat + `Ask Note` / `Save Note` + an `Ink` overlay, all in one app (ROADMAP Track F2). Long prompts and long notes split into `MSGP` parts (Track F1); built by `make newton-packages`. Since A8 the transcript is wrapped onto a 12-row grid and the **Up**/**Dn** buttons page that window over the 6 KiB ring (Track A8). `HarnessClientA7` is what is installed on the physical MP2000 — everything since is emulator-proven only |
| `harness-loader` | `-HarnessLoaderZC40:jbfly` (v2.4) | CURRENT WiFi package loader; installed on physical MP2000 (ZC39 fallback also installed); built by `make newton-packages` |
| `harness-tools` | `HarnessToolsR10P:jbfly` | fixed-op tools client (ping/front_app/get_note/note_list/note_probe/battery/store_info/pkg_list), all proven over the `POST /tools` link on Einstein, not yet on hardware; ROADMAP Track C |
| `hello` | `HarnessHello:jbfly` | toolchain smoke test (`make toolchain-hello`) |

Package identities are never reused — see `docs/phase3-chat-round.md`
"Package identity" for why, and use `scripts/newton-round.sh` to bump one
correctly. The `.pkg` files checked into each dir above are the built
artifacts; the emulator is served them read-only via the `compose.yaml:41`
mount.

`ink-capture` (`InkPad2:jbfly`) and `note-export` (`NoteExportN13:jbfly`) were
deleted in Track F2 — their canvas, encoder and note read/create code now live
inside `harness-client`, which is the whole point of the panel. Git history
keeps them; `docs/ink-client-design.md` and `docs/notes-bridge.md` still
describe what they proved.
