# Phase 3 — Newton chat client round

Overnight round, 2026-07-26. All five queued items landed. The Newton runs a
real chat client: you type a prompt, it goes out as a framed `MSG`, and the
reply renders in the transcript.

Final commit: `8abbc8e`, clean and pushed to `origin/master`.

## Bottom line

Framed native mode now engages, a typed prompt completes a full round trip on
screen, error recovery is pinned by tests, the UI is built on stock Newton
protos, and draft/double-send/`/new` all behave. 19 host tests pass. The
device runs stable `|HarnessClient:jbfly|` package version 8, app version 1.9.

The one fragile thing left is outside this repo: a local patch to `tntk`
(see [Risk](#risk-the-tntk-patch-is-uncommitted-and-outside-this-repo)).

## What works

| # | Item | Commit | Evidence |
|---|---|---|---|
| 1 | Handshake negotiation | `e9d2637` | proxy log shows `ACK 00`, not a PT100 echo |
| 2 | MSG/TEXT round trip | `0f624b4` | reply text on the Newton screen |
| 3 | ACK/NAK, retry, duplicate | `b8bce68` | `test_server.py`, 18 → 19 tests |
| 4 | Chat UI on stock protos | `30917e2`, `21f8575` | `runtime/evidence/b-exchange.png` |
| 5 | Draft / double-send / `/new` | `e86504f` | `runtime/evidence/q5-wire.log` |
| — | Stable identity on device | `8abbc8e` | `runtime/evidence/s9-info.png` |

### 1. Handshake negotiation — `e9d2637`

One line. `server.py:424` gave the client a hard 0.15 s to deliver its first
byte; a real Newton is still inside `SetInputSpec` when that expires, so the
host fell back to PT100 and echoed `~NEWTONCLI 1` as plain text. Window is now
1.0 s. Wire format unchanged. PT100 telnet users are unaffected in practice —
the deadline only delays the fallback for a client that connects and says
nothing.

Framing is proven in **both** directions; the Newton ACKs the host's frames too:

```
C> b'~NEWTONCLI 1\r\n'
C> b':00 HELLO NEWTON1 1.2-p3a*02\r\n'
<S b'ACK 00\r\n'
<S b':00 STAT READY*51\r\n'
C> b'ACK 00\r\n'
```

### 2. MSG/TEXT round trip — `0f624b4`

A typed prompt goes out framed and the reply lands on screen. Correct sequence
discipline throughout, every frame ACKed both ways.

### 3. Error recovery — `b8bce68`

Host-side tests rather than emulator rounds: corrupting a checksum and
swallowing an ACK is easier and more rigorous over a plain socket, and a test
is permanent evidence where a log is a throwaway.

- **Corruption** — flip a checksum byte, expect exactly `NAK 01 CHECKSUM`,
  assert nothing applied, resend the *identical* good bytes at the *same*
  sequence, drive to completion, assert history contains `"recover me"` once.
- **Retry ceiling** — withhold every ACK, assert `attempts == [attempts[0]] * 4`
  (four byte-identical sends), assert the connection closes rather than
  emitting a fifth.
- **Duplicate** — re-send sequence `01` mid-turn, expect a *second* `ACK 01`,
  assert the user message landed once.

**No production code changed.** `server.py` already implemented the contract;
these tests pin it down. That is the right outcome — spec and implementation
already agreed.

### 4. Chat UI — `30917e2`, `21f8575`

`examples/harness-client/Main.newt`, all stock protos: `protoTitle`,
`protoStaticText` transcript, `protoDivider`, `protoInputLine` prompt,
`protoTextButton` New/Send, quiet status line. Transcript gets 240 of 404 px —
it is the content, the prompt is just input.

The 6 KiB cap is genuinely proven, not asserted. `SelfTest` pushes 400 lines
(~17 KB) through the *shipped* `AppendLine` and the device renders
`Cap test PASS: size=6120 first=265 0123456789…` — under 6144, not emptied,
newest kept, oldest survivor a *complete* line. Re-runnable:

```sh
curl -X POST .../newtonscript --data-binary 'GetRoot().|<sym>|:SelfTest();'
```

Evidence: `final-captest.png` / `.txt`, `final-ui-ready.png`, `b-exchange.png`.

### 5. Draft, double-send, `/new` — `e86504f`

Proven with a proxy that delays the MSG ACK by 8 s, turning an unscreenshottable
race into a wide deterministic window:

```
:01 MSG keep this draft*36     ← ONE frame, from a deliberate double tap
DELAY  ACK 01 for 8 seconds    ← draft still in the field
:02 MSG /new*02                ← /new is an ordinary MSG on the wire
```

Evidence: `q5-draft-double.png` (draft retained, one `You:` line, status
`Turn in flight`), `q5-after-ack.png` (field cleared), `q5-new-cleared.png`,
`q5-wire.log`.

## What cost the most time — NewtonScript lessons

Three of the four hard bugs this round were NewtonScript string and view
handling, not protocol work. Read this before touching `Main.newt`.

- **Text-field values are rich strings.** `Length` throws — use `StrLen`.
  `StrEqual` compiles and then throws on-device — use native `=`. Read a
  prompt with `DecodeRichString(field.text, field.viewFont).text`
  (`Main.newt:306`).
- **Newton's input callback retains the line terminator.** `BeginsWith("ACK ")`
  matched while exact equality silently did not — the draft survived correctly
  and then never cleared. Prefer `StrLen` + `BeginsWith`.
- **Never find a child by index, and never by `viewFrontKey`.** Newton reorders
  floating controls, and `viewFrontKey` points at the **Send button** right
  after you tap Send — so `field.text` was read off a button, which is the
  actual source of the `-48200` throw. `Wire()` (`Main.newt:50`) identifies
  children by unique `GlobalBox().top`.
- **A stale app window in front masquerades as a failed install.** Explicitly
  open the app after installing before concluding anything.
- The instrumented-marker technique (set the status line to `M1`, `M2`, … at
  successive points, one install round, see which survives) localises a throw
  in a single round. Use it instead of guessing.

## Package identity — the actual rule

"Never reuse a package identity" is true but incomplete, and the incomplete
version cost two rounds.

- Bumping the package version **does not** allow replacement. NewtonOS returns
  `-10402 Package already exists`.
- `SafeRemovePackage(GetPkgRef("HarnessClient:jbfly"))` — the one-argument
  lookup — **fails silently**. This is what made removal look impossible.
- The sequence that works:

  ```newtonscript
  GetRoot().|HarnessClient:jbfly|:Close();

  local p := GetPkgRef("HarnessClient:jbfly", GetDefaultStore());
  if p then SafeRemovePackage(p);
  ```

  The store-specific `GetPkgRef(..., GetDefaultStore())` is the difference.
  Then install, then explicitly open, then verify with `GetPkgRefInfo`.

## Risk: the `tntk` patch is uncommitted and outside this repo

`~/newton-dev/tntk/package.cpp:161` hardcoded the package header version to
`1`. It was patched to read an integer `version` slot from the `.nprj`:

- `~/newton-dev/tntk/package.cpp`
- `~/newton-dev/tntk/package.h`
- rebuilt to `~/newton-dev/prefix/bin/tntk`

**That patch is the only copy and it is not under version control.** That tree
also carried a pre-existing unrelated `tntk.cpp` modification and an untracked
`build-cxx17/`, both preserved. If that directory is reset or the toolchain
rebuilt from upstream, package builds regress to version 1.

Preserving it is the single next action below.

## What does not work / out of scope

- **Out of scope by instruction, not attempted:** ink, Notes soup, file
  browsing, GET/PUT/PATCH/RUN, rich text, Unicode, streaming, multiple
  conversations, settings screens. Long prompts are capped to one frame
  (240 bytes) rather than split via MSG_BEGIN/PART/END.
- **Transcript is bottom-anchored by tail-trimming, not scrolled.** You cannot
  scroll back past the 6 KiB window. Adequate, not elegant.
- **Cosmetics deliberately left:** the gap between the buttons and the status
  line is looser than the rest of the vertical rhythm.
- **`pytest` is not installed in the system python.** All 19 tests were run in a
  temporary `uv` environment. Reproduce with
  `uv run --with pytest pytest -q`. There is no checked-in test environment.

## Where this stopped

Everything queued is done and pushed. Verified directly, not taken on a
worker's word:

- `8abbc8e` clean, matching `origin/master`
- 19/19 tests passing
- emulator healthy, running stable `|HarnessClient:jbfly|` pkg version 8 /
  app 1.9, wire-confirmed via `:00 HELLO NEWTON1 1.9*D8`
- no `podman logs` followers; ports 6801/6802 clear
- `runtime/raw_pkg_server.py` the sole listener on `10.42.0.1:18081`

Note: `pgrep -af "podman logs"` matches its own command line and will report a
false positive. Check `/proc/<pid>/cmdline` instead.

## Next

**Preserve the `tntk` project-version patch** — vendor it into this repo as a
patch file under `tools/`, or upstream it. It is currently one `git checkout`
away from being lost, and without it every stable package rebuild silently
regresses to version 1.
