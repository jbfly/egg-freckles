# NewtonScript evaluation outcome signal

Investigation date: 2026-07-26.

## Bottom line

MAIN's injected NewtonScript evaluator works, but arbitrary received source still
has no result channel: Einstein emits no result to process output, a transient
script cannot own NIE networking, and NewtonOS 2.1 does not expose the documented
`Compile(string)` global to an installed application. Fixed compiled operations do
work. The fifth investigation proved and restored a resident package plus host
`POST /tools` route with distinct result, Newton error, unknown-operation, and
timeout outcomes.

The earlier SCRATCH-only negative was not trustworthy because SCRATCH never
proved that it could execute any script. This rerun corrects that mistake: MAIN
visibly executed `GetRoot():Notify(3, "MAIN baseline", "evaluator runs")` before
any result-channel conclusion was drawn. See the screenshot and OCR in
[`newtonscript-main-working-evaluator.png`](../runtime/evidence/newtonscript-main-working-evaluator.png)
and
[`newtonscript-main-working-evaluator.txt`](../runtime/evidence/newtonscript-main-working-evaluator.txt).

No log-scraping code was committed. Without an emitted result line, the proposed
synchronous wrapper would return `timeout` for successful and failed scripts as
well as genuinely dropped scripts, which would not provide the required
three-way distinction.

## Existing paths

The control socket added by
`containers/patches/einstein-control-socket.patch` calls
`TPlatformManager::EvalNewtonScript()` and immediately replies `queued`. The
call itself only enqueues a Newton event.

Einstein's Newton-side runtime still appears to offer a possible output path:
`Drivers/NSRuntime/Handlers.f` prints the returned value, or writes `Exception`
and prints `CurrentException()`. Native primitive `0x1A` in
`Emulator/TNativePrimitives.cpp` forwards that text to Einstein's log/process
output.

On MAIN, a compliant `podman logs --since 0s -f` capture saw only HTTP request
lines. The capture was repeated while issuing a visibly executing notification,
`2+2`, and an undefined symbol; MAIN was then restarted to force buffered
process output to flush. The resulting capture still contained no value,
`Exception`, or Newton error:
[`newtonscript-main-buffer-flush.log`](../runtime/evidence/newtonscript-main-buffer-flush.log).

## Three required cases on MAIN

The exact caller observations are captured in
[`newtonscript-main-three-cases.txt`](../runtime/evidence/newtonscript-main-three-cases.txt).

| Case | Probe | Observed caller response | Result |
|---|---|---|---|
| Success | `2+2` | HTTP 200, `queued` | No returned `4`; not distinguishable |
| Error | `PonytailUndefinedProbe` | HTTP 200, `queued` | Newton visibly showed `-48807`, but the caller received no error |
| Drop/timeout | `while true do nil` | HTTP 200, `queued` | No bounded outcome; not distinguishable |

The error execution is independently visible in
[`newtonscript-main-undefined-error.png`](../runtime/evidence/newtonscript-main-undefined-error.png)
and its OCR
[`newtonscript-main-undefined-error.txt`](../runtime/evidence/newtonscript-main-undefined-error.txt).
MAIN was restarted after the bounded blocked-evaluation probe.

## Remaining limitation

A reliable endpoint needs an explicit completion signal from Einstein's
Newton-side evaluation handler to the host, carrying either the result or the
exception. Scraping process output is not viable in the current image because a
working evaluator emits neither form there, even when process termination
forces buffered output to flush.

## Third investigation: script-reported HTTP callback

The proposed callback was implemented and tested on MAIN, then reverted because it
still returned timeout for both `2+2` and an undefined symbol. No classifier was
shipped.

The host-side prototype was intentionally small: `POST /newtonscript?timeout=N`
wrapped the caller's script in `try`/`onexception`, retained a callback frame on
`GetRoot()`, queued that wrapper through the existing control socket, and waited on a
condition variable keyed by a random request ID. Its candidate JSON shape was
`{"queued":true,"status":"result","result":"4","request_id":"..."}` for success,
`{"queued":true,"status":"error","error":-48807,"request_id":"..."}` for a Newton
exception, and `{"queued":true,"status":"timeout","request_id":"..."}` with HTTP
504 for no callback. The frame reused the ink client's
NIE + `protoBasicEndpoint` pattern to POST `request-id / result-or-error / value` to
the existing listener on `10.42.0.1:18081`. The listener forwarded valid callbacks
to the waiting control request. The original no-query endpoint continued to return
`queued`.

### Where it broke

The wrapper parsed and ran far enough to assign
`GetRoot().|NewtonScriptEvalReporter|`; MAIN visibly reported `rooted` in
[`newtonscript-callback-rooted.png`](../runtime/evidence/newtonscript-callback-rooted.png).
Retaining the frame therefore did not fix the send.

Directly invoking that frame's `Send("result", "manual")` raised Newton error
`-48809` on-device before any HTTP request reached `raw_pkg_server.py`; see
[`newtonscript-callback-send-error.png`](../runtime/evidence/newtonscript-callback-send-error.png).
The exact retained-frame attempt and empty listener observation are recorded in
[`newtonscript-callback-retained-attempt.txt`](../runtime/evidence/newtonscript-callback-retained-attempt.txt).
The first full success/error run is in
[`newtonscript-callback-live.txt`](../runtime/evidence/newtonscript-callback-live.txt):
both requests returned clean HTTP 504 timeouts after 20.001 seconds.

| Case | Probe | Caller result | Round trip |
|---|---|---|---:|
| Success candidate | `2+2` | HTTP 504, `status: timeout` | 20.001 s |
| Error candidate | `PonytailUndefinedProbe` | HTTP 504, `status: timeout` | 20.001 s |
| Genuine no-callback | retained reporter whose `Send` raised `-48809` | HTTP 504, `status: timeout` | 30.001 s |

These are not three distinguishable outcomes, so the prototype was reverted. The
host unit prototype did classify fake result/error/timeout inputs and brought the
suite from 24 to 25 tests, but that test was also reverted with the unproven code.

### Remaining limitation

The failure is now narrower than either log-scraping negative: host waiting expired
at the requested bounds and the evaluated wrapper persisted on the Newton, but no
live callback exercised request correlation because a plain evaluated frame could
not reuse the installed application's asynchronous NIE send path. The resident
package experiment below tested the remaining package-owned transport option.

## Fourth investigation: resident package owns transport

A fresh package, `ResidentEvalR1:jbfly`, reused the proven ink application's NIE +
`protoBasicEndpoint` HTTP path. It polled the existing sole listener on
`10.42.0.1:18081`, received one request ID plus expression, called
`Compile(expression)`, and POSTed either the value or the exception number. The host
prototype held one pending request and classified fake `result`, `error`, and
`timeout` outcomes; the temporary test raised the suite from 24 to 25 passing tests.

The transport worked, but runtime compilation did not. For the exact caller input
`2+2`, the resident package returned Newton error `-48808` instead of `4` after
**8.341 seconds**. An undefined-symbol request returned the same `-48808` after
**8.918 seconds**, so success and expression error were not distinguishable. The
Newton Programmer's Reference identifies `-48808` as **“Undefined global function”**;
the unavailable global was the package's direct `Compile(self.expression)` call.
The package-running proof and HTTP sequence are in
[`resident-eval-running.png`](../runtime/evidence/resident-eval-running.png),
[`resident-eval-running.txt`](../runtime/evidence/resident-eval-running.txt), and
[`resident-eval-server.log`](../runtime/evidence/resident-eval-server.log). Exact
caller results and the error-code reference are in
[`resident-eval-result.txt`](../runtime/evidence/resident-eval-result.txt) and
[`resident-eval-compile-gate.txt`](../runtime/evidence/resident-eval-compile-gate.txt).

| Case | Probe | Caller result | Round trip |
|---|---|---|---:|
| Intended result | `2+2` | HTTP 422, error `-48808`; no `4` | 8.341 s |
| Intended expression error | `PonytailUndefinedProbe` | HTTP 422, same error `-48808` | 8.918 s |
| No package running | `2+2` after closing the package | HTTP 504, `status: timeout` | 2.001 s |

The clean timeout is captured in
[`resident-eval-timeout.txt`](../runtime/evidence/resident-eval-timeout.txt). The
poll interval was 0.5 seconds, but repeated NIE link acquisition made delivered
requests take 6–9 seconds; that latency would be a material cost even if compilation
worked.

Per the spike stop rule, the unproven package, host routes, and temporary classifier
test were reverted. The fresh package was removed from MAIN, independently shown in
[`resident-eval-removed.png`](../runtime/evidence/resident-eval-removed.png) and its
[`OCR`](../runtime/evidence/resident-eval-removed.txt). The three earlier negatives
remain above because each excludes a distinct completion path.

## Remaining limitation

NewtonOS 2.1's reference documents `Compile(string)`, but this ROM/application
context resolves it as an undefined global function. With injected evaluation
unable to report and installed applications unable to
compile received source, arbitrary NewtonScript still requires an explicit
Einstein-side completion channel. Patching Einstein remains intentionally out of
scope. The fixed-operation route below does not compile received source and is
therefore unaffected by this negative.

## Fifth investigation: fixed named operations

The fixed-operation foundation **passed and is restored as the deliverable**. Git
objects and the prior worker session confirmed that the reverted implementation
was never saved as a recoverable tree, so it was rebuilt from the recorded protocol
and live evidence. The committed resident package is `HarnessToolsR6:jbfly` in
`examples/harness-tools`; it remains installed and open on MAIN.

The public protocol is `POST /tools` with a JSON object containing an operation
name and argument object:

```json
{"op":"ping","args":{}}
{"op":"front_app","args":{}}
{"op":"get_note","args":{"id":5}}
```

Responses carry `request_id` and `status`, where status is `result`, `error`,
`unknown_op`, or `timeout`. The host restricts operation names to ASCII letters,
digits, and underscore, and rejects a non-integer `args.id`. The package uses a
floating resident window, polls every 0.5 seconds, and dispatches with `StrEqual`;
a bare comparison previously fell through on-device. The host route is part of
`pkg_publisher.make_server`, so `runtime/raw_pkg_server.py` remains the sole
listener on `10.42.0.1:18081`.

### Five live MAIN cases

The device, not a prompt fixture, is the source of truth for `get_note`. The ID-5
response is captured beside a fresh screenshot of the actual stock Notes entry;
the returned recognized text matches the note shown on the Newton. Duplicate IDs
across stores are resolved by selecting the entry with the newest `EntryModTime`.
No note was created or rewritten for this proof.

| Required case | Live MAIN result | Round trip | Evidence |
|---|---|---:|---|
| `ping` | HTTP 200, `result: "pong"` | 10.913 s | [`harness-tools-r6-ping.txt`](../runtime/evidence/harness-tools-r6-ping.txt) |
| `front_app` | HTTP 200, `result: "Notepad (paperroll)"`; stock Notes visibly frontmost behind the floating package | 10.506 s | [`harness-tools-r6-front-app.txt`](../runtime/evidence/harness-tools-r6-front-app.txt), [`harness-tools-r6-front-app.png`](../runtime/evidence/harness-tools-r6-front-app.png) |
| `get_note`, ID 5 | HTTP 200 returned the real text shown by stock Notes | 5.779 s | [`harness-tools-r6-get-note.txt`](../runtime/evidence/harness-tools-r6-get-note.txt), [`harness-tools-r6-stock-note.png`](../runtime/evidence/harness-tools-r6-stock-note.png) |
| unknown operation | HTTP 400, `status: "unknown_op"`, distinct from Newton `error` | 11.543 s | [`harness-tools-r6-unknown.txt`](../runtime/evidence/harness-tools-r6-unknown.txt) |
| package closed | HTTP 504, clean `timeout` | 2.001 s | [`harness-tools-r6-timeout.txt`](../runtime/evidence/harness-tools-r6-timeout.txt) |

The original successful calls measured 5.6-7.5 seconds; the restoration run
measured 5.8-11.7 seconds. Both are dominated by repeated NIE link acquisition,
not the 0.5-second poll interval. The fresh listener sequence is in
[`harness-tools-r6-server.log`](../runtime/evidence/harness-tools-r6-server.log).
No adaptive scheduler, push channel, registry, or plugin layer was added.

The classification test is committed and the suite now has 25 tests. Operation
four follows the same single-branch pattern exactly:

```newtonscript
else if StrEqual(op, "op_four") then begin self.outcomeStatus := "result"; self.outcomeValue := :OpFour(argument); end
```

Add `OpFour` beside the existing operation bodies and one host classification
assertion; no registry or schema layer is needed.
