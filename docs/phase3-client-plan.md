# Phase 3 client implementation plan

## Recommendation

Ship a **text-first native client** before ink. The first useful release should provide a Newton-native editable prompt, a readable scrolling transcript, Send/New controls, connection status, and a reliable framed request/response loop. That already beats PT100 by removing terminal setup and echo behavior, using native text editing, preserving a visible conversation, and presenting explicit progress and errors.

Do not put ink, Notes soup access, file browsing, PATCH, or RUN in the first milestone. Ink still depends on unverified capture and polygon APIs (`protoInkView`, its callback, and `GetPoints` in `docs/ink-client-design.md`). GET/PUT are the next increment after chat proves the shared framing code. PATCH and RUN are only useful once GET/PUT have real Newton-side objects to operate on.

Evidence for this ordering:

- `PLAN.md` defines Phase 3 as a native app with a nicer UI, framing, and GET/PUT; it does not require ink.
- `examples/harness-loader/Main.newt` already proves NIE acquisition and synchronous `protoBasicEndpoint` TCP using `Instantiate(options, self)`, lowercase `connect`, and lowercase `output`.
- `docs/ink-client-design.md` marks the load-bearing ink APIs as `[verify]`.
- The local `Newton 2.1` platform file verifies text-view building blocks, while no `protoInkView` symbol was found.

## 1. Scope: the smallest client worth shipping

### Milestone 1: native text chat

One package, retaining the stable `HarnessClient:jbfly` package identity, with:

- one editable prompt;
- one read-only transcript showing user and server text;
- `Send` and `New` buttons;
- a short status line: `Offline`, `Connecting`, `Thinking`, `Ready`, or a bounded error;
- ASCII input and output only;
- one connection per submitted turn unless persistent connections prove simpler in practice;
- the framed chat subset: `HELLO`, `MSG`, `STAT`, `TEXT`, and `PROMPT`, with ACK/NAK and retries;
- host conversation persistence through the existing `server.py` session state;
- `/new` represented as a framed operation or as a reserved `MSG /new` in milestone 1. Prefer the reserved message unless a separate operation is needed by a test.

Explicitly deferred:

- ink capture and recognition;
- Notes soup integration;
- arbitrary local file browsing;
- GET/PUT/PATCH/RUN UI;
- rich text, Unicode, Markdown rendering, streaming tokens, multiple conversations, settings screens, and background networking.

<!-- ponytail: text chat proves the native UI and framing before file and ink code multiply the failure modes. -->

### Milestone 2: bounded GET/PUT

After chat is reliable, add transfer of **one app-owned plain-text document** at a time. This exercises Phase 3's GET/PUT requirement without risking the user's Notes soup. Use a fixed app-local object name first, a maximum byte count, explicit overwrite confirmation, and byte-for-byte readback after PUT. Add a picker or Notes integration only after this path works.

### Later milestones

1. PATCH for the app-owned document, only if whole-document PUT is measurably wasteful or unreliable.
2. RUN only after a concrete Newton-side runnable artifact exists and confirmation/error semantics are defined.
3. Ink after a capture-only spike verifies the actual NewtonOS callback and polygon extraction API.

## 2. UI for a 480x320 grayscale screen

Assume a landscape 480x320 content area for layout planning. Before coding final bounds, verify how `protoFloatNGo` chrome and Einstein rotation map that nominal screen to root-view coordinates; the current examples use roughly 320-pixel-wide portrait bounds, and `README.md` currently describes `/screen.png` as 320x480.

### Proposed view tree

```text
protoFloatNGo mainView                                  [verified]
├── protoStaticText statusView                          [verified]
├── protoParagraph transcriptView                       [verified proto name]
├── protoInputLine promptView                           [verified proto name]
├── protoTextButton newButton                           [verified]
└── protoTextButton sendButton                          [verified]
```

Use these initial bounds after confirming the root coordinate system:

| View | Bounds `(left, top, right, bottom)` | Purpose |
|---|---:|---|
| `mainView` | `(4, 4, 476, 316)` | Almost full-screen floating app window |
| `statusView` | `(8, 6, 464, 26)` | One-line connection/progress/error state |
| `transcriptView` | `(8, 30, 464, 218)` | Read-only conversation text |
| `promptView` | `(8, 224, 464, 274)` | Two or three lines of editable prompt text |
| `newButton` | `(8, 280, 104, 308)` | Reset conversation after confirmation only if text exists |
| `sendButton` | `(344, 280, 464, 308)` | Submit prompt; disabled or ignored while a turn is active |

The bounds are a starting layout, not a verified fit: window title/chrome may reduce usable height. Prefer shrinking the transcript over creating a second screen.

### Protos and flags

The following names are present in the local `Newton 2.1` platform data or `21PTF/21DEFS.TXT`:

- `protoFloatNGo`
- `protoStaticText`
- `protoParagraph`
- `protoInputLine`
- `protoTextButton`
- `clEditView`
- `vVisible`, `vReadOnly`, `vClickable`, `vStrokesAllowed`, `vGesturesAllowed`, `vCharsAllowed`, `vNumbersAllowed`, `vLettersAllowed`, `vPunctuationAllowed`, `vShapesAllowed`, and `vAnythingAllowed`

Recommended flags:

- `transcriptView`: `vVisible + vReadOnly`. **Verify** whether `protoParagraph` supplies additional required defaults and whether this combination scrolls automatically. Do not claim a scrollbar proto until it is tested; `protoUpDownScroller` exists, but its attachment slots and behavior were not verified.
- `promptView`: start with `protoInputLine` defaults. If explicit flags are required, try `vVisible + vClickable + vGesturesAllowed + vCharsAllowed + vNumbersAllowed + vLettersAllowed + vPunctuationAllowed`. **Verify** multiline behavior, keyboard focus, recognition behavior, and the slot used to cap text length before relying on them.
- buttons and status: use proto defaults unless a compile or device test shows a missing flag. The existing examples compile and display `protoStaticText` and `protoTextButton` without explicit `viewFlags`.

Do **not** use the names `vLettersOK`, `vNumbersOK`, `vPunctuationOK`, `vCursiveOK`, `vShapesOK`, or `vInkOK` from the older ink design. Those exact names were not found locally; the verified Newton 2.1 names use `Allowed`, including `vStrokesAllowed`.

### Transcript behavior

Keep one bounded NewtonScript string, initially capped at 6 KiB. Append `You: ...` and server `TEXT` lines, then discard complete oldest lines when over the cap. This is deliberately not a message-object model. Preserve the draft if connect, send, parse, timeout, or server processing fails; clear it only after the server ACKs the `MSG` frame.

## 3. Transport and protocol

### Recommendation: move chat to the framed protocol now

Use raw TCP to `server.py` on port 6801 and negotiate native mode with an exact first line such as `~NEWTONCLI 1`. Reusing HTTP/1.0 would be the fastest single round trip, but it would create a temporary chat API in `pkg_publisher.py` and postpone the central Phase 3 risk. The endpoint call shape is already proven; the next unknown worth resolving is bidirectional framing and retry behavior.

Keep HTTP/1.0 on port 18081 for package publication and installation. Do not combine package delivery with the interactive protocol.

### Framing to reuse from model100

Reuse the model100 v2 wire shape and algorithms, not its Model 100 file semantics:

```text
:SS OP payload*HH\r\n
ACK SS\r\n
NAK SS REASON\r\n
```

- `SS`: decimal sequence `00` through `99`.
- `HH`: two-digit uppercase hex of `sum(ASCII bytes in "SS OP payload") & 0xFF`.
- one outstanding frame per direction (stop-and-wait);
- ACK valid frames, NAK parse/checksum failures when the sequence is recoverable;
- retransmit the identical frame with the identical sequence after timeout or NAK;
- receiver remembers the last accepted sequence, ACKs a duplicate again, and does not apply it twice;
- maximum encoded line: 240 ASCII bytes initially, matching the proven model100 budget and keeping Newton allocation bounded;
- maximum three retries after the first send;
- reset sequence state on each TCP connection;
- reject non-ASCII payload before sending.

Milestone 1 operations:

| Direction | Operation | Payload |
|---|---|---|
| Client → server | `HELLO` | `NEWTON1` plus optional app version |
| Client → server | `MSG` | One prompt segment, capped so the encoded frame stays ≤240 bytes |
| Server → client | `STAT` | `READY`, `THINKING`, or `ERROR short-text` |
| Server → client | `TEXT` | One display line; split longer replies into multiple frames |
| Server → client | `PROMPT` | No payload; the turn is complete |

A single prompt longer than one `MSG` frame is deferred. Start with a visible input cap that fits one frame after framing overhead. Add `MSG_BEGIN/MSG_PART/MSG_END` only when users actually need longer prompts.

The host should add a native-mode branch to the existing 6801 listener, leaving PT100 behavior unchanged unless the exact handshake is received. Adapt model100's `v2_frame_line`, checksum parser, duplicate ACK handling, and stop-and-wait sender; do not copy its BASIC, file-width, run-repair, or emulator-specific code.

### GET/PUT extension

For milestone 2, reuse model100's operation pattern:

- `GET name`
- `FILE_BEGIN name byteCount checksum`
- `FILE_PART offset ascii-data`
- `FILE_END name byteCount checksum`
- `PUT_BEGIN name byteCount checksum`
- `PUT_PART offset ascii-data`
- `PUT_END name byteCount checksum`
- final `STAT OK` or `STAT ERROR reason`

Use the same per-frame SUM8 plus one whole-file checksum. **Verify before implementation** whether model100's Fletcher-like line checksum should be reused unchanged or replaced with a byte-oriented checksum, because Newton documents are not BASIC line arrays. PATCH and RUN remain protocol-reserved, not milestone-2 requirements.

## 4. Build, install, and test loop

A future agent should use this loop; no step requires modifying the emulator image for ordinary client iterations.

1. **Edit only the client and matching host tests/code.** Keep `examples/harness-client/harness-client.nprj` name and `kAppSymbol` stable so installation replaces the existing client rather than creating another app.
2. **Run host tests first.** Add focused protocol tests to the existing unittest suite, including checksum rejection, duplicate frame idempotence, one dropped ACK/retry, and unchanged PT100 mode. Run:

   ```sh
   python3 -m unittest -v test_server.py test_pkg_publisher.py
   ```

3. **Build and stage both packages reproducibly:**

   ```sh
   make newton-packages
   sha256sum -c runtime/staging/SHA256SUMS
   ```

   For a quicker compile-only client iteration:

   ```sh
   make -B -C examples/harness-client
   ```

4. **Publish the staged client package.** Point `pkg_publisher.py` at the staged artifact so the tested bytes are the installed bytes:

   ```sh
   python3 pkg_publisher.py \
     --host 10.42.0.1 --port 18081 \
     --package runtime/staging/harness-client.pkg
   ```

5. **Install through Harness Loader.** Launch the already-installed loader, tap `Install client update`, and wait for `Deferred install queued`. Use the control API rather than manual mouse input once the app/launcher coordinates are recorded:

   ```sh
   python3 -m emulator.client status
   python3 -m emulator.client tap X Y
   python3 -m emulator.client screen runtime/phase3-install.png
   ```

   The exact launcher and button coordinates are installation-state dependent and must be recorded during the first implementation session rather than guessed in this plan.

6. **Exercise the client with the fake backend.** Start `server.py` with `NEWTON_FAKE_BACKEND=1`, launch Harness Client, focus the prompt, type a short ASCII message, tap Send, and capture the result:

   ```sh
   NEWTON_FAKE_BACKEND=1 python3 server.py
   python3 -m emulator.client tap PROMPT_X PROMPT_Y
   python3 -m emulator.client text 'hello newton'
   python3 -m emulator.client tap SEND_X SEND_Y
   python3 -m emulator.client screen runtime/phase3-chat.png
   ```

7. **Test failure recovery.** Stop the host server, submit once, and verify the draft remains with a readable bounded error. Restart the server and retry without retyping. Then run one dropped-ACK scenario through a host test or a test-only fault-injection setting; do not attempt to induce packet loss through the emulator manually.

8. **Run the real backend only after the fake round trip passes.** Verify a second turn uses the same persisted host conversation and `/new` resets it.

## 5. Risk-ordered task list

Each step is intended to fit one worker session and ends with a runnable acceptance check.

1. **Extract a Newton-independent framing core in `server.py` and tests.** Add encode/parse, sequence, checksum, ACK/NAK, duplicate suppression, and retry tests without changing PT100 behavior.
   - Acceptance: `python3 -m unittest -v test_server.py` passes tests for valid frame, bad checksum, duplicate application exactly once, dropped ACK retry, and an ordinary PT100 line session.

2. **Add native-mode negotiation and fake chat on the host.** The exact `~NEWTONCLI 1` first line switches that connection to framing; all other clients retain the current line editor.
   - Acceptance: a small Python socket test handshakes, sends framed `HELLO` and `MSG`, ACKs `STAT/TEXT/PROMPT`, and receives the fake response; the existing PT100 test still passes.

3. **Compile a static text UI using only verified protos.** Replace the status-button screen with status, transcript, input, New, and Send views; no networking yet.
   - Acceptance: `make -B -C examples/harness-client` succeeds, installation replaces the old package, and `/screen.png` visibly shows all five controls without overlap or clipping.

4. **Verify text editing and transcript scrolling on NewtonOS.** Resolve `protoInputLine` multiline/focus behavior and `protoParagraph` read-only/scroll behavior before adding transport.
   - Acceptance: control API taps the prompt, `/text` inserts at least 120 ASCII characters, Send moves the text into the transcript, the oldest transcript line can be reached or is visibly retained after enough lines, and no unverified proto name remains in source.

5. **Port the framed client transport with a fake local turn.** Reuse the loader's exact endpoint setup and cleanup. Implement frame parse/encode, one outstanding send, ACK/NAK, duplicate suppression, timeout, and retry.
   - Acceptance: fake backend round trip displays `FAKE REPLY TO: hello newton`; host test drops one ACK and the Newton shows only one user turn and one reply.

6. **Finish chat UX and recovery.** Preserve drafts until `MSG` ACK, bound transcript and errors, prevent double Send while busy, and make New reset host and local transcript.
   - Acceptance: server-down submit retains the draft; retry succeeds after restart; two rapid Send taps produce one host turn; New followed by a message creates a new host thread.

7. **Add one app-owned GET/PUT object.** Implement bounded transfer, overwrite confirmation, whole-object checksum, temporary receive state, commit only after validated `PUT_END`, and readback verification.
   - Acceptance: PUT known ASCII text, GET it back byte-for-byte, corrupt one part and observe NAK/no commit, then retry successfully; oversized input is rejected before allocation.

8. **Decide whether Phase 3 needs PATCH/RUN before ink.** Implement neither without a real Newton object and user workflow.
   - Acceptance: written decision based on GET/PUT use; if no measured need exists, close Phase 3 with those operations documented as reserved.

9. **Run an ink API spike, not an ink product.** Verify the actual capture proto/callback and point extraction names using a separate minimal example or a temporary branch.
   - Acceptance: one control-API `/drag` produces a visible stroke count and point count on screen. Only then update `docs/ink-client-design.md` confidence tags and plan the ink UI.

## 6. Open questions requiring a human decision

1. **Does the text-chat milestone count as the first Phase 3 shipment, with GET/PUT following immediately after?** Recommendation: yes; it isolates the native UI and framing risks and already beats PT100.
2. **Should native framing negotiate on the existing port 6801 or use a dedicated port?** Recommendation: use 6801 with an exact handshake so PT100 remains a fallback and only one server/session store exists.
3. **What should the first GET/PUT object be: an app-owned text document or direct Notes soup data?** Recommendation: app-owned text first; touch Notes only after bounded transfer, overwrite confirmation, and readback are proven.

## Evidence and verification boundaries

- Verified locally: endpoint call shape in `examples/harness-loader/Main.newt`; HTTP package publication in `pkg_publisher.py`; reproducible package staging in `Makefile`; control endpoints in `emulator/control.py`; model100 framing and stop-and-wait implementation in `~/git/model100/server.py` and `proto/m100v2_sim.py`; listed text protos/constants in `~/newton-dev/ntk-platform-files/Newton 2.1` and `21PTF/21DEFS.TXT`.
- Not verified: final landscape root bounds, `protoParagraph` scrolling configuration, `protoInputLine` multiline/cap slots, automatic Send-button disabling, any ink capture proto/callback, `GetPoints`, Notes soup record shape, and a Newton-appropriate whole-object checksum choice.
- Current mismatch to resolve during implementation: `PLAN.md` and this task target 480x320, while current examples and `README.md` reflect a 320x480 Newton coordinate surface. Do not hard-code final view bounds until the intended orientation is demonstrated in Einstein and on the target MessagePad.
