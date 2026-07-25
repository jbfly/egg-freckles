# Harness Client networking port

The client keeps its `|HarnessClient:jbfly|` identity and existing status-check UI. Its networking path now follows the runtime-proven Round 11–14 loader patterns.

| Lesson | Old code | New code | Error prevented |
|---|---|---|---|
| Endpoint frame comes first | The broken loader ancestor passed options first; the client source already showed the corrected order but still used the surrounding old scaffolding. | Retain `Instantiate(self.endpoint, options)` while porting the proven option frames and diagnostics around it. | `-48400` / `kNSErrNotAFrame` (“Expected a frame”). |
| NIE progress is not failure | Any `linkStatus` other than `'connected` called `Failed`, including normal `'initializing` and `'connecting` notifications. | Return without error for every non-error state until `linkStatus = 'connected`. | `Failed` → `Stop` → `InetReleaseLink` during connection, which raised `-48803` in `RemoveLinkClient`. |
| Duplicate notifications cannot reconnect | Every connected notification created another endpoint and TCP connection. | `if self.endpoint then return nil;` is the first statement in `Grabbed`. | Two simultaneous TCP connections from one tap and late-notification cleanup failures. |
| Synchronous connect continues directly | Code patterns expected an asynchronous completion after `connect(..., {async: nil})`. | Call `ReceiveStatus()` immediately after synchronous `connect` returns. | A connection stuck at “Connecting...” with no HTTP request sent. |
| Input uses the endpoint input-spec contract | `Input({async: nil, ...})` expected returned chunks and passed arguments to `Input`; the binary target was not wrapped in a target frame. | `SetInputSpec` uses `target: {data: self.inputTarget, offset: 0}`; `Input()` takes zero arguments; `InputScript` is `func(endpoint, data, terminator, options)`. | `-54000`, missing input script, invalid binary target handling, and treating the terminator as a result code. |
| Exceptions are captured where thrown | Only `evt.ex.comm` was caught, then cleanup ran through `Failed` before preserving the full exception. | Broad `evt.ex` handlers immediately capture `CurrentException()` and display the active call plus `name`, NIE error number, `data`, and `message`. | The original endpoint or receive failure being hidden by a later cleanup exception. |

The `/status` source server emits a fixed 125-byte HTTP/1.0 response (`runtime/raw_pkg_server.py` and `pkg_publisher.STATUS_BODY`), so the client uses the loader’s proven byte-count input termination without adding a second-stage HTTP parser.
