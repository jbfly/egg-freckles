# Einstein NewtonScript eval wedge on large Notes entries

Investigation date: 2026-08-07. Emulator only; no hardware. One bounded live
pass was made on isolated instance `ef13fix`, then stopped at the first timed-out
eval as required.

## Bottom line

The wedge is **not a control-socket result-size limit**. The first operation that
requires the Notes cursor to materialize the newest seeded 400-stroke entry —
`c:Next()` in the indexed cursor expression below — does not return to the
NewtonScript evaluator within 10 seconds. The requested result is only the
entry's numeric `_uniqueID`, and the result file remains absent, so execution
never reaches Einstein's result-printing primitive.

A second harness flaw turns that slow/stuck NewtonOS evaluation into a poisoned
channel: the control socket accepts every eval immediately as `queued`, unlinks
one global result file for every request, and has no request ID, busy state,
cancellation, or resynchronization. Concurrent calls can erase or consume each
other's result; after any timeout, a later call cannot know whether an older eval
is still running or whether a newly observed file belongs to it.

Do not use `ns_eval` to inspect a large ink note. Trigger the installed package
through the emulator UI (or a bounded fixed operation) and observe its host POSTs.
A durable control-channel fix needs request correlation plus a busy/poisoned
state; a host-only retry or a second socket would still enqueue work onto the
same NewtonOS event loop.

## One bounded reproduction

The full timestamped transcript is
[`runtime/evidence/emulator-nseval-wedge-pass.txt`](../runtime/evidence/emulator-nseval-wedge-pass.txt).
Every eval used both an outer 20-second process bound and `ns_eval.py --timeout
10`; the pass stopped on the first timeout.

| Step | NewtonScript source | Source bytes | Outcome | Elapsed |
|---|---|---:|---|---:|
| Trivial evaluator | `2+2` | 3 | `4` (2 stdout bytes including newline) | 444 ms |
| Store directory only | `Length(GetStores())` | 19 | `1` | 269 ms |
| Open Notes union soup | `ClassOf(GetUnionSoup("Notes"))` | 30 | `'UnionSoup` | 272 ms |
| Create descending `_uniqueID` cursor and fetch first entry | `local s:=GetUnionSoup("Notes"); local c:=s:Query({indexPath: ROM_uniqueId, order: descending}); local e:=c:Next(); e._uniqueID` | 126 | **timeout; zero stdout bytes** | 10,298 ms |

This localizes the boundary to the first full-entry cursor fetch. The union soup
itself is immediate; `GetSysEntryData(e)` and all ink expansion code are never
reached. The existing findings distinguish index-only work from entry scans:
`cursor:CountEntries()` walks the index, while a full-soup entry scan can starve
the event loop (`docs/newtonscript-eval.md:759-766`). The seeded workload is 200
ink items, 400 strokes, and 9,000 points (`docs/ef13-memory-diagnosis.md:9-15,
56-59`).

## Result size at the boundary

The timed-out expression asks Einstein to print one numeric `_uniqueID`, not the
note frame, its `data` array, strokes, or points. It produced **zero bytes**. The
control socket's synchronous reply is always the six-byte text `queued`; it does
not carry the NewtonScript value
(`containers/patches/einstein-control-socket.patch:132-136`).

Larger result capture had already worked on the same instance before this pass:
`/state/einstein-ns-result` contained a 2,223-byte, eight-part EF13 phase log.
The repository also has a 14,083-byte multi-probe transcript in
`runtime/evidence/sketchprobe-probe.txt`. Therefore neither the socket's 8,192
byte command cap nor a small result boundary explains this failure. The failure
is before result output.

## Channel behavior after the timeout

Post-timeout evidence is
[`runtime/evidence/emulator-nseval-wedge-posthang.txt`](../runtime/evidence/emulator-nseval-wedge-posthang.txt)
and
[`runtime/evidence/emulator-nseval-wedge-posthang.png`](../runtime/evidence/emulator-nseval-wedge-posthang.png):

- HTTP `/health` still returned `status: ready` and the 320x480 screenshot API
  still worked.
- `/state/einstein-control.sock` still existed.
- `/state/einstein-ns-result` did not exist: the request unlinked it before
  enqueueing and no Newton result recreated it.
- The emulator container remained alive at about 1.22% CPU and 34.86 MB memory.

These host/UI checks do not prove the NewtonOS event loop is free; they are
served by Einstein's FLTK/control process. They do prove the emulator process
and HTTP control service did not crash.

## Why prior workers became ambiguous

`runtime/ns_eval.py` sends an eval, then polls the same fixed path
`/state/einstein-ns-result` (`runtime/ns_eval.py:9-14,17-46`). The FLTK patch
unlinks that path, enqueues the eval, and replies `queued` immediately
(`containers/patches/einstein-control-socket.patch:132-136`). There is no lock
or request token on either side.

The `ef13-prove` transcript confirms two calls were accidentally in flight
together: a `GetPkgRef(...)` probe timed out while a package-root probe returned
`"agent=frame"`; later note probes were queued onto that ambiguous channel. This
is expected from the implementation: either request may unlink the other's
file, and a waiter accepts whichever complete text appears first. The 240-second
and 3,600-second worker wedges were therefore not evidence of a multi-kilobyte
reply limit; they were an expensive note fetch followed by retries/concurrency
on an uncorrelated single-result channel.

## Proposed fix

No code fix is implemented here. A safe fix crosses the Einstein C++ patch and
the Python client, and cannot be reduced to a retry without risking another
mis-correlated result.

1. **Make eval explicitly single-flight in Einstein.** Track `idle`, `busy`, and
   `poisoned` state beside the control socket. Reject a second `ns` command while
   busy instead of returning `queued`.
2. **Correlate completion.** Give each accepted eval a request ID and write its
   output to a request-specific, atomically published result (or return it on a
   request-specific socket). `ns_eval.py` must wait only for its own ID.
3. **Poison on timeout; do not retry.** Einstein exposes no cancellation or
   completion callback for `EvalNewtonScript()`; it only enqueues an event
   (`~/newton-dev/Einstein/Emulator/Platform/TPlatformManager.cpp:640-674`, also
   summarized in `docs/einstein-automation.md`, “Recommended plan”, step 6).
   After a client timeout, reject further evals until the isolated emulator is
   restarted or a real completion for that request is observed. A file lock
   alone prevents concurrency but does not resynchronize an already timed-out
   event.
4. **Keep large-note proof off this channel.** Use the app's Ask action through
   bounded UI automation and count `/ink` POSTs. For diagnostics that only need
   counts, add a bounded fixed operation that walks index metadata where
   possible and returns a small scalar; do not return or print soup entries,
   `data`, stroke bundles, or point arrays.
5. **Add regression checks.** Pin rejection of a concurrent eval, request-ID
   matching, timeout-to-poison behavior, and a stale-result file that must never
   satisfy a newer request. The live large-note test remains an isolated,
   hard-timeout integration check.

A separate Unix socket is not sufficient by itself: both sockets would still
call `TPlatformManager::EvalNewtonScript()` and enqueue onto the same NewtonOS
event path. Likewise, increasing `ns_eval.py`'s timeout only makes the wedge more
expensive and leaves result ownership ambiguous.

## What remains unknown

The one-pass bound prevents splitting the final expression into another live
`Query()`-only probe followed by a `Next()` probe. Existing behavior and the
index-vs-entry finding identify `c:Next()`/full entry materialization as the
expensive boundary, but no instruction-level NewtonOS trace was taken. It is
also unknown whether that fetch eventually completes after more than 10–20
seconds; waiting longer would not make the current uncorrelated channel safe.
