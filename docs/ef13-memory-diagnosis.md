# EF13 ink out-of-memory diagnosis

**Diagnosis only.** This branch adds heap probes to a uniquely named emulator
package (`EggFrecklesEF13DIAG2:jbfly`); it does not change collection, encoding,
or transport behavior. Hardware was not touched.

## Result

The killer is **multipart body materialization, not the soup query and not one
`ExpandInk` item**. On a clean emulator run of a synthetic note with exactly
**200 ink items, 400 strokes, and 9,000 expanded points**, soup lookup plus
whole-note stroke collection retained about **33.6 KB**. Partitioning plus
materializing and retaining all seven bodies consumed about **142.0 KB**, while
a single body-concatenation pass produced an observed **191.6 KB transient
trough** before automatic garbage collection.

The unconstrained emulator survived because it began the measured path with
297,492 bytes free. Its lowest reading was 49,068 bytes during body encoding:
**248,424 bytes of simultaneous heap pressure**. A constrained emulator rerun
stopped after `body-4-before free=97084`; there is no `body-4-after`, encode,
send, or POST sample. That reproduces the hardware fact that zero `/ink` POSTs
leave the Newton: exhaustion occurs while building a part body.

Evidence:

- clean run: `runtime/evidence/ef13-clean-400-memory.log`
- constrained stop: `runtime/evidence/ef13-constrained-400-memory.log`
- synthetic seed: `runtime/evidence/ef13-clean-seed.log`
- package build: `runtime/evidence/ef13-final-build.log`
- source tests: `runtime/evidence/ef13-source-tests.txt`
- screenshots: `runtime/evidence/ef13-constrained-oom.png`

## Pipeline map

| Phase | Shipped EF12 path | Source |
|---|---|---|
| Soup query | `Ask` calls `FindNewest`; `FindNewest` opens the Notes union soup and queries `_uniqueID` (falling back to `timeStamp`). | `examples/harness-client/Main.newt:1236-1276`, `:1689-1697` |
| Soup data fetch | `Ask` materializes the selected entry's `data` array with `GetSysEntryData`. | `examples/harness-client/Main.newt:1698-1701` |
| Ink expansion and collection | `CollectNote` walks every item; each `'ink2` item calls `ExpandInk`, then reads every stroke with `GetStrokePointsArray`. | `examples/harness-client/Main.newt:1284-1313`, `:1353-1372` |
| Whole-note stroke arrays | Every flat point array is pair-swapped and retained in `self.askStrokes`; nothing is released before encoding. | `examples/harness-client/Main.newt:1421-1433`, `:1461-1488` |
| Part reference arrays | `InkParts` creates a second tree of arrays/frames pointing at the retained strokes. | `examples/harness-client/Main.newt:1536-1566` |
| Per-part body encoding | `EncodeInkAt` repeatedly concatenates each `S` line and the complete body string. | `examples/harness-client/Main.newt:1571-1601` |
| All-body materialization | `EncodeInkPages` encodes every part and appends every completed string to `bodies` before returning. | `examples/harness-client/Main.newt:1617-1660` |
| Send setup | Only after all bodies exist does `Ask` call `SendInk`; `SendInk` retains the complete bodies array and selects part 1. | `examples/harness-client/Main.newt:1714-1731`, `:1971-1988` |
| HTTP request/send loop | `InkPost` duplicates the current body into a full HTTP request string and outputs it; later ACK/drop handling advances to the next retained body. | `examples/harness-client/Main.newt:2115-2148`, `:2176-2185` |

`Stats()` is the documented free-heap call and returns bytes
(`refs/NewtonProgrammerRef20.txt:70128-70138`). `MemLog` intentionally does not
call `GC()`, so the samples include the same automatic-GC behavior as the real
button path (`examples/harness-client/Main.newt:1662-1673`). Positive deltas in
the table therefore mean an automatic collection happened inside that phase;
they do not mean encoding freed its retained output.

## Clean emulator measurements

Synthetic note construction is recorded as `"EF13SEED done uid=3 items=200"`.
The real **Ask Note** button then reported `strokes=400 raw=9000` in the phase
log. The note uses 150 two-stroke items that expand to 42 points each and 50
that expand to 54 each: `150*42 + 50*54 = 9,000`.

| Phase | Free before (bytes) | Free after (bytes) | Delta (after - before) |
|---|---:|---:|---:|
| Soup query | 297,492 | 296,740 | -752 |
| Soup `data` fetch | 296,240 | 295,600 | -640 |
| First representative `ExpandInk` item | 294,040 | 293,236 | -804 |
| Whole collection, including all 400 stroke arrays | 294,992 | 262,684 | -32,308 |
| Build seven part-reference frames | 261,364 | 258,736 | -2,628 |
| Body 1, 6,081 bytes | 257,572 | 74,248 | -183,324 |
| Body 2, 6,137 bytes | 73,544 | 242,064 | +168,520 (automatic GC) |
| Body 3, 6,081 bytes | 241,356 | 49,772 | **-191,584** |
| Body 4, 6,137 bytes | 49,068 | 70,740 | +21,672 (automatic GC) |
| Body 5, 6,677 bytes | 70,036 | 132,480 | +62,444 (automatic GC) |
| Body 6, 6,877 bytes | 131,772 | 161,956 | +30,184 (automatic GC) |
| Body 7, 2,549 bytes | 161,248 | 121,180 | -40,068 |
| All bodies retained (`bodies-before` to `bodies-after`) | 258,212 | 120,520 | **-137,692** |
| Entire encode phase | 261,936 | 119,892 | **-142,044** |
| `SendInk` retains bodies | 118,544 | 117,924 | -620 |
| Endpoint/open work before `InkPost` | 117,924 | 110,372 | -7,552 |
| Build first 6,205-byte HTTP request | 110,372 | 96,100 | -14,272 |

The clean run's maximum reading was 297,492 and its minimum was 49,068, so the
observed peak simultaneous pressure was **248,424 bytes**. The seven completed
wire bodies total **40,539 bytes**, but body strings are not the whole cost:
repeated immutable-string concatenation and `ThinPartAt` scratch arrays make an
individual 6 KB result transiently cost roughly 180-192 KB.

## Constrained reproduction

To localize the failure on an emulator with a tighter heap, two temporary root
arrays were retained as ballast; they are not package code and disappear on
restart. The logged rerun reaches:

| Last phases reached | Free before | Free after |
|---|---:|---:|
| Body 1 | 132,312 | 85,000 |
| Body 2 | 84,296 | 34,812 |
| Body 3 | 34,108 | 97,788 (automatic GC) |
| Body 4 | **97,084** | **no sample: allocation aborted** |

There is no `body-4-after`, `bodies-after`, `encode-after`, `send-retained`,
`post-before`, or request sample in
`runtime/evidence/ef13-constrained-400-memory.log`. This is the same boundary as
the hardware observation of zero `/ink` requests: the failure is before send
setup, inside `EncodeInkAt` while concatenating body 4.

## Killer-allocation assessment

1. **All part bodies plus per-body encoding scratch are the primary killer.**
   The retained encode delta is 142,044 bytes versus 32,308 bytes for the
   complete 400-stroke collection, and the constrained run dies in body 4.
2. **The whole-note stroke array is material but secondary.** It remains live
   throughout all seven encodes, so its ~32 KB reduces the headroom available
   to the much larger body transient.
3. **A single huge `ExpandInk` item is not the trigger in this reproduction.**
   The first two-stroke item changed free memory by only 804 bytes, and all 200
   items completed with the exact 400/9,000 totals. A pathological one-item note
   can still have a larger transient, but it is not needed to explain this bug.
4. **Transport is downstream, not causal.** The constrained run never reaches
   `SendInk` or `InkPost`. In the clean run, transport starts only after all
   40,539 body bytes and the original stroke arrays are already retained.

## Verification

- Final package: `examples/harness-client/egg-freckles.pkg`, SHA-256
  `3b8c2b6bcb7ee3fd03b4dd676325aa644a5798cf351b041aa020cbf2665b9ee2`.
- Build succeeded with `tntk`; see `runtime/evidence/ef13-final-build.log`.
- Instrumented identity is unique: `EggFrecklesEF13DIAG2:jbfly`, version string
  `1.0-ef13diag2`; the shipped EF12 identity was not reused.
- Emulator instances only: `ef13diag` and clean confirmation `ef13clean`.
- No hardware, Mars, loader, deployment, or transport-format changes.


## Source implementation status (2026-08-07)

Commit `ddcdf29` was reviewed as an unproven draft. Its lazy page-count and
`StrMunger` body construction were retained, but two source problems were
corrected before release: the previous HTTP endpoint is now disposed before the
next page is encoded, and speculative collection-time `CountPoints` /
`GetStrokePoint` sampling plus a 32 KiB item refusal were removed because the
diagnosis above does not identify collection or one large `ExpandInk` item as
the trigger. The proven EF12 collection path remains intact.

The finished source owns one body at a time: count partitions, encode part 1,
POST it, dispose the closed endpoint/request, run `GC()`, encode the next part,
and release each encoded part's stroke references. `StrMunger` replaces the
per-point immutable body and HTTP-request concatenation. The 99-part wire cap
and any later encode failure use a computed `Note too long - first N pages sent`
message; Notes routes file that outcome instead of silently aborting.

Source-only verification: `test_newton_client_source.py` passed 38 tests and
`test_pkg_publisher.py` passed 12 tests. The rebuilt EF13 package SHA-256 is
`d14f183fe611aa1cb26ca317fe608fd7a1314335dc17f313199673b38873ac56`;
the package and `pkg_publisher.py` ship in the same commit. **Emulator prove
remains PENDING.**

## Deployed to mars — 2026-08-07 (emulator prove blocked; hardware test next)

Emulator prove could NOT be completed: on two clean instances (`ef13ship2`,
`ef13ship`) the NewtonScript eval channel answers a trivial probe (`2+2`->4)
but hangs 20s on the first eval touching the seeded ~400-stroke note state.
The follow-up diagnosis localizes the expensive call to the cursor's first
full-entry fetch and identifies the uncorrelated singleton result file as what
turns a timeout into a poisoned channel (`docs/emulator-nseval-wedge.md`). Prior
worker wedges (240s, 3600s) were retries/concurrency on that channel, not a
large result crossing a socket-size boundary. Decision (human):
accept source + unit-test evidence and proceed to the human-gated hardware
test on the physical Newton; investigate the emulator harness afterward.

Deploy = two-file ship + `raw_pkg_server` restart (the fix is device code in
the pkg AND the paired streaming `/ink` handler in `pkg_publisher.py`, which
is imported at process start, so a restart is required to load it):

| Item | Value |
|---|---|
| Branch / commit | `task/ef13-fix @ 27d0418` |
| Served pkg (mars `examples/harness-client/egg-freckles.pkg`) | `d14f183fe611` |
| Publisher (mars `pkg_publisher.py`) | `4d56debf2ff4` |
| HTTP verify (`curl http://10.42.0.1:18081/egg-freckles.pkg`) | `d14f183fe611` ✓ |
| New `raw_pkg_server` pid | 371667 (log: `serving http://10.42.0.1:18081`) |
| `server.py` (179424) | untouched |

Rollback (one-step, staged on mars):
- EF12 pkg `egg-freckles.EF12.bak.pkg` = `90ee54e8cb66`, publisher
  `pkg_publisher.EF12.bak.py` = `5def2cd4f3e2` — restore both, restart server.
- Older: EF9 `egg-freckles.EF9.bak.pkg` = `f7de62f9f705`.

## Hardware test #1 — memory fix WORKS; interpret 502 was a PATH regression

First physical-Newton run (~332 strokes): server log shows the streaming fix
working — `INK BODY mode=text part=1/6 bytes=6275 strokes=64 points=1287`,
parts streamed one at a time, **no OOM** (EF12 aborted before body-4). The
Newton showed "No reading"; server returned `POST /ink ... 502`.

Root cause: `interpret()` execs `codex` (`/home/jbfly/.local/bin/codex`), which
is only on the LOGIN-shell PATH. `raw_pkg_server` had been restarted from a
bare non-interactive ssh shell whose PATH lacked `~/.local/bin`, so the
subprocess raised errno 2 (no such file) -> RuntimeError -> 502. This is the
exact failure the EF13 source comment already flags ("the hardware 502 was
codex missing from PATH").

Fix: relaunch with `~/.local/bin` on PATH. Verified pid 372370 PATH now
includes `/home/jbfly/.local/bin` and `codex` is executable. HTTP still serves
`d14f183f`. **Restart requirement:** always launch raw_pkg_server from a login
shell (or `env PATH="$HOME/.local/bin:$PATH"`), else interpret 502s.

Durable-hardening follow-up (not yet done): make `interpret()` resolve codex by
absolute path / explicit PATH so a bare-shell restart can't reintroduce this.

## PATH-restart 502 permanently closed (commit f3c18db)

The codex-missing-from-PATH 502 had hit twice because interpret() called codex
by bare name, depending on the launch shell's PATH. Fixed in the code so no
launch method can reintroduce it:

- `pkg_publisher._codex_bin()` resolves codex to an ABSOLUTE path each call:
  `NEWTON_CODEX_BIN` override → `~/.local/bin/codex` → `shutil.which("codex")`,
  else raises a legible RuntimeError naming all three (no more bare errno 2).
  interpret() uses that absolute path as argv[0]. Commit `f3c18db`,
  pkg_publisher.py sha `2e9b728d98f8`; `.pkg` unchanged (`d14f183fe611`).
- Tests: focused suite 50 → 51 passed (`uv run --with pytest pytest -q
  test_pkg_publisher.py test_newton_client_source.py`); existing subprocess
  boundary test updated to pin the absolute argv[0].

Proven on mars UNDER A BARE PATH (the exact failure condition):
`env PATH=/usr/local/sbin:/usr/local/bin:/usr/bin python3 -c "import
pkg_publisher; print(pkg_publisher._codex_bin())"` ->
`/home/jbfly/.codex/packages/.../bin/codex`. Live server (pid 375664) is
running with that bare PATH and still serves `d14f183f`; publisher `2e9b728d`.

Restart requirement REMOVED: raw_pkg_server no longer needs a login shell.

## HARDWARE PASS — EF13 proven on the physical Newton

The ~332-stroke note that OOM'd under EF12 completed under EF13. Durable
evidence on mars (`runtime/evidence/`), surviving a log truncation:
`ink-latest-part-01.png` … `-part-06.png`, written 22:27–22:29 — **all 6
parts streamed and rendered one at a time** (build→send→free). User confirmed
the transcript returned and displayed on the Newton. No OOM / 502 / errno /
traceback anywhere in the run logs.

Caveats / notes:
- Latency ~1–2 min for the full note: interpret() runs codex vision once PER
  part (6 sequential ~9 s reads). That is the cost of streaming instead of
  materialising all bodies; it is the fix working, not a fault. Possible future
  speedup: interpret parts concurrently, or show progress. Not done.
- A power-cycle was NOT required by the fix; it reset a flaky wifi session so
  the already-completing result surfaced. First "nothing came back" was the
  send still in-flight (slow), not a failure.
- Ops lesson: raw_pkg_server was relaunched with `>` (truncating the log),
  erasing the successful request lines. Relaunch with `>>` (append) next time;
  the per-part PNGs are the durable record regardless.

Status: EF13 memory fix DONE and hardware-proven. The separate emulator
NS-eval wedge is diagnosed in `docs/emulator-nseval-wedge.md`; its correlated,
single-flight control-channel fix is proposed there but not implemented.
