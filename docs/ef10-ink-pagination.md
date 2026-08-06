# EF10 ink pagination — EF11 reviewed correction

Date: 2026-08-06. EF10 originally shipped as `EggFrecklesEF10:jbfly` (`1.0-ef10`, package version 22). The reviewed correction is `EggFrecklesEF11:jbfly` (`1.0-ef11`, package version 23; `examples/harness-client/Main.newt:10-13`, `egg-freckles.nprj:8-10`). Nothing in either round was installed on the physical MP2000.

## Why image budgets replaced page height

`CollectNote` walks the complete stored note data array in reading order (`examples/harness-client/Main.newt:1278-1305`). EF9 grouped those strokes only by 428-pixel note-space bands, so one dense screen-height band still became one PNG while sparse ink in separate bands spent extra calls (`docs/ef9-ink-pagination.md`, "Fix").

The renderer budgets are 64 strokes and 1,600 points per image (`Main.newt:66-84`). Sixty-four is above the measured 37-stroke dense real page (`runtime/evidence/ef6round-ink-decimation.txt`). One soup item is not one stroke: an `'ink2` item expands through `CountStrokes` (`Main.newt:1340-1356`), which is why the multipart stream has a separate 99-part wire backstop.

`InkParts` flushes before the next whole stroke would exceed either image budget (`Main.newt:1517-1551`). `ThinPartAt` preserves every stroke's first and last point when an individual part or stroke exceeds its point budget (`Main.newt:1476-1515`). Each encoded part subtracts its own minimum Y and the note's left origin before clamping to 320×480 (`Main.newt:1553-1587`).

## EF11 review fixes

1. **Text-only Notes routes no longer disappear.** `Route` sends non-empty text through `EncodeInkPages`; with no strokes, the encoder now calls `EncodeInk([], 0, hint, mode, 1, 1)` and returns one zero-stroke body (`Main.newt:194-246,1604-1616`). If encoding still fails, the route calls `InkDone` so the promised failure note is filed instead of returning silently (`Main.newt:231-246`). The host accepts zero strokes only with a non-empty hint and answers Ask mode through the model (`pkg_publisher.py:328-370,425-434`). The host test pins the exact client-built `M ask` plus `H` shape (`test_pkg_publisher.py:181-225`).
2. **Each part gets a full watchdog budget.** `SendInk` arms one ticket, and both `INKP` handlers call `ArmInkWatch`; incrementing `inkSeq` invalidates every older delayed call (`Main.newt:250-270,1931-1966,2112-2118`). The next HTTP endpoint still opens on the same NIE `linkID` (`Main.newt:2131-2162`).
3. **The client never emits part 100.** `kMaxInkParts = 99` matches the host's `total <= 99` validation (`Main.newt:79-84,1618-1642`; `pkg_publisher.py:348-355`). If the backstop fires, `askThinned` makes the existing warning visible in the app transcript or route reply label (`Main.newt:240,1618-1625,1691-1692`).
4. **Body overflow retries one part, not the whole note.** `EncodeInk` measures the finished body; above 16,384 bytes it reruns `EncodeInkAt` with `maxPoints div 2`, marks the part thinned, and only rejects it if the second body is still too large (`Main.newt:1556-1601`; host cap `pkg_publisher.py:328-331`).
5. **Uninstall identity is measured.** EF11 removal left exactly `Duplicate/newtDuplicateScript` and `Delete/newtDeleteScript`, not merely an array of length two (`runtime/evidence/ef10round-fix-uninstall-routes.txt`).

## Emulator evidence

All new evidence used isolated instance `ef10round-fix`, seeded from `internal-before-round9-loader-20260725-195622.flash`. Image parts went through the real `pkg_publisher.py` image interpreter; the zero-stroke Ask used real `server.py` with `fake=False` (`runtime/evidence/ef10round-fix-chat-host.log`).

- **Zero-stroke Ask AI:** the client built one 60-byte body with zero strokes; the host logged `mode=ask ... strokes=0`, returned `ZERO STROKE OK`, and the agent filed that exact text in AI (`ef10round-fix-zero-route-start.txt`, `ef10round-fix-zero-host.log`, `ef10round-fix-zero-reply.txt`, screenshot `ef10round-fix-zero-reply.png`).
- **Exact boundaries:** 63 and 64 strokes stayed in one part; 65 became 64+1. Totals 1,599 and 1,600 stayed together; 1,601 across two strokes became 1+1. One 1,601-point stroke stayed in one part and thinned to 801 points (`ef10round-fix-boundaries.txt`).
- **99-part backstop:** a controlled installed-client probe forced one stroke per part and requested 100 parts. It returned 99 bodies, set `askThinned=yes`, emitted `P 99 99`, emitted no `P 100`, and reported 198 of 200 points sent (`ef10round-fix-backstop.txt`).
- **Body re-thin:** a controlled installed-client probe raised the local point budget to 2,000 to construct an actual 18,229-byte body above the real 16,384-byte cap. `EncodeInk` retried at half budget and returned a 6,240-byte body with 668 points, `retried=yes`, `thinned=yes` (`ef10round-fix-body-rethin.txt`).
- **Four-part client stream:** one 36-stroke/6,120-point note produced four parts of 9 strokes/1,530 points. The host rendered four PNGs and returned four ordered readings; the filed note read `ALPHA ALPHA ALPHA ALPHA`. The watchdog sequence advanced from 2 after initial arming to 5 after three `INKP` acknowledgements (`ef10round-fix-many-probe.txt`, `ef10round-fix-many-route-start.txt`, `ef10round-fix-many-host.log`, `ef10round-fix-many-reply.txt`, renders `ef10round-fix-many-part-01.png` through `-04.png`).
- **Build and tests:** tntk built EF11/package version 23 (`ef10round-fix-build.log`), and the full suite passed 105 tests (`ef10round-fix-full-tests.txt`). Package SHA-256 is recorded in `ef10round-fix-package-sha256.txt`.

## Earlier EF10 budget proofs

The original point-budget proof used 27 strokes/2,430 points in one EF9 band and filed `ALPHA BRAVO ALPHA` (`ef10round-pointsplit-probe.txt`, `ef10round-pointsplit-host.log`, `ef10round-pointsplit-reply.txt`). The independent stroke-budget proof used 128 strokes and filed the same ordered text (`ef10round-pagination-probe.txt`, `ef10round-dense-host.log`, `ef10round-dense-reply.txt`). The one-part ink path filed `ALPHA` (`ef10round-short-probe.txt`, `ef10round-short-host.log`, `ef10round-short-reply.txt`).

## Deferred

Physical MP2000 validation remains human-gated. EF11 was not deployed to Mars or installed on hardware.
