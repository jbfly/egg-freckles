# EF10 — paginate Notes ink by per-image legibility budget

Date: 2026-08-06. Package identity: `EggFrecklesEF10:jbfly` (`1.0-ef10`, package version 22).
Emulator evidence only; nothing in this round was installed on the physical MP2000.

## Why EF9's page height was the wrong budget

`CollectNote` already walks the complete stored note data array in reading order (`examples/harness-client/Main.newt:1282-1300`). EF9 then grouped those strokes only by 428-pixel note-space bands. That fixed later-page Y clamping, but one dense screen-height band still became one PNG no matter how many strokes or points it contained. Conversely, sparse ink in separate geometric bands spent multiple model calls even when one image budget was enough (`docs/ef9-ink-pagination.md`, "Fix").

The renderer's actual constraints are per image. The host accepts at most 16,384 body bytes (`pkg_publisher.py:328-331`), and the existing measured-safe point budget remains `kMaxPoints = 1600` (`examples/harness-client/Main.newt:69-85`). The new stroke budget is 64: the densest measured real screen-height handwriting page had 37 strokes, so 64 leaves useful headroom for normal writing while honestly refusing to claim that hundreds of tiny strokes remain legible in one 320×480 render (`examples/harness-client/Main.newt:86-96`; `runtime/evidence/ef6round-ink-decimation.txt`).

## Fix

`InkParts` now walks `askStrokes` in stored reading order and flushes the current part before adding a whole stroke that would exceed either 64 strokes or 1,600 points (`examples/harness-client/Main.newt:1518-1552`). It never splits or drops a stroke. A single pathological stroke above 1,600 raw points is still handled by the existing endpoint-preserving thinning pass, now named `ThinPart` (`Main.newt:1480-1516`).

Each part keeps EF9's independent thinning and canvas normalization: `EncodeInk` subtracts that part's minimum Y and the note's existing left origin before clamping to the 320×480 canvas (`Main.newt:1554-1586`). The one-part path still omits `P`; multipart bodies still use `P KK NN` (`Main.newt:1561-1566,1589-1610`).

The proven transport did not change. Intermediate `INKP` closes one HTTP/1.0 endpoint, then `InkNext` opens the next endpoint on the same `linkID`; it does not grab a second NIE link (`Main.newt:2072-2122`). Both the Notes-menu agent and app window still recognize `INKP` (`test_newton_client_source.py`, `test_long_ink_is_split_by_per_image_legibility_budgets_and_sent_in_order`).

The host needed no code change. It already accepts totals through 99, renders each part separately, stores readings in sequence, and joins them only on the final part (`pkg_publisher.py:348-355,402-452`). The host test now sends four parts and verifies four PNG names plus `INK FIRST SECOND THIRD FOURTH`, proving there is no three-part cap (`test_pkg_publisher.py:223-256`).

## Emulator proof

Isolated instance `ef10round`, seeded from `internal-before-round9-loader-20260725-195622.flash`; the host was the real `pkg_publisher.py` image-interpretation path, not a fake chat backend.

- **Point-budget proof matching the hardware failure shape:** uid 3 held 27 strokes and 2,430 raw points between Y=110 and Y=302—under the 64-stroke cap, over the 1,600-point cap, and wholly inside one EF9 band. EF10 emitted two parts: part 1 had 18 strokes and 1,530 raw/sent points; part 2 had 9 strokes and 900 raw/sent points. Neither part needed thinning (`runtime/evidence/ef10round-pointsplit-seed.txt`, `ef10round-pointsplit-probe.txt`).
- **Real ordered point-split interpretation:** the host rendered `ef10round-pointsplit-part-01.png` and `ef10round-pointsplit-part-02.png`, logging 1,530 and 900 points respectively, and the filed AI note read exactly `ALPHA BRAVO ALPHA` in order (`ef10round-pointsplit-host.log`, `ef10round-pointsplit-reply.txt`, screenshot `ef10round-pointsplit-reply.png`).
- **Independent stroke-budget proof:** uid 5 contained 128 stored strokes between Y=110 and Y=302, so EF9's 428-pixel rule would have emitted one over-budget image. EF10 reported `ef9Bands=1 parts=2 part1=64st/128pt/top110 part2=64st/128pt/top260` (`runtime/evidence/ef10round-seed-dense-note.txt`, `ef10round-pagination-probe.txt`). The host rendered two PNGs and filed `ALPHA BRAVO ALPHA` in order (`ef10round-dense-host.log`, `ef10round-dense-reply.txt`, `ef10round-dense-part-01.png`, `ef10round-dense-part-02.png`).
- **Short fast path:** uid 7 reported `strokes=9 rawPoints=25 parts=1`; the host logged one 211-byte body with no `part=` field and filed `ALPHA` (`ef10round-short-probe.txt`, `ef10round-short-host.log`, `ef10round-short-reply.txt`, render `ef10round-short-part.png`).
- **Transport/agent invariants:** the two EF10 menu entries shared one agent, and `POST /tools` ping returned `pong` (`ef10round-sweep-ef10-initial.txt`, `ef10round-tools-ping.json`).
- **Install/uninstall:** installing EF10 over installed EF9 left exactly four routes—two stock plus two EF10—with one shared agent, not accumulated EF9 routes (`ef10round-sweep-ef9.txt`, `ef10round-sweep-ef10.txt`). Removing EF10 left `routes=2` while `EF9=installed EF10=missing`, proving the generation sweep and identity-scoped uninstall remain intact (`ef10round-sweep-uninstall.txt`, `ef10round-sweep-final.txt`, `ef10round-sweep-package-refs-final.txt`).
- **Build and tests:** the package rebuilt as identity EF10/version 22 (`ef10round-build.log`); the full suite passed `102 passed` (`ef10round-full-tests.txt`). Package SHA-256 is recorded in `ef10round-package-sha256.txt`.

## Deferred

Physical MP2000 validation remains human-gated. EF10 was not deployed to Mars or installed on hardware.
