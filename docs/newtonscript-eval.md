# NewtonScript evaluation outcome signal

Investigation date: 2026-07-26.

## Bottom line

No reliable evaluation result channel was found in the current Einstein FLTK
transport. `/newtonscript` still returns plain text `queued\n`; success, a
Newton exception, and a dropped evaluation remain indistinguishable.

A synchronous log-backed implementation was attempted and reverted because
SCRATCH acknowledged every command but emitted no evaluator output, even after
all prescribed restart/reset recoveries. Shipping that code would have turned
all three cases into `timeout`, not provided a real outcome signal.

Full commands and observations are captured in
[`runtime/evidence/newtonscript-eval-negative.txt`](../runtime/evidence/newtonscript-eval-negative.txt).
The compliant live log capture is
[`runtime/evidence/newtonscript-eval-emulator.log`](../runtime/evidence/newtonscript-eval-emulator.log).

## Existing paths

The control socket added by
`containers/patches/einstein-control-socket.patch` calls
`TPlatformManager::EvalNewtonScript()` and immediately replies `queued`. The
call itself only enqueues a Newton event.

Einstein's Newton-side runtime appears to offer a possible output path:
`Drivers/NSRuntime/Handlers.f` prints the returned value, or writes `Exception`
and prints `CurrentException()`. Native primitive `0x1A` in
`Emulator/TNativePrimitives.cpp` forwards that text to Einstein's log/process
output. However, no such output appeared in the live tests, including for a
direct `Write()` probe sent to the Unix socket.

## Three required cases

| Case | Probe | Observed caller response | Result |
|---|---|---|---|
| Success | `2+2` | `queued` | No result; acceptance criterion not met |
| Error | `PonytailUndefinedProbe` | `queued` | No `-48807`, exception, or message; acceptance criterion not met |
| Drop/timeout | blocked/dropped evaluation | `queued` | No bounded timeout in the committed endpoint; acceptance criterion not met |

The reverted candidate correctly returned a bounded timeout for all three, but
never produced a result or error and therefore was not a valid fix.

## Remaining limitation and next foundation

The next change must add an explicit acknowledgement from the Newton-side
runtime event handler back to the host, carrying either the printed result or
exception data. Scraping Einstein output is only viable after a live successful
evaluation proves that output is emitted consistently; this investigation
could not establish that prerequisite.
