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

### Known imperfection

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
required.

Evidence: `runtime/evidence/s4-open.png`, `runtime/evidence/s4-drawn.png`,
`runtime/evidence/s4-sending.png`, `runtime/evidence/s4-reply.png`,
`runtime/evidence/s4-reply-settled.png`, `runtime/evidence/s4-cleared.png`,
`runtime/evidence/s4-render.png`, `runtime/evidence/s4-emulator.log`,
`runtime/evidence/s4-main-restored.png`, and
`runtime/evidence/s4-result.txt`.
