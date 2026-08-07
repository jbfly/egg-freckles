# EF9 — paginate long Notes ink

Date: 2026-08-06. Package identity: `EggFrecklesEF9:jbfly` (`1.0-ef9`, package version 21).
Emulator evidence only; nothing in this round was installed on the physical MP2000.

## Truncation diagnosis

The hardware symptom is confirmed as a rendering/transport-budget problem, not a visible-page capture problem.

1. **Capture walks the note's stored data array, not the visible Notes page.**
   `CollectNote` iterates `foreach item in data` (`examples/harness-client/Main.newt:1278-1295`). It never reads `targetView`, the current Notes scroll position, or screen `viewBounds`. The walk is deliberately bounded by `kMaxItems = 256`; within that safety bound it sees typed frames from every page in the entry's one scrolling note-space array.
2. **EF8 forced all pages through one 16 KiB body and one 320×480 PNG.**
   The host rejects `/ink` bodies above 16,384 bytes (`pkg_publisher.py:328-331`). EF8 therefore ran one global `ThinInk` budget of 1,600 points and subtracted one global top origin from every stroke. `ClampAt(..., 479)` then put every point below the first canvas onto Y=479. Page 2 and page 3 were not absent from capture; their geometry collapsed onto the bottom row of the first PNG.
3. **The measured decimation was already severe on one dense page and scales badly.**
   EF6's real wire measurement retained 1,308 of 2,569 points (50.9%, stride 2) for 37 strokes (`runtime/evidence/ef6round-ink-decimation.txt`). Three pages of similar density would put about 7,707 points through the same 1,600-point budget. With 111 strokes the EF8 formula gives `target = 1600 - 222 = 1378` and `stride = (7707 div 1378) + 1 = 6`: roughly one sampled point in six, plus endpoints, before the page-2/page-3 Y clamping. That is enough to make later handwriting illegible even though its strokes were collected.

## Fix

The client now bands note-space strokes into 428-pixel pages (`kPageHeight = kWinHeight`), applies the existing thinning algorithm independently to each page, and encodes one `NSI1` body per non-empty page (`Main.newt:1479-1607`). A multipart body adds `P KK NN`, mirroring the existing two-digit `MSGP` order/total fields. A one-page note omits `P` and keeps the EF8 one-POST fast path.

The client sends one page at a time. `INKP KK NN` acknowledges an intermediate page; after HTTP/1.0 closes that endpoint, `InkNext` opens the next endpoint on the existing `linkID` (`Main.newt:2068-2119`). It never grabs a second NIE link, preserving the hardware-proven `-16009` constraint. Both the app window and the Notes-menu agent handle `INKP`.

The host validates `P`, renders each body to its own PNG, interprets it immediately, and stores ordered readings under the Newton's client address (`pkg_publisher.py:339-451`). Intermediate responses are `INKP`; the final response is one `INK` line containing the readings joined in page order. Starting a new part 1 resets an abandoned stream. The server uses one lock because the Newton sends the next page only after the prior HTTP response closes.

## Emulator proof

Isolated instance `ef9round`, seeded from `internal-before-round9-loader-20260725-195622.flash`; real image interpretation, not the fake chat backend.

- Native source note: uid 4, 32 `'poly`/`'polygonShape` frames, first Y=110, last Y=986. The installed EF9 agent reported `strokes=32 rawPoints=104 pages=3 tops=110,538,966` (`runtime/evidence/ef9round-pagination-probe.txt`).
- Long Convert-to-Text: three ordered 200 responses:
  - part 1/3: 220 bytes, 9 strokes, 25 points
  - part 2/3: 281 bytes, 9 strokes, 37 points
  - part 3/3: 337 bytes, 14 strokes, 42 points
  The filed AI note reads `ALPHA BRAVO CHARLIE` (`ef9round-long-host.log`, `ef9round-long-reply.txt`, screenshot `ef9round-12-long-reply.png`). Page renders are `ef9round-13-page-01.png`, `ef9round-14-page-02.png`, and `ef9round-15-page-03.png`.
- Short fast path: uid 6 reported `strokes=9 pages=1`; the host logged one body, `mode=text bytes=211 strokes=9 points=25`, with no `part=` field, and filed `ALPHA` (`ef9round-short-host.log`, `ef9round-short-reply.txt`, render `ef9round-16-short-page.png`).
- EF8 invariants: the two menu entries shared one agent (`sameAgent=yes`), its tools endpoint was live, and `/tools` ping returned `pong` (`ef9round-single-agent.txt`, `ef9round-tools-ping.json`). `M text`/`M ask` remain literal lowercase wire values.
- Install/uninstall: a committed EF8 install first produced two EF8 AI routes; installing EF9 replaced them with exactly two EF9 routes, not four (`ef9round-sweep-ef8.txt`, `ef9round-sweep-ef9.txt`). Actual EF9 removal then reported `EF9=missing EF8=installed` and left exactly the two stock routes (`ef9round-sweep-uninstall.txt`, `ef9round-sweep-package-refs.txt`, `ef9round-sweep-final.txt`), proving generation sweep plus identity-scoped uninstall.

## Deferred

Appending Ask answers to the source note was not attempted. It is secondary and requires careful paragraph-frame placement relative to the source note's existing `viewBounds`; doing it in the same round would add risk after the primary transport and route-agent lifecycle changes. Ask therefore keeps EF8's new-reply-note behavior.
