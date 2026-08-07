# Newton Harness client and loader notes

## Current source state

- `examples/harness-loader/Main.newt` is the NewtonOS 2.1 package installer. The user enters a staged `.pkg` filename; it opens an NIE link, connects to `10.42.0.1:18081`, downloads that name with HTTP/1.0, validates a `Content-Length` from 1 to 524,288 bytes, stores the exact body in a VBO, and installs it with `SuckPackageFromBinary`.
- `examples/harness-client/Main.newt` is **Egg Freckles 1.0-ef19** with package identity `EggFrecklesEF19:jbfly` (package version 31). EF19 fixes EF18's Convert-to-Text regression: `StampInkTime` used the two-argument `StrPos(body, marker)`, which raises the literal wrong-argument error `-48803` on NewtonOS 2.1 while building the first body, before any `/ink` POST. It now supplies the required start offset, `StrPos(body, marker, 0)`. Emulator bisect proved the `T` header was the trigger (unchanged EF18: 0 POSTs/-48803; progress disabled: 0 POSTs/-48803; header disabled: 8/8 POSTs), and the final EF19 UI run kept the progress view plus all eight `INKTIME` headers with eight HTTP 200 responses and no -48803 (`docs/ef19-convert-regression.md`; `runtime/evidence/ef19-final-publisher.log`). EF14 radio ownership, EF15 UI, EF16 refresh, EF17 encoder rollback, endpoint-dispose-before-release guard, callback armor, and bind retry are unchanged. Physical MP2000 validation remains human-gated.
- `pkg_publisher.py` is the source-level reference server for `/egg-freckles.pkg` and `/status`. It still answers the old `/harness-client.pkg` path as an alias (`pkg_publisher.py:482-487`) so a loader with the old filename typed in keeps working. The separate live raw server is operational runtime state, not part of this build path.
- Each app has a `.nprj` file and a small Makefile that invokes tntk against the Newton 2.1 platform file.

## Reproducible build

From the repository root:

```sh
make newton-packages
```

This builds both projects and writes install candidates to:

```text
runtime/staging/harness-loader.pkg
runtime/staging/egg-freckles.pkg
runtime/staging/SHA256SUMS
```

The defaults use the local toolchain under `~/newton-dev`. Override the existing per-project Make variables when needed:

```sh
make newton-packages \
  TNTK=/usr/local/bin/tntk \
  PLATFORMS=/platforms
```

`tntk` embeds its current Newton epoch time at package bytes 32 through 35, so otherwise identical builds have different hashes. The top-level target replaces that one big-endian timestamp with `NEWTON_SOURCE_DATE_EPOCH + 2082844800` (Unix-to-Newton epoch offset). The default Unix epoch is `1767225600` (`2026-01-01T00:00:00Z`). Set `NEWTON_SOURCE_DATE_EPOCH` to another stable Unix timestamp if release policy requires it.

## Package and compiler gotchas

- A Newton package starts with `package0`. The reproducible target checks this magic and minimum header length before changing the timestamp.
- A distinct build must receive a fresh `.nprj` `name` and matching `appSymbol`; changing only the package version does not permit replacement. The exact same verified binary may of course be installed on multiple devices. Loader and client identities remain separate.
- The project platform string is exactly `Newton 2.1`, and tntk's `-P` argument names the directory containing that platform file, not the file itself.
- tntk's generated package changes only at the package timestamp for identical source in the currently pinned toolchain. If a future tntk changes other bytes, the two-build hash check should fail rather than expanding normalization casually.
- NewtonScript method names may print with different capitalization in tntk's diagnostic dump (`Stop` appears as `stop`); that is normal symbol behavior.
- Keep device strings ASCII and responses small. The chat client caps each wire frame at 240 bytes and retains at most 6 KiB of transcript.
- The chat input path is `SetInputSpec`-only. Bind, connect, handshake, ACK, and message outputs use `async: true`; every output explicitly uses `form: 'string`.

## `SuckPackageFromBinary`

The loader allocates a package VBO with:

```newtonscript
GetDefaultStore():NewVBO('package, contentLength)
```

It copies response bytes into that VBO with `BinaryMunger` and only installs after the exact advertised body length arrives. `ClearVBOCache` is not a NewtonOS 2.1 global and must not be called. Installation is delayed until after the endpoint receive callback returns:

```newtonscript
AddDelayedCall(
    func(theBinary)
        GetDefaultStore():SuckPackageFromBinary(theBinary, nil),
    [binary],
    5000);
```

Deferring matters: package installation can alter application state, so it should not run inside the endpoint receive stack. Keep the binary referenced until the deferred call runs. The current install exception is intentionally contained because there is no safe UI reference in that deferred function; a later version can report install completion through a persistent status slip.

## Loader and client behavior

Loader ZC40 v2.4 shows its version, accepts a name-only `.pkg` filename, reports fetch/install progress on its large button, and performs one deferred retry after a link, TCP, HTTP, allocation, or length failure. The removed LAN/Mars toggle bought enough package space for the fix; ZC40 always connects to `10.42.0.1`. Filenames are limited to ASCII letters, digits, `-`, `_`, and `.`, and must end in `.pkg`; no directory-listing protocol was added. ZC40 also sets `installQueued` before deferring installation, so a repeated final input callback cannot schedule the same binary twice; only a genuinely new `TryFetch` resets that guard.

Output is asynchronous and explicitly uses `form: 'string`; its completion script reports send failure. Input remains `'binary` for the complete HTTP response. The first 1,024-byte target contains the header and initial body bytes; `HeaderReceived` copies that body suffix with `BinaryMunger`, then installs binary body specs at advancing VBO offsets. For the 82-byte-header / 18,320-byte-body hardware case, the offsets are 942, 9,134, 17,326, and 18,320.

An input spec normally persists after `InputScript`: Newton automatically reposts the same spec. Calling `SetInputSpec` inline is needed only to change or stop it (and to repost one-shot options), not before every callback. Evidence: `refs/NewtonProgrammerGuide20.txt:50167-50178,50543-50547` and `refs/NewtonProgrammerRef20.txt:56549-56557`. ZC39 changes specs inline because each binary target offset and final chunk count differ; it never calls synchronous `Input()`. The NIE handling and ZC38 teardown re-entry guard remain unchanged.

The emulator acceptance run downloaded the staged `inetenbl.pkg` at 318,276 bytes and opened its live `PCMCIA Ethernet` / `NE2000` configuration UI after installation. During a repeat large transfer, the Newton opened `AllIcons` while `ss -tnp` still showed the sole client connection to `10.42.0.1:18081` in `ESTAB`, demonstrating that the event loop remained responsive. The physical Newton was not used.

For ZC39, the one-shot `scripts/verify-loader-download.py` check served the exact 82-byte header plus 18,320-byte `harness-tools.pkg` body. Both unchanged ZC38 and fixed ZC39 ACKed all 18,402 bytes in the private emulator, so Einstein did not reproduce the hardware-only 2,920-byte stall. ZC39 parsed 18,320 and reached `SuckPackageFromBinary`; the copied flash then rejected the already-present package identity. Evidence: `runtime/evidence/zc39-baseline-ack.txt` and `runtime/evidence/zc39-fixed-ack.txt`.

Physical hardware proved the complete WiFi path with fresh packages. ZC40 installed and launched a 1,136-byte proof, then installed and launched a 321,920-byte proof; Mars logged one GET for the large success and TCP ACKs for all 322,003 HTTP response bytes. The first large attempt reached installation but failed with Newton error `-10617` (card memory full); freeing the `Ultimate Newton` flash card from 498 KB to 893 KB made the unchanged package succeed. Allow roughly twice the package size for the download VBO plus installation copy.

The earlier same-name warning followed a real retry: Mars logged a first partial transfer and a second complete GET. ZC40's `installQueued` guard remains cheap protection against repeated final callbacks, but duplicate callback scheduling was not the cause observed on hardware. Its post-install `GetPkgRef` check can still display `Install not confirmed` even when a package installs and launches, so treat that text as a status-check defect rather than transfer failure.

Newton Chat 2.1-a1 uses the unchanged Phase 3 framed protocol. On 2026-08-02
an isolated configured Einstein flash connected through one TCP session, sent
`Reply with exactly A1 ASYNC OK`, rendered `Agent: A1 ASYNC OK`, cleared the
in-flight state, and returned to `Ready`. Its production address remains
`10.42.0.1:6801`; the address is a view slot so an isolated emulator can point
at its rootless-container host without rebuilding or reusing the identity.

On the physical MP2000, the A1 package appears in Extras with the short caption
**Newton Chat**, not **Newton Chat 2.1-a1**. Opening it shows the full window
title **Newton Chat 2.1-a1**, which is the reliable on-device version check.
Do not assume an Extras item captioned **Newton Chat** is an older build without
opening it. This hardware install followed a single HTTP 200 response for the
19,040-byte package, with all 19,122 HTTP bytes acknowledged; ZC40 nevertheless
ended with its known-faulty `Install not confirmed` status.

The physical command/response gate passed on 2026-08-02. The MP2000 at
`10.42.0.114` held one TCP connection to Mars at `10.42.0.1:6801`; after the
user tapped **New**, Newton Chat sent `Hi`, the real Codex backend answered
`Hi! What can I help you with?`, and the response rendered on the Newton. The
first attempt exposed stale host state rather than a transport failure: Codex
could no longer resume the saved 2026-07-22 thread. The server sent a status
error followed by `PROMPT`, and A1 rendered a blank `Agent:` line. Tapping
**New** reset the host thread and made the next turn succeed without reconnecting
or reinstalling.

Newton Chat 2.4-a4 is current in source; the section below describes A3, which
A4 keeps unchanged apart from the Track F1 additions: `MSGP` splitting for long
prompts, a visible `NAK` status instead of a hung turn, and `FindBreak` in place
of `StrPos(text, Chr(13), 0)`, which raises `-48802` on this ROM and froze the
transcript at 640 characters (`docs/newton-dev-notes.md`, Track F1 round).

Newton Chat 2.3-a3 removes `protoInputLine`'s default
`oneLineOnly` justification and provides a 276-by-118-pixel prompt with four
visible 24-pixel handwriting lines. The transcript gives up 66 vertical pixels;
the status, New, and Send controls share one compact row. Its Extras label is
**Chat A3**, while the open window title remains **Newton Chat 2.3-a3**. A3 also
copies a host `STAT ERROR` payload into the transcript before `PROMPT`, avoiding
A1's blank `Agent:` result.

The final 19,184-byte A3 package has SHA-256
`ee5280dfc67b05b84e5a976ddb79b948ceefd162226bc3faa378b62debaa5736`.
An isolated Einstein run showed the four ruled lines and wrapped a long prompt
onto two of them. On the physical MP2000, ZC40 fetched it with one HTTP 200 and
Mars saw ACKs for all 19,266 HTTP bytes; the user confirmed that handwriting in
the larger field worked much better. The app then opened a live TCP connection
from `10.42.0.114` to Mars port 6801. Preserve A1 as fallback; A2 was an
emulator-only layout iteration and was never staged as the final package.

## Physical Dock-over-TCP backup

Dock TCP 1.2 is installed on the physical MP2000 and adds **TCP/IP** to the
ROM Dock application's connection popup. Its one-time preferences are desktop
`10.42.0.1` plus the working Mars/WaveLAN Internet Setup in the **Link** popup.
Newton error `-60037` means that selected NIE network is inactive; it is not a
host listener or Dante-handshake failure.

The first physical general-session attempt exposed a real host bug:
`runtime/newton_backup.py` sent synchronize session type 2 directly and the
Newton rejected it with `-28011`, “incompatible protocol.” The fixed client
uses setup session type 1, Dante protocol 10, the `dinf`/`ninf` capability
exchange, and the Newton-compatible DES password challenge before issuing any
store command. The empty-password vector is covered by the known result
`7cbe6fb757f31ac1`.

On 2026-08-03, read-only physical inventory succeeded for both **Internal** and
**Ultimate Newton**: 72 soups total. The final resumable export contains all
716 manifest entries as raw `.nsof` files, including `DEMO.BAS:NSBASIC`,
`SCRATCH.BAS:NSBASIC`, and `TEMPHTML:NewtsCape`. Long soup streaming was too
fragile on this Wi-Fi path, so dumps now request entries individually with
`rete`; `--resume` skips existing sequential files without overwriting them.
The complete ignored directory exists on both Mars and the local workspace at
`runtime/backups/mp2000-20260803-docktcp-a3`, with matching tree digest
`8203cc2de461b51b3b62380804b011b4c1b35df51dd32393f98f8a250265ebc2`.

The same path then backed up a second physical card in one uninterrupted
connection: a 16 MB CF card in a PC Card ATA adapter. Newton identified its
mounted store as **16 MB**, kind `ATA Store`. The store contained 5 soups and
49 entries: 1 OutBox entry, 48 Packages entries, and 3 empty soups. The complete
Internal-plus-card export has 40 soups and 417 raw entries at
`runtime/backups/mp2000-cf32-20260803-docktcp-a1` on both Mars and the local
workspace. The `cf32` text is a historical filename created before the physical
capacity was corrected; the card is 16 MB. Its matching tree digest is
`e7bab0732e39d936c6d3092aabacc7c6fcafa0de423e228628d02b829f1a6a13`;
the ignored 5,056,544-byte local archive has SHA-256
`5409b5ef0171bb80d97d0ebf16b878e848dcaa926e5b91d28e26a329a9e0ba1b`.

## Path toward ink and notes (not implemented in v1)

Keep the current view as the connection/status shell. A later version can add one Newton-native drawing/ink view and serialize completed strokes or selected Notes data into a bounded request body. Send one item at a time to a harness endpoint, wait for an explicit server acknowledgement, and retain the local item until acknowledged. That preserves the current small-memory, close-after-each-request transport and leaves batching, interpretation, and richer synchronization on the server. Do not add an ink abstraction or queue until the Newton APIs and payload format have been verified on-device.
