# ROADMAP — from a working chat app to "Claude Code for the Newton"

Written 2026-08-03 after a full-repo audit. This is the successor to `PLAN.md`
(phases 0–3 there are shipped; this doc picks up at its phase 4). Point new
sessions here; each track below is sized so a single session of a cheaper
agent can complete one task and verify it.

## Status log (update this section as tracks complete)

- **2026-08-03 — Track F4 done: the Newton drives its own agent.** Seven slash
  commands — `/help`, `/status`, `/model`, `/effort`, `/sessions`,
  `/new [name]`, `/resume <n|name>` — are intercepted in `server.py` before the
  backend is called and answered as ordinary `TEXT` frames. **Nothing on the
  Newton changed**: no client rebuild, no new wire op, so this is live on
  hardware **Chat A3** as it stands, and the PT100 terminal path gets it for
  free from the same code. Model and effort are **per session**, persisted in a
  new `sessions.json` registry that adopts the old single `session.json` as
  session 1, and they reach codex as `-m <model>` / `-c
  model_reasoning_effort=<level>`. Numbers beat names on a touchscreen, so
  `/model 2` and `/resume 1` work everywhere a name does.
  Proven on isolated instance `f4round` (seeded flash) with the **committed**
  Chat A7 bytes and `NEWTON_FAKE_BACKEND=1 server.py:6801`, then with the real
  backend: `/model 5` typed on the Newton, then a prompt, produced
  `codex argv: codex exec … -m gpt-5.4-mini -c model_reasoning_effort=low
  resume --json … 019fc923-c03a-7fd3-b7c7-4fe1670ebd77` — the **Track D3
  thread** — and that thread's codex rollout now records turn 1 as
  `gpt-5.6-sol/high` (D3) and turn 2 as `gpt-5.4-mini/low`. A 1997 MessagePad
  changed the model of a live codex thread. Clean screenshot of the whole
  feature with a real reply: `runtime/evidence/f4round-21-real-clean.png`.
  **Four empirical findings about this host's codex**, all in
  `docs/chat-commands.md`: valid model names come from
  `~/.codex/models_cache.json` and an invalid one is *not* a CLI error but an
  HTTP 400 mid-turn; `minimal` effort parses but the API refuses it while
  `web_search` is enabled, so the list is `low/medium/high/xhigh`; **`resume`
  does honour `-m` and `-c`** (so a model change needs no `/new`); and both
  flags must precede the `resume` subcommand or the CLI rejects `--sandbox`.
  One real defect found in **shipped** client code: `Main.newt:432` takes the
  **first** `*` in a frame as the checksum delimiter, so a `TEXT` payload
  containing one is silently truncated on screen — `/sessions` first rendered
  as a bare `3.`. The wire format allows `*` and the host parses it correctly,
  so the fix is a host-side rule: no reply may contain `*` (marker is now `>`,
  session names are stripped). A3 has the same code, so this matters for
  hardware. 76 tests (60 at baseline + 16). Round record
  `runtime/evidence/f4round-round.txt`, screens `runtime/evidence/f4round-*.png`.
  Still open: `/model` cannot list what codex would default to (it reports
  `codex default` rather than reading `config.toml`), and the A7 transcript
  clips long replies with no scroll — a client-side matter for a future round.

- **2026-08-03 — publishing prep: the repo is ready to go public as "Egg
  Freckles".** Three things changed, none of them functional. (1) `README.md`
  is now a public front door — what works, an architecture diagram, an honest
  emulator-first "Try it", credits — and its old operational content moved
  verbatim to **`docs/dev-harness.md`** (ports, security boundary, emulator
  control API, package builds). The three docs that cited `README.md` by line
  number were repointed: `docs/install-lifeline-plan.md` and the two in this
  file. (2) **Apple-copyrighted material is no longer tracked.** All 11 files
  under `refs/` and the 9 NIE/NewtonIM archives under `downloads/` were
  `git rm --cached`'d (kept on disk) and are now fetched by
  **`refs/fetch-refs.sh`** and **`downloads/fetch-downloads.sh`**, in the style
  of `scripts/fetch-recovery-packages.sh`. Every URL was verified the same day:
  all 14 fetched files returned HTTP 200 from `unna.org` and hashed
  **byte-identical** to the copies this repo was developed against. Two derived
  layers also reproduce exactly — `refs/nie11/` is extracted from
  `NIEDVLPR.EXE`'s nested `DATA` zip with stdlib `python3` (no p7zip), and the
  `.txt` files are **regenerated with `pdftotext`, not downloaded**, because
  dozens of docs cite them by line number; poppler 26.07.0 reproduces all three
  byte-for-byte, and `refs/SHA256SUMS` is the check that a different poppler
  would fail loudly. `downloads/unixnpi-1.1.3.tar.gz` stays tracked: it is GPL
  C source, redistributable, 21 KB. New `refs/README.md`, `downloads/README.md`,
  and a `.gitignore` block keep the untracked binaries out of `git status`.
  `docs/START-HERE.md`'s dev loop now opens with the fetch step, because agents
  grep `refs/` constantly and a fresh clone has an empty one. (3) `LICENSE` —
  MIT, © 2026 jbfly, with a clause naming what it does *not* cover. A privacy
  sweep found nothing needing removal; the only private-infrastructure detail
  is `docs/next-hardware-session.md:74`'s `ssh jbfly@10.13.13.12` /
  `192.168.1.242`, RFC1918 addresses with no credentials, in an
  already-SUPERSEDED doc. 76 tests pass (the count includes another session's
  in-flight Track F4 work in `server.py`/`test_server.py`; nothing here touches
  either). Internal names are unchanged — Egg Freckles is the public name, the
  package identities and directory names stay as they are.

- **2026-08-03 — Track F2 done: the harness panel is one app.**
  `HarnessClientA7:jbfly` ("Chat A7", v2.4-a7) is Chat A4 plus a second control
  row — **`Ask Note`**, **`Save Note`**, **`Ink`** — and a hideable ink overlay.
  Two plain buttons rather than a toggle: `Ask Note` sends the newest stock note
  as the prompt **through the normal chat path**, so a long note splits into
  `MSGP` parts and the `No answer: LENGTH` failure is dead; `Save Note` writes
  the last reply (chat *or* ink) back as a native note with the proven
  `MakeTextNote` + `NewNote` two-step. `examples/note-export` and
  `examples/ink-capture` are deleted — their code lives in the client now.
  Proven live on isolated instance `f2round` against `NEWTON_FAKE_BACKEND=1
  server.py:6801` + `pkg_publisher.py:18081`: a 266-character note →
  `MSGP part 1/2 220B` + `2/2 46B` → `assembled 2 parts into 266B prompt` →
  reply in the transcript; `Save Note` → status `Saved note id=8` matching an
  independent `ns_eval` read of the soup; a short typed prompt right after
  logged **no** `MSGP` at all. **The E2/E3 encoder blocker is fixed**: `Encode`
  no longer adds the canvas origin to points `GetPointsArray` already hands back
  global, and the host render of an "L" drawn at screen `60,110→60,280→220,280`
  measures **x 60..221, y 110..281** instead of the old +16,+54 shift; the real
  vision call answered *"An L-shaped right angle."* and that line lands in the
  chat transcript. 60 tests. Full record `runtime/evidence/f2round-round.txt`,
  screens `runtime/evidence/f2round-*.png`.
  Three defects found in code three docs called proven, each costing one
  rebuild: (1) **`cursor:ResetToEnd()` lands *on* the last entry and returns
  it**, so note-export's `ResetToEnd(); Prev()` read the **second** newest note
  (measured: `reset=3 entry=3`, `Prev()` → 2) — a real bug in shipped
  `NoteExportN13`; (2) dropping the chat's NIE link to re-grab one for the ink
  POST fails `connect` with **-16009**, so the ink endpoint now rides the link
  the chat already holds; (3) a slot named `inkOpen` shadowed the method
  `InkOpen` (**-48200**), the `transcriptTail` trap again. Also: `vfFrameBlack`
  draws no frame without a pen width, and `scripts/newton-round.sh` now honours
  `NEWTON_INSTANCE` so a round can run off the shared emulator.
  Still open: hardware is **still on A3**, and F3 (a true Notes panel that grabs
  the *currently open* note) is untouched.

- **2026-08-03 — Track G done: an agent built a Newton app end to end, first
  build.** G1 is `docs/agent-dev-loop.md` — ten numbered steps from
  `cp -r examples/hello` to teardown, with the identity rule, the `tntk` patch
  caveat, the raw `/packages/` install path and a footgun table. G2 proved it:
  one `codex exec` run (host, MCP `newton`, `approve` mode) was told to build
  **NewtonDice** (`Dice1:jbfly`, a floating window whose **Roll** button shows a
  random 1–6) into a new `examples/dice` on isolated instance `gloop`. It read
  the runbook, then ran the loop in **six MCP calls with no failures and no
  intervention**: `build_pkg` (compiled first try) → `emulator_install
  /packages/dice/dice.pkg` → `emulator_newtonscript
  GetRoot().|Dice1:jbfly|:Open()` → `emulator_screen` (window + `Roll` button)
  → `emulator_tap(220,218)` → `emulator_screen` (`-` had become `1`). This is
  also the first time any `emulator_*` tool has been driven by an agent rather
  than by tests, which closes one of the two gaps the previous "Next up" named.
  Independently re-verified with six more `curl` taps: `1 3 2 3 3 1`. Evidence
  `runtime/evidence/gloop-codex-transcript.txt`, `gloop-02-codex-launched.png`,
  `gloop-03-codex-after-tap.png`, `gloop-verify-rolls.txt`,
  `gloop-verify-roll1..6.png`; the app is committed as `examples/dice`. One new
  finding: **a `protoFloatNGo` does not render at its declared `viewBounds` x**
  (declared `left: 60`, rendered `x=112`, right edge 8 px inside the screen)
  while its y matched exactly — so tap coordinates come off a screenshot, never
  off the source (`docs/newton-dev-notes.md` Track G round). G2's optional
  hardware half (install `Dice1` on the MP2000 via ZC40 after a `store_info`
  check) was **not** done — it needs the human, and it is the same gate as E2.
  55 tests, measured in a detached worktree holding HEAD plus exactly this
  track's files: the shared working tree showed 53 passed / 2 failed at the
  time, both from another session's in-flight Chat **A5** edit to
  `examples/harness-client` (Track F2), not from Track G.

- **2026-08-03 — Track F1 done (proven on the emulator).** The 240-byte
  single-frame prompt cap is lifted. New client → host op
  `:SS MSGP KK NN <chunk>*HH` (two-digit part/total, 220-character chunks,
  8 KiB assembled cap) documented as an extension in `docs/phase3-protocol.md`;
  `MSG` and every other op are byte-for-byte unchanged and an old client keeps
  working. `Chat A4` (`HarnessClientA4:jbfly`, v2.4-a4) splits anything over
  227 characters and sends the parts stop-and-wait on the existing ACK
  machinery. Live on isolated instance `f1round`: a 378-character typed prompt
  → `MSGP part 1/2 220B` + `part 2/2 158B` → `assembled 2 parts into 378B
  prompt` → 453-character reply rendered on the Newton
  (`runtime/evidence/f1round-round.txt`, `f1round-12-reply.png`); a short
  prompt straight after it logged no `MSGP` at all. 55 tests.
  The round also found a **pre-existing A3 bug**: `StrPos(text, Chr(13), 0)`
  raises `-48802` on this ROM, so the transcript froze the moment it passed 640
  characters. Fixed with a hand-rolled `FindBreak`; see
  `docs/newton-dev-notes.md` Track F1 round and the footgun table in
  `docs/newton-networking-lessons.md` §2. The note bridge still sends a single
  `MSG` — moving it onto `MSGP` is part of F2.

- **2026-08-03 — Track A done.** A3/A5 `3ca0b94` (spikes deleted, old staged
  loaders untracked; true test count was 40 not the documented 30 — now 37);
  A4/A6 `923ae43` (untracked debris archived to
  `~/newton-archive/newton-harness/` — 9 flash snapshots + 100 logs; patch
  audit found **all 9 patches applied**, nothing to archive); A1/A2/A7
  `46565a1` (superseded banner, ink claims fixed, `examples/README.md`);
  A8 `65caa6f` (`drag`/`install`/`newtonscript` CLI subcommands, README
  endpoint table).
- **2026-08-03 — Track B done.** `2786479`: `docs/install-paths.md` (the one
  blessed install story) + `make stage-hw PKG=<dir>` (dry-run verified with
  `examples/hello`).
- **Open decisions resolved 2026-08-03:** superseded sources deleted (git
  history retains); archive location is `~/newton-archive/newton-harness/`;
  Track D stays codex + MCP.
- **2026-08-03 — Track C1–C3 done (proven over the wire).** The `POST /tools`
  acceptance round ran on isolated instance `c2round` against
  `runtime/raw_pkg_server.py` on `10.42.0.1:18081`; the broker logged
  `Newton tools connected` and all three ops answered. Wire replies:
  `battery` → `count=0 cap=100% charge=discharging ac=no type=nimh`;
  `store_info` → `Internal total=7638048 used=883236 free=6754812 ro=n`;
  `pkg_list` → `count=39`, id 1 → `1/39 ScreenBuffer|428|?`, id 39 →
  `39/39 PT100:Scrawl|174416|Internal`, id 99 → HTTP 422
  `package ordinal must be 1..39`. **~0.8 s per device-touching op** on the warm
  link (`ping` 0.05 s). Full `curl -i` transcripts in
  `runtime/evidence/toolsround-r10m-wire-*.txt`, Extras drawer in
  `runtime/evidence/toolsround-r10m-wire-screen.png`.
  The round found one real defect that `ns_eval` could not have found:
  **`StringToNumber` returns a `Real` on this ROM**, and indexing an array with
  a `Real` throws `evt.ex.fr.type;type.ref.frame`, so `R10M`'s `pkg_list` failed
  on *every* valid ordinal over the wire
  (`runtime/evidence/toolsround-r10m-wire-pkg-list-1-r10m-bug.txt`). Fixed by a
  one-line `Floor` at the dispatch site and shipped as
  **`HarnessToolsR10N:jbfly`**; details in `docs/newtonscript-eval.md`
  fourteenth finding. Also learned: seeding a fresh instance's
  `/state/internal.flash` from a saved NIE-configured flash replaces the whole
  tour + `newtdev`/`NE2K` + Internet Setup dance and takes ~90 s
  (`docs/parallel-emulators.md`, "Seed an instance from a saved flash"); and
  `GetPackages()` ordering is not stable across a reboot.
- **2026-08-03 — Track C1–C3 code round (`af6be49`, `1dd099a`) — the transport
  claim in it is superseded by the entry above.** `examples/harness-tools`
  bumped `R10L`→`R10M` and gained `battery`, `store_info`, `pkg_list` on the
  existing `StrEqual` dispatch; no host-side change was needed (generic
  `POST /tools` pass-through, C6 note below). API choices verified against
  `refs/` before coding — `BatteryLevel` is documented-obsolete,
  `BatteryStatus`/`GetStores` sizes/`GetPackages` are the real calls; details
  and citations in `docs/newtonscript-eval.md` thirteenth finding. Each op's
  expression was evaluated on isolated instance `c1round` via
  `runtime/ns_eval.py` (`runtime/evidence/toolsround-r10m-nseval.txt`), which
  proved the *system calls* but, as the wire round later showed, not the
  dispatch path. Two mechanics learned and documented: `POST /install` takes a
  raw `/packages/…` path, not a `curl -F` upload (`docs/install-paths.md`
  row 1), and a fresh `make emulator-instance-up` Newton is *not* network-ready
  — since fixed by flash seeding rather than by hand.
- **2026-08-03 — Track D1 code done** (its live demo ran the same day, see the
  D3 entry below). `newton_mcp.py` —
  one stdlib-only file, MCP over stdio (JSON-RPC 2.0, hand-rolled
  `initialize`/`ping`/`tools/list`/`tools/call`) exposing `newton_tool`,
  `emulator_screen/tap/text/key/newtonscript/install`, `build_pkg`, `stage_hw`.
  D2's rails are folded in **as code**: mutating emulator ops refuse the shared
  instance unless `NEWTON_ALLOW_SHARED=1` (screen always allowed), `newton_tool`
  refuses device-mutating op names with the human's `curl`, and there is no
  physical-install tool at all. Registered with `make server-mcp`
  (`codex mcp add newton -- python3 /app/newton_mcp.py`, writes
  `[mcp_servers.newton]` into the `codex-home` volume, same pattern as
  `make server-login`); `containers/server.Dockerfile` copies the file in;
  `server.py` unchanged. `test_newton_mcp.py` adds 8 tests (45 total).
  **Measured networking finding** (`docs/agent-tools.md`): from the server
  container `10.42.0.1:<port>` on the host **is** reachable — so `newton_tool`
  works in-container — but host `127.0.0.1` is refused, so every `emulator_*`
  tool (control ports are published on `127.0.0.1` only, and `instance_url`
  needs `podman`) plus `build_pkg`/`stage_hw` require running `server.py` on
  the host. Also observed this session: `10.42.0.1/24` **is** now on `lo`
  (`ip -4 addr show lo`), so the C1–C3 acceptance blocker is gone — that round
  has since run, see the C1–C3 entry above.
  The two unverified items in this entry were **settled by D3 below**: no, and
  no.
- **2026-08-03 — Track E1 done (visible ink).** `examples/ink-capture` is now
  `InkPad2:jbfly` v2: one `MakePolygon` retained per stroke, painted in a
  `ViewDrawScript` on the capture view, with `Dirty()` + `RefreshViews()` at
  capture / `Undo` / `Clear` and a new `Undo` button. The Stage 4 `[verify]`
  is settled in both directions — `MakePolygon` *does* take the flat array
  (`ClassOf(...)` → `'polygon`), but as **x,y** pairs while `GetPointsArray`
  returns **y,x** global coordinates, proved by
  `ShapeBounds(MakePolygon([0,0,100,10,0,20]))` → `0/0/101/21` and by a drag
  from screen `60,100` retaining `y0=100 x0=60`. No `MakeLine` loop, no manual
  binary, and the figure is not auto-closed (a hand-injected bent stroke drew
  as an open "L"). Proven on isolated instance `e1ink` (flash-seeded, no
  network, no `/ink` POST): three `/drag` strokes stayed visible after pen-up,
  `Undo` removed only the last, `Clear` wiped all — `runtime/evidence/e1ink-*`
  and `docs/ink-client-design.md` "Stage 5 result". The round also found a
  defect it did not fix: `Encode()` adds the ink view's origin to points that
  are already global, so the host's render is shifted +16,+54 — folded into
  **E2**, which stays open along with hardware install.
- **2026-08-03 — Track D3 done: the keystone demo is live.** From Chat on an
  emulated Newton (isolated instance `d3demo`, seeded flash), the typed prompt
  *"use your newton tools. what app is in front, how much free space, and how
  many packages are installed."* came back on the Newton's own screen 19
  seconds later as **"Front app: Notepad (paperroll) / Free space: 6,758,976
  bytes (6.45 MiB) / Installed packages: 39"**. Three `newton_tool` calls ran
  inside that one turn — `front_app` 0.127 s, `store_info` 0.805 s, `pkg_list`
  0.796 s — so the model, not the Newton, is the latency. The numbers are
  device-derived: a pre-flight `curl` before `HarnessClientA3` was installed
  read `free=6778912`/`count=38`, one package fewer. Evidence:
  `runtime/evidence/d3demo-screen.png`, `…-chat-turn.txt`, `…-mcp-verify.txt`,
  `…-prompt-typed.png`; page is `docs/agent-tools.md`, now flipped to
  live-proven. **Both `[verify]` items are settled and one was a real
  blocker:** (1) `codex exec` does **not** auto-approve MCP tool calls — the
  call fails with `user cancelled MCP tool call` until the server entry carries
  `default_tools_approval_mode = "approve"` (valid values `auto`/`prompt`/
  `writes`/`approve`; `codex mcp add` has no flag for it, so `make server-mcp`
  now writes it and the host registration has it by hand); (2) the MCP
  subprocess is **not** inside `--sandbox read-only` — `build_pkg` wrote a real
  `.pkg` under that flag, so no `--add-dir` is needed *and* the sandbox is not
  a rail for this surface, only `newton_mcp.py`'s own D2 rails are.
  `server.py` ran on the **host** per the container-networking finding, and
  `HarnessClientA3` needed no rebuild — its hardcoded `10.42.0.1:6801` reaches
  a host process on the `lo` alias just like the tools long-poll. Two
  operational notes: the tools client and the chat client coexist on one Newton
  but the tools client's reconnect throws a cosmetic modal `Communications`
  slip over the chat window mid-turn; and `xdotool` typing drops the first
  characters and mangles shifted keys, so tap, wait, then type in chunks.
- **2026-08-03 — Track C4 done (proven over the wire).** `HarnessToolsR10P:jbfly`
  adds `note_list` and hardens `get_note`; the acceptance round ran on isolated
  instance `c4round` (seeded flash) against `runtime/raw_pkg_server.py` on
  `10.42.0.1:18081`, broker logged `Newton tools connected 10.42.0.1:57652`.
  Wire replies: `note_list` → `count=6`, id 1 → `1/6 (untitled)|64461125`,
  id 4 → `4/6 C4 alpha note about batteries|64477198`, id 6 →
  `6/6 C4 charlie note that is delibera...|64477198`, id 7 and id 99 → HTTP 422
  `note ordinal must be 1..6`; `get_note` id 6 → the whole 89-character note,
  id 1 → `""`; `ping` and `battery` unchanged. ~0.8 s per device-touching op
  (`ping` 0.127 s). Evidence `runtime/evidence/c4round-*.txt` (summary in
  `c4round-wire-summary.txt`, ROM probes in `c4round-nseval.txt`, the three
  notes rendered in stock Notepad in `c4round-screen.png`). Three things
  learned, all in `docs/newtonscript-eval.md` fifteenth finding:
  **`cursor:CountEntries()` works on this ROM** and walks the index rather than
  the entries, so counting does not reintroduce the twelfth finding's
  starvation; **a nil `title` is the normal case** for a Notepad entry, so the
  listing label falls back to the note's first 32 characters; and **`ns_eval`
  cannot see NTK platform constants** such as `ROM_paperRollSoupName` — they are
  compile-time symbols, so probing with one throws
  `evt.ex.fr.intrp;type.ref.frame` and you must use the literal (`"Notes"`).
  Also confirmed: the three Notepad entries inside the seed flash are the
  `data=nil` failed writes `docs/notes-bridge.md` diagnosed in N2/N3.
- **Next up (2026-08-03, after G):** the remaining work splits cleanly.
  **Needs the human and the bench:** E2 (the ink client on hardware — its
  doubled `Encode()` origin is **fixed and wire-proven** as of F2, so only the
  hardware half is left), and every other hardware deploy — Chat A7, the tools
  client, `Dice1` — since the whole tools channel has still never run on the
  **physical** MessagePad and there is no tool that installs there by design.
  **Agent-sized and unblocked:** C5 (`pkg_install`/`pkg_remove` ops, still
  human-gated at the device), E3 (multi-part `/ink` POST), F3 (true Notes
  integration, genuinely unexplored), then the Track H backlog. `stage_hw` is the one MCP tool no
  agent has driven yet; G exercised all six `emulator_*` calls it needed.

**The vision, in one paragraph.** The Newton runs a small harness panel that
can send the current note — text *or* ink — to an agent and get replies back
as notes. The agent has tools to manage the device: see status and battery,
list/read/write notes, check free space, install and remove packages. The
same agent can design a new Newton app, build it with the host toolchain,
test it in an isolated Einstein instance (screenshots, taps, ns_eval), and —
behind a human gate — install it on the physical MP2000, then iterate:
delete the old version, install the new one. Modern LLMs paper over the
Newton's weak handwriting recognition by reading ink directly. Long term:
lower-level development (games, richer UIs) on the same rails.

## Where we are (2026-08-03, all claims audited against source)

Hardware-proven and current:

- **Chat**: `examples/harness-client` (`HarnessClientA7:jbfly`, "Chat A7"; the
  physical MP2000 still runs A3) ↔ `server.py:6801`, framed ASCII protocol,
  codex backend via `codex exec` subprocess. One turn in flight; since Track F1
  a prompt over 227 characters goes as `MSGP` parts and the host reassembles up
  to 8 KiB. Since Track F2 it is the **harness panel**: `Ask Note` sends the
  newest note down that same path, `Save Note` writes a reply back as a native
  note, and `Ink` opens the capture canvas whose reading joins the transcript
  (`POST /ink` on 18081). Emulator-proven.
- **Install path**: `examples/harness-loader` (`-HarnessLoaderZC40:jbfly`) pulls
  any staged `.pkg` over WiFi from `runtime/dual_send.py` on 18081. ZC39 is the
  installed fallback. NS Basic bootstrap (`bootstrap/`) is the bare-metal
  lifeline; Newt's Cape and Dock TCP are preserved in `downloads/recovery/`.
- **Backup/inventory**: `runtime/newton_backup.py` speaks real Dock protocol
  (DES auth, NSOF); produced `docs/installed-package-inventory.md`.

Emulator-proven, **not yet on hardware**:

- **Tools channel**: `examples/harness-tools` (`HarnessToolsR10P`) long-polls
  `pkg_publisher.py`'s `ToolBroker` on 18081; emulator-proven ops are `ping`,
  `front_app`, `get_note`, `note_list`, `note_probe`, `battery`, `store_info`,
  `pkg_list` — the last three travelled the real link on 2026-08-03
  (`runtime/evidence/toolsround-r10m-wire-*.txt`, `docs/newtonscript-eval.md`
  thirteenth finding) and `note_list` + `get_note` v2 the same day
  (`runtime/evidence/c4round-*.txt`, fifteenth finding). Host API:
  `POST /tools` (`pkg_publisher.py:354-385`).
  Median 0.3–0.8 s per call on the warm link.
- **Ink**: built end to end and now **inside the chat client** (Track F2; the
  separate `examples/ink-capture` is deleted). The canvas captures strokes with
  `GetPointsArray`, retains one `MakePolygon` per stroke in a `ViewDrawScript`
  (Stage 5), encodes NSI1 and POSTs `/ink`; the host renders a PNG (stdlib
  Bresenham, `pkg_publisher.py:241-278`) and calls a vision model whose one
  sentence lands in the chat transcript. Six staged results in
  `docs/ink-client-design.md`; the `Encode()` doubled-origin defect is **fixed
  and measured on the wire** ("Track F2 result").
- **Notes**: also inside the chat client (`examples/note-export` deleted).
  `Ask Note` reads the newest note and sends it as an ordinary prompt — no
  `/note` request — and `Save Note` creates a native note via the proven
  two-step `MakeTextNote(answer, nil)` + `NewNote` path.

The critical architectural gap was: **the agent has no tools.** `/tools`,
`/ink`, the emulator control API, and the build toolchain all existed as
separate host surfaces that a *human* curled, and nothing let the agent behind
the chat session call them. **Closed 2026-08-03** by Track D: `newton_mcp.py`
exposes them as MCP tools (`docs/agent-tools.md`), and on 2026-08-03 a prompt
typed into Chat on an emulated Newton drove three of them and answered with the
device's own numbers (D3 entry above). Track G then closed the other half: on
the same day an agent drove `build_pkg`, `emulator_install`,
`emulator_newtonscript`, `emulator_screen` and `emulator_tap` to build a new
app and show it running (G2 entry above). What is left is breadth, not shape —
`stage_hw` has still only been run by tests, and none of it has run against the
physical MessagePad.

## Track A — repo cleanup and doc truth (first; one cheap-agent session)

Goal: an agent landing in this repo finds only current things, and no doc
tells it to do something destructive.

- **A1. Neutralize the dangerous doc.** `docs/next-hardware-session.md` is a
  complete pre-ZC40 session plan; its Step 5 (`:359-377`) instructs deleting
  every loader except `ZC34 Loader 2.0` — six generations behind current.
  The 2026-08-02 hardware session it plans for already happened. Add a
  `> **SUPERSEDED 2026-08-02**` banner at the top pointing to
  `docs/installed-package-inventory.md` and `docs/hardware-bench-runbook.md`.
  Do not delete the doc; its NIE/AP appendices are still cited.
- **A2. Fix the stale ink claim.** `docs/START-HERE.md:44` says ink is
  "Entirely unbuilt". Reality: stages 1–4 verified, results appended to
  `docs/ink-client-design.md`. Update the table row and the doc's own header.
  Per `CLAUDE.md`, grep for other copies of the claim.
- **A3. Delete superseded spike code** (git history keeps everything):
  `examples/harness-tools-persistent/` + `runtime/persistent_tools_server.py`
  + `test_persistent_tools_server.py` (self-described "Disposable" spike,
  wrong port, blocking I/O — `runtime/persistent_tools_server.py:2`), and
  `examples/network-probe/` (early diagnostic; deleting source does not
  affect the copy still installed on the device). Update
  `docs/START-HERE.md:83`'s note about silently-skipped tests.
- **A4. Sweep untracked round debris** (all gitignored, zero git risk):
  seven throwaway listeners in `runtime/` (`round5/6/7_*listener*.py`,
  `sniff18081.py` — keep `raw_pkg_server.py`, it's cited by six docs), stale
  `*.pid` files, `runtime/ns-eval-image-build.log`, `runtime/logs/` round
  debris. Move `runtime/backups/internal-before-round*.flash` (15 × 8 MB,
  rounds 3–9, superseded by `runtime/emulators/mp2000-core-20260803/`) to
  `~/newton-archive/` rather than deleting — they are backups.
- **A5. Untrack superseded staged builds**: `runtime/staging/hardware/`
  ZC37/ZC38 loaders and `harness-client-a1.pkg`. ZC39 stays (documented live
  fallback), ZC40 and A3 stay.
- **A6. Audit `containers/patches/`**: the five `einstein-tcp-*`/
  `einstein-nie-rom-trace` diagnostic patches date from the closed rounds 3–8
  TCP investigation. Check `containers/emulator.Dockerfile` for which patches
  are actually applied; move unapplied ones to `containers/patches/archive/`
  with a README line each.
  **Audited 2026-08-03: all 9 patches, including all five suspected-unapplied
  diagnostic ones, are applied by `containers/emulator.Dockerfile`'s single
  `RUN` block (`git apply` calls at lines 37–44); `git blame` shows they were
  added during the TCP investigation (`8b471e0`, `2ddc8cc`, `6680ef1`) and
  never removed. Nothing archived; `containers/patches/` is unchanged.**
- **A7. Add `examples/README.md`** — a 10-line table: package, identity,
  status (current / smoke-test / seed-for-Track-X), where it runs. This is
  the cheap alternative to renaming `examples/` (renaming would break dozens
  of doc references and the `compose.yaml:41` mount for no functional gain).
- **A8. Fix README drift**: endpoint table (then in `README.md`, now
  `docs/dev-harness.md`, "Agent screen and input control") omits
  `/drag`, `/install`, `/newtonscript`; add the missing `emulator.client`
  subcommands note or (5 lines) add `drag`/`install`/`newtonscript`
  subcommands to `emulator/client.py`.

Acceptance: `uv run --with pytest pytest -q` still passes (count drops by the
3 deleted spike tests); `grep -ri "ZC34 Loader"` finds only the banner-ed doc
and history; `make newton-packages` unaffected.

## Track B — one blessed install story (one cheap-agent session)

Today three host listeners can serve packages (`pkg_publisher.py`,
`runtime/raw_pkg_server.py`, `runtime/dual_send.py`) and the knowledge of
which to use lives in five docs. Streamline by documentation and one target,
not by rewriting servers:

- **B1.** Write `docs/install-paths.md` — one page, one table:
  | Situation | Path | Command |
  with exactly three rows: (1) emulator → `scripts/newton-round.sh` /
  `POST /install`; (2) physical, normal → `dual_send.py` on 18081 + ZC40
  loader taps; (3) physical, bare-metal recovery → NS Basic bootstrap →
  Newt's Cape / Dock TCP (pointers into `docs/install-lifeline-plan.md`).
  State plainly: `dual_send.py` is *the* 18081 listener
  (`docs/newton-networking-lessons.md` §4.9); `raw_pkg_server.py` is
  historical; `pkg_publisher.py`'s pkg-serving is for the tools/ink/note
  channel, not the loader.
- **B2.** Add `make stage-hw PKG=<dir>`: build + copy to
  `runtime/staging/hardware/` + refresh SHA256SUMS + print the exact
  filename to type into ZC40. (The typing cost on the device is the human
  interface; keep filenames short — `docs/install-lifeline-plan.md:170-180`.)
- **B3.** Fold the `dual-send` systemd user unit instructions
  (`runtime/dual-send.service`, currently documented only inside the
  superseded `next-hardware-session.md:96-106`) into `install-paths.md`.

## Track C — tools channel v2: device management ops (2–3 sessions)

Grow `examples/harness-tools` (R10P lineage) into the device-management
surface the agent needs. Fixed-op dispatch stays (arbitrary eval is a proven
dead end — `docs/newtonscript-eval.md`; four investigations reverted). New
ops, each one session-sized with its emulator acceptance test:

- **C1. `battery` — done 2026-08-03**, proven over the wire in `R10N`.
- **C2. `store_info` — done 2026-08-03**, proven over the wire in `R10N`.
- **C3. `pkg_list` — done 2026-08-03**, proven over the wire in `R10N`. Note
  its `size` is uncompressed bytes, so it does *not* match the Dock counts in
  `docs/installed-package-inventory.md`.
- **C4. `note_list` / `get_note` v2 — done 2026-08-03**, proven over the wire
  in `R10P`. `note_list` is paged exactly like `pkg_list` (`count=N`, then one
  `i/N <label>|<timeStamp>` line per request, ordinals capped at 64) and counts
  with `cursor:CountEntries()`, which walks the index rather than the entries.
  `get_note` keeps its reply shape and gains the nil-guard + `Floor` at its
  dispatch site. Details in `docs/newtonscript-eval.md` fifteenth finding.
- **C5. `pkg_install <name>` / `pkg_remove <name>`** — reuse ZC40's proven
  VBO receive + `SuckPackageFromBinary` code inside the tools client;
  removal API `[verify]`. **Human gate on physical hardware, always**
  (`docs/notes-bridge.md:16`).
- **C6. Rehost ToolBroker — deferred, no longer a prerequisite.** Two facts
  found 2026-08-03: (1) the host `POST /tools` route is a **generic
  pass-through** — any op name matching `TOOL_OP` is forwarded and the
  Newton client answers `unknown_op` for names it lacks
  (`pkg_publisher.py:354-386`), so C1–C5 need *only* Newton-side changes
  (plus host arg validation if a new op takes args beyond `id`); (2) the
  tools long-poll and package serving **share port 18081 by design** (the
  `POLL` hijack, `pkg_publisher.py:284-292`), so splitting them means either
  a new port (client rebuild + identity bump) or a pointless rename. Revisit
  only if the file becomes genuinely hard to work in.

Constraint carried from the wire: keep every op's reply ASCII and small;
the 3 s host heartbeat and >3 s client watchdog relationship is load-bearing
(`docs/newton-networking-lessons.md` §2 footgun table).

## Track D — give the agent the tools (the keystone; 2–3 sessions)

Make the agent behind chat able to *act*. Recommended shape: a small **MCP
server** (stdlib-thin, one file) exposing:

- `newton_tool(op, args)` → `POST /tools` on 18081 (physical or emulator);
- `emulator_*` → the `emulator/control.py` HTTP API (screen, tap, drag,
  text, key, install, newtonscript) against a *named instance*, never the
  shared `newton-harness_emulator_1` without explicit opt-in;
- `build_pkg(dir)` → `make`/`tntk` build returning the staged path;
- `stage_hw(pkg)` → Track B's staging (install itself stays human-gated).

`codex exec` supports MCP servers via its config, so `server.py`'s backend
gains these without changing the chat wire protocol. If the backend ever
switches to Claude, the same MCP server plugs in. Steps:

- **D1. Done 2026-08-03.** `newton_mcp.py` written and registered
  (`make server-mcp`, or `codex mcp add newton` on the host);
  `docs/agent-tools.md` is the page. Its acceptance — a chat turn from the
  Newton client whose answer comes from `front_app` — passed as part of D3.
- **D2. Done 2026-08-03, in code.** Rails live in `newton_mcp.py`, not in a
  prompt: device-mutating `newton_tool` ops return "needs human confirmation"
  with the exact command; the shared emulator refuses mutating ops without
  `NEWTON_ALLOW_SHARED=1` while `emulator_screen` stays open; no
  physical-install tool exists in the surface at all. Tested in
  `test_newton_mcp.py`.
- **D3. Done 2026-08-03 — gate passed.** From Chat on the emulated Newton, one
  prompt drove `front_app`, `store_info` (C2) and `pkg_list` (C3) and answered
  `Free space: 6,758,976 bytes (6.45 MiB)` / `Installed packages: 39` on the
  device's own screen. Status log entry above; `docs/agent-tools.md` "The live
  demo (D3)"; `runtime/evidence/d3demo-*`.

## Track E — finish ink and the HWR-assist loop (2 sessions)

- **E1. Visible ink — DONE 2026-08-03.** `InkPad2:jbfly` retains one
  `MakePolygon` per stroke and paints them in a `ViewDrawScript`, and gained
  the `Undo` button. `MakePolygon` takes the flat array but as **x,y** pairs,
  so `GetPointsArray`'s y,x order is swapped and the ink view's origin
  subtracted; no per-segment `MakeLine`. See `docs/ink-client-design.md`
  "Stage 5 result" and `runtime/evidence/e1ink-*`.
- **E2. Install the ink client on hardware** via the Track B path; first real
  stylus drawing → vision model round trip. **Half done 2026-08-03**: the
  `Encode()` doubled origin is fixed and proven over the wire in Track F2 (host
  render of an "L" drawn at `60,110→60,280→220,280` measures x 60..221,
  y 110..281), and the ink client is now the chat client, so the hardware step
  is one ZC40 install of `HarnessClientA7` — which is the same human gate as
  every other hardware deploy.
- **E3. HWR assist.** New flow: send a note's *ink* to the agent, get clean
  text back as a new note. Needs the multi-part `/ink` POST that was
  designed and deferred (`pkg_publisher.py:313` caps at 16 KiB; `?part=k&of=n`
  reassembly is specified in `docs/ink-client-design.md` but unwritten).

## Track F — the harness panel (Chat A4/A7; 2–3 sessions)

Evolve the chat client toward the panel-over-Notes dream, incrementally:

- **F1. Multi-frame prompts — DONE 2026-08-03.** `MSGP KK NN <chunk>` shipped
  in `Chat A4`; grammar and host state machine in `docs/phase3-protocol.md`,
  "Extension: `MSGP`"; status log entry above. The note bridge was folded onto
  it by F2, so `No answer: LENGTH` is gone. Everything since A3 is
  emulator-proven only — the physical MP2000 still runs A3.
- **F2. The harness panel — DONE 2026-08-03**, shipped as `Chat A7`
  (`HarnessClientA7:jbfly`, v2.4-a7) rather than A5: three identity bumps were
  spent inside the round, one per defect found (see the status log). `Ask Note`
  + `Save Note` + an `Ink` overlay, all in one app; the note path rides the
  normal chat `MSG`/`MSGP` transport instead of `POST /note`; the ink encoder's
  doubled origin is fixed. `examples/note-export` and `examples/ink-capture` are
  deleted, per the Track A rationale. Status log entry above; round record
  `runtime/evidence/f2round-round.txt`.
- **F3. True Notes integration** (later): a floating `protoFloatNGo` panel
  or a Notes auxButton that grabs the *currently open* note rather than the
  newest. API surface `[verify]` — this is genuinely unexplored.
- **F4. Claude-Code-style session and model control — DONE 2026-08-03.**
  `/help`, `/status`, `/model`, `/effort`, `/sessions`, `/new [name]`,
  `/resume <n|name>`, answered in `server.py` **before** the backend runs, as
  ordinary `TEXT` frames. No client change, no wire change — so it works from
  hardware **Chat A3 unchanged**, from emulator Chat A7, and from the PT100
  terminal path. Model and effort are per session and reach codex as `-m` /
  `-c model_reasoning_effort=`, placed before the `resume` subcommand; state
  lives in a `sessions.json` registry that absorbs the old single
  `session.json` as session 1. Bare `/new` keeps its exact pre-F4 reply
  because A7's New button sends it. Page: `docs/chat-commands.md`; status log
  entry above; round record `runtime/evidence/f4round-round.txt`.

## Track G — agent-driven app development loop (after D; 2 sessions)

The "ask for an app, watch it appear" loop. All the parts exist; this track
is glue + a runbook:

- **G1. Done 2026-08-03.** `docs/agent-dev-loop.md` — ten numbered steps:
  scaffold from `examples/hello`, fresh identity (`-10402` rule), build with
  `build_pkg` (`tntk` + vendored patch — without it every rebuild silently
  regresses to version 1), isolated + flash-seeded emulator, install with the
  raw `/packages/` path, launch, screenshot, tap, iterate, tear down. It also
  records that `scripts/newton-round.sh` does **not** fit a new app on an
  isolated instance (it drives the shared container and needs a `kVersion` tag
  the scaffold lacks), so a new app bumps its identity by hand.
- **G2. Done 2026-08-03 — gate passed.** codex built `Dice1:jbfly`
  ("NewtonDice") into `examples/dice` on isolated instance `gloop` in six MCP
  calls with no intervention and no failed build, and the screenshots show the
  app working. Status log entry above; `docs/agent-dev-loop.md`
  "Proven 2026-08-03"; `runtime/evidence/gloop-*`.
  **Still open:** the hardware half — the human installing it on the MP2000 via
  ZC40 after a `store_info` free-space check. `stage_hw` makes that one command
  away, but the install itself is gated (`docs/agent-tools.md` rail 3).

## Track H — backlog (not scheduled)

- Lower-level development: NCT/C++ toolchain research for games and custom
  drawing — a survey session against `refs/` and UNNA before committing.
- Serial Dock lifeline proof (one bench afternoon —
  `docs/install-lifeline-plan.md` §4).
- Portable networking (PLAN.md phase 5).
- Backend abstraction (Claude alongside codex) — only if/when wanted; the
  MCP design in Track D already keeps this cheap.
- Reboot-persistent host services (`dual-send` unit exists; server/emulator
  units don't — `docs/dev-harness.md`, "Verification status").

## Track I — image generation on the Newton (designed 2026-08-03, not started)

Requested by the human 2026-08-03; also the original `PLAN.md` phase 4 item
("image gen, Newton-optimized dithered grayscale, 320x480 portrait"). Ask for
an image in chat, get a Newton-friendly version back — as a bitmap on screen,
or ideally as a native note.

- **I1. Host pipeline.** Prompt → image API (the codex CLI does vision *in*,
  not generation *out* — pick and wire an image-generation backend; the
  OpenAI images API off the same account is the obvious candidate, decision
  open) → downscale to 320×480 portrait → grayscale → dither. Use Atkinson
  dithering (the period-correct Apple algorithm) to the MP2000's 4-bit
  (16-level) panel; 1-bit fallback. Pure-stdlib PNG handling already exists
  (`pkg_publisher.py` writes PNGs with zlib/struct); reading/dithering can
  stay stdlib the same way.
- **I2. Bitmap delivery.** Do NOT push 76 KB through the 240-byte chat
  frames (~350 frames). Reuse the proven bulk path: the client fetches bytes
  over HTTP from 18081 into a VBO, exactly like the ZC40 loader pulls
  packages (proven to 512 KB). Chat flow: `/image <prompt>` (server-side
  command like F4's) → reply `TEXT image ready: <name>` → client (A8+) adds
  a viewer that GETs the payload and draws it. `[verify]` the NewtonScript
  bitmap APIs against `refs/` before coding: candidate path is a raw
  bitmap frame for `DrawShape` (`MakeBitmap`/`SetPixel` family — names
  unverified; grep the Ref before believing any of them).
- **I3. Vector-into-a-note (the ideal).** Notes' sketch stationery stores
  strokes natively, and Track E proved stroke geometry round-trips
  (`GetPointsArray`, `MakePolygon`, the x,y/y,x swap — sixteenth-finding
  territory). Invert it: host converts the generated image to polylines
  (edge-trace, or ask the model for SVG and flatten paths to polylines),
  ships them over `/tools` or the bulk HTTP path, and the client writes a
  **sketch note** the Newton renders natively and the human can edit with
  the stylus. `[verify]` how sketch-note entries store strokes
  (`viewStationery` and slot shape — probe with `note_probe`/ns_eval on a
  hand-drawn sketch note first; nobody has looked yet). Cap complexity
  (points per note) — the twelfth-finding event-loop lessons apply to soup
  writes too.
- Sizing: I1 one session (host-only, testable without a Newton); I2 one
  session (client round); I3 one to two (probe round, then write round).

## Track J — web interface for the modern side (designed 2026-08-03, not started)

Requested by the human 2026-08-03: see all Newton notes in a modern browser
(phone or desktop), browse device data, installed packages, battery — the
Newton's data made useful in the modern age.

- **J1. Sync layer first, UI second.** The web view must not depend on the
  Newton being awake. A host sync job walks `note_list`/`get_note` (and
  `pkg_list`/`store_info`/`battery`) over the proven `/tools` channel and
  writes a local store — plain JSON files or sqlite under a new
  `state/sync/` (decision open; JSON matches the repo's stdlib habit). Each
  sync is incremental and respects the wire lessons (paged ordinals, ~0.8 s
  per call — a 40-note sync is ~35 s, fine for a background job). The Dock
  backup path (`runtime/newton_backup.py`) stays the deep-backup tool; this
  is the light continuous one.
- **J2. Web server.** One stdlib `http.server` file (the repo pattern),
  serving: notes list + note view (rendered text; later sketch-note strokes
  as inline SVG — the same geometry knowledge from Track E/I3), package
  inventory, store/battery status, and a "sync now" button that fires the
  tools calls live when the Newton is connected. Bind LAN, not localhost,
  so a phone can reach it; NO auth beyond the isolated-subnet assumption at
  first — say so on the page — revisit if it ever leaves the bench network.
  New port (e.g. 8090); do not overload 18081 (the POLL hijack makes that
  server special — C6 note).
- **J3. Later**: write-back (edit a note in the browser → new note on the
  Newton via the sanctioned two-step create), and serving the ink PNGs the
  `/ink` path already renders.
- Sizing: J1 one session (host + live emulator round), J2 one session, J3
  later. J1's store is also what a future mobile/RSS/export anything would
  read — keep it dumb and documented.

## Sequencing

A → B → (C6, D1) → C1–C3 → D2–D3 → E1–E2 → F1 → F2 → G → C5/E3/F3 → H.
A and B are pure cheap-agent work. C/D/E/F Newton-side code is where the
NewtonScript footguns live — sessions doing those must read
`docs/newton-networking-lessons.md` §2 and `docs/phase3-chat-round.md`
"What cost the most time" first (this is already the START-HERE rule).

## Decisions still open for the human

1. **Delete vs keep superseded example sources** (Track A3): recommended
   delete — git history retains them; nothing on-device depends on host
   sources.
2. **`~/newton-archive/` location** for the 120 MB of old emulator flash
   snapshots (Track A4): recommended over deletion; confirm the path.
3. **Track D backend**: recommended to stay on codex + MCP now; say the word
   if you want Claude wired in as an alternate backend while D1 is being
   built, since it changes the config work slightly.
