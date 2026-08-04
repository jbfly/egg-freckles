# examples/ — Newton-side packages

Four package source dirs. Each holds a NewtonScript project built into a
`.pkg` checked into the same directory.

| dir | identity | status |
|---|---|---|
| `dice` | `Dice1:jbfly` ("Newton Dice") | Track G2 proof artifact: the first app an **agent** built end to end (`docs/agent-dev-loop.md`, "Proven 2026-08-03"). Roll button → `Random(1, 6)`; emulator-proven on instance `gloop`, never on hardware. Also the smallest working example of a button + a live-updated text view |
| `harness-client` | `EggFrecklesEF6:jbfly` ("Egg Freckles", v1.0-ef6) | CURRENT and **the only package the human installs**: the chat window, the `Ask Note`/`Save Note` bridge to stock Notes, and the fixed-op `/tools` channel, in one app on one NIE link (ROADMAP Track L1). `Ask Note` sends the newest note *whatever kind it is* — text down the chat path, drawings as `NSI1` strokes to `POST /ink`, a mixed page as one request carrying both — and "newest" now means the highest `EntryUniqueID`, which a wrong device clock cannot poison. Long prompts and long notes split into `MSGP` parts (Track F1); the transcript is wrapped onto a 12-row grid with **Up**/**Dn** paging it (Track A8); the window centres itself on the live root box. Built by `make newton-packages` as `egg-freckles.pkg`. **The physical MP2000 still runs `HarnessClientA7` plus the separate `HarnessToolsR10P`** — everything from A8 on is emulator-proven only, and Egg Freckles supersedes A8, A9 *and* R10P in one install. **Since Track L2 it also puts "Send to AI" in the stock Notes Action (envelope) menu** — choose it on any page and that page, whatever kind it is, goes to the host and the answer comes back as a native note filed in an "AI" folder. It works with the Egg Freckles window closed, it is hooked from the part frame's `InstallScript` so it survives a reset, and it needs no newest-note guess because the ROM hands the route script the live soup entry of the page whose envelope was tapped. **EF5 fixes what the third hardware test found there**: EF4 filed the reply by searching for "the newest note" afterwards, which on the MP2000's multi-store Notes soup named the *source* note instead — the reply arrived Unfiled and the user's own note went into AI. The reply entry is now held rather than searched for, and both icons arrived in the same round (`docs/notes-integration-design.md`, "Third hardware test"). **EF6 answers the fourth and fifth hardware tests**: ink is now *decimated, not truncated* — every stroke survives and the points inside it are thinned to fit (`kMaxPoints` 400 -> 1600), the true drawn stroke count is reported, and thinning is stated out loud, which is what fixes a handwritten sentence arriving as its first three words; the `/tools` long poll is owned by the package-level install-hook agent rather than the window, so it answers **with the app closed and after a reset** (the "Newton not responding to pings" failure); and every NIE-invoked callback is wrapped in `try ... onexception` with one 5-second retry on a bind failure, against the `-48803`/`-60047` pair the fourth test photographed. ROADMAP status log, EF6 entry |
| `harness-loader` | `-Loader1:jbfly` ("Loader", v1.0) | CURRENT WiFi package loader in source. Renamed out of dev cruft after the fifth hardware test: Extras shows plain **Loader**, the filename field is the full window width and 42px tall instead of 26, and the stock `protoKeyboardButton` sits beside it so a name can be typed on the ROM keyboard instead of written in ink. Identity convention is `-Loader<n>:jbfly`, `n` incrementing and never reused; the leading `-` is kept from the `-HarnessLoaderZC*` series. Emulator-proven on instance `loaderround` (`runtime/evidence/loaderround-*`), **not yet on hardware** — the physical MP2000 still runs `-HarnessLoaderZC40:jbfly` ("ZC40 Loader 2.4") — `ZC39` was the deep fallback but the user deleted it from the device (reported 2026-08-04), so ZC40 is now the deep fallback — and the upgrade path is in `docs/ROADMAP.md`. Built by `make newton-packages` |
| `hello` | `HarnessHello:jbfly` | toolchain smoke test (`make toolchain-hello`) |

Package identities are never reused — see `docs/phase3-chat-round.md`
"Package identity" for why, and use `scripts/newton-round.sh` to bump one
correctly. The `.pkg` files checked into each dir above are the built
artifacts; the emulator is served them read-only via the `compose.yaml:41`
mount.

Three example dirs have been folded into `harness-client` rather than kept
beside it, because the human installs packages one at a time on a 1997
touchscreen and every extra package is another install, another Extras icon and
another NIE client:

- `ink-capture` (`InkPad2:jbfly`) and `note-export` (`NoteExportN13:jbfly`),
  deleted in Track F2 — their encoder and note read/create code moved in.
- `harness-tools` (`HarnessToolsR10P:jbfly`), deleted in Track L1 — its long-poll
  transport and all eight ops (`ping`, `front_app`, `battery`, `store_info`,
  `pkg_list`, `note_list`, `get_note`, `note_probe`) moved in verbatim, with
  every name prefixed `Tool*` so nothing collides case-insensitively with the
  chat side. The `POST /tools` wire contract did not change; what changed is
  that the answers now come from the app the human already has open. A second
  tools app was also a second NIE client competing for the broker's single
  long-poll slot — the source of the cosmetic `Communications` alerts in the
  2026-08-03 hardware test.

Git history keeps all three; `docs/ink-client-design.md`, `docs/notes-bridge.md`
and `docs/newtonscript-eval.md` still describe what they proved.

Note that `harness-client/` keeps its directory name (a lot of docs cite paths
inside it) while the project, the package and the app carry the product name:
`egg-freckles.nprj` -> `egg-freckles.pkg` -> "Egg Freckles" in Extras.
