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

**Tests** — **139 pass for the prepared M2 state** (verified 2026-08-09;
`runtime/evidence/m2-ef23-integration/full-tests.txt`). Historical master
milestone `2fbbd4b` passes 136; M2 adds three client-source tests. Of the M2 total,
**31** are client-source tests
pinning the `MSGP` split, the Track A9 Ask routing and its two ink converters,
the Track L1 `EntryUniqueID` ordering rule and merged tools channel, the `NSI1`
`H` line, the Track A8 transcript row window and the Track L2 "Send to AI" hook
(the `InstallScript` route, the closure-free `RouteScript`, the AI-folder reply
— which since EF5 pins that the reply entry is *held*, never searched for — the
drawn icon, and that nothing ever calls `RemoveSlot`); 16 of the rest cover the Track
F4 slash commands and the session registry. `pytest` is not in
the system python, so use `uv`:

```sh
uv run --with pytest pytest -q          # 139 passed with M2
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

## Current state — updated 2026-08-11 (ages fastest; verify before trusting)

**2026-08-09 — read `docs/ROADMAP.md` "Recovery plan (2026-08-09)" before
starting anything.** The M2 recovery milestone is
`3b2be4f5c44aafde7d981352a9d87105a6c4c721`; it atomically landed M2's final
EF23 client on the recovery server/tooling base and passes 139 tests. M3's
emulator gate is now evidenced through the actual EF23 client: one fresh
source/build/install/launch completed in 234 seconds with no byte-identical
retry or timeout, and a genuine screenshot shows the 3×3 board/status
(`runtime/evidence/m3-tic-tac-toe-20260809/`). Generated source/package prove
the title and identity; the screenshot does not. Runtime taps produced no pixel
change, so playability is source-supported and the MP2000 game remains
human-gated. Do **not** rebase or modify preserved
`prepare/ef22-autofind`, rejected-history `task/m2-ef22-integration`, or the M2
landing branches. The old `HarnessClientP3C` stash is preserved as branch
`archive/p3c-chat-wip-stash`.

Historical (2026-08-02): the framed native client worked end to end. A1 proved
the asynchronous transport in Einstein and completed a real Codex turn on the
physical MP2000. `HarnessClientA3:jbfly` kept that transport and
added a four-line handwriting field, compact controls, a distinct **Chat A3**
Extras label, and visible host errors. ZC40 physically installed A3 on
2026-08-02, all 19,266 HTTP bytes were acknowledged, and the larger prompt was
confirmed substantially easier to use. Preserve A1 as the installed fallback.
(The physical MP2000 ran **A7** from the 2026-08-03 bench session; its last
evidenced install is **EF13**, 2026-08-07 — see "Current state" below.)

Historical milestone `4c834a9` carries `EggFrecklesEF23:jbfly`; parent commit
`629f20e` prepared `EggFrecklesEF24:jbfly` — user-visible name **"Egg
Freckles"**, title "Egg Freckles 1.0-ef24", package version 38. M2 had changed
only the primary chat connect `reqTimeout` from 45,000 ms to 10,000 ms; EF24
restores it to 45,000 ms while leaving the 12-second post-connect handshake
watchdog and 10-second marker-output timeout unchanged. Two normalized builds
are byte-identical at 114,704 bytes, SHA-256
`5147937cd38086aa2b5ac258630f7f51f03e04d246d41fe3c440cd8a735981ba`; 140
tests and a disposable isolated-emulator handshake pass are recorded in
`runtime/evidence/ef24-chat-timeout/`.

The first physical EF24 iPad run did **not** prove the handshake. Mars was
confirmed at the pinned address with its listener active. On one `/status`
Send, with no retry, the operator directly observed `Connecting to server...
will send` followed by `Connect error -16013`; no photo was taken, no
HS-A/HS-B/HS-C status appeared, and no reply arrived. The 90-second pcap ended
before the Send and contains zero packets, so it is only a disclosed timing
miss. The sanitized authoritative Mars journal records seven accepted
connections from 16:41:36Z through 16:41:55Z at three-second intervals and
no harness protocol observed by the service. Because the pcap missed the Send
and the journal records lifecycle rather than payload, EF24 has no transmitted
byte-count evidence. Compared with EF23's earlier `Connect error
-16005`, timeout restoration changed the visible result to `-16013` but did not
advance the handshake. Evidence:
`runtime/evidence/ef24-ipad-physical-20260811/README.md:9-38` and
`runtime/evidence/ef24-ipad-physical-20260811/mars-journal-summary.txt:7-14`.

EF25 is the smallest diagnostic response to that failure, directly atop
historical EF24 result commit `25c2cc56`: only the primary chat connect is synchronous with
`async: nil, reqTimeout: 10000`, followed immediately by `:Connected()` after
a successful return. It uses fresh `EggFrecklesEF25:jbfly`, title **Egg
Freckles 1.0-ef25**, and package version 39. The hypothesis is that iOS NIE is
failing in the async connect completion path; this build does **not** prove
that hypothesis. Two normalized 114,480-byte builds are byte-identical at
SHA-256 `edf439e9a7bf6ec8051fcc1fb03d24ae5bae8368acb3c54655b78092190b3a0e`;
83 focused and 140 full tests pass. One seeded disposable Einstein accepted
exactly one connection and completed marker, HELLO, ACK, `STAT READY`, client
ACK, and teardown. Its screenshots did not preserve the transient painted
HS-A/B/C states, so the exact evidence is source order plus the marker/HELLO
wire path, not a visual claim. Evidence:
`runtime/evidence/ef25-sync-connect/README.md`. iOS remains unverified.

The physical EF25 iPad diagnostic is recorded and closes the EF2x
client-parameter series. On one `/status` Send with no retry, the operator
observed `Connecting to active server; will send...` then `Connect exception`;
no HS-A/HS-B/HS-C status or reply appeared. The covering capture contains 15
packets and no drops recorded; because the pcapng has no drop counter, that is
not a measured zero. Three TCP handshakes completed, the service sent one
48-byte greeting on each connection, and the client acknowledged each greeting
but sent no TCP payload. EF25's synchronous `connect` raised before
`:Connected()` and before any marker or `HELLO`. EF23/EF24/EF25 therefore did
not advance the harness handshake under the tested client parameter changes.
The series is closed and parked as an external Einstein-platform issue, not a
proven iOS-specific failure. If resumed, use the stock Einstein network path
with the **same seeded flash** as the successful isolated EF25 gate, retaining
only build/automation patches. Evidence:
`runtime/evidence/ef25-ipad-physical-20260811/`; the raw pcapng is not
committed.

EF24 otherwise retains EF23's no-Dock package tools, native arrows, persisted
Advanced server picker, minimized HS-A/HS-B/HS-C probe, and transient `STAT
PROGRESS` painting. EF23's separate, completed M4 record remains in
`runtime/evidence/m4-ipad-ef23-20260809/` and `docs/ef22-server-autofind.md`.
Since EF5 it has an Extras icon of its own: a little egg with freckles, the same
one that now sits beside "Send to AI" in the Notes menu. It
supersedes `HarnessClientA9:jbfly` ("Chat A9", v2.4-a9), and it is the
**harness panel**, not just a chat window:

- it is now the *only* client package. Track L1 folded the fixed-op tools client
  into it: `examples/harness-tools/` is deleted and its POLL transport and fixed operations live in
  `examples/harness-client/Main.newt` under `Tool*` names
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
  the ROM **up/down scroll arrows** page that window over the whole 6 KiB ring. A7 fed
  the pane 640 characters, which is far more rows than it can draw, so long
  replies ran off the bottom unreachably — the blocker the first hardware test
  found.

The physical MP2000's client has been upgraded repeatedly since A7
(2026-08-03): EF4/EF5 in the 2026-08-04 bench tests, and the **last evidenced
hardware install is EF13** — "HARDWARE PASS — EF13 proven on the physical
Newton", all 6 ink parts streamed, `docs/ef13-memory-diagnosis.md` (commit
39aa963, 2026-08-07). **EF21 has no hardware install record**: every EF21
evidence artifact is from emulator instance `ef21arrows`, and
`docs/ef21-native-scroll.md` explicitly leaves the MP2000 install human-gated
— the merge subject "hardware-confirmed" (d12dfff) overclaims. Hardware docs
and inventories that say A7 describe the 2026-08-02/03 state only.

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
