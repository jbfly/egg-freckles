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
