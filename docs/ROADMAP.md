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
- **Next up:** Track C1–C3 (Newton-side ops; see revised C6 note — no host
  refactor needed first), then D1.

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

- **Tools channel**: `examples/harness-tools` (`HarnessToolsR10L`) long-polls
  `pkg_publisher.py`'s `ToolBroker` on 18081; ops today are `ping`,
  `front_app`, `get_note`, `note_probe`. Host API: `POST /tools`
  (`pkg_publisher.py:354-385`). Median 0.3–0.8 s per call on the warm link.
- **Ink**: contrary to `docs/START-HERE.md`'s stale claim, this is built
  end-to-end: `examples/ink-capture` (`InkPad`) captures strokes with
  `GetPointsArray`, encodes NSI1, POSTs to `/ink`; host renders a PNG
  (stdlib Bresenham, `pkg_publisher.py:241-278`) and calls a vision model.
  Four staged results appended to `docs/ink-client-design.md:224-408`.
  One known defect: ink is invisible on the canvas after pen-up
  (`ink-client-design.md:380-401`).
- **Notes**: `examples/note-export` (`NoteExportN13`) reads the newest note,
  POSTs `/note`, and creates a native reply note via the proven two-step
  `MakeTextNote(answer, nil)` + `NewNote` path.

The critical architectural gap: **the agent has no tools.** `server.py` only
relays chat. `/tools`, `/ink`, the emulator control API, and the build
toolchain all exist as separate host surfaces that a *human* curls. Nothing
lets the agent behind the chat session call them. Closing that gap is Track D
and it is the heart of this roadmap.

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

Grow `examples/harness-tools` (R10L lineage) into the device-management
surface the agent needs. Fixed-op dispatch stays (arbitrary eval is a proven
dead end — `docs/newtonscript-eval.md`; four investigations reverted). New
ops, each one session-sized with its emulator acceptance test:

- **C1. `battery`** — level/charging state. API names need `[verify]`
  against `refs/NewtonProgrammerRef20.txt` first (repo convention).
- **C2. `store_info`** — per-store total/used/free bytes. This is the
  free-space gate for agent-driven installs.
- **C3. `pkg_list`** — installed package names + sizes (compare against
  `docs/installed-package-inventory.md` format).
- **C4. `note_list` / `get_note` v2** — titles + ids, then fetch by id;
  respect the 1..64 ordinal lesson (event-loop starvation on big soups,
  `docs/newtonscript-eval.md` twelfth finding) by paging.
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

- **D1.** Write `newton_mcp.py` + register in the codex config used by
  `containers/server.Dockerfile`; prove with a chat turn from the emulator
  client: "what app is front on the newton?" → agent calls `front_app` →
  answers in chat.
- **D2.** Add the safety rails in the MCP layer, not in prompts: physical
  device = read-only ops allowed, mutating ops return "needs human
  confirmation" with the exact command for the human; emulator instances =
  unrestricted except the shared instance.
- **D3.** End-to-end demo gate: from Chat on the emulated Newton, ask the
  agent to check free space (C2) and report installed packages (C3).

## Track E — finish ink and the HWR-assist loop (2 sessions)

- **E1. Visible ink.** The one named defect: strokes vanish at pen-up.
  Retain per-stroke shapes and paint them in `ViewDrawScript`; the open
  `[verify]` is whether `MakePolygon` takes the flat Y/X array or needs
  per-segment lines (`docs/ink-client-design.md:380-401`). Verify against
  `refs/` first, then emulator (`/drag` draws test strokes; Stage 1 already
  drew a 94-point stroke that way).
- **E2. Install InkPad on hardware** via Track B path; first real stylus
  drawing → vision model round trip.
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
