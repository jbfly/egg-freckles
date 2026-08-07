# Progress and feedback design

Date: 2026-08-07. P2 is source-complete in EF15 and P4 in EF18; emulator and
hardware proof remain deliberately human-gated.

## Bottom line

**Implementation result (EF15 + EF18).** Intermediate multipart `/ink` requests still
return `INKP` immediately while their vision futures run concurrently. The final
request now flushes close-delimited `STATUS received`, `STATUS rendered`, and
`STATUS vision` lines before waiting for the combined reading, then ends in one
`INK` or `INKERR` line (`pkg_publisher.py:458-490,628-640`). The Newton keeps
`Sending page n/total` visible during each upload and maps those fixed STATUS
lines to its existing status surface. EF18 gives the Notes-menu agent the same
surface as a small root-level `protoFloatNGo`: it opens immediately before
`SendInk`, stays non-modal over Notes, mirrors `SetStatus`, shows filing/error
completion for 1.5 seconds, and closes (`examples/harness-client/Main.newt:149-
179,208-258,306-359`). Source and socket-level tests pin the Notes path, immediate
`INKP`, ordered STATUS-before-INK, no final `Content-Length`, and EF14's
send-owned radio lifecycle.

Use one tiny status record everywhere: a short machine phase, a human sentence,
and optional `n/total`. Render transient work in the existing Newton status
line, write the same record to the host log, and reserve the transcript or filed
note for durable results and errors. Do not build a telemetry service, job
queue, progress database, or always-on push channel.

For ink, the server can report progress on the request that already keeps the
radio up: after accepting the body, return a close-delimited HTTP/1.0 response
whose body contains zero or more `STATUS` lines and ends with the existing
`INK` result line. For chat, use the existing framed `STAT` operation. Both are
fixed messages interpreted by named client code; neither evaluates received
NewtonScript.

The first user-visible slice should be only this:

1. keep `Sending page n/total` visible while each ink page is uploaded;
2. then show `Server is reading page n/total...` while that page's vision call
   runs; and
3. log `received`, `rendered`, `vision start/done`, `reply assembled`, and
   `reply filed` at the corresponding host/Newton boundaries.

That directly fixes the hardware-proven failure mode: a six-part note takes
about 1–2 minutes because six roughly 9-second vision reads run sequentially,
and the first “nothing came back” report was actually a send still in flight
(`docs/ef13-memory-diagnosis.md:229-245`).

## Constraints that determine the design

- **Fixed operations only.** The client is not an eval target; `Compile(string)`
  is unavailable in this ROM/application context (`docs/START-HERE.md:5-10`,
  `docs/newton-networking-lessons.md:250-251`). `STATUS` is therefore a fixed
  input shape handled by a named method, just like `STAT`, `INKP`, and `INK`.
- **Radio off until send.** The planned lifecycle removes the install-time
  always-on tools poll and permits connections only while the Newton has work
  to send (`docs/chat-ui-and-radio-lifecycle-plan.md:36-60`). Status must ride
  the active chat or ink exchange. There is no background host push.
- **HTTP/1.0 request/response.** `/ink` is already one HTTP/1.0 request per part,
  with the server closing each response before the client opens the next part
  (`examples/harness-client/Main.newt:2148-2163,2190-2230`;
  `pkg_publisher.py:319-327,462-479`). A response body delimited by connection
  close can contain progress lines before its final result without chunking,
  WebSockets, server-sent events, or another port.
- **NIE progress is not failure.** `'initializing` and `'connecting` are normal
  states and must remain non-error status phases (`docs/newton-networking-lessons.md:235-244`).
- **Keep waits bounded.** Chat and ink model calls already cap at 120 seconds,
  and the client ink watchdog is 150 seconds (`server.py:34`,
  `pkg_publisher.py:55,254-260`,
  `examples/harness-client/Main.newt:2004-2021`). No designed leaf operation is
  allowed to run silently for three minutes; log at every boundary below.

## Inventory of quiet or under-reported work

“Silent” here means the user or operator cannot tell which concrete step is
running. Some rows already show a generic `Connecting` or `Thinking`; those are
still under-reported when several materially different waits share the same
text.

### A. Newton client (`examples/harness-client/Main.newt`)

| Operation | What is quiet today | Typical or bounded wait | Evidence | Required status |
|---|---|---:|---|---|
| Radio/link acquisition | The app says only `Connecting`; normal NIE states are ignored, so the user cannot distinguish radio startup from TCP setup. | Usually seconds; a dead idle link has measured about 7–9 s recovery. | `examples/harness-client/Main.newt:803-832`; `docs/newton-networking-lessons.md:238-243`; `docs/newtonscript-eval.md:413-425` | `radio` — `Turning radio on...`, then `connect` — `Connecting to server...` |
| Endpoint bind/connect and retry | Bind and TCP connect are separate async steps, but only a failed bind reveals itself as `Bind retry`; the connect timeout can run to 45 s. | 5 s bind retry; at most 45 s connect. | `examples/harness-client/Main.newt:839-929` | `connect` — `Opening connection...`; retry text remains visible. |
| Chat send | A short `MSG` changes directly to `Thinking` before its ACK, hiding whether bytes are still leaving the Newton. Multipart `MSGP` does show `Sending n/total`, but only until the last ACK. | Normally sub-second on a live link; each output is bounded at 10 s. | `examples/harness-client/Main.newt:994-1008,1081-1135` | `send` — `Sending message...` or `Sending part n/total...`; change phase only after ACK. |
| Per-part ink upload | `Sending page n/total` is set, but `InkPost` immediately overwrites it with generic `Thinking...`; while the request body is uploading, the user loses the page number. | Hardware-dependent; six parts plus processing took 1–2 min end to end. | `examples/harness-client/Main.newt:1987-2001,2128-2164,2190-2201`; `docs/ef13-memory-diagnosis.md:231-245` | Keep `send` — `Sending page n/total...` until the server emits `received`. |
| Per-part render/vision wait | Every page waits for a blocking vision call, but the screen says only `Thinking...`; it does not identify the page or distinguish rendering from model work. | About 9 s per image in the current code; measured 9–15 s by payload, and the four-part evidence completed one response about every 10–12 s. | `examples/harness-client/Main.newt:2139-2145`; `pkg_publisher.py:246-260`; `docs/ink-client-design.md:342-350`; `runtime/evidence/ef10round-fix2-many-host.log:1-12` | `render` — `Rendering page n/total...`; then `vision` — `Server is reading page n/total...`. |
| Waiting for a chat reply | The existing `STAT THINKING` proves the server started work but says nothing after that until text arrives. | About 6 s in the original real turn; model timeout is 120 s. | `docs/phase3-chat-round.md:18-25`; `server.py:747-767`; `examples/harness-client/Main.newt:1053-1076` | `model` — `Server is writing a reply...`; completion remains the transcript answer. |
| Filing a Notes-menu reply | The headless route stores status only in `aiStatus`; the user sees nothing until a new note appears in AI. The design record already calls a note appearing about 9 s later “a bad experience.” | About 9 s for one image; 1–2 min for the proven six-part note. | `examples/harness-client/Main.newt:153-186,244-285,309-330`; `docs/notes-integration-design.md:199-204,250-260`; `docs/ef13-memory-diagnosis.md:229-245` | While Notes owns the action, show a small non-modal progress view; close it after `Answer filed in AI`. This is later UI work, not the first slice. |
| Ink/chat endpoint teardown and radio-down | Endpoint disposal and `InetReleaseLink` happen after 1 s delayed cleanup with no positive “done/radio off” indication. The new lifecycle is not built yet. | About 1 s deliberate settle, then platform teardown. | `examples/harness-client/Main.newt:2242-2266,2276-2283`; `docs/chat-ui-and-radio-lifecycle-plan.md:36-64` | `disconnect` — `Closing connection...`, then `idle` — `Radio off` briefly before `Ready`. Do not keep a connection merely to report this. |

### B. Host server (`server.py` and `pkg_publisher.py`)

| Operation | What is quiet today | Typical or bounded wait | Evidence | Required status/log |
|---|---|---:|---|---|
| Chat message/part received | `server.py` logs each `MSGP` part and final assembly, but a normal one-frame `MSG` has no equivalent receipt log. Neither path emits a human-specific “message received” phase beyond generic `THINKING`. | Sub-second after connection. | `server.py:672-747` | Log `received` for both `MSG` and `MSGP`; send `STAT` status only when it changes what the user can see. |
| Chat model call | The host logs the Codex argv and errors, but not a start/done pair or elapsed time; the Newton sees only `Thinking`. | About 6 s in the real proof; hard timeout 120 s. | `server.py:516-557,747-767`; `docs/phase3-chat-round.md:18-25` | Log `model start` and `model done elapsed_ms=...`; surface `Server is writing a reply...` on Newton. |
| Chat reply assembly/transmission | Reply chunking and state save are silent on success; only save failure is logged. | Normally sub-second after model completion. | `server.py:651-658,757-767` | Log `reply assembled chars=... parts=...`, then `reply sent`. Do not add each chunk to the transcript. |
| Ink part received/parsed | `INK BODY` already logs mode, part, bytes, strokes, and points. It does not use the same phase vocabulary or tell the Newton that upload completed. | Immediate after body read. | `pkg_publisher.py:335-421` | Emit/log `received` with `n/total`; this is the event that replaces `Sending page...` on Newton. |
| PNG rendered | The PNG is written with no success log, so an operator cannot tell whether time is in parsing, rendering, or the model. | Small compared with the 9–15 s model call; not separately measured. | `pkg_publisher.py:279-318,439-450` | Log/emit `rendered` after `save_ink_png`; no percentage or invented ETA. |
| Vision call | The prompt is logged before one blocking `codex exec`; completion and elapsed time are not. This runs once per ink part. | Commented/measured about 9 s; measured 9–15 s by payload. | `pkg_publisher.py:246-276`; `docs/ink-client-design.md:342-350` | Emit/log `vision start n/total`; log `vision done elapsed_ms=...`; Newton message is `Server is reading page n/total...`. |
| Multipart reply assembly | Each reading is appended in memory; only the final HTTP access log proves a response. There is no “part accepted” or “all readings assembled” log. | Sub-second after the final vision call. | `pkg_publisher.py:423-474` | Log `part done n/total`; on final part log `reply assembled parts=... chars=...`. |
| `/note` accepted and model answered | The JSON file is atomically replaced, then the model call blocks, with no route-specific progress logs. | Model-dominated; bounded by the server/model socket timeout. | `pkg_publisher.py:532-564` | Log `note saved`, `model start/done`, and `reply sent`. This route does not need Newton UI status unless a Newton request is actively waiting on it. |
| Reply note filed | This is **not a host operation** despite often being described that way. `pkg_publisher.py` returns `INK`; the Newton creates and labels the AI note. Today neither side logs a successful filing boundary. | Normally sub-second after final `INK`. | `pkg_publisher.py:462-479`; `examples/harness-client/Main.newt:252-266,288-330` | The Newton emits `filed` locally (`Answer filed in AI`); if a host correlation channel is active, log the acknowledgement, but do not add a new connection solely for it. |

### C. Emulator and tools channel

| Operation | What is quiet today | Typical or bounded wait | Evidence | Required status/log |
|---|---|---:|---|---|
| Emulator package install / injected NewtonScript | `/install` and `/newtonscript` return only `queued`; the command API does not report execution completion. `install-and-launch.sh` therefore queues install and open back to back. | Usually seconds; HTTP client timeout is 10 s, but execution continues after `queued`. | `emulator/control.py:343-356`; `emulator/client.py:60-75,159-162`; `scripts/install-and-launch.sh:1-9` | CLI prints `queued install`, `queued open`; the round script remains responsible for the existing screenshot/OCR completion check. Do not turn the control socket into a job system. |
| Full emulator install round | The script prints `Installing and launching`, then is quiet while the queued commands run and while OCR retries up to five times. | About 2–7 s from the explicit sleeps/retries, excluding build time. | `scripts/newton-round.sh:199-225` | Print one line before each existing step: install queued, launch queued, OCR attempt n/5, confirmed. |
| `ns_eval.py` result wait | After queue acceptance it polls a result file every 50 ms without output until success or timeout. | Default 5 s maximum. | `runtime/ns_eval.py:17-46,58-69` | One stderr line after queueing (`waiting for result, timeout=5s`) and the existing final result/error. No per-poll logging. |
| `POST /tools` fixed operation | The HTTP caller blocks in `Condition.wait_for` with no server log naming the op, dispatch, or completion. Warm calls are fast; a cold/dead-link race is visibly long. | Warm about 0.3–0.8 s; cold about 7–9 s; default timeout 20 s, allowed maximum 120 s. | `pkg_publisher.py:75-101,481-512`; `docs/ROADMAP.md:979-984`; `docs/newtonscript-eval.md:413-425` | Log `tool queued op=...`, `tool dispatched`, and `tool done status=... elapsed_ms=...`. Keep the HTTP result schema unchanged. |
| Tools connection/reconnect | Connect/disconnect is logged, but retry/bind/connect phases are silent because the owner is headless. Under the radio-off rule this channel should exist only during an active send/tool request. | 5 s slow bind retry; connect bounded at 45 s. | `pkg_publisher.py:110-151`; `examples/harness-client/Main.newt:2322-2424`; `docs/chat-ui-and-radio-lifecycle-plan.md:36-64` | Host log only unless a foreground send is active; then the Newton status line may show `Reconnecting...`. No always-on “connected” indicator. |

## Uniform minimal mechanism

### The record

Every long operation reports this logical record:

```text
phase     short stable ASCII token
message   printable human sentence, short enough for the Newton status line
n,total   optional positive integers; both present or both absent
```

Examples:

```text
{phase: received, message: "Server received page 2 of 6", n: 2, total: 6}
{phase: vision,   message: "Server is reading page 2 of 6...", n: 2, total: 6}
{phase: filed,    message: "Answer filed in AI"}
```

That is the entire schema. Correlation IDs, percentages, ETAs, persistence,
metrics export, and arbitrary metadata are deliberately omitted. Each transport
already permits only one relevant in-flight turn/ink stream, so `n/total` is
sufficient correlation. Add an ID only if concurrent sends become real.

### Encodings on existing transports

1. **Framed chat:** keep the existing `STAT` operation and add a fixed payload
   form such as `STAT WORK <phase> [<n>/<total>] <message>`. `READY`, `THINKING`,
   and `ERROR` remain accepted during migration. The client maps `WORK` to
   `SetStatus`; final `TEXT`/`PROMPT` behaviour is unchanged.
2. **Ink HTTP/1.0:** once `/ink` has validated and accepted a request, send the
   response headers and flush close-delimited ASCII body lines:

   ```text
   STATUS received 2/6 Server received page 2 of 6
   STATUS rendered 2/6 Rendered page 2 of 6
   STATUS vision 2/6 Server is reading page 2 of 6...
   INKP 02 06
   ```

   The final part ends with `INK <answer>` instead of `INKP`. `HandleInkLine`
   handles `STATUS` with `SetStatus` and keeps its existing `INKP`/`INK` logic.
   This is legal HTTP/1.0 connection-close framing and uses the same endpoint
   already waiting asynchronously (`examples/harness-client/Main.newt:2133-2146`). It requires no
   `/tools` poll and therefore still works after radio-off-until-send lands.

   Committing an accepted response before model completion means processing
   failures must end with a fixed body line such as `INKERR <message>` rather
   than changing a later HTTP status to 502. Validation failures still return
   ordinary 4xx before streaming starts. This trade is explicit and must be
   pinned by publisher/client tests in the implementation round.
3. **Host logs:** one line per boundary, using the existing logger/`print`
   paths, for example:

   ```text
   status phase=vision n=2 total=6 message="Server is reading page 2 of 6..."
   status phase=vision_done n=2 total=6 elapsed_ms=9184
   ```

   Use the process's existing timestamp. Do not create a logging dependency or
   structured-log service.
4. **Emulator/tools CLI:** print the same human message at existing command
   boundaries. There is no need to put the schema on the emulator HTTP API.

### Where status appears

| Surface | Put here | Do not put here |
|---|---|---|
| Newton status line | Radio/connect/send/received/render/vision/disconnect; latest event replaces the prior one. | Per-stroke counters during sending, percentages, raw error objects, host argv. |
| Host/server log | Every boundary in the inventory, counts, elapsed milliseconds, and errors. | Prompt or note contents beyond existing deliberate diagnostics; repeated heartbeat spam. |
| Chat transcript | Final answer, final error, and durable truncation/thinning notices only. | Transient `Connecting`, `Rendering`, or `page n/total` rows; they would bury the conversation. |
| Notes-menu progress view | Latest transient event and final `Answer filed in AI`; then close. | A second permanent note for every intermediate phase. |

## Phased implementation plan

The ordering is by file ownership and merge risk, not by conceptual purity.
`Main.newt` work must not race the radio/battery or chat-UI rounds.

| Round / branch | Inventory covered | Why this order | Acceptance evidence |
|---|---|---|---|
| **P0 — host logs**, future `release/progress-host`, based after the current `server.py` / `pkg_publisher.py` owners merge | Chat receipt/model/reply; ink receipt/render/vision/assembly; `/note`; tools queued/dispatched/done | Independent of Newton wire/UI and immediately useful to operators. Smallest safe merge. | Unit tests capture one ordered line per boundary; one real or fake round shows elapsed time and `n/total`. |
| **P1 — radio lifecycle**, existing `release/radio-battery` | Radio-up, connect, disconnect, radio-off; tools poll active only during a send/tool request | This branch already owns the connection lifetime. Progress must not accidentally preserve the EF6 always-on poll that the battery round is deleting. | Source tests pin no install-time `ToolStart`; emulator evidence shows status during connect and no tools socket after idle teardown. |
| **P2 — first user-visible ink slice**, future `release/progress-ink`, based on merged P0 + P1 and after the current ink worker | Per-part send, received, render, vision, final reply; streamed `STATUS`/`INKERR` response | Highest-value path and the exact 1–2 minute hardware complaint. It touches both `Main.newt` and `pkg_publisher.py`, so it follows their current owners rather than merging around them. | Fake publisher deterministically emits all phases; real-image emulator round shows `Sending page 1/N` then `Server is reading page 1/N`; multipart order and existing final filing remain correct. Hardware remains human-gated. |
| **P3 — chat detail**, fold into the planned chat-UI round after P1/P2 | Chat send ACK boundary, model phase, reply assembly | Existing `Thinking` is already adequate for ~6 s; lower value than ink. Folding avoids moving/re-wiring the status line twice. | Existing framed protocol tests plus one emulator turn; legacy `READY`/`THINKING` still work. |
| **P4 — Notes headless progress view** — source-complete in EF18 | Notes-menu route and `Answer filed in AI` | The persistent agent builds a root-level `protoFloatNGo` from the route, updates its static text through the existing `SetStatus`, and closes it after completion; no second channel or application launch (`examples/harness-client/Main.newt:149-179,208-258,306-359`). | Source assertions and clean `tntk` compile pass. Still human-gated: invoke from Notes with Egg Freckles closed, confirm Notes stays interactive, progress updates, one AI note is filed, and the view closes. |
| **P5 — emulator/tools messages**, existing `release/emulator-nseval` where applicable, otherwise a tiny tools round | Queued install/open, OCR attempt, `ns_eval` wait, `/tools` lifecycle logs | Developer-facing and independent; serialize with the worker already changing the emulator/ns-eval harness. | CLI transcript contains a line before each wait and no polling spam; existing completion checks still decide success. |

### Recommended first slice

Land **P0 host logs first**, because it is independent and gives immediate
background visibility without touching a device. The first release that changes
the human experience should then be **P2**, limited to:

- `Sending page n/total...` remains until the body is accepted;
- `Server is reading page n/total...` arrives on that part's existing HTTP/1.0
  response;
- the host logs received/rendered/vision start/vision done/reply assembled; and
- the final `INK`/filing path remains exactly one answer.

Do not add percentages, ETA math, a job endpoint, a status database, a second
long poll, or concurrent vision calls in this slice. Six honest page milestones
solve the reported “it failed” experience; performance work is a separate
release (`docs/ef13-memory-diagnosis.md:238-242`).
