# The agent dev loop — build a Newton app end to end

ROADMAP Track G1. This is the recipe an **agent** follows to take a Newton app
from nothing to running-on-screen, using only the MCP tools in
`docs/agent-tools.md` plus ordinary file edits. Every step below has been run;
the round that proved the whole sequence is at the bottom ("Proven
2026-08-03").

Nothing here touches the physical MessagePad. The loop ends at a screenshot of
the app running in an isolated Einstein instance; getting it onto hardware is a
separate, human-gated path (`docs/install-paths.md` row 2, step 9 below).

## The loop

1. **Create and build the confined project first** (steps 3-5 below), then
   **boot a fresh isolated emulator.** Never the shared
   `newton-harness_emulator_1`. Building first avoids spending emulator time on
   compiler retries. The MCP tool creates disposable state, waits at most 90
   seconds for health, and dismisses the first-run Welcome UI:

   ```json
   emulator_boot {"instance": "<yourname>"}
   ```

   No flash seed is needed for authoring. If any later emulator call reports a
   crash or unreachable control service, call `emulator_boot` again, then
   reinstall, relaunch, and screenshot. The tool recreates only that named
   isolated instance.

2. **Use bounded autonomous retries.** One authoring turn is capped at 300
   seconds; builds and emulator subprocesses are capped at 60 seconds, emulator
   health at 90 seconds, and control/install/screenshot calls at 60 seconds or
   less. A tool error is not a handoff to the
   human. Retry each stage at most five times. For a compiler error, read the
   exact tntk diagnostic, replace the complete source, and rebuild. Do not reply
   until the package builds, installs, launches, and a screenshot visibly shows
   the app. After five failures, return the stage, attempt count, and last exact
   error.

3. **Create a confined workspace project.** Do not copy into or edit
   `examples/`; it remains the read-only toolchain/reference tree. The
   `create_project` tool copies the trusted `examples/hello` scaffold into one
   direct child of `runtime/agent-workspace/`, renames the `.nprj` and Makefile
   targets, and writes the identity/title/version consistently:

   ```json
   create_project {"project": "<name>-r1", "identity": "<Name>R1:jbfly", "title": "<Title>", "version": "0.1-r1"}
   ```

4. **Generate the complete NewtonScript source.** Call `write_source`; it can
   replace only that project's `Main.newt` and refuses path/symlink escapes:

   ```json
   write_source {"project": "<name>-r1", "source": "<complete Main.newt>"}
   ```

   Keep `kAppSymbol` identical to the fresh identity passed to
   `create_project`. Never reuse an installed identity: NewtonOS answers
   `-10402 Package already exists`, and one-argument `GetPkgRef` cleanup fails
   silently (`docs/phase3-chat-round.md`, "Package identity — the actual
   rule").

5. **Build with the host toolchain.** `build_pkg` accepts only the dedicated
   workspace and forces its Makefile target in a no-network bubblewrap sandbox
   where `/` is read-only and only `runtime/agent-workspace/` is writable:

   ```json
   build_pkg {"dir": "runtime/agent-workspace/<name>-r1"}
   ```

   On success it also copies the package under the same basename to
   `runtime/staging/hardware/` and returns the exact Loader filename, alongside
   the host `.pkg` and `/agent-workspace/...` emulator path. A failed build is
   not published. `tntk` must carry
   `tools/tntk-project-version.patch`; without it every rebuild silently
   regresses the package header to version 1 (`docs/START-HERE.md:95-104`).

6. **Install it into your instance.** The workspace is bind-mounted read-only
   at `/agent-workspace` in the emulator (`compose.yaml:41`), so this is a path,
   not an upload:

   ```json
   emulator_install {"pkg_path": "/agent-workspace/<name>-r1/<name>-r1.pkg", "instance": "<yourname>"}
   ```

7. **Launch it explicitly.** Installing does not open the app:

   ```json
   emulator_newtonscript {"source": "GetRoot().|<Symbol>:jbfly|:Open();", "instance": "<yourname>"}
   ```

8. **Verify with your eyes, then with a tap.** `emulator_screen {"instance":
   "<yourname>"}` returns the 320×480 screen as an image. A screenshot that
   shows the window is *installation* proof, not *behaviour* proof — drive the
   UI too: `emulator_tap` the control, then screenshot again and compare. Two
   screenshots that differ in the way the feature predicts is the gate.

   **Read the tap coordinates off the screenshot, not off `viewBounds`.** A
   `protoFloatNGo` does not necessarily land where its `viewBounds` say. In the
   G2 round the window was declared at `left: 60` and rendered at `x=112`, its
   right edge 8 px inside the screen edge — while the *vertical* numbers matched
   exactly (button declared at absolute y 200–236, rendered 198–237). Measured
   pixel scan in `runtime/evidence/gloop-verify-rolls.txt`.

9. **Iterate with a new project and identity every round.** Call
   `create_project` again with `<name>-r2` / `<Name>R2:jbfly`, then write the
   revised complete source and repeat steps 5–8. The tools deliberately do not
   let the chat agent edit `.nprj` or Makefiles in place; that keeps every write
   inside the narrow scaffold/source/build path.

10. **Tear down.** `make emulator-instance-down INSTANCE=<yourname>` deletes the
    instance's state volume, flash included — that is the point. Copy anything
    you need out first (`docs/parallel-emulators.md`, "Release it when you are
    done"). Save screenshots and transcripts under `runtime/evidence/<name>-*`
    and commit them; an artifact that exists only inside a disposable container
    is already gone.

**Hardware is a separate, human-gated step.** The agent-facing MCP surface
can neither install onto the MessagePad nor stage files outside its workspace.
A human uses the host procedure in `docs/install-paths.md` row 2 after checking
free space with `newton_tool {"op": "store_info"}`.

## Footguns that bite new Newton code

The full table is `docs/newton-networking-lessons.md` §2 — read it before
writing anything that touches the network. The ones that bite plain UI apps:

| Trap | What happens | Fix |
|---|---|---|
| A top-level `tntk` constant used inside a function body | the compiler **segfaults with no diagnostic** | put it in a view slot (`cap: kCap`, then `self.cap`) — `docs/newton-dev-notes.md`, "Five NewtonScript/tntk traps" |
| Case-insensitive symbol collision | a slot `transcriptTail` makes `:TranscriptTail()` call a number, `-48200` | never name a slot and a method the same word |
| `StrPos(text, Chr(13), 0)` | raises `-48802` on this ROM and freezes the app | scan by hand with `Ord(text[i]) = 13` (`examples/harness-client/Main.newt`, `FindBreak`) |
| `StringToNumber` | returns a **`Real`**, and indexing an array with a Real throws `evt.ex.fr.type;type.ref.frame` | `Floor()` at the point of use — `docs/newtonscript-eval.md` fourteenth finding |
| NTK platform constants in `emulator_newtonscript` / `ns_eval` | `ROM_paperRollSoupName` and friends are **compile-time** symbols; probing with one throws `evt.ex.fr.intrp;type.ref.frame` | use the literal (`"Notes"`) when probing; the constant is fine inside a package you compile — `docs/newtonscript-eval.md` fifteenth finding |
| Arbitrary `Compile(string)` | `-48808`, undefined global; there is no eval on this ROM | fixed operations only (`docs/newtonscript-eval.md`) |
| Reinstalling the same identity | `-10402 Package already exists` | step 4 |

## Workspace plumbing proven 2026-08-07

The current steps 3–8 are **emulator-proven** through direct MCP JSON-RPC calls,
not only source tests. Isolated instance `pkgproof0807b` used the known-good
EF13 proof flash rather than a blank first-run flash; after replacement it
reached healthy in 15 seconds. Its image was rebuilt from commit `a70a7dd`, and
container inspection confirmed this checkout's `runtime/agent-workspace` was
mounted at `/agent-workspace` with `rw=false`.

| # | call | result |
|---|---|---|
| 1 | `create_project` for `hello-agent-0807b`, identity `HelloAgent0807B:jbfly` | created the confined project |
| 2 | `write_source` with complete `Main.newt` | wrote 579 bytes; title `HelloAgent Plumbing Proof` |
| 3 | `build_pkg {"dir":"runtime/agent-workspace/hello-agent-0807b"}` | built 1,120-byte package and returned `/agent-workspace/hello-agent-0807b/hello-agent-0807b.pkg` |
| 4 | `emulator_install` with that returned path | `queued` |
| 5 | `emulator_newtonscript` opening `HelloAgent0807B:jbfly` | `queued` |
| 6 | `emulator_screen` | 320×480 PNG showing “HelloAgent is alive!” |

The package SHA-256 was
`4887dd0e565746cc185e89d442ca5bb6c09c9a88c70fc8a36d2cca27fb2a3c03` and no
copy existed outside `runtime/agent-workspace`. Before/after hashes were
identical for `examples/` and for repository files outside the workspace and
`runtime/evidence`. Evidence:
[`pkgproof0807b-mcp-transcript.jsonl`](../runtime/evidence/pkgproof0807b-mcp-transcript.jsonl),
[`pkgproof0807b-identity-build.txt`](../runtime/evidence/pkgproof0807b-identity-build.txt),
and [`pkgproof0807b-07-launched.png`](../runtime/evidence/pkgproof0807b-07-launched.png).

The earlier `pkgchat0807a` attempt did not reach the agent because
`emulator_text` left Egg Freckles' prompt field empty; its evidence remains the
reason not to depend on Newton glass text injection for automation.

The real chat-agent gate is now closed by `pkgchat0807b`. A short tic-tac-toe
request entered the same native `server.py:6801` channel that Egg Freckles
**Send** uses ([wire transcript, lines 1–8](../runtime/evidence/pkgchat0807b-wire-transcript.txt#L1-L8)).
The agent selected `create_project`, authored complete source with
`write_source`, corrected a compiler-reported syntax error, rebuilt, selected
`emulator_install`, launched, and called `emulator_screen`
([tool transcript, lines 1–39](../runtime/evidence/pkgchat0807b-agent-tool-transcript.txt#L1-L39)).
Its final source contains the title and visible 3x3 board
([`pkgchat0807b-agent-Main.newt:1-34`](../runtime/evidence/pkgchat0807b-agent-Main.newt#L1-L34));
the exact screenshot returned by the agent is
[`pkgchat0807b-agent-screen.png`](../runtime/evidence/pkgchat0807b-agent-screen.png).
Fresh identity `TTTGridP0807bR1:nwtn` had zero prior git-history matches, and
the 1,784-byte package has SHA-256
`40fdc2e6157cc2afd2f2e075166cad475f4b479be9e55c98f9dc1c257c79f898`
([identity/build evidence, lines 1–9](../runtime/evidence/pkgchat0807b-identity-build.txt#L1-L9)).

The first server request timed out only after those tool calls while the agent
kept visually checking. The one recovery resumed that preserved Codex thread
through the same port-6801 input path and obtained a normal completion reply
([recovery transcript, lines 6–14](../runtime/evidence/pkgchat0807b-recovery-wire-transcript.txt#L6-L14)).
Focused tests passed 65/65 and the full suite passed 120/120
([focused](../runtime/evidence/pkgchat0807b-focused-tests.txt#L1-L3),
[full](../runtime/evidence/pkgchat0807b-full-tests.txt#L1-L3)).

## Proven 2026-08-03 (Track G2)

**An agent ran this loop end to end and the app worked on the first build.**
`codex exec` (codex-cli 0.146.0, host, MCP server `newton` registered with
`default_tools_approval_mode = "approve"` — `docs/agent-tools.md`) was given one
prompt: build "NewtonDice", identity `Dice1:jbfly`, a floating window with a
**Roll** button that shows a random 1–6; scaffold into a new `examples/dice`;
instance `gloop` is already up and seeded; use the MCP tools. Steps 1–2 were
done for it by the supervising session; steps 3–8 it did itself, unaided.

Six MCP calls, all successful, no retries and no intervention. This is
historical proof of the old examples-writing path; the confined workspace path
was subsequently emulator-proven in the 2026-08-07 round above:

| # | call | result |
|---|---|---|
| 1 | `build_pkg {"dir": "examples/dice"}` | `examples/dice/dice.pkg` (1,984 bytes) — **first attempt** |
| 2 | `emulator_install {"pkg_path": "/packages/dice/dice.pkg", "instance": "gloop"}` | `queued` |
| 3 | `emulator_newtonscript {"source": "GetRoot().\|Dice1:jbfly\|:Open();", "instance": "gloop"}` | `queued` |
| 4 | `emulator_screen {"instance": "gloop"}` | window on screen showing `-` and **Roll** |
| 5 | `emulator_tap {"x": 220, "y": 218, "instance": "gloop"}` | `{"ok":true}` |
| 6 | `emulator_screen {"instance": "gloop"}` | the `-` had become `1` |

Evidence: [`gloop-codex-transcript.txt`](../runtime/evidence/gloop-codex-transcript.txt)
(every call verbatim plus codex's own report),
[`gloop-02-codex-launched.png`](../runtime/evidence/gloop-02-codex-launched.png)
and [`gloop-03-codex-after-tap.png`](../runtime/evidence/gloop-03-codex-after-tap.png)
— both produced by codex's `emulator_screen`, decoded out of the run's JSONL.
The app is committed as `examples/dice`.

**Independently re-verified**, because two screenshots and one `1` are thin
proof of a die: the supervising session then tapped Roll six more times with
plain `curl` against the control port and read the value back each time — `1 3 2
3 3 1`, all inside 1–6 and changing
([`gloop-verify-rolls.txt`](../runtime/evidence/gloop-verify-rolls.txt),
`gloop-verify-roll1..6.png`).

Four things the round showed:

- **The runbook is followable by an agent.** codex's first action after the
  prompt was `cat docs/agent-dev-loop.md`, and it then executed steps 3–8 in
  order, including `rm examples/dice/hello.pkg` (the scaffold's built artifact,
  which step 3 tells you to drop) without being told twice.
- **Step 8's tap rule earned its place.** codex took the screenshot *before*
  choosing where to tap — "after tapping the button's center at (220, 218)" —
  which is why a single tap hit a button whose declared x-bounds were 52 px
  away from where it rendered.
- **`ViewSetupDoneScript` is the way to keep a handle on a child view.** The app
  binds the value view into a parent slot at setup
  (`self:Parent().valueView := self`) and then updates it with
  `SetValue(self.valueView, 'text, "" & Random(1, 6))`. No compiler trap, no
  identity churn, 38 lines total.
- **Nothing needed the network.** No broker, no `server.py`, no NIE — the whole
  loop is `build_pkg` + the emulator control API. The flash seed in step 2 is
  for the Welcome tour, not for connectivity.

Instance `gloop` was torn down (`make emulator-instance-down INSTANCE=gloop`)
after the evidence was copied out.
