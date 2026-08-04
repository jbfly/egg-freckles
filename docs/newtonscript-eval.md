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

## Sixth investigation: persistent named-operation socket

The persistent-socket hypothesis **failed at Newton endpoint input**, after the
TCP connection itself succeeded. A fresh package, `HarnessToolsP5:jbfly` in
`examples/harness-tools-persistent`, grabs the NIE link once, creates and connects
one `protoBasicEndpoint`, arms a CRLF-terminated string `Input()`, and intends to
write each named-operation outcome on the same socket. The disposable host in
`runtime/persistent_tools_server.py` speaks the newline protocol and exposes a
loopback-only `/tools` driver for measurement.

The requested spare listener on `10.42.0.1:18082` was bound and tested first, but
the installed host policy drops it: `ap/newton-ap.nft` permits Newton TCP only to
6801 and 18081. The device reported `-48809` after the 45-second connect attempt
([`p2-open.png`](../runtime/evidence/p2-open.png)); no SYN reached the listener.
No-sudo rules prevented changing the active policy,
and port 18081 remained exclusively owned by `runtime/raw_pkg_server.py`.

To separate that host-policy failure from NIE behavior, the chat container was
temporarily stopped and the identical P5 protocol was tested on already-allowed
port 6801. The device established one TCP connection from `10.42.0.1:51918` to
`10.42.0.1:6801`. Host request bytes were accepted by TCP and the connection
remained `ESTAB`, but the Newton `InputScript` never ran and no response bytes
arrived. The Newton UI also remained blocked in the synchronous `Input()` call.
Ten sequential `ping` requests on that same connection all reached the caller's
2-second timeout:

| Calls | Result | Minimum | Median | Maximum | Evidence |
|---:|---|---:|---:|---:|---|
| 10 | HTTP 504, `Newton did not answer on the persistent connection` | 2.001911 s | 2.002277 s | 2.002626 s | [`p5-timeouts.jsonl`](../runtime/evidence/p5-timeouts.jsonl), [`p5-timeout-summary.txt`](../runtime/evidence/p5-timeout-summary.txt) |

There is therefore no successful per-call latency distribution to compare with
the current poll-plus-POST path's 5.8-11.5 seconds. The persistent path's measured
result is ten bounded timeouts despite an established socket, not a latency win.
Forcing the host listener closed did wake the Newton endpoint and P5 reconnected
in **10.152 seconds**, captured in
[`p5-reconnect.txt`](../runtime/evidence/p5-reconnect.txt). That is in the same
cost class as the existing repeated NIE acquisition.

The connection remained `ESTAB` for the full **360-second** idle
observation interval; see [`p5-idle.txt`](../runtime/evidence/p5-idle.txt). NIE did
not report an idle-timeout error during that interval. The exact negative is thus
not idle link teardown: NIE/Einstein keeps the TCP session, but a resident package
blocked in this endpoint `Input()` shape does not receive unsolicited host data.
The live package build has no undefined-symbol warning
([`p5-build.log`](../runtime/evidence/p5-build.log)); the TCP session and ten call
outcomes are device-derived rather than hardcoded fixtures.

The production `HarnessToolsR6:jbfly` package and HTTP protocol are unchanged.
The persistent package remains a spike because it cannot complete even `ping`;
`front_app` and `get_note` consequently cannot pass end to end on this path.

## Seventh investigation: Newton-initiated long-poll

The Newton-initiated long-poll hypothesis **passed**, but only with asynchronous
endpoint input. A fresh `HarnessToolsL3:jbfly` package grabs one NIE link,
connects one endpoint to the temporarily freed allowed port 6801, writes
`POLL\r\n`, and arms `SetInputSpec` without calling synchronous `Input()`. The
host holds that poll until a named operation arrives, returns `TOOLS ...` as the
response, and receives the operation result on the same socket. The input script
immediately sends the result and installs the next poll before returning.

The synchronous control, `HarnessToolsL1:jbfly`, sent the six-byte poll on an
established connection but its following `Input()` immediately raised a
Communications `Stopped` alert, sent FIN, and reconnected. Its ten calls produced
zero results: five HTTP 503 closed-connection responses and five two-second HTTP
504 timeouts ([`l1-calls.jsonl`](../runtime/evidence/l1-calls.jsonl)). A first
asynchronous attempt, L2, proved solicited delivery with one **61.668 ms** ping,
but delayed re-arming outside `InputScript` caused connection churn and only
five of ten calls completed. Re-arming from inside the input callback, as the
Newton endpoint guide permits, removed that churn.

L3 completed all ten sequential pings over one unchanged TCP connection (source
port 33238). Host-observed end-to-end latency was:

| Calls | Result | Minimum | Median | Maximum | Evidence |
|---:|---|---:|---:|---:|---|
| 10 | 10 HTTP 200, `pong` | 0.124964 s | 0.809219 s | 0.810243 s | [`l3-pings.jsonl`](../runtime/evidence/l3-pings.jsonl), [`l3-ping-summary.txt`](../runtime/evidence/l3-ping-summary.txt), [`l3-server.log`](../runtime/evidence/l3-server.log) |

This is a direct improvement over the current poll-plus-POST path's measured
5.8-11.5 seconds. The first already-armed exchange completed in 124 ms; steady
sequential calls clustered at about 809 ms because the next HTTP submission
waited for Newton to send and arm its next poll.

The asynchronous input does **not** block the UI event loop. While L3 had an
outstanding poll, the device accepted `GetRoot().paperroll:Open()`. The next
`front_app` call returned the real frontmost application, `Notepad (paperroll)`,
in 34 ms, and `get_note` for device entry ID 5 returned the real stored text,
`Export test received. I see: "the nthis note.ewton sees"`, in 820 ms
([`l3-front-app.txt`](../runtime/evidence/l3-front-app.txt),
[`l3-get-note.txt`](../runtime/evidence/l3-get-note.txt),
[`l3-result-summary.txt`](../runtime/evidence/l3-result-summary.txt)). A persistent
PCMCIA information slip obscured the Notes screen capture, so these device
read-backs, rather than OCR of that overlay, are the acceptance evidence.

The persistent direction is therefore **open**. Newton cannot synchronously
block in `Input()`, and it cannot receive bare unsolicited host data, but an
asynchronous Newton-originated poll can reuse one endpoint across calls with
sub-second steady latency. The L3 package and `runtime/persistent_tools_server.py`
remain a measured spike; the production R6 poll-plus-POST path is unchanged.

## Eighth investigation: production persistent tools promotion

The async Newton-initiated long poll is now the production path. Fresh
`HarnessToolsR9:jbfly` replaces R6's per-call GET plus POST lifecycle with one
endpoint on `10.42.0.1:18081`: it sends `POLL`, arms asynchronous input, replies
from `InputScript`, and re-arms before that callback returns. `pkg_publisher.py`
accepts the newline transport on the same listener that preserves the existing
`POST /tools` JSON API. A three-second internal ping keeps the outstanding poll
active; after three missed callbacks the Newton tears down and reconnects.

R6 was first recovered independently after boot-time close/remove cleanup, with
fresh device-originated `/tools/poll` requests at 16:55:01 and 16:55:07
([`r6-recovery-20260726.txt`](../runtime/evidence/r6-recovery-20260726.txt)).
The final R9 production benchmark then completed ten sequential `ping` calls on
one unchanged TCP source port, 56256:

| Calls | Result | Minimum | Median | Maximum | Evidence |
|---:|---|---:|---:|---:|---|
| 10 | 10 HTTP 200, `pong` | 0.109552 s | 0.813895 s | 0.814582 s | [`r9-pings.jsonl`](../runtime/evidence/r9-pings.jsonl), [`r9-ping-summary.txt`](../runtime/evidence/r9-ping-summary.txt), [`r9-connection-after-pings.txt`](../runtime/evidence/r9-connection-after-pings.txt) |

Device read-back remained real: after opening Notes, `front_app` returned
`Notepad (paperroll)` in 0.125936 s and `get_note(5)` returned the stored text
`Export test received. I see: "the nthis note.ewton sees"` in 0.824420 s
([`r9-front-app.txt`](../runtime/evidence/r9-front-app.txt),
[`r9-get-note.txt`](../runtime/evidence/r9-get-note.txt)). Finally, killing the
18081 listener forced a real drop; R9 reconnected without intervention in
14.712 s on source port 47034
([`r9-forced-reconnect-summary.txt`](../runtime/evidence/r9-forced-reconnect-summary.txt),
[`r9-forced-reconnect-after.txt`](../runtime/evidence/r9-forced-reconnect-after.txt)).
`runtime/raw_pkg_server.py` remained the sole 18081 listener and chat remained
available on 6801.

## Ninth investigation: zombie package teardown and watchdog floor

R10A's stable ESTAB socket was not a live R10A transport. Restarting the main
emulator removed source port 39886, and no package reconnected during the next
45 seconds. A clean, fresh R10B install did connect and initially returned 5/5
pings in 0.040-0.814 s, proving that the 2-second delayed call could run and that
`InputScript` still re-armed. It was not stable, however: the host heartbeat is
sent every 3 seconds (`pkg_publisher.py:70`), and the faster watchdog eventually
forced false reconnects, a communications slip, and a 9.015-second warm call.
The watchdog period must therefore stay above the 3-second heartbeat cadence;
R10D uses 4 seconds.

The persistent zombie had a separate lifecycle cause. Closing and removing
R10B left its source port 42920 alive beside fresh R10C port 47368 because the
app never called `Stop()` when its view closed. R10D adds the missing
`ViewQuitScript`: closing it removed port 41322 within 3 seconds, and reopening
created only port 36340. The final package registration frame is present and the
`tntk` build contains no undefined-symbol diagnostic
([`r10d-build.log`](../runtime/evidence/r10d-build.log)).

Two separate 92-second idle trials stayed on source port 36340. Their first
post-idle calls were 0.123 s and 0.124 s; all ten post-idle calls succeeded, with
maxima of 0.815 s and 0.814 s
([trial 1](../runtime/evidence/r10d-idle-trial1.txt),
[trial 2](../runtime/evidence/r10d-idle-trial2.txt)). Final device-executed
read-back returned `Notepad (paperroll)` in 0.045 s and note entry 5's stored
text in 0.766 s ([front app](../runtime/evidence/r10d-front-app.txt),
[note](../runtime/evidence/r10d-get-note.txt)). The full test suite passed 30/30
without changing the live device connection; its `Newton tools disconnected`
line comes from the loopback ephemeral-port heartbeat test, not port 18081
([`r10d-pytest.txt`](../runtime/evidence/r10d-pytest.txt)).

## Tenth investigation: the idle "threshold" is a race, not a threshold

Measured on R10D (`40adcfb`), one sweep, source port sampled before idle,
after idle, and after the bench. Raw data: `runtime/evidence/idle-sweep.txt`.

| Gap | Port during idle | First call |
|---:|---|---:|
| 60 s | unchanged -> changed on bench | **7.113 s** |
| 80 s | changed during idle | 0.100 s |
| 90 s | unchanged, still valid | 0.090 s |
| 95 s | unchanged -> changed on bench | **7.263 s** |
| 110 s | unchanged -> changed on bench | **7.754 s** |
| 150 s | changed during idle | 0.844 s |
| 300 s | unchanged -> changed on bench | 0.187 s |

Gap length does not predict cost: 60 s cost 7.1 s, 300 s cost 0.19 s. What
predicts it is **who notices the dead link first**. The link dies silently
while idle; if the 4 s watchdog reconnects during the idle window the cost is
free, and if it does not, the first call pays ~7-9 s of synchronous
reacquisition.

This is why four separate idle trials (two by a worker at 92 s, two by the
orchestrator at 95/100 s) disagreed. All four were sampling the same race.

Do not tune the gap. If the ~7 s worst case matters, the fix is a host-side
keepalive cadence that touches the link more often than it dies, so the
watchdog always wins the race. Even unfixed, the worst case is no worse than
the 5.8-11.5 s per-call baseline this transport replaced, and warm calls
remain ~0.8 s.

## Eleventh investigation: non-blocking endpoint lifecycle

Real hardware exposed the remaining synchronous endpoint calls in R10D: `Bind`,
`Connect`, and both `Output` operations can hold Newton's application task for
seconds or for the full 45-second connect timeout. Fresh `HarnessToolsR10I:jbfly`
uses endpoint callback specs with `async: true` for those operations. Its input
path remains `SetInputSpec`-only: `InputScript` installs the next input spec inline
before returning and never calls synchronous `Input()`. `ViewQuitScript` still
calls the existing `Stop()` teardown so closing the window disconnects, unbinds,
disposes, and releases the NIE link.

The output specs must include `form: 'string`; without it Einstein established TCP
but emitted no payload. The first poll arms input from its output completion. After
a tool result, `InputScript` has already re-armed input, so the reply completion
sends the next `POLL` without installing a second input spec. Treating replacement
of the prior input spec as a communication error caused connection churn and was
also removed.

R10I completed twelve sequential emulator pings on one unchanged TCP connection:

| Calls | Result | Minimum | Median | Maximum |
|---:|---|---:|---:|---:|
| 12 | 12 HTTP 200, `pong` | 0.308 s | 0.814 s | 0.814 s |

After opening stock Notes, `front_app` returned `Notepad (paperroll)` in 0.132 s.
`get_note(5)` returned the text rendered by a device-side notification in 0.767 s:
`Export test received. I see: "the nthis note.ewton sees"`.

The non-blocking failure gates also passed. With the sole listener paused, a
`POST /tools` remained in flight while the Newton rendered a new notification in
2.037 s. After the listener was killed, the Newton rendered another notification
while reconnects were refused and its health endpoint stayed ready. Restoring
`runtime/raw_pkg_server.py` produced one connection in 8 seconds and the next ping
completed in 0.076 s. The 30-test suite passed without disturbing that live link.

## Twelfth finding: `get_note` IDs were not ordinals

Physical hardware with many Notepad entries exposed two bugs hidden by the small
Einstein soup. R10I compared `args.id` with `EntryUniqueID(entry)`, an internal
soup identifier callers cannot discover, so values such as 0, 2, and 5 returned an
empty string even though Notepad contained many notes. Worse, each request walked
every `paperroll` entry on every store synchronously. A large soup held the
NewtonScript event loop long enough to starve the 3-second host heartbeat and
4-second watchdog; `get_note(1)` timed out after 20 seconds and the persistent TCP
connection was torn down.

R10J defines `args.id` as a 1-based ordinal in ascending `timeStamp` index order.
It queries the `paperroll` union soup once, reads the cursor's first entry directly,
and uses one `cursor:Move(id - 1)` call for later entries. Ordinals are deliberately
limited to 1 through 64 so an arbitrarily large request cannot restore unbounded
synchronous cursor work; out-of-range values return `status: "error"` with
`note ordinal must be 1..64`. This keeps the existing `/tools` JSON envelope and
wire format unchanged while removing the all-stores soup scan.

## Thirteenth finding: three device-management ops (Track C1–C3)

`HarnessToolsR10M:jbfly` (shipped as `HarnessToolsR10N:jbfly` after the wire
round found the `pkg_list` defect below) adds `battery`, `store_info`, and `pkg_list` to the
fixed-op dispatch. Nothing about the wire protocol changed: the host `POST
/tools` route is a generic pass-through that forwards any `TOOL_OP`-matching
name and validates only that `args.id` is an integer if present
(`pkg_publisher.py:354-386`), so these three ops needed **only** Newton-side
code. The reply still travels as the 3-line escaped `id / status / value`
frame (`Reply`; that client was folded into `examples/harness-client/Main.newt` as `ToolReply` in Track L1 and the
separate package deleted).

| op | args | reply shape | status |
|---|---|---|---|
| `battery` | none | `count=N cap=NN% charge=<state> ac=<yes/no> type=<t>` | **proven over the wire** |
| `store_info` | none | one line per store, `<name> total=N used=N free=N ro=<y/n>`, newline-separated (the reply escaper turns them into `\n`) | **proven over the wire** |
| `pkg_list` | optional `id` (1-based ordinal) | no `id` or `id=0` → `count=N`; valid `id` → `i/N <title>\|<size>\|<storeName>`; out of range → `status: "error"`, `package ordinal must be 1..N` | **proven over the wire** in `R10N`; `R10M` threw on every valid `id` (see the `StringToNumber` finding below) |

### What the ops actually produce on Einstein

The `10.42.0.1` blocker below stopped the `POST /tools` round, but it does not
stop the *NewtonScript* from being run: each op's expression was evaluated
directly on isolated instance `c1round` through `runtime/ns_eval.py`, which
proves every system call against the real 717006 ROM. Full transcript in
[`toolsround-r10m-nseval.txt`](../runtime/evidence/toolsround-r10m-nseval.txt).

| op | value returned on Einstein |
|---|---|
| `battery` | `count=0 cap=100% charge=discharging ac=no type=nimh` |
| `store_info` | `Internal total=7638048 used=599716 free=7038332 ro=n` (one store) |
| `pkg_list` (count) | `32` |
| `pkg_list` id 1 | `1/32 ScreenBuffer\|428\|?` |
| `pkg_list` id 32 | `32/32 NIE Ethernet Module\|74888\|Internal` |

Three things behaved differently from the documentation, and all three are the
reason the defensive code earns its keep:

1. **`BatteryCount()` returns `0` on Einstein** while `BatteryStatus(0)` still
   returns a fully populated frame. The reference describes the count as "the
   count of installed battery packs" with battery 0 always being the primary
   pack, so a `0` count with a live battery 0 is self-contradictory — it is an
   emulator artifact. Callers must not use `count` to decide whether to ask for
   status. On this ROM `chargeState`, `acPower`, and `batteryType` all came back
   as the documented symbols, and `batteryCapacity` as a plain integer.
2. **A package's `store` slot can be `nil`.** `GetPackages()[0]` on this ROM is
   `ScreenBuffer`, whose slot classes are
   `id=int;size=int;store=weird_immediate;pssid=weird_immediate;title=string;version=int;timestamp=int;copyprotection=weird_immediate;`
   — `weird_immediate` is `nil`. Calling `pkg.store:GetName()` on it throws, so
   the unguarded form of the op would have failed on its very first ordinal. The
   guarded form prints `?`. (There is also an undocumented `pssid` slot.)
3. **Dynamic slot access `frame.(tagVariable)` works** at runtime, not just at
   compile time — `BatteryStatus(0).('batteryCapacity)` returned `100`. That is
   what lets one `SlotOr` helper nil-guard every battery slot instead of eight
   copies of `HasSlot`.

### Proven over the `POST /tools` long-poll (2026-08-03)

The transport round finally ran, on isolated instance `c2round` against
`runtime/raw_pkg_server.py` on `10.42.0.1:18081`. The broker logged
`Newton tools connected 10.42.0.1:33744` and every op below travelled the link
as a `TOOLS` line and came back as an escaped three-line reply. Evidence files
are `runtime/evidence/toolsround-r10m-wire-*.txt` (full `curl -i` transcripts
with headers and `%{time_total}`) plus
[`toolsround-r10m-wire-screen.png`](../runtime/evidence/toolsround-r10m-wire-screen.png).

| request | wire reply | HTTP | round trip | evidence |
|---|---|---:|---:|---|
| `{"op":"ping"}` | `"pong"` | 200 | 0.053 s | [`…-ping.txt`](../runtime/evidence/toolsround-r10m-wire-ping.txt) |
| `{"op":"battery"}` | `"count=0 cap=100% charge=discharging ac=no type=nimh"` | 200 | 0.817 s | [`…-battery.txt`](../runtime/evidence/toolsround-r10m-wire-battery.txt) |
| `{"op":"store_info"}` | `"Internal total=7638048 used=883236 free=6754812 ro=n"` | 200 | 0.823 s | [`…-store-info.txt`](../runtime/evidence/toolsround-r10m-wire-store-info.txt) |
| `{"op":"pkg_list"}` | `"count=39"` | 200 | 0.825 s | [`…-pkg-list-count.txt`](../runtime/evidence/toolsround-r10m-wire-pkg-list-count.txt) |
| `{"op":"pkg_list","args":{"id":1}}` | `"1/39 ScreenBuffer\|428\|?"` | 200 | 0.856 s | [`…-pkg-list-1.txt`](../runtime/evidence/toolsround-r10m-wire-pkg-list-1.txt) |
| `{"op":"pkg_list","args":{"id":39}}` | `"39/39 PT100:Scrawl\|174416\|Internal"` | 200 | 0.814 s | [`…-pkg-list-max.txt`](../runtime/evidence/toolsround-r10m-wire-pkg-list-max.txt) |
| `{"op":"pkg_list","args":{"id":99}}` | `status: "error"`, `"package ordinal must be 1..39"` | 422 | 0.744 s | [`…-pkg-list-oor.txt`](../runtime/evidence/toolsround-r10m-wire-pkg-list-oor.txt) |

Latency is **~0.8 s for every op that touches the device**, and ~0.05 s for
`ping` when a poll is already parked — the same warm-link profile the fifth
investigation measured, and far below the 10-second cold-link numbers of the
R6 round. No op needed a host-side change, confirming the generic-pass-through
claim above.

Two wire-vs-`ns_eval` differences showed up, and both mattered:

1. **`pkg_list id=<n>` failed over the wire while passing under `ns_eval`** —
   the `StringToNumber` finding immediately below. This is the single most
   useful result of the round: `ns_eval` proves *system calls*, it does not
   prove the *dispatch path*, because it hands the op body an integer literal
   where the wire hands it a string.
2. **`GetPackages()` ordering is not stable across a reboot.** Before the
   container restart ordinal 38 was `HarnessToolsR10M:jbfly|23336|Internal`;
   after it, ordinal 39 was `PT100:Scrawl|174416|Internal`. Treat the ordinal
   as a paging cursor for one conversation, never as a package identifier.

### Fourteenth finding: `StringToNumber` returns a `Real`, and arrays reject it

`HarnessToolsR10M`'s `pkg_list` returned `status: "error"` /
`evt.ex.fr.type;type.ref.frame` for *every* valid ordinal over the wire
([`…-pkg-list-1-r10m-bug.txt`](../runtime/evidence/toolsround-r10m-wire-pkg-list-1-r10m-bug.txt),
[`…-pkg-list-38-r10m-bug.txt`](../runtime/evidence/toolsround-r10m-wire-pkg-list-38-r10m-bug.txt)),
while `:PkgEntry(1, 38)` called directly through `ns_eval` returned
`"1/38 ScreenBuffer|428|?"`. The cause, proven on instance `c2round`:

```
runtime/ns_eval.py --instance c2round 'ClassOf(StringToNumber("1"))'
  -> 'Real
runtime/ns_eval.py --instance c2round \
  'begin local r := "ok"; try r := "" & GetPackages()[StringToNumber("1") - 1].title
   onexception |evt| do r := "EX " & CurrentException().name; r end'
  -> "EX evt.ex.fr.type;type.ref.frame"
```

`Dispatch` gets `args.id` as a **string token** off the wire and converts it
with `StringToNumber`, which on this ROM yields a `Real` even for `"1"`.
`1.0 - 1` is `0.0`, and **indexing an array with a `Real` throws
`evt.ex.fr.type;type.ref.frame`** ("expected a frame") rather than any
index-flavoured exception, which is why the error text is so misleading.

`get_note` escapes the same bug by luck of implementation: it never indexes
with the ordinal, it drives `for position := 1 to ordinal`, and a `for` limit
accepts a `Real` happily. That is why the twelfth finding's ordinal work
passed its wire round and `pkg_list` did not.

The fix in `R10N` is one line at the dispatch site
(`examples/harness-tools/Main.newt`, `pkg_list` branch):

```newtonscript
if ordinal = nil then ordinal := 0 else ordinal := Floor(ordinal);
```

`Floor` is applied *after* the nil guard because `Floor(nil)` throws. **Any
future op that turns a wire argument into an array index must do the same.**

### A cosmetic anomaly worth knowing

On the seeded flash the `protoFloatNGo` window never painted, even though the
package was fully alive: `Visible()` returned `TRUE`, `viewCObject` was
non-nil, `viewBounds` was the expected `220,34,316,72`, `:Dirty()` +
`RefreshViews()` changed nothing — and it answered every request on the link.
Do not use "I can see the float" as the liveness test; use the broker's
`Newton tools connected` line. The Extras drawer screenshot
([`toolsround-r10m-wire-screen.png`](../runtime/evidence/toolsround-r10m-wire-screen.png))
is the installation evidence for this round instead.

### Which system calls these use, and which are traps

Checked against `refs/NewtonProgrammerRef20.txt` before any code was written,
per the repo's `[verify]`-first convention:

- **`BatteryLevel` is documented-obsolete** — the Newton Programmer's Guide says
  so outright at `refs/NewtonProgrammerGuide20.txt:37895-37896`. Do not use it.
  `PowerStatus`, `GetPowerStatus`, `BatteryRawStatus`, and Gestalt battery
  selectors have **zero hits** anywhere in `refs/`; they do not exist.
- The verified pair is **`BatteryCount()`** and **`BatteryStatus(which)`**
  (`refs/NewtonProgrammerRef20.txt:41816-41919`; Guide `39015-39024`,
  `39166-39167`), where `which` is 0 for the primary pack and 1 for the backup.
  The status frame carries `batteryCapacity` (integer percent — this, not any
  `BatteryLevel`, is the level field), `chargeState` and `acPower` and
  `batteryType` (symbols, *or* integers if the driver returned something else),
  and `batteryVoltage` / `acVoltage` / `chargeCurrent` / temperatures as
  **reals**. The reference states plainly that **any slot may be `nil`** when
  "the underlying hardware cannot supply this information". The op therefore
  nil-guards every slot and prints `?` for a missing one, renders symbols with
  the proven `"" & sym` idiom, and emits no reals — `NumStr` floors a non-integer
  rather than spilling a long decimal onto the wire.
- **`store_info`** uses `GetStores()` (`refs/NewtonProgrammerRef20.txt:32710-32720`;
  element 0 is always the internal store), `store:GetName()` (`:32664-32669`),
  and `store:TotalSize()` / `store:UsedSize()` (`:32834-32846`). There is **no
  `FreeSize` method** — free is computed as total minus used. `store:IsReadOnly()`
  is the store method; do not confuse it with the unrelated global
  `IsReadOnly(obj)` (`:64323-64336`). `GetStores`/`GetName` were already proven
  on this ROM (`examples/harness-tools/Main.newt` `NoteProbeSteps`/`GetNote`);
  `TotalSize`/`UsedSize`/`IsReadOnly` are documented-2.0 and remain `[verify]`.
- **`pkg_list`** uses `GetPackages()` (`refs/NewtonProgrammerRef20.txt:31996-32039`),
  which returns an array of frames with `{id, size, title, store, version,
  timeStamp, copyProtection}`. Two traps: its `size` is **uncompressed** bytes,
  so it will *not* match the compressed Dock byte counts in
  `docs/installed-package-inventory.md`; and the physical MP2000 holds 83
  packages, so dumping the array in one reply would violate the small-ASCII-reply
  constraint and risk the event-loop starvation of the twelfth finding above.
  The op is therefore paged with the same 1-based-ordinal shape `get_note` uses,
  and `store` is a store reference that must be rendered via `pkg.store:GetName()`.
  `GetPackages` cannot be called from an `InstallScript`/`RemoveScript` — the
  installer is not reentrant — which does not affect the tools client but is
  worth recording for Track C5.

### A fresh emulator instance is not network-ready

Discovered while trying to run the acceptance round in an isolated instance, and
not previously written down anywhere: `make emulator-instance-up INSTANCE=<name>`
gives you a **blank Newton flash**, which means

1. the ROM boots into the first-run Welcome tour, which suppresses the tools
   client's `protoFloatNGo` window even though `GetRoot().|HarnessToolsR10N:jbfly|`
   exists and `:Open()` returns `TRUE` — the tour has to be clicked through
   (name, country, address, phones, date, time, handwriting, signature, Done)
   before the float will appear;
2. none of the NIE stack in `runtime/nie2/` is installed, so there is no
   Ethernet driver and no saved Internet Setup for `InetGrabLink` to use.
   (`InetGrabLink` itself *is* in the 717006 ROM — `GetGlobalFn('InetGrabLink)`
   returns non-nil on a blank flash.) The working long-lived emulator has
   `Untitled Ethernet Setup` / `PCMCIA Ethernet` configured
   (`docs/newton-dev-notes.md:450`); a fresh instance does not.

Two mechanics matter when installing that stack: `POST /install` only accepts
paths under `/packages/`, i.e. the repo's `examples/` mount
(`containers/patches/einstein-control-socket.patch:119-124`), so the packages in
`runtime/nie2/` must be staged into `examples/` first; and **`newtdev.pkg`
(Newton Device Drivers) must be installed before `NE2K.pkg`**, otherwise the
driver installs but refuses to activate with `Unable to activate NE2K since
Newton Device Drivers are not in the system`.

### The host-address precondition (resolved, but still a precondition)

`examples/harness-tools/Main.newt:72` hardcodes the broker at `10.42.0.1:18081`
with no runtime override, and `runtime/raw_pkg_server.py` binds that literal
address, so the host must have `10.42.0.1/24` on `lo` before any of this can be
exercised. Check with `ip addr show lo | grep 10.42.0.1`; add it with
`sudo ap/emulator-only.sh`. This was the blocker that stopped the first attempt
at the round; it was satisfied for the 2026-08-03 wire round above.

### Seeding an instance's flash instead of building one (the fast path)

The manual route described above — click through the tour, stage
`runtime/nie2/` into `examples/`, install `newtdev.pkg` then `NE2K.pkg`, then
configure Internet Setup by hand — was **not needed** for the wire round and
should not be needed again. A saved flash that already has the NIE stack and a
saved `Untitled Ethernet Setup` can simply be copied into a fresh instance's
state volume; the full recipe is in `docs/parallel-emulators.md`
("Seed an instance from a saved flash"). It cost about 90 seconds and booted
straight into the Notepad with the `PCMCIA Ethernet` card recognised.

Note that `runtime/emulators/mp2000-core-20260803/internal.flash` is **not** a
suitable seed — it is a blank flash restored with core packages over Dock and
contains no `NE2K` at all (`strings -a … | grep -c NE2K` → `0`), which
`docs/installed-package-inventory.md:167-171` records but does not spell out.

## Fifteenth finding: `note_list`, and `get_note` v2 (Track C4)

`HarnessToolsR10P:jbfly` adds `note_list` and hardens `get_note`. As with
C1–C3 no host-side change was needed: `POST /tools` forwards any
`TOOL_OP`-matching name and only validates that `args.id` is an integer
(`pkg_publisher.py:354-386`). Proven over the wire on isolated instance
`c4round`, 2026-08-03 — the broker logged
`Newton tools connected 10.42.0.1:57652` and every call below travelled the
long-poll. Full `curl -i` transcripts are `runtime/evidence/c4round-*.txt`
(summary table in
[`c4round-wire-summary.txt`](../runtime/evidence/c4round-wire-summary.txt)),
the three created notes are photographed in stock Notepad at
[`c4round-screen.png`](../runtime/evidence/c4round-screen.png), and the ROM
probes are in [`c4round-nseval.txt`](../runtime/evidence/c4round-nseval.txt).

| op | args | reply shape | status |
|---|---|---|---|
| `note_list` | optional `id` (1-based ordinal) | no `id` or `id=0` → `count=N`; valid `id` → `i/N <label>\|<timeStamp>`; out of range → `status: "error"`, `note ordinal must be 1..min(N,64)` | **proven over the wire** in `R10P` |
| `get_note` | `id` (1-based ordinal, 1..64) | unchanged: the note's paragraph text, or `""` | **proven over the wire** in `R10P`; reply shape identical to `R10N` |

`<label>` is the entry's `title` when it has one, otherwise the first 32
characters of its text with `…` appended, with newlines, tabs and `|` mapped to
spaces so the one field separator stays unambiguous; an entry with neither is
`(untitled)`. `<timeStamp>` is the raw Notepad stamp — **minutes since
1904-01-01**, not seconds and not a date string (`docs/notes-bridge.md:27`).

Wire replies, ~0.8 s each on the warm link (`ping` 0.127 s):

| request | wire reply | HTTP |
|---|---|---:|
| `{"op":"note_list"}` | `"count=6"` | 200 |
| `{"op":"note_list","args":{"id":1}}` | `"1/6 (untitled)\|64461125"` | 200 |
| `{"op":"note_list","args":{"id":4}}` | `"4/6 C4 alpha note about batteries\|64477198"` | 200 |
| `{"op":"note_list","args":{"id":6}}` | `"6/6 C4 charlie note that is delibera...\|64477198"` | 200 |
| `{"op":"note_list","args":{"id":7}}` | `status: "error"`, `"note ordinal must be 1..6"` | 422 |
| `{"op":"note_list","args":{"id":99}}` | `status: "error"`, `"note ordinal must be 1..6"` | 422 |
| `{"op":"get_note","args":{"id":6}}` | the whole 89-character note | 200 |
| `{"op":"get_note","args":{"id":1}}` | `""` | 200 |

Four things the round settled:

1. **`cursor:CountEntries()` works on this ROM** and is what `note_list` counts
   with (`refs/NewtonProgrammerRef20.txt:34215-34243`). It walks the *index*,
   not the entries, so it does not reintroduce the twelfth finding's
   event-loop starvation the way R10I's full-soup entry scan did. The
   reference still warns that counting a large soup costs heap and time, so
   `count` remains the one unpaged number the op will ever return; every
   listing line is a separate request, and ordinals stay capped at 64 exactly
   like `get_note`'s.
2. **A nil `title` is the normal case, not the exception.** Every entry in the
   seeded flash had `ClassOf(GetSysEntryData(entry, 'title))` =
   `weird_immediate`, i.e. `nil` — the same rendering `pkg_list`'s `store` slot
   has in the thirteenth finding. A `note_list` that printed `title` unguarded
   would have printed nothing useful on any note the user has not explicitly
   named, which is most of them. Hence the first-characters fallback.
3. **`ns_eval` cannot see NTK platform constants.** Probing
   `store:HasSoup(ROM_paperRollSoupName)` through `runtime/ns_eval.py` throws
   `evt.ex.fr.intrp;type.ref.frame`, because `ROM_paperRollSoupName` is a
   *compile-time* symbol NTK resolves out of
   `~/newton-dev/ntk-platform-files`, and injected NewtonScript is never
   compiled by NTK — the name is simply unbound, so `HasSoup(nil)` throws.
   Probe with the literal (`GetSoupNames()` on this ROM proves
   `ROM_paperRollSoupName` is `"Notes"`); keep the constant in package source.
   This is the second way `ns_eval` differs from the dispatch path, after the
   fourteenth finding's string-vs-integer argument.
4. **Empty is a real answer, and both ops agree on it.** The three Notepad
   entries carried in the seed flash all have `data = nil` — they are the
   failed-write garbage `docs/notes-bridge.md` diagnosed in N2/N3, preserved by
   the snapshot. `note_list` labels them `(untitled)` and `get_note` returns
   `""`; neither throws, and the pair is consistent, which is what makes an
   empty `get_note` readable as "this note has no text" rather than "the
   ordinal was wrong".

`get_note` v2 is a hardening, not a reshape. Its dispatch now nil-guards a
missing argument and `Floor`s the ordinal like `pkg_list` does — a `get_note`
with no `id` used to reach `StringToNumber(nil)` and answer with a raw Newton
exception name, and the fourteenth finding's rule ("any wire argument that
becomes an array index must be `Floor`ed") now holds at every dispatch site
whether or not the current implementation happens to index with it. The cursor
walk itself is unchanged R10J code, lifted into a shared `NoteAt(ordinal)` that
both ops call, so `note_list` cannot drift away from what `get_note` reads.

## Sixteenth finding: `ResetToEnd` lands *on* the last entry (Track F2)

The idiom `examples/note-export` used to find the newest note —

```newtonscript
cursor:ResetToEnd();
local entry := cursor:Prev();
```

— reads the **second** newest entry on this ROM. `ResetToEnd` positions the
cursor on the last entry *and returns it*; `Prev` then steps back one. Measured
on instance `f2round` against a Notepad soup holding four entries
(`0/64461125/nil 1/64462106/nil 2/64464021/nil 3/64477232/1`, the three
`data=nil` seed notes plus one real one):

```text
local c := GetUnionSoupAlways("Notes"):Query({indexPath: 'timeStamp});
local a := c:ResetToEnd(); local b := c:Entry();
"reset=" & EntryUniqueID(a) & " entry=" & EntryUniqueID(b)
=> "reset=3 entry=3"

... while the same cursor's c:Prev() answered with entry 2.
```

Use `local entry := cursor:ResetToEnd();`. The two symptoms this produced are
worth recognising because neither looks like a cursor bug: reading the newest
note returned a `data=nil` seed entry and the client said "Newest note has no
text" (`runtime/evidence/f2round-03-asknote.png`), and a create-then-read-back
reported `Saved note id=3` for an entry that was really `id=4`
(`runtime/evidence/f2round-08-savenote.png`). After the one-line fix the
on-screen id matched an independent `ns_eval` read of the soup twice, at id 6
and id 8.

`examples/harness-tools` is **not** affected: `NoteAt(ordinal)` starts from
`cursor:Entry()` and merges forward with `Next()` across stores
(`examples/harness-tools/Main.newt:630-660`), and never calls `ResetToEnd` or
`Prev` at all. The affected code was `NoteExportN13`'s `ReadOne` and `Create`,
which Track F2 replaced.

Related, and the reason this took a rebuild to find rather than an `ns_eval`
probe: the probe that would have caught it needs the *literal* `"Notes"` soup
name, since `ROM_paperRollSoupName` is an NTK compile-time symbol that `ns_eval`
cannot see (fifteenth finding).

## Seventeenth finding: sketch notes, and how to get the strokes out (Track I3)

**Sketch geometry is extractable, exactly, and every stroke survives.** This
settles the `[verify]` that Track I3 has carried since it was written
("probe with `note_probe`/ns_eval on a hand-drawn sketch note first; nobody has
looked yet") and it is the evidence base for the "Ask Sketch" pivot in
`docs/ink-client-design.md`. Measured on isolated instance `sketchprobe`
(seeded flash, ROM 717006). Full transcript with every probe and its verbatim
answer: [`sketchprobe-probe.txt`](../runtime/evidence/sketchprobe-probe.txt).

### There is no sketch stationery — there is a drawing *mode*

The Notes `+New` picker offers only **Note / Checklist / Outline / Recording**
([`sketchprobe-02-new-picker.png`](../runtime/evidence/sketchprobe-02-new-picker.png)),
which matches the reference exactly — *"The Notes application includes three
types of built-in stationery: notes, outlines, and checklists"*
(`refs/NewtonProgrammerGuide20.txt:42614-42616`; the three are itemised at
`:42627`, `:42631`, `:42635`).
A "sketch note" is an ordinary `class 'paperroll` note that happens to contain
drawn objects.

What you actually switch is the **recognition mode**, from the `A` button in
the Notes bottom bar at screen `(30, 425)`. Its popup
([`sketchprobe-05-styles.png`](../runtime/evidence/sketchprobe-05-styles.png))
is the whole drawing UI, and these are the tap coordinates:

| Mode | Tap | What it stores |
|---|---|---|
| Text | `(88, 354)` | a `'para` object |
| Ink Text | `(88, 369)` | ink text (`'inkWord`) |
| Shapes | `(88, 387)` | a cleaned-up `'poly` object |
| **Sketches** | `(88, 402)` | **freehand `'ink2` sketching ink** |
| Preferences | `(88, 422)` | — |

Selecting Sketches swaps the `A` glyph for a pen squiggle, which is the only
on-screen confirmation you get
([`sketchprobe-06-sketches-mode.png`](../runtime/evidence/sketchprobe-06-sketches-mode.png)).

### The soup shape

The entry itself is unremarkable — nothing at entry level says "sketch":

```text
id=3 class=paperroll slots=viewStationery:symbol class:symbol height:int
 data:Array timestamp:int _version:int _modTime:int _uniqueID:int
```

The kinds live in `data`, one item **per pen stroke**. On the mixed probe note
— five freehand strokes, four shape-recognised strokes, one typed paragraph —
the ten items classified as:

```text
n=10 0=ink2 1=ink2 2=ink2 3=ink2 4=ink2 5=poly 6=poly 7=poly 8=poly 9=para
```

| Kind | Slots on this ROM | Reference |
|---|---|---|
| freehand | `ink:ink2 viewBounds:frame _proto:frame` — **no `viewStationery`** | `refs/NewtonProgrammerRef20.txt:47843-47852` — *"The ink object frames have these slots: `ink` … `viewBounds` … `timeStamp`"* |
| shape | `viewStationery:'poly viewBounds:frame points:polygonshape _proto:frame` | `refs/NewtonProgrammerRef20.txt:47835-47842` |
| text | `viewStationery:'para viewBounds:frame text:…` | `refs/NewtonProgrammerRef20.txt:47808-47820` |

Two ROM-vs-reference differences: the ink binary's class is **`'ink2`**, not the
documented `'ink` — `InkConvert`'s own parameter list settles what that means,
`'ink2` being *"converted to 2.x sketching ink"* against `'ink` for
*"1.x-compatible ink"* and `'inkword` for *"2.x ink text"*
(`refs/NewtonProgrammerRef20.txt:30147-30158`) — and the ink items carry **no
`timeStamp`** but do carry an undocumented `_proto`.

### `ExpandInk` cracks `'ink2`, and it takes the soup frame directly

This was the load-bearing unknown and it is settled. The reference describes
`ExpandInk(poly, format)` as taking "a `clPolygonView`, which is stored as a
child of a `clEditView` and has an `ink` slot"
(`refs/NewtonProgrammerRef20.txt:29948-29968`), which reads like it needs a
live view. **It does not.** Handed the raw soup data frame it returns a stroke
bundle:

```text
polyContainsInk= expand=strokeBundle slots=class:symbol bounds:frame strokes:Array
```

`PolyContainsInk` returns `nil` on the same frame — *that* one really does want
a live view — so do not use it as the gate. Test `ClassOf(item.ink) = 'ink2`.

The full chain, all four calls proven on this ROM:

```newtonscript
local bundle := ExpandInk(item, 0);              // 0 = screen resolution
local n      := CountStrokes(bundle);
local stroke := GetStroke(bundle, i);
local points := GetStrokePointsArray(stroke, 0); // flat, alternating Y,X
```

`format` `0` is "screen resolution, filter out duplicate points"
(Table 8-6, `refs/NewtonProgrammerRef20.txt:27098-27125`); `2`/`3` give tablet
resolution, which is for recognition, not for us. The point array is the same
Y-then-X structure `GetPointsArray` returns
(`refs/NewtonProgrammerRef20.txt:27164-27171`), so the Stage 5 pair-swap rule
applies unchanged. Also live and useful: `CountPoints(stroke)`
(`refs/NewtonProgrammerRef20.txt:30018-30023`) and `GetStrokeBounds(stroke)`
(`:30065-30071`).

Three API names that look plausible and are **not** the path:
`GetInkWordInfo` returns font metrics for an ink *word*
(`refs/NewtonProgrammerRef20.txt:25333-25352`), not sketch geometry; `InkOff`
merely stops the inker drawing during capture (`:29606-29609`); and
`PointsToArray` on a sketch item returns an empty polygon (see the trap below).

### The extraction, cross-checked against where the pen went

Three strokes were dragged at known screen coordinates and read back:

| Stroke | Dragged (screen) | Stored (note space) | Points | Delta |
|---|---|---|---:|---|
| vertical | `(60,120) → (60,220)` | `(60,84) → (60,184)` | 17 | `0, -36` |
| diagonal | `(100,120) → (180,220)` | `(100,84) → (180,185)` | 89 | `0, -36` |
| horizontal | `(210,140) → (280,140)` | `(210,104) → (280,104)` | 17 | `0, -36` |

X is exact and Y is off by **one constant, 36, for every stroke**: the
coordinates are the paper roll's own space, not screen space, and 36 is where
this note happened to sit under the current scroll. Every stroke in a note
shares that space, so a host renderer normalises against the note's own
bounding box and never has to know the offset. The raw dump of the first
stroke, for the record:

```text
nstrokes=1 npoints=17 alen=34
pts=84 60 94 60 103 60 111 60 117 60 122 60 126 60 130 60 134 60 138 60
     142 60 146 60 151 60 157 60 165 60 174 60 184 60
```

### Every stroke survives — this is the whole point of the pivot

Five pen strokes, including two that physically cross, produced five separate
items each holding exactly one stroke:

```text
dlen=5 [0] inkbytes=10 ns=1 np=17, | [1] inkbytes=24 ns=1 np=89, |
       [2] inkbytes=9  ns=1 np=17, | [3] inkbytes=22 ns=1 np=74, |
       [4] inkbytes=24 ns=1 np=74, |
```

271 points in **89 bytes** of compressed ink. Nothing merged and nothing was
dropped — which is exactly what the client's own InkPad-derived canvas failed
to do on hardware (`docs/ROADMAP.md` status log, first full-stack hardware
test, finding 5). Screenshots:
[`sketchprobe-07-drawn.png`](../runtime/evidence/sketchprobe-07-drawn.png) (three
strokes),
[`sketchprobe-10-cross.png`](../runtime/evidence/sketchprobe-10-cross.png) (five,
with the X),
[`sketchprobe-13-mixed.png`](../runtime/evidence/sketchprobe-13-mixed.png) (the
mixed note).

### The `_proto` trap

Every ink item's `_proto` is a `clPolygonView` template that carries **its own
`points` binary**:

```text
inkclass=ink2 inklen=10 vb=58,82,63,186
protoslots=viewClass:int viewFlags:int viewFormat:int points:polygonshape debug:int
```

So `item.points` resolves through the proto chain on a *sketch* item and hands
you a degenerate polygon — `PointsToArray` on all three read `14 0`, meaning
shape type 14 with **zero** points. A classifier that tests `points` before
`viewStationery` will silently report every freehand stroke as an empty shape.
Test in this order: `viewStationery = 'para`, then `'poly`, then `'pict`, then
`ClassOf(item.ink) = 'ink2`.

### Shapes mode is a different, simpler shape — and a coordinate trap

A hand-drawn box in Shapes mode was cleaned into four *separate* 2-point line
shapes, not one rectangle:

```text
[5] vb=200,214,290,215 arr=8 2 0 0 90 0  |
[6] vb=290,214,291,294 arr=8 2 0 0 0 80  |
[7] vb=200,294,290,295 arr=8 2 90 0 0 0  |
[8] vb=200,214,201,294 arr=8 2 0 80 0 0  |
```

`PointsToArray` gives `[shapeType, nPoints, x1,y1, …]`
(`refs/NewtonProgrammerRef20.txt:37811-37846`). Adding `viewBounds.left/top`
to each pair reproduces the four drags exactly, with the same `0,-36` offset.

**The two kinds disagree about coordinates, and both disagree with each other's
axis order:**

| | Origin | Pair order |
|---|---|---|
| `'poly` via `PointsToArray` | **relative** to the item's `viewBounds` | **x, y** |
| `'ink2` via `ExpandInk` + `GetStrokePointsArray` | **absolute** in the note's space | **y, x** |

Getting either one backwards produces geometry that is plausible-looking and
wrong, which is the expensive kind of bug.

### Ink Text is a fourth case, and it hides inside a paragraph

The `A` menu's other ink mode does **not** add a `data` item. Two strokes
written in Ink Text left the array at ten and went into the existing `'para`
item instead:

```text
slots=viewStationery:symbol viewBounds:frame text:string _proto:frame styles:Array
styles n=8  0=int 1=int 2=int 3=inkWord 4=int 5=int 6=int 7=inkWord
codes=110 111 116 101 32 112 114 111 98 101 32 63233 32 63233
```

`text` is a plain string carrying placeholder character **63233 (0xF701)** once
per ink word, and `styles` is the usual alternating `[runLength, style]` array
whose style for an ink run is a binary of class `'inkWord`. Two consequences:

1. **A text-only extractor puts 63233 straight into the prompt.** That is a
   live defect in `examples/harness-client/Main.newt:683-689`, which reads
   `item.text` and cleans it without knowing about the placeholder.
2. **It expands too**, via the same bridge as the inverse path below, with
   `GetInkWordInfo` supplying the bounds `ExpandInk` needs:

```text
class=inkWord len=22 w=52 asc=7 desc=0 conv=ink2 ns=1 np=46
```

So all three ink representations on this ROM are extractable, and this is the
one place `GetInkWordInfo` is the right call rather than a decoy:

| Mode | Stored as | Extract with |
|---|---|---|
| Sketches | `'ink2` in its own data item | `ExpandInk(item, 0)` |
| Shapes | `'poly` with a `points` binary | `PointsToArray(item.points)` |
| Ink Text | `'inkWord` inside a `'para`'s `styles` | `InkConvert(w, 'ink2)` → `ExpandInk`, bounds from `GetInkWordInfo` |

### The inverse direction works too (Track I3's write half)

Not needed for Ask Sketch, but it is the other half of I3 and it was one probe
away, so: a host-supplied point array round-trips into native sketching ink.

```text
MakeStrokeBundle([[10,10,20,20,30,30,40,40]], 0) -> strokeBundle, ns=1 np=4
CompressStrokes(bundle)                          -> frame {ink:inkWord, viewBounds:frame}
InkConvert(p.ink, 'ink2)                         -> ink2, 8 bytes
ExpandInk({ink: i2, viewBounds: p.viewBounds}, 0) -> ns=1 np=17
  pts=10 10 13 13 16 16 18 18 20 20 21 21 23 23 24 24 25 25 26 26 27 27
       29 29 30 30 32 32 34 34 37 37 40 40
```

`CompressStrokes` (`refs/NewtonProgrammerRef20.txt:30010-30016`) returns
exactly the `{ink, viewBounds}` frame a note's `data` array holds, but as
`'inkWord` — 2.x ink *text* — so `InkConvert(…, 'ink2)` is a required step, not
an optional one. Points in at `(10,10)…(40,40)`, same endpoints back out,
interpolated to 17. `MakeStrokeBundle` is at `:30160-30175`.

### "Newest note" is not what `timeStamp` says

Walking the whole soup, with `EntryModTime` beside the creation stamp:

```text
id0 ts=64461125 mod=64461125 n=-1 | id1 ts=64462106 mod=64462106 n=-1 |
id2 ts=64464021 mod=64464021 n=-1 | id3 ts=64477370 mod=64477379 n=10 |
```

The sketch note's two stamps are **nine minutes apart**: drawing updates
`EntryModTime` and never touches `timeStamp`, which is creation time
(`docs/notes-bridge.md:41-42`). So a drawing added to an existing page never
becomes "newest" under `Query({indexPath: 'timeStamp})` — the index
`examples/harness-client/Main.newt:677` orders by. And the obvious fix is not
available:

```text
GetUnionSoupAlways("Notes"):Query({indexPath: '_modTime})
  -> EX evt.ex.fr.store
```

**There is no modification-time index on the Notes soup on this ROM.** Finding
the most recently *touched* note therefore means comparing `EntryModTime`
yourself, which must be bounded — see the design in
`docs/ink-client-design.md`, "Sketch-note pivot". (The three `n=-1` entries are
the seed flash's `data=nil` failed writes, `docs/notes-bridge.md` N2/N3.)

### Two operational notes

`ExpandInk` needs no live view and no frontmost Notes: the section-5 probe was
re-run with the Extras drawer open over Notes
([`sketchprobe-12-extras.png`](../runtime/evidence/sketchprobe-12-extras.png))
and returned byte-identical output. A tools op can read a sketch while the chat
client owns the screen.

A modal `Sorry, a problem has occurred. (-48601)` appeared once mid-drawing and
**swallowed the two strokes issued while it was up**
([`sketchprobe-08-cross.png`](../runtime/evidence/sketchprobe-08-cross.png));
dismissing it and redrawing worked. The seed flash is already documented as
throwing `-48807`/`-48601` (`docs/parallel-emulators.md`), so this is that same
noise rather than anything about sketches — but it is a reminder that an alert
can eat pen input on this ROM.

Honest limit on the measurement: `emulator/control.py:185`'s `/drag` is
start-to-end only, so every probe stroke is a straight line. The digitizer still
sampled 17-89 points per stroke, so the capture and storage mechanism is the
one a freehand curve uses; only the drawn shapes are simpler than a human's.

## Eighteenth finding: a `protoFloatNGo` app never receives the scroll arrows (Track A8)

The Newton's own scroll arrows — the button-bar pair a user reaches without
typing — cannot be used by the chat client, and one `ns_eval` line proves it
rather than inferring it.

`ViewScrollUpScript` / `ViewScrollDownScript` are only ever sent to a view with
`vApplication` set: "when the user taps the scroll arrows, the system searches
all views to find the frontmost view that has this bit set, and then sends the
scroll event to that view" (`refs/NewtonProgrammerRef20.txt:3193-3199`, where
Table 2-2 also gives `vApplication` = **4**). The requirement is repeated in the
method descriptions themselves (`:7338`, `:7373`).

Measured on the live Chat A8 window:

```
runtime/ns_eval.py --instance a8scroll 'GetRoot().|HarnessClientA8:jbfly|.viewFlags'
-> 576
```

576 = 512 + 64 = `vClickable` + `vFloating`. Bit 4 is clear, so this window is
not an application view, and tapping the arrows on screen changed nothing.
`protoFloatNGo` is the proto every app in this repo uses, so the rule
generalises: **a floating harness app has to supply its own scroll control.**
Chat A8 does, with two `protoTextButton`s that page a row window.

**Answered 2026-08-04 (Track L1): adding `vApplication` does not help.** The
experiment this paragraph asked for was run on instance `efround` and the answer
is no, so nobody needs to run it again:

| Step | Result |
|---|---|
| Ship `viewFlags: 580` (`vFloating` + `vClickable` + `vApplication`) | live window reads **581**, the ROM adding `vVisible` — the flag is really set |
| Parent chain requirement (`refs/NewtonProgrammerGuide20.txt:8394-8396`) | satisfied: `GetRoot()` reads `viewFlags` **5** = `vVisible` + `vApplication` |
| `ViewScrollUpScript` / `ViewScrollDownScript` / `ViewOverviewScript` supplied and called directly | works — `scrollRow` 0 → 10 |
| Tap the ROM's up arrow at `(309,461)` with the window frontmost | **nothing at all**: zero changed pixels, `scrollRow` still 0 |
| Same tap with the window closed | the Notepad scrolls (~1,800 changed pixels) — so the hit point is right |

The mechanism was in the Reference the whole time. Scroll routing resolves the
target the way `'viewFrontMostApp` does, and that symbol returns "the frontmost
view on the screen that has the `vApplication` flag set in its `viewFlags` slot,
**but not including floating views** (those with `vFloating` set in their
`viewFlags` slot)" (`refs/NewtonProgrammerRef20.txt:4510-4512`). A floating
window is excluded *by definition*, flag or no flag. The same exclusion shows up
from the other side in the merged client: with the Egg Freckles window open and
frontmost, its own `front_app` op still answers `Notepad (paperroll)`.

So the eighteenth finding's rule is stronger than it was, not weaker: **a
floating harness app cannot have the ROM's scroll arrows, and no view flag will
give them to it.** The flag was reverted (the shipped window is back to the
proto default) and the three scripts were deleted rather than shipped dead. The
transcript keeps its own Up/Dn buttons. Apple's own advice points the same way:
"For the base view of an application, it is recommended that you use
protoDragger instead of protoFloater. The floating property interferes with some
system services for applications" (`:21606-21609`) — which is the real, larger
experiment nobody has run: build the app on `protoDragger` and see what else
changes.

## Twentieth finding: the clock lies, and `EntryUniqueID` does not (Track L1)

The human's MessagePad had its date set to 2008 and then corrected. That is not
a curiosity: it silently breaks every "newest note" rule built on a date, and it
is why `Ask` sent the wrong note on hardware **twice** — the second time even
after Track A9 had switched from `timeStamp` to `EntryModTime`.

### Why A9's fix was not enough

A9 scanned sixteen entries back from the **end of the `timeStamp` cursor** and
took the largest `EntryModTime`. Both halves of that trust the clock. A note
written while the clock said 2008 gets a 2008 `timeStamp`, which puts it at the
**front** of the index — outside a window that starts at the back — and a 2008
`EntryModTime` to match, which loses every comparison. The note is invisible to
the rule twice over. Months-old D&D notes win, exactly as reported.

Reproduced by construction on instance `efround` and both rules run over the
same 25-entry soup ([`efround-ordering.txt`](../runtime/evidence/efround-ordering.txt)):

```text
A9 rule (timeStamp cursor, max EntryModTime) picks id=23 mod=64478106 text=EF dnd session 18
EF1 rule (_uniqueID cursor, max EntryUniqueID) picks id=24 ts=54919320 text=EF cat drawing page
```

`id=24` is the "cat", created last and stamped 2008-06-01. The old rule cannot
see it; the new rule cannot miss it.

### `_uniqueID` is a queryable index on this ROM

Undocumented as a query path — the manuals mention `_uniqueID` exactly twice and
never in a query — but it works, and it is the one index the ROM refuses to let
you drop (error `-48023`, "Tried to call RemoveIndex on the `_uniqueID` index",
`refs/NewtonProgrammerRef20.txt:74421`):

```text
GetUnionSoupAlways("Notes"):Query({indexPath: '_uniqueID})   -> uidq=ok
```

Cursor order is allocation order, measured: consecutive `NewNote` calls on the
seeded flash returned ids 3, 4, 5, … 24, 25, and `ResetToEnd()` on that cursor
lands on the note just created. `EntryUniqueID` reads it "without reading the
entry into the cache" (`:34872`), so a bounded scan is cheap.

**What the manuals actually promise is less than that**, and the honest reading
matters: they define the ID only as "the value that identifies the specified
entry to the system" (`:34871-34872`) and never promise monotonicity or
non-reuse. The nearest thing to a contract is `soup:GetNextUid()` — "the unique
identifier to be assigned to the next entry added to the soup" (`:33348`) —
which is a counter by construction. So the rule rests on a documented counter
plus a measurement, not on a documented ordering guarantee. If a future ROM or a
restore reuses IDs, this breaks; nothing else available on the device is any
better, and everything date-based is already known to be worse.

### The shipped rule, and what it costs

`FindNewest` takes the **highest `EntryUniqueID`** in the last `scanLimit`
entries of the `_uniqueID` cursor, with `EntryModTime` breaking a tie only
(a union soup can interleave two stores whose ID spaces are independent), and
falls back to the `timeStamp` cursor if the ID query ever throws.

The cost is real and was accepted deliberately: **A9 could answer with an older
page you had just drawn on, and this cannot.** Between "the note you just made"
and "the page you just touched", only the first survives a broken clock, and a
broken clock is what the hardware has. Reading the *open* note (Track F3) is the
fix that needs neither.

### `SetTime` is documented, and does nothing under Einstein

Worth knowing before anyone plans a clock experiment. `SetTime(time)` "Sets the
time of the system clock", taking minutes since 1904
(`refs/NewtonProgrammerRef20.txt:50542-50548`), and `SetTimeInSeconds` is its
1993-epoch sibling (`:50554-50560`). Both resolve on this ROM. Neither moves the
clock in the emulator:

```text
runtime/ns_eval.py --instance efround 'SetTime(54919320); "after=" & Time()'
  -> "after=64478105"          (unchanged: still the host's wall clock)
```

Einstein drives the Newton's clock from the host RTC, so a poisoned-clock
scenario has to be built by construction — create the notes, then write the past
`timeStamp` onto the entry with `EntryChangeXmit`. `EntryModTime` cannot be
forged that way at all, which is why the proof above demonstrates the
*window* half of the poisoning empirically and argues the comparison half from
the fact that both stamps come off the same wrong clock.

## Twenty-first finding: modal `Communications` alerts are opt-out (Track L1)

The "Sorry, a problem has occurred" slips that the 2026-08-03 hardware test
logged as cosmetic noise (finding 3) are not something the app has to live with.
They are what the ROM does with an exception the app declined to catch:

> If no `ExceptionHandler` method is specified, the exception is passed up the
> handler chain. Exceptions that are not caught are displayed as warning
> messages to the user.
> — `refs/NewtonProgrammerRef20.txt:57321-57323`

`endpoint:ExceptionHandler(error)` is sent "whenever an exception is thrown and a
corresponding `CompletionScript` method does not exist" (`:57291-57294`). Every
`Output`/`Bind`/`connect` in this repo already carries a `CompletionScript`, so
those errors were always handled — but an **unsolicited disconnect** has no
completion script to land in, and that is precisely the case that reaches the
user as a modal slip. Egg Freckles gives all three endpoints (chat, ink, tools)
an `ExceptionHandler` that routes into the existing failure path, turning a
modal alert into a one-second reconnect.

**The second alert source is a delayed call landing on a closed view**, and it is
easy to ship by accident. `AddDelayedCall(func(view) view:ToolWatch(), [self],
4000)` reschedules a watchdog forever; when the window closes, the call already
in the queue still fires, the method is gone with the view, and the ROM shows
`-48809` — "undefined method"
(`docs/newton-networking-lessons.md` §1.4). Measured this round: closing the
window raised exactly that slip. Every `AddDelayedCall` in the client now reads

```newtonscript
AddDelayedCall(func(view) try view:ToolWatch() onexception |evt.ex| do nil, [self], 4000);
```

and closing the window is silent — verified with the tools long poll live, the
broker logging one `Newton tools disconnected` and no reconnect
([`efround-round.txt`](../runtime/evidence/efround-round.txt),
[`efround-18-closed-silent.png`](../runtime/evidence/efround-18-closed-silent.png)).

## Nineteenth finding: `EntryModTime` is coarse, and it lags (Track A9)

The eighteenth finding's neighbour. The seventeenth finding established that
`EntryModTime` is the only way to find the most recently *touched* note, since
`Query({indexPath: '_modTime})` raises `evt.ex.fr.store` on this ROM. Building
Chat A9 on top of that turned up two properties of the stamp itself that bound
how well "newest note" can ever work. Both measured on isolated instance
`a9ask`; full transcript [`a9ask-round.txt`](../runtime/evidence/a9ask-round.txt).

### It has one-minute granularity, so ties are ordinary

A note (`id5`) was drawn on in the same minute another note (`id6`) was created.
Both stamps read the same value:

```text
id6 ts=64477415 mod=64477415 | id5 ts=64477411 mod=64477415 |
```

The stamp is minutes since 1904, like `timeStamp` — `Time()` returned
`64477416` in the same probe, four digits of seconds nowhere in sight. So two
notes touched inside one minute are **indistinguishable by modification**, and
a scan that compares with strict `>` walking back from the end of the
`timeStamp` cursor leaves the later-*created* one winning. Repeating the draw
after the minute rolled over separated them cleanly (`mod=64477418` against
`64477415`), which is what the A9 proof used.

Practical reading: the hardware bug this fixes had its two notes nine minutes
apart, so the fix holds for the case it was built for. A human who creates a
text note and immediately draws on an older one, inside the same minute, still
gets the older behaviour.

### It is stale while the note is still on screen

More surprising, and more likely to bite. Immediately after a `/drag` added a
stroke, the entry's `data` array had **already grown** while its stamp had
**not** moved:

```text
(right after the drag)   now=64477418  id5 mod=64477415 n=6
(after scrolling away)   now=64477418  id5 mod=64477418 n=6
```

`Length(data)` went 5 → 6 at once; `EntryModTime` only settled once the Notepad
was scrolled off that page. The Notes app holds the open note's entry dirty and
flushes the modification stamp when it stops displaying it. Anything that reads
`EntryModTime` to decide *which* note is newest must therefore run after the
user has left the page — which the Chat A9 flow does by construction, because
opening the chat window is itself leaving it. A `/tools` op polled while the
note is still on screen would read the stale value.

### One tntk trap on the way

`local mod := EntryModTime(entry)` does not compile: `mod` is the modulo
operator. tntk reports the syntax error a dozen lines further down, at the
first line it cannot re-sync on, so the message points nowhere near the cause.
The A9 client uses `stamp`.

## Twentieth finding: the Notes Action menu takes a third-party entry, and it hands you the note (Track L2)

Track L2 asked whether a package can put "Send to AI" in the stock Notes
envelope menu. It can, on the ROM, with one array assignment — and the entry
receives the *live soup entry of the note whose envelope was tapped*, which
retires the newest-note heuristic the nineteenth finding above exists to
support. Probed on isolated instance `l2probe`, 2026-08-04; full transcript
with every command and answer in
[`runtime/evidence/l2probe-routescripts.txt`](../runtime/evidence/l2probe-routescripts.txt),
design in [`docs/notes-integration-design.md`](notes-integration-design.md).

### The stock app's array, and ours next to it

```text
GetRoot().paperroll             -> frame
Length(n.routeScripts)          -> 2
titles                          -> " <GetTitle> <GetTitle>"   (Duplicate, Delete)
```

Assigning `n.routeScripts := <old entries> + {title, icon, RouteScript}`
creates an **own slot on the RAM view frame that shadows the ROM proto**, and
the method the picker itself calls to build its list
(`view:GetRouteScripts(targetInfoFrame)`,
`refs/NewtonProgrammerRef20.txt:52547-52561`) returns it:

```text
len=3 |<GetTitle> |<GetTitle> |Send to AI
```

The real envelope menu then draws `Print Note / Fax / Beam / — / Duplicate /
Delete / Send to AI` (`runtime/evidence/l2probe-action-picker.png`). No
transport, no routing slip, no Out Box: application-defined routing actions run
immediately (`refs/NewtonProgrammerGuide20.txt:46271-46273`).

There is **no `RegNotesRouteScript`**. The only documented per-app registry is
Names-only (`kRegNamesRouteScriptFunc`, `Ref:43732-43746`); the bare
`RegRouteScript` / `UnRegRouteScript` / `extraRouteScripts` / `devRouteScripts`
symbols do exist in the 2.1 platform file but appear in neither 2.0 book and
were not probed.

### What the RouteScript receives

`RouteScript(target, targetView)` — target and targetView out of
`self:GetTargetInfo('routing)` (`Ref:51446-51450`):

```text
first note's envelope   -> fired isEntry=1 cursor=0 cls=list uid=2 stat=paperroll
second note's envelope  -> uid=3 isEntry=1 tv=1 soup=Notes nData=1 [frame]
```

`IsSoupEntry` is 1 and `TargetIsCursor` is 0: it is the **live Notes soup
entry**, not a copy, so `ExpandInk` and the rest of the seventeenth finding's
extraction apply to it directly. Two different envelopes gave two different
`uid`s with nothing else changed, so the target follows the page, not the
clock.

### Three traps in one probe

1. **`entry.data` can be nil.** `Length(target.data)` on a blank page threw
   `-48410` and `-48418` on two attempts. Guard it.
2. **`ClassOf(item) = 'para` is not a reliable test.** An item created by
   `MakeTextNote` has no class slot at all — `ClassOf` is `'frame`, slots are
   `(text, viewBounds, viewFont, _proto, viewStationery)`. Typed notes on
   hardware do carry `'para` (which is why A9's reader works), but a reader
   that only accepts `'para` will refuse to re-send a note the harness itself
   wrote.
3. **`Length()` on a string returns bytes, not characters.** "the cat sat on
   the mat" measured 46: strings are 16-bit and terminated, so `(22+1)*2`. Use
   `StrLen`.

### Folders are three documented calls, and they work

```text
AddFolder("AI", 'paperroll)     -> 'AI    (idempotent, Ref:38952-38966)
GetFolderStr('AI)               -> "AI"   (Ref:39010-39017)
GetFolderList('paperroll, nil)  -> AI,Business,Miscellaneous,personal
entry.labels := 'AI; EntryChangeXmit(entry, nil)
```

Filing *is* the `labels` slot — "Setting the value of the labels slot is really
the only 'filing' that is done" (`Guide:35418-35427`). The whole loop ran from
inside the route script: `replied uid=6 from=3 chars=46 folder=AI`, and the
note shows under the Notes "AI" tab
(`runtime/evidence/l2probe-ai-folder.png`). Limits: twelve local folders per
app, twelve global system-wide, and only the user can make global ones.
`NewNote` returns nil rather than the entry, so the just-written note is found
by re-querying and taking `ResetToEnd` (sixteenth finding).

### It is RAM-only, and it removes cleanly

```text
=== inject before reboot
"len=3"
=== after reboot (podman restart)
"len=2 |<GetTitle> |<GetTitle>"
```

The paperroll view frame is rebuilt from ROM at every reset, so the hook must
be re-applied each boot — which is precisely what an application part's
`InstallScript` is for: it "is executed when an application or auto part is
activated on the Newton **or whenever the Newton is reset**"
(`Guide:5209-5210`), with the matching rule that everything it changes must be
undone in `RemoveScript` (`:5223-5234`).

`RemoveSlot(n, 'routeScripts)` restores the ROM array exactly (`len=2`) — which
is a *hazard*, not a feature: it would also discard an entry some other package
appended after ours. Uninstall by rebuilding the array without our own frame.
