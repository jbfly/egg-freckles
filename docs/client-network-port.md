# Harness Client networking port

The client keeps its `|HarnessClient:jbfly|` identity and existing status-check UI. Its networking path now follows the runtime-proven Round 11–14 loader patterns.

| Lesson | Old code | New code | Error prevented |
|---|---|---|---|
| Endpoint frame comes first | The broken loader ancestor passed options first; the client source already showed the corrected order but still used the surrounding old scaffolding. | Retain `Instantiate(self.endpoint, options)` while porting the proven option frames and diagnostics around it. | `-48400` / `kNSErrNotAFrame` (“Expected a frame”). |
| NIE progress is not failure | Any `linkStatus` other than `'connected` called `Failed`, including normal `'initializing` and `'connecting` notifications. | Return without error for every non-error state until `linkStatus = 'connected`. | `Failed` → `Stop` → `InetReleaseLink` during connection, which raised `-48803` in `RemoveLinkClient`. |
| Duplicate notifications cannot reconnect | Every connected notification created another endpoint and TCP connection. | `if self.endpoint then return nil;` is the first statement in `Grabbed`. | Two simultaneous TCP connections from one tap and late-notification cleanup failures. |
| Synchronous connect continues directly | Code patterns expected an asynchronous completion after `connect(..., {async: nil})`. | Call `ReceiveStatus()` immediately after synchronous `connect` returns. | A connection stuck at “Connecting...” with no HTTP request sent. |
| Input uses the endpoint input-spec contract | `Input({async: nil, ...})` expected returned chunks and passed arguments to `Input`; the binary target was not wrapped in a target frame. | `Input()` takes zero arguments; `InputScript` is `func(endpoint, data, terminator, options)`. Binary receives require `target: {data: VBO, offset: 0}`; the status receive now stays in `'string` form and needs no target. | `-54000`, missing input script, invalid binary target handling, and treating the terminator as a result code. |
| Exceptions are captured where thrown | Only `evt.ex.comm` was caught, then cleanup ran through `Failed` before preserving the full exception. | Broad `evt.ex` handlers immediately capture `CurrentException()` and display the active call plus `name`, NIE error number, `data`, and `message`. | The original endpoint or receive failure being hidden by a later cleanup exception. |

## Variable-length `/status` receive

The client no longer assumes the current 125-byte HTTP response. It uses one `'string` input form for the entire response, with a 4,096-byte safety ceiling. `InputScript` and `PartialScript` retain the currently buffered string; when the HTTP/1.0 peer closes, `CompletionScript` parses the header/body delimiter and ASCII `Content-Length`, verifies that the full body arrived, and displays up to the existing 80-character UI limit.

This deliberately does **not** read headers as `'string` and then switch the body to `'binary`: Apple's `refs/qa/inptspec.htm` documents that such a non-binary-to-binary/frame transition discards already-buffered bytes unless the sender waits for a receiver handshake. A plain HTTP server cannot provide that handshake, so one input form is used throughout. The 4,096-byte cap is a failure ceiling, not an expected response length; oversized, malformed, and truncated replies produce visible errors instead of waiting for a hardcoded count.

Real emulator evidence used the same receive path under unique test identities:

| Status body | Full HTTP response | Visible result | Evidence |
|---:|---:|---|---|
| 3 bytes (`OK\n`) | 104 bytes | `Online: OK` | `runtime/evidence/r17g-short-3.png`, `r17g-short-3.txt`, `r17g-short-3-server.log` |
| 23 bytes (canonical status) | 125 bytes | `Harness server v1.1 OK` | `runtime/evidence/r18d-default.png`, `r18d-default.txt`, `r18d-default-server.log` |
| 87 bytes | 189 bytes | `Online: Harness variable response...` | `runtime/evidence/r17g-long-87.png`, `r17g-long-87.txt`, `r17g-long-87-server.log` |

`scripts/newton-round.sh examples/harness-client r18d` correctly built, checked the package symbol, zeroed and started capture, installed, launched, and confirmed visible version `1.1-r18d`. Its strict OCR gate was awkward for this first client use: the untagged stable identity required a temporary seed tag, long test titles were clipped, and several lowercase suffixes were misread (`r17a` as `117a`). Tags with OCR-friendly suffixes passed without changing the tool.
