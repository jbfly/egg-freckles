# Ink client design — Newton as an AI input surface

Scope: a future `harness-client` that captures stylus ink on a NewtonOS 2.1
device (MP2100-class, or Einstein), ships it to the host over the existing
HTTP/1.0 path, and displays a short model response. Ink is the primary
channel; the keyboard is a fallback, not the default.

Confidence tags: **[verified]** = exists in this repo's code or was confirmed
there; **[confident]** = well-documented NewtonScript/NTK concept the author is
sure exists; **[verify]** = believed real but the name/behavior must be
confirmed in the NTK 2.1 docs or on-device before building on it. Anything not
tagged in section 1 is a gap, stated as a gap.

---

## 1. What NewtonOS 2.1 gives us for ink capture

### The view system

- NewtonScript apps are trees of views based on `clView`; editable text/ink
  views are `clEditView`. **[confident]**
- Recognition behavior is controlled by `viewFlags` with the documented
  recognition constants: `vAnythingAllowed`, `vLettersOK`, `vNumbersOK`,
  `vPunctuationOK`, `vCursiveOK`, `vShapesOK`, `vInkOK`, plus gesture flags.
  The idiom `vAnythingAllowed - vNumbersOK` appears throughout the NTK docs.
  **[confident]** A canvas that keeps ink as ink (never recognizes it) sets
  `vInkOK` without the text recognizer flags. **[verify: exact constant set
  against the "Newton 2.1" platform file]**
- NewtonOS buffers pen input into *strokes*; apps do not get a continuous
  pen-move event stream. Stroke granularity is what we get, which is fine —
  we never need sub-stroke timing. **[confident]**

### What a stroke is

- Ink is delivered/stored as a **stroke bundle**: a frame
  `{bounds: <rect frame>, strokes: [<polygon binary>, ...]}`. Each stroke is
  a binary of class `'polygon'`. This is the same representation Notes keeps
  in its soup. **[confident on the shape, verify on exact slot names]**
- Points are extractable from a polygon binary with `GetPoints`, which
  returns an array of point frames `{x:, y:}`. **[verify — this is the single
  most load-bearing API name in this design; see risk R1]** Fallback if
  `GetPoints` does not exist or misbehaves: the polygon binary layout is
  simple (point count + integer x/y pairs) and can be parsed with
  `ExtractByte`/`BinaryMunger`, which we already use and trust
  (`examples/harness-loader/Main.newt`). **[verified that those primitives
  work in our toolchain]**
- There is a toolkit proto intended exactly for this — `protoInkView` — a
  view that captures ink and reports a completed stroke bundle to the app.
  **[verify: presence in the 2.1 protos palette and the name of its
  completion callback]** If it does not exist as remembered, the fallback is
  a plain `clView` with `vInkOK` plus whatever ink-notification message the
  view system sends; either way the payload is the same stroke-bundle frame.
- Redraw/erase is the OS's job: the system renders ink as you write, so a
  capture view costs us no drawing code. Undo = drop the last stroke from our
  array and force a redraw; Clear = empty the array. **[confident]**

### The recognition system, and why we mostly bypass it

NewtonOS 2.1 ships printed + cursive (Calligrapher) text recognizers and a
shapes recognizer. We deliberately do **not** recognize on-device: the host
model is strictly better at messy ink, and skipping recognition avoids the
lag and the correction UI. One cheap on-device use remains plausible later:
let the user flip a region to `vCursiveOK` to get plain text for a quick
query without a network round trip. Not in v1.

### What is *not* realistically available

- Per-point timestamps or pressure. Newton digitizes at a fixed rate; apps
  see strokes, not timed samples. Design the wire format so timestamps could
  be added later but assume none. **[confident there's no documented
  per-point timing; verify pressure — believed absent on MP2x00 digitizers]**
- Raw pen events. No `viewDownScript`-style continuous callback is
  documented for app views; don't plan on one.
- On-device bitmap grab of the canvas as a fallback (if stroke extraction
  fails entirely): there may be a view-to-bitmap path, but it's
  **[unknown]** — listed as a fallback experiment, not a plan.

---

## 2. Wire format: strokes off-device

### Constraints that shape the format

- MP2100: StrongARM SA-110 @ 162 MHz, but NewtonScript is interpreted and
  the app heap is small (order of hundreds of KB usable). Keep per-request
  buffers in the single-digit KB range. **Never** build the whole response in
  one giant string the way early code would; the loader's chunked-copy
  pattern (`CopyChunk` + VBO) is the template. **[verified pattern exists]**
- Transport is NIE + `protoBasicEndpoint`, synchronous `Input`/`Output` with
  timeouts, HTTP/1.0, `Connection: close`, server at `10.42.0.1`. Reuse the
  loader's endpoint setup verbatim. **[verified]**
- NewtonScript strings are 16-bit Unicode; the existing path treats bytes
  safely via binaries, but the *request* path in the loader sends ASCII
  strings. Cheapest correct choice: **ASCII-safe request body**. A screen of
  handwriting is ~50 strokes × ~30 points; as ASCII decimal deltas that's
  ~5–10 KB — trivial for one HTTP/1.0 request, and debuggable with
  `telnet`/`curl`. No base64, no varints in v1.
  <!-- ponytail: ASCII decimals; binary varint encoding only if profiling shows body size matters -->

### Format v1 (text, one line per stroke)

```text
POST /ink HTTP/1.0
Host: 10.42.0.1
Content-Type: application/x-newton-strokes
Content-Length: N
Connection: close

NSI1 <canvasW> <canvasH> <strokeCount>
S <nPoints> x0 y0 dx1 dy1 dx2 dy2 ...
S <nPoints> x0 y0 dx1 dy1 ...
```

- First point absolute (view coordinates, x 0–319, y 0–479), rest deltas.
  Deltas keep numbers short (±1–20 typical), which is why the body stays
  small without any real encoding.
- `NSI1` header lets the host reject/version the format.
- No chunking needed at these sizes; if a doodle exceeds ~16 KB body, the
  client splits into sequential `POST /ink?part=k&of=n` requests and the host
  reassembles by a client-supplied session id. Implement only when hit.
  <!-- ponytail: multi-part upload deferred until a real drawing exceeds the cap -->

### Host-side reconstruction

The host needs, per request:

1. Parse strokes (10 lines of Python, stdlib).
2. Render to PNG for the vision model: draw polylines, black on white, at
   2× (640×960) then downscale to 320×480 for antialiasing. A minimal
   grayscale PNG writer is stdlib-only (`zlib` + `struct`); if Pillow is
   already on the host, use it and delete the writer.
3. Keep the vector form (JSON list of strokes) alongside the image — some
   models/prompts do better with both, and the vector is free.

---

## 3. Host-side pipeline sketch

Extend the existing services, don't add new ones:

- `pkg_publisher.py` grows `do_PUT`/`do_POST` for `/ink` (it's already the
  HTTP/1.0 endpoint the Newton talks to). **[verified it's the right shape]**
- On POST: parse → render PNG → call the backend with
  `[image, optional stroke JSON, user hint]` → constrain the reply with the
  existing strict-JSON-schema pattern (`response_schema.json`, `visible`
  string ≤ 2000 chars — here ≤ ~600 chars is plenty for 320×480).
  **[verified pattern from server.py]**
- Keep `NEWTON_FAKE_BACKEND=1` returning canned text so every stage is
  testable without burning model calls. **[verified pattern exists]**

### Round-trip UX on 320×480 grayscale

- **Canvas mode** (default): full-screen ink view, bottom bar with three
  buttons: `Clear`, `Undo`, `Send`. Drawing feels native because the OS
  renders the ink.
- **Sending**: status line ("sending… / thinking…") replaces the bar; the
  synchronous endpoint call with a reqTimeout is exactly how the loader
  already blocks. **[verified pattern]**
- **Response mode**: swap canvas for a scrollable read-only text view
  (`clParagraphView`-family; a proto paragraph view is fine) showing the
  `visible` string in a 12-pt system font. Bottom bar becomes `New sketch`
  and `Back`. Short text is cheap — one screen holds ~40 lines at 10-pt.
- Later, not v1: "insert into Notes" (soup add), host-rendered image replies
  (PLAN.md already lists dithered 480×320 image gen — the same response path
  serves this), multi-turn sketch refinement (send prior response text back
  as context).

---

## 4. Staged roadmap (each stage independently testable in Einstein)

Einstein's mouse is the stylus, so ink capture is fully emulator-testable.
**Prerequisite gap in this repo:** the emulator control API has `/tap`,
`/text`, `/key` but no drag. Stage 0 is adding a `/drag` endpoint
(mouse-down, N moves, mouse-up) so tests can draw. **[verified gap in
`emulator/control.py` + README endpoint table]**

- **Stage 1 — capture only, no network.** New example `examples/ink-capture`:
  ink view + Clear/Undo + a status line showing stroke count and total point
  count. Test: `/drag` a known polyline via the control API, screenshot,
  assert counts on screen. Resolves R1/R2 (does ink arrive, in what form).
- **Stage 2 — encode + upload.** Add `Send`; POST to `pkg_publisher.py`
  extended with `/ink`, which echoes parsed stroke/point counts as the body;
  Newton displays the echo. Test: draw in Einstein, compare echo numbers to
  Stage 1's on-screen numbers. Pure transport check, zero model.
- **Stage 3 — render + fake interpretation.** Host renders PNG from the same
  strokes (test asserts the PNG is non-empty and 320×480; visual check via
  saved file); `NEWTON_FAKE_BACKEND=1` returns a canned reading; Newton shows
  response mode. Full round trip, still no model.
- **Stage 4 — real model + UX polish.** Wire the real backend with the JSON
  schema; add Undo/Clear polish, timeouts with a readable error line, and a
  1–2 character "hint" line (user can scribble a word the model should weigh).
  Promote from `examples/` to replace `harness-client`.

---

## 5. Risks and unknowns, ranked

| # | Risk | Blast radius | Cheapest experiment |
|---|------|--------------|---------------------|
| R1 | `GetPoints` / polygon extraction doesn't work as remembered | Blocks everything | Stage 1: capture one stroke, print point count on screen. If it fails, parse the binary manually with `ExtractByte` and print the first 8 bytes as hex |
| R2 | `protoInkView` (or equivalent ink-notification path) absent/different in 2.1 | Redesign of capture view, days not weeks | Same Stage 1 build resolves it — it's the first thing that either works or doesn't |
| R3 | Einstein mouse-drag → pen-stroke fidelity (dropped points, throttling) | Wrong-looking uploads from emulator tests only | `/drag` a 100-point zigzag, compare captured point count on Newton vs. expected; repeat at different drag speeds |
| R4 | Binary/string gotchas on the request path (`Output` of non-ASCII) | Corrupt uploads | Avoided by design (ASCII body); Stage 2 echo check catches it anyway |
| R5 | Heap pressure from large doodles | App crash mid-capture | Draw until ~2× expected max strokes, watch for `-10061`-style memory errors; mitigations: cap stroke count, multi-part POST |
| R6 | No per-point timestamps/pressure | Loses pen-speed features | None needed — confirm by reading the stroke bundle in Stage 1; design already assumes none |
| R7 | Synchronous send blocks UI for many seconds on slow model calls | Feels frozen | Show "thinking…" (cheap); if real latency is bad, poll: POST returns a job id, client GETs until ready. Decide after Stage 4 with real timings |
| R8 | On-device bitmap capture as ultimate fallback | Only if R1+R2 both fail | Investigate view-to-bitmap in NTK docs; out of scope until needed |

---

## Reuse map (what this design borrows from the repo)

| Existing piece | Reused for |
|---|---|
| `harness-loader` endpoint setup, NIE grab, sync HTTP/1.0, chunked binary copy | All networking in the ink client |
| `pkg_publisher.py` | Host HTTP endpoint; add POST `/ink` |
| `server.py` ASCII-clean, strict JSON schema, `NEWTON_FAKE_BACKEND` | Response contract and testability |
| `emulator/control.py` + client | All stage tests (after `/drag` lands) |
| `examples/harness-client` | Shell app being replaced by Stage 4 output |

---

## Stage 1 result — 2026-07-26

Stage 1 succeeded with the documented NewtonOS 2.1 equivalent path, without
networking. `protoInkView` is absent from the 2.1 platform file, but a plain
`clView` with `vStrokesAllowed` receives `ViewStrokeScript(unit)`, resolving
R2. The extraction API is `GetPointsArray(unit)`, not `GetPoints`; it returns a
flat array of alternating Y/X coordinates. One control-API drag produced the
on-screen result **`Strokes: 1 Points: 94`**, resolving R1. The manual
`ExtractByte` fallback was not needed.

Evidence: `runtime/evidence/s1-ink-after.png`,
`runtime/evidence/s1-ink-after.txt`, `runtime/evidence/s1-ink-result.txt`, and
`runtime/evidence/s1-ink-emulator.log`.
