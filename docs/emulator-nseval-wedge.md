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

The underlying flow still sends an eval and polls the same fixed path,
`/state/einstein-ns-result` (`runtime/ns_eval.py:16-19,78-103`). The FLTK patch
unlinks that path, enqueues the eval, and replies `queued` immediately
(`containers/patches/einstein-control-socket.patch:132-136`). Einstein has no
lock or request token; before Option A, the host client had neither as well.

The `ef13-prove` transcript confirms two calls were accidentally in flight
together: a `GetPkgRef(...)` probe timed out while a package-root probe returned
`"agent=frame"`; later note probes were queued onto that ambiguous channel. This
is expected from the implementation: either request may unlink the other's
file, and a waiter accepts whichever complete text appears first. The 240-second
and 3,600-second worker wedges were therefore not evidence of a multi-kilobyte
reply limit; they were an expensive note fetch followed by retries/concurrency
on an uncorrelated single-result channel.

## Option A — implemented host-side guard

Option A is implemented in `runtime/ns_eval.py`. It deliberately does not try
to repair Einstein's uncorrelated control protocol; it makes that protocol safe
to use for small, bounded probes:

1. **One eval per container.** A non-blocking `flock` keyed by container name
   covers submission and result polling. A second process is rejected with
   `NewtonScript eval already in flight ...`; it never reaches the control
   socket and therefore cannot unlink the first call's global result file.
2. **Fail closed across client death.** Before sending `ns`, the client writes a
   small per-container state file atomically. Only a successfully read result
   removes it. A timeout, lost socket reply, killed client, or other ambiguous
   exit leaves the channel marked **POISONED**, so a retry cannot consume or
   erase an old request's result.
3. **Poison lasts until restart.** The state records the container ID and
   `StartedAt` value from `podman inspect`. A later call with the same value is
   refused with an error that says to restart the isolated emulator. A changed
   value proves that container has restarted, so the stale marker is removed
   and one new eval may proceed. Do not delete the marker by hand: that would
   discard the only evidence that an old NewtonOS eval may still be queued.

Recovery is to restart only the disposable instance named in the error, wait
for it to become healthy, and then retry once:

```sh
podman restart newton-harness-<instance>_emulator_1
until [ "$(podman inspect -f '{{.State.Health.Status}}' newton-harness-<instance>_emulator_1)" = healthy ]; do sleep 5; done
runtime/ns_eval.py --instance <instance> '2+2'
```

Never restart the shared `newton-harness_emulator_1` without coordinating with
its users. Prefer an isolated instance for every eval, as required by
`docs/parallel-emulators.md`.

Tests in `test_ns_eval.py` pin concurrent rejection and timeout poisoning,
including automatic recovery only after the mocked container start identity
changes. They use no emulator.

## Proving large-note behavior: installed app plus bounded UI automation

A large or soup-touching note is not an `ns_eval` proof target. Prove it through
the installed Egg Freckles app, because that is the production path whose
memory and multipart behavior matter. The existing UI helper is
`python3 -m emulator.client`; no additional automation layer is needed.

Use this concrete procedure in a fresh isolated instance that already contains
the installed package and test note. Creating or inspecting the large note is a
separate setup step and must not use `ns_eval` during the prove pass.

1. Start the real publisher with a dedicated log, then record the baseline:

   ```sh
   LOG=runtime/evidence/<round>-publisher.log
   python3 -u pkg_publisher.py --host 10.42.0.1 --port 18081 \
     --package examples/harness-client/egg-freckles.pkg >"$LOG" 2>&1 &
   PUBLISHER_PID=$!
   before=$(grep -c '"POST /ink' "$LOG" || true)
   ```

2. Export `NEWTON_INSTANCE=<instance>`, capture a screen, use the observed
   coordinates to open the **installed** Egg Freckles app, and tap its **Ask**
   button. Do not launch the action by NewtonScript and do not inspect the Notes
   soup with `ns_eval`:

   ```sh
   python3 -m emulator.client screen runtime/evidence/<round>-before.png
   python3 -m emulator.client tap <app-x> <app-y>
   python3 -m emulator.client tap <ask-x> <ask-y>
   ```

3. Bound the wait to three minutes. Capture screens periodically with
   `emulator.client screen`; stop on a visible reply/error or at 180 seconds.
   Then count the requests and preserve the log:

   ```sh
   after=$(grep -c '"POST /ink' "$LOG" || true)
   printf 'ink_posts=%s\n' "$((after-before))"
   python3 -m emulator.client screen runtime/evidence/<round>-after.png
   kill "$PUBLISHER_PID"
   wait "$PUBLISHER_PID" 2>/dev/null || true
   ```

The acceptance evidence is the bounded UI transcript/screenshots plus the exact
`POST /ink` delta and each HTTP status in the publisher log. For a multipart
large note the delta may be greater than one; that is expected. Do not infer
success from `/health`, and do not add a post-hoc soup read: both bypass the
installed-app behavior under test or return to the wedged channel.

## Option B — FUTURE GOAL: correlated Einstein control channel

Do not build Option B unless robust programmatic eval automation becomes
load-bearing. The interim proving path above exercises the installed app and
avoids spending a full Einstein rebuild on a diagnostic convenience.

If that threshold is reached, fix the C++ control channel and Python client as
one protocol change:

1. assign every accepted eval a request ID and atomically publish a result tied
   to that ID;
2. expose explicit `idle`, `busy`, and `poisoned` state and reject work while
   not idle;
3. add cancellation or a completion callback sufficient to resynchronize after
   a timeout; and
4. add a regression suite for concurrent rejection, ID matching, cancellation,
   timeout-to-poison behavior, restart recovery, and stale results that must
   never satisfy a newer request.

A second socket, a retry, or a longer timeout is not Option B: all still enqueue
onto the same NewtonOS event path without ownership or cancellation. Per-request
correlation is the part that justifies the C++ rebuild.

## What remains unknown

The one-pass bound prevents splitting the final expression into another live
`Query()`-only probe followed by a `Next()` probe. Existing behavior and the
index-vs-entry finding identify `c:Next()`/full entry materialization as the
expensive boundary, but no instruction-level NewtonOS trace was taken. It is
also unknown whether that fetch eventually completes after more than 10–20
seconds; waiting longer would not make the current uncorrelated channel safe.
