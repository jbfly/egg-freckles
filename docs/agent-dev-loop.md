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

1. **Claim an isolated emulator.** Never the shared `newton-harness_emulator_1`
   — other sessions and the hardware bench use it, and `newton_mcp.py` refuses
   mutating tools on it anyway (`newton_mcp.py:guard_shared`).

   ```sh
   make emulator-instance-up INSTANCE=<yourname>
   until [ "$(podman inspect -f '{{.State.Health.Status}}' newton-harness-<yourname>_emulator_1)" = healthy ]; do sleep 5; done
   ```

2. **Seed its flash, even though the dev loop needs no network.** A fresh
   instance boots into the first-run Welcome tour, and *the tour suppresses
   floating windows* — a `protoFloatNGo` app installs fine and then shows
   nothing, which reads like a broken app. Copy a flash that is already past the
   tour (~90 s, recipe and seed-picking table in `docs/parallel-emulators.md`,
   "Seed an instance from a saved flash"):

   ```sh
   podman stop -t 20 newton-harness-<yourname>_emulator_1
   podman cp ~/newton-archive/newton-harness/flash-backups/internal-before-round9-loader-20260725-195622.flash \
             newton-harness-<yourname>_emulator_1:/state/internal.flash
   podman start newton-harness-<yourname>_emulator_1
   ```

   It boots to the Notepad with a `PCMCIA Ethernet` slip on top; tap its close
   box at roughly `247,178`. Sometimes one or more `Sorry, a problem has
   occurred` alerts sit above it — close box at roughly `247,271`, tap until
   they are gone. `emulator_screen` after each tap; do not proceed until the
   screen is a bare Notepad.

3. **Scaffold from `examples/hello`.** Copy the directory, do not edit `hello`
   itself — it is the toolchain smoke test (`make toolchain-hello`,
   `examples/README.md`). Three files: `Main.newt`, `<name>.nprj`, `Makefile`.

   ```sh
   cp -r examples/hello examples/<name> && rm -f examples/<name>/hello.pkg
   mv examples/<name>/hello.nprj examples/<name>/<name>.nprj
   ```

   Then rename inside them: the `Makefile` names `hello.pkg` and `hello.nprj`
   in three places (target, prerequisite, `clean`), and `tntk` is invoked as
   `-c <name>.nprj`. `build_pkg` looks for `<dirname>.pkg` first and only falls
   back to any `*.pkg` in the directory (`newton_mcp.py:272-275`), so keep
   directory, `.nprj` and `.pkg` basenames identical. (`examples/harness-client`
   is the one deliberate exception — it builds `egg-freckles.pkg` and rides that
   fallback, because Track L1 renamed the package without renaming the
   directory.)

4. **Give it a brand-new identity — never reuse one.** In `Main.newt` set
   `kAppSymbol := '|<Name><Round>:jbfly|;` and put the *same* string in the
   `.nprj`'s `name:` slot. Bumping only `kVersion` does **not** let a package
   replace an installed one: NewtonOS answers `-10402 Package already exists`,
   and the one-argument `GetPkgRef` used to clean up fails silently
   (`docs/phase3-chat-round.md`, "Package identity — the actual rule"). Put a
   round tag in the symbol from the start (`Dice1`, `Dice2`, …) so there is
   always a next one.

5. **Build with the host toolchain** — the `build_pkg` MCP tool, which is
   `make -C examples/<name>` with `~/newton-dev/prefix/bin/tntk`:

   ```json
   build_pkg {"dir": "examples/<name>"}
   ```

   It returns the built `.pkg` path, or the tail of the compiler output when the
   build fails — iterate on that text, it is the only diagnostic you get.
   `tntk` must have been built with `tools/tntk-project-version.patch` applied
   out of tree; **without that patch every rebuild silently regresses the
   package header to version 1** (`docs/START-HERE.md:95-104`,
   `docs/phase3-chat-round.md` "Risk"). That is a one-time host setup, not
   something the loop does.

6. **Install it into your instance.** `/packages` inside the emulator is a
   read-only bind mount of the repo's `examples/` (`compose.yaml:40`), so a
   directory you created after the container started is already visible there —
   no upload, no copy. `POST /install` takes a **path**, not a file
   (`docs/install-paths.md` row 1):

   ```json
   emulator_install {"pkg_path": "/packages/<name>/<name>.pkg", "instance": "<yourname>"}
   ```

   The equivalent from a shell is
   `NEWTON_CONTROL_URL=http://127.0.0.1:<port> scripts/install-and-launch.sh /packages/<name>/<name>.pkg '<Symbol>:jbfly'`,
   which also does step 7.

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

9. **Iterate: bump the identity every round.** Change the source, then give it a
   new symbol *before* rebuilding — the installed copy will not be replaced
   otherwise (step 4). `scripts/newton-round.sh <dir> <tag>` does the bump plus
   build/install/launch/OCR in one shot, but note two limits before reaching for
   it: it drives the **shared** container `newton-harness_emulator_1`
   (`scripts/newton-round.sh`, `container=newton-harness_emulator_1`), and its
   bumper requires `kVersion := "<base>-<tag>";` with a lowercase tag, which the
   `hello` scaffold does not have. For an isolated instance, either add that
   `kVersion` shape and reuse `bump_identity`'s conventions by hand, or just
   edit `Main.newt` + `.nprj` yourself and repeat steps 5–8. Editing two lines
   is the cheap, honest option for a new app.

10. **Tear down.** `make emulator-instance-down INSTANCE=<yourname>` deletes the
    instance's state volume, flash included — that is the point. Copy anything
    you need out first (`docs/parallel-emulators.md`, "Release it when you are
    done"). Save screenshots and transcripts under `runtime/evidence/<name>-*`
    and commit them; an artifact that exists only inside a disposable container
    is already gone.

**Hardware is a separate, human-gated step.** There is no tool that installs
onto the MessagePad, by design (`docs/agent-tools.md`, rail 3). The most an
agent may do is `stage_hw {"pkg_dir": "examples/<name>"}`, which builds, copies
into `runtime/staging/hardware/`, refreshes `SHA256SUMS` and prints the short
filename. A human then opens the ZC40 Loader, types that filename and taps
Install (`docs/install-paths.md` row 2). Check free space first with
`newton_tool {"op": "store_info"}`.

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

## Proven 2026-08-03 (Track G2)

**An agent ran this loop end to end and the app worked on the first build.**
`codex exec` (codex-cli 0.146.0, host, MCP server `newton` registered with
`default_tools_approval_mode = "approve"` — `docs/agent-tools.md`) was given one
prompt: build "NewtonDice", identity `Dice1:jbfly`, a floating window with a
**Roll** button that shows a random 1–6; scaffold into a new `examples/dice`;
instance `gloop` is already up and seeded; use the MCP tools. Steps 1–2 were
done for it by the supervising session; steps 3–8 it did itself, unaided.

Six MCP calls, all successful, no retries and no intervention:

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
