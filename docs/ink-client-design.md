# Ink client design — Newton as an AI input surface

> **Status (2026-08-03): implemented, and no longer a separate app.** The
> design below reads as a proposal, but Stages 1–5 were built and proven on
> the emulator — see the "Stage 1 result" through "Stage 5 result" sections
> appended below — and **Track F2 folded the whole thing into the chat
> client** as a hideable overlay, deleting `examples/ink-capture`. The pen-up
> defect is **RESOLVED** (Stage 5) and the doubled `Encode()` origin is
> **RESOLVED and measured on the wire** ("Track F2 result", the last section).
> EF12, the final hardening of the reviewed EF10/EF11 path, groups native Notes ink into ordered
> per-image stroke/point-budget POSTs while preserving the one-POST short path (`docs/ef10-ink-pagination.md`;
> EF9 fixed-height history: `docs/ef9-ink-pagination.md`). The
> remaining gap is physical-hardware validation. See `docs/ROADMAP.md` Tracks E
> and F2.
>
> **Superseded in part (2026-08-04): the capture canvas is being retired.**
> Hardware testing found it drops all but the first stroke when drawing
> freely, and the human's direction is to stop reinventing an ink canvas and
> read **native Notes sketches** instead. The stroke *encoding* and the
> `/ink` host pipeline below all survive; the on-device capture view does not.
> Read the last section, "Sketch-note pivot (design)", before building
> anything from sections 1 and 4.

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

---

## Stage 2 result — 2026-07-26

Stage 2 succeeded as a pure transport check. `InkCaptureB:jbfly` retains the
Stage 1 point arrays, encodes the documented ASCII `NSI1` delta format, caps a
single body at 16 KiB, and posts it to `/ink`. The host handler counted the
stroke lines and coordinate pairs and echoed the totals. One drag showed
**`Strokes: 1 Points: 94`** before Send and the host echo showed the same
**`Strokes: 1 Points: 94`** after Send; the host logged an HTTP/1.0 `POST /ink`
with status 200. No rendering, interpretation, model, or AI backend was used.

The scratch emulator captured `1 / 94`, but its separate podman network could
not reach `10.42.0.1:18081` (`FAILED: Connect 0`, with no host request), so the
round trip used the instructed `18080` fallback. Cleanup removed the temporary
ink package and restored `HarnessClient:jbfly` 1.9 to `Ready`.

Evidence: `runtime/evidence/s2-final-before.png`,
`runtime/evidence/s2-final-before.txt`,
`runtime/evidence/s2-final-after.png`,
`runtime/evidence/s2-final-after.txt`,
`runtime/evidence/s2-ink-after-send.png`,
`runtime/evidence/s2-ink-after-send.txt`,
`runtime/evidence/s2-main-restored.png`,
`runtime/evidence/s2-main-restored.txt`, and
`runtime/evidence/s2-ink-result.txt`.

---

## Stage 3 result — 2026-07-26

Stage 3 is proven end to end. `InkCaptureD:jbfly` captured a real main-emulator
stroke as **`Strokes: 1 Points: 98`** and sent its own `NSI1` body. The host
logged `POST /ink` with status 200 and rendered a fresh 320×480, 8-bit
grayscale PNG with ink bounding box `185x156+67+146`. The Newton displayed the
canned response **“A simple curved line.”** It also raised alert `-48200` after
displaying the response; Stage 4 must remove that post-response error.

The scratch emulator is usable for non-network work only. Its fresh flash has
no working NIE stack. A bounded provisioning attempt confirmed that the
control API accepts install paths only below the read-only `/packages` mount,
while the supplied NIE packages are mounted at `/nie2`; adding a nested mount
under `/packages` also fails because that mount is read-only. No reproducible
scratch NIE install was found within the time box, so network ink work must use
the main emulator.

Cleanup removed `InkCaptureD:jbfly`, restarted the main emulator after its link
state wedged, dismissed the PCMCIA card notice, and restored **Newton Chat 1.9**
to **Ready**. `runtime/raw_pkg_server.py` remains the sole listener on
`10.42.0.1:18081`.

Evidence: `runtime/evidence/s3d-before.png`,
`runtime/evidence/s3d-after.png`, `runtime/evidence/s3d-render.png`,
`runtime/evidence/s3d-server.log`, `runtime/evidence/s3d-main-restored.png`,
and `runtime/evidence/s3d-result.txt`.

---

## Stage 4 result — 2026-07-26

Stage 4 is proven end to end with a real vision model. `InkPad:jbfly`
captured four real strokes drawn on the main emulator, reported **`4 strokes`**
on its status line, posted its own `NSI1` body, and displayed the model's
reading **`A square.`** No `-48200` alert appeared, and none appeared on a
settled screenshot fifteen seconds later.

### The model call

The backend is the one already installed and authenticated in this repo:
`codex-cli 0.145.0` under ChatGPT auth, config model `gpt-5.6-sol` with
`model_reasoning_effort = high`, invoked with no `-m` override. `codex exec`
accepts images with `-i/--image`, so no SDK, dependency, or OCR was needed.
The exact shape, one blocking `subprocess.run` in the same boring style as
`server.py`'s `CodexBackend`:

```sh
codex exec --sandbox read-only --skip-git-repo-check --cd <tmpdir> \
  --json -i <render.png> -- "<INK_PROMPT>"
```

`-i` is variadic, so the `--` before the prompt is required; without it the
prompt is swallowed as a second image path and `codex` blocks reading stdin.

Measured latency, host-side wall clock, same CLI and prompt:

| Payload | Latency |
|---|---:|
| One-stroke Stage 3 render | 9.0 s |
| Four-stroke square (the device round's payload) | 15.0 s |

Both sit well inside the client's 150 s input timeout, so R7 is answered by
measurement rather than architecture: the send stays **synchronous**. No job
id, no polling, no queue.

The host replies `INK <reading>\r\n`. That four-byte prefix is the whole
protocol change — it is all the Newton needs to tell the body apart from the
HTTP header lines its endpoint also delivers. A backend failure returns 502
with the same `INK ` prefix, so the device shows the error instead of hanging.
There is no canned fallback: `NEWTON_FAKE_BACKEND` was deliberately not wired
into the ink path.

### The two defects

**`-48200` after the reply (the Stage 3 defect).** Stage 3 called `Stop()`
from inside `InputScript`, disposing the endpoint while `Input()` was still on
the stack; the throw unwound past the `|evt.ex.comm|` handler. Teardown now
happens only from `CompletionScript`, deferred one second by `AddDelayedCall`
— the same idiom `harness-client` already uses for its peer-close path.

**`-48402` on open (found this stage).** `protoDivider` draws its label
unconditionally, and it inherits the app's `title` slot unless the child
frame shadows it. Shadowing with `title: nil` throws; `title: ""` renders a
plain rule and opens cleanly. This cost most of the round, because a package
that throws during view setup is indistinguishable from one that failed to
install — until the Newton itself says so. The Extras drawer's info menu
surfaced the real message, *"the package … was not installed because a package
by the same name is already installed"*, which proved the install had
succeeded all along and the fault was in the view.

Two smaller landmines worth recording: `install-and-launch.sh` fires `Open()`
immediately after `install`, and on a package this size the open loses the
race and raises `-48402` on its own; and a modal alert left on screen makes
every subsequent diagnosis ambiguous, so drain alerts before concluding
anything.

### UX

Stock protos only, no custom drawing, no settings, no chrome. A hint line
(`Draw here, then tap Send`), a rule, a 280×262 writing area that is the
dominant surface, a rule, a quiet status line, and `Clear` / `Send`.

The status line is the whole state machine: `Ready` → `N strokes` →
`Sending...` → `Thinking...` → the reading, or a readable error. A single
`busy` slot is the entire double-Send guard. The ink is never erased on tap —
`Clear` is the only thing that discards it, and it refuses while a request is
in flight. A 150 s watchdog reports `The host did not answer. Your ink is
still here.` rather than leaving the app stuck in `Thinking...`.

The encoder no longer carries the hardcoded `+16 / +58` screen offset Stage 3
used. `ViewStrokeScript` runs on the ink view, so it reports its own
`GlobalBox()` origin upward and the offset cannot rot when a view moves.

### Known imperfection — RESOLVED in Stage 5 (see below)

> Fixed on 2026-08-03 by `InkPad2:jbfly`: retained polygons drawn in a
> `ViewDrawScript`. Read the Stage 5 section for the API answer and the
> screenshots. The paragraph below is kept as the record of the defect.

**The ink is not visible.** NewtonOS hands a bare `clView` with
`vStrokesAllowed` a transient stroke and erases it once `ViewStrokeScript`
consumes it; nothing retains it. The stroke count, the upload, and the reading
are all correct, but the writing area looks blank after the pen lifts, which
is the wrong feel for a sketch app. Making it visible means a real redraw
subsystem — keeping shape objects per stroke and drawing them in a
`ViewDrawScript` — which is exactly the "large redraw subsystem" this design
said to avoid at this stage. `Clear` already calls `Dirty()` + `RefreshViews()`,
so it will erase visible ink for free once ink is retained. A cosmetic
side effect of that refresh: the two dividers render at different weights
after a `Clear`.

### Single next action after ink

**Retain and render the ink**, by holding a shape per stroke and drawing them
in a `ViewDrawScript` on the capture view. It is the one thing standing
between this and a sketch app someone would actually use, and it needs one
unverified symbol confirmed first — whether `MakePolygon` accepts the flat
Y/X array `GetPointsArray` returns, or whether per-segment `MakeLine` is
required. **Done in Stage 5; the answer is one `MakePolygon` per stroke with
the pair order swapped.**

Evidence (Stage 4): `runtime/evidence/s4-open.png`, `runtime/evidence/s4-drawn.png`,
`runtime/evidence/s4-sending.png`, `runtime/evidence/s4-reply.png`,
`runtime/evidence/s4-reply-settled.png`, `runtime/evidence/s4-cleared.png`,
`runtime/evidence/s4-render.png`, `runtime/evidence/s4-emulator.log`,
`runtime/evidence/s4-main-restored.png`, and
`runtime/evidence/s4-result.txt`.

---

## Stage 5 result — visible ink — 2026-08-03

The pen-up defect is fixed. `InkPad2:jbfly` (version 2) keeps one polygon
shape per stroke and paints them in a `ViewDrawScript` on the capture view,
and it grows the third button the original design asked for: `Clear`,
**`Undo`**, `Send`. Three `/drag` strokes stayed on the canvas after pen-up,
`Undo` removed only the last one, and `Clear` wiped all of them — screenshots
below. Nothing on the network path changed: the encoder, the 16 KiB cap and
the whole `Send` flow are byte-for-byte the Stage 4 code, and this round used
no host, no server and no `/ink` POST at all.

### The API answer (the Stage 4 `[verify]`, settled)

`MakePolygon` is the right call and it needs **no** per-segment `MakeLine`,
but it does not take `GetPointsArray`'s array as-is — the pair order is
reversed:

- `MakePolygon(pointArray)` — *"An array of x and y coordinate pairs
  specifying the vertices of the polygon."*
  (`refs/NewtonProgrammerRef20.txt:36929-36934`; same wording in the Guide,
  `refs/NewtonProgrammerGuide20.txt:32928-32931`.)
- `GetPointsArray(unit)` — *"The first element contains the Y coordinate of
  the first point, the second element contains the X coordinate, and so on.
  (Note that this is the reverse of the usual way that coordinate pairs are
  written.) Coordinates are global; that is, they are relative to the
  upper-left corner (0, 0) of the screen."*
  (`refs/NewtonProgrammerRef20.txt:29883-29887`.)

Both claims were then checked on the device with `runtime/ns_eval.py`, because
the docs alone do not prove what this ROM does:

| Probe | Result | What it settles |
|---|---|---|
| `ClassOf(MakePolygon([10,10,50,50,90,10]))` | `'polygon` | a flat numeric array is accepted; no `MakeLine` loop, no hand-built binary |
| `ShapeBounds(MakePolygon([0,0,100,10,0,20]))` → `left/top/right/bottom` | `0/0/101/21` | read as **x,y** pairs. Y,X would have given `0/0/21/101` |
| drag `60,100 → 200,160`, then read `strokes[0]` | `y0=100 x0=60 n=128` | `GetPointsArray` really is **screen-global**, exactly as the ref says |
| `:CountStroke([280,60,280,140,210,140], 16, 54)` (a bent stroke injected by hand) | canvas shows an open "L" | `MakePolygon` does **not** close the figure — safe for handwriting |

So the whole conversion is a pair swap plus the view origin:

```newtonscript
coords[index]     := points[index + 1] - originLeft;   // x
coords[index + 1] := points[index]     - originTop;    // y
```

and the draw is one call with the default style frame — `penSize` 1,
`penPattern` `vfBlack`, `fillPattern` `vfNone`
(`refs/NewtonProgrammerRef20.txt:35382-35420`), so an unclosed polygon draws
as a hairline polyline and nothing is filled:

```newtonscript
ViewDrawScript: func()
begin
    local shapes := self:Parent().shapes;
    if shapes and (Length(shapes) > 0) then :DrawShape(shapes, nil);
    return nil;
end,
```

`DrawShape` takes the whole array in one call
(`refs/NewtonProgrammerRef20.txt:37299-37308`), so N strokes cost one message.
Retaining the *original* stroke unit was never an option and the refs say so
outright: *"This object is valid only while the various recognition-related
ViewXxxScript methods are being called. Do not attempt to save units for later
use."* (`refs/NewtonProgrammerRef20.txt:29243-29245`). A shape per stroke is
the cheapest thing that survives pen-up.

### The one trap

The probe build drew the polygons straight from `GetPointsArray`, and the ink
landed **+16,+54** down-right of where the mouse drew it
(`runtime/evidence/e1ink-0-probe-offset.png`) — precisely the ink view's
`GlobalBox` origin (app view `left 8/top 24` + ink child `left 8/top 30`).
`DrawShape` draws in view-local coordinates and the points arrive global, so
the origin has to come off. One rebuild fixed it and the strokes then landed
exactly under the drag.

That measurement also exposes a defect in code this round deliberately did not
touch: **`Encode()` adds the same origin** (`examples/ink-capture/Main.newt`,
`local x := points[1] + self.inkLeft`). The points are already global, so the
`NSI1` body the host renders is shifted by the same +16,+54 and ink near the
bottom-right of the canvas can fall outside the 320×480 render. Stage 3's
hardcoded `+16 / +58` was the same mistake with a constant. The Send path was
out of scope here (no host, no network), so it is left for Track E2/E3, where
it can be re-proven over the wire.

### Repaint points

`Dirty()` + `RefreshViews()` is wrapped in one `Repaint` method and called
from exactly three places: the end of stroke capture, `Undo`, and `Clear`.
`Undo` is `SetLength(self.strokes, n-1)` on both retained arrays — the
point arrays and the shapes are grown and shrunk together, so the encoder and
the canvas can never disagree. Both arrays are re-made in
`ViewSetupDoneScript`, because the template's literal `[]` lives in the
read-only package.

### The round

Isolated instance `e1ink`, flash seeded from
`internal-before-round9-loader-20260725-195622.flash` per
`docs/parallel-emulators.md` — which skipped the first-run tour entirely and
cost about 90 s. Install and open via `scripts/install-and-launch.sh` with
`NEWTON_CONTROL_URL` pointed at the instance. No alert appeared at any point.

| Screenshot | What it shows |
|---|---|
| `runtime/evidence/e1ink-1-open.png` | opens clean, canvas blank, `Ready` |
| `runtime/evidence/e1ink-2-three-strokes.png` | **the gate** — three strokes still on the canvas after pen-up, each where it was dragged, `3 strokes` |
| `runtime/evidence/e1ink-3-undo.png` | `Undo` dropped only the last stroke, the other two remain, `2 strokes` |
| `runtime/evidence/e1ink-4-polyline.png` | injected bent stroke draws as an open "L" — no closing chord |
| `runtime/evidence/e1ink-5-clear.png` | `Clear` wiped everything, `Ready` |
| `runtime/evidence/e1ink-6-redraw.png` | capture and repaint still work after a `Clear` |
| `runtime/evidence/e1ink-7-final-build.png` | the exact committed build, removed/reinstalled and re-proven |
| `runtime/evidence/e1ink-0-probe-open.png`, `runtime/evidence/e1ink-0-probe-offset.png` | the probe build and its +16,+54 offset |

Full transcript with every `ns_eval` probe and its answer:
`runtime/evidence/e1ink-result.txt`.

---

## Track F2 result — the origin fix, and ink inside the chat app — 2026-08-03

The Stage 5 section closes with a defect it deliberately did not fix: `Encode()`
added the canvas origin to points that `GetPointsArray` already hands back in
**screen-global** coordinates, so every host render was shifted +16,+54 and ink
near the bottom-right could fall outside the 320×480 page. Track E2 owned it
"because it needs the wire to prove". This round had the wire.

### The fix

Two lines, and the origin now exists in exactly one place:

```newtonscript
// Encode (host render, global coordinates) — was `points[1] + self.inkLeft`
local x := points[1];
local y := points[0];

// StrokeShape (on-screen repaint, view-local coordinates) — unchanged
coords[index]     := points[index + 1] - originLeft;
coords[index + 1] := points[index]     - originTop;
```

The `inkLeft`/`inkTop` slots are gone rather than left unused, so there is no
origin for the encoder to reach for. `test_newton_client_source.py` pins both
halves.

### The measurement

Two drags on the canvas, at screen coordinates `60,110 → 60,280` and
`60,280 → 220,280` — an "L". They stayed on the canvas after pen-up
(`runtime/evidence/f2round-13-ink-drawn.png`, status `2 strokes`). One `Send`:

```text
10.42.0.1 - - [03/Aug/2026 21:43:56] "POST /ink HTTP/1.0" 200 -
```

The PNG the host wrote (`runtime/evidence/f2round-15-ink-host-render.png`, kept
byte-for-byte from `runtime/evidence/ink-latest.png`) contains 664 black pixels
spanning:

| | drawn | rendered | with the old bug |
|---|---|---|---|
| x | 60 … 220 | **60 … 221** | 76 … 237 |
| y | 110 … 280 | **110 … 281** | 164 … 335 |

The extra pixel on each maximum is the host's 2×2 dot brush
(`pkg_publisher.py:244-247`). Nothing is shifted.

The vision call was the real one — `codex exec -i`, no stub — and answered:

```text
An L-shaped right angle.
```

which the client appends to the **chat transcript** as `Ink: An L-shaped right
angle.` rather than showing it on a private status line, then hides the overlay
so the answer is where every other answer is
(`runtime/evidence/f2round-16-ink-reply.png`).

### What the overlay is

A `clView` child of the chat window, `viewFormat: vfFillWhite` (that is what
makes it opaque), holding the hint line, the capture canvas, the stroke-count
line and `Clear` / `Undo` / `Send` / `Chat`. Three mechanics are worth carrying
forward:

- **`Show()` only works on a view that was opened and then hidden**
  (`refs/NewtonProgrammerRef20.txt:4650-4652`), so the panel ships with
  `vVisible` set and a 150 ms delayed call hides it at launch. There is no way
  to declare it hidden and message it later.
- **`vfFrameBlack` on its own draws nothing** — the frame pen width is zero
  without `vfPen` — so the canvas box was invisible for two builds. Two
  `protoDivider` rules mark the writing area, exactly as `InkPad2` did.
- **The ink POST rides the NIE link the chat already holds.** The first build
  called `:Stop()` to drop the chat link and re-grabbed one; `connect` then
  failed with `-16009`, *"Phone connection was cut off, or invalid call when not
  connected"* (`refs/NewtonProgrammerRef20.txt:73102`). One link, two endpoints,
  and the chat session is never interrupted by drawing.

The POST itself was rewritten from `InkPad2`'s synchronous form (`async: nil`
plus a blocking `Input()`, which would have frozen the app for the whole vision
call) onto the chat client's asynchronous machinery: `async: true` Bind,
connect and output, and a `SetInputSpec` whose `InputScript` looks for the
`INK ` prefix.

Full round record: `runtime/evidence/f2round-round.txt`.

---

## Sketch-note pivot (design) — 2026-08-04

**This section is a plan, not a result.** Nothing below is built. What *is*
proven is the thing the plan rests on: the sketch-note soup probe in
`docs/newtonscript-eval.md`, "Seventeenth finding", with its transcript at
`runtime/evidence/sketchprobe-probe.txt`.

### Why the canvas dies

The first full-stack hardware test found that the client's capture canvas
"drops all but the first stroke when drawing freely" (`docs/ROADMAP.md` status
log, 2026-08-03, finding 5). The human's direction was not to fix it: stop
reinventing an ink canvas, and let people draw in stock Notes with its real
drawing tools instead. The probe says that works — a native sketch note keeps
**every** stroke, including strokes that physically cross, and hands the
geometry back exactly:

> Five pen strokes → five data items, each holding exactly one stroke.
> 271 points in 89 bytes of compressed ink. Nothing merged and nothing dropped.

So the pivot trades code we wrote and got wrong for code Apple wrote and got
right.

**What is deleted when this ships:** the `Ink` overlay Track F2 folded into the
chat client — the capture `clView`, its `ViewStrokeScript`, the retained
`strokes`/`shapes` arrays, the `MakePolygon` + `ViewDrawScript` repaint, the
`Repaint`/`Undo`/`Clear` methods and the `Clear`/`Undo`/`Send`/`Chat` button
bar. The multi-stroke defect goes with it **unfixed**, because the code that
has it is gone. Net client size goes down.

**What survives and moves behind the new button:** `Encode()`'s `NSI1` emitter
(host-proven, origin bug already fixed — "Track F2 result"), the asynchronous
`/ink` POST machinery (`async: true` Bind/connect/output plus the
`INK `-prefix `InputScript`), and the transcript append. None of that is
touched.

### One button, one meaning

The failure that motivates this is not only the canvas. On hardware
2026-08-03 the human drew a cat as a sketch note, tapped **Ask Note**, and got
an answer about an older D&D *text* note. So the design rule is a UX rule
first:

> **One button whose meaning is "send the newest note, whatever kind it is."**

Never a "Ask Note" and a separate "Ask Sketch" the user has to choose between,
and never a silent skip. The routing happens inside, on the classification the
probe proved:

| Newest note's `data` contains | Route |
|---|---|
| only `'para`, no embedded ink words | the chat path, exactly as today — `Send(text)` over `MSG`/`MSGP` |
| `'poly` and/or `'ink2`, no `'para` | the `/ink` vision path |
| **both** | **one `/ink` request carrying both** — see below |
| a `'para` whose `styles` holds `'inkWord` runs | treat as mixed: the ink words are drawing, the rest is text |
| nothing readable | say so on the status line; never fall through to an older note |

Order the tests `'para` → `'poly` → `'pict` → `ClassOf(item.ink) = 'ink2`.
Testing `item.points` first is a trap: it resolves through every ink item's
`_proto` and returns an empty polygon (seventeenth finding).

Ink Text needs saying out loud because it is invisible in the `data` array: it
adds no item, it embeds `'inkWord` binaries in a paragraph's `styles` and
leaves placeholder character **63233 (0xF701)** in `text`. A7's `ReadNote`
(`Main.newt:683-689`) reads that `text` and cleans it without knowing, so
**today it puts 63233 into the prompt**. The client must at minimum strip the
placeholder; the better answer is to expand those words and send them as
strokes like anything else — `InkConvert(w, 'ink2)` then `ExpandInk`, with
`GetInkWordInfo` supplying the bounds, proven on this ROM at
`class=inkWord len=22 w=52 asc=7 desc=0 conv=ink2 ns=1 np=46`.

### The mixed-note rule, and why it is "send both"

A mixed note goes out as **one** `/ink` POST: the strokes as `NSI1` `S` lines,
the note's paragraph text as a single new `H <text>` line after the header.
The alternatives were considered and lost:

1. *Strokes only, ignore the text* — repeats the bug in the other direction.
2. *Text only, ignore the strokes* — this is literally today's behaviour.
3. *Two requests* — two model calls, two replies, and an ordering problem in a
   transcript that has one column.

Sending both is one round trip, one reply, one transcript line, and it can
never silently drop half of what the user put on the page. It is also just
better input: a word written under a drawing is the most useful token in a
vision prompt. The cost is one line in the client encoder and one branch in
the host parser.

**Wire delta.** `pkg_publisher.py:308-341` currently requires
`len(lines) == stroke_count + 1` and every non-header line to start with `S`.
The change is to permit at most one `H <text>` line immediately after the
`NSI1` header, cap it at ~200 ASCII characters, and pass it to `interpret()`
as prompt context. **Keep the `NSI1` tag** — the header's four fields do not
change, `H` is optional, and the physical MP2000 still runs an older client, so
a new host must keep parsing bodies that have no `H` line.

### Coordinates — the one real encoding hazard

`/ink` validates the canvas as exactly `320x480` and rejects any point outside
it (`pkg_publisher.py:320` and `:337`). Sketch points do **not** arrive in
screen coordinates: they are absolute in the paper roll's own space, which for
the probe note meant a uniform `0,-36` offset from where the pen actually went,
and which for a long note can exceed 480. So the client must translate before
encoding: take the minimum `viewBounds.left`/`.top` across the note's drawn
items, subtract it from every point, and clamp. That preserves the existing
320×480 contract and existing host validation, and renders the sketch as drawn.

Two converters are needed, not one, because the two kinds disagree on both
origin and axis order (seventeenth finding):

```newtonscript
// 'poly item — points are RELATIVE to viewBounds, ordered x,y
local a := PointsToArray(item.points);           // [type, n, x1,y1, x2,y2, ...]
x := a[k]     + item.viewBounds.left;
y := a[k + 1] + item.viewBounds.top;

// 'ink2 item — points are ABSOLUTE in the note's space, ordered y,x
local bundle := ExpandInk(item, 0);              // 0 = screen resolution
local pts    := GetStrokePointsArray(GetStroke(bundle, i), 0);
y := pts[k];
x := pts[k + 1];
```

Getting either backwards yields plausible-looking wrong geometry, which is the
expensive kind. `test_newton_client_source.py` should pin both, the way it
already pins the `Encode()` origin fix.

### Which component ships it — recommend the chat client (Chat A9)

**Recommendation: the client button, not a `/tools` op.** Four reasons:

1. **The reply belongs in the user's transcript.** A `/tools` op answers the
   *host agent*, not the person holding the Newton. The flow being designed is
   "draw, tap once, read the answer on the Newton", and the client already
   does that last step.
2. **The transport is already in the client and nowhere else.** It owns the NIE
   link, the asynchronous `/ink` POST and the `INK ` reply parsing (Track F2
   result). A tools op would need a second package installed and running (true
   when this was written; Track L1 has since merged the two into one package, so
   only the reply-shape half of this reason still applies), and
   the tools reply is a small single-line escaped ASCII envelope
   (`examples/harness-tools/Main.newt` `Reply`, now `ToolReply` in the
   tools-channel section of `examples/harness-client/Main.newt`) — the wrong shape for a
   279-point payload, and the twelfth finding's starvation lesson says building
   that string synchronously is exactly how the long-poll link dies.
3. **It replaces code instead of adding it.** The overlay comes out, a
   content-aware read goes in.
4. **Deployment is already scheduled.** The human has to install a new client
   anyway for A8's transcript-scrolling fix; this rides that identity bump
   rather than buying its own.

**Where a tools op still makes sense — later, not now.** A read-only
`sketch_note` op would let Track J2's web UI render a note's strokes as inline
SVG and let the Track D agent look at a drawing with no human tap at all. Same
extraction code, different consumer. Build it after A9 proves the extraction on
hardware, so the NewtonScript is debugged once.

### Finding the right note — the second half of the hardware bug

`ReadNote` (`examples/harness-client/Main.newt:675-691`) collects only items
where `item.viewStationery = 'para`, and `AskNote` (`:696-706`) refuses with
`"Newest note has no text"` when that comes back empty. That explains the
silent skip. It does **not** by itself explain answering from the older D&D
note, and the probe found the missing half:

> `id3 ts=64477370 mod=64477379` — the sketch note's creation stamp and its
> modification time are nine minutes apart.

`timeStamp` is **creation** time and never moves (`docs/notes-bridge.md:41-42`);
drawing updates `EntryModTime` only. `ReadNote` orders by
`{indexPath: 'timeStamp}` (`Main.newt:677`), so a drawing added to an
*existing* page never becomes "newest" and an untouched older note wins. That
is the shape of what the human saw.

And the obvious fix is not available: `Query({indexPath: '_modTime})` on the
Notes union soup throws `evt.ex.fr.store` on this ROM — **there is no
modification-time index**. So:

> Walk the `timeStamp` cursor back from the end over at most **16** entries and
> take the highest `EntryModTime`; fall back to the last entry.

Bounded work, so the twelfth finding's event-loop starvation cannot return.
**Honest limit:** a drawing added to a note older than those 16 still loses.
The real fix for that case is Track F3 — grab the *currently open* note rather
than the newest — which stays the right long-term answer and is still
unexplored.

### The flow, end to end

1. Human draws in stock Notes. The drawing tools are the `A` button in the
   Notes bottom bar → **Sketches** (tap coordinates are tabulated in the
   seventeenth finding); no stationery to pick, there isn't one.
2. Switches to Chat, taps **Ask**.
3. Client finds the newest-by-`EntryModTime` entry within a 16-entry window and
   classifies its `data` array.
4. Text only → `Send(text)`, unchanged.
5. Any drawn items → convert each (the two converters above), translate by the
   note's bounding box, emit `NSI1` plus an optional `H` line, async POST to
   `/ink`.
6. Host renders the PNG it already renders, calls the vision model with the
   hint as context, replies `INK <reading>`.
7. Client appends `Sketch: <reading>` to the transcript, same as
   `Ink: An L-shaped right angle.` does today.

### Budget, and what this does *not* need

The probe note held 9 drawn items and 279 points. At the format's ~4 ASCII
bytes per delta point that is roughly 1.1 KB — comfortably inside the 16 KiB
single-body cap (`pkg_publisher.py:313`). **The multi-part `/ink` POST that
Track E3 has been carrying is therefore still not needed**, and should stay
unbuilt until a real drawing exceeds the cap. Cap the client at ~400 points and
~64 items, and say so on the status line when it truncates, rather than
building an unbounded string on the Newton.

> **Superseded by EF6 (2026-08-04).** Risk S1 below landed on real hardware: a
> handwritten sentence blew past 400 points and the client *dropped whole
> strokes*, so the host was asked to read a drawing that was missing most of
> itself. Truncating is the wrong answer for ink. EF6 raises the budget to
> `kMaxPoints := 1600` / `kMaxItems := 256` (arithmetic against the 16 KiB cap;
> **measured 4.27 bytes per point** on the wire) and, when a note still exceeds
> it, thins points *within* each stroke at an integer stride so every stroke
> survives at lower resolution. See the ROADMAP status log's EF6 entry and
> `runtime/evidence/ef6round-ink-decimation.txt`.

### Open risks

| # | Risk | Cheapest experiment |
|---|---|---|
| S1 | A real freehand curve produces far more points than a straight `/drag` did | Draw a cat by hand in Einstein via noVNC, count points; the emulator `/drag` is start-to-end only (`emulator/control.py:185`) so the probe could not measure this |
| S2 | The 16-entry `EntryModTime` window is wrong for how the human actually files notes | Ask; or ship it and watch |
| S3 | `ExpandInk` cost on a large sketch holds the event loop | Time a 400-point note on-device before shipping; cap already specified |
| ~~S4~~ | ~~Ink Text notes fall through the classifier~~ | **Closed by the probe** — Ink Text adds no data item, it embeds `'inkWord` in a `'para`'s `styles` with placeholder 63233 in `text`, and it expands via `InkConvert` → `ExpandInk`. Folded into the routing table above |

---

## A9 result — the pivot shipped — 2026-08-04

**Built and emulator-proven.** The section above is now history: `Chat A9`
(`HarnessClientA9:jbfly`, v2.4-a9, project version 17) ships one **Ask** button
that sends the newest note whatever kind it is, and the capture canvas is
deleted. (The same Ask code now ships as **Egg Freckles**,
`EggFrecklesEF1:jbfly`, v1.0-ef1, package version 18 — Track L1 renamed the
client and folded the tools package into it; none of the ink behaviour below
changed.) Full round record with every probe and its verbatim output:
[`a9ask-round.txt`](../runtime/evidence/a9ask-round.txt). Proven on isolated
instance `a9ask` (seeded flash) against `NEWTON_FAKE_BACKEND=1 server.py:6801`
and `runtime/raw_pkg_server.py` on `10.42.0.1:18081`, with **real `codex`
0.146.0** answering every vision call — no stub readings.

### The three routes, each measured

| Note | What Ask did | Evidence |
|---|---|---|
| text only | chat path, `Send(text)` over `MSG` | `a9ask-02-text-note-ask.png`; the turn is in `state/session.json`; `POST /ink` count **0** |
| 3 sketch strokes | one `/ink` POST, **no** `H` line | `a9ask-05-sketch-reply.png`, render `a9ask-06-sketch-render.png`, reply `Ink: The letter N is written.` |
| text + 3 strokes | **one** `/ink` POST carrying both | `a9ask-08-mixed-reply.png`, render `a9ask-09-mixed-render.png`, reply `Ink: A simple outline of a cat's head.` |

The mixed case is the one that justifies the design. The drawing was a bare
triangle; the note said `the cat`; the reading was *"A simple outline of a cat's
head."* The publisher log shows why:

```
INK PROMPT '... No preamble, no markdown. The drawing is accompanied by
            this note text: the cat'
```

### Coordinates came out exactly as designed

Three `/drag` strokes at the probe's own screen coordinates read back with the
same uniform `0,-36` note-origin offset, and the minimum `viewBounds` across
the drawn items was `(58,82)`:

```
n=3 [0] vb=58,82  np=17 first=x60,y84   last=x60,y184
    [1] vb=98,82  np=17 first=x100,y84  last=x180,y184
    [2] vb=208,102 np=17 first=x210,y104 last=x280,y104
```

`EncodeInk` therefore emitted the vertical stroke starting at `(2,2)`, and the
host PNG renders it there. The body, read straight off the live app through
`ns_eval` (CR shown as ` / `):

```
NSI1 320 480 5 / H the cat / S 17 2 2 6 0 6 0 4 0 ... / S 51 62 2 -1 1 ...
```

### NSI1 `H` grammar, as shipped

```
NSI1 <width> <height> <strokeCount>     header, unchanged, four fields
H <text>                                OPTIONAL, at most one, immediately
                                        after the header, before any S line
S <count> <x> <y> <dx> <dy> ...         exactly <strokeCount> of these
```

`<text>` is 1–200 characters, all printable us-ascii. The client truncates at
`kHintBytes := 200`; the host rejects an empty hint, an over-long one, a second
`H` line, and an `H` line that appears after an `S` line
(`test_pkg_publisher.py::test_ink_hint_line_is_optional_and_reaches_the_prompt`).
**The tag stays `NSI1` and `H` stays optional** because the physical MP2000 runs
an older client whose bodies have no `H` line and must keep parsing. The host
appends the text to `INK_PROMPT` as `INK_HINT_PROMPT`; nothing else changed in
`/ink`.

### The cat/D&D bug is dead

Set up so creation order and modification order disagree — a D&D text note
created *after* the cat note, then two more strokes drawn on the older cat page:

```
now=64477418  id6 ts=64477415 mod=64477415 n=1   <- newest CREATED (D&D text)
              id5 ts=64477411 mod=64477418 n=6   <- newest MODIFIED (the cat)
```

A7 answered from `id6`. A9's bounded 16-entry `EntryModTime` scan picked `id5`
and POSTed its strokes: `Note: the cat` / `Ink: A cat.`
(`a9ask-11-modorder-reply.png`). The render `a9ask-12-modorder-render.png` shows
the triangle **plus two crossing strokes kept separate** — the property the
deleted canvas never had.

Two `EntryModTime` facts fell out that the design did not anticipate, and they
bound how well this can ever work. They are written up as
`docs/newtonscript-eval.md`, "Nineteenth finding": the stamp has **one-minute
granularity** (so two notes touched in the same minute tie, and the scan's
strict `>` leaves the later-created one winning), and it is **stale until you
leave the note** (`Length(data)` had already grown while the stamp had not).

### What was deleted

The overlay `clView`, its `ViewStrokeScript`/`ViewDrawScript`, the retained
`strokes`/`shapes` arrays and `strokeCount`, `MakePolygon`/`StrokeShape`,
`Repaint`, `CountStroke`, `InkUndo`, `InkClear`, `ShowInk`/`HideInk`/
`InkStatus`/`StrokeText`, the `Clear`/`Undo`/`Send`/`Chat` button bar, the `Ink`
button, and `inkPanel`/`inkCanvas`/`inkStatusView`. The multi-stroke defect went
with it, unfixed. `ReadNote` and `AskNote` are gone too, replaced by
`FindNewest` + `CollectNote` + `Ask`.

**What survived, untouched:** the `/ink` POST machinery — `InkOpen`, `InkBound`,
`InkPost`, `HandleInkLine`, `InkDropped`, `InkFailed`, `InkDone`, `InkStop`, all
three `async: true` calls and the `INK `-prefix `InputScript`. The pinned count
`SOURCE.count("async: true") == 9` is unchanged from A8, which is the test that
proves the transport was not disturbed.

### Two deviations from the design above, and why

1. **The transcript prefix stays `Ink: `, not `Sketch: `.** The design proposed
   renaming it. The prefix is pinned by
   `test_the_ink_overlay_shares_the_chat_link` and means "this came back from
   `/ink`", which is still exactly true; renaming it would churn a test for no
   behaviour.
2. **The truncation notice goes in the transcript, not on the status line.**
   The design said status line. `InkPost` overwrites the status with
   `Thinking...` a moment later, so a status-line notice would be invisible.

### Still open

- **Not on hardware.** The physical MP2000 runs A7. A8 and A9 are both
  emulator-only, and so is their Track L1 successor **Egg Freckles**
  (`EggFrecklesEF1:jbfly`) — install that one and skip A8/A9.
- **Risk S1 is still unmeasured.** Every probe stroke is a straight `/drag`
  (`emulator/control.py:185`), 17–51 points. A real freehand curve may produce
  far more. **Measured 2026-08-04: it does.** A human's handwritten sentence on
  the MP2000 exceeded the 400-point cap and lost strokes (fifth hardware test),
  and 37 emulator drags produced 2569 points where the same count of probe-style
  strokes would have produced ~630. EF6 replaced the cap-and-truncate with
  decimation; this risk is closed.
- **Risk S3 (ExpandInk cost) is untimed.** The largest note measured here was
  153 points across 5 strokes and felt instant, well short of the 400 cap.
  EF6 measured the other end: collecting 2569 points, thinning them and encoding
  a 5585-byte body held the NewtonScript event loop long enough that a `/tools`
  ping issued mid-encode took 5.77 s instead of its usual sub-second, but the
  channel stayed up and answered. So it is not free, and it is not dangerous.
- A note older than the 16-entry window still loses. Track F3 — read the
  *currently open* note — remains the real answer and is still unexplored.
