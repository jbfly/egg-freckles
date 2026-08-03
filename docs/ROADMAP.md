# ROADMAP — from a working chat app to "Claude Code for the Newton"

Written 2026-08-03 after a full-repo audit. This is the successor to `PLAN.md`
(phases 0–3 there are shipped; this doc picks up at its phase 4). Point new
sessions here; each track below is sized so a single session of a cheaper
agent can complete one task and verify it.

## Status log (update this section as tracks complete)

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
- **Next up:** E2, then F1, F2, G per Sequencing. Two things still open: none
  of the `emulator_*` tools or `stage_hw` has been driven by an agent yet (only
  by tests), and the whole tools channel has still never run on the **physical**
  MessagePad. (`newton_mcp.py`'s `newton_tool` forwards `op` generically, so
  `note_list` is callable from a chat turn already; only its listed-ops
  description needed updating.)

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

- **Chat**: `examples/harness-client` (`HarnessClientA3:jbfly`, "Chat A3") ↔
  `server.py:6801`, framed ASCII protocol, codex backend via
  `codex exec` subprocess (`server.py:227-260`). Text only, 240-byte prompt
  cap, one turn in flight.
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
- **Ink**: contrary to `docs/START-HERE.md`'s stale claim, this is built
  end-to-end: `examples/ink-capture` (`InkPad`) captures strokes with
  `GetPointsArray`, encodes NSI1, POSTs to `/ink`; host renders a PNG
  (stdlib Bresenham, `pkg_publisher.py:241-278`) and calls a vision model.
  Five staged results appended to `docs/ink-client-design.md`. The pen-up
  defect is fixed (Stage 5, `InkPad2`): retained polygons painted in a
  `ViewDrawScript`, plus an `Undo` button. Newly found and still open:
  `Encode()` double-counts the ink view's origin, so the host render is
  shifted +16,+54 (Stage 5 section, "The one trap").
- **Notes**: `examples/note-export` (`NoteExportN13`) reads the newest note,
  POSTs `/note`, and creates a native reply note via the proven two-step
  `MakeTextNote(answer, nil)` + `NewNote` path.

The critical architectural gap was: **the agent has no tools.** `/tools`,
`/ink`, the emulator control API, and the build toolchain all existed as
separate host surfaces that a *human* curled, and nothing let the agent behind
the chat session call them. **Closed 2026-08-03** by Track D: `newton_mcp.py`
exposes them as MCP tools (`docs/agent-tools.md`), and on 2026-08-03 a prompt
typed into Chat on an emulated Newton drove three of them and answered with the
device's own numbers (D3 entry above). What is left is breadth, not shape — the
`emulator_*` tools and `stage_hw` have not been driven by an agent yet, and
none of it has run against the physical MessagePad.

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
- **A8. Fix README drift**: endpoint table (`README.md:143-151`) omits
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
- **E2. Install InkPad2 on hardware** via Track B path; first real stylus
  drawing → vision model round trip. Fix `Encode()`'s doubled origin (found
  in E1) as part of this, since it needs the wire to prove.
- **E3. HWR assist.** New flow: send a note's *ink* to the agent, get clean
  text back as a new note. Needs the multi-part `/ink` POST that was
  designed and deferred (`pkg_publisher.py:313` caps at 16 KiB; `?part=k&of=n`
  reassembly is specified in `docs/ink-client-design.md` but unwritten).

## Track F — the harness panel (Chat A4/A5; 2–3 sessions)

Evolve the chat client toward the panel-over-Notes dream, incrementally:

- **F1. Multi-frame prompts.** Today a prompt must fit one 240-byte frame —
  this is what visibly breaks the note bridge (`No answer: LENGTH`,
  `docs/notes-bridge.md:246-256`). The wire format in
  `docs/phase3-protocol.md` is pinned but extensible: add a *new* op (e.g.
  `MSGP k/n <chunk>`) rather than touching `MSG`. Server reassembles;
  old clients unaffected. Update protocol doc + tests both sides.
- **F2. Chat A4 = A3 + "Note" button** (fold in `note-export`'s read/create
  code: send newest note as the prompt, replies can land as a native note)
  **+ "Ink" button** (fold in `ink-capture`'s canvas as an overlay view).
  One app, one identity bump via `scripts/newton-round.sh`. This retires
  `note-export` and `ink-capture` as separate packages (delete their dirs
  when A4 ships, per Track A rationale).
- **F3. True Notes integration** (later): a floating `protoFloatNGo` panel
  or a Notes auxButton that grabs the *currently open* note rather than the
  newest. API surface `[verify]` — this is genuinely unexplored.

## Track G — agent-driven app development loop (after D; 2 sessions)

The "ask for an app, watch it appear" loop. All the parts exist; this track
is glue + a runbook:

- **G1.** `docs/agent-dev-loop.md` — the recipe an agent follows: scaffold
  from `examples/hello`, build (`tntk` + vendored patch — without it every
  rebuild silently regresses to version 1), spin an isolated emulator
  (`make emulator-instance-up NAME=...`, `docs/parallel-emulators.md`),
  install via `POST /install`, launch, screenshot-verify, iterate. Identity
  bumping via `scripts/newton-round.sh` is mandatory (`-10402` replacement
  rule, `docs/phase3-chat-round.md`).
- **G2.** Prove it: one session where the agent (with Track D tools) builds
  a trivial new app end-to-end in an isolated instance and shows a
  screenshot, then the human installs it on hardware via ZC40 after a C2
  free-space check.

## Track H — backlog (not scheduled)

- Lower-level development: NCT/C++ toolchain research for games and custom
  drawing — a survey session against `refs/` and UNNA before committing.
- Serial Dock lifeline proof (one bench afternoon —
  `docs/install-lifeline-plan.md` §4).
- Portable networking (PLAN.md phase 5).
- Backend abstraction (Claude alongside codex) — only if/when wanted; the
  MCP design in Track D already keeps this cheap.
- Reboot-persistent host services (`dual-send` unit exists; server/emulator
  units don't — `README.md:176-180`).

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
