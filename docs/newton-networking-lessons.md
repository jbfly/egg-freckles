# Newton networking lessons — what driving NIE/ethernet actually taught us

Distilled from the 2026-07 networking arc (`559af01`..`76aa593`) so a future
agent does not re-derive it the hard way. Each claim carries evidence; where two
sources disagree, both are cited. Read time: ~5 minutes.

Scope: PCMCIA ethernet via NIE (Newton Internet Enabler), `protoBasicEndpoint`
TCP, the ZC34 bootstrap loader, HTTP package delivery, and the persistent
Newton-initiated long-poll transport. Real hardware (MessagePad) and the
Einstein emulator, with explicit notes where only one was proved.

---

## 1. What we now know is true

Each item is verified, not guessed.

### 1.1 The `protoBasicEndpoint` TCP call shape is settled

`Instantiate(options, endpointFrame)`, then lowercase `connect(options,
requestSpec)`, then lowercase `output(data, nil, outputSpec)` — **three
arguments on `output`**, not two. The two-argument form leaves the output-spec
slot absent and produced no payload on the wire.

- Evidence: `docs/newton-dev-notes.md:79,419` calls this the "PT100-compatible
  call pattern" and ascribes it to a working EnRoute source image
  (`Output: func(data, opts, outSpec)`). The broken two-arg form is documented
  at `docs/newton-dev-notes.md:79`.
- Live source: `examples/harness-loader/Main.newt` `Output(binary, nil,
  {async: nil, reqTimeout: 10000, ...})`; `examples/harness-tools/Main.newt:95`
  `self.endpoint:Output("POLL\r\n", nil, {form: 'string, async: true, ...})`.

### 1.2 Synchronous `connect` continues directly; do not wait for a callback

After `connect(..., {async: nil})` returns, call `Connected(nil, nil)` (or
`ReceiveStatus()`) immediately. Code that armed an async completion callback on
a synchronous connect sat at "Connecting..." and never sent an HTTP request.

- Evidence: `docs/client-network-port.md` ("Synchronous connect continues
  directly ... Call `ReceiveStatus()` immediately after synchronous `connect`
  returns").
- Reproduced in the loader: `docs/newton-dev-notes.md:535` ("r12a removed the
  unreachable synchronous-connect completion callback and called
  `Connected(nil, nil)` after `connect` returned").

### 1.3 Receive uses `SetInputSpec` and never calls synchronous `Input()`

`Input()` takes zero arguments and is for synchronous blocking reads; an
endpoint armed with a binary `target: {data: VBO, offset: N}` frame receives
into that VBO via `InputScript`. The async callback shape is:

```newtonscript
SetInputSpec({ _parent: self, form: 'string | 'binary,
               termination: {...}, discardAfter: N,
               target: {data: VBO, offset: N},   // 'binary only
               InputScript: func(endpoint, data, terminator, options) ... })
```

`InputScript` **must re-arm `SetInputSpec` before returning**; re-arming outside
the callback caused connection churn.

- Evidence: `docs/newtonscript-eval.md:290-310` (re-arming from inside the
  input callback, as the Newton endpoint guide permits, removed churn);
  `examples/harness-loader/Main.newt:200-244` (header as `'string` with
  `endSequence`, body as `'binary` with `target`); `examples/harness-tools/Main.newt:107-119`.

### 1.4 Error-code corrections (most expensive knowledge we own)

These are the corrections where the on-screen error code misled us. Verified
against `refs/NewtonProgrammerRef20.txt`.

| Code | We initially read it as | Verified meaning | Where the correction landed |
|---|---|---|---|
| `-48803` | "link teardown error" | **"Wrong number of arguments"** — the system raises it *when it cannot call a callback at all* | `refs/NewtonProgrammerRef20.txt:74810-74812` ("–48803 / Wrong number of arguments"); also `:57308-57313` ("error … usually results in error –48803 … when a callback can't be called"). Corrected in commit `559af01` body: "–48803 is 'wrong number of arguments' (NewtonProgrammerRef20.txt:74810), not a link-teardown error." |
| `-36003` | (none — this is the loader completion failure) | **"Cancel is in progress"** — a double cancel; usually ignorable | `refs/NewtonProgrammerRef20.txt:74083-74085` ("–36003 / Cancel is in progress"); `:57235-57238` ("If the Cancel method throws an exception with error -36003, that means a cancel operation is already in progress … you can probably ignore it"). Loader still fails completion with `-36003` per `559af01` body: "still fails at completion with -36003 (cancel in progress) before reporting install queued." |
| `-48807` | | **Undefined variable** | `refs/NewtonProgrammerRef20.txt:74821-74824` |
| `-48808` | (compile failure) | **Undefined global function** — `Compile(string)` is not callable from an installed application on this ROM | `refs/NewtonProgrammerRef20.txt:74825-74828`; reproduced `docs/newtonscript-eval.md:157-167` (`2+2` returned `-48808`, not `4`). |
| `-48809` | | **Undefined method** | `refs/NewtonProgrammerRef20.txt:74829-74832` |

### 1.5 The on-screen `-48803` from `RemoveLinkClient` was *our* fault, not NIE's

For two rounds (R9–R13A) the loader finished downloading the package but was
overlayed by `RemoveLinkClient` / `-48803` in `inetManagerFSM`. We first treated
it as an NIE teardown defect. **It was a `Grabbed` handler bug:** the `Grabbed`
callback fired for normal NIE progress states (`'initializing`, `'connecting`),
the code routed them to `Failed`, `Failed` called `Stop("Failed")` and then
`InetReleaseLink`, and *that overlay path* raised `-48803`.

The fix: ignore every non-error `Grabbed` state until `linkStatus = 'connected`.
R14G then reported "Harness Client install queued" with no overlay.

- Evidence: `docs/newton-dev-notes.md:573-593` ("Round 14: `Grabbed` progress
  handling removed `-48803`" … "r14b exposed the earlier normal state `Link:
  initializing` … `Grabbed` was incorrectly sending ordinary NIE progress
  notifications to `Failed`"). The corrected `Grabbed` guard is at
  `examples/harness-loader/Main.newt:87-93` and `examples/harness-tools/Main.newt:40-44`.
- Nuance: `-48803` *does* mean "wrong number of arguments / callback can't be
  called" (§1.4). The teardown overlay surfaces it because a half-stopped link
  can't call a callback. So both readings are right: the error code's meaning is
  "callback cannot be called," and in *this* system the trigger was our own
  premature `Stop()`. Commit `559af01` body makes the same point: "defer `Stop()`
  out of the callback so `InetReleaseLink` cannot throw -48803 from inside
  `InputScript`."

### 1.6 Stock NewtonOS TCP payload does NOT reach the host on stock Einstein

Configured stock PT100 (Telnet, numeric host, custom port) completed the TCP
handshake, showed a connected terminal, and accepted typed `xy`, but the host
listener received `TOTAL b''`. This exonerates our Loader NewtonScript: a stock
NewtonOS app reproduces the missing outbound payload, so the defect was in the
Einstein/NIE networking path, not our code.

- Evidence: `docs/newton-dev-notes.md:326` ("Stock PT100 TCP payload **DOES
  NOT** reach the host. Because a stock NewtonOS application reproduces the
  Loader's symptom, the defect is in the Einstein/NIE networking path");
  `docs/einstein-automation.md:65` ("a 77-byte native frame … `Looking up
  machine address...` … did not establish a known-good TCP data-bearing
  control").

### 1.7 The real outbound fix was an async output spec, not an Einstein patch

The TCPDIAG patch series (`einstein-tcp-*`) was built to trace the missing
payload. The decisive finding (`newton-dev-notes.md:406`): stock PT100 reaches
`TNewScriptEndpointClient::DoOutput` at ROM `0x00134fdc`, then `OutputRaw`,
`TEndpoint::nSnd(raw)`, `PConnectionEnd::PutBytesStart`, and a **one-byte TCP
frame** that the host *does* send (`host-send requested=1 sent=1 errno=0`). The
patch `einstein-tcp-send-after-ack.patch` lets Newton ACK the SYN and send
payload in the same packet (fall through `kStateConnectionWaitACK` into
`kStateConnected`). The notes record it as "proven insufficient before this
session" (`newton-dev-notes.md:53`) — the actual payload delivery was unlocked
by switching the Newton side to **async output specs with a `completionScript`**
(`async: true`, `form: 'string`), matching EnRoute's working code.

- Evidence: `docs/newton-dev-notes.md:79,91` ("EnRoute's working code
  predominantly uses an async output spec with a completion callback rather
  than a synchronous spec"); production shape at
  `examples/harness-tools/Main.newt:95-100,140-141`.
- The `einstein-nie-rom-trace.patch` records the ROM addresses of the NIE
  endpoint send chain (`TNewScriptEndpointClient::DoOutput` @ `0x00134fdc`,
  `OutputRaw` @ `0x0013558C`, `TEndpoint::nSnd(raw)` @ `0x00382BBC`,
  `PConnectionEnd::PutBytesStart` @ `0x00383854`) for any future binary
  instrumentation above the Einstein host-network bridge.

### 1.8 A persistent Newton-initiated long poll beats per-call NIE acquisition

The production transport is now one endpoint: Newton sends `POLL\r\n`, arms
async input, replies from `InputScript`, re-arms before returning, and the host
holds the poll until a named operation arrives. Steady sequential latency
**~0.81 s median**, first exchange **0.11 s**, vs the old poll-plus-POST path's
**5.8–11.5 s** (dominated by repeated NIE link acquisition).

- Evidence: `docs/newtonscript-eval.md:335-360` (R9 production benchmark, 10
  `ping` calls on one TCP source port, min 0.110 s / median 0.814 s / max
  0.815 s); `examples/harness-tools/Main.newt:92-100` (the `Poll`/`ArmInput`
  cycle). Old baseline at `docs/newtonscript-eval.md:241-247` (5.8–11.5 s).

### 1.9 Async endpoint I/O does not block the UI event loop

While the R9/R10D long poll was outstanding, the device still accepted
`GetRoot().paperroll:Open()`, `front_app` returned the frontmost app in
**0.034–0.126 s**, and `get_note(5)` returned real stored text in **0.77–0.82 s**.
So the transport is non-blocking from the user's perspective.

- Evidence: `docs/newtonscript-eval.md:322-331` (L3 async), `:384-394` (R10D).

### 1.10 One input form throughout an HTTP exchange

Do not read HTTP headers as `'string` and then switch the body to `'binary`.
Apple's `refs/qa/inptspec.htm` documents that such a non-binary→binary/frame
transition **discards already-buffered bytes** unless the sender waits for a
receiver handshake — which a plain HTTP server can't provide. The loader uses
`'string` with `endSequence:"\r\n\r\n"` for headers and a *separate* `'binary`
`SetInputSpec` for the body (the `endSequence` leaves the body queued, and the
binary spec receives directly into the package VBO via `target:{data,offset}`).

- Evidence: `docs/client-network-port.md` ("deliberately does **not** read
  headers as `'string` and then switch the body to `'binary`"); live shape
  `examples/harness-loader/Main.newt:200-244` with the `ponytail:` comment at
  `:226`.

### 1.11 `SuckPackageFromBinary` must run out of the callback stack

Package install can alter application state, so it is deferred:

```newtonscript
AddDelayedCall(func(theBinary)
    GetDefaultStore():SuckPackageFromBinary(theBinary, nil), [binary], 5000);
```

Keep the binary referenced until the delayed call runs. `ClearVBOCache` before
install.

- Evidence: `docs/newton-client-notes.md` ("SuckPackageFromBinary" section);
  `examples/harness-loader/Main.newt:179-181`.

### 1.12 Zero-click install/launch is real, via a control socket

Einstein's FLTK build has no host entry point for unattended install/launch
(`docs/einstein-automation.md` bottom line). The fix was a mode-`0600` Unix
socket on the FLTK thread exposing `TPlatformManager::InstallPackage` and
`EvalNewtonScript`, reached by `emulator-control` `POST /install` and
`POST /newtonscript` (`docs/newton-dev-notes.md:600-630`). One `curl` per
endpoint, both reply `queued`; no file picker, OCR, GUI click, or launch tap.

---

## 2. Footguns and their fixes

The traps that cost real time.

| Footgun | Cost | Fix | Evidence |
|---|---|---|---|
| **The 18081 port-swap** | Running the NS Basic bootstrap (bare `G` byte, wants 15000 padded bytes) and the Loader HTTP GET (also starts with `G`) on the same port required manual swapping of the listener; "already cost two hardware test cycles." | `runtime/dual_send.py` sniffs the first bytes and dispatches: `GET ` → HTTP, else → 15000-byte padded bootstrap. One listener, both protocols. | `runtime/dual_send.py:4-9` (docstring), `:70` (`if text.startswith("GET ")`) |
| **Treating NIE progress as failure** | `'initializing` and `'connecting` `linkStatus` notifications were routed to `Failed` → `Stop` → `InetReleaseLink`, raising the `-48803` overlay for two+ rounds. | Return without error for every non-error state until `linkStatus = 'connected`. | `docs/newton-dev-notes.md:577-593`; `docs/client-network-port.md` ("NIE progress is not failure") |
| **Duplicate `Grabbed` notifications creating a second endpoint** | Each connected notification spawned another endpoint/TCP connection from one tap. | First statement in `Grabbed`: `if self.endpoint then return nil;` | `docs/client-network-port.md` ("Duplicate notifications cannot reconnect") |
| **Idle link is a race, not a threshold** | Four idle trials at ~92–100 s disagreed; we kept trying to tune the gap. Gap length does not predict cost: 60 s cost 7.1 s, 300 s cost 0.19 s. What predicts cost is **who notices the dead link first**. | Don't tune the gap. If the ~7 s worst case matters, run a host-side keepalive that touches the link more often than it dies, so the 4 s watchdog always wins the race. Worst case is no worse than the 5.8–11.5 s baseline this replaced. | `docs/newtonscript-eval.md:398-413`; `runtime/evidence/idle-sweep.txt`; commit `6442573` |
| **Watchdog period below heartbeat cadence** | A faster-than-3 s watchdog forced false reconnects and a 9.0 s warm call. | Watchdog period must stay **above the 3 s host-heartbeat cadence** (`pkg_publisher.py:70`); R10D uses 4 s. | `docs/newtonscript-eval.md:366-375` |
| **Zombie package tears down without `Stop()`** | Closing the app's view left the source port alive (zombie) beside a fresh connection. | Add `ViewQuitScript` that calls `Stop()` (unbind, dispose, release NIE). | `docs/newtonscript-eval.md:377-383`; `examples/harness-tools/Main.newt:26-30` |
| **Startup `Bind`/`Connect`/`Output` can hold the app task for the full 45 s connect timeout** | Real-hardware bring-up exposed synchronous endpoint calls blocking the UI. | Use endpoint callback specs with `async: true` for `Bind`, `Connect`, and both `Output` operations. Input path stays `SetInputSpec`-only. | `docs/newtonscript-eval.md:415-435` (R10I) |
| **Missing `form: 'string` on the output spec** | Einstein established TCP but emitted no payload. | Every output spec includes `form: 'string`. | `docs/newtonscript-eval.md:431-435` |
| **Treating replacement of the prior input spec as a communication error** | Caused connection churn. | Remove that error path; `InputScript` re-arming inline before return is the intended use. | `docs/newtonscript-eval.md:435` |
| **Hand-written header byte loop** | `SubStr(text, Length(text)-4, 4)` threw on the first byte; a stale armed spec then ate body chunks as header text until the 4096 guard tripped. | Use Newton's native `termination: {endSequence: "\r\n\r\n"}`. | commit `559af01` body ("Header scan: replace the hand-written byte loop…") |
| **Reading the stale `.text` slot for the filename** | Every request went out as the hardcoded `inetenbl.pkg` default regardless of typing. | Read the live edit with `GetRichString()` (and default the field to `harness-tools.pkg`). | commit `559af01` body ("Filename field …") |
| **Invented globals** | `SplitString`, `ClearVBOCache` were assumed to exist; neither does in NewtonOS 2.1. | Audited all 26 globals in the file against the Reference, Guide and NIE docs. | commit `559af01` body ("Remove invented globals…") |
| **Reading the callback `data` argument as the VBO** | The receive callback's data argument is not the binary; the VBO is `endpoint._parent.inputTarget`. | Read the configured VBO via `endpoint._parent.inputTarget`, use `async:nil` + explicit `Input()`. | commit `559af01` body ("Receive callbacks…") |
| **`Compile(string)` assumed callable** | Resident package returned `-48808` (undefined global function) for `2+2`. | NewtonOS 2.1 documents `Compile(string)` but this ROM/application context does not resolve it. Fixed named operations work; arbitrary received source does not compile. | `docs/newtonscript-eval.md:157-178` |
| **Log-scraping for an eval result** | A working evaluator emits neither result nor `Exception` to process output, even after forced flush. | Use a distinct result channel (the R6+ `POST /tools` protocol, or the ns_eval Print()-to-file channel). | `docs/newtonscript-eval.md:1-58` |
| **tntk top-level constant referenced in a function body** | `kCap := 6144; F: func() kCap` segfaults the compiler with no diagnostic. | Put the constant in a view slot (`cap: kCap` then `self.cap`). | `docs/newton-dev-notes.md` "Five NewtonScript/tntk traps" section |
| **Case-insensitive symbol collision** | A slot `transcriptTail` made `:TranscriptTail()` call a number (`-48200`). | Slots are `capBytes` / `tailBytes`. | same |
| **tntk rewrites package version 1** | Newton rejects any same-name reinstall as "already installed"; the identity string isn't the real replace trap — `tntk` hardcodes version 1. | Use uniquely-named builds per round (`scripts/newton-round.sh`); `SafeRemovePackage` did not clear it. | `~/newton-dev/tntk/package.cpp:161`, per `newton-dev-notes.md` |
| **NIE link wedge** | Open apps holding NIE links accumulate until every connect returns `-16013`. | Restart the emulator container to clear. | `docs/newton-dev-notes.md` operational note |

---

## 3. What is still unverified

Do not treat these as fact.

- **The historical ZC34 `-36003` hardware failure remains a hardware gate.**
  The reference meaning is verified as "Cancel is in progress" (`:57235-57238`,
  `:74083-74085`). ZC37 removes the mismatched synchronous-output completion
  callback by using the proven `async: true`, `form: 'string` output shape and
  reports success only after `SuckPackageFromBinary` returns and `GetPkgRef`
  finds the installed identity. The ZC37 package builds and its unattended
  Einstein proof is scripted in `runtime/test_wifi_install.py`; do not call the
  teardown fixed on physical hardware until that runbook gate passes.
- **Real-hardware parity for the long-poll transport.** The R9/R10D latency
  numbers are Einstein/emulator-derived. `docs/newtonscript-eval.md` notes R10I
  "real hardware exposed the remaining synchronous endpoint calls" — i.e. the
  async-output fixes were made *for* hardware, but the published latency table
  is emulator. We have not published a hardware-side latency table for the
  persistent path.
- **Whether `einstein-tcp-send-after-ack.patch` is necessary on the current
  path.** It is "proven insufficient" on its own (`newton-dev-notes.md:53`) and
  the real unlock was the async output spec. Whether the patch is now redundant
  (payload flows without it) or still needed for the SYN+payload same-packet
  case has not been re-tested in isolation.
- **The exact source of the silent idle link death.** We know the link dies
  silently while idle and the 4 s watchdog reacquires it; we have **not**
  traced which NIE/Einstein side drops the TCP session or why. The idle-sweep
  data (`runtime/evidence/idle-sweep.txt`) shows the *port changing* as a
  symptom, not the cause.
- **`Compile(string)` unavailability is a ROM/application-context finding, not
  necessarily a universal NewtonOS 2.1 fact.** The Reference documents it; we
  could not call it from an installed application on this Einstein/ROM. Whether
  a different application context (or a recovered NIE source build) exposes it
  is open.
- **ns_eval result channel robustness.** `c007655` records that "Einstein's
  existing `Print()` primitive writes a disposable result file that
  `runtime/ns_eval.py` polls. The TCP callback path was tried first and dropped
  after live payload timeouts." Whether the Print()-file polling path is robust
  under concurrent operations or large results is not characterized here.
- **The `-48809` from the `NewtonScriptEvalReporter:Send("result","manual")`
  attempt** (`newtonscript-eval.md:128-133`) is recorded as an observed failure
  of a plain evaluated frame reusing the app's async NIE send path. We did not
  determine whether a differently-structured reporter frame could avoid it.

---

## 4. What this means for the harness

The goal is "Claude Code for the Apple Newton" — an agentic harness with a
Newton-side client. Which of these lessons change the plan?

### 4.1 `docs/phase3-client-plan.md` §3 assumes "one connection per submitted
turn unless persistent connections prove simpler." **Persistent proved
simpler and far faster.** The long poll (§1.8) gives ~0.8 s steady latency on
one reused endpoint and does not block the UI (§1.9). The plan's per-turn NIE
acquisition cost is the 5.8–11.5 s baseline the persistent path replaced. The
client transport should adopt the R9 long-poll shape, not the "one connection
per turn" default.

### 4.2 `docs/phase3-client-plan.md` §3 frames bidirectional framing as the
"central Phase 3 risk" and proposes port 6801 raw TCP with a `~NEWTONCLI 1`
native-mode handshake. The networking arc *already resolved* the harder
question — Newton can hold one persistent socket and exchange newline-delimited
frames via async `SetInputSpec` + `Output(form:'string, async:true)`. The
remaining risk is the model100 framing/retry *logic*, not whether Newton can
sustain a bidirectional socket. Don't re-litigate persistence; reuse
`examples/harness-tools/Main.newt` as the transport skeleton.

### 4.3 The same-socket long poll (§1.8) needs a **host-side keepalive** (§2
footgun). The plan's stop-and-wait framing assumes a live link; the idle race
(§1.8/§2) means the link dies silently and the first turn after a gap can cost
~7 s. Build the keepalive into `server.py`/`pkg_publisher.py` rather than
tuning the Newton-side watchdog.

### 4.4 All Newton-side endpoint calls must be **async with completion
callbacks** (`async: true`), including `Bind`, `Connect`, and `Output` (§1.7,
§2 footgun). The plan's "endpoint call shape is already proven" (§1) is true for
*emulator* bring-up but real hardware blocks the app task for the full 45 s
connect timeout on synchronous calls. Port the R10I async lifecycle wholesale.

### 4.5 Every output spec needs `form: 'string` (§2 footgun). Without it
Einstein connects but emits no payload — a silent failure that looks exactly
like a dead link. Bake this into any new client from the start; do not
"discover" it again.

### 4.6 Treat NIE progress notifications as non-failures (§1.5/§2). Any
`linkStatus ≠ 'connected` that is not an explicit error must *return*, not
call `Failed`/`Stop`. The single most expensive debugging pattern in this arc
was misreading normal NIE progress as a failure and then spending rounds
chasing the `-48803` overlay *that our own `Stop()` caused*.

### 4.7 Arbitrary NewtonScript runtime compilation is **not available** on
this ROM context (§1.4, §1.12). The harness cannot rely on `Compile(string)`-
style "send arbitrary code to the device." Use the **fixed named-operation**
protocol (`POST /tools`, `op`/`args`) as the agent's tool surface, adding new
operations as package code. This is a hard constraint on the harness
architecture: the Newton side is a fixed-op tool server, not a code-eval
target.

### 4.8 The result channel is a distinct problem from the transport (§1.12,
§2 footgun). The ns_eval Print()-to-file path is the current eval-result
channel; the TCP callback path was tried and dropped (timeout). The harness
client should assume fixed-op request/response over the long poll, with any
async result delivered through the same `InputScript` re-arm cycle — not
through log-scraping or a synchronous `Input()`.

### 4.9 Use `dual_send.py` on 18081 from day one (§2 footgun). The
NS-Basic-bootstrap vs HTTP-Loader port collision cost two hardware cycles
before the sniff-and-branch server removed it. Any new package-delivery flow
must speak through `dual_send.py` (or its successor), not a hand-swapped
listener.

### 4.10 Assume Einstein's `InstallNewPackages` scanner and drag-and-drop are
*not* host entry points (§1.12). Zero-click install needs the control socket;
the FLTK build provides no other. Any "watch a directory" or "drop a package"
idea is already disproven in `docs/einstein-automation.md`.