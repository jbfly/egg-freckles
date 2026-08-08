# START HERE — orientation for a new agent session

Read this first. It is the only doc that tries to tell you *where the truth is*.

## What this project is

An agentic AI harness for a 1997 Apple Newton MessagePad 2000 running NewtonOS
2.1 — "Claude Code for the Newton". A host server (`server.py`, port 6801)
speaks a framed ASCII protocol to a native NewtonScript client app that the
human runs on real hardware or in the Einstein emulator. The Newton side is a
fixed-operation tool client, not a code-eval target: arbitrary
`Compile(string)` does not work on this ROM.

## Read-first order

Four docs matter. Read them in this order and stop. (If you are here to pick
*what to work on next*, also read **`docs/ROADMAP.md`** — the 2026-08-03
track plan that succeeds `PLAN.md`.)

1. **This file.**
2. **`docs/newton-networking-lessons.md`** — the distilled, evidence-carrying
   summary of everything the networking arc taught. Authoritative for: how to
   call `protoBasicEndpoint`, NIE behaviour, error-code meanings, and the
   footgun table in §2. Its §4 explicitly overrides parts of
   `docs/phase3-client-plan.md`. If you are about to write Newton networking
   code, §2 alone will save you a day.
3. **`docs/phase3-chat-round.md`** — what the working chat client actually is,
   as of 2026-07-26. Authoritative for: current client behaviour, the
   NewtonScript string/view traps in "What cost the most time", and the real
   package-replacement sequence.
4. **`docs/newton-dev-notes.md`** (652 lines, chronological) — the raw
   round-by-round log. Do not read front to back. `grep` it for your symptom;
   every round records its evidence files. Authoritative for: what was tried
   and what the screen actually showed.

Everything else is reference you open only when the task lands on it:

| Doc | Open it when |
|---|---|
| `docs/phase3-protocol.md` | You touch the wire format. **Read-only** — see constraints. |
| `docs/chat-commands.md` | You touch `server.py`'s slash commands (`/model`, `/effort`, `/sessions`, `/resume`), the sessions registry, or how the codex backend is invoked. Records what this host's codex accepts (model names, effort levels, whether `resume` honours them) and the one rule the client imposes: **no `*` in a reply**. |
| `docs/newtonscript-eval.md` | You work on the `POST /tools` fixed-op channel or `ns_eval`. |
| `docs/install-lifeline-plan.md` | Anything about recovering a bare-metal Newton. |
| `docs/hardware-bench-runbook.md` | You are about to touch the real MessagePad. |
| `docs/einstein-automation.md` | You need Einstein internals, serial ports, or the control socket. |
| `docs/newton-client-notes.md` | Package build/toolchain overrides. |
| `docs/host-setup.md` | You are setting up the package toolchain (cDCL + `tntk` + platform files) on a **new host** from nothing. The from-zero recipe; verified reproducible byte-for-byte across two hosts 2026-08-04. |
| `docs/agent-tools.md` | You touch `newton_mcp.py` — the MCP server that gives the chat agent tools (ROADMAP Track D). Also the place the container→host networking limits are measured. |
| `docs/agent-dev-loop.md` | You are building a **new** Newton app. Ten numbered steps from `cp -r examples/hello` to teardown, with the identity rule and the UI footguns. An agent ran it end to end on 2026-08-03 (ROADMAP Track G, "Proven 2026-08-03"). |
| `docs/install-paths.md` | You are about to get a `.pkg` onto a Newton, real or emulated. |
| `docs/dev-harness.md` | You need the containers, ports, security boundary, or the full emulator control API. This was the old `README.md`; the README is now the public front door. |
| `docs/ink-client-design.md` | Ink. Built and emulator-proven end to end; results appended after the design, and **read "A9 result" first — it is the current state**. Track A9 deleted the capture canvas (it dropped all but the first stroke) and moved capture into stock Notes: one **Ask** button reads the newest note's strokes out of the soup and POSTs them, with the page's text on an optional `NSI1` `H` line. Earlier sections ("Stage 5 result", "Track F2 result") describe the canvas that no longer exists. EF12 is the final hardening of the reviewed EF10/EF11 path: per-image stroke/point budgets, zero-stroke Notes routes, per-part watchdogs, and body/part backstops; see `docs/ef10-ink-pagination.md` (EF9 fixed-height history: `docs/ef9-ink-pagination.md`). Still open: physical-hardware validation. See `docs/ROADMAP.md` Tracks E, F and A9. |
| `docs/notes-integration-design.md` | You touch "Send to AI", the entry in the **stock Notes envelope menu** (ROADMAP Track L2). **For current radio ownership read `docs/chat-ui-and-radio-lifecycle-plan.md` §B and `docs/newton-client-notes.md`; EF14 supersedes EF6's always-on poll.** The human used it on the MP2000 on 2026-08-04 and it filed the wrong note: `EggFrecklesEF5:jbfly` fixes that (the reply entry is held, not searched for) and adds the egg icon to Extras and to the menu item. The "Build result" section above it settles every `[verify]` in the design but its §3 filing is superseded. EF6 historically gave that agent an always-on `/tools` poll; EF14 now starts it only for an active send and closes it after idle. Evidence `runtime/evidence/effix-*`, `l2build-*` and `ef6round-*`; findings twenty, twenty-two to twenty-seven in `docs/newtonscript-eval.md`. Neither fix is on hardware. |
| `docs/notes-bridge.md`, `docs/client-network-port.md`, `docs/unna-survey.md` | Narrow topics named by their titles. |

## Ground truth vs plans — read this before trusting any doc

**Verified-findings docs.** Claims carry evidence (a `file:line`, a commit sha,
an evidence file under `runtime/evidence/`, or quoted screen text). Trust them:

- `docs/newton-networking-lessons.md`
- `docs/newton-dev-notes.md`
- `docs/phase3-chat-round.md`
- `docs/newtonscript-eval.md`

**Plans.** Written before the work; parts are already overtaken by it. Do not
treat as current state:

- `PLAN.md` — the phase roadmap. Its "Current checkpoint" ages fastest.
- `docs/phase3-client-plan.md` — largely **superseded** by
  `docs/phase3-chat-round.md`; the client it plans has shipped. Its §3
  transport recommendations are corrected by
  `docs/newton-networking-lessons.md` §4.1–4.9.
- `docs/install-lifeline-plan.md` — proposal.
- `docs/ink-client-design.md` — mostly a proposal document, but its Stage
  1–5 result sections (everything after the "Reuse map" table) are verified
  findings, not plan; trust those the same as the four docs above.

When the two classes disagree, the verified doc wins, and **fixing the stale
one is part of your task** (see `CLAUDE.md`).

## The dev loop

Every command below was executed in this repo on 2026-07-31 and produced the
stated result. Run from the repo root.

**Setup, once per clone — fetch `refs/`.** The Apple manuals and Q&A notes are
not tracked (they are Apple copyright); a fresh clone has an empty `refs/`.
Almost every doc in this repo backs a claim with a line citation into
`refs/*.txt`, and you will `grep refs/` constantly, so do this first or you are
guessing at the API:

```sh
./refs/fetch-refs.sh                    # ~14 MB from unna.org, checksum-verified
./downloads/fetch-downloads.sh          # NIE distributions; only for network work
```

`refs/fetch-refs.sh` regenerates the `.txt` extractions with `pdftotext` rather
than downloading them, and `refs/SHA256SUMS` is what proves your poppler
numbers the lines the same way the citations assume. Details in
`refs/README.md`.

**Tests** — 128 pass (2026-08-08), of which **28** are client-source tests
pinning the `MSGP` split, the Track A9 Ask routing and its two ink converters,
the Track L1 `EntryUniqueID` ordering rule and merged tools channel, the `NSI1`
`H` line, the Track A8 transcript row window and the Track L2 "Send to AI" hook
(the `InstallScript` route, the closure-free `RouteScript`, the AI-folder reply
— which since EF5 pins that the reply entry is *held*, never searched for — the
drawn icon, and that nothing ever calls `RemoveSlot`); 16 of the rest cover the Track
F4 slash commands and the session registry. `pytest` is not in
the system python, so use `uv`:

```sh
uv run --with pytest pytest -q          # 128 passed
```

`make test` now runs the same command. Before 2026-07-31 it ran only
`test_server.py` and `test_emulator_control.py` under `unittest` (18 tests),
silently skipping `test_pkg_publisher.py` — if you are on an older checkout,
do not trust it. (`test_persistent_tools_server.py` and the spike it tested
were deleted in Track A3 2026-08-03; see `docs/ROADMAP.md` Track A3.)

**Build packages** — builds on the host with `~/newton-dev/prefix/bin/tntk`,
no container needed:

```sh
make newton-packages                    # writes runtime/staging/*.pkg + SHA256SUMS
```

`tntk` needs the patch vendored at `tools/tntk-project-version.patch`; without
it every rebuild silently regresses to package version 1
(`docs/phase3-chat-round.md`, "Risk"). Setting up `~/newton-dev` on a host
that does not have it yet (cDCL, `tntk` with its two vendored patches, the
NTK platform files) is `docs/host-setup.md`, the from-zero recipe — verified
reproducible: a second host built from that page alone produced
byte-identical `.pkg` output to this one.

**Emulator** — it is normally already running and shared. Check before
starting anything:

```sh
podman ps --format '{{.Names}} {{.Status}}'
curl -fsS http://127.0.0.1:18080/health
```

`newton-harness_emulator_1` is the shared instance. `/health` reports
`"newton_screen":{"width":320,"height":480,...}` — this is the live proof of
the portrait orientation. `make emulator-up` only if nothing is running.

**Screen and input:**

```sh
python3 -m emulator.client status
python3 -m emulator.client screen /tmp/newton.png   # 320x480 4-bit grayscale PNG
python3 -m emulator.client tap 160 240
python3 -m emulator.client text "hello"
```

**Evaluate NewtonScript** — one line, result printed to stdout. The default
`--container` is a scratch emulator that usually does not exist, so pass the
container explicitly:

```sh
runtime/ns_eval.py --container newton-harness_emulator_1 '2+2'   # -> 4
```

**A full install round:** `scripts/newton-round.sh examples/harness-loader r16a`
bumps identities, builds, installs, launches, and screenshots. Use it rather
than hand-rolling the sequence.

## Hard constraints — do not violate these

- **The human types every character on a 1997 touchscreen.** Minimise
  Newton-side typing in anything you design. Typing cost is a real decision
  metric, tabulated at `docs/install-lifeline-plan.md:170-180`.
- **Real hardware needs an explicit human confirmation gate**, and destructive
  operations doubly so (`docs/notes-bridge.md:16`). The emulator is free; a
  hard reset on the MessagePad is a disaster (`docs/install-lifeline-plan.md`).
- **Never reuse a package identity.** The precise rule is in
  `docs/phase3-chat-round.md`, "Package identity — the actual rule": bumping
  the version does *not* permit replacement (`-10402`), and one-argument
  `GetPkgRef` fails silently. Use `scripts/newton-round.sh`, which bumps
  identity for you.
- **Do not change the wire format in `docs/phase3-protocol.md`.** It is
  implemented on both sides and pinned by tests. Extend around it.
- **No sudo on alpha.** Host network/AP changes are prepared for the human to
  apply, never applied by an agent.
- **Worktrees go OUTSIDE the repo directory.** A worktree inside it makes
  pytest collect duplicate test files and the suite breaks.
- **The emulator is shared.** Other sessions are using it. Never stop,
  rebuild, or reconfigure `newton-harness_emulator_1` without asking.

## Current state — 2026-08-02 (ages fastest; verify before trusting)

Working: the framed native client end to end. A1 proved the asynchronous
transport in Einstein and completed a real Codex turn on the physical MP2000.
Fresh identity `HarnessClientA3:jbfly` is current; it keeps that transport and
adds a four-line handwriting field, compact controls, a distinct **Chat A3**
Extras label, and visible host errors. ZC40 physically installed A3 on
2026-08-02, all 19,266 HTTP bytes were acknowledged, and the larger prompt was
confirmed substantially easier to use. Preserve A1 as the installed fallback.

As of 2026-08-07 the *source* client is `EggFrecklesEF21:jbfly` — user-visible
name **"Egg Freckles"**, title "Egg Freckles 1.0-ef21", package version 33, and
since EF5 it has an Extras icon of its own: a little egg with freckles, the same
one that now sits beside "Send to AI" in the Notes menu. It
supersedes `HarnessClientA9:jbfly` ("Chat A9", v2.4-a9), and it is the
**harness panel**, not just a chat window:

- it is now the *only* client package. Track L1 folded the fixed-op tools client
  into it: `examples/harness-tools/` is deleted and its POLL transport and all
  eight ops live in `examples/harness-client/Main.newt` under `Tool*` names
  (`ToolStart`, `ToolPoll`, `ToolDispatch`, `ToolStop`). There is nothing
  separate for the human to install. **Since EF6 that channel is owned by the
  package-level Notes agent, started only by an active chat/ink send**. It stays
  up through that reply, then the five-second idle callback stops every endpoint;
  unsolicited host tools while the Newton is idle are deliberately unavailable
  (radio lifecycle plan §B, EF14);
- it splits a prompt over 227 characters into `MSGP` frames that the host
  reassembles (ROADMAP Track F1, `docs/phase3-protocol.md` "Extension: `MSGP`");
- it puts **"Send to AI" into the stock Notes Action (envelope) menu** (Track
  L2), which is the interesting one: choosing it routes *the page whose envelope
  you tapped* — text, drawing or both — and files the answer as a new note in an
  "AI" folder. No newest-note heuristic, and it works with the Egg Freckles
  window closed, because the hook is installed from the part frame's
  `InstallScript` and re-installed on every reset. `docs/notes-integration-design.md`
  "Build result" is the current state; it supersedes **Ask** eventually, but
  **Ask stays until the human has used it on hardware**;
- one **Ask** button sends the newest stock note *whatever kind it is* — text
  down that same chat path, drawings as `NSI1` strokes to `POST /ink`, a mixed
  page as one request carrying both — and `Save Note` writes a reply back as a
  native note (Tracks F2 and A9; this replaced `examples/note-export`, deleted);
- **the ink capture canvas is gone** (Track A9). Draw in stock Notes with its
  real drawing tools; the client reads the strokes out of the soup. The canvas
  dropped all but the first stroke when drawing freely, and it was deleted
  rather than fixed;
- **the transcript scrolls** (Track A8): it is wrapped onto a 12-row grid and
  the **Up**/**Dn** buttons page that window over the whole 6 KiB ring. A7 fed
  the pane 640 characters, which is far more rows than it can draw, so long
  replies ran off the bottom unreachably — the blocker the first hardware test
  found.

Everything after A7 is emulator-proven only — **the physical MP2000 runs A7**
(A3 before the 2026-08-03 hardware session), so hardware docs and inventories
that say A7 are correct.

Human gates and preserved recovery state:

- **The NS Basic REPLACE DEMO bootstrap is preserved.** All 27 lines in
  `bootstrap/nsbasic-bootstrap.bas` were checked against device photos; the
  saved target is Mars at `10.42.0.1:18081`. Keep it as the bare recovery path.
- **Newt's Cape is preserved and physically installed.** The pinned 296,128-byte
  freeware/unexpiring package is checksum-addressed in `downloads/recovery/`
  and installed/launched in Einstein. ZC40 installed it on the physical MP2000
  on 2026-08-02; ZC40 is what runs on the device. ZC39 was the unchanged
  fallback until the user deleted it from the physical device at the bench
  (reported 2026-08-04) — ZC40 is now the fallback. **In source the loader is
  now `-Loader1:jbfly`, Extras label plain "Loader"** (2026-08-04, ROADMAP
  Track L4) — bigger filename field, an on-screen-keyboard button,
  emulator-proven only. Install it using ZC40, prove one real install with it;
  keep ZC40 installed as the deep fallback afterward (it is not deleted).
- **The physical Extras and Storage state is photographed and transcribed.**
  See `docs/physical-newton-inventory.md`. It confirms Chat A3, NewtScape,
  ZC39, ZC40, NIE, `Internet Setups`, and `DEMO.BAS:NSBASIC` as of the
  2026-08-02 photos; ZC39 has since been deleted from the device by the user
  (reported 2026-08-04). Dock TCP was not visible and Dock had no TCP/IP
  choice.
- **Dock TCP 1.2 is preserved and ready for ZC40.** The byte-identical upstream
  data fork appears in Newton Research NCX 1.4, 2.3, and 3.0.2. Its 72,432-byte
  recovery copy and checksum are in `downloads/recovery/`; it adds the missing
  TCP/IP choice to Dock after NIE is working.
- **The serial Dock lifeline is unproven.** It needs one afternoon of hardware
  time and a photograph of the working cable chain
  (`docs/install-lifeline-plan.md`, §4).
- **The `tntk` patch is uncommitted upstream.** Vendored here as
  `tools/tntk-project-version.patch`, but `~/newton-dev/tntk` still builds from
  a dirty working tree.

Known-unverified items are listed honestly in
`docs/newton-networking-lessons.md` §3. Read that before claiming anything in
it is settled.
