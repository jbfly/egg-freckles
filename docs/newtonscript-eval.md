# NewtonScript evaluation outcome signal

Investigation date: 2026-07-26.

## Bottom line

MAIN's NewtonScript evaluator is working, but Einstein's printed evaluation
result does not reach its container output. `/newtonscript` therefore still
returns plain text `queued\n`; success, a Newton exception, and a blocked
execution remain indistinguishable to the caller.

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
