# Newton app authoring guide

This is the curated source of truth for an agent that writes NewtonScript packages. The compact copy in `agent_prompt.txt` is what the chat agent sees every turn; keep it aligned with this page.

## Drive the whole loop

For a new app, complete the sequence yourself: `create_project` -> `write_source` -> `build_pkg` -> `emulator_boot` (isolated instance) -> `emulator_install` -> `emulator_newtonscript` (explicit `:Open()`) -> `emulator_screen`. Exercise the UI when behavior needs a tap, then screenshot again. The confined workspace, exact tool calls, fresh-identity rule, and visual gate are documented at `docs/agent-dev-loop.md:40-109`; installing does not launch the app (`docs/agent-dev-loop.md:78-96`).

A tool failure is a repair instruction. Retry a stage at most five times. Read the exact compiler/runtime error, replace the complete source, and repeat until the package builds, installs, opens, and the screen proves it. Do not hand a compiler error or blank screenshot back to the user. The bounded retry contract is `docs/agent-dev-loop.md:30-38`; a real chat-agent round corrected a compiler error and finished the loop at `docs/agent-dev-loop.md:169-188`.

Build before booting so compiler retries do not consume emulator time. Use only a named isolated instance, never the shared emulator. Long emulator work must be bounded; current limits are 60 seconds for build/Compose/control subprocesses and 90 seconds for health (`docs/dev-loop-reliability.md:75-99`).

## NewtonScript and `tntk` traps

- **A zero exit code can still be a failed build.** `tntk` can print `Uncaught exception:`, leave a tiny partial `.pkg`, and let `make` exit 0 after an undefined helper such as `CellButton`. Treat the exception text as failure and never publish/install that artifact (`docs/dev-loop-reliability.md:35-53`).
- **No captured locals in nested functions.** A nested `func` that reads an enclosing function's local makes `tntk` die with SIGSEGV 139 and no diagnostic. Top-level constants referenced by methods are the same closure bug because `tntk` wraps the file in a function. Put values in view slots and read `self.slot`; callbacks may use their own arguments, globals, and `self` (`docs/newtonscript-eval.md:1498-1544`).
- **Undefined names are runtime/build failures, not missing imports.** `-48807` is undefined variable, `-48808` undefined global function, and `-48809` undefined method (`docs/newton-networking-lessons.md:75-86`). `Compile(string)` is unavailable from installed apps in this ROM context; author fixed operations instead (`docs/newton-networking-lessons.md:248-251`).
- **Symbols are case-insensitive.** A slot can silently shadow a method and cause `-48200`; grep slot and method names for collisions (`docs/newton-dev-notes.md:631-636`).
- **Strings and text views are old-ROM objects.** Use `StrLen`, not `Length`, for strings; avoid `StrEqual` on device; decode rich text explicitly. Do not find children by array index or `viewFrontKey` (`docs/phase3-chat-round.md:125-146`).
- **`protoFloatNGo` geometry is not pixel truth.** Take tap coordinates from a screenshot, not declared `viewBounds` (`docs/newton-dev-notes.md:956-968`). A fresh emulator's Welcome tour can suppress a floating window even when `:Open()` returns true (`docs/newton-dev-notes.md:683-689`). Installing also leaves stale windows in front, so explicitly open the new app before judging it (`docs/phase3-chat-round.md:142-146`).
- **A floating app needs its own scrolling UI.** Stock scroll arrows do not route to ordinary `protoFloatNGo` roots; adding `vApplication` did not fix it (`docs/newtonscript-eval.md:1148-1180`).

## Networking pattern that works

Use NIE's saved connection through `InetGrabLink`, then a `protoBasicEndpoint` TCP client. A fresh blank emulator has neither the NIE packages nor an Internet Setup, so seed a named instance when testing networking (`docs/parallel-emulators.md:46-72`).

1. Call `InetGrabLink(nil, self, 'Grabbed)`.
2. In `Grabbed`, return on errors, ignore ordinary progress until `state.linkStatus = 'connected`, and make `if self.endpoint then return nil` the first guard. Treating `initializing`/`connecting` as failure caused the old `-48803` teardown loop (`docs/newton-networking-lessons.md:88-113,231-245`).
3. Create `{_proto: protoBasicEndpoint, _parent: self}` and instantiate **endpoint frame first**, options second: `endpoint:Instantiate(endpoint, options)`. The current Loader uses this at `examples/harness-loader/Main.newt:134-169`, and `docs/client-network-port.md:7-11` records that the reversed order threw `-48400`. Note: `docs/newton-networking-lessons.md:18-23` still says options-first; its own footgun table and the live source supersede that stale sentence.
4. Use lowercase `connect` and lowercase three-argument `output(data, nil, outputSpec)`. Synchronous `connect(..., {async:nil})` continues directly after it returns; do not wait for a callback that will never run (`docs/newton-networking-lessons.md:35-46`).
5. For outbound bytes, use an async output spec with `form: 'string`, `async: true`, and a completion callback. Missing `form` or using the wrong output shape produced a connected socket with no payload (`docs/newton-networking-lessons.md:130-149,243-245`).
6. Receive with `SetInputSpec`, not argument-taking `Input()`. For HTTP, keep one input form for the whole exchange; string-to-binary switching discards buffered bytes. The Loader's proven GET arms binary input, parses `\r\n\r\n`, then sends `GET /... HTTP/1.0` (`docs/newton-networking-lessons.md:48-73,179-203`; `examples/harness-loader/Main.newt:232-335`).
7. Give every endpoint an `ExceptionHandler`, and make delayed callbacks safe after close. Unsolicited disconnects and delayed calls on dead views otherwise become modal errors (`docs/newtonscript-eval.md:1310-1329`).
8. On quit, clear the input spec, disconnect, unbind, dispose, and release the NIE link. Reuse one held link for multiple endpoints rather than dropping/re-grabbing it (`docs/newton-networking-lessons.md:242-254`).

The emulator can prove real outbound networking: Einstein's user-mode network reaches host listeners on `10.42.0.1`, and a seeded isolated instance can use the same NIE/endpoint code (`docs/agent-tools.md:158-178`; `docs/parallel-emulators.md:46-72`). This repository's WiFi proof app fetched `WIFI ROUND TRIP WORKS`; the host request log is `runtime/evidence/wifi-app/server.log`, the rendered screen is `runtime/evidence/wifi-app/final-network-reply.png`, and OCR is `runtime/evidence/wifi-app/final-network-reply.txt`.

## Package replacement

Prefer a fresh package identity for every iteration. If removal is required, close the app, use the **two-argument** store lookup, then remove:

```newtonscript
GetRoot().|OldIdentity:dev|:Close();
local p := GetPkgRef("OldIdentity:dev", GetDefaultStore());
if p then SafeRemovePackage(p);
```

Bumping only the package version still returns `-10402`, and one-argument `GetPkgRef` fails silently (`docs/phase3-chat-round.md:148-167`). After install, explicitly open and verify.

## Know what can be tested where

- **Emulator-testable:** ordinary Newton UI, stores/Notes operations, and outbound TCP/HTTP through NIE and Einstein user-mode networking. The committed proof is under `runtime/evidence/wifi-app/`.
- **Hardware-only:** optical infrared transmission. Einstein exposes host serial drivers/PTY/TCP-client serial plumbing, not an optical consumer-remote transmitter (`docs/einstein-automation.md:70-96`). Do not claim an emulator IR test.
- **IR is not one protocol.** Newton's normal IR communications tool is half-duplex packet communication and uses the Sharp Infrared protocol (`refs/NewtonProgrammerGuide20.txt:51965-52046`), not a generic 38 kHz television-remote carrier. Apple documented a separate send-only Remote Control API (`refs/qa/endpoint.htm:4-21`), so consumer-remote work requires physical hardware and that separate API; never substitute the standard IrDA/Sharp endpoint or an Einstein serial port.
- **Screen contract:** user-facing chat text is 45 columns, 7-bit ASCII, plain and short (`agent_prompt.txt:4-11`). App UI is a 320x480 grayscale screen (`docs/agent-dev-loop.md:92-103`).

## Final gate

Do not answer “done” until: build output is clean; the exact fresh identity installed; the app was explicitly opened; the screenshot visibly proves the requested behavior; and any network claim has both peer-side log evidence and on-screen response evidence. Save source, package hash, logs, screenshot, and OCR under `runtime/evidence/<app>/` before tearing the isolated instance down.
