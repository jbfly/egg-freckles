
## Pending integration — status heartbeat and emulator drag

- `runtime/raw_pkg_server.py` now serves `GET /status` as HTTP/1.0 with the canonical `pkg_publisher.STATUS_BODY`: `Harness server v1.1 OK\n`.
- `emulator/control.py` now accepts `POST /drag` with integer `start_x`, `start_y`, `end_x`, `end_y`, optional `duration` seconds (default `0.5`), and optional `steps` (default `20`). It issues mouse-down, interpolated moves, and mouse-up in Newton screen coordinates.
- The control source is copied into the emulator image by `containers/emulator.Dockerfile`, so `/drag` needs an image rebuild and container restart before it is live. The raw server also needs a restart for `/status`. Neither service was restarted or rebuilt while preparing this change.

**`/drag` is live as of 2026-07-31.** On the running `newton-harness_emulator_1`,
`POST /drag` with an empty body returns HTTP 400 (argument validation) while an
unrouted path returns 404, so the route is present in the deployed image. The
`/status` half was not re-checked; `10.42.0.1` is not always assigned.

Run these checks after the respective integration restarts:

```sh
curl --http1.0 -fsS http://10.42.0.1:18081/status | cmp - <(printf 'Harness server v1.1 OK\n')
curl -fsS -X POST http://127.0.0.1:18080/drag -H 'Content-Type: application/json' -d '{"start_x":40,"start_y":120,"end_x":280,"end_y":360,"duration":0.5,"steps":20}'
```

## 2026-07-24 — Einstein TCP payload drop investigation (stopped after three failed fixes)

### Bottom line

The HTTP GET is not reaching `TUsermodeNetwork::SendPacket` at all. Einstein completes the host-side TCP connection and Newton completes the emulated SYN/SYN-ACK/ACK handshake, then the Loader visibly reaches `Requesting /harness-client.pkg...`; however, no Newton Ethernet data frame follows. The raw server times out after five seconds with `RAW b''`.

The diagnostic boundary is now precise:

1. NewtonScript's synchronous `protoBasicEndpoint:Connect` returns and `DownloadPackage` calls `endpoint:Output` (the Loader screen changes to `Requesting /harness-client.pkg...`).
2. Einstein's native bridge logs every `EinsteinNetSendBuffer` and `EinsteinNetSendPacket` call.
3. After the handshake ACK, there is no native send call for the GET. Therefore the payload is not being dropped by `TTCPPacketHandler::send`, its state guard, `GetTCPPayloadSize`, or host `::send`; Newton/NIE never hands a data frame to Einstein's NE2000 native primitive.

### Reproduction and evidence

- Fresh flash backup before restart testing: `runtime/backups/internal-before-tcpdiag-rebuild-20260724-060617.flash`, SHA-256 `d566009ec599651275091ac04efb7343ea87a8affe6fbc793c77f92ba861ba3d`.
- Raw package server remained running as `python3 runtime/raw_pkg_server.py` on `10.42.0.1:18081`; it reports `bytes=1328`.
- Baseline diagnostic attempt:
  - SYN: `size=58 iptotal=44 tcphdr=24 payload=0 flags=0x002`.
  - Handshake ACK: `size=54 iptotal=40 tcphdr=20 payload=0 flags=0x010`.
  - No payload packet appears before the server FIN; raw log records `ERROR ... timed out` and `RAW b''`.
- Native-bridge diagnostic attempt:
  - Control packets call `native SendBuffer` followed by `native SendPacket` (58-byte SYN and 54-byte ACK).
  - No `SendBuffer`/`SendPacket` call follows the Loader's `endpoint:Output`.
- Consolidated trace: `runtime/evidence/tcpfix-three-failed-hypotheses-20260724.txt`.
- Screenshots:
  - `runtime/evidence/tcpfix-native-loader-ready.png`
  - `runtime/evidence/tcpfix-isn-after.png` (status remains `Requesting /harness-client.pkg...`).

### Three failed fix hypotheses

1. **Remove the SYN-ACK acknowledgment increment.** Replaced `SetTCPAck(++mNewtonPacketsSeq)` with `SetTCPAck(mNewtonPacketsSeq)`. This was based on an initially mistaken reading that the constructor's `seq + 1` survived into `connect`; in fact, `connect` resets `mNewtonPacketsSeq` to the SYN sequence before incrementing it. Newton immediately sent RST (`flags=0x004`) and reported TCP error 10021. The patch was removed.
2. **Send a duplicate ACK when entering `kStateConnected`.** This tested whether a missing interrupt/window update kept the synchronous endpoint blocked after its handshake ACK. Newton still sent no data frame; the Loader reached `Requesting...`, and the raw server again timed out with an empty request. The patch was removed.
3. **Use a nonzero Einstein initial sequence number.** Set `mEinsteinPacketsSeq = 1` before generating the SYN-ACK, testing whether zero acted as a Newton TCP sentinel. Newton ACKed the new sequence (`ack=2`), but again emitted no data frame and the raw server received `b''`. The patch was removed from the canonical Dockerfile after the test.

### Patch/build state

- `containers/patches/einstein-tcp-newton-payload.patch` retains the TCP state/payload/host-send diagnostics.
- `containers/patches/einstein-tcp-native-diag.patch` logs NE2000 native `SendBuffer`, `SendCBufferList`, and `SendPacket` calls.
- `containers/patches/einstein-tcp-send-after-ack.patch` remains present but was already proven insufficient before this session.
- The canonical `containers/emulator.Dockerfile` includes those three diagnostic patches and no failed hypothesis patch.
- The currently running container was built with the third test (`mEinsteinPacketsSeq = 1`); it was not restarted again because the procedure requires stopping after three failed fixes. Rebuild/restart from the canonical Dockerfile before continuing.

### Next investigation boundary

Continue below `protoBasicEndpoint:Output` and above the NE2000 driver's `EinsteinNetSendBuffer` call: inspect the Newton NIE endpoint/transport state and the installed Loader's output object/options. Do not spend another cycle changing `TUsermodeNetwork` packet state or payload arithmetic unless a new trace first shows a data-bearing Ethernet frame reaching `EinsteinNetSendPacket`.

## 2026-07-24 — Round 3 Loader endpoint investigation (stopped after three failed hypotheses)

### Bottom line

Round 3 disproved three Loader-side output hypotheses. A stock PT100 session proved that NewtonOS/NIE can emit an outbound frame through Einstein, but that frame was the 77-byte DNS lookup while PT100 displayed `Looking up machine address...`; it did not establish a known-good TCP data-bearing control. Every Loader build still completed TCP SYN/SYN-ACK/ACK and then delivered no payload to Einstein's native bridge. The raw server received `b''` for every connection.

The remaining boundary is narrower but unresolved: the Loader calls the documented three-argument `protoBasicEndpoint:Output`, but NIE still never calls `EinsteinNetSendBuffer` with the request. Stop here because the round's three-hypothesis cap is reached.

### Required reset and control experiment

- Rebuilt the canonical `containers/emulator.Dockerfile` in the background and polled it to completion. `runtime/logs/round3-canonical-build.exit` is `0`; the canonical/running image is `63ee1f3db21b979939bfedc6c0a9fd489ce93a1c302515badab53db3d8e2e364`, with no nonzero-ISN patch.
- The raw package server remained running on `10.42.0.1:18081` and continued to report `serving ... bytes=1328`.
- Tried NewtonOS's stock PT100 client as the cheap control. It emitted a 77-byte native frame while the UI said `Looking up machine address...` (`runtime/evidence/round3-pt100-control-result2.txt`), but no TCP state diagnostic appeared. This is evidence that NIE can reach the NE2000 bridge for DNS/UDP, not evidence that stock outbound TCP payload works. No installed stock client was successfully configured far enough to produce a TCP payload this round.

### Three failed Loader hypotheses

1. **Send the HTTP request as a binary rather than a NewtonScript string.** Built and installed `HarnessLoaderR3:jbfly` using `MakeBinaryFromHex(..., 'binary)`. One button action triggered the Loader's two built-in attempts. Both handshakes completed, both raw-server reads timed out with `RAW b''`, and no data-bearing native frame appeared. Evidence: `runtime/evidence/round3-hypothesis1-result.txt`.
2. **Explicitly flush after synchronous `Output`.** Built and installed `HarnessLoaderR3F:jbfly`, adding `endpoint:FlushOutput()` after the binary request. Fresh pre-install backup: `runtime/backups/internal-before-round3-loader-flush-20260724-071430.flash`, SHA-256 `87258706e3c83690d2b7421385430a4ff4a927569c1083414aa5f8d5238d51b6`. Both built-in attempts again timed out with `RAW b''`; the last Newton native calls were handshake ACKs. Evidence: `runtime/evidence/round3-hypothesis2-result.txt` and `runtime/evidence/round3-hypothesis2-after-fetch.png`.
3. **Correct the `Output` call from two arguments to the documented three arguments.** A known-working EnRoute source image contains `Output: func(data, opts, outSpec)` and sends with `enRoute:Output(v_outStrBuff, nil, outSpec)`. It also defines async output specs with `async: true` and a `completionScript`. The Loader had incorrectly called `Output(data, {async: nil, reqTimeout: 10000})`, leaving the output-spec argument absent. Built and installed `HarnessLoaderR3O:jbfly` with `Output(binary, nil, {async: nil, reqTimeout: 10000})` and removed the disproven flush. Fresh pre-install backup: `runtime/backups/internal-before-round3-outputspec-20260724-072727.flash`, SHA-256 `2c878492b92cbfc046e73d02c549897e0ac79006bf73faf121f37f9e5e4d8161`. Both attempts still timed out with `RAW b''`, with no native payload frame. Evidence: `runtime/evidence/round3-hypothesis3-result.txt` and `runtime/evidence/round3-hypothesis3-after-fetch.png`.

### Build and runtime state

- Current Loader source/package symbol: `HarnessLoaderR3O:jbfly`; source uses the corrected three-argument call at `examples/harness-loader/Main.newt:159-164`.
- Current staged Loader SHA-256: `f8646115a956f430878a750795dced212ae981875a783cd15d3a5201620d5232`.
- Current staged client is 6,456 bytes, SHA-256 `dceacc8130d175c151b2261f0e06873d7e9e63752f035820428e820c125bbee3`. The long-running raw server intentionally stayed untouched as required and still serves the 1,328-byte package it loaded at startup; because no GET arrived, this size difference did not affect any result.
- `HarnessClient:jbfly` was not installed and the acceptance criteria were not met. No client launch screenshot exists.
- Emulator remains running on canonical image `63ee1f3d...`; raw server remains running; no AP/firewall settings changed; no physical Newton was touched; all backups were preserved.

### Next boundary

Do not make another Loader fix without a new round. First obtain a true stock TCP control (for example, configure PT100 with a numeric host and reachable TCP listener, or use Dock/NCX) and prove whether a data-bearing TCP frame reaches `EinsteinNetSendPacket`. If stock TCP works, inspect the endpoint's async output state/callback path and the full `Input`/`SetInputSpec` API shape; EnRoute's working code predominantly uses an async output spec with a completion callback rather than a synchronous spec.

## Upstream prior art

Research performed 2026-07-24 against the Einstein upstream repository, its
GitHub issues and pull requests, and the NewtonTalk MARC archive.

### No post-pin network fix exists upstream

The pinned revision,
[`f5544a039fc3964e18b217ccffa030c6bf1e4044`](https://github.com/pguyot/Einstein/commit/f5544a039fc3964e18b217ccffa030c6bf1e4044),
is still the `HEAD` of `pguyot/Einstein`'s default branch. A comparison of all
current remote branches found no later network implementation: the three
post-pin branch differences in `TUsermodeNetwork.cpp` only change C++ empty
initializers from `{ }` to `{}`. The only GitHub issue or PR created after the
pin is unrelated [PR #220, “Fix Pulseaudio
buffering”](https://github.com/pguyot/Einstein/pull/220).

Therefore there is no later outbound-TCP fix available to cherry-pick from
upstream.

### Earlier upstream network fixes are already in the pinned revision

The relevant upstream history predates the pin and is already ancestral to it:

- [`6029f5320cd2108c899cab41a5a1f7c7224fe1bf`](https://github.com/pguyot/Einstein/commit/6029f5320cd2108c899cab41a5a1f7c7224fe1bf)
  (2010-06-07) says: **“TCP is working OK. Closing a socket from either side
  needs to be implemented.”** This changed `TUsermodeNetwork` and
  `TNativePrimitives`.
- [`dddd9e4ebfe578a799159ecde209d73f3bb700f0`](https://github.com/pguyot/Einstein/commit/dddd9e4ebfe578a799159ecde209d73f3bb700f0)
  (2010-06-08) says: **“Courier is somewhat working now, but incredibly slow.
  NewtsCape is also slower than expected.”**
- [`dd19326f0f2f3f737fb5ad75bb28824a34bf2dba`](https://github.com/pguyot/Einstein/commit/dd19326f0f2f3f737fb5ad75bb28824a34bf2dba)
  (2010-06-19) describes **“the first version of the User Mode Ethernet
  connection that works ok.”**
- [`1d1437602f6b4feb7878dcf53728b3f7e1e75787`](https://github.com/pguyot/Einstein/commit/1d1437602f6b4feb7878dcf53728b3f7e1e75787)
  (2010-06-21) says: **“We can load web pages that are larger than 1000
  bytes! Actually, we can load pretty large web pages now. I managed to load a
  gif.”** Its remaining reported problem was premature peer close, not failure
  to emit the first outbound request.
- [Issue #58, “First byte is eaten in user mode
  networking”](https://github.com/pguyot/Einstein/issues/58), concerned the
  first byte of data sent *from the host to the Newton* immediately after
  connection establishment. It explicitly reported that the Newton did echo
  subsequent data, so it was not the present “no Newton data frame” symptom.
  The issue was closed by
  [`c3a030ec4ec04179923e677d5c09296f4a961ac6`](https://github.com/pguyot/Einstein/commit/c3a030ec4ec04179923e677d5c09296f4a961ac6);
  the corresponding master-line commit is
  [`9956874cba0a2fe3c3a830234cc7ed20cec13d09`](https://github.com/pguyot/Einstein/commit/9956874cba0a2fe3c3a830234cc7ed20cec13d09),
  **“Fix network code, including #58.”** Besides correcting sequence tracking,
  that change still sends Newton payload with
  `write(mSocket, packet.GetTCPPayloadStart(), packet.GetTCPPayloadSize())`.
- [`963556382aecce9a2ded6077d1c028732df5e1d4`](https://github.com/pguyot/Einstein/commit/963556382aecce9a2ded6077d1c028732df5e1d4)
  (2022-01-07), **“Much improved UserMode network emulation,”** fixed sequence
  and acknowledgment handling and throttled packets sent toward NewtonOS.
  [Issue #119](https://github.com/pguyot/Einstein/issues/119) tracks remaining
  user-mode-network work such as timeouts and disconnect handling; neither the
  issue nor its comments mention missing outbound buffer chains.
- [PR #132](https://github.com/pguyot/Einstein/pull/132), merge commit
  [`5e3ea5afa36009b63012b19943719e0ab4433181`](https://github.com/pguyot/Einstein/commit/5e3ea5afa36009b63012b19943719e0ab4433181),
  added emulated DHCP and DNS. It substantially changed
  `TUsermodeNetwork.cpp` but did not change the NE2000 send primitives.

No issue, pull request, commit message, or code-history change was found that
implements `TNativePrimitives` primitive `0x08` or `0x09`, or that identifies
either stub as an outbound TCP data-loss bug.

### NIE/Lantern supports both a flat buffer and a buffer chain

Einstein’s bundled driver is derived from Apple’s NIE 2.0 F1C2 Lantern driver
sample. It registers handlers for both `kLanternSendBuffer` and
`kLanternSendCBufferList`. Its own comment describes their contract:

> “Send a packet in the buffer ptr or the CBufferList”
>
> “These events [are] sent to a driver when Lantern needs data to be sent. The
> driver should send data asynchronously. The driver should buffer data to be
> sent as it may receive more data to send.”

The two handlers converge before crossing into native Einstein code. The
single-buffer path directly calls `EinsteinNetSendPacket`:

```cpp
void TNE2000Sample::SendBuffer(Ptr thePacket, Size packetSize)
{
    NewtonErr err = noErr;

    EinsteinNetSendBuffer(this);
    EinsteinNetSendPacket(this, (UChar*)thePacket, packetSize);

    fDriverAPI->PostReply(err);
}
```

The chained-buffer path obtains the complete chain size, resets its read mark,
copies the entire chain into a temporary contiguous buffer, and then invokes
the same `EinsteinNetSendPacket` entry point:

```cpp
void TNE2000Sample::SendCBufferList(CBufferList* thePacket)
{
    NewtonErr err = noErr;

    EinsteinNetSendCBufferList(this);

    Size packetSize = thePacket->GetSize();
    thePacket->ResetMark();
    UChar *tmpBuffer = (UChar*)malloc(packetSize);
    thePacket->Getn(tmpBuffer, packetSize);
    EinsteinNetSendPacket(this, tmpBuffer, packetSize);
    free(tmpBuffer);

    fDriverAPI->PostReply(err);
}
```

Source:
[`Drivers/NE2000Driver/NE2000.cpp`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Drivers/NE2000Driver/NE2000.cpp).
The same code is present in the initial network-emulation commit
[`8b7ffd3214e142bff08f22b45bca9d468a844fc1`](https://github.com/pguyot/Einstein/commit/8b7ffd3214e142bff08f22b45bca9d468a844fc1),
so this is not a later workaround.

This explains the apparently suspicious native stubs. In
[`TNativePrimitives.cpp` lines 2972–3003](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Emulator/TNativePrimitives.cpp#L2972-L3003),
`0x08` and `0x09` only log `SendBuffer` or `SendCBufferList`; `0x0a` reads the
already-contiguous packet from Newton memory and calls
`mNetworkManager->SendPacket(data, size)`. The driver, not native primitive
`0x09`, owns traversal and flattening of the `CBufferList`.

Consequently, a trace containing `SendCBufferList` but not the immediately
following `SendPacket` would implicate the installed Newton driver’s
`GetSize`/`ResetMark`/`Getn` path, a stale or different `NE2K.pkg`, or a fault
between the two native calls. It would not show that native primitive `0x09`
discarded the payload. In the current trace there is not even a post-`Output`
`SendCBufferList` call, so the observed loss is still above this driver
boundary.

I found no NewtonTalk, 40hz.org, or UNNA list/documentation post that discusses
`SendCBufferList` by name. Thus the single-buffer-versus-chain behavior above
is supported by the recovered Apple-derived driver source, not independently
confirmed by a community list post.

### Public evidence of working outbound TCP

There is direct historical evidence that user-mode networking emitted
data-bearing outbound TCP frames:

- Matthias Melcher’s 2010 NewtonTalk developer-preview post said Einstein could
  **“load very minimal web pages via the host’s internet connection”** and gave
  exact instructions for selecting the **“User Mode”** driver, installing
  NIE 2.0, the Einstein NE2000 package, and Courier:
  [NewtonTalk, 2010-06-19](https://marc.info/?l=newtontalk&m=127698576108716&w=2).
  This was the OS X implementation.
- Four days later he published an OS X binary and reported:
  **“Network support just got a whole lot better”**; Courier could load simple
  pages, while Newt’s Cape could eventually load Google:
  [NewtonTalk, 2010-06-23](https://marc.info/?l=newtontalk&m=127727247206541&w=2).
- Follow-up testing reported Courier receiving a 2,792-byte UNNA page but
  cutting it off after a repeatable point:
  [NewtonTalk, 2010-07-15](https://marc.info/?l=newtontalk&m=127919622201400&w=2).
  That is evidence of a functioning HTTP request and response stream, although
  with receive/close bugs.
- The current source’s status comment still says **“TCP connections are
  created and can send and receive,”** lists `TCP connect`, `TCP send`, and
  `TCP receive` as done, and says TCP port 3679 **“works mostly well with NCX
  2.0”**:
  [`TUsermodeNetwork.cpp` lines 24–85](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Emulator/Network/TUsermodeNetwork.cpp#L24-L85).
  This is developer documentation rather than an independently reproduced
  modern test.
- In 2016, a Mac user reported that an NPDS tracker successfully received the
  emulated Newton’s registration but inbound access to the NPDS server failed.
  Matthias explained that the **User Mode network driver** did not support
  opening listening ports:
  [question](https://marc.info/?l=newtontalk&m=148304793012724&w=2),
  [answer](https://marc.info/?l=newtontalk&m=148312495827573&w=2).
  The successful tracker registration is additional evidence of outbound
  application data; the “one way only” limitation concerned host-to-Newton
  connection initiation, not Newton-to-host sends.
- A 2022 NewtonTalk thread about NCU “via TCP” is *not* evidence for the
  Ethernet user-mode path. Its detailed instructions show that it used
  Einstein’s emulated serial port transported over a host TCP socket:
  [NewtonTalk, 2022-02-01](https://marc.info/?l=newtontalk&m=164374899207138&w=2).

I could not verify a modern, version-specific report of Courier or another
HTTP client successfully sending through `TUsermodeNetwork` on the current
2024–2026 releases. I also could not verify a user-mode Ethernet NCX session
on a named release and platform; the source comment is the only explicit NCX
claim found. UNNA supplied the application packages but yielded no relevant
driver documentation, and no searchable 40hz.org or NewtonTalk material was
found for the primitive names.

### Verdict

There is no known upstream fix to cherry-pick: the harness already pins
upstream `HEAD`, and every relevant historical TCP, sequence-number, and
user-mode-network fix is included. The evidence does **not** support the
theory that native `SendCBufferList` primitive `0x09` discards outbound TCP
payload. NIE/Lantern may hand the driver either a flat buffer or a
`CBufferList`, but Einstein’s Newton-side NE2000 driver explicitly flattens
the latter and always passes the resulting frame through primitive `0x0a`.
Historical Courier and NPDS reports prove that outbound application TCP has
worked through this architecture. Given the present trace’s absence of any
post-`Output` `SendBuffer`, `SendCBufferList`, or `SendPacket` call, the
remaining fault is more likely above the Lantern driver entry points—endpoint
state, NIE transport scheduling/completion, or a difference between the
installed `NE2K.pkg` and the driver source—rather than in
`TUsermodeNetwork` or the native `0x09` stub.

## 2026-07-24 — Round 4: stock PT100 control experiment

### Bottom line

The decisive stock control failed in the same way as the Loader. PT100 completed a TCP connection to a numeric host, displayed a connected terminal, and accepted typed input, but the host listener received zero payload bytes. This confirms that the missing outbound TCP payload is Einstein/NIE-side rather than a Loader NewtonScript problem; the Loader's data representation, flush behavior, and `Output` argument form are exonerated by an independent stock NewtonOS application.

### Experimental setup and flash restores

- Ran a logged TCP listener on host address `10.42.0.1`, port `18082`, with no DNS involved. Listener evidence is `runtime/logs/round4-pt100-listener.log`.
- Configured stock PT100 with a Telnet session targeting numeric host `10.42.0.1` and custom port `18082`. The final visible configuration is captured in `runtime/evidence/round4-stock-config-final-decisive.png`.
- Before any restore, preserved the then-current flash as `runtime/backups/internal-before-round4-stock-control-restore-20260724-074316.flash`, SHA-256 `65a216599b9700692ac70afaa0ffaf4d8d8480449002b99f31031e8a30f92833` (`runtime/evidence/round4-stock-control-restore-backup.sha256`).
- First restored `runtime/backups/internal-before-tcpdiag-rebuild-20260724-060617.flash`, SHA-256 `d566009ec599651275091ac04efb7343ea87a8affe6fbc793c77f92ba861ba3d`, to clear PT100's wedged saved state. The matching restore stamp is `runtime/evidence/round4-restored-flash.sha256`. This produced a clean PT100 terminal but required constructing a session and custom port from scratch; the image was restored again while correcting mistaken session-editor actions and stale connection state.
- For the decisive run, restored the Round 3 pre-binary-hypothesis image `runtime/backups/internal-before-round3-loader-binary-20260724-070952.flash`, SHA-256 `240f92fb95e690099448ba0a07e8d677d1b215107835bdc83112d87f3e208e0`. Its saved PT100 Telnet session (`ouagadougou`) avoided rebuilding the session from a blank editor; only the host and port were changed for this control.

### Decisive result

PT100 established the connection and showed its connected terminal (`runtime/evidence/round4-stock-connected-before-input.png` and `runtime/evidence/round4-stock-terminal-active.png`). The characters `xy` were then entered; the post-input state is captured in `runtime/evidence/round4-stock-final-xy.png` and `runtime/evidence/round4-stock-payload-verdict.png`.

The listener recorded exactly:

```text
LISTEN 10.42.0.1:18082
ACCEPT ('10.42.0.1', 35442)
TIMEOUT
TOTAL b''
```

Thus the TCP handshake reached the host, but no data-bearing frame or application byte followed. Stock PT100 TCP payload **DOES NOT** reach the host. Because a stock NewtonOS application reproduces the Loader's symptom, the defect is in the Einstein/NIE networking path, not in Loader NewtonScript. No Round 4 fix hypothesis was applied; the requested stock control alone moved the fault boundary decisively.

### Key evidence

- Listener acceptance and empty read: `runtime/logs/round4-pt100-listener.log`.
- Final numeric host and custom port: `runtime/evidence/round4-stock-config-final-decisive.png`.
- PT100 connected before typing: `runtime/evidence/round4-stock-connected-before-input.png`.
- Connected terminal and typed-input state: `runtime/evidence/round4-stock-terminal-active.png`, `runtime/evidence/round4-stock-final-xy.png`, and `runtime/evidence/round4-stock-payload-verdict.png`.
- Native-diagnostic baseline markers captured around attempts: `runtime/evidence/round4-decisive-native-before.txt`, `runtime/evidence/round4-stock-native-before.txt`, and `runtime/evidence/round4-stock-final-native-before.txt`.
- Restore checksums: `runtime/evidence/round4-stock-control-restore-backup.sha256` and `runtime/evidence/round4-restored-flash.sha256`.

### Flash state left behind

The live flash is the restored `internal-before-round3-loader-binary-20260724-070952.flash` state plus PT100's saved `10.42.0.1:18082` session changes; it therefore no longer matches the backup byte-for-byte. Its final observed SHA-256 is `8cacf74b97f44c691372b46b89517e2a03d813acfeedb9b9c0bc7f52e31538e6`.

That restored image still has the earlier `HarnessLoader:jbfly` Loader and `HarnessProbe:jbfly` diagnostic application installed. It does not contain the later Round 3 `HarnessLoaderR3*` variants, and `HarnessClient:jbfly` is not installed. PT100 and the NIE/NE2000 networking packages used by the control remain installed. No acceptance install occurred.

### PT100 and control-API notes for future agents

- The Extras drawer is paged. Do not trust a nearby text label alone: the icon initially mistaken for PT100 was Dock. Navigate to the page containing the actual PT100 icon and verify the resulting app screen.
- PT100 normally opens to a blank terminal canvas; that does not mean launch failed. Open PT100's command/menu control and choose Connect to reach the connection slip.
- Reusing the saved `ouagadougou` Telnet session is much more reliable than creating a blank session through the control API. The session editor is multipage, and the port is selected through a port-list editor rather than a simple port field.
- To add port `18082`, enter a custom `Name: port` row on the port editor's input line, press **Add**, then select that new row. The adjacent unlabeled control is **Delete**; an exploratory tap there removed an entry and required a restore.
- Fully select and clear PT100 text fields before typing replacements. A field can look correct while retaining stale characters or an old lookup state. If PT100 is already stuck in `Looking up machine address...` or a stale connection attempt, restart from the saved configuration before making the clean test connection.
- The `/drag` control endpoint is useful for PT100's multipage forms and field selection, but screenshots after each action are still necessary because taps on small, unlabeled controls are easy to misidentify.

## 2026-07-24 — Round 5 matched-driver verification

### Bottom line

The prime stale/mismatched-driver hypothesis is disproven. The pinned Einstein tree at `f5544a039fc3964e18b217ccffa030c6bf1e4044` contains a 4,768-byte `Drivers/NE2000Driver/NE2K.pkg` with SHA-256 `fa8df5d6c77d5d1e85cea72ce2fb80d9ec648c40a77d50ac6f1549f4d7290a85`. Reconstructing the installed package from the current flash's noncontiguous 1 KiB storage chunks produces the identical 4,768 bytes and the identical hash. The active PT100 setup is also bound to this package: its connection slip says `Card PCMCIA Ethernet`, exactly the package's `DeviceDisplayName`, and this FLTK Einstein build unconditionally constructs `TUsermodeNetwork` in `app/FLTK/TFLApp.cpp`.

No package was installed, so no flash mutation or pre-install backup was required. The stock PT100 payload failure therefore remains above the matched NE2K driver's send entry points; the existing frame-hex instrumentation capture remains the decisive next-boundary evidence. The Loader acceptance cycle was not run because its required gate—stock PT100 payload bytes reaching the listener—did not pass.

### Three evidence-backed hypotheses/results

1. **The current flash contains a stale or mismatched `NE2K.pkg`. — Disproven.** A cached Docker builder stage materialized the exact pinned/patched source tree and confirmed commit `f5544a039fc3964e18b217ccffa030c6bf1e4044`. Its tracked `Drivers/NE2000Driver/NE2K.pkg` is 4,768 bytes, SHA-256 `fa8df5d6c77d5d1e85cea72ce2fb80d9ec648c40a77d50ac6f1549f4d7290a85`, and is byte-identical to `runtime/nie2/NE2K.pkg`. Newton stored the installed package across noncontiguous flash chunks: logical package offsets `0`, `1024`, `2048`, `3072`, and `4096` were recovered at physical offsets `1613196`, `1614240`, `1610064`, `1611108`, and `1612152`. Concatenation reconstructed all 4,768 source bytes exactly. Evidence: `runtime/evidence/round5-ne2k-flash-compare.txt`, `runtime/round5/NE2K-f5544a.pkg`, and `runtime/round5/NE2K-from-current-flash.pkg`.
2. **The correct package is installed but Internet Setup is bound to another Ethernet driver/backend. — Disproven.** The stock PT100 configuration slip visibly reports `Using Untitled Ethernet Setup` and `Card PCMCIA Ethernet` (`runtime/evidence/round4-decisive-nie-slip.png`). `strings -el` on the pinned package reports `NE2K` and `PCMCIA Ethernet`; the latter is its `DeviceDisplayName`. On the host side, pinned `app/FLTK/TFLApp.cpp:1177-1183` unconditionally assigns `mNetworkManager = new TUsermodeNetwork(mLog)` for Linux, and the running native diagnostics identify frames crossing that backend. Thus both the Newton-side NE2K selection and Einstein-side User Mode backend are active.
3. **With a matched and bound driver, the first application payload still fails before a driver send entry point. — Supported.** The frame-hex instrumentation already built for the single decisive stock PT100 attempt records a 58-byte SYN and 54-byte handshake ACK, then no data-bearing `EinsteinNetSendBuffer`, `EinsteinNetSendCBufferList`, or `EinsteinNetSendPacket` call. The host listener records `ACCEPT ('10.42.0.1', 35442)`, `TIMEOUT`, and `TOTAL b''`. Evidence: `runtime/logs/round4-pt100-listener.log`, the `TCPDIAG native frame` sequence in `podman logs newton-harness_emulator_1`, and `runtime/evidence/round4-stock-payload-verdict.png`. Because the trace was read before any patch and shows no driver-level payload submission, no new network patch was made.

### Build and runtime actions

- Built the Docker `builder` target in the background with `nohup`; `runtime/logs/round5-builder.exit` is `0` and the resulting image is `localhost/newton-harness-builder:round5` (`4bcd29b54f7c...`).
- Extracted the pinned package to `runtime/round5/NE2K-f5544a.pkg` and reconstructed the current flash copy at `runtime/round5/NE2K-from-current-flash.pkg`.
- Restarted only `newton-harness_emulator_1` to clear PT100's volatile stale connected state while attempting a fresh control. The health API returned `status: ready`; flash was not replaced or installed to, and the physical Newton, AP, and firewall were untouched.
- Did not install NE2K, did not run the Loader acceptance cycle, and did not alter Einstein network code because the matched-driver check failed to open the stock-payload gate.

### Next boundary

Instrument NIE/endpoint scheduling above `TNE2000Sample::SendBuffer`/`SendCBufferList`, not `TUsermodeNetwork`: the matched driver receives control frames correctly, but stock PT100 application output never invokes either driver send handler. A useful next experiment is a Newton-side completion/error trace around Lantern's outbound queue and PT100's first `Output`, captured once before changing behavior.

## 2026-07-24 — Round 6: synthesized SYN-ACK validation

### Bottom line

The prime malformed-SYN-ACK hypothesis is disproven. In one stock PT100 connection to a live listener on `10.42.0.1:18082`, Einstein handed Newton a 58-byte SYN-ACK with a nonzero 4,096-byte window, sequence `0`, acknowledgment `90412705` for Newton's SYN sequence `90412704`, a single MSS 1460 option, and valid IPv4 and TCP checksums. Newton returned the correct handshake ACK (`seq=90412705`, `ack=1`) but still emitted no payload after `xy` was typed; the listener accepted the connection and ended with `TOTAL b''`.

No network behavior patch was made and the Loader acceptance cycle was not run, because the SYN-ACK is well formed and the required stock-PT100-payload gate still fails. The remaining boundary is the NewtonOS NIE/Lantern outbound scheduler above the registered `kLanternSendBuffer` / `kLanternSendCBufferList` driver callbacks.

### Three evidence-backed hypotheses/results

1. **Einstein synthesizes a malformed SYN-ACK that leaves Newton with no send window. — Disproven.** `TCPPacketHandler::NewPacket` creates an Ethernet/IP/TCP frame with a 20-byte IP header, default 20-byte TCP header, sequence `mEinsteinPacketsSeq` (initialized to `0`), acknowledgment `mNewtonPacketsSeq`, and TCP window `0x1000`. `connect()` reserves four TCP-option bytes, sets SYN+ACK, changes the TCP header to 24 bytes, keeps sequence `0`, sets acknowledgment to `++mNewtonPacketsSeq`, and writes MSS option `02 04 05 b4` (1460). It then recomputes both checksums. The existing `einstein-tcp-send-after-ack.patch` only changes handling of Newton's following ACK/payload in `kStateConnectionWaitACK`; it does not alter SYN-ACK construction. Static evidence: `runtime/evidence/round6-synack-static.txt`.
2. **The correctly constructed SYN-ACK is corrupted or materially changed before Newton receives it. — Disproven.** New diagnostic patch `containers/patches/einstein-tcp-inbound-diag.patch`, wired into `containers/emulator.Dockerfile`, hex-dumps the final buffer in `TUsermodeNetwork::ReceiveData` immediately after the copy to Newton memory. The actual inbound SYN-ACK was `58 b0 35 77 d7 22 00 fa c0 a8 01 01 08 00 45 00 00 2c 03 e8 00 00 40 06 aa e7 0a 2a 00 01 c0 a8 01 2a 46 a2 83 37 00 00 00 00 05 63 96 a1 60 12 10 00 56 3b 00 00 02 04 05 b4`. Independent decoding gives frame length 58, IP total length 44, source `10.42.0.1:18082`, destination `192.168.1.42:33591`, sequence `0`, acknowledgment `90412705`, SYN+ACK flags `0x012`, 24-byte TCP header, window 4096, MSS 1460, IPv4 checksum `0xaae7`, and TCP checksum `0x563b`; recomputing each checksum over the captured bytes returns zero. Evidence: `runtime/evidence/round6-capture-tcpdiag.txt` and `runtime/evidence/round6-synack-decode.txt`.
3. **NewtonOS accepts the well-formed handshake but its NIE/Lantern outbound queue never schedules the first application payload to either registered driver send callback. — Supported.** The live listener recorded `ACCEPT ('10.42.0.1', 33316)`, then `TIMEOUT` and `TOTAL b''`. The native trace records the 58-byte SYN, the exact inbound SYN-ACK, and Newton's 54-byte ACK (`seq=90412705`, `ack=1`, window 4096), but no subsequent `EinsteinNetSendBuffer`, `EinsteinNetSendCBufferList`, or `EinsteinNetSendPacket` before the listener timed out. The pinned tree exposes only the Apple-derived driver-side registration (`fDriverAPI->AddEventHandler(kLanternSendBuffer, ...)` and `kLanternSendCBufferList`) and the two callback implementations; it does not contain the NewtonOS NIE/Lantern queue implementation that decides to dispatch those events. Thus further instrumentation above this boundary requires binary-level NIE tracing or separately recovered NIE source, not another Einstein host-network patch. Evidence: `runtime/logs/round6-live-listener.log`, `runtime/evidence/round6-capture-tcpdiag.txt`, and pinned `Drivers/NE2000Driver/NE2000.cpp`.

### Build, runtime, and flash actions

- Built the emulator in the background with `nohup` and polled `runtime/logs/round6-emulator-build.exit`; exit status is `0`. The running image is `112a018dabf0d709581abdd7dfa11bf968f8d823cc1e48e7947212aa48bf00c5`.
- Added only inbound frame observation; packet construction and delivery behavior are unchanged.
- PT100's saved machine field had a stale hidden `xy` suffix from earlier UI state. Preserved the live flash first as `runtime/backups/internal-before-round6-pt100-restore-20260724-090216.flash`, SHA-256 `b13243a39c3461180d857bce465880e4538cc24967d64045b5eef3ac5368782c`, then corrected the field to exactly `10.42.0.1` while preserving custom port `harness: 18082`.
- No package was installed, so no pre-install backup/install transaction occurred. The physical Newton, AP, and firewall were untouched; all prior backups and evidence remain present.

### Acceptance status and next boundary

Stock PT100 payload did not reach the listener, so the Loader acceptance gate remains closed. `runtime/raw_pkg_server.py` was left running on `10.42.0.1:18081`, but no Loader install/download cycle was attempted. The next useful experiment is a NewtonOS-side trace at the NIE TCP output queue and the Lantern event-dispatch decision immediately above `kLanternSendBuffer` / `kLanternSendCBufferList`; the Einstein repository does not provide that scheduler source, so this needs recovered NIE symbols/source or targeted binary instrumentation of the installed NIE packages.

## 2026-07-25 — Round 7B: Loader output investigation

### Starting evidence and repository state

- `runtime/evidence/round7-decisive-xy-trace.txt` proves stock PT100 reaches `TNewScriptEndpointClient::DoOutput` at ROM `0x00134fdc`, then `OutputRaw`, `TEndpoint::nSnd(raw)`, `PConnectionEnd::PutBytesStart`, and a one-byte TCP frame (`state=kStateConnected payload=1`, `host-send requested=1 sent=1 errno=0`).
- The requested Round 7 section is absent from `docs/newton-dev-notes.md` at `HEAD 2ddc8cc`. `git show --stat 2ddc8cc` lists only `containers/emulator.Dockerfile` and `containers/patches/einstein-nie-rom-trace.patch`; this Round 7B section therefore records the recovered starting point.
- Loader source constructs `{_proto: protoBasicEndpoint}` at `examples/harness-loader/Main.newt:62` and synchronously calls three-argument `Output(data, nil, outSpec)` at lines 159-164. The same endpoint construction is used by the harness client and network probe; neither is evidence of a successful payload send.

### Source-level cause identified

- PT100's package frame inherits the same ROM prototype as the Loader (`eptClass._proto: @383`, which `21DEFS.TXT:206` names `protoBasicEndpoint`), so the prototype itself is not wrong.
- PT100's `MConnectAction` bytecode/literals call `Instantiate(configOptions, self)`, `Bind(nil, nil)`, and lowercase `connect(addressOptions, completionSpec)`. Its `MOutputBinary` calls lowercase three-argument `output(data, nil, fEndpointOutputBinarySpec)`. Evidence: `runtime/evidence/round7b-pt100-actions-full.txt` and the concise extracts in `runtime/evidence/round7b-pt100-connect-call.txt`.
- The Loader instead reverses the `Instantiate` arguments (`Instantiate(self.endpoint, options)`) and uses uppercase `Connect` and `Output` at `examples/harness-loader/Main.newt:65-88,159-164`. The ROM symbol table distinguishes old `CIConnect`/`CIOutput` (`TScriptEndpointClient`) from `CINewConnect`/`CINewOutput` (`TNewScriptEndpointClient`), matching the observed old-versus-new client behavior.
- The minimum candidate fix is therefore to match PT100: pass configuration options first and the endpoint frame second, then call lowercase `connect` and `output`. No endpoint-class replacement or Einstein network patch is needed.

### Fix applied and verification status

- Applied the PT100-compatible call pattern in `examples/harness-loader/Main.newt`: `Instantiate(options, endpointFrame)`, lowercase `connect(options, requestSpec)`, and lowercase `output(data, nil, outputSpec)`. The package keeps the existing `HarnessLoaderR3O:jbfly` identity so it replaces the saved diagnostic Loader, while its visible version is `1.1-r7b`.
- `make -B -C examples/harness-loader` succeeds; replacement package SHA-256 is `37b003f8c61b9c4299e87844409dbd7d189e018b30d332319ee86619776a4e71`. `runtime/evidence/round7b-fixed-loader-bytecode.txt` confirms the built package contains lowercase `connect` and `output` literals.
- Independently validated that `containers/patches/einstein-nie-rom-trace.patch`, including the old-client addresses, builds successfully. `runtime/logs/round7b-romtrace-build.exit` is `0`; image ID is `f158c81fdc6d75e0ba3f86c9970919c10776e374d6acbb3975f262b6ab83b9f2`.
- Backed up live flash before package installation as `runtime/backups/internal-before-round7b-loader-20260725-180001.flash`, SHA-256 `8a2c37ebcc2e922025537d50cc3c4a780a8dd8e2c1f6b2839ab8ee0d509db369`.
- Installed both the uniquely named R7B diagnostic and then the R3O replacement; live-flash strings confirm `Harness Loader v1.1-r7b`. The replacement launches (`runtime/evidence/round7b-loader-open-clean.png`).
- A decisive live send was not reached in this session: after the emulator restart, `InetGrabLink` first returned a non-connected state displayed as `Link: connect...`, and the next attempt remained at `Fetch attempt 1 of 2...` without a TCP SYN. Therefore no claim is made that the HTTP download/input path is fully verified. This does not contradict the source diagnosis: the test stopped before `Instantiate`, `connect`, or `output` could execute.

### Round 7B bottom line

The Loader never sent because it used the legacy endpoint API incorrectly: its `Instantiate` arguments were reversed and it invoked uppercase legacy `Connect`/`Output`. Stock PT100 proves the working Newton 2.x path uses the same `protoBasicEndpoint` but calls `Instantiate(configOptions, endpointFrame)`, lowercase `connect`, and lowercase `output`, which dispatch to `TNewScriptEndpointClient`. The Loader source now matches that pattern; the remaining verification step is to rerun it once `InetGrabLink` reports `connected` and confirm the built request reaches `runtime/raw_pkg_server.py`.

## 2026-07-25 — Round 8: runtime confirmation

### Starting state

- Began at clean `master` commit `3bb0def19f1c8cda521c3412cc5d2b06d08c85e1`; the Loader fix is commit `86be141` and its built package SHA-256 is `37b003f8c61b9c4299e87844409dbd7d189e018b30d332319ee86619776a4e71`.
- Round 8 is gated on two live observations from the fixed Loader: a non-empty HTTP GET in `runtime/logs/raw-pkg-server.log` and `TNewScriptEndpointClient::DoOutput` in the emulator ROM trace. No harness-client or network-probe source will be changed unless both observations are captured.
- Before the Round 8 install, copied the live 8,388,608-byte flash to `runtime/backups/internal-before-round8-loader-20260725-182141.flash`. Both source and backup SHA-256 are `813b401f22483bea8a5a772afe31e62bbf6f53f269b2668888a6b614c51cb2ba`; evidence is `runtime/evidence/round8-loader-backup-sha256.txt`.
- Einstein's package installer opened the exact `/packages/harness-loader/harness-loader.pkg`, but Newton rejected it only because `HarnessLoaderR3O:jbfly` was already installed on Internal (`runtime/evidence/round8-after-loader-install-screen.png`). The live flash contains `Harness Loader v1.1-r7b`; the source package SHA-256 remains `37b003f8c61b9c4299e87844409dbd7d189e018b30d332319ee86619776a4e71`.

### Screen orientation resolved

- The emulator Newton display is **320 pixels wide by 480 pixels high (portrait)**. `containers/emulator.Dockerfile:128-129` sets `NEWTON_SCREEN_WIDTH=320` and `NEWTON_SCREEN_HEIGHT=480`; `README.md` documents `/screen.png` as 320×480; and the Round 7B cropped screenshots are 320×480 PNGs. `PLAN.md:45` says 480×320 and is stale. Runtime controls and view bounds must use 320×480 unless the emulator configuration changes. Evidence: `runtime/evidence/round8-screen-orientation.txt`.

### Runtime transport result — stopped at the Loader gate

- The saved Newton network setup is present and usable. Internet Setup shows `Untitled Ethernet Setup` with `PCMCIA Ethernet`; PT100 selected its saved `Ouagadougou` session and displayed `Using Untitled Ethernet Setup` / `Card PCMCIA Ethernet`. A control connection emitted a 58-byte TCP SYN from `192.168.1.42:33392` to `10.42.0.1:18082`, received a SYN-ACK, and returned the handshake ACK. This proves the Einstein NIE/NE2000 transport reached a connected TCP state and that a SYN left Newton. Evidence: `runtime/evidence/round8-pt100-connect-button-result.png`, `runtime/evidence/round8-nie-control-syn.txt`, and `runtime/evidence/round8-pt100-link-result.png` (the final `-48410` is expected because no listener was running on PT100's saved control port 18082).
- The host AX200 AP was not stable: each verified `ssid newton` / `type AP` launch was followed within seconds by repeated iwlwifi resets and loss of `10.42.0.1`. For the emulator-only test, the same address was temporarily assigned to loopback through the existing authorized AP script, the script text was immediately reverted, and `runtime/raw_pkg_server.py` was verified listening on `10.42.0.1:18081`. The temporary address and AP were removed afterward; the repository scripts have no diff. Evidence: `runtime/evidence/round8-ax200-reset.txt`, `runtime/evidence/round8-host-listener.txt`, and `runtime/logs/round8-ap-teardown.log`.
- The fixed installed Loader still did **not** pass the runtime gate. Its first tap emitted link traffic only and ended `Install failed twice: Link: connect`. After the link transition settled, the bounded second tap reached `Fetch attempt 1 of 2...` and remained there for 16 seconds. The complete emulator delta contains only control-API requests: no `NIE7`, no `TCPDIAG`, and no `TNewScriptEndpointClient::DoOutput`. The package-server delta is empty, so no HTTP GET arrived. Evidence: `runtime/evidence/round8-loader-after-5s.png`, `runtime/evidence/round8-loader-retry-6s.png`, `runtime/evidence/round8-loader-retry-16s.png`, `runtime/evidence/round8-loader-retry-emulator-delta.txt`, and zero-byte `runtime/evidence/round8-loader-retry-server-delta.txt`.
- **Hard-gate verdict:** transport itself is runtime-proven with PT100, but the fixed Loader remains stalled before endpoint setup/output. Goal 1 therefore fails; no claim is made that the endpoint fix completes an HTTP fetch. Per the gate, `examples/harness-client/Main.newt` and `examples/network-probe` were not changed or rebuilt.

## 2026-07-25 — Round 9: Loader link-state correction (runtime gate still closed)

### PT100 evidence and source changes

- Reused the Round 7B decode rather than decoding PT100 again. `runtime/evidence/round9-pt100-call-sequence.txt` preserves the existing `MConnectAction` evidence: PT100 calls `Instantiate(configOptions, self)`, then `Bind`, then lowercase `connect`.
- The preferred no-`InetGrabLink` path was tested in an independently named package (`HarnessLoaderR9D:jbfly`) so Newton could not retain the previously installed R3O package. It failed before a SYN with Newton error `-48400`; therefore this Loader configuration requires the `ilid` option and the deletion-only fix is not viable on the current image.
- Restored the link-ID path with the three source corrections: `Instantiate(..., self)` uses the owner frame; the `'connect` callback is treated as an in-progress transition rather than a failure; and the link ID is saved immediately so `Stop` can release it before a retry. The project/package identity is restored to `HarnessLoaderR3O:jbfly`, visible version `1.1-r9`.

### Runtime result

- Built and installed uniquely named r9/r9b/r9c diagnostic packages to avoid the stale stable-identity package seen in Round 8. The fallback path progressed past the initial `'connect` callback, but endpoint setup failed before any TCP SYN or `TNewScriptEndpointClient::DoOutput`; cleanup then exposed Newton Internet Enabler event error `-48803` while removing the link client from the connected FSM. Representative evidence: `runtime/evidence/round9b-fetch-after-10s.png` and `runtime/evidence/round9c-fetch-result.png`.
- The hard acceptance gate did **not** pass: `runtime/logs/round9-raw-server.log` remained empty, no SYN to `10.42.0.1:18081` appeared, and no HTTP GET arrived. No success screenshot exists. `examples/harness-client` and `examples/network-probe` were not touched.
- The temporary `10.42.0.1/24` loopback address was added through the authorized `ap/apply.sh` workaround, the tracked script was restored immediately, and the address and raw package server were removed after testing. The final loopback has only `127.0.0.1/8` and `::1/128`.

### Next boundary

Capture the original communication exception before `Failed` calls `Stop`; the asynchronous `InetReleaseLink` event currently overlays the actual endpoint error. Do not change Einstein transport: Round 8 already proved it with PT100.

## 2026-07-25 — Round 10: captured Loader endpoint exception

### Bottom line

The hard gate did **not** pass. The uniquely identified diagnostic package `-HarnessLoaderR10G:jbfly` / visible `- R10G Loader 1.1-r10g` catches the failure before cleanup and shows that `Instantiate` throws `|evt.ex.fr.type;type.ref.frame|`, error `-48400` (`kNSErrNotAFrame`, “Expected a frame”). No SYN, HTTP GET, or Loader success state followed.

### Changes and evidence

- Broadened the endpoint catch to `|evt.ex|`, captured `CurrentException()` as the handler's first statement, labeled the active `Instantiate`/`Bind`/`connect` call, and displayed the exception name, numeric error, data, and message without calling `Failed` or `Stop`. Evidence: `runtime/evidence/round10d-real-exception.png` and `runtime/evidence/round10-gate-summary.txt`.
- Replaced orientation-specific bounds with Newton's runtime parent justification (`vjParentFullH + vjParentFullV` and negative margins). The tested screen remained 320×480 portrait.
- Decoded PT100's actual option builders. Its configuration and connect options contain `result: nil` and case-sensitive `typeList` slots; the Loader now matches those frames. PT100 emits `opCode: 512`, equal to `opSetRequired`.
- Tested both the direct ROM endpoint prototype and a PT100-like two-level endpoint subclass, and tested the second `Instantiate` argument as the endpoint frame. All still threw the same `-48400` at `Instantiate`; `Bind` and `connect` were never reached. Final screenshots: `runtime/evidence/round10g-loader-open.png` and `runtime/evidence/round10g-underlying-result.png`.
- Every runtime-tested package had a unique identity (`r10a` through `r10g`). The final screenshot visibly shows `1.1-r10g`; live-flash evidence is `runtime/evidence/round10g-live-flash-identity.txt`.
- Host setup could not be applied because noninteractive sudo required a password. `10.42.0.1` was never added, and no package server or capture process remained running.

### Next boundary

Inspect the exact endpoint instance frame that PT100's `eptClass:New` passes into ROM and the first frame dereference in `TNewScriptEndpointClient::InitScriptEndpointClient` at ROM symbol `0x001377B8`. The Loader's option array now matches PT100, so the remaining `-48400` is in the endpoint-instance contract, not transport or option encoding.

## 2026-07-25 — Round 11B: endpoint-first runtime result

### Bottom line

The endpoint-first `Instantiate` hypothesis is confirmed: r11a no longer throws round 10's `-48400` at `Instantiate`. A demonstrably fresh trace reaches `10.42.0.1:18081` and completes the SYN/SYN-ACK/ACK handshake. The hard gate still does **not** pass because no HTTP request bytes follow; the raw server times out with `RAW b''`, and there is no Loader success screenshot.

The final tested package is `-HarnessLoaderR11E:jbfly`, visible version `1.1-r11e`. It adds PT100's three-argument connect completion shape and prevents repeated `InetGrabLink` `connected` notifications from replacing an already-created endpoint. That guard reduces one tap from two simultaneous TCP connections to exactly one, but the completion remains stuck at `Connecting...` and never calls `output`.

### Runtime evidence

- Freshness is explicit in `runtime/evidence/round11b-r11e-baseline.txt`: the capture command is `podman logs --since 0s -f`, its initial size is zero, and the package-server baseline is byte 215.
- Gate (a) passes. `runtime/evidence/round11b-r11e-runtime-relevant.txt` contains one 58-byte SYN with destination IP bytes `0a 2a 00 01` and destination port bytes `46 a1`, followed by the handshake ACK. The decoded trace reports `dst=18081`.
- Gate (b) fails. The server delta is `ERROR ('10.42.0.1', 51630) timed out` and `RAW b''`; no non-empty GET arrived. Consolidated evidence is `runtime/evidence/round11b-gate-summary.txt`.
- Gate (c) fails. `runtime/evidence/round11b-r11e-open.png` visibly identifies `R11E Loader 1.1-r11e`, but the tested result remains `Connecting...` and no success screenshot exists.
- Live-flash identity evidence is `runtime/evidence/round11b-r11e-live-flash.txt`; package build and checksum evidence are `runtime/evidence/round11b-r11e-build.log` and `runtime/evidence/round11b-r11e-package.sha256`.

### Iterations and source result

- r11a changed only the call to endpoint-first: `self.endpoint:Instantiate(self.endpoint, options)`. It cleared `-48400`, reached TCP, then surfaced connect-stage `-48808` (Einstein toolkit: “Undefined global function”) after the host timed out with no payload.
- r11c mirrored PT100's connect completion frame. A captured local closure crashed `tntk`; replacing it with a non-capturing callback built cleanly. Runtime still remained at `Connecting...`.
- r11d used PT100-like lexical `self` in the completion callback. One tap still created two TCP connections, both empty.
- r11e added `if self.endpoint then return nil` before `Resolved`. One tap then created exactly one TCP connection, proving duplicate `InetGrabLink` notifications caused the double connect. It did not cause the GET to be emitted.

`examples/harness-client` and `examples/network-probe` were not touched. Runtime parent-relative bounds remain `vjParentFullH + vjParentFullV`. Einstein transport and `ap/apply.sh` were not changed.

### Preserved state and next boundary

All capture processes were stopped. `10.42.0.1/24` remains on loopback. The original raw server exited after the r11a timeout attempts; after confirming no process and no listener remained, exactly one replacement was started and left listening as PID 1102453 on `10.42.0.1:18081`.

The next boundary is why the new endpoint client's connect completion does not fire after a valid handshake. Do not revisit `Instantiate` argument order or Einstein transport: r11e proves both frame construction and the TCP path now reach a single established host socket. Compare the live completion event contract—not just its frame slots—with PT100's `MConnectCompProc`, or trace the ROM callback dispatch immediately after the handshake ACK.

## 2026-07-25 — Round 12: synchronous connect reached HTTP output

### Bottom line

The hard gate does **not** fully pass. r12a confirmed that synchronous `connect` must continue directly into `Connected`; r12b then sent the first real Loader HTTP request. Gate (a) and gate (b) pass, but gate (c) remains blocked by Einstein's `RemoveLinkClient` `-48803` overlay after the 6,567-byte response is received.

The final preserved diagnostic package is `-HarnessLoaderR12N:jbfly`, visible version `1.1-r12n`, SHA-256 `be42798fe89ed9c6ef69d9bf91a47eb81d2b0fe1aa737e66450bd584427a27c1`. Its receive callback is deliberately a no-op: the same overlay still appears, proving the remaining alert is independent of Loader callback code.

### Runtime evidence

- Gate (a) passes. `runtime/evidence/round12b-final-baseline.txt` records `capture_initial_bytes=0` and `podman logs --since 0s -f`. `runtime/evidence/round12b-final-runtime-relevant.txt` contains the fresh SYN with destination IP bytes `0a 2a 00 01`, destination port bytes `46 a1`, and decoded `dst=18081`.
- Gate (b) passes. `runtime/evidence/round12b-final-server-delta.txt` contains `RAW b'GET /harness-client.pkg HTTP/1.0\r\nHost: 10.42.0.1\r\nConnection: close\r\n\r\n'`, exactly matching `runtime/raw_pkg_server.py`.
- The capture also shows a 72-byte TCP payload containing that request and ACK progression through all 6,567 response bytes.
- Gate (c) fails. `runtime/evidence/round12b-r12n-after-run.png` visibly identifies r12n but is overlaid by Newton Internet Enabler event `RemoveLinkClient`, connected `InetManagerFSH`, `evt.ex.fr.intrp`, error `-48803`. Consolidated result: `runtime/evidence/round12b-gate-summary.txt`.

### Iterations and source result

- r12a removed the unreachable synchronous-connect completion callback and called `Connected(nil, nil)` after `connect` returned.
- r12b removed the runtime-undefined `MakeBinaryFromHex` helper and passed the ASCII request string to lowercase three-argument `output`; this produced the accepted GET.
- r12c corrected `Input` to zero arguments; the resulting `-54000` identified the missing active input script.
- r12d through r12f established the binary input-spec contract: `SetInputSpec`, a binary target frame `{data: VBO, offset: 0}`, and a termination count.
- r12g established the exact response size as 6,567 bytes (111-byte HTTP header plus 6,456-byte package) and the trace ACKed all bytes.
- r12h through r12m tested callback receiver, root-frame, package-copy, and status paths. The same `RemoveLinkClient` overlay remained.
- r12n reduced `InputScript` to `func(endpoint, data, result, error) nil`; the overlay still remained, isolating it from callback logic.

`examples/harness-client`, `examples/network-probe`, Einstein transport, and `ap/apply.sh` were not changed. Runtime parent-relative bounds remain `vjParentFullH + vjParentFullV`.

### Preserved state and next boundary

All capture processes are stopped. `10.42.0.1/24` remains on loopback. The temporary delayed-close test server was stopped, and exactly one original `runtime/raw_pkg_server.py` process is listening on `10.42.0.1:18081`.

The next boundary is the source of `InetReleaseLink` / `RemoveLinkClient` during active input completion. It occurs even with a no-op `InputScript` and while the test socket remains open, so do not continue tuning callback argument order or response parsing until that FSM event is traced.

## 2026-07-25 — Round 13A: late `Grabbed` guard did not remove `-48803`

### Bottom line

The proposed `Grabbed` ordering guard did **not** pass the hard gate. The uniquely identified package `-HarnessLoaderR13A:jbfly`, visible version `1.1-r13a`, SHA-256 `faca19baef84907d18f6b599901fff3d2df1bcf0c36403d72a562671b90e50d4`, still reaches the correct server and receives the complete response, but Newton again overlays the Loader with `RemoveLinkClient` in connected `inetManagerFSM`, error `-48803`.

Per the stop condition, no r13b receive-work restoration was made. A delayed-close control proves the alert occurs **before** the peer closes: it appeared at `23:21:50.676943937+01:00`, while the server held the socket open until `CLOSE_BEGIN` at `23:22:20.085923+01:00`, about 29.4 seconds later.

### Runtime evidence

- Identity hard check passes. `runtime/evidence/round13a-loader-open-hard-check.png` is a 320×480 Newton-screen capture visibly reading `- R13A Loader 1.1-r13a`; artifact identity and checksum are in `round13a-package-identity.txt` and `round13a-loader-package.sha256`.
- Gate (a) passes. `runtime/evidence/round13a-baseline.txt` records `capture_initial_bytes=0` and `podman logs --since 0s -f`. `round13a-runtime-relevant.txt` contains the fresh SYN with destination bytes `0a 2a 00 01`, port bytes `46 a1`, and decoded `dst=18081`.
- Gate (b) passes. `runtime/evidence/round13a-server-delta.txt` contains the exact 72-byte request `GET /harness-client.pkg HTTP/1.0\r\nHost: 10.42.0.1\r\nConnection: close\r\n\r\n`. The trace advances through `ack=6569`, covering all 6,567 response bytes.
- Gate (c) fails. `runtime/evidence/round13a-after-tap-6s.png` is a distinct 320×480 Newton-screen capture showing r13a beneath the `RemoveLinkClient` / `-48803` alert. Consolidated evidence is `runtime/evidence/round13a-gate-summary.txt`.
- The single delayed-close ordering result is `runtime/evidence/round13a-delayed-close-ordering.txt`, with the corresponding Newton-screen capture `round13a-delayed-close-alert.png`. `SEND_DONE` preceded the alert; `CLOSE_BEGIN` followed it by about 29.4 seconds.

### Source and preserved state

The only source change is the requested early `if self.endpoint then return nil` at the top of `Grabbed`, above error and `linkStatus` handling, plus the unique r13a identity in `Main.newt` and `harness-loader.nprj`. `examples/harness-client` and `examples/network-probe` were not touched.

All emulator-log captures are stopped. The temporary delayed-close copy lived under `/tmp` and exited; `runtime/raw_pkg_server.py` matched its pre-test SHA-256 afterward. Exactly one original raw package server is listening on `10.42.0.1:18081`, and `10.42.0.1/24` remains on loopback.

## 2026-07-25 — Round 14: `Grabbed` progress handling removed `-48803`

### Bottom line

The hard gate **passes** with `-HarnessLoaderR14G:jbfly`, visible version `1.1-r14g`, SHA-256 `f0eff73afeff5f9849dc79ddc4973a98dd4bb861f6cea9aa9b765d3116189a78`. Experiment 1 proved the alert was our call path: r14a visibly reported `FAILED: Install failed twice: Link: connecting` before `RemoveLinkClient/-48803`, and r14b exposed the earlier normal state `Link: initializing`. `Grabbed` was incorrectly sending ordinary NIE progress notifications to `Failed`, which called `Stop("Failed")` and then `InetReleaseLink`.

The fix is to ignore every non-error `Grabbed` state until `linkStatus = 'connected`. Experiment 2's link-layer deletion was therefore not run. With the call path fixed, the real receive callback copies the 6,456-byte package body from offset 111, queues installation, and visibly reports `Harness Client install queued` without the `RemoveLinkClient/-48803` overlay.

### Runtime evidence

- Identity hard check passes. `runtime/evidence/round14g-loader-open-hard-check.png` is a distinct 320×480 Newton-screen capture visibly reading `- R14G Loader 1.1-r14g`; checksum and exact chooser path are in `round14g-package-identity.txt` and `round14g-installer-exact-fullpath.png`.
- Gate (a) passes. `round14g-baseline.txt` records `capture_initial_bytes=0` and `podman logs --since 0s -f`. `round14g-runtime-relevant.txt` contains the fresh SYN to `0a 2a 00 01`, destination port `46 a1` / 18081.
- Gate (b) passes. `round14g-server-delta.txt` contains the exact 72-byte request `GET /harness-client.pkg HTTP/1.0\r\nHost: 10.42.0.1\r\nConnection: close\r\n\r\n`. The fresh trace records the 72-byte TCP payload and ACK progression through `ack=6569`, covering the complete 6,567-byte response.
- Gate (c) passes. `round14g-success.png` and the distinct `round14g-after-tap-4s.png` through `-6s.png` visibly show `Harness Client install queued` with `1.1-r14g` and no `RemoveLinkClient/-48803` overlay. Consolidated evidence is `round14-gate-summary.txt`.
- The later package notice identifies `HarnessClient:jbfly` and says it is already installed on Internal. That is expected in this preserved flash: r14d's restored callback had already passed the body to `SuckPackageFromBinary` while validating the receive path. `InstallBinaryLater` now uses NewtonOS `AddDelayedCall(..., 5000)` so the success state is visible before installation proceeds.

### Iterations and source result

- r14a added the requested `Stop(reason)` and `FAILED:` markers without changing behavior; it caught `Failed("Link: connecting")` before the overlay.
- r14b accepted `'connecting` but then caught `Failed("Link: initializing")`, proving all pre-connected states are normal progress.
- r14c changed `Grabbed` to return for every non-error state other than `'connected`; `RemoveLinkClient/-48803` disappeared while both transport gates continued to pass.
- r14d restored the receive work: copy 6,456 bytes from input-target offset 111, clear the VBO cache, call `InstallBinaryLater`, and set a clear success status. The first nested callback form triggered an old `tntk` compiler segfault and produced no package; moving the work into `InputReceived` compiled normally.
- r14e ignored the post-callback `evt.ex.comm` from `Input()` so it could no longer overwrite callback status. r14f/r14g calibrated the native delayed install from 300 ms to 5,000 ms, leaving a stable success-screen evidence window.

`examples/harness-client` and `examples/network-probe` were not changed. All emulator-log captures are stopped, the original raw package server remains the sole listener on `10.42.0.1:18081`, and `10.42.0.1/24` remains on loopback.

## 2026-07-26 — zero-click Einstein install and launch

### Bottom line

Einstein now accepts package-install and NewtonScript requests through a mode-`0600` Unix socket on its FLTK thread, and `emulator-control` forwards `POST /install` and `POST /newtonscript` to it with two-second timeouts. The new image is `localhost/newton-harness-dev:zeroclick` (ID `200a11722745cdbf192501e1b66a86074bc51a42345e7c4bd62c5b23e0b263fc`) and is running healthy.

### End-to-end result

- Built the Loader under fresh identity `-HarnessLoaderZC1:jbfly`, visible version `1.1-zc1`; package SHA-256 is `e0d9704144af3107ddb747bd2ff9f5041de3c3d0ac92f85e0bca5770c106984f` (`runtime/evidence/zeroclick-loader-identity.txt`, `zeroclick-loader-package.sha256`).
- `scripts/install-and-launch.sh /packages/harness-loader/harness-loader.pkg -HarnessLoaderZC1:jbfly` issued exactly one `curl` to each endpoint; both replies were `queued` (`zeroclick-control-replies.txt`). The Newton-only 320×480 proof capture is `zeroclick-loader-open.png`. No file picker, OCR, GUI install click, or launch tap was used.
- Starting the actual fetch still requires the Loader's button, so one simulated Newton-screen tap was used only after zero-click install and launch. This is the explicit exception allowed for this round.
- The packet capture began in a verified zero-byte file with `podman logs --since 0s -f` (`zeroclick-baseline.txt`). It records a fresh SYN to `10.42.0.1:18081`, including destination bytes `0a 2a 00 01 46 a1`; the package-server delta contains exactly `GET /harness-client.pkg HTTP/1.0\r\nHost: 10.42.0.1\r\nConnection: close\r\n\r\n` (`zeroclick-gate-summary.txt`, `zeroclick-server-delta.txt`). Round 14's transport gates therefore still pass.
- `containers/patches/einstein-control-socket.patch` applies to pinned Einstein commit `f5544a039fc3964e18b217ccffa030c6bf1e4044`, and the image build completed. The socket was verified at `/state/einstein-control.sock`, owned by `newton:newton` with mode `0600`; invalid install paths and multiline commands return HTTP 400. Existing Python tests remain green (7/7).

All temporary `podman logs -f` captures are stopped. The original package server remains the sole listener on `10.42.0.1:18081`; `examples/harness-client` and `examples/network-probe` were not touched.

## One-command test-round setup

Run `scripts/newton-round.sh <example-dir> <round-tag>` from anywhere in the repository, for example `scripts/newton-round.sh examples/harness-loader r15a`. It bumps both package identities, builds and verifies the package, starts a fresh emulator-log capture with a package-server baseline, installs and launches the app, and saves a Newton-screen screenshot after confirming the visible version with OCR. It deliberately does not tap the app's fetch button. The summary includes the capture PID and stop command; run `scripts/newton-round.sh --self-check` to check the identity rewrite without building or touching source.

## 2026-07-26 — Chat UI: five NewtonScript/tntk traps

Building the real chat UI (`examples/harness-client/Main.newt`) cost far more than the
layout did. Every one of these produced a bare `-48200` alert or a compiler crash with no
message, and each was isolated by installing a throwaway probe package and reading the
screen. Evidence: `runtime/evidence/final-summary.txt`.

1. **tntk segfaults on a top-level constant referenced inside a function body.**
   `kCap := 6144; ... F: func() kCap` crashes the compiler; a view slot holding the same
   constant (`cap: kCap` then `self.cap`) compiles. No diagnostic, just SIGSEGV.
2. **NewtonScript symbols are case-insensitive, so a slot shadows a method.** A slot named
   `transcriptTail` made `:TranscriptTail()` call a number: `-48200`. Slots are now
   `capBytes` / `tailBytes`.
3. **A child view cannot reach its parent during setup.** `self:Parent()` inside a child's
   `ViewSetupDoneScript` throws `-48200`, and custom marker slots (`role: 'status`) do not
   survive instantiation — verified directly on screen. `:ChildViewFrames()` works, but
   only *after* the view is open, so wiring happens in a delayed `Boot`. A live view also
   has no readable `viewBounds` slot; reading it throws. Index order is the float's own
   close box first, then template order: 1 title, 2 transcript, 3 divider, 4 prompt,
   5 status, then the buttons.
4. **A live paragraph rejects an empty string.** `SetValue(view, 'text, "")` throws
   `-48200`, and a paragraph whose template `text` starts empty cannot be set later. The
   transcript therefore ships with hint text and falls back to it when the conversation is
   empty; clearing the prompt is wrapped in `try ... onexception |evt.ex| do nil`.
5. **`GetRichString()` throws on this ROM's input line** (an instrumented build caught the
   throw exactly there). Reading `field.text` gets past that call but Send still fails —
   see the open defect in the summary.

Two operational notes: `tntk` hardcodes package version 1
(`~/newton-dev/tntk/package.cpp:161`), so Newton rejects any same-name reinstall as
"already installed" — that, not the identity string, is the real replace trap, and
`SafeRemovePackage(GetPkgRef(...))` over the control API did not clear it. And an
accumulation of open apps holding NIE links wedges the link layer until every connect
returns `-16013`; restarting the emulator container clears it.

## 2026-08-03 — Track C1–C3 round: three ops proven by evaluation, not by link

Isolated instance `c1round` (`make emulator-instance-up INSTANCE=c1round`,
control `http://127.0.0.1:55225`), `HarnessToolsR10M:jbfly` built and installed.
The `POST /tools` acceptance round did **not** run — `10.42.0.1/24` never
appeared on `lo`, and that address is hardcoded in the client
(`examples/harness-tools/Main.newt:72`) and bound literally by the broker. So the
three new ops' NewtonScript was evaluated directly through `runtime/ns_eval.py`
instead, which proves every system call on the 717006 ROM while leaving the
transport unproven. `battery` → `count=0 cap=100% charge=discharging ac=no
type=nimh`; `store_info` → `Internal total=7638048 used=599716 free=7038332
ro=n`; `GetPackages()` → 32 packages, ordinal 1 `1/32 ScreenBuffer|428|?`,
ordinal 32 `32/32 NIE Ethernet Module|74888|Internal`. Evidence:
`runtime/evidence/toolsround-r10m-nseval.txt`,
`runtime/evidence/toolsround-r10m-status.txt`,
`runtime/evidence/toolsround-r10m-screen.png`.

Four things worth carrying forward:

1. **`BatteryCount()` returns `0` on Einstein** even though `BatteryStatus(0)`
   returns a fully populated frame. Never gate a status read on the count.
2. **A package's `store` slot can be `nil`** — `GetPackages()[0]` here is
   `ScreenBuffer` with `store` and `pssid` and `copyProtection` all nil, so an
   unguarded `pkg.store:GetName()` throws on the very first ordinal.
3. **A fresh instance is not network-ready.** `make emulator-instance-up` gives a
   blank flash: the ROM boots into the first-run Welcome tour, and while that
   tour is up a `protoFloatNGo` app will not show even though `:Open()` returns
   `TRUE` and `GetRoot().|sym|` is a frame. Click the tour through to the Notepad
   first. None of `runtime/nie2/` is installed either, so there is no Ethernet
   driver and no saved Internet Setup for `InetGrabLink` (which *is* in ROM) to
   use.
4. **`newtdev.pkg` must be installed before `NE2K.pkg`**, or the driver installs
   but refuses to activate: "Unable to activate NE2K since Newton Device Drivers
   are not in the system", followed by `-48807` on the next boot. Also,
   `POST /install` only accepts container paths under `/packages/`
   (`containers/patches/einstein-control-socket.patch:119-124`), which is the
   read-only `examples/` mount — the `nie2` packages have to be staged there.

## 2026-08-03 — Track C1–C3 wire round: the three ops travelled the link

The round the entry above could not finish. `10.42.0.1/24` was on `lo` this
time, so `python3 runtime/raw_pkg_server.py` came up on `10.42.0.1:18081` and
the whole thing ran end to end on a fresh isolated instance `c2round`
(control `http://127.0.0.1:42165`).

**The network setup took 90 seconds, not an afternoon.** Point 3 of the entry
above — tour, `newtdev`, `NE2K`, Internet Setup by hand — was skipped entirely
by seeding the instance's flash. Bring the instance up so the `emulator-state`
volume exists, `podman stop` it, `podman cp` a saved NIE-configured flash over
`/state/internal.flash`, `podman start`. The seed used was
`~/newton-archive/newton-harness/flash-backups/internal-before-round9-loader-20260725-195622.flash`,
picked because `strings -a … | grep -c NE2K` → 4 and
`strings -el … | grep -ci 'Untitled Ethernet'` → 3, and because it carries no
HarnessTools package to compete for the broker's single poll slot. It booted
straight into the Notepad with the `PCMCIA Ethernet` card slip up. Full recipe
in `docs/parallel-emulators.md`. Do **not** use
`runtime/emulators/mp2000-core-20260803/internal.flash` — it has zero `NE2K`
hits; it is a Dock-restored core baseline, not a network image.

After `scripts/install-and-launch.sh /packages/harness-tools/harness-tools.pkg`
the broker logged `Newton tools connected 10.42.0.1:33744` about 15 seconds
later, and every op answered in **~0.8 s** (`ping` 0.05 s when a poll is already
parked). Replies, all in `runtime/evidence/toolsround-r10m-wire-*.txt`:

```
ping            "pong"                                                  200  0.053 s
battery         "count=0 cap=100% charge=discharging ac=no type=nimh"    200  0.817 s
store_info      "Internal total=7638048 used=883236 free=6754812 ro=n"   200  0.823 s
pkg_list        "count=39"                                              200  0.825 s
pkg_list id=1   "1/39 ScreenBuffer|428|?"                               200  0.856 s
pkg_list id=39  "39/39 PT100:Scrawl|174416|Internal"                    200  0.814 s
pkg_list id=99  error "package ordinal must be 1..39"                   422  0.744 s
```

Four things worth carrying forward:

1. **The wire found a bug `ns_eval` could not.** `R10M`'s `pkg_list` returned
   `evt.ex.fr.type;type.ref.frame` for every valid ordinal
   (`…-wire-pkg-list-1-r10m-bug.txt`) while `:PkgEntry(1, 38)` under `ns_eval`
   returned the right string. Cause: `StringToNumber("1")` is a **`Real`** on
   this ROM, and `packages[1.0 - 1]` throws that frame-type exception rather
   than anything index-shaped. `ns_eval` hands the op an integer literal; the
   wire hands it a string token. Fixed with one `Floor` at the dispatch site and
   shipped as `HarnessToolsR10N:jbfly`. `get_note` was never affected only
   because it uses `for position := 1 to ordinal` instead of an array index.
2. **`GetPackages()` order is not stable across a reboot.** Ordinal 38 was
   `HarnessToolsR10M` before a `podman restart` and ordinal 39 was
   `PT100:Scrawl` after. The ordinal is a paging cursor, never an identifier.
3. **A closed tools client keeps fighting.** Closing `R10M`'s float with
   `:Close()` (which returned `TRUE`) did not stop its endpoint from retrying,
   and it raised modal `Communications — Sorry, a problem has occurred.
   (Connection may have been dropped.)` alerts over the Notepad while `R10N`
   was answering fine. `podman restart` on the container cleared it — the same
   remedy as the wedged-NIE-link note in the previous entry.
4. **Do not use "I can see the float" as the liveness test.** On this flash the
   `protoFloatNGo` window never painted, while `Visible()` was `TRUE`,
   `viewCObject` non-nil, `viewBounds` the expected `220,34,316,72`, and
   `:Dirty()` + `RefreshViews()` changed nothing — and it answered every
   request. The broker's `Newton tools connected` line is the real signal. The
   round's screenshot is the Extras drawer instead
   (`runtime/evidence/toolsround-r10m-wire-screen.png`), which incidentally
   shows the seeded flash's whole NIE stack: `NE2K`, `Newton Devices`,
   `Newton Internet`, `NIE Ethernet`, `Internet Setup`, `PT100`.

## 2026-08-03 — Track D3: the agent behind chat calls the Newton's tools

The keystone round. A prompt typed on an emulated Newton reached `codex`, the
model called `newton_tool` three times through `newton_mcp.py`, and the answer
rendered in the Newton's own chat transcript with the device's real numbers.
Nineteen seconds end to end. Full page: `docs/agent-tools.md`, "The live demo
(D3)"; evidence `runtime/evidence/d3demo-*`.

```
You:   use your newton tools. what app is in front, how much free
       space, and how many packages are installed.
Agent: Front app: Notepad (paperroll)
       Free space: 6,758,976 bytes (6.45 MiB)
       Installed packages: 39
```

Setup was the cheap path throughout: a fresh instance `d3demo`, flash seeded
from `internal-before-round9-loader-20260725-195622.flash` (~90 s, the
`docs/parallel-emulators.md` recipe — it works exactly as written, PCMCIA
Ethernet slip and all), then `HarnessToolsR10N` and `HarnessClientA3` installed
over `POST /install` and opened with one `ns_eval` `:Open()` each.

Six things worth carrying forward:

1. **`codex exec` does not auto-approve MCP tool calls, and the failure is
   disguised.** The tool call is *attempted* and comes back
   `"error": {"message": "user cancelled MCP tool call"}` — no human, no
   approval, auto-decline. Nothing in the output says "approval". The cure is
   `default_tools_approval_mode = "approve"` in the server's config block;
   `codex mcp add` has no flag for it, so it is a hand-edit (or the new step in
   `make server-mcp`). Valid values are `auto`, `prompt`, `writes`, `approve`,
   which is knowable only from codex's rejection message for a bad one.
2. **`--sandbox read-only` does not reach the MCP server subprocess.** Under
   that flag, `build_pkg` ran `make` and wrote a real `.pkg`. Good news for
   `build_pkg`/`stage_hw`; a standing warning otherwise, because it means the
   sandbox is not a rail here. The only rails on this surface are the ones
   coded into `newton_mcp.py`.
3. **`HarnessClientA3` needed no rebuild to talk to a host `server.py`.** Its
   hardcoded `serverAddress: [10, 42, 0, 1]` / `serverPort: 6801` lands on the
   host's `lo` alias exactly like the tools long-poll does. Run `server.py`
   with plain `python3` on the host — that is the shape the container
   networking finding calls for, and it is now proven, not just recommended.
4. **The model batched the three tool calls through code mode.** It emitted one
   `exec` script doing `await Promise.all([tools.mcp__newton__newton_tool(…) ×3])`
   rather than three tool turns. The tools are re-exported into that sandbox as
   `mcp__<server>__<tool>`, and the parallel calls serialised fine on the
   broker's single poll slot.
5. **Two NIE clients on one Newton is noisy but works.** Mid-turn the broker
   logged one `Newton tools disconnected` / `connected`, and a modal
   `Communications — Sorry, a problem has occurred` slip appeared *over the
   chat window*. The turn completed correctly; the slip has a close box. Same
   family as the closed-client alerts in the previous entry — expect it.
6. **`xdotool` typing into a Newton field is lossy.** The first attempt lost
   the leading `Use ` and turned `:` into `;` and `?` into `/`. Tap the field,
   wait ~3 s, then send short chunks with a pause between them. Check the
   screenshot before tapping Send.

## 2026-08-03 — Track C4: `note_list`, and `get_note` grows a guard

`HarnessToolsR10P:jbfly`. Isolated instance `c4round`, flash seeded from
`internal-before-round9-loader-20260725-195622.flash`, broker
`runtime/raw_pkg_server.py` on `10.42.0.1:18081`, which logged
`Newton tools connected 10.42.0.1:57652`. Fourteen `POST /tools` calls, all
answered; transcripts `runtime/evidence/c4round-*.txt`, summary
`c4round-wire-summary.txt`, ROM probes `c4round-nseval.txt`, screenshot
`c4round-screen.png`. Full page: `docs/newtonscript-eval.md`, fifteenth finding.

```
{"op":"note_list"}                   -> "count=6"
{"op":"note_list","args":{"id":4}}   -> "4/6 C4 alpha note about batteries|64477198"
{"op":"note_list","args":{"id":6}}   -> "6/6 C4 charlie note that is delibera...|64477198"
{"op":"note_list","args":{"id":7}}   -> 422 "note ordinal must be 1..6"
{"op":"get_note","args":{"id":6}}    -> the whole 89-character note
```

Five things worth carrying forward:

1. **`cursor:CountEntries()` exists and works on this ROM** — `n=3` on the
   seeded Notepad, matching the manual cursor walk. It is how `note_list`
   answers `count=`, and unlike R10I's full-soup scan it walks the index rather
   than reading entries, so it does not reintroduce the twelfth finding's
   event-loop starvation. `refs/NewtonProgrammerRef20.txt:34215-34243`.
2. **A Notepad entry with no title is the normal case.** Every entry in the
   seed flash had `title` = nil (`ClassOf` → `weird_immediate`), so a listing
   that printed `title` unguarded would print nothing useful for almost every
   real note. `note_list` falls back to the note's first 32 characters, and
   `(untitled)` only when there is no text either.
3. **`ns_eval` cannot see NTK platform constants, and the error blames the
   wrong thing.** `store:HasSoup(ROM_paperRollSoupName)` through `ns_eval`
   throws `evt.ex.fr.intrp;type.ref.frame`; the constant is resolved at
   *compile* time out of `~/newton-dev/ntk-platform-files`, and injected script
   is never compiled by NTK, so the name is unbound and `HasSoup(nil)` throws.
   `GetSoupNames()` proves the literal is `"Notes"`. Probe with literals, ship
   the constant. Second known `ns_eval`-vs-wire divergence after the fourteenth
   finding's string arguments.
4. **The seed flash's three notes are the old failed writes.** All three have
   `data` = nil — the exact garbage shape `docs/notes-bridge.md` diagnosed as
   N2/N3 entry 4, carried along by the snapshot ever since. They are why
   `get_note(1)` legitimately returns `""`. Anything proving note *content*
   must create its own notes first; the sanctioned two-step
   (`notes:NewNote(notes:MakeTextNote(text, nil), nil, nil)`) worked first try
   through `ns_eval` here, three times, each confirmed by the count going
   3 → 4 → 5 → 6 and by all three rendering in stock Notepad.
5. **The seeded flash can boot with stacked `-48807` / `-48601` NIE alerts.**
   They queue up behind the PCMCIA Ethernet card slip before any broker is
   listening. Tap the close box repeatedly until they are gone, then dismiss
   the card slip; the link came up normally afterwards. Not a fault — do not
   go debugging the driver over it.

## 2026-08-03 — Track F1: multi-frame prompts, and the `StrPos` trap they exposed

A prompt longer than one frame now leaves the Newton as `MSGP` parts, and the
host reassembles it. On isolated instance `f1round` (flash seeded per
`docs/parallel-emulators.md`) against `NEWTON_FAKE_BACKEND=1 python3 server.py`
on `10.42.0.1:6801`, a 378-character prompt typed into `Chat A4 2.4-a4` went out
as two parts and came back as a rendered 453-character reply:

```
MSGP part 1/2 220B total=220B
MSGP part 2/2 158B total=378B
MSGP assembled 2 parts into 378B prompt
```

Evidence: `runtime/evidence/f1round-round.txt` (full round record),
`runtime/evidence/f1round-12-reply.png` (reply on the Newton screen),
`runtime/evidence/f1round-13-short-msg.png` (a short prompt right after it,
which logged no `MSGP` line at all — it still goes as a plain `MSG`).
Grammar and host state machine: `docs/phase3-protocol.md`, "Extension: `MSGP`".

Three things worth carrying forward:

1. **`StrPos(text, Chr(13), 0)` raises `-48802` on this ROM.** The first
   attempt assembled the prompt correctly, ACKed every host frame including
   `PROMPT` (proved in the Einstein `TCPDIAG` payloads,
   `runtime/evidence/f1round-einstein.log`), and then froze under
   `Sorry, a problem has occurred (-48802)` with the reply invisible. The
   client's own slots located it: `responseText` was 453 characters and
   `transcript` 846, but `ready`/`inFlight` were untouched — so it died inside
   `ShowTranscript` → `TranscriptTail`, whose only remaining call was the
   newline search. `StrPos` with a *printable* needle works on the same string
   (`StrPos(transcript, "Agent:", 0)` → 384) and `Ord(transcript[383])` → 13,
   so the indexing is fine; it is the control-character needle that throws.
   `Chr(10)` throws too. Every probe ran with a `2+2` → `4` sanity eval
   immediately before it, because a stray modal alert makes `ns_eval` time out
   and look like the same failure. Fix: `FindBreak(text, from)` scans with
   `Ord`. This was a **pre-existing A3 bug** — A3 simply never had a transcript
   over the 640-character tail threshold.
2. **`-48802` is not in the interpreter-error table.**
   `refs/NewtonProgrammerRef20.txt:74796-74840` lists `-48800`, `-48803`,
   `-48804`, `-48806`…`-48811` and skips `-48801`/`-48802`. Do not spend time
   looking it up; treat it as "the interpreter threw" and bisect.
3. **The wire is not the app.** Everything the host logs can be perfect while
   the Newton shows nothing. When that happens, read the running view's slots
   through `ns_eval` (`GetRoot().|HarnessClientA4:jbfly|.responseText`) — the
   partially-updated state names the statement that threw.

`scripts/newton-round.sh` now also bumps an optional `kAppLabel`, and its
`kAppTitle` pattern finally matches this package (A3's title carried no tag, so
the script could not have bumped the chat client at all).

## 2026-08-03 — Track G: an agent built a Newton app from scratch, first try

The dev loop is written down (`docs/agent-dev-loop.md`, G1) and an agent has
now run it (G2). Instance `gloop`, isolated and flash-seeded per
`docs/parallel-emulators.md`; no broker, no `server.py`, no NIE — this loop is
`build_pkg` plus the emulator control API and nothing else.

One `codex exec` invocation (codex-cli 0.146.0, host, `--sandbox
workspace-write`, MCP server `newton` with `default_tools_approval_mode =
"approve"`) was told to build "NewtonDice": identity `Dice1:jbfly`, a floating
window with a **Roll** button that shows a random 1–6, scaffolded into a new
`examples/dice`, on instance `gloop`, using the MCP tools. It read
`docs/agent-dev-loop.md` first, then did steps 3–8 with **six MCP calls, zero
failures and zero interventions**: `build_pkg` → `emulator_install` →
`emulator_newtonscript` → `emulator_screen` → `emulator_tap(220,218)` →
`emulator_screen`. First build compiled. Full call log and codex's own report:
`runtime/evidence/gloop-codex-transcript.txt`; its two screenshots (decoded from
the run's JSONL) are `gloop-02-codex-launched.png` (`-` and a **Roll** button)
and `gloop-03-codex-after-tap.png` (`1`).

The app is 38 lines (`examples/dice/Main.newt`). The one piece of NewtonScript
worth stealing is how it keeps a handle on the view it updates:

```newtonscript
ViewSetupDoneScript: func()
begin
    inherited:?ViewSetupDoneScript();
    self:Parent().valueView := self;
end,
...
Roll: func() SetValue(self.valueView, 'text, "" & Random(1, 6)),
```

Two findings from verifying it:

1. **A `protoFloatNGo`'s rendered x position does not follow its `viewBounds`.**
   Declared `left: 60`, rendered at `x=112` — right edge 8 px inside the 320-px
   screen. The *vertical* numbers matched exactly (button declared at absolute
   y 200–236, measured 198–237). Pixel scan and method in
   `runtime/evidence/gloop-verify-rolls.txt`. So: take tap coordinates off a
   screenshot, never off the source. codex did that on its own — it screenshot
   first and only then chose (220, 218), which is the button's true centre.
2. **Two screenshots are not proof of a die.** The supervising session tapped
   Roll six more times with plain `curl` against the control port: `1 3 2 3 3 1`
   — inside 1–6 and changing, so `Random(1, 6)` really runs per tap
   (`gloop-verify-roll1..6.png`).

Operational notes. The `hello` scaffold ships a built `hello.pkg`; `cp -r` drags
it along and it must be removed — the runbook's step 3 says so, and codex still
listed it as the one thing that surprised it, which is a fair sign the scaffold
should probably not carry a built artifact at all.
`scripts/newton-round.sh` was **not** usable for a new app on an
isolated instance: it drove the shared container `newton-harness_emulator_1`,
and its bumper needs a `kVersion := "<base>-<tag>";` shape the `hello` scaffold
does not have. **Half of that is fixed as of Track F2**: the script now reads
`NEWTON_INSTANCE`, derives the container name and the control URL from it, and
runs entirely against an isolated instance. The `kVersion` shape requirement
stands, so for a *new* app you still edit `Main.newt` and the `.nprj` by hand
and repeat the loop.

---

## 2026-08-03 — Track F2: the harness panel, and three "proven" bugs

`Ask Note`, `Save Note` and an `Ink` overlay folded into the chat client, which
retires `examples/note-export` and `examples/ink-capture`. The shipped package
is `HarnessClientA7:jbfly` ("Chat A7", v2.4-a7) and not A5, because the round
spent one identity per defect. Full record and evidence index:
`runtime/evidence/f2round-round.txt`; instance `f2round`, seeded flash,
`NEWTON_FAKE_BACKEND=1 server.py` on 6801 and `pkg_publisher.py` on 18081.

What works, with its evidence:

```
MSGP part 1/2 220B total=220B          266-character note, one "Ask Note" tap
MSGP part 2/2 46B total=266B
MSGP assembled 2 parts into 266B prompt
```

`f2round-17-a7-asknote.png` (reply in the transcript), `f2round-18-a7-savenote.png`
(`Saved note id=8`, matching an independent `ns_eval` read of the soup),
`f2round-12-notepad.png` (source note and created reply note in stock Notepad),
`f2round-16-ink-reply.png` (`Ink: An L-shaped right angle.` from the real
vision call), `f2round-19-short-prompt.png` (short prompt, and the host logged
no `MSGP` line at all for that turn).

Three defects, each in code an earlier round called proven, each costing a
rebuild:

1. **`cursor:ResetToEnd()` lands *on* the last entry and returns it.** So
   `note-export`'s `ResetToEnd(); Prev()` reads the **second** newest note.
   Measured on a soup holding `0 1 2 3`:
   `local a := c:ResetToEnd(); local b := c:Entry();` → `"reset=3 entry=3"`,
   while `c:Prev()` gave `2`. On screen it looked like two unrelated bugs — the
   note reader said `Newest note has no text` (it had read a `data=nil` seed
   entry) and the create readback said `Saved note id=3` for an entry that was
   really `id=4`. Fix: `local entry := cursor:ResetToEnd();`. Written up in
   `docs/notes-bridge.md`, "Correction (F2)".
2. **Do not drop the NIE link to make a second connection.** The first build
   called `:Stop()` before the ink POST and grabbed a fresh link; `connect` then
   failed with `-16009` — *"Phone connection was cut off, or invalid call when
   not connected"* (`refs/NewtonProgrammerRef20.txt:73102`). Two endpoints on
   the one link the chat already holds works, and the chat session survives the
   drawing.
3. **A slot named `inkOpen` shadowed the method `InkOpen`** → `-48200` on every
   ink Send, before anything reached the wire. This is the `transcriptTail`
   trap from the A2 round, second occurrence; symbols are case-insensitive and
   the compiler says nothing. The slot was write-only, so it was deleted.

Three view mechanics worth keeping:

- **`Show()` only works on a view that was opened and then hidden**
  (`refs/NewtonProgrammerRef20.txt:4650-4652`). A `stepChildren` overlay
  therefore ships `vVisible` and is hidden by a delayed call at launch; there is
  no way to declare it hidden and message it later.
- **`vfFillWhite` is what makes an overlay opaque**, and **`vfFrameBlack` alone
  draws no frame** — the frame pen width is zero without `vfPen`. Two
  `protoDivider` rules are the cheap way to outline a writing area.
- Grandchild views reach the app through `self:Parent():Parent()`, and the
  panel's own children are wired by geometry relative to the panel's
  `GlobalBox()`, the same trick `Wire()` uses one level up.

And one process note, twice over: a stray `-48601` (Syntax error) and `-8007`
(Exception not handled) alert each appeared over the running app during the
round, both from a malformed `ns_eval` or a closed view's pending delayed call
rather than from the app under test — and each one sat exactly where the next
tap was going. Screenshot before every tap sequence, and run a `2+2` sanity eval
before believing an `ns_eval` timeout, per the F1 round.

## Track F4 round — slash commands from the Newton (2026-08-03)

Isolated instance `f4round`, seeded flash, Chat A7 installed from the
**committed** package bytes (`git show HEAD:examples/harness-client/harness-client.pkg`,
37,264 B) — this round changed no NewtonScript at all. Everything it proves is
host-side, which is the point: `/help`, `/status`, `/model`, `/effort`,
`/sessions`, `/new [name]` and `/resume <n|name>` are answered in `server.py`
before the backend runs, as ordinary `TEXT` frames, so **hardware Chat A3 has
them without a rebuild**. Full record `runtime/evidence/f4round-round.txt`; the
page is `docs/chat-commands.md`.

**The defect this round found is in shipped client code.** `/sessions` first
came back on screen as a bare `3.` where it should have read `3.*demo 0t now`.
`examples/harness-client/Main.newt:432` is

```
local star := StrPos(line, "*", 0);
```

— the **first** `*` in the frame is taken as the checksum delimiter, and the
payload is sliced up to it. The frame still ACKs, so the loss is silent. The
host's own `parse_frame` uses the last `*` and `docs/phase3-protocol.md`
explicitly allows `*` inside a payload, so this is a client limitation, and A3
carries the same code. The fix is a host-side rule — **no reply the server
builds may contain `*`** — implemented as a `>` marker and a `*`-stripping
`snippet()`, pinned by two tests. Anyone adding a host reply should know it.

Three operational notes, all cheap to lose an hour to:

- **Chat A7's prompt field only takes typed text when the tap lands on a ruled
  line.** A tap at `150,285` (between lines) focuses nothing, `xdotool` typing
  goes nowhere, and Send answers `Type a prompt first` — which reads like a
  protocol failure. `100,272` works.
- **The transcript renders top-down and clips**, and the Newton's global scroll
  arrows do not scroll it. For a readable screenshot of reply number six, tap
  **New** first; that also exercises bare `/new`, which is why bare `/new` on an
  untouched session resets in place instead of appending an empty registry row.
- **After the host server restarts, the first Send only reconnects.** Tap Send
  a second time to actually deliver the line still sitting in the field.

And one accident worth more than the fixture it replaced: the state directory
still held the **Track D3 round's** pre-F4 `state/session.json`, so the first
start migrated real data — thread `019fc923-c03a-7fd3-b7c7-4fe1670ebd77`, one
turn, name taken from D3's own prompt
(`runtime/evidence/f4round-registry-after-migration.json`). The real-backend
spot check then resumed that same thread with a model chosen on the Newton, and
its codex rollout now reads `gpt-5.6-sol/high` for the D3 turn and
`gpt-5.4-mini/low` for this one.
