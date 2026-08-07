# EF20 note teardown and ink transport

Date: 2026-08-07. Emulator validation is required before this round is complete;
physical hardware remains human-gated.

## Part 1 — Notes completion owns teardown

EF19's Notes agent filed a terminal `INK` reply but returned without calling
`InkDone`; it depended on a later NIE peer-drop callback to finish the transfer.
If that callback did not arrive, neither delayed disposal of `inkEndpoint` nor
the five-second radio-idle timer was scheduled, leaving the `/tools` endpoint on
the shared link established. EF20 makes the terminal Notes reply clear
`inkBusy` and call `InkDone` directly
(`examples/harness-client/Main.newt:333-347`). `InkDone` still delays disposal
out of the NIE input callback by one second, preserving the Stage 3 callback
armor, and arms the existing ticketed five-second idle path
(`examples/harness-client/Main.newt:2398-2424`). That path stops `/tools`, stops
chat/ink, and only then allows the endpoint-presence guard to release the link
(`examples/harness-client/Main.newt:811-881`).

The first emulator pass exposed a second teardown blocker: each three-second
host heartbeat arrived as `TOOLS 0 ping`, and `ToolDispatch` treated it as real
activity while `ToolReplySent` armed a fresh idle ticket. The five-second timer
therefore could never win. EF20 excludes request ID `0` from both activity
refreshes; if the existing timer lands during a heartbeat callback, it retries
the same ticket one second later rather than disposing inside that callback
(`examples/harness-client/Main.newt:804-827,2687-2724,2708-2720`).

The isolated EF13 proof flash then completed all eight `/ink` POSTs and logged
the active tools endpoint disconnect; `ss -tnp` showed no connection on port
18081 after idle (`runtime/evidence/ef20-part1-publisher.log`,
`runtime/evidence/ef20-emulator.log`).

Regression coverage pins the terminal Notes transition, idle arming, and the
all-endpoint `RadioExpired` shutdown in
`test_newton_client_source.py:185-196`. The focused source and publisher suites
pass (56 tests), and `tntk` compiled package identity
`EggFrecklesEF20:jbfly`, version 32, cleanly.

Part 2 instrumentation, emulator proof, reproducible package builds, and final
suite counts follow in the next commit(s).

## Part 2 — measured transport split; transport rewrite deferred

EF20 measures Newton output completion separately from endpoint teardown and
reopen. Each completed page contributes one small timing frame; the existing
three-second `/tools` heartbeat carries it to the publisher, so instrumentation
opens no fourth endpoint and retains no ink body. The publisher validates and
deduplicates those frames. `InkNext` still disposes the closed endpoint, runs
`GC()`, and builds only the next body, preserving EF13's one-body-at-a-time
memory bound. The NSI1 encoder is unchanged
(`examples/harness-client/Main.newt:1720-1825,2258-2465,2755-2800`;
`pkg_publisher.py:61-66,81-162`).

The final isolated-emulator run used the EF13 proof flash and stock Notes ->
Convert to Text, driven only by `python3 -m emulator.client`. It produced eight
HTTP 200 `/ink` POSTs, eight distinct final timing records, no OOM/error text,
and then a `/tools` disconnect with no port-18081 socket left after idle
(`runtime/evidence/ef20-final-publisher.log`,
`runtime/evidence/ef20-emulator.log`, `runtime/evidence/ef20-final-*.png`).

| Emulator measurement | Median | Range |
|---|---:|---:|
| Body build | 383 ms | 200-400 ms |
| Newton output completion | 8 ms | 0-16 ms |
| Intermediate endpoint dispose + reopen | 99 ms | 33-133 ms |
| Final endpoint dispose (no reopen) | 1,900 ms | one sample |

The observed POST spacing remained roughly 6-7 seconds per page, so neither the
measured output callback nor endpoint churn explains the emulator gap. That
means the emulator does **not** justify either risky candidate change: persistent
HTTP would require changing the close-delimited response lifecycle, while
larger pages would raise the EF13 peak-memory and legibility budgets. EF20
therefore ships instrumentation but no transport rewrite. The required next
measurement is the same final `INKTIME` split on physical hardware; only that
can decide whether a follow-up should pursue connection reuse or a conservative,
measured page-size increase.

## Final verification

- Full host suite: **113 passed in 17.10 s**
  (`runtime/evidence/ef20-full-tests.txt`).
- Clean `tntk` compilation produced `EggFrecklesEF20:jbfly`, package version 32.
- Two consecutive `make newton-packages` runs produced identical
  `runtime/staging/SHA256SUMS`.
- EF20 package SHA-256:
  `91381832725a2563dcf6c635c3f7f98306a5d1214d1bdafd183757d5c5d4e0bd`.
- Paired publisher SHA-256:
  `538d6fa41b65373c4cb3040ff3e7512078e93e7f4d6914e8a18e7b583f6ec566`.

Hardware remains human-gated: install EF20 on the MP2000, run the measured
six-page note, confirm eight or the expected part count of HTTP 200 POSTs, no
OOM, one final timing record per page, and radio disconnect after idle. Do not
deploy this round to Mars before that gate.
