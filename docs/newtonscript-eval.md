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
frame (`examples/harness-tools/Main.newt` `Reply`).

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

What is **not** established: whether adding `vApplication` to the float
window's `viewFlags` would make the arrows work without breaking `Show`/`Hide`,
the close box, or `'viewFrontMostApp` resolution. That was not tried, and it is
the obvious next experiment for anyone who wants zero-tap scrolling.
